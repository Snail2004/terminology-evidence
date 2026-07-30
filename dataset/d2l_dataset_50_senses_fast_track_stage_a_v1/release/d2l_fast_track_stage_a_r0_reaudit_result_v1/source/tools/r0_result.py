from __future__ import annotations

import copy
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import (
        canonical_json_bytes,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
    )
    from .r0_repair import blank_review
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        canonical_json_bytes,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
    )
    from r0_repair import blank_review  # type: ignore


RESULT_POLICY_ID = "d2l-fast-track-stage-a-r0-reaudit-result-v1.0"
EXPECTED_TERMS = ("BatchNorm", "broadcasting", "interaction matrix", "single GPU")
DECISION_FIELDS = (
    "definition_decision",
    "part_of_speech_decision",
    "scope_decision",
    "evidence_decision",
    "candidate_set_decision",
)


@dataclass(frozen=True)
class ValidatedR0Result:
    path: Path
    sha256: str
    payload: dict[str, Any]
    records: tuple[dict[str, Any], ...]


def load_canonical_input(repair_root: Path) -> dict[str, Any]:
    report = strict_json_object(repair_root / "repair_report.json")
    zip_path = repair_root / str(report.get("handoff_zip"))
    if sha256_file(zip_path) != report.get("handoff_zip_sha256"):
        raise ValueError("canonical R0 handoff ZIP hash mismatch")
    try:
        with zipfile.ZipFile(zip_path) as archive:
            raw = archive.read("reviewer_input.json")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"cannot read canonical R0 reviewer input: {exc}") from exc
    value = json.loads(raw.decode("utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise ValueError("canonical R0 reviewer input must be an object")
    return value


def _validate_review(
    review: Any, *, source_term: str, prefix: str, errors: list[str]
) -> None:
    expected_fields = set(blank_review())
    if not isinstance(review, Mapping) or set(review) != expected_fields:
        errors.append(f"{prefix}: review fields do not match the contract")
        return
    for field in DECISION_FIELDS:
        if review.get(field) != "ACCEPT":
            errors.append(f"{prefix}: {field} must be ACCEPT to unlock exact-50")
    for field in (
        "corrected_definition_en",
        "corrected_part_of_speech",
        "corrected_scope",
    ):
        if review.get(field) != "":
            errors.append(f"{prefix}: {field} must be blank for ACCEPT")
    for field in (
        "invalid_evidence_context_ids",
        "candidate_replacements",
        "proposed_split_labels",
    ):
        if review.get(field) != []:
            errors.append(f"{prefix}: {field} must be empty for ACCEPT")
    if review.get("sense_status") != "READY_FOR_CONTRACT_CONSTRUCTION":
        errors.append(f"{prefix}: sense_status is not ready")
    if review.get("review_status") != "COMPLETE":
        errors.append(f"{prefix}: review_status must be COMPLETE")
    notes = review.get("review_notes")
    if not isinstance(notes, str) or not notes.strip():
        errors.append(f"{prefix}: review_notes must be nonblank")
    if source_term not in EXPECTED_TERMS:
        errors.append(f"{prefix}: unexpected R0 source term")


def validate_completed_r0_result(
    canonical: Mapping[str, Any], completed_path: Path
) -> tuple[ValidatedR0Result | None, list[str]]:
    errors: list[str] = []
    try:
        completed = strict_json_object(completed_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [str(exc)]
    if set(completed) != set(canonical):
        errors.append("R0 result top-level keys changed")
    for key, value in canonical.items():
        if key != "cases" and completed.get(key) != value:
            errors.append(f"R0 result immutable top-level field changed: {key}")
    source_cases = canonical.get("cases")
    result_cases = completed.get("cases")
    if not isinstance(source_cases, list) or not isinstance(result_cases, list):
        return None, errors + ["R0 result cases must be arrays"]
    if len(source_cases) != 4 or len(result_cases) != 4:
        errors.append("R0 result must contain exactly four cases")
    records: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for index, (source_case, result_case) in enumerate(zip(source_cases, result_cases)):
        prefix = f"R0/case_{index + 1}"
        if not isinstance(source_case, Mapping) or not isinstance(result_case, Mapping):
            errors.append(f"{prefix}: case must be an object")
            continue
        if set(result_case) != set(source_case):
            errors.append(f"{prefix}: case keys changed")
        for key, value in source_case.items():
            if key != "review" and result_case.get(key) != value:
                errors.append(f"{prefix}: immutable case field changed: {key}")
        source_payload = result_case.get("source_payload")
        if not isinstance(source_payload, Mapping):
            errors.append(f"{prefix}: source_payload is invalid")
            continue
        if result_case.get("source_payload_sha256") != sha256_bytes(
            canonical_json_bytes(source_payload)
        ):
            errors.append(f"{prefix}: source payload hash mismatch")
        sense_id = result_case.get("sense_id")
        if sense_id in seen:
            errors.append(f"{prefix}: duplicate sense_id")
        seen.add(sense_id)
        source_term = str(source_payload.get("source_term", ""))
        _validate_review(
            result_case.get("review"),
            source_term=source_term,
            prefix=prefix,
            errors=errors,
        )
        if result_case.get("provider_call_count") != 0:
            errors.append(f"{prefix}: provider_call_count must remain zero")
        if result_case.get("stage_b_gold_label") is not None:
            errors.append(f"{prefix}: Stage B gold must remain null")
        if result_case.get("final_glossary_decision") is not None:
            errors.append(f"{prefix}: final glossary decision must remain null")
        records.append(
            seal_record(
                {
                    "schema_id": "D2LFastTrackStageAR0ReauditResultRecordV1",
                    "schema_version": "1.0.0",
                    "policy_id": RESULT_POLICY_ID,
                    "sense_id": sense_id,
                    "source_term": source_term,
                    "source_case_sha256": source_case.get("case_sha256"),
                    "source_payload": copy.deepcopy(dict(source_payload)),
                    "source_payload_sha256": result_case.get("source_payload_sha256"),
                    "review": copy.deepcopy(result_case.get("review")),
                    "result_file_sha256": sha256_file(completed_path),
                    "stage_a_status": "READY_FOR_CONTRACT_CONSTRUCTION",
                    "provider_call_count": 0,
                    "stage_b_gold_label": None,
                    "final_glossary_decision": None,
                },
                "result_record_sha256",
            )
        )
    if {record["source_term"] for record in records} != set(EXPECTED_TERMS):
        errors.append("R0 result term set mismatch")
    if errors:
        return None, errors
    return (
        ValidatedR0Result(
            path=completed_path,
            sha256=sha256_file(completed_path),
            payload=completed,
            records=tuple(sorted(records, key=lambda row: row["source_term"].casefold())),
        ),
        [],
    )
