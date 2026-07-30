from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import canonical_json_bytes, sha256_bytes, sha256_file, strict_json_object
    from .spec import ALLOWED_SENSE_STATUS, ALLOWED_STANDARD_DECISIONS, REVIEW_FIELDS
except ImportError:  # pragma: no cover - direct script execution
    from common import canonical_json_bytes, sha256_bytes, sha256_file, strict_json_object  # type: ignore
    from spec import ALLOWED_SENSE_STATUS, ALLOWED_STANDARD_DECISIONS, REVIEW_FIELDS  # type: ignore


CORE_REVIEW_FIELDS = tuple(field for field in REVIEW_FIELDS if field not in {"review_notes", "review_status"})
DECISION_TO_CORRECTION = {
    "definition_decision": "corrected_definition_en",
    "part_of_speech_decision": "corrected_part_of_speech",
    "scope_decision": "corrected_scope",
}


@dataclass(frozen=True)
class ValidatedResult:
    batch_id: str
    reviewer_slot: str
    path: Path
    sha256: str
    payload: dict[str, Any]


def _validate_candidate_replacements(
    replacements: Any,
    source: Mapping[str, Any],
    prefix: str,
    errors: list[str],
) -> str:
    if not isinstance(replacements, list):
        errors.append(f"{prefix}: candidate_replacements must be a list")
        return "INVALID"
    if not replacements:
        return "EMPTY"
    candidates = {
        (row.get("candidate_id"), row.get("candidate_slot"))
        for row in source.get("candidates", [])
        if isinstance(row, Mapping)
    }
    formats: set[str] = set()
    for index, item in enumerate(replacements):
        if isinstance(item, str):
            if not item.strip():
                errors.append(f"{prefix}: blank replacement at index {index}")
            formats.add("LEGACY_UNBOUND_TEXT")
            continue
        if not isinstance(item, Mapping) or set(item) != {
            "candidate_id",
            "candidate_slot",
            "replacement_target_vi",
        }:
            errors.append(f"{prefix}: invalid replacement object at index {index}")
            continue
        if (item.get("candidate_id"), item.get("candidate_slot")) not in candidates:
            errors.append(f"{prefix}: replacement target is not a source candidate")
        target = item.get("replacement_target_vi")
        if not isinstance(target, str) or not target.strip():
            errors.append(f"{prefix}: replacement target text is blank")
        formats.add("CANDIDATE_BOUND_OBJECT")
    return "+".join(sorted(formats)) if formats else "INVALID"


def _validate_review(
    review: Any,
    source: Mapping[str, Any],
    prefix: str,
    errors: list[str],
) -> str:
    if not isinstance(review, Mapping) or set(review) != set(REVIEW_FIELDS):
        errors.append(f"{prefix}: review fields do not match the contract")
        return "INVALID"
    for field in (
        "definition_decision",
        "part_of_speech_decision",
        "scope_decision",
        "evidence_decision",
        "candidate_set_decision",
    ):
        if review.get(field) not in ALLOWED_STANDARD_DECISIONS:
            errors.append(f"{prefix}: invalid {field}")
    if review.get("sense_status") not in ALLOWED_SENSE_STATUS:
        errors.append(f"{prefix}: invalid sense_status")
    if review.get("review_status") != "COMPLETE":
        errors.append(f"{prefix}: review_status must be COMPLETE")
    for decision_field, correction_field in DECISION_TO_CORRECTION.items():
        decision = review.get(decision_field)
        correction = review.get(correction_field)
        if not isinstance(correction, str):
            errors.append(f"{prefix}: {correction_field} must be a string")
        elif decision == "REVISE" and not correction.strip():
            errors.append(f"{prefix}: {correction_field} is required for REVISE")
        elif decision == "ACCEPT" and correction.strip():
            errors.append(f"{prefix}: {correction_field} must be blank for ACCEPT")
    context_ids = {
        row.get("context_id")
        for row in source.get("evidence_contexts", [])
        if isinstance(row, Mapping)
    }
    invalid_ids = review.get("invalid_evidence_context_ids")
    if not isinstance(invalid_ids, list) or len(invalid_ids) != len(set(invalid_ids)):
        errors.append(f"{prefix}: invalid evidence context list")
    elif any(item not in context_ids for item in invalid_ids):
        errors.append(f"{prefix}: invalid evidence context ID is not in the source")
    if review.get("evidence_decision") == "ACCEPT" and invalid_ids:
        errors.append(f"{prefix}: ACCEPT evidence cannot list invalid contexts")
    replacement_format = _validate_candidate_replacements(
        review.get("candidate_replacements"), source, prefix, errors
    )
    if review.get("candidate_set_decision") == "ACCEPT" and review.get(
        "candidate_replacements"
    ):
        errors.append(f"{prefix}: ACCEPT candidate set cannot contain replacements")
    if review.get("candidate_set_decision") == "REVISE" and not review.get(
        "candidate_replacements"
    ):
        errors.append(f"{prefix}: REVISE candidate set requires replacements")
    split_labels = review.get("proposed_split_labels")
    if not isinstance(split_labels, list) or any(
        not isinstance(item, str) or not item.strip() for item in split_labels
    ):
        errors.append(f"{prefix}: proposed_split_labels must be nonblank strings")
    if review.get("sense_status") == "SPLIT_REQUIRED" and not split_labels:
        errors.append(f"{prefix}: SPLIT_REQUIRED requires proposed split labels")
    if review.get("sense_status") != "SPLIT_REQUIRED" and split_labels:
        errors.append(f"{prefix}: split labels are only allowed for SPLIT_REQUIRED")
    notes = review.get("review_notes")
    if not isinstance(notes, str) or not notes.strip():
        errors.append(f"{prefix}: review_notes must be nonblank")
    decisions = [
        review.get(field)
        for field in (
            "definition_decision",
            "part_of_speech_decision",
            "scope_decision",
            "evidence_decision",
            "candidate_set_decision",
        )
    ]
    if review.get("sense_status") == "READY_FOR_CONTRACT_CONSTRUCTION" and any(
        decision != "ACCEPT" for decision in decisions
    ):
        errors.append(f"{prefix}: READY status requires all ACCEPT decisions")
    return replacement_format


