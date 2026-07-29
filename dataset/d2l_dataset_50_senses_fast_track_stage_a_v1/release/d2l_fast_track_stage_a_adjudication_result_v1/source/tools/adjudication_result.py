from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import (
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        verify_record,
    )
    from .spec import ALLOWED_SENSE_STATUS, ALLOWED_STANDARD_DECISIONS, REVIEW_FIELDS
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        verify_record,
    )
    from spec import (  # type: ignore
        ALLOWED_SENSE_STATUS,
        ALLOWED_STANDARD_DECISIONS,
        REVIEW_FIELDS,
    )


ADJUDICATION_FIELDS = tuple(REVIEW_FIELDS) + (
    "adjudication_rationale",
    "adjudication_status",
)
DECISION_FIELDS = (
    "definition_decision",
    "part_of_speech_decision",
    "scope_decision",
    "evidence_decision",
    "candidate_set_decision",
)
DECISION_TO_CORRECTION = {
    "definition_decision": "corrected_definition_en",
    "part_of_speech_decision": "corrected_part_of_speech",
    "scope_decision": "corrected_scope",
}


@dataclass(frozen=True)
class ValidatedAdjudication:
    batch_id: str
    path: Path
    sha256: str
    payload: dict[str, Any]
    metrics: dict[str, int]


def _validate_candidate_replacements(
    replacements: Any,
    source: Mapping[str, Any],
    prefix: str,
    errors: list[str],
) -> int:
    if not isinstance(replacements, list):
        errors.append(f"{prefix}: candidate_replacements must be a list")
        return 0
    candidates = {
        (row.get("candidate_id"), row.get("candidate_slot"))
        for row in source.get("candidates", [])
        if isinstance(row, Mapping)
    }
    seen: set[tuple[Any, Any]] = set()
    replacement_targets: dict[tuple[Any, Any], str] = {}
    for index, item in enumerate(replacements):
        if not isinstance(item, Mapping) or set(item) != {
            "candidate_id",
            "candidate_slot",
            "replacement_target_vi",
        }:
            errors.append(f"{prefix}: invalid replacement object at index {index}")
            continue
        binding = (item.get("candidate_id"), item.get("candidate_slot"))
        if binding not in candidates:
            errors.append(f"{prefix}: replacement target is not a source candidate")
        if binding in seen:
            errors.append(f"{prefix}: duplicate replacement target")
        seen.add(binding)
        target = item.get("replacement_target_vi")
        if not isinstance(target, str) or not target.strip():
            errors.append(f"{prefix}: replacement target text is blank")
        else:
            replacement_targets[binding] = target.strip()
    effective_targets = []
    for candidate in source.get("candidates", []):
        if not isinstance(candidate, Mapping):
            continue
        binding = (candidate.get("candidate_id"), candidate.get("candidate_slot"))
        target = replacement_targets.get(binding, candidate.get("candidate_target_vi"))
        if isinstance(target, str):
            effective_targets.append(target.strip().casefold())
    if len(effective_targets) != len(set(effective_targets)):
        errors.append(f"{prefix}: effective candidate targets must remain distinct")
    return len(replacements)


