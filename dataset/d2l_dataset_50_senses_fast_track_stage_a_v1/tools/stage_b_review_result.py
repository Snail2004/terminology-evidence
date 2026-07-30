from __future__ import annotations

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
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        verify_record,
    )


STAGE_B_ALLOWED_LABELS = (
    "ACCEPT",
    "CONDITIONAL",
    "REJECT",
    "SPLIT_REQUIRED",
    "HUMAN_UNJUDGEABLE",
)
STAGE_B_REVIEW_FIELDS = (
    "candidate_gold_label",
    "allowed_scope",
    "validated_variants",
    "rejected_variants",
    "reason_codes",
    "positive_context_refs",
    "vietnamese_evidence_refs",
    "review_notes",
    "review_status",
)


@dataclass(frozen=True)
class ValidatedStageBReview:
    reviewer_slot: str
    path: Path
    sha256: str
    payload: dict[str, Any]
    cases_by_candidate: dict[str, dict[str, Any]]
    label_counts: dict[str, int]


def _string_list(
    value: Any,
    *,
    field: str,
    prefix: str,
    errors: list[str],
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{prefix}: {field} must be a list")
        return []
    if any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{prefix}: {field} must contain nonblank strings")
        return []
    normalized = [item.strip().casefold() for item in value]
    if len(normalized) != len(set(normalized)):
        errors.append(f"{prefix}: {field} contains duplicates")
    return value


def _validate_review(
    review: Any,
    source_payload: Mapping[str, Any],
    *,
    prefix: str,
    errors: list[str],
) -> str | None:
    if not isinstance(review, Mapping) or set(review) != set(STAGE_B_REVIEW_FIELDS):
        errors.append(f"{prefix}: review fields do not match the Stage B contract")
        return None
    label = review.get("candidate_gold_label")
    if label not in STAGE_B_ALLOWED_LABELS:
        errors.append(f"{prefix}: invalid candidate_gold_label")
        return None
    if review.get("review_status") != "COMPLETE":
        errors.append(f"{prefix}: review_status must be COMPLETE")
    allowed_scope = review.get("allowed_scope")
    if not isinstance(allowed_scope, str):
        errors.append(f"{prefix}: allowed_scope must be a string")
    elif label not in {"REJECT", "HUMAN_UNJUDGEABLE"} and not allowed_scope.strip():
        errors.append(f"{prefix}: allowed_scope is required for {label}")

    validated = _string_list(
        review.get("validated_variants"),
        field="validated_variants",
        prefix=prefix,
        errors=errors,
    )
    rejected = _string_list(
        review.get("rejected_variants"),
        field="rejected_variants",
        prefix=prefix,
        errors=errors,
    )
    reason_codes = _string_list(
        review.get("reason_codes"),
        field="reason_codes",
        prefix=prefix,
        errors=errors,
    )
    positive_refs = _string_list(
        review.get("positive_context_refs"),
        field="positive_context_refs",
        prefix=prefix,
        errors=errors,
    )
    _string_list(
        review.get("vietnamese_evidence_refs"),
        field="vietnamese_evidence_refs",
        prefix=prefix,
        errors=errors,
    )
    if not reason_codes:
        errors.append(f"{prefix}: at least one reason code is required")
    normalized_validated = {item.strip().casefold() for item in validated}
    normalized_rejected = {item.strip().casefold() for item in rejected}
    if normalized_validated & normalized_rejected:
        errors.append(f"{prefix}: validated and rejected variants overlap")
    target = source_payload.get("candidate_target_vi")
    normalized_target = target.strip().casefold() if isinstance(target, str) else None
    if label in {"ACCEPT", "CONDITIONAL"}:
        if normalized_target not in normalized_validated:
            errors.append(f"{prefix}: accepted candidate is not a validated variant")
        if not positive_refs:
            errors.append(f"{prefix}: {label} requires positive context evidence")
    if label == "REJECT" and normalized_target not in normalized_rejected:
        errors.append(f"{prefix}: rejected candidate is not a rejected variant")

    contexts = source_payload.get("contexts")
    if not isinstance(contexts, list):
        errors.append(f"{prefix}: source contexts are invalid")
        contexts = []
    contexts_by_id = {
        row.get("context_id"): row
        for row in contexts
        if isinstance(row, Mapping) and isinstance(row.get("context_id"), str)
    }
    for context_id in positive_refs:
        context = contexts_by_id.get(context_id)
        if context is None:
            errors.append(f"{prefix}: unknown positive context ref {context_id}")
        elif (
            context.get("synthetic")
            or context.get("boundary_only")
            or context.get("sense_relation") != "SAME_SENSE"
        ):
            errors.append(f"{prefix}: positive context ref is not real same-sense evidence")
    notes = review.get("review_notes")
    if not isinstance(notes, str) or not notes.strip():
        errors.append(f"{prefix}: review_notes must be nonblank")
    return label if isinstance(label, str) else None


def validate_completed_stage_b_review(
    canonical_input_path: Path,
    completed_path: Path,
    *,
    expected_reviewer_slot: str,
) -> tuple[ValidatedStageBReview | None, list[str]]:
    errors: list[str] = []
    try:
        canonical = strict_json_object(canonical_input_path)
        completed = strict_json_object(completed_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [str(exc)]
    prefix = expected_reviewer_slot
    if set(completed) != set(canonical):
        errors.append(f"{prefix}: top-level keys changed")
    for key, value in canonical.items():
        if key != "cases" and completed.get(key) != value:
            errors.append(f"{prefix}: immutable top-level field changed: {key}")
    if completed.get("reviewer_slot") != expected_reviewer_slot:
        errors.append(f"{prefix}: reviewer slot mismatch")
    if completed.get("provider_call_count") != 0:
        errors.append(f"{prefix}: provider_call_count must remain zero")
    if completed.get("final_gold_label_count") != 0:
        errors.append(f"{prefix}: final_gold_label_count must remain zero")
    if completed.get("final_glossary_decision") is not None:
        errors.append(f"{prefix}: final glossary decision must remain null")

    source_cases = canonical.get("cases")
    result_cases = completed.get("cases")
    if not isinstance(source_cases, list) or not isinstance(result_cases, list):
        return None, errors + [f"{prefix}: cases must be arrays"]
    if len(source_cases) != 150 or len(result_cases) != len(source_cases):
        errors.append(f"{prefix}: expected exactly 150 unchanged cases")
    source_binding: list[dict[str, Any]] = []
    cases_by_candidate: dict[str, dict[str, Any]] = {}
    label_counts: dict[str, int] = {label: 0 for label in STAGE_B_ALLOWED_LABELS}
    for index, (source_case, result_case) in enumerate(zip(source_cases, result_cases), 1):
        case_prefix = f"{prefix}/case_{index}"
        if not isinstance(source_case, Mapping) or not isinstance(result_case, Mapping):
            errors.append(f"{case_prefix}: case must be an object")
            continue
        if not verify_record(source_case, "case_sha256"):
            errors.append(f"{case_prefix}: canonical case hash mismatch")
        if set(result_case) != set(source_case):
            errors.append(f"{case_prefix}: case keys changed")
        for key, value in source_case.items():
            if key != "review" and result_case.get(key) != value:
                errors.append(f"{case_prefix}: immutable case field changed: {key}")
        source_payload = result_case.get("source_payload")
        claimed = result_case.get("source_payload_sha256")
        if not isinstance(source_payload, Mapping):
            errors.append(f"{case_prefix}: source_payload is invalid")
            continue
        if claimed != sha256_bytes(canonical_json_bytes(source_payload)):
            errors.append(f"{case_prefix}: source payload hash mismatch")
        label = _validate_review(
            result_case.get("review"),
            source_payload,
            prefix=case_prefix,
            errors=errors,
        )
        if label is not None:
            label_counts[label] += 1
        candidate_id = source_payload.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            errors.append(f"{case_prefix}: candidate_id is invalid")
        elif candidate_id in cases_by_candidate:
            errors.append(f"{case_prefix}: duplicate candidate_id")
        else:
            cases_by_candidate[candidate_id] = dict(result_case)
        source_binding.append(
            {
                "case_id": result_case.get("case_id"),
                "case_sha256": result_case.get("case_sha256"),
            }
        )
    if completed.get("source_input_sha256") != sha256_bytes(
        canonical_json_bytes(source_binding)
    ):
        errors.append(f"{prefix}: source input binding mismatch")
    if len(cases_by_candidate) != 150:
        errors.append(f"{prefix}: candidate coverage is not 150/150")
    if errors:
        return None, errors
    return (
        ValidatedStageBReview(
            reviewer_slot=expected_reviewer_slot,
            path=completed_path,
            sha256=sha256_file(completed_path),
            payload=completed,
            cases_by_candidate=cases_by_candidate,
            label_counts={key: value for key, value in label_counts.items() if value},
        ),
        [],
    )
