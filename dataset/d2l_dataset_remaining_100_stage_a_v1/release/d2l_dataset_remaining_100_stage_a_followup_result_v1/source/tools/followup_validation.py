from __future__ import annotations

import copy
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
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.review_result import (
    validate_completed_result,
)


R0_REPAIR_FIELDS = {
    "candidate_replacements",
    "corrected_definition_en",
    "corrected_part_of_speech",
    "corrected_scope",
    "invalid_evidence_context_ids",
    "proposed_split_labels",
    "repair_rationale",
    "repair_status",
}
HIGH_RISK_REPAIR_FIELDS = {
    "candidate_replacements",
    "child_sense_repairs",
    "corrected_definition_en",
    "corrected_part_of_speech",
    "corrected_scope",
    "invalid_evidence_context_ids",
    "repair_rationale",
    "repair_status",
    "resolution_status",
}
CHILD_SENSE_FIELDS = {
    "candidate_assignments",
    "context_ids",
    "definition_en",
    "part_of_speech",
    "scope",
    "temporary_child_sense_id",
}
PROPOSAL_AUDIT_FIELDS = {
    "audit_decision",
    "audit_notes",
    "audit_status",
    "invalid_child_sense_ids",
}


@dataclass(frozen=True)
class ReviewFileSpec:
    kind: str
    reviewer_role: str
    batch_id: str
    input_path: Path
    response_path: Path


def source_payload_sha256(source: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(source))