def _validate_adjudication(
    adjudication: Any,
    source: Mapping[str, Any],
    prefix: str,
    errors: list[str],
) -> Counter[str]:
    metrics: Counter[str] = Counter()
    if not isinstance(adjudication, Mapping) or set(adjudication) != set(
        ADJUDICATION_FIELDS
    ):
        errors.append(f"{prefix}: adjudication fields do not match the contract")
        return metrics
    for field in DECISION_FIELDS:
        decision = adjudication.get(field)
        if decision not in ALLOWED_STANDARD_DECISIONS:
            errors.append(f"{prefix}: invalid {field}")
        elif isinstance(decision, str):
            metrics[f"{field}:{decision}"] += 1
    sense_status = adjudication.get("sense_status")
    if sense_status not in ALLOWED_SENSE_STATUS:
        errors.append(f"{prefix}: invalid sense_status")
    elif isinstance(sense_status, str):
        metrics[f"sense_status:{sense_status}"] += 1
    if adjudication.get("review_status") != "COMPLETE":
        errors.append(f"{prefix}: review_status must be COMPLETE")
    if adjudication.get("adjudication_status") != "COMPLETE":
        errors.append(f"{prefix}: adjudication_status must be COMPLETE")
    for decision_field, correction_field in DECISION_TO_CORRECTION.items():
        decision = adjudication.get(decision_field)
        correction = adjudication.get(correction_field)
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
    invalid_ids = adjudication.get("invalid_evidence_context_ids")
    if not isinstance(invalid_ids, list) or len(invalid_ids) != len(set(invalid_ids)):
        errors.append(f"{prefix}: invalid evidence context list")
    elif any(item not in context_ids for item in invalid_ids):
        errors.append(f"{prefix}: invalid evidence context ID is not in the source")
    if adjudication.get("evidence_decision") == "ACCEPT" and invalid_ids:
        errors.append(f"{prefix}: ACCEPT evidence cannot list invalid contexts")
    if adjudication.get("evidence_decision") == "REVISE" and not invalid_ids:
        errors.append(f"{prefix}: REVISE evidence requires invalid context IDs")
    replacement_count = _validate_candidate_replacements(
        adjudication.get("candidate_replacements"), source, prefix, errors
    )
    metrics["candidate_replacement_count"] += replacement_count
    candidate_decision = adjudication.get("candidate_set_decision")
    if candidate_decision == "ACCEPT" and replacement_count:
        errors.append(f"{prefix}: ACCEPT candidate set cannot contain replacements")
    if candidate_decision == "REVISE" and not replacement_count:
        errors.append(f"{prefix}: REVISE candidate set requires replacements")
    split_labels = adjudication.get("proposed_split_labels")
    if not isinstance(split_labels, list) or len(split_labels) != len(set(split_labels)):
        errors.append(f"{prefix}: proposed_split_labels must be a unique list")
    elif any(not isinstance(item, str) or not item.strip() for item in split_labels):
        errors.append(f"{prefix}: proposed_split_labels must be nonblank strings")
    if sense_status == "SPLIT_REQUIRED" and not split_labels:
        errors.append(f"{prefix}: SPLIT_REQUIRED requires proposed split labels")
    if sense_status != "SPLIT_REQUIRED" and split_labels:
        errors.append(f"{prefix}: split labels are only allowed for SPLIT_REQUIRED")
    notes = adjudication.get("review_notes")
    if not isinstance(notes, str) or not notes.strip():
        errors.append(f"{prefix}: review_notes must be nonblank")
    rationale = adjudication.get("adjudication_rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        errors.append(f"{prefix}: adjudication_rationale must be nonblank")
    if sense_status == "READY_FOR_CONTRACT_CONSTRUCTION" and any(
        adjudication.get(field) not in {"ACCEPT", "REVISE"}
        for field in DECISION_FIELDS
    ):
        errors.append(
            f"{prefix}: READY status requires every decision to be resolved"
        )
    return metrics


def validate_completed_adjudication(
    canonical: Mapping[str, Any],
    completed_path: Path,
    *,
    expected_batch_id: str,
) -> tuple[ValidatedAdjudication | None, list[str], dict[str, int]]:
    errors: list[str] = []
    metrics: Counter[str] = Counter()
    try:
        completed = strict_json_object(completed_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [str(exc)], {}
    prefix = f"{expected_batch_id}/reviewer_3_adjudicator"
    if set(completed) != set(canonical):
        errors.append(f"{prefix}: top-level keys changed")
    for key, value in canonical.items():
        if key != "cases" and completed.get(key) != value:
            errors.append(f"{prefix}: immutable top-level field changed: {key}")
    if completed.get("batch_id") != expected_batch_id:
        errors.append(f"{prefix}: batch identity mismatch")
    if completed.get("reviewer_slot") != "reviewer_3_adjudicator":
        errors.append(f"{prefix}: reviewer slot mismatch")
    source_cases = canonical.get("cases")
    result_cases = completed.get("cases")
    if not isinstance(source_cases, list) or not isinstance(result_cases, list):
        errors.append(f"{prefix}: cases must be arrays")
        return None, errors, dict(metrics)
    if canonical.get("case_count") != len(source_cases):
        errors.append(f"{prefix}: canonical case_count mismatch")
    if completed.get("case_count") != len(result_cases):
        errors.append(f"{prefix}: completed case_count mismatch")
    if len(source_cases) != len(result_cases):
        errors.append(f"{prefix}: case count changed")
    source_binding = [
        {
            "adjudication_case_id": row.get("adjudication_case_id"),
            "adjudication_case_sha256": row.get("adjudication_case_sha256"),
        }
        for row in source_cases
        if isinstance(row, Mapping)
    ]
    if canonical.get("source_input_sha256") != sha256_bytes(
        canonical_json_bytes(source_binding)
    ):
        errors.append(f"{prefix}: canonical source input binding mismatch")
    seen_senses: set[Any] = set()
    for index, (source_case, result_case) in enumerate(zip(source_cases, result_cases)):
        case_prefix = f"{prefix}/case_{index + 1}"
        if not isinstance(source_case, Mapping) or not isinstance(result_case, Mapping):
            errors.append(f"{case_prefix}: case must be an object")
            continue
        if not verify_record(source_case, "adjudication_case_sha256"):
            errors.append(f"{case_prefix}: canonical adjudication case hash mismatch")
        if set(result_case) != set(source_case):
            errors.append(f"{case_prefix}: case keys changed")
        for key, value in source_case.items():
            if key != "adjudication" and result_case.get(key) != value:
                errors.append(f"{case_prefix}: immutable case field changed: {key}")
        source_payload = result_case.get("source_payload")
        claimed = result_case.get("source_payload_sha256")
        if not isinstance(source_payload, Mapping):
            errors.append(f"{case_prefix}: source_payload is invalid")
            continue
        if claimed != sha256_bytes(canonical_json_bytes(source_payload)):
            errors.append(f"{case_prefix}: source payload hash mismatch")
        sense_id = result_case.get("sense_id")
        if sense_id in seen_senses:
            errors.append(f"{case_prefix}: duplicate sense_id")
        seen_senses.add(sense_id)
        case_metrics = _validate_adjudication(
            result_case.get("adjudication"), source_payload, case_prefix, errors
        )
        metrics.update(case_metrics)
        if result_case.get("provider_call_count") != 0:
            errors.append(f"{case_prefix}: provider_call_count must remain zero")
        if result_case.get("stage_b_gold_label") is not None:
            errors.append(f"{case_prefix}: Stage B gold must remain null")
        if result_case.get("final_glossary_decision") is not None:
            errors.append(f"{case_prefix}: final glossary decision must remain null")
        metrics["case_count"] += 1
    if errors:
        return None, errors, dict(metrics)
    return (
        ValidatedAdjudication(
            batch_id=expected_batch_id,
            path=completed_path,
            sha256=sha256_file(completed_path),
            payload=completed,
            metrics=dict(metrics),
        ),
        [],
        dict(metrics),
    )
