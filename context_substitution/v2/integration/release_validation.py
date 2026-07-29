from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from context_substitution.v2.contracts.input import validate_context_substitution_input
from context_substitution.v2.contracts.run import validate_context_substitution_run
from context_substitution.v2.dataset.reviewed_support import (
    validate_reviewed_support_receipt,
)
from context_substitution.v2.integration.authority import (
    AUTHORITY_COMMIT,
    AUTHORITY_TAG,
    CONTRACT_MANIFEST_SHA256,
    validate_authority,
    validate_authority_receipt,
    validate_official_contract,
    verify_frozen_candidate_binding,
)
from context_substitution.v2.integration.common import (
    file_sha256,
    object_sha256,
)
from context_substitution.v2.integration.ledger_binding import (
    build_provider_ledger_manifest,
)
from context_substitution.v2.integration.projection import (
    PACKAGE_SET_COMPLETE_STATUS,
    PACKAGE_SET_SCHEMA_ID,
    PACKAGE_SET_SCHEMA_VERSION,
    PROJECTION_REPORT_SCHEMA_ID,
    PROJECTION_REPORT_SCHEMA_VERSION,
)


DATASET_FROZEN_SET_SCHEMA_ID = "DatasetFrozenCandidateSetV1"
DATASET_FROZEN_SET_SCHEMA_VERSION = "1.0.0"


def validate_integration_evidence(
    *,
    evidence_root: Path,
    junit_summary: Mapping[str, int],
    authority_receipt_path: Path,
    expected_allowed_skips: int = 0,
) -> dict[str, Any]:
    root = Path(evidence_root).resolve()
    _validate_junit(junit_summary, expected_allowed_skips=expected_allowed_skips)
    authority = validate_authority()
    authority_receipt = validate_authority_receipt(authority_receipt_path)

    input_payload = validate_context_substitution_input(_load(root / "pilot_input.json"))
    run = validate_context_substitution_run(_load(root / "fake_run.json"))
    if run["input_sha256"] != input_payload["integrity"]["input_sha256"]:
        raise ValueError("fake run is bound to another Context Substitution input")

    adapter = _verify_nested_self_hash(
        _load(root / "pilot_adapter_receipt.json"), "receipt_sha256"
    )
    runtime = validate_reviewed_support_receipt(
        _load(root / "pilot_runtime_receipt.json")
    )
    summary = _verify_nested_self_hash(
        _load(root / "pilot_zero_api_summary.json"), "summary_sha256"
    )
    replay = _verify_nested_self_hash(
        _load(root / "replay_report.json"), "report_sha256"
    )
    _validate_zero_api_receipts(
        adapter=adapter,
        runtime=runtime,
        summary=summary,
        replay=replay,
        input_payload=input_payload,
        run=run,
    )

    ledger_manifest = build_provider_ledger_manifest(
        run_payload=run,
        ledger_path=root / "fake_ledger" / "provider_attempts.jsonl",
    )
    frozen = _validate_dataset_frozen_set(
        _load(root / "frozen_candidates.json"), run=run
    )
    package_root = root / "context_evidence_packages"
    package_manifest = _verify_nested_self_hash(
        _load(package_root / "manifest.json"), "manifest_sha256"
    )
    projection_report = _verify_nested_self_hash(
        _load(package_root / "projection_report.json"), "report_sha256"
    )
    packages = _validate_packages(
        package_root=package_root,
        manifest=package_manifest,
        frozen_candidates=frozen,
        run=run,
        ledger_manifest=ledger_manifest,
    )
    _validate_projection_report(
        projection_report,
        package_manifest=package_manifest,
        packages=packages,
        run=run,
        ledger_manifest=ledger_manifest,
    )
    return {
        "status": "PASS",
        "authority": authority,
        "authority_receipt_self_sha256": authority_receipt["integrity"]["self_sha256"],
        "authority_receipt_physical_sha256": authority_receipt["physical_sha256"],
        "source_input_sha256": run["input_sha256"],
        "source_run_sha256": run["integrity"]["run_sha256"],
        "provider_attempt_count": len(run["provider_attempts"]),
        "provider_ledger_manifest": ledger_manifest,
        "package_count": len(packages),
        "package_manifest_sha256": package_manifest["integrity"]["manifest_sha256"],
        "projection_report_sha256": projection_report["integrity"]["report_sha256"],
        "provider_call_count": 0,
        "final_glossary_decision": None,
    }


def _validate_junit(
    value: Mapping[str, int], *, expected_allowed_skips: int
) -> None:
    if value.get("tests", 0) <= 0:
        raise ValueError("no tests executed")
    if value.get("failures", 0) != 0 or value.get("errors", 0) != 0:
        raise ValueError("test suite did not pass")
    if value.get("skipped", 0) != expected_allowed_skips:
        raise ValueError("unexpected skipped tests")