def _validate_immutable_response(
    source: Mapping[str, Any],
    response: Mapping[str, Any],
    mutable_case_field: str,
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
            if key != mutable_case_field and response_case.get(key) != value:
                errors.append(f"{prefix}: immutable field changed: {key}")
    return errors


def _source_bindings(source: Mapping[str, Any]) -> tuple[set[str], set[tuple[Any, Any]]]:
    context_ids = {
        row.get("context_id")
        for row in source.get("evidence_contexts", [])
        if isinstance(row, Mapping)
    }
    candidate_keys = {
        (row.get("candidate_id"), row.get("candidate_slot"))
        for row in source.get("candidates", [])
        if isinstance(row, Mapping)
    }
    return context_ids, candidate_keys


def _validate_bound_lists(
    repair: Mapping[str, Any], source: Mapping[str, Any], prefix: str
) -> list[str]:
    errors: list[str] = []
    context_ids, candidate_keys = _source_bindings(source)
    invalid_ids = repair.get("invalid_evidence_context_ids")
    if not isinstance(invalid_ids, list) or len(invalid_ids) != len(set(invalid_ids)):
        errors.append(f"{prefix}: invalid context IDs must be unique")
    elif any(value not in context_ids for value in invalid_ids):
        errors.append(f"{prefix}: foreign context ID")
    replacements = repair.get("candidate_replacements")
    if not isinstance(replacements, list):
        errors.append(f"{prefix}: candidate_replacements must be an array")
        return errors
    seen_slots: set[Any] = set()
    for item in replacements:
        if not isinstance(item, Mapping) or set(item) != {
            "candidate_id",
            "candidate_slot",
            "replacement_target_vi",
        }:
            errors.append(f"{prefix}: invalid candidate replacement")
            continue
        binding = (item.get("candidate_id"), item.get("candidate_slot"))
        if binding not in candidate_keys:
            errors.append(f"{prefix}: foreign candidate ID or slot")
        slot = item.get("candidate_slot")
        if slot in seen_slots:
            errors.append(f"{prefix}: duplicate candidate replacement slot")
        seen_slots.add(slot)
        target = item.get("replacement_target_vi")
        if not isinstance(target, str) or not target.strip():
            errors.append(f"{prefix}: blank replacement target")
    return errors


def validate_r0_repair(input_path: Path, response_path: Path) -> list[str]:
    source = strict_json_object(input_path)
    response = strict_json_object(response_path)
    errors = _validate_immutable_response(source, response, "repair")
    source_cases = source.get("cases", [])
    response_cases = response.get("cases", [])
    for index, (source_case, response_case) in enumerate(
        zip(source_cases, response_cases), 1
    ):
        prefix = f"case_{index}"
        repair = response_case.get("repair")
        if not isinstance(repair, Mapping) or set(repair) != R0_REPAIR_FIELDS:
            errors.append(f"{prefix}: repair fields do not match the contract")
            continue
        if repair.get("repair_status") != "COMPLETE":
            errors.append(f"{prefix}: repair_status must be COMPLETE")
        rationale = repair.get("repair_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"{prefix}: repair_rationale must be nonblank")
        required = set(source_case.get("required_repairs", []))
        for field in (
            "corrected_definition_en",
            "corrected_part_of_speech",
            "corrected_scope",
        ):
            value = repair.get(field)
            if not isinstance(value, str):
                errors.append(f"{prefix}: {field} must be a string")
            elif field in required and not value.strip():
                errors.append(f"{prefix}: {field} is required")
            elif field not in required and value.strip():
                errors.append(f"{prefix}: {field} is outside requested repair")
        errors.extend(_validate_bound_lists(repair, source_case["source_payload"], prefix))
        if "candidate_replacements" in required and not repair[
            "candidate_replacements"
        ]:
            errors.append(f"{prefix}: candidate replacement is required")
        if "candidate_replacements" not in required and repair[
            "candidate_replacements"
        ]:
            errors.append(f"{prefix}: candidate replacement is outside requested repair")
        if "invalid_evidence_context_ids" in required and not repair[
            "invalid_evidence_context_ids"
        ]:
            errors.append(f"{prefix}: evidence repair requires a context ID")
        if "invalid_evidence_context_ids" not in required and repair[
            "invalid_evidence_context_ids"
        ]:
            errors.append(f"{prefix}: invalid context IDs are outside requested repair")
        labels = repair.get("proposed_split_labels")
        if not isinstance(labels, list) or any(
            not isinstance(value, str) or not value.strip() for value in labels
        ):
            errors.append(f"{prefix}: proposed_split_labels are invalid")
        elif "proposed_split_labels" in required and len(labels) < 2:
            errors.append(f"{prefix}: split repair requires at least two labels")
        elif "proposed_split_labels" not in required and labels:
            errors.append(f"{prefix}: split labels are outside requested repair")
    return errors


def _validate_split(
    repair: Mapping[str, Any], case: Mapping[str, Any], prefix: str
) -> list[str]:
    errors: list[str] = []
    children = repair.get("child_sense_repairs")
    targets = case.get("split_targets")
    if not isinstance(children, list) or not isinstance(targets, list):
        return [f"{prefix}: child senses must be arrays"]
    expected_ids = {row["temporary_child_sense_id"] for row in targets}
    actual_ids = {
        row.get("temporary_child_sense_id")
        for row in children
        if isinstance(row, Mapping)
    }
    if actual_ids != expected_ids or len(children) != len(expected_ids):
        return [f"{prefix}: child-sense IDs do not match sealed split targets"]
    source = case["source_payload"]
    expected_contexts, expected_candidates = _source_bindings(source)
    assigned_contexts: list[Any] = []
    assigned_candidates: list[tuple[Any, Any]] = []
    for child in children:
        if not isinstance(child, Mapping) or set(child) != CHILD_SENSE_FIELDS:
            errors.append(f"{prefix}: child-sense fields do not match contract")
            continue
        for field in ("definition_en", "part_of_speech", "scope"):
            value = child.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}: child {field} must be nonblank")
        context_ids = child.get("context_ids")
        if not isinstance(context_ids, list) or not context_ids:
            errors.append(f"{prefix}: each child requires contexts")
        else:
            assigned_contexts.extend(context_ids)
        assignments = child.get("candidate_assignments")
        if not isinstance(assignments, list) or not assignments:
            errors.append(f"{prefix}: each child requires candidates")
            continue
        for item in assignments:
            if not isinstance(item, Mapping) or set(item) != {
                "candidate_id",
                "candidate_slot",
                "target_vi",
            }:
                errors.append(f"{prefix}: invalid child candidate assignment")
                continue
            assigned_candidates.append(
                (item.get("candidate_id"), item.get("candidate_slot"))
            )
            target = item.get("target_vi")
            if not isinstance(target, str) or not target.strip():
                errors.append(f"{prefix}: child candidate target must be nonblank")
    if set(assigned_contexts) != expected_contexts or len(assigned_contexts) != len(
        expected_contexts
    ):
        errors.append(f"{prefix}: contexts must be assigned exactly once")
    if set(assigned_candidates) != expected_candidates or len(
        assigned_candidates
    ) != len(expected_candidates):
        errors.append(f"{prefix}: candidates must be assigned exactly once")
    return errors


def validate_high_risk_repair(input_path: Path, response_path: Path) -> list[str]:
    source = strict_json_object(input_path)
    response = strict_json_object(response_path)
    errors = _validate_immutable_response(source, response, "repair")
    for index, (source_case, response_case) in enumerate(
        zip(source.get("cases", []), response.get("cases", [])), 1
    ):
        prefix = f"case_{index}"
        repair = response_case.get("repair")
        if not isinstance(repair, Mapping) or set(repair) != HIGH_RISK_REPAIR_FIELDS:
            errors.append(f"{prefix}: repair fields do not match the contract")
            continue
        if repair.get("repair_status") != "COMPLETE":
            errors.append(f"{prefix}: repair_status must be COMPLETE")
        rationale = repair.get("repair_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"{prefix}: repair_rationale must be nonblank")
        mode = source_case.get("repair_mode")
        resolution = repair.get("resolution_status")
        if mode == "UNRESOLVED":
            if resolution != "BLOCKED":
                errors.append(f"{prefix}: unresolved evidence must remain BLOCKED")
            continue
        if mode == "SPLIT_REQUIRED":
            if resolution not in {"SPLIT_PROPOSED", "BLOCKED"}:
                errors.append(f"{prefix}: invalid split resolution")
            elif resolution == "SPLIT_PROPOSED":
                errors.extend(_validate_split(repair, source_case, prefix))
            continue
        if resolution not in {"REPAIRED", "BLOCKED"}:
            errors.append(f"{prefix}: invalid revision resolution")
            continue
        if resolution == "BLOCKED":
            continue
        required = set(source_case.get("required_repairs", []))
        for field in (
            "corrected_definition_en",
            "corrected_part_of_speech",
            "corrected_scope",
        ):
            value = repair.get(field)
            if not isinstance(value, str):
                errors.append(f"{prefix}: {field} must be a string")
            elif field in required and not value.strip():
                errors.append(f"{prefix}: {field} is required")
            elif field not in required and value.strip():
                errors.append(f"{prefix}: {field} is outside requested repair")
        errors.extend(_validate_bound_lists(repair, source_case["source_payload"], prefix))
        if "candidate_replacements" in required and not repair[
            "candidate_replacements"
        ]:
            errors.append(f"{prefix}: candidate replacement is required")
        if "invalid_evidence_context_ids" in required and not repair[
            "invalid_evidence_context_ids"
        ]:
            errors.append(f"{prefix}: evidence repair requires invalid context IDs")
    return errors


def validate_blind_result(input_path: Path, response_path: Path) -> list[str]:
    input_payload = strict_json_object(input_path)
    reviewer_slot = input_payload.get("reviewer_slot")
    if not isinstance(reviewer_slot, str) or not reviewer_slot:
        return ["blind input reviewer_slot must be a nonblank string"]
    result, errors, _ = validate_completed_result(
        input_path,
        response_path,
        expected_batch_id=str(input_payload["batch_id"]),
        expected_reviewer_slot=reviewer_slot,
    )
    if result is None and not errors:
        errors.append("blind result did not produce a validated result")
    return errors


def validate_high_risk_audit(input_path: Path, response_path: Path) -> list[str]:
    source = strict_json_object(input_path)
    response = strict_json_object(response_path)
    errors = _validate_immutable_response(source, response, "audit")
    allowed_decisions = source.get("allowed_audit_decisions")
    if not isinstance(allowed_decisions, list) or set(allowed_decisions) != {
        "APPROVE",
        "BLOCK",
        "REVISE",
    }:
        errors.append("invalid allowed audit decision contract")
        allowed_decisions = []
    for index, response_case in enumerate(response.get("cases", []), 1):
        prefix = f"case_{index}"
        if not isinstance(response_case, Mapping):
            continue
        audit = response_case.get("audit")
        if not isinstance(audit, Mapping) or set(audit) != PROPOSAL_AUDIT_FIELDS:
            errors.append(f"{prefix}: audit fields do not match the contract")
            continue
        decision = audit.get("audit_decision")
        if decision not in allowed_decisions:
            errors.append(f"{prefix}: invalid audit decision")
        if audit.get("audit_status") != "COMPLETE":
            errors.append(f"{prefix}: audit_status must be COMPLETE")
        notes = audit.get("audit_notes")
        if not isinstance(notes, str) or not notes.strip():
            errors.append(f"{prefix}: audit_notes must be nonblank")
        proposal = response_case.get("proposal")
        child_rows = (
            proposal.get("child_sense_repairs", [])
            if isinstance(proposal, Mapping)
            else []
        )
        child_ids = {
            child.get("temporary_child_sense_id")
            for child in child_rows
            if isinstance(child, Mapping)
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
        if (
            decision == "REVISE"
            and isinstance(proposal, Mapping)
            and proposal.get("proposal_type") == "SPLIT_PROPOSAL"
            and not invalid_ids
        ):
            errors.append(f"{prefix}: split REVISE must identify an invalid child")
    return errors


def validate_spec(spec: ReviewFileSpec, response_path: Path | None = None) -> list[str]:
    path = response_path or spec.response_path
    if spec.kind == "r0_repair":
        return validate_r0_repair(spec.input_path, path)
    if spec.kind == "high_risk":
        return validate_high_risk_repair(spec.input_path, path)
    if spec.kind in {"r0_blind", "followup_reaudit"}:
        return validate_blind_result(spec.input_path, path)
    if spec.kind == "high_risk_audit":
        return validate_high_risk_audit(spec.input_path, path)
    return [f"unsupported review kind: {spec.kind}"]


def capture_review_files(
    specs: Sequence[ReviewFileSpec],
    capture_root: Path,
    after_inventory: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    resolved = [spec.response_path.resolve(strict=True) for spec in specs]
    if len(resolved) != len(set(resolved)):
        raise ValueError("review response paths must be distinct")
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
        relative = Path(spec.kind) / spec.reviewer_role / source_path.name
        captured_path = capture_root / relative
        captured_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, captured_path)
        if sha256_file(source_path) != row["sha256"]:
            raise ValueError(f"source review drift during capture: {source_path.name}")
        if sha256_file(captured_path) != row["sha256"]:
            raise ValueError(f"captured review hash mismatch: {source_path.name}")
        errors = validate_spec(spec, captured_path)
        if errors:
            raise ValueError(f"{source_path.name}: " + "; ".join(errors))
        records.append(
            {
                "batch_id": spec.batch_id,
                "captured_relative_path": relative.as_posix(),
                "kind": spec.kind,
                "reviewer_role": spec.reviewer_role,
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "source_file_name": source_path.name,
                "source_input_sha256": sha256_file(spec.input_path),
            }
        )
    return records


def apply_resolution(
    source: Mapping[str, Any], resolution: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    effective = copy.deepcopy(dict(source))
    operations: list[dict[str, Any]] = []
    field_map = {
        "corrected_definition_en": "proposed_definition_en",
        "corrected_part_of_speech": "proposed_part_of_speech",
        "corrected_scope": "proposed_scope",
    }
    for repair_field, source_field in field_map.items():
        value = resolution.get(repair_field)
        if isinstance(value, str) and value.strip():
            old_value = effective.get(source_field)
            effective[source_field] = value
            operations.append(
                {
                    "field": source_field,
                    "new_value": value,
                    "old_value": old_value,
                    "operation": "REPLACE_FIELD",
                }
            )
    candidates = {
        (row.get("candidate_id"), row.get("candidate_slot")): row
        for row in effective.get("candidates", [])
        if isinstance(row, dict)
    }
    for replacement in resolution.get("candidate_replacements", []):
        binding = (replacement.get("candidate_id"), replacement.get("candidate_slot"))
        candidate = candidates.get(binding)
        target = replacement.get("replacement_target_vi")
        if candidate is None or not isinstance(target, str) or not target.strip():
            raise ValueError(f"invalid candidate replacement binding: {binding}")
        old_target = candidate.get("candidate_target_vi")
        candidate["candidate_target_vi"] = target
        operations.append(
            {
                "candidate_id": binding[0],
                "candidate_slot": binding[1],
                "new_target_vi": target,
                "old_target_vi": old_target,
                "operation": "REPLACE_CANDIDATE_TARGET",
            }
        )
    invalid_ids = set(resolution.get("invalid_evidence_context_ids", []))
    if invalid_ids:
        contexts = effective.get("evidence_contexts", [])
        effective["evidence_contexts"] = [
            row for row in contexts if row.get("context_id") not in invalid_ids
        ]
        for context_id in sorted(invalid_ids):
            operations.append(
                {
                    "context_id": context_id,
                    "operation": "REMOVE_INVALID_EVIDENCE_CONTEXT",
                }
            )
    normalized_targets = [
        str(row.get("candidate_target_vi", "")).strip().casefold()
        for row in effective.get("candidates", [])
    ]
    if len(normalized_targets) != 3 or len(set(normalized_targets)) != 3:
        raise ValueError(
            f"effective candidates must remain three distinct values: {source.get('sense_id')}"
        )
    for context in effective.get("evidence_contexts", []):
        if context.get("synthetic") and context.get("positive_evidence_eligible"):
            raise ValueError(
                f"synthetic context cannot be positive evidence: {source.get('sense_id')}"
            )
    return effective, operations


def sanitize_for_blind_review(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in source.items()
        if key not in {"review_requirement", "risk_class", "source_review_status"}
    }