def validate_completed_result(
    canonical_input_path: Path,
    completed_path: Path,
    *,
    expected_batch_id: str,
    expected_reviewer_slot: str,
) -> tuple[ValidatedResult | None, list[str], dict[str, int]]:
    errors: list[str] = []
    metrics: dict[str, int] = {
        "case_count": 0,
        "legacy_unbound_replacement_case_count": 0,
        "candidate_bound_replacement_case_count": 0,
    }
    try:
        canonical = strict_json_object(canonical_input_path)
        completed = strict_json_object(completed_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [str(exc)], metrics
    prefix = f"{expected_batch_id}/{expected_reviewer_slot}"
    if set(completed) != set(canonical):
        errors.append(f"{prefix}: top-level keys changed")
    for key, value in canonical.items():
        if key != "cases" and completed.get(key) != value:
            errors.append(f"{prefix}: immutable top-level field changed: {key}")
    if completed.get("batch_id") != expected_batch_id:
        errors.append(f"{prefix}: batch identity mismatch")
    if completed.get("reviewer_slot") != expected_reviewer_slot:
        errors.append(f"{prefix}: reviewer slot mismatch")
    source_cases = canonical.get("cases")
    result_cases = completed.get("cases")
    if not isinstance(source_cases, list) or not isinstance(result_cases, list):
        errors.append(f"{prefix}: cases must be arrays")
        return None, errors, metrics
    if len(source_cases) != len(result_cases):
        errors.append(f"{prefix}: case count changed")
    for index, (source_case, result_case) in enumerate(zip(source_cases, result_cases)):
        case_prefix = f"{prefix}/case_{index + 1}"
        if not isinstance(source_case, Mapping) or not isinstance(result_case, Mapping):
            errors.append(f"{case_prefix}: case must be an object")
            continue
        if set(result_case) != set(source_case):
            errors.append(f"{case_prefix}: case keys changed")
        source_payload = result_case.get("source_payload")
        if source_payload != source_case.get("source_payload"):
            errors.append(f"{case_prefix}: source_payload changed")
        claimed = result_case.get("source_payload_sha256")
        if claimed != source_case.get("source_payload_sha256"):
            errors.append(f"{case_prefix}: source payload binding changed")
        if isinstance(source_payload, Mapping) and claimed != sha256_bytes(
            canonical_json_bytes(source_payload)
        ):
            errors.append(f"{case_prefix}: source payload hash mismatch")
        if not isinstance(source_payload, Mapping):
            errors.append(f"{case_prefix}: source_payload is invalid")
            continue
        replacement_format = _validate_review(
            result_case.get("review"), source_payload, case_prefix, errors
        )
        if "LEGACY_UNBOUND_TEXT" in replacement_format:
            metrics["legacy_unbound_replacement_case_count"] += 1
        if "CANDIDATE_BOUND_OBJECT" in replacement_format:
            metrics["candidate_bound_replacement_case_count"] += 1
        metrics["case_count"] += 1
    if errors:
        return None, errors, metrics
    return (
        ValidatedResult(
            batch_id=expected_batch_id,
            reviewer_slot=expected_reviewer_slot,
            path=completed_path,
            sha256=sha256_file(completed_path),
            payload=completed,
        ),
        [],
        metrics,
    )


def review_core_projection(review: Mapping[str, Any]) -> dict[str, Any]:
    return {field: review[field] for field in CORE_REVIEW_FIELDS}


def review_disagreement_fields(
    reviewer_1: Mapping[str, Any], reviewer_2: Mapping[str, Any]
) -> list[str]:
    return [
        field
        for field in CORE_REVIEW_FIELDS
        if reviewer_1.get(field) != reviewer_2.get(field)
    ]