def _validate_zero_api_receipts(
    *,
    adapter: Mapping[str, Any],
    runtime: Mapping[str, Any],
    summary: Mapping[str, Any],
    replay: Mapping[str, Any],
    input_payload: Mapping[str, Any],
    run: Mapping[str, Any],
) -> None:
    for name, value in (("adapter", adapter), ("summary", summary), ("replay", replay)):
        if value.get("status") != "PASS":
            raise ValueError(f"{name} evidence did not pass")
        if value.get("final_glossary_decision") is not None:
            raise ValueError(f"{name} evidence contains a final glossary decision")
    if adapter.get("provider_call_count") != 0 or runtime.get("provider_call_count") != 0:
        raise ValueError("zero-API receipts report provider calls")
    if runtime.get("final_glossary_decision") is not None:
        raise ValueError("runtime receipt contains a final glossary decision")
    if runtime.get("input_sha256") != input_payload["integrity"]["input_sha256"]:
        raise ValueError("runtime receipt input binding mismatch")
    selection = input_payload["selection_contract"]
    dataset_sha = selection["dataset_manifest_sha256"]
    parent_sha = selection["parent_dataset_manifest_sha256"]
    if adapter.get("dataset_manifest_sha256") != dataset_sha or runtime.get(
        "source_manifest_sha256"
    ) != dataset_sha:
        raise ValueError("adapter/runtime dataset manifest binding mismatch")
    if adapter.get("parent_dataset_manifest_sha256") != parent_sha or runtime.get(
        "parent_dataset_manifest_sha256"
    ) != parent_sha:
        raise ValueError("adapter/runtime parent manifest binding mismatch")
    if runtime.get("adapted_candidate_count") != len(run["candidates"]):
        raise ValueError("runtime receipt candidate count mismatch")
    run_sha = run["integrity"]["run_sha256"]
    attempts = len(run["provider_attempts"])
    if summary.get("source_run_sha256") != run_sha:
        raise ValueError("fake summary source run mismatch")
    if summary.get("provider_attempt_count") != attempts:
        raise ValueError("fake summary provider attempt count mismatch")
    if summary.get("candidate_count") != len(run["candidates"]):
        raise ValueError("fake summary candidate count mismatch")
    if summary.get("accepted_attempt_count") != run["usage"]["accepted_count"] or summary.get(
        "rejected_attempt_count"
    ) != run["usage"]["rejected_count"]:
        raise ValueError("fake summary accepted/rejected count mismatch")
    if summary.get("raw_response_storage_complete") is not True:
        raise ValueError("fake summary raw response storage is incomplete")
    if replay.get("provider_call_count") != 0 or replay.get(
        "raw_response_hashes_verified"
    ) != replay.get("raw_response_count"):
        raise ValueError("replay is not zero-API hash-verified")
    if replay.get("normalized_output_equal") is not True:
        raise ValueError("replay normalized output differs")
    if replay.get("original_run_sha256") != run_sha or replay.get(
        "replayed_run_sha256"
    ) != run_sha:
        raise ValueError("replay run hash mismatch")
    if replay.get("provider_attempt_count") != attempts:
        raise ValueError("replay attempt count mismatch")


