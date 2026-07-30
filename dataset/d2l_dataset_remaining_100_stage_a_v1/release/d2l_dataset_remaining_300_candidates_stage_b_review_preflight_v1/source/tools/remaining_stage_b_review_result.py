from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    verify_record,
)


EXPECTED_CASE_COUNT = 300
ALLOWED_LABELS = (
    "ACCEPT",
    "CONDITIONAL",
    "REJECT",
    "SPLIT_REQUIRED",
    "HUMAN_UNJUDGEABLE",
)
REVIEW_FIELDS = (
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
MISSING_ALLOWED_SCOPE = "MISSING_ALLOWED_SCOPE"


@dataclass(frozen=True)
class ReviewIssue:
    code: str
    reviewer_slot: str
    case_index: int | None
    candidate_id: str | None
    message: str


@dataclass(frozen=True)
class ValidatedReview:
    reviewer_slot: str
    path: Path
    sha256: str
    payload: dict[str, Any]
    cases_by_candidate: dict[str, dict[str, Any]]
    label_counts: dict[str, int]


def _issue(
    issues: list[ReviewIssue],
    *,
    code: str,
    slot: str,
    index: int | None,
    candidate_id: str | None,
    message: str,
) -> None:
    issues.append(
        ReviewIssue(
            code=code,
            reviewer_slot=slot,
            case_index=index,
            candidate_id=candidate_id,
            message=message,
        )
    )


def _string_list(
    value: Any,
    *,
    field: str,
    slot: str,
    index: int,
    candidate_id: str | None,
    issues: list[ReviewIssue],
) -> list[str]:
    if not isinstance(value, list):
        _issue(
            issues,
            code="INVALID_REVIEW_FIELD",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message=f"{field} must be a list",
        )
        return []
    if any(not isinstance(item, str) or not item.strip() for item in value):
        _issue(
            issues,
            code="INVALID_REVIEW_FIELD",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message=f"{field} must contain nonblank strings",
        )
        return []
    normalized = [item.strip().casefold() for item in value]
    if len(normalized) != len(set(normalized)):
        _issue(
            issues,
            code="INVALID_REVIEW_FIELD",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message=f"{field} contains duplicates",
        )
    return value


def _validate_review(
    review: Any,
    source_payload: Mapping[str, Any],
    *,
    slot: str,
    index: int,
    issues: list[ReviewIssue],
) -> str | None:
    candidate_id = source_payload.get("candidate_id")
    candidate_id = candidate_id if isinstance(candidate_id, str) else None
    if not isinstance(review, Mapping) or set(review) != set(REVIEW_FIELDS):
        _issue(
            issues,
            code="INVALID_REVIEW_FIELDS",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="review fields do not match the Stage B contract",
        )
        return None
    label = review.get("candidate_gold_label")
    if label not in ALLOWED_LABELS:
        _issue(
            issues,
            code="INVALID_LABEL",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="invalid candidate_gold_label",
        )
        return None
    if review.get("review_status") != "COMPLETE":
        _issue(
            issues,
            code="INCOMPLETE_REVIEW",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="review_status must be COMPLETE",
        )
    allowed_scope = review.get("allowed_scope")
    if not isinstance(allowed_scope, str):
        _issue(
            issues,
            code="INVALID_REVIEW_FIELD",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="allowed_scope must be a string",
        )
    elif label not in {"REJECT", "HUMAN_UNJUDGEABLE"} and not allowed_scope.strip():
        _issue(
            issues,
            code=MISSING_ALLOWED_SCOPE,
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message=f"allowed_scope is required for {label}",
        )

    validated = _string_list(
        review.get("validated_variants"),
        field="validated_variants",
        slot=slot,
        index=index,
        candidate_id=candidate_id,
        issues=issues,
    )
    rejected = _string_list(
        review.get("rejected_variants"),
        field="rejected_variants",
        slot=slot,
        index=index,
        candidate_id=candidate_id,
        issues=issues,
    )
    reason_codes = _string_list(
        review.get("reason_codes"),
        field="reason_codes",
        slot=slot,
        index=index,
        candidate_id=candidate_id,
        issues=issues,
    )
    positive_refs = _string_list(
        review.get("positive_context_refs"),
        field="positive_context_refs",
        slot=slot,
        index=index,
        candidate_id=candidate_id,
        issues=issues,
    )
    _string_list(
        review.get("vietnamese_evidence_refs"),
        field="vietnamese_evidence_refs",
        slot=slot,
        index=index,
        candidate_id=candidate_id,
        issues=issues,
    )
    if not reason_codes:
        _issue(
            issues,
            code="MISSING_REASON",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="at least one reason code is required",
        )
    normalized_validated = {item.strip().casefold() for item in validated}
    normalized_rejected = {item.strip().casefold() for item in rejected}
    if normalized_validated & normalized_rejected:
        _issue(
            issues,
            code="VARIANT_OVERLAP",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="validated and rejected variants overlap",
        )
    target = source_payload.get("candidate_target_vi")
    normalized_target = target.strip().casefold() if isinstance(target, str) else None
    if label in {"ACCEPT", "CONDITIONAL"}:
        if normalized_target not in normalized_validated:
            _issue(
                issues,
                code="TARGET_NOT_VALIDATED",
                slot=slot,
                index=index,
                candidate_id=candidate_id,
                message="accepted candidate is not a validated variant",
            )
        if not positive_refs:
            _issue(
                issues,
                code="MISSING_POSITIVE_EVIDENCE",
                slot=slot,
                index=index,
                candidate_id=candidate_id,
                message=f"{label} requires positive context evidence",
            )
    if label == "REJECT" and normalized_target not in normalized_rejected:
        _issue(
            issues,
            code="TARGET_NOT_REJECTED",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="rejected candidate is not a rejected variant",
        )

    contexts = source_payload.get("contexts")
    if not isinstance(contexts, list):
        _issue(
            issues,
            code="INVALID_CONTEXTS",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="source contexts are invalid",
        )
        contexts = []
    contexts_by_id = {
        row.get("context_id"): row
        for row in contexts
        if isinstance(row, Mapping) and isinstance(row.get("context_id"), str)
    }
    for context_id in positive_refs:
        context = contexts_by_id.get(context_id)
        if context is None:
            message = f"unknown positive context ref {context_id}"
        elif (
            context.get("synthetic")
            or context.get("boundary_only")
            or context.get("sense_relation") != "SAME_SENSE"
        ):
            message = "positive context ref is not real same-sense evidence"
        else:
            continue
        _issue(
            issues,
            code="INVALID_POSITIVE_EVIDENCE",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message=message,
        )
    notes = review.get("review_notes")
    if not isinstance(notes, str) or not notes.strip():
        _issue(
            issues,
            code="MISSING_REVIEW_NOTES",
            slot=slot,
            index=index,
            candidate_id=candidate_id,
            message="review_notes must be nonblank",
        )
    return label if isinstance(label, str) else None


def validate_completed_review(
    canonical_input_path: Path,
    completed_path: Path,
    *,
    expected_reviewer_slot: str,
) -> tuple[ValidatedReview | None, list[ReviewIssue]]:
    issues: list[ReviewIssue] = []
    try:
        canonical = strict_json_object(canonical_input_path)
        completed = strict_json_object(completed_path)
    except (OSError, UnicodeError, ValueError) as exc:
        _issue(
            issues,
            code="INVALID_JSON",
            slot=expected_reviewer_slot,
            index=None,
            candidate_id=None,
            message=str(exc),
        )
        return None, issues
    slot = expected_reviewer_slot
    if set(completed) != set(canonical):
        _issue(
            issues,
            code="TOP_LEVEL_KEYS_CHANGED",
            slot=slot,
            index=None,
            candidate_id=None,
            message="top-level keys changed",
        )
    for key, value in canonical.items():
        if key != "cases" and completed.get(key) != value:
            _issue(
                issues,
                code="IMMUTABLE_TOP_LEVEL_CHANGED",
                slot=slot,
                index=None,
                candidate_id=None,
                message=f"immutable top-level field changed: {key}",
            )
    source_cases = canonical.get("cases")
    result_cases = completed.get("cases")
    if not isinstance(source_cases, list) or not isinstance(result_cases, list):
        _issue(
            issues,
            code="INVALID_CASE_ARRAY",
            slot=slot,
            index=None,
            candidate_id=None,
            message="cases must be arrays",
        )
        return None, issues
    if len(source_cases) != EXPECTED_CASE_COUNT or len(result_cases) != len(source_cases):
        _issue(
            issues,
            code="CASE_COUNT_MISMATCH",
            slot=slot,
            index=None,
            candidate_id=None,
            message=f"expected exactly {EXPECTED_CASE_COUNT} unchanged cases",
        )
    cases_by_candidate: dict[str, dict[str, Any]] = {}
    label_counts = {label: 0 for label in ALLOWED_LABELS}
    source_binding: list[dict[str, Any]] = []
    for index, (source_case, result_case) in enumerate(
        zip(source_cases, result_cases), 1
    ):
        if not isinstance(source_case, Mapping) or not isinstance(result_case, Mapping):
            _issue(
                issues,
                code="INVALID_CASE",
                slot=slot,
                index=index,
                candidate_id=None,
                message="case must be an object",
            )
            continue
        source_payload = result_case.get("source_payload")
        candidate_id = (
            source_payload.get("candidate_id")
            if isinstance(source_payload, Mapping)
            else None
        )
        candidate_id = candidate_id if isinstance(candidate_id, str) else None
        if not verify_record(source_case, "case_sha256"):
            _issue(
                issues,
                code="CANONICAL_CASE_HASH_MISMATCH",
                slot=slot,
                index=index,
                candidate_id=candidate_id,
                message="canonical case hash mismatch",
            )
        if set(result_case) != set(source_case):
            _issue(
                issues,
                code="CASE_KEYS_CHANGED",
                slot=slot,
                index=index,
                candidate_id=candidate_id,
                message="case keys changed",
            )
        for key, value in source_case.items():
            if key != "review" and result_case.get(key) != value:
                _issue(
                    issues,
                    code="IMMUTABLE_CASE_CHANGED",
                    slot=slot,
                    index=index,
                    candidate_id=candidate_id,
                    message=f"immutable case field changed: {key}",
                )
        if not isinstance(source_payload, Mapping):
            _issue(
                issues,
                code="INVALID_SOURCE_PAYLOAD",
                slot=slot,
                index=index,
                candidate_id=candidate_id,
                message="source payload is invalid",
            )
            continue
        if result_case.get("source_payload_sha256") != sha256_bytes(
            canonical_json_bytes(source_payload)
        ):
            _issue(
                issues,
                code="SOURCE_PAYLOAD_HASH_MISMATCH",
                slot=slot,
                index=index,
                candidate_id=candidate_id,
                message="source payload hash mismatch",
            )
        label = _validate_review(
            result_case.get("review"),
            source_payload,
            slot=slot,
            index=index,
            issues=issues,
        )
        if label is not None:
            label_counts[label] += 1
        if not candidate_id or candidate_id in cases_by_candidate:
            _issue(
                issues,
                code="INVALID_CANDIDATE_ID",
                slot=slot,
                index=index,
                candidate_id=candidate_id,
                message="candidate_id is invalid or duplicated",
            )
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
        _issue(
            issues,
            code="SOURCE_INPUT_BINDING_MISMATCH",
            slot=slot,
            index=None,
            candidate_id=None,
            message="source input binding mismatch",
        )
    if len(cases_by_candidate) != EXPECTED_CASE_COUNT:
        _issue(
            issues,
            code="CANDIDATE_COVERAGE_MISMATCH",
            slot=slot,
            index=None,
            candidate_id=None,
            message="candidate coverage is not 300/300",
        )
    return (
        ValidatedReview(
            reviewer_slot=slot,
            path=completed_path,
            sha256=sha256_file(completed_path),
            payload=completed,
            cases_by_candidate=cases_by_candidate,
            label_counts={key: value for key, value in label_counts.items() if value},
        ),
        issues,
    )
