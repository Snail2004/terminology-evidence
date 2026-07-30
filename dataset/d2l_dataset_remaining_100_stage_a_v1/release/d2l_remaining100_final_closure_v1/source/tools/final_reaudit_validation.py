from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_object,
)


AUDIT_FIELDS = {
    "audit_decision",
    "audit_notes",
    "audit_status",
    "invalid_child_sense_ids",
}


@dataclass(frozen=True)
class FinalReauditSpec:
    reviewer_role: str
    batch_id: str
    input_path: Path
    response_path: Path


def _validate_immutable_response(
    source: Mapping[str, Any], response: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []
    if set(source) != set(response):
        errors.append("top-level keys changed")
    for key, value in source.items():
        if key != "cases" and response.get(key) != value:
            errors.append(f"immutable top-level field changed: {key}")
    source_cases = source.get("cases")
    response_cases = response.get("cases")
    if not isinstance(source_cases, list) or not isinstance(response_cases, list):
        return errors + ["cases must be arrays"]
    if len(source_cases) != len(response_cases):
        errors.append("case count changed")
    for index, (source_case, response_case) in enumerate(
        zip(source_cases, response_cases), 1
    ):
        prefix = f"case_{index}"
        if not isinstance(source_case, Mapping) or not isinstance(
            response_case, Mapping
        ):
            errors.append(f"{prefix}: case must be an object")
            continue
        if set(source_case) != set(response_case):
            errors.append(f"{prefix}: case keys changed")
        for key, value in source_case.items():
            if key != "audit" and response_case.get(key) != value:
                errors.append(f"{prefix}: immutable field changed: {key}")
    return errors


def validate_final_reaudit(input_path: Path, response_path: Path) -> list[str]:
    source = strict_json_object(input_path)
    response = strict_json_object(response_path)
    errors = _validate_immutable_response(source, response)
    allowed = source.get("allowed_audit_decisions")
    if not isinstance(allowed, list) or set(allowed) != {
        "APPROVE",
        "BLOCK",
        "REVISE",
    }:
        errors.append("invalid allowed audit decision contract")
        allowed = []
    for index, case in enumerate(response.get("cases", []), 1):
        prefix = f"case_{index}"
        if not isinstance(case, Mapping):
            continue
        source_payload = case.get("source_payload")
        if not isinstance(source_payload, Mapping) or case.get(
            "source_payload_sha256"
        ) != sha256_bytes(canonical_json_bytes(source_payload)):
            errors.append(f"{prefix}: source payload binding mismatch")
        audit = case.get("audit")
        if not isinstance(audit, Mapping) or set(audit) != AUDIT_FIELDS:
            errors.append(f"{prefix}: audit fields do not match the contract")
            continue
        decision = audit.get("audit_decision")
        if decision not in allowed:
            errors.append(f"{prefix}: invalid audit decision")
        if audit.get("audit_status") != "COMPLETE":
            errors.append(f"{prefix}: audit_status must be COMPLETE")
        notes = audit.get("audit_notes")
        if not isinstance(notes, str) or not notes.strip():
            errors.append(f"{prefix}: audit_notes must be nonblank")
        proposal = case.get("repaired_proposal")
        children = (
            proposal.get("child_sense_repairs", [])
            if isinstance(proposal, Mapping)
            else []
        )
        child_ids = {
            child.get("temporary_child_sense_id")
            for child in children
            if isinstance(child, Mapping)
            and isinstance(child.get("temporary_child_sense_id"), str)
        }
        invalid_ids = audit.get("invalid_child_sense_ids")
        if not isinstance(invalid_ids, list) or len(invalid_ids) != len(
            set(invalid_ids)
        ):
            errors.append(f"{prefix}: invalid child IDs must be a unique array")
            continue
        if any(child_id not in child_ids for child_id in invalid_ids):
            errors.append(f"{prefix}: invalid child ID is not in the proposal")
        if decision == "APPROVE" and invalid_ids:
            errors.append(f"{prefix}: APPROVE cannot list invalid child IDs")
        if decision == "REVISE" and not invalid_ids:
            errors.append(f"{prefix}: REVISE must identify an invalid child")
    return errors


def capture_final_reaudits(
    specs: Sequence[FinalReauditSpec],
    capture_root: Path,
    after_inventory: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    if len(specs) != 2:
        raise ValueError("exactly two final re-audit responses are required")
    resolved = [spec.response_path.resolve(strict=True) for spec in specs]
    if len(resolved) != len(set(resolved)):
        raise ValueError("final re-audit response paths must be distinct")
    inventory = [
        {
            "spec": spec,
            "source_path": path,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for spec, path in zip(specs, resolved)
    ]
    if after_inventory is not None:
        after_inventory()
    capture_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for row in inventory:
        spec = row["spec"]
        source_path = row["source_path"]
        captured = capture_root / spec.reviewer_role / source_path.name
        captured.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, captured)
        if sha256_file(source_path) != row["sha256"]:
            raise ValueError(f"final re-audit source drift: {source_path.name}")
        if sha256_file(captured) != row["sha256"]:
            raise ValueError(f"final re-audit capture mismatch: {source_path.name}")
        errors = validate_final_reaudit(spec.input_path, captured)
        if errors:
            raise ValueError(f"{source_path.name}: " + "; ".join(errors))
        records.append(
            {
                "batch_id": spec.batch_id,
                "captured_relative_path": captured.relative_to(
                    capture_root
                ).as_posix(),
                "reviewer_role": spec.reviewer_role,
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "source_file_name": source_path.name,
                "source_input_sha256": sha256_file(spec.input_path),
            }
        )
    return sorted(records, key=lambda item: item["batch_id"])