def _validate_dataset_frozen_set(
    value: Mapping[str, Any], *, run: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    required = {
        "schema_id",
        "schema_version",
        "status",
        "authority_owner",
        "candidate_count",
        "candidates",
        "final_glossary_decision",
        "integrity",
    }
    if set(value) != required:
        raise ValueError("Dataset Frozen Candidate set fields differ")
    if value["schema_id"] != DATASET_FROZEN_SET_SCHEMA_ID or value[
        "schema_version"
    ] != DATASET_FROZEN_SET_SCHEMA_VERSION:
        raise ValueError("Dataset Frozen Candidate set schema mismatch")
    if value["status"] != "COMPLETE_IMMUTABLE" or value[
        "authority_owner"
    ] != "DATASET_ADAPTER":
        raise ValueError("Frozen Candidates are not Dataset authority output")
    if value["final_glossary_decision"] is not None:
        raise ValueError("Dataset Frozen Candidate set contains a final decision")
    _verify_integrity(value, "self_sha256")
    rows = value["candidates"]
    if not isinstance(rows, list) or value["candidate_count"] != len(rows):
        raise ValueError("Dataset Frozen Candidate count mismatch")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        frozen = validate_official_contract(row)
        if frozen.get("schema_id") != "FrozenCandidateContractV1" or not verify_frozen_candidate_binding(
            frozen
        ):
            raise ValueError("Dataset Frozen Candidate binding is invalid")
        provenance = frozen.get("input_provenance", {})
        if provenance.get("component_id") == "context-substitution-fixture-freezer" or str(
            provenance.get("policy_version", "")
        ).startswith("C_LOCAL_"):
            raise ValueError("C-local Frozen Candidate cannot enter release evidence")
        candidate_id = frozen["candidate_key"]["candidate_id"]
        if candidate_id in result:
            raise ValueError("duplicate Dataset Frozen Candidate")
        result[candidate_id] = frozen
    expected_ids = {row["candidate_id"] for row in run["candidates"]}
    if set(result) != expected_ids:
        raise ValueError("Dataset Frozen Candidate coverage differs from run candidates")
    return result


def _validate_packages(
    *,
    package_root: Path,
    manifest: Mapping[str, Any],
    frozen_candidates: Mapping[str, Mapping[str, Any]],
    run: Mapping[str, Any],
    ledger_manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected = {
        "schema_id": PACKAGE_SET_SCHEMA_ID,
        "schema_version": PACKAGE_SET_SCHEMA_VERSION,
        "status": PACKAGE_SET_COMPLETE_STATUS,
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "source_run_sha256": run["integrity"]["run_sha256"],
        "projection_provider_call_count": 0,
        "source_run_provider_attempt_count": len(run["provider_attempts"]),
        "provider_ledger_manifest_sha256": ledger_manifest["integrity"][
            "manifest_sha256"
        ],
        "final_glossary_decision": None,
        "global_gate_action": None,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"Context Evidence package manifest {key} mismatch")
    entries = manifest.get("packages")
    if not isinstance(entries, list) or manifest.get("package_count") != len(entries):
        raise ValueError("Context Evidence package manifest count mismatch")
    packages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("Context Evidence package entry must be an object")
        relative = _safe_relative_path(entry.get("path"))
        path = package_root.joinpath(*relative.parts)
        current = package_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Context Evidence package path contains a symlink")
        if not path.is_file() or not path.resolve().is_relative_to(package_root.resolve()):
            raise ValueError("Context Evidence package file is missing or symlinked")
        if file_sha256(path) != entry.get("physical_sha256"):
            raise ValueError("Context Evidence package physical hash mismatch")
        package = validate_official_contract(_load(path))
        candidate_id = package["candidate_key"]["candidate_id"]
        frozen = frozen_candidates.get(candidate_id)
        if frozen is None or package["candidate_key"] != frozen["candidate_key"] or package[
            "input_contract_sha256"
        ] != frozen["input_contract_sha256"]:
            raise ValueError("Context Evidence package Frozen Candidate binding mismatch")
        if package["integrity"]["self_sha256"] != entry.get("package_self_sha256"):
            raise ValueError("Context Evidence package self-hash entry mismatch")
        if package.get("final_glossary_decision") is not None or "global_gate_action" in package:
            raise ValueError("Context Evidence package exceeds C decision ownership")
        raw_ref = package["provenance"]["raw_ledger_ref"]
        if raw_ref.get("sha256") != ledger_manifest["ledger_physical_sha256"]:
            raise ValueError("Context Evidence package ledger provenance mismatch")
        if candidate_id in seen:
            raise ValueError("duplicate Context Evidence package candidate")
        seen.add(candidate_id)
        packages.append(package)
    if seen != set(frozen_candidates):
        raise ValueError("Context Evidence package coverage mismatch")
    return packages


def _validate_projection_report(
    value: Mapping[str, Any],
    *,
    package_manifest: Mapping[str, Any],
    packages: list[Mapping[str, Any]],
    run: Mapping[str, Any],
    ledger_manifest: Mapping[str, Any],
) -> None:
    expected = {
        "schema_id": PROJECTION_REPORT_SCHEMA_ID,
        "schema_version": PROJECTION_REPORT_SCHEMA_VERSION,
        "status": PACKAGE_SET_COMPLETE_STATUS,
        "agent": "CONTEXT_SUBSTITUTION_C",
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "source_run_sha256": run["integrity"]["run_sha256"],
        "source_input_sha256": run["input_sha256"],
        "package_manifest_sha256": package_manifest["integrity"]["manifest_sha256"],
        "provider_ledger_manifest_sha256": ledger_manifest["integrity"][
            "manifest_sha256"
        ],
        "package_count": len(packages),
        "provider_call_count": 0,
        "final_glossary_decision": None,
        "global_gate_action": None,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise ValueError(f"projection report {key} mismatch")
    report_entries = value.get("packages")
    manifest_entries = package_manifest.get("packages")
    if not isinstance(report_entries, list) or not isinstance(manifest_entries, list):
        raise ValueError("projection report package list is invalid")
    expected_entries = [
        {
            "candidate_id": row["candidate_key"]["candidate_id"],
            "input_contract_sha256": row["input_contract_sha256"],
            "package_self_sha256": row["package_self_sha256"],
            "physical_sha256": row["physical_sha256"],
        }
        for row in manifest_entries
    ]
    if report_entries != expected_entries:
        raise ValueError("projection report package entries differ from manifest")


def _verify_nested_self_hash(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = dict(value)
    _verify_integrity(result, key)
    return result


def _verify_integrity(value: Mapping[str, Any], key: str) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {key}:
        raise ValueError(f"artifact integrity must contain only {key}")
    identity = dict(value)
    identity["integrity"] = {}
    if integrity[key] != object_sha256(identity):
        raise ValueError(f"artifact {key} self-hash mismatch")


def _safe_relative_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("artifact path is not canonical relative POSIX form")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("artifact path escapes the evidence root")
    if path.as_posix() != value:
        raise ValueError("artifact path is noncanonical")
    return path


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load integration evidence {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"integration evidence {path.name} must be an object")
    return value
