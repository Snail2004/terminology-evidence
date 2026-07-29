"""Build deterministic, zero-network adapter evidence outside the repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path

from integration_harness.adapter_v1.build import build_adapter_bundle
from integration_harness.adapter_v1.dataset import (
    OFFICIAL_MODE,
    SYNTHETIC_MODE,
    load_dataset_release,
)
from integration_harness.adapter_v1.producer import write_explicit_hold_set
from integration_harness.adapter_v1.replay import replay_adapter_bundle
from integration_harness.hashing import self_sha256, sha256_file
from integration_harness.jsonio import canonical_bytes, dump_json
from tests.system_integration.adapter_helpers import (
    make_producer_set,
    make_synthetic_dataset_release,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--issuer-commit", required=True)
    args = parser.parse_args()
    repo = args.repository_root.resolve()
    output = args.output_root.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    schema = repo / "docs" / "integration" / "artifact_inventory_50_150_schema.json"
    contracts = repo / "terminology_contracts_v1"
    official_root = (
        repo / "review_evidence" / "dataset" / "d2l-stage-a-official-5-sense-pilot-v1"
    )
    with tempfile.TemporaryDirectory(prefix="adapter-evidence-") as temp_name:
        temp = Path(temp_name)
        official_dataset = load_dataset_release(
            official_root / "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip",
            official_root / "official_dataset_input_pin_v1.json",
            git_receipt_path=official_root / "git_source_receipt.json",
            schema_root=contracts,
            mode=OFFICIAL_MODE,
            repository_root=repo,
        )
        official_context = write_explicit_hold_set(
            temp / "official-context-hold",
            role="context_evidence",
            candidates=official_dataset.candidates,
            reason_code="C_PACKAGE_SET_NOT_MAIN_ACCEPTED",
            issuer_commit=args.issuer_commit,
            run_id="official-5-15-adapter-preflight",
        )
        official_attestation = write_explicit_hold_set(
            temp / "official-attestation-hold",
            role="attestation_evidence",
            candidates=official_dataset.candidates,
            reason_code="E_PACKAGE_SET_NOT_MAIN_ACCEPTED",
            issuer_commit=args.issuer_commit,
            run_id="official-5-15-adapter-preflight",
        )
        official_out = output / "official_5_sense_15_candidate_preflight"
        official_result = build_adapter_bundle(
            dataset_zip=official_dataset.zip_path,
            dataset_pin=official_dataset.pin_path,
            dataset_git_receipt=official_dataset.git_receipt_path,
            context_set_manifest=official_context,
            attestation_set_manifest=official_attestation,
            contracts_root=contracts,
            repository_root=repo,
            output_root=official_out,
            adapter_mode=OFFICIAL_MODE,
            allowed_hold_roles=frozenset({"context_evidence", "attestation_evidence"}),
            inventory_schema_path=schema,
        )
        official_replay = replay_adapter_bundle(official_out, contracts_root=contracts, repository_root=repo)

        synthetic_source = make_synthetic_dataset_release(repo, temp / "synthetic-dataset")
        synthetic_dataset = load_dataset_release(
            synthetic_source["zip"],
            synthetic_source["pin"],
            git_receipt_path=None,
            schema_root=contracts,
            mode=SYNTHETIC_MODE,
        )
        synthetic_context = make_producer_set(
            repo,
            temp / "synthetic-context",
            candidates=synthetic_dataset.candidates,
            role="context_evidence",
            hold=False,
        )
        synthetic_attestation = make_producer_set(
            repo,
            temp / "synthetic-attestation",
            candidates=synthetic_dataset.candidates,
            role="attestation_evidence",
            hold=False,
        )
        synthetic_out = output / "synthetic_50_sense_150_candidate_conformance"
        synthetic_result = build_adapter_bundle(
            dataset_zip=synthetic_source["zip"],
            dataset_pin=synthetic_source["pin"],
            dataset_git_receipt=None,
            context_set_manifest=synthetic_context,
            attestation_set_manifest=synthetic_attestation,
            contracts_root=contracts,
            repository_root=repo,
            output_root=synthetic_out,
            adapter_mode=SYNTHETIC_MODE,
            inventory_schema_path=schema,
        )
        synthetic_replay = replay_adapter_bundle(synthetic_out, contracts_root=contracts)

    summary = {
        "schema_id": "HarnessDataset50150EvidenceSummaryV1",
        "schema_version": "1.0.0",
        "source_commit": args.issuer_commit,
        "official_5_15": {"build": official_result, "replay": official_replay},
        "synthetic_50_150": {"build": synthetic_result, "replay": synthetic_replay},
        "invariants": {
            "provider_calls": 0,
            "network_calls": 0,
            "auto_approved_count": 0,
            "certificate_count": 0,
            "final_glossary_decision": None,
            "global_execution_for_official": "HOLD_EXPLICIT_PRODUCER_PACKAGE",
            "synthetic_is_not_official": True,
        },
        "integrity": {},
    }
    summary["integrity"]["self_sha256"] = self_sha256(summary)
    dump_json(output / "HARNESS_DATASET_50_150_ADAPTER_SUMMARY_V1.json", summary)
    _zip_tree(official_out, output / "official_5_15_adapter_bundle.zip")
    _zip_tree(synthetic_out, output / "synthetic_50_150_adapter_bundle.zip")
    release = {
        "schema_id": "HarnessDataset50150EvidenceReleaseManifestV1",
        "schema_version": "1.0.0",
        "status": "PASS_WITH_OFFICIAL_C_E_HOLD",
        "files": {},
        "summary_self_sha256": summary["integrity"]["self_sha256"],
        "integrity": {},
    }
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"CHECKSUMS.sha256", "manifest.json"}:
            release["files"][path.relative_to(output).as_posix()] = {
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
    release["integrity"]["self_sha256"] = self_sha256(release)
    dump_json(output / "manifest.json", release)
    _write_checksums(output)
    print(json.dumps({"status": "PASS", "output": str(output), **summary["invariants"]}, ensure_ascii=False))
    return 0


def _zip_tree(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.name == "CHECKSUMS.sha256":
                continue
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes())


def _write_checksums(root: Path) -> None:
    lines = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    ]
    (root / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
