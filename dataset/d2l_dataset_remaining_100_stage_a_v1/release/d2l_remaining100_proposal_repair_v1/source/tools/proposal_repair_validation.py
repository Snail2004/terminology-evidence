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

from .followup_validation import _validate_split


PROPOSAL_REPAIR_FIELDS = {
    "repair_notes",
    "repair_status",
    "revised_proposal",
}


@dataclass(frozen=True)
class ProposalRepairSpec:
    reviewer_role: str
    batch_id: str
    input_path: Path
    response_path: Path


def _validate_immutable_wrapper(
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
            if key != "repair" and response_case.get(key) != value:
                errors.append(f"{prefix}: immutable field changed: {key}")
    return errors


def _child_map(proposal: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    children = proposal.get("child_sense_repairs")
    if not isinstance(children, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for child in children:
        if not isinstance(child, Mapping):
            continue
        child_id = child.get("temporary_child_sense_id")
        if isinstance(child_id, str) and child_id not in result:
            result[child_id] = child
    return result


def validate_split_proposal(
    proposal: Mapping[str, Any],
    source_payload: Mapping[str, Any],
    expected_child_ids: set[str],
    prefix: str,
) -> list[str]:
    if set(proposal) != {"child_sense_repairs", "proposal_type"}:
        return [f"{prefix}: split proposal fields do not match the contract"]
    if proposal.get("proposal_type") != "SPLIT_PROPOSAL":
        return [f"{prefix}: proposal_type must remain SPLIT_PROPOSAL"]
    return _validate_split(
        {"child_sense_repairs": proposal.get("child_sense_repairs")},
        {
            "source_payload": source_payload,
            "split_targets": [
                {"temporary_child_sense_id": child_id}
                for child_id in sorted(expected_child_ids)
            ],
        },
        prefix,
    )


def validate_proposal_repair(input_path: Path, response_path: Path) -> list[str]:
    source = strict_json_object(input_path)
    response = strict_json_object(response_path)
    errors = _validate_immutable_wrapper(source, response)
    for index, response_case in enumerate(response.get("cases", []), 1):
        prefix = f"case_{index}"
        if not isinstance(response_case, Mapping):
            continue
        source_payload = response_case.get("source_payload")
        claimed_source_sha = response_case.get("source_payload_sha256")
        if not isinstance(source_payload, Mapping) or claimed_source_sha != sha256_bytes(
            canonical_json_bytes(source_payload)
        ):
            errors.append(f"{prefix}: source payload binding mismatch")
            continue
        audit = response_case.get("audit")
        if not isinstance(audit, Mapping) or audit.get("audit_decision") != "REVISE":
            errors.append(f"{prefix}: source audit must be REVISE")
            continue
        invalid_ids = audit.get("invalid_child_sense_ids")
        if not isinstance(invalid_ids, list) or not invalid_ids:
            errors.append(f"{prefix}: source audit must identify invalid children")
            continue
        repair = response_case.get("repair")
        if not isinstance(repair, Mapping) or set(repair) != PROPOSAL_REPAIR_FIELDS:
            errors.append(f"{prefix}: repair fields do not match the contract")
            continue
        if repair.get("repair_status") != "COMPLETE":
            errors.append(f"{prefix}: repair_status must be COMPLETE")
        notes = repair.get("repair_notes")
        if not isinstance(notes, str) or not notes.strip():
            errors.append(f"{prefix}: repair_notes must be nonblank")
        original = response_case.get("original_proposal")
        revised = repair.get("revised_proposal")
        if not isinstance(original, Mapping) or not isinstance(revised, Mapping):
            errors.append(f"{prefix}: original and revised proposals must be objects")
            continue
        original_children = _child_map(original)
        revised_children = _child_map(revised)
        expected_ids = set(original_children)
        if not expected_ids or set(revised_children) != expected_ids:
            errors.append(f"{prefix}: revised child IDs changed")
            continue
        changed_ids = {
            child_id
            for child_id in expected_ids
            if original_children[child_id] != revised_children[child_id]
        }
        if changed_ids != set(invalid_ids):
            errors.append(
                f"{prefix}: changed children must match the audited invalid child IDs"
            )
        errors.extend(
            validate_split_proposal(revised, source_payload, expected_ids, prefix)
        )
    return errors


def capture_proposal_repairs(
    specs: Sequence[ProposalRepairSpec],
    capture_root: Path,
    after_inventory: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    resolved = [spec.response_path.resolve(strict=True) for spec in specs]
    if len(resolved) != len(set(resolved)):
        raise ValueError("proposal repair response paths must be distinct")
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
            raise ValueError(f"proposal repair source drift: {source_path.name}")
        if sha256_file(captured) != row["sha256"]:
            raise ValueError(f"proposal repair capture mismatch: {source_path.name}")
        errors = validate_proposal_repair(spec.input_path, captured)
        if errors:
            raise ValueError(f"{source_path.name}: " + "; ".join(errors))
        records.append(
            {
                "batch_id": spec.batch_id,
                "captured_relative_path": captured.relative_to(capture_root).as_posix(),
                "reviewer_role": spec.reviewer_role,
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "source_file_name": source_path.name,
                "source_input_sha256": sha256_file(spec.input_path),
            }
        )
    return records
