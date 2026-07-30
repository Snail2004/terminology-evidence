from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


CANDIDATE_ID = "candidate_479fdd8ff6d15304debec117"
PHASE_ID = "D0_ONE_CANDIDATE"
RUN_ID = "RUN-D0"
MAIN_REPOSITORY = Path(os.environ.get("D0_MAIN_REPOSITORY", r"C:\work\terminology_evidence"))
C_WORKTREE = Path(os.environ.get("D0_C_WORKTREE", str(MAIN_REPOSITORY)))
E_WORKTREE = Path(os.environ.get("D0_E_WORKTREE", str(MAIN_REPOSITORY)))
GLOBAL_WORKTREE = Path(os.environ.get("D0_GLOBAL_WORKTREE", str(MAIN_REPOSITORY)))
CONTRACT_PYTHON = MAIN_REPOSITORY / "terminology_contracts_v1" / "python"
CONTRACT_RECEIPT = (
    MAIN_REPOSITORY
    / "terminology_contracts_v1"
    / "release"
    / "v1.1.0-final"
    / "contracts_v1_1_0_authority_receipt_r2.json"
)
DEFAULT_CREDENTIALS = MAIN_REPOSITORY / "API-Key"
EXACT_GO_CONFIRMATION_SHA = hashlib.sha256(b"GO ONE-CANDIDATE API CANARY").hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def seal(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    integrity = result.setdefault("integrity", {})
    integrity.pop("self_sha256", None)
    integrity["self_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def verify_seal(value: Mapping[str, Any]) -> bool:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or not isinstance(integrity.get("self_sha256"), str):
        return False
    payload = copy.deepcopy(dict(value))
    payload["integrity"].pop("self_sha256", None)
    return hashlib.sha256(canonical(payload)).hexdigest() == integrity["self_sha256"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure_tls_ca(target: Path) -> str:
    import certifi
    import ssl

    parts = [Path(certifi.where()).resolve(strict=True).read_text(encoding="ascii")]
    seen: set[str] = set()
    for store in ("ROOT", "CA"):
        for certificate, encoding, _trust in ssl.enum_certificates(store):
            if encoding != "x509_asn":
                continue
            digest = hashlib.sha256(certificate).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            parts.append(ssl.DER_cert_to_PEM_cert(certificate))
    target.write_text("\n".join(parts), encoding="ascii", newline="\n")
    os.environ["SSL_CERT_FILE"] = str(target)
    os.environ["REQUESTS_CA_BUNDLE"] = str(target)
    return sha(target)


def now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime | None = None) -> str:
    return (value or now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise RuntimeError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(RuntimeError(f"non-finite JSON in {path}: {value}")),
    )
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def package_root(script: Path) -> Path:
    if (script.parent / "release" / "build-a" / "authority_pins.json").is_file():
        return script.parent / "release" / "build-a"
    if script.parent.name == "run" and (script.parent.parent / "authority_pins.json").is_file():
        return script.parent.parent
    raise RuntimeError("cannot locate pre-GO package root")


def safe_extract(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    seen: set[str] = set()
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            ref = Path(info.filename)
            key = info.filename.casefold()
            if info.is_dir() or ref.is_absolute() or ".." in ref.parts or key in seen:
                raise RuntimeError(f"unsafe ZIP member: {info.filename}")
            seen.add(key)
            destination = target.joinpath(*ref.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(info))


def reuse_acquired_corpus(source: Path, target: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    summary = load_json(source / "summary.json")
    receipt = load_json(source / "acquisition_receipt.json")
    if not verify_seal(summary) or not verify_seal(receipt):
        raise RuntimeError("reused corpus receipt or summary self hash mismatch")
    if (
        summary.get("status") != "ACQUISITION_COMPLETE"
        or summary.get("candidate_id") != CANDIDATE_ID
        or summary.get("provider_calls") != 0
        or summary.get("gold_access") != 0
        or receipt.get("mode") != "LIVE_AUTHORIZED"
    ):
        raise RuntimeError("reused corpus authority boundary mismatch")
    rows = receipt.get("rows")
    if not isinstance(rows, list) or len(rows) != summary.get("document_count") or not rows:
        raise RuntimeError("reused corpus inventory mismatch")
    for row in rows:
        ref = row.get("file_ref")
        if not isinstance(ref, str) or Path(ref).name != ref:
            raise RuntimeError("unsafe reused corpus file reference")
        path = source / "source" / ref
        expected = ref.rsplit("-", 1)[-1].split(".", 1)[0]
        if not path.is_file() or path.is_symlink() or sha(path) != expected:
            raise RuntimeError("reused corpus file hash mismatch")
    if not (source / "acquisition_ledger.jsonl").is_file():
        raise RuntimeError("reused corpus ledger is missing")
    shutil.copytree(source, target)
    return summary


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    log_root: Path,
    label: str,
    timeout: int,
) -> None:
    result = subprocess.run(command, cwd=cwd, env=dict(env), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    log_root.mkdir(parents=True, exist_ok=True)
    (log_root / f"{label}.stdout.log").write_text(result.stdout, encoding="utf-8", newline="\n")
    (log_root / f"{label}.stderr.log").write_text(result.stderr, encoding="utf-8", newline="\n")
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def seal_execution_output(output: Path, status: Mapping[str, Any]) -> None:
    control = output / "control"
    c_run_path = output / "c" / "c01_canary_run.json"
    e_run_path = output / "e" / "runs" / RUN_ID / "run.json"
    corpus_path = output / "corpus_acquisition" / "summary.json"
    c_run = load_json(c_run_path) if c_run_path.is_file() else None
    e_run = load_json(e_run_path) if e_run_path.is_file() else None
    corpus = load_json(corpus_path) if corpus_path.is_file() else None
    decision_paths = sorted(
        (output / "global" / "runs").rglob("global_decision_package.json")
    )
    if status["status"] == "ONE_CANDIDATE_CANARY_COMPLETED" and len(decision_paths) != 1:
        raise RuntimeError("completed canary must contain exactly one Global decision package")
    global_decision = load_json(decision_paths[0]) if len(decision_paths) == 1 else None
    metrics = seal({
        "schema_id": "D0OneCandidateCanaryMetricsSummaryV1",
        "schema_version": "1.0.0",
        "status": status["status"],
        "candidate_id": CANDIDATE_ID,
        "phase_id": PHASE_ID,
        "c_usage": None if c_run is None else c_run.get("usage"),
        "e_usage": None if e_run is None else e_run.get("usage"),
        "e_provider_calls": None if e_run is None else e_run.get("provider_calls"),
        "e_network_calls": None if e_run is None else e_run.get("network_calls"),
        "corpus_network_requests": None if corpus is None else corpus.get("network_request_count"),
        "global_development_decision": None if global_decision is None else global_decision.get("decision"),
        "global_approval_score": None if global_decision is None else global_decision.get("approval_score"),
        "global_decision_self_sha256": None if global_decision is None else global_decision.get("integrity", {}).get("self_sha256"),
        "global_decision_reasons": [] if global_decision is None else global_decision.get("decision_reasons", []),
        "token_accounting_mode": "TOKEN_ONLY",
        "cost": None,
        "currency": None,
        "cost_status": "TOKEN_ONLY_COST_UNAVAILABLE",
        "gold_access": 0,
        "final_glossary_decision": None,
        "integrity": {},
    })
    metrics_path = control / "canary_metrics_summary.json"
    write_json(metrics_path, metrics)
    excluded = {"artifact_manifest.json", "CHECKSUMS.sha256", "run_stop_receipt.json"}
    files = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name not in excluded and "credentials" not in path.name.casefold()
    )
    manifest = seal({
        "schema_id": "D0OneCandidateCanaryArtifactManifestV1",
        "schema_version": "1.0.0",
        "status": status["status"],
        "candidate_id": CANDIDATE_ID,
        "files": [
            {"path": path.relative_to(output).as_posix(), "sha256": sha(path), "size": path.stat().st_size}
            for path in files
        ],
        "secret_files_included": False,
        "gold_access": 0,
        "final_glossary_decision": None,
        "integrity": {},
    })
    manifest_path = control / "artifact_manifest.json"
    write_json(manifest_path, manifest)
    live_path = control / "live_authorization_receipt.json"
    start_path = control / "run_start_receipt.json"
    if live_path.is_file() and start_path.is_file():
        live = load_json(live_path)
        start = load_json(start_path)
        ledger_candidates = [
            output / "e" / "runs" / RUN_ID / "events.jsonl",
            output / "c" / "ledger" / "provider_attempts.jsonl",
            control / "execution_status.json",
        ]
        ledger = next(path for path in ledger_candidates if path.is_file())
        stop = seal({
            "schema_id": "LiveRunStopReceiptV1_1",
            "schema_version": "1.1.0-draft.4",
            "receipt_id": "main-d0-one-candidate-run-stop-v1",
            "phase_id": PHASE_ID,
            "issued_at": timestamp(),
            "terminal_status": "COMPLETED" if status["status"] == "ONE_CANDIDATE_CANARY_COMPLETED" else "STOPPED",
            "stop_reason": "CANARY_COMPLETE" if status["status"] == "ONE_CANDIDATE_CANARY_COMPLETED" else str(status.get("stop_reason", "EXECUTION_STOP")),
            "authorization_receipt_self_sha256": live["integrity"]["self_sha256"],
            "run_start_receipt_self_sha256": start["integrity"]["self_sha256"],
            "final_ledger_head_sha256": sha(ledger),
            "usage_snapshot_self_sha256": metrics["integrity"]["self_sha256"],
            "usage_snapshot_physical_sha256": sha(metrics_path),
            "preserved_artifact_manifest_sha256": manifest["integrity"]["self_sha256"],
            "integrity": {},
        })
        write_json(control / "run_stop_receipt.json", stop)
    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "CHECKSUMS.sha256")
    (output / "CHECKSUMS.sha256").write_text(
        "\n".join(f"{sha(path)}  {path.relative_to(output).as_posix()}" for path in files) + "\n",
        encoding="ascii",
    )


def validate_go(path: Path, pins: Mapping[str, Any]) -> dict[str, Any]:
    value = load_json(path)
    if not verify_seal(value):
        raise RuntimeError("user GO receipt self hash mismatch")
    required = {
        "schema_id": "MainUserGoReceiptV1",
        "schema_version": "1.0.0",
        "status": "USER_GO_CONFIRMED",
        "candidate_id": CANDIDATE_ID,
        "phase_id": PHASE_ID,
        "run_id": RUN_ID,
        "confirmation_statement_sha256": EXACT_GO_CONFIRMATION_SHA,
        "corpus_authorization_self_sha256": pins["corpus_authorization_self_sha256"],
        "corpus_authority_package_sha256": pins["corpus_acquisition_package_sha256"],
        "draft4_final_authority_self_sha256": pins["draft4_final_authority_self_sha256"],
        "corpus_acquisition_authorized": True,
        "one_candidate_api_canary_authorized": True,
        "remainder_authorized": False,
        "gold_access": 0,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise RuntimeError(f"user GO receipt mismatch: {key}")
    current = now()
    valid_until = datetime.fromisoformat(str(value["valid_until"]).replace("Z", "+00:00"))
    issued_at = datetime.fromisoformat(str(value["issued_at"]).replace("Z", "+00:00"))
    if not issued_at <= current <= valid_until:
        raise RuntimeError("user GO receipt is outside validity")
    return value


def secret_readiness(credentials: Path) -> dict[str, Any]:
    required = ["CKEY.txt", "GEMINI-KEY.txt", "LOCAL-GPT-GATEWAY.txt"]
    rows = []
    for name in required:
        path = credentials / name
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"required credential is unavailable: {name}")
        rows.append({"name": name, "present": True, "nonempty": True})
    return seal({
        "schema_id": "MainSecretReadinessReceiptV1",
        "schema_version": "1.0.0",
        "status": "READY_FOR_ONE_CANDIDATE_CANARY",
        "candidate_id": CANDIDATE_ID,
        "credential_files": rows,
        "secret_values_excluded": True,
        "secret_hashes_excluded": True,
        "provider_key_values_logged": False,
        "issued_at": timestamp(),
        "integrity": {},
    })


def old_authorities(e05: Any, pins: Mapping[str, Any]) -> dict[str, Any]:
    values = copy.deepcopy(e05.authorization_receipt["bindings"]["pre_acquisition_authorities"])
    values.update({
        "e_release_commit": pins["e_authority_commit"],
        "e_release_tree_git_oid": pins["e_authority_tree"],
        "e_release_manifest_self_sha256": pins["e_adapter_manifest_self_sha256"],
        "e_release_zip_physical_sha256": pins["e_adapter_package_sha256"],
        "protocol_authority_self_sha256": pins["draft4_final_authority_self_sha256"],
        "protocol_authority_physical_sha256": pins["draft4_final_authority_physical_sha256"],
    })
    return values


def token_authorities(e05: Any, pins: Mapping[str, Any]) -> dict[str, Any]:
    values = old_authorities(e05, pins)
    values.update({
        "token_accounting_authority_self_sha256": pins["main_token_authority_self_sha256"],
        "token_accounting_authority_physical_sha256": pins["main_token_authority_physical_sha256"],
        "token_accounting_acceptance_anchor_self_sha256": pins["main_token_anchor_self_sha256"],
        "token_accounting_acceptance_anchor_physical_sha256": pins["main_token_anchor_physical_sha256"],
    })
    return values


def create_run_authorities(
    *,
    root: Path,
    pins: Mapping[str, Any],
    e05: Any,
    registry_self: str,
    snapshot_self: str,
    retrieval_self: str,
    query_self: str,
    secret_path: Path,
    final_receipt_path: Path,
) -> tuple[Path, Path, Path]:
    budget = load_json(root / "run" / "TOKEN_ONLY_BUDGET.json")
    if not verify_seal(budget):
        raise RuntimeError("token-only budget self hash mismatch")
    budget_self = budget["integrity"]["self_sha256"]
    secret = load_json(secret_path)
    common = {
        "phase_authorized_candidate_set_self_sha256": pins["phase_candidate_set_self_sha256"],
        "phase_authorized_candidate_set_physical_sha256": pins["phase_candidate_set_physical_sha256"],
        "c_role_plan_self_sha256": pins["c_role_plan_self_sha256"],
        "c_role_plan_physical_sha256": pins["c_role_plan_physical_sha256"],
        "e_registry_sha256": registry_self,
        "e_corpus_sha256": snapshot_self,
        "e_retrieval_policy_sha256": retrieval_self,
        "query_template_set_sha256": query_self,
        # Historical field name; it binds the exact reviewed controlled discovery authority.
        "brave_plan_terms_receipt_sha256": pins["corpus_authorization_self_sha256"],
    }
    run_spec = seal({
        "schema_id": "LivePhaseRunSpecV1_1",
        "schema_version": "1.1.0-draft.4",
        "phase_id": PHASE_ID,
        "run_id": RUN_ID,
        **common,
        "budget_spec_sha256": budget_self,
        "secret_readiness_receipt_sha256": sha(secret_path),
        "secret_readiness_receipt_self_sha256": secret["integrity"]["self_sha256"],
        "prior_gate_receipt_sha256": pins["e_adapter_acceptance_physical_sha256"],
        "pre_acquisition_authorities": token_authorities(e05, pins),
        "integrity": {},
    })
    run_spec_path = secret_path.parent / "live_phase_run_spec.json"
    write_json(run_spec_path, run_spec)
    current = now()
    final_receipt = load_json(final_receipt_path)
    live = seal({
        "schema_id": "LiveAuthorizationReceiptV1_1",
        "schema_version": "1.1.0-draft.4",
        "receipt_id": "main-d0-one-candidate-live-authorization-v1",
        "authorization_status": "RUN_AUTHORIZED",
        "test_only": False,
        "phase_id": PHASE_ID,
        "issued_at": timestamp(current),
        "valid_from": timestamp(current - timedelta(minutes=2)),
        "valid_until": timestamp(current + timedelta(hours=6)),
        "issuer_id": final_receipt["issuer_id"],
        "authority_id": final_receipt["authority_id"],
        "approval_artifact_self_sha256": pins["draft4_final_authority_self_sha256"],
        "approval_artifact_physical_sha256": pins["draft4_final_authority_physical_sha256"],
        "protocol_commit": pins["draft4_commit"],
        "protocol_tree_git_oid": pins["draft4_tree"],
        "bindings": {
            "run_spec_self_sha256": run_spec["integrity"]["self_sha256"],
            "run_spec_physical_sha256": sha(run_spec_path),
            **common,
            "pre_acquisition_authorities": old_authorities(e05, pins),
        },
        "budget_spec_sha256": budget_self,
        "secret_readiness_receipt_sha256": sha(secret_path),
        "secret_readiness_receipt_self_sha256": secret["integrity"]["self_sha256"],
        "prior_gate_receipt_sha256": pins["e_adapter_acceptance_physical_sha256"],
        "integrity": {},
    })
    live_path = secret_path.parent / "live_authorization_receipt.json"
    write_json(live_path, live)
    start = seal({
        "schema_id": "LiveRunStartReceiptV1_1",
        "schema_version": "1.1.0-draft.4",
        "receipt_id": "main-d0-one-candidate-run-start-v1",
        "phase_id": PHASE_ID,
        "issued_at": timestamp(),
        "authorization_receipt_self_sha256": live["integrity"]["self_sha256"],
        "authorization_receipt_physical_sha256": sha(live_path),
        "run_spec_self_sha256": run_spec["integrity"]["self_sha256"],
        "run_spec_physical_sha256": sha(run_spec_path),
        "phase_authorized_candidate_set_self_sha256": pins["phase_candidate_set_self_sha256"],
        "phase_authorized_candidate_set_physical_sha256": pins["phase_candidate_set_physical_sha256"],
        "budget_spec_sha256": budget_self,
        "secret_readiness_receipt_sha256": sha(secret_path),
        "secret_readiness_receipt_self_sha256": secret["integrity"]["self_sha256"],
        "initial_ledger_head": None,
        "integrity": {},
    })
    start_path = secret_path.parent / "run_start_receipt.json"
    write_json(start_path, start)
    return run_spec_path, live_path, start_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute the exact D0 one-candidate canary after explicit user GO.")
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--go-receipt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--credentials-root", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--reuse-corpus-output", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    root = (args.package_root or package_root(Path(__file__).resolve())).resolve(strict=True)
    pins = load_json(root / "authority_pins.json")
    go = validate_go(args.go_receipt.resolve(strict=True), pins)
    if not args.execute:
        print(json.dumps({"status": "USER_GO_RECEIPT_VALID_BUT_EXECUTE_FLAG_ABSENT", "candidate_id": CANDIDATE_ID, "provider_calls": 0, "network_calls": 0}, sort_keys=True))
        return 2
    output = args.output_root.absolute()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("live output root must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    control = output / "control"
    logs = output / "logs"
    control.mkdir()
    tls_ca_bundle_sha256 = configure_tls_ca(control / "tls_ca_bundle.pem")
    write_json(control / "user_go_receipt.json", go)
    secret = secret_readiness(args.credentials_root.resolve(strict=True))
    secret_path = control / "secret_readiness_receipt.json"
    write_json(secret_path, secret)
    status = {
        "schema_id": "D0OneCandidateCanaryExecutionStatusV1",
        "schema_version": "1.0.0",
        "candidate_id": CANDIDATE_ID,
        "phase_id": PHASE_ID,
        "status": "RUNNING",
        "completed_stages": [],
        "provider_calls": 0,
        "network_calls": 0,
        "gold_access": 0,
        "tls_ca_bundle_sha256": tls_ca_bundle_sha256,
        "final_glossary_decision": None,
    }
    write_json(control / "execution_status.json", status)
    try:
        draft4_extract = output / "control" / "draft4_final_authority"
        safe_extract(root / "authorities" / "draft4_final_authority.zip", draft4_extract)
        corpus_runner_extract = output / "control" / "corpus_authority"
        safe_extract(root / "authorities" / "corpus_acquisition_authority.zip", corpus_runner_extract)
        corpus_output = output / "corpus_acquisition"
        env_e = dict(os.environ)
        env_e["PYTHONPATH"] = str(E_WORKTREE)
        env_e["E05_TOKEN_ACCOUNTING_PACKAGE"] = str(root / "authorities" / "main_token_accounting.zip")
        env_e["E05_DRAFT4_TOKEN_SCHEMA_ROOT"] = str(root / "protocol")
        if args.reuse_corpus_output is not None:
            reuse_acquired_corpus(args.reuse_corpus_output, corpus_output)
            status["completed_stages"].append("CORPUS_ACQUISITION_REUSED")
        else:
            run_command(
                [sys.executable, "-B", str(corpus_runner_extract / "acquire_canary_corpus.py"),
                 "--authorization", str(corpus_runner_extract / "main_corpus_acquisition_authorization_v1.json"),
                 "--user-go-receipt", str(args.go_receipt.resolve()),
                 "--source-governance-package", str(root / "authorities" / "source_governance.zip"),
                 "--output-root", str(corpus_output)],
                cwd=E_WORKTREE, env=env_e, log_root=logs, label="corpus_acquisition", timeout=600,
            )
            status["completed_stages"].append("CORPUS_ACQUISITION")

        sys.path.insert(0, str(E_WORKTREE))
        from vietnamese_attestation.v1.live.authority_adapter.e05 import load_e05_exact_integration_inputs
        from vietnamese_attestation.v1.live.authority_adapter.final_canary import load_final_canary_authority_inputs, load_future_live_authorization_receipt
        from vietnamese_attestation.v1.live.authority_adapter.source_governance import load_runtime_registry_projection
        from vietnamese_attestation.v1.live.common import load_object
        from vietnamese_attestation.v1.live.policies import make_aggregation_policy, make_budget, make_query_template_set, make_retrieval_policy, validate_policy_bundle
        from vietnamese_attestation.v1.live.provider_adapters.gemini_official import GeminiOfficialAdapter
        from vietnamese_attestation.v1.live.service import ELiveService, make_run_request
        from vietnamese_attestation.v1.live.snapshot import build_snapshot, verify_snapshot

        e05 = load_e05_exact_integration_inputs(root / "inputs" / "e05_delivery.zip")
        projection = load_runtime_registry_projection(root / "authorities" / "source_governance.zip")
        retrieval = make_retrieval_policy(max_queries_per_candidate=2, max_direct_fetches=5, max_redirect_hops=3, max_fetch_retries=2, max_download_bytes=15_000_000, max_accepted_documents=5, network_mode="LIVE_AUTHORIZED")
        queries = make_query_template_set(max_queries=2)
        aggregation = make_aggregation_policy()
        policies = {"retrieval_policy": retrieval, "query_template_set": queries, "provider_role_plan": e05.provider_role_plan, "aggregation_policy": aggregation}
        policy_hashes = validate_policy_bundle(policies)
        acquisition_receipt_path = corpus_output / "acquisition_receipt.json"
        snapshot_root = output / "e" / "live_snapshot"
        build_snapshot(
            corpus_output / "source", snapshot_root,
            registry=projection.registry,
            retrieval_policy=retrieval,
            acquisition_receipt=load_object(acquisition_receipt_path),
            producer_commit=pins["e_authority_commit"],
            producer_tree=pins["e_authority_tree"],
            acquisition_receipt_source=acquisition_receipt_path,
            corpus_authority_package_path=root / "authorities" / "corpus_acquisition_authority.zip",
            draft4_final_authority_package_path=root / "authorities" / "draft4_final_authority.zip",
            source_governance_package_path=root / "authorities" / "source_governance.zip",
        )
        snapshot = verify_snapshot(snapshot_root)
        status["completed_stages"].append("E_LIVE_SNAPSHOT")

        bridge_root = output / "control" / "global_contract_bridge"
        safe_extract(root / "authorities" / "global_contract_bridge.zip", bridge_root)
        frozen_path = bridge_root / "contracts" / "frozen_candidate.json"
        frozen = load_json(frozen_path)
        run_spec_path, live_path, start_path = create_run_authorities(
            root=root, pins=pins, e05=e05,
            registry_self=projection.registry["integrity"]["self_sha256"],
            snapshot_self=snapshot["integrity"]["self_sha256"],
            retrieval_self=policy_hashes["retrieval_policy"], query_self=policy_hashes["query_template_set"],
            secret_path=secret_path,
            final_receipt_path=draft4_extract / "draft4_final_authority_receipt_v1.json",
        )
        final = load_final_canary_authority_inputs(root / "authorities" / "corpus_acquisition_authority.zip", root / "authorities" / "draft4_final_authority.zip")
        load_future_live_authorization_receipt(
            live_path, inputs=e05, final_authority=final,
            registry_self_sha256=projection.registry["integrity"]["self_sha256"],
            snapshot_self_sha256=snapshot["integrity"]["self_sha256"],
            retrieval_policy_sha256=policy_hashes["retrieval_policy"],
            query_template_set_sha256=policy_hashes["query_template_set"],
        )
        status["completed_stages"].append("LIVE_AUTHORIZATION_VALIDATED")

        env_c = dict(os.environ)
        env_c["PYTHONPATH"] = str(C_WORKTREE)
        c_root = output / "c"
        c_ledger = c_root / "ledger"
        c_run = c_root / "c01_canary_run.json"
        run_command(
            [sys.executable, "-B", "-m", "context_substitution.v2", "context-run",
             "--input", str(root / "inputs" / "c_runtime_input.json"),
             "--provider-catalog", str(root / "inputs" / "c_provider_catalog.json"),
             "--provider-role-plan", str(root / "inputs" / "c_provider_role_plan.json"),
             "--provider-role-plan-sha256", pins["c_role_plan_physical_sha256"],
             "--credentials-root", str(args.credentials_root.resolve()),
             "--ledger-root", str(c_ledger), "--output", str(c_run),
             "--candidate-target-id", CANDIDATE_ID, "--evaluation-mode", "DEVELOPMENT", "--allow-api"],
            cwd=C_WORKTREE, env=env_c, log_root=logs, label="c_context_run", timeout=3600,
        )
        run_command([sys.executable, "-B", "-m", "context_substitution.v2", "run-validate", "--run", str(c_run)], cwd=C_WORKTREE, env=env_c, log_root=logs, label="c_run_validate", timeout=120)
        bridge_set = seal({
            "schema_id": "DatasetFrozenCandidateSetV1", "schema_version": "1.0.0",
            "status": "COMPLETE_IMMUTABLE", "authority_owner": "MAIN_DEVELOPMENT_CANARY_ADAPTER",
            "candidate_count": 1, "candidates": [frozen], "final_glossary_decision": None, "integrity": {},
        })
        bridge_set_path = bridge_root / "bridge_frozen_candidate_set.json"
        write_json(bridge_set_path, bridge_set)
        c_packages = c_root / "context_evidence_packages"
        run_command(
            [sys.executable, "-B", "-m", "context_substitution.v2", "project-context-evidence",
             "--run", str(c_run), "--frozen-candidates", str(bridge_set_path),
             "--ledger", str(c_ledger / "provider_attempts.jsonl"), "--output-directory", str(c_packages)],
            cwd=C_WORKTREE, env=env_c, log_root=logs, label="c_project_context_evidence", timeout=300,
        )
        status["completed_stages"].append("C_CONTEXT_EVIDENCE")

        gemini_key = (args.credentials_root / "GEMINI-KEY.txt").read_text(encoding="utf-8").strip()
        adapter = GeminiOfficialAdapter(role_plan=e05.provider_role_plan, api_key=gemini_key, token_accounting_authority=e05.token_accounting)
        budget = make_budget(max_semantic_calls=8, max_physical_requests=16)
        candidate_key = frozen["candidate_key"]
        request = make_run_request(
            run_id=RUN_ID, phase_id=PHASE_ID, sense_id=candidate_key["sense_id"], candidate_id=CANDIDATE_ID,
            term_en=candidate_key["source_term"], candidate_vi=candidate_key["candidate_vi"],
            sense_definition=frozen["effective_definition_en"],
            domain={"scope_id": candidate_key["scope_id"], "anchors": frozen["domain_profile"]["anchors_vi"] or [candidate_key["candidate_vi"]]},
            candidate_variants=list(dict.fromkeys([*frozen.get("alternatives_vi", []), *frozen["surfaces"].get("validated_variants_vi", [])])),
            authority_refs={
                "cohort_id": "producer-safe-ev02-cohort-authority-v1",
                "registry_self_sha256": projection.registry["integrity"]["self_sha256"],
                "snapshot_manifest_sha256": snapshot["integrity"]["self_sha256"],
                "candidate_key": candidate_key,
                "input_contract_sha256": frozen["input_contract_sha256"],
            },
            budget=budget, policy_hashes=policy_hashes,
            query_template_ids=("exact_candidate", "candidate_definition"),
        )
        constructor = inspect.signature(ELiveService.__init__).parameters
        if "frozen_candidate_contract_path" not in constructor:
            raise RuntimeError("E production FrozenCandidate join child is not active")
        service = ELiveService(
            root=output / "e", registry=projection.registry, snapshot_root=snapshot_root,
            policy_bundle=policies, authorization_receipt={},
            authorized_cohort_id="producer-safe-ev02-cohort-authority-v1",
            authorized_candidate_ids=[CANDIDATE_ID], execution_mode="PRODUCTION_AUTHORITY",
            e05_delivery_path=root / "inputs" / "e05_delivery.zip",
            source_governance_package_path=root / "authorities" / "source_governance.zip",
            corpus_authority_package_path=root / "authorities" / "corpus_acquisition_authority.zip",
            draft4_final_authority_package_path=root / "authorities" / "draft4_final_authority.zip",
            live_authorization_receipt_path=live_path,
            frozen_candidate_contract_path=frozen_path,
            provider_adapter=adapter,
        )
        e_result = service.create_run(request)
        write_json(output / "e" / "service_result.json", e_result)
        service.replay(RUN_ID)
        status["completed_stages"].append("E_ATTESTATION_EVIDENCE")

        context_package = next((c_packages / "packages").glob("*.json"))
        attestation_package = output / "e" / "runs" / RUN_ID / "attestation_package.json"
        sys.path.insert(0, str(CONTRACT_PYTHON))
        from terminology_contracts.bindings import seal_frozen_candidate_contract
        from terminology_contracts.validation import validate_instance

        effective_original = load_json(bridge_root / "contracts" / "effective_sense.json")
        frozen_original = load_json(frozen_path)
        constraint_original = load_json(bridge_root / "contracts" / "constraint_evidence.json")
        context_original = load_json(context_package)
        attestation_original = load_json(attestation_package)
        join_root = output / "global" / "development_join_projection"

        diagnostics = attestation_original.get("diagnostics")
        if not isinstance(diagnostics, dict):
            raise RuntimeError("E diagnostics must be an object")
        internal_diagnostics = {}
        for field in (
            "positive_eligible_count",
            "supporting_eligible_count",
            "ineligible_count",
        ):
            if field in diagnostics:
                internal_diagnostics[field] = diagnostics.pop(field)
        if set(diagnostics) != {"strong_positive_cluster_count", "conflict_ratio"}:
            raise RuntimeError("E diagnostics do not match Contracts V1.1")
        attestation_original = seal(attestation_original)
        write_json(
            join_root / "e_internal_diagnostics.json",
            seal({
                "schema_id": "EInternalDiagnosticsPreservationV1",
                "schema_version": "1.0.0",
                "candidate_id": CANDIDATE_ID,
                "fields": internal_diagnostics,
                "integrity": {},
            }),
        )

        frozen_projected = copy.deepcopy(frozen_original)
        frozen_projected["domain_profile"] = copy.deepcopy(effective_original["domain_profile"])
        frozen_projected = seal_frozen_candidate_contract(frozen_projected)
        projected_input_hash = frozen_projected["input_contract_sha256"]

        def project_input_binding(value: dict[str, Any]) -> dict[str, Any]:
            result = copy.deepcopy(value)
            result["input_contract_sha256"] = projected_input_hash
            provenance = result.get("provenance")
            if isinstance(provenance, dict):
                source_hashes = provenance.get("source_artifact_hashes")
                if isinstance(source_hashes, dict) and "input_contract" in source_hashes:
                    source_hashes["input_contract"] = projected_input_hash
            return seal(result)

        global_artifacts = {
            "effective_sense.json": effective_original,
            "frozen_candidate.json": frozen_projected,
            "constraint_evidence.json": project_input_binding(constraint_original),
            "context_evidence.json": project_input_binding(context_original),
            "attestation_evidence.json": project_input_binding(attestation_original),
        }
        for name, artifact in global_artifacts.items():
            errors = validate_instance(
                artifact, MAIN_REPOSITORY / "terminology_contracts_v1" / "schemas"
            )
            if errors:
                raise RuntimeError(
                    f"Global development join projection {name} is invalid: "
                    + "; ".join(errors)
                )
            write_json(join_root / name, artifact)

        global_input = output / "global" / "global_input.json"
        global_env = dict(os.environ)
        global_env["PYTHONPATH"] = os.pathsep.join([str(GLOBAL_WORKTREE), str(CONTRACT_PYTHON)])
        common = ["--repository-root", str(MAIN_REPOSITORY), "--authority-receipt", str(CONTRACT_RECEIPT)]
        run_command(
            [sys.executable, "-B", "-m", "global_validator.v1.cli", "assemble-input", *common,
             "--effective-sense", str(join_root / "effective_sense.json"),
             "--frozen-candidate", str(join_root / "frozen_candidate.json"), "--constraints", str(join_root / "constraint_evidence.json"),
             "--context-evidence", str(join_root / "context_evidence.json"), "--attestation-evidence", str(join_root / "attestation_evidence.json"),
             "--assembled-at", timestamp(), "--output", str(global_input)],
            cwd=GLOBAL_WORKTREE, env=global_env, log_root=logs, label="global_assemble", timeout=300,
        )
        run_command(
            [sys.executable, "-B", "-m", "global_validator.v1.cli", "run", *common,
             "--input", str(global_input), "--mode", "DEVELOPMENT_HEURISTIC", "--output-dir", str(output / "global" / "runs"),
             "--run-id", "D0-ONE-CANDIDATE-GLOBAL", "--started-at", timestamp(), "--completed-at", timestamp(),
             "--certificate-issued-at", timestamp()],
            cwd=GLOBAL_WORKTREE, env=global_env, log_root=logs, label="global_run", timeout=300,
        )
        status["completed_stages"].append("GLOBAL_DEVELOPMENT")
        status["status"] = "ONE_CANDIDATE_CANARY_COMPLETED"
    except Exception as exc:
        status["status"] = "STOPPED"
        status["stop_reason"] = type(exc).__name__
        status["stop_message"] = str(exc)
        (logs / "main_exception.log").parent.mkdir(parents=True, exist_ok=True)
        (logs / "main_exception.log").write_text(traceback.format_exc(), encoding="utf-8", newline="\n")
        write_json(control / "execution_status.json", status)
        seal_execution_output(output, status)
        raise
    write_json(control / "execution_status.json", status)
    seal_execution_output(output, status)
    print(json.dumps({"status": status["status"], "candidate_id": CANDIDATE_ID, "output_root": str(output), "gold_access": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
