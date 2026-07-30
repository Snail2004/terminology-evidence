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
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.remaining_stage_b_review_result import (
    ALLOWED_LABELS,
)


EXPECTED_ADJUDICATION_COUNT = 55
ADJUDICATION_FIELDS = (
    "adjudicator_label",
    "adjudication_reason",
    "adjudication_status",
)


@dataclass(frozen=True)
class ValidatedAdjudication:
    path: Path
    sha256: str
    payload: dict[str, Any]
    cases_by_candidate: dict[str, dict[str, Any]]
    label_counts: dict[str, int]


def validate_completed_adjudication(
    canonical_input_path: Path,
    completed_path: Path,
) -> tuple[ValidatedAdjudication | None, list[str]]:
    errors: list[str] = []
    try:
        canonical = strict_json_object(canonical_input_path)
        completed = strict_json_object(completed_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [str(exc)]
    prefix = "reviewer_3_adjudicator"
    if set(completed) != set(canonical):
        errors.append(f"{prefix}: top-level keys changed")
    for key, value in canonical.items():
        if key != "cases" and completed.get(key) != value:
            errors.append(f"{prefix}: immutable top-level field changed: {key}")
    if completed.get("reviewer_slot") != prefix:
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
    if (
        len(source_cases) != EXPECTED_ADJUDICATION_COUNT
        or len(result_cases) != len(source_cases)
    ):
        errors.append(
            f"{prefix}: expected exactly {EXPECTED_ADJUDICATION_COUNT} unchanged cases"
        )
    cases_by_candidate: dict[str, dict[str, Any]] = {}
    label_counts = {label: 0 for label in ALLOWED_LABELS}
    source_binding: list[dict[str, Any]] = []
    for index, (source_case, result_case) in enumerate(
        zip(source_cases, result_cases), 1
    ):
        case_prefix = f"{prefix}/case_{index}"
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
        adjudication = result_case.get("adjudication")
        if not isinstance(adjudication, Mapping) or set(adjudication) != set(
            ADJUDICATION_FIELDS
        ):
            errors.append(f"{case_prefix}: adjudication fields do not match contract")
            continue
        label = adjudication.get("adjudicator_label")
        if label not in ALLOWED_LABELS:
            errors.append(f"{case_prefix}: invalid adjudicator_label")
        elif isinstance(label, str):
            label_counts[label] += 1
        reason = adjudication.get("adjudication_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{case_prefix}: adjudication_reason must be nonblank")
        if adjudication.get("adjudication_status") != "COMPLETE":
            errors.append(f"{case_prefix}: adjudication_status must be COMPLETE")
        candidate_id = result_case.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            errors.append(f"{case_prefix}: candidate_id is invalid")
        elif candidate_id in cases_by_candidate:
            errors.append(f"{case_prefix}: duplicate candidate_id")
        else:
            cases_by_candidate[candidate_id] = dict(result_case)
        if result_case.get("provider_call_count") != 0:
            errors.append(f"{case_prefix}: provider_call_count must remain zero")
        if result_case.get("final_gold_label") is not None:
            errors.append(f"{case_prefix}: final gold label must remain null")
        if result_case.get("final_glossary_decision") is not None:
            errors.append(f"{case_prefix}: final glossary decision must remain null")
        source_binding.append(
            {
                "adjudication_case_id": result_case.get("adjudication_case_id"),
                "adjudication_case_sha256": result_case.get(
                    "adjudication_case_sha256"
                ),
            }
        )
    if completed.get("source_input_sha256") != sha256_bytes(
        canonical_json_bytes(source_binding)
    ):
        errors.append(f"{prefix}: source input binding mismatch")
    if len(cases_by_candidate) != EXPECTED_ADJUDICATION_COUNT:
        errors.append(
            f"{prefix}: adjudication coverage is not "
            f"{EXPECTED_ADJUDICATION_COUNT}/{EXPECTED_ADJUDICATION_COUNT}"
        )
    if errors:
        return None, errors
    return (
        ValidatedAdjudication(
            path=completed_path,
            sha256=sha256_file(completed_path),
            payload=completed,
            cases_by_candidate=cases_by_candidate,
            label_counts={key: value for key, value in label_counts.items() if value},
        ),
        [],
    )
