"""Controlled test-only mutations of sealed bundles."""

from __future__ import annotations

import shutil
from pathlib import Path

from .errors import ValidationError
from .hashing import self_sha256
from .jsonio import dump_json, load_json


FAULTS = {
    "missing_package",
    "duplicate_json_key",
    "nan",
    "checksum_drift",
    "identity_mismatch",
    "path_traversal",
    "r2_receipt_drift",
    "approval_binding_missing",
    "approval_binding_swap",
    "approval_artifact_drift",
    "action_policy_drift",
    "r1_automatic_fallback",
}


def _replace_json(path: Path, value: dict) -> None:
    path.unlink()
    dump_json(path, value)


def inject_fault(source: Path, destination: Path, fault: str) -> Path:
    if fault not in FAULTS:
        raise ValidationError(f"unknown fault: {fault}")
    if destination.exists():
        raise ValidationError(f"fault output already exists: {destination}")
    shutil.copytree(source, destination)
    if fault == "missing_package":
        package = next((destination / "input" / "packages").rglob("*.json"), None)
        if package is None:
            raise ValidationError("no package available for fault")
        package.unlink()
    elif fault == "duplicate_json_key":
        path = destination / "run_spec.json"
        path.write_text('{"schema_id":"SystemIntegrationRunSpecV1","schema_id":"tampered"}\n', encoding="utf-8", newline="\n")
    elif fault == "nan":
        path = destination / "run_spec.json"
        path.write_text('{"value":NaN}\n', encoding="utf-8", newline="\n")
    elif fault == "checksum_drift":
        path = destination / "run_spec.json"
        path.write_text(path.read_text(encoding="utf-8") + "x", encoding="utf-8", newline="\n")
    elif fault == "identity_mismatch":
        path = next((destination / "input" / "packages").rglob("frozen_candidate.json"), None)
        if path is None:
            raise ValidationError("frozen candidate is unavailable")
        value = load_json(path, require_object=True)
        value["candidate_key"]["candidate_id"] = "foreign-candidate"
        path.write_text(__import__("json").dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    elif fault == "path_traversal":
        path = destination / "CHECKSUMS.sha256"
        path.write_text(path.read_text(encoding="utf-8") + "0  ../escape\n", encoding="utf-8", newline="\n")
    elif fault == "r2_receipt_drift":
        path = destination / "input" / "authority" / "authority_receipt.json"
        value = load_json(path, require_object=True)
        value["final_release_zip_sha256"] = "0" * 64
        value["integrity"]["self_sha256"] = self_sha256(value)
        _replace_json(path, value)
    elif fault == "approval_binding_missing":
        path = destination / "input" / "authority" / "approval" / "approval_binding_v1.json"
        if not path.is_file():
            raise ValidationError("sealed AR-1 approval binding is unavailable")
        path.unlink()
    elif fault == "approval_binding_swap":
        root = destination / "input" / "authority" / "approval"
        left = root / "Independent_Review_Contract_Steward_Authority_Maintenance_V1_2_R2.md"
        right = root / "Hau_Review_Contract_Steward_R2_Authority_Promotion.md"
        if not left.is_file() or not right.is_file():
            raise ValidationError("sealed AR-1 evidence is unavailable")
        left.write_bytes(right.read_bytes())
    elif fault == "approval_artifact_drift":
        path = destination / "input" / "authority" / "approval" / "contracts_v1_1_0_authority_receipt_r2_independent_approval.json"
        if not path.is_file():
            raise ValidationError("sealed AR-1 approval artifact is unavailable")
        path.write_bytes(path.read_bytes() + b" ")
    elif fault == "action_policy_drift":
        path = destination / "input" / "authority" / "global_action_policy.json"
        if not path.is_file():
            raise ValidationError("sealed Global action policy is unavailable")
        path.write_bytes(path.read_bytes() + b" ")
    elif fault == "r1_automatic_fallback":
        path = destination / "run_spec.json"
        value = load_json(path, require_object=True)
        value["authority_mode"] = "CONTRACTS_R1_HISTORICAL_REPLAY"
        value["compatibility_mode"] = "CONTRACTS_R1_HISTORICAL_REPLAY"
        _replace_json(path, value)
    return destination
