from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import read_csv, read_jsonl
from evidence import load_v3_context_authority, validate_explicit_evidence
from policy import load_review_schema


DEFINITION_LABELS = {"ACCEPTED", "CORRECTED", "REJECTED"}
POS_LABELS = {"ACCEPTED", "CORRECTED", "UNCERTAIN", "REJECTED"}
LIST_FIELDS = (
    "positive_definition_evidence_ids",
    "positive_pos_evidence_ids",
    "boundary_context_ids",
    "risk_flags",
)


def _list_field(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def normalize_review_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for field in LIST_FIELDS:
        normalized[field] = _list_field(normalized.get(field))
    confidence = normalized.get("confidence")
    if confidence not in (None, ""):
        try:
            normalized["confidence"] = float(confidence)
        except (TypeError, ValueError):
            pass
    return normalized


def _is_blank(row: dict[str, Any]) -> bool:
    fields = (
        "definition_status",
        "effective_definition_en",
        "part_of_speech_status",
        "effective_part_of_speech",
        "positive_definition_evidence_ids",
        "positive_pos_evidence_ids",
        "boundary_context_ids",
        "scope_note",
        "confidence",
        "rationale",
        "risk_flags",
    )
    return not any(row.get(field) not in (None, "", []) for field in fields)


def validate_review_record(
    *,
    review: dict[str, Any],
    case: dict[str, Any],
    context_authority: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    schema = load_review_schema()
    expected = {
        "schema_id": schema["properties"]["schema_id"]["const"],
        "policy_id": schema["properties"]["policy_id"]["const"],
        "case_sha256": case["case_sha256"],
        "source_payload_sha256": case["source_payload_sha256"],
        "term_id": case["term_id"],
        "sense_id": case["sense_id"],
    }
    for field, value in expected.items():
        if review.get(field) != value:
            errors.append(f"immutable field differs: {field}")

    definition_status = review.get("definition_status")
    definition = str(review.get("effective_definition_en", ""))
    if definition_status not in DEFINITION_LABELS:
        errors.append("invalid definition_status")
    elif definition_status == "ACCEPTED" and definition != case["model_definition_en"]:
        errors.append("accepted definition must equal model definition")
    elif definition_status == "CORRECTED" and (
        not definition.strip() or definition == case["model_definition_en"]
    ):
        errors.append("corrected definition must be nonblank and changed")
    elif definition_status == "REJECTED" and definition:
        errors.append("rejected definition must be blank")

    pos_status = review.get("part_of_speech_status")
    pos = str(review.get("effective_part_of_speech", ""))
    if pos_status not in POS_LABELS:
        errors.append("invalid part_of_speech_status")
    elif pos_status == "ACCEPTED" and pos != case["model_part_of_speech"]:
        errors.append("accepted POS must equal model POS")
    elif pos_status == "CORRECTED" and (
        not pos.strip() or pos == case["model_part_of_speech"]
    ):
        errors.append("corrected POS must be nonblank and changed")
    elif pos_status in {"UNCERTAIN", "REJECTED"} and pos:
        errors.append("unresolved POS must be blank")

    if not str(review.get("scope_note", "")).strip():
        errors.append("scope_note is blank")
    if not str(review.get("rationale", "")).strip():
        errors.append("rationale is blank")
    confidence = review.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        errors.append("confidence must be numeric")
    elif not 0 <= float(confidence) <= 1:
        errors.append("confidence must be between 0 and 1")
    errors.extend(validate_explicit_evidence(review, context_authority))
    return errors


def validate_review_file(
    *,
    batch_root: Path,
    review_file: Path,
    dataset_root: Path,
    require_complete: bool = False,
) -> dict[str, Any]:
    _, contexts = load_v3_context_authority(dataset_root)
    cases = {
        str(case["sense_id"]): case
        for case in read_jsonl(batch_root / "sense_review_cases.jsonl")
    }
    rows = [normalize_review_row(row) for row in read_csv(review_file)]
    errors: list[str] = []
    ids = [str(row.get("sense_id", "")) for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("review sense IDs are duplicated")
    if set(ids) != set(cases):
        errors.append("review sense IDs differ from batch cases")
    complete = 0
    for index, row in enumerate(rows, start=1):
        sense_id = str(row.get("sense_id", ""))
        case = cases.get(sense_id)
        if case is None:
            continue
        if _is_blank(row) and not require_complete:
            continue
        row_errors = validate_review_record(
            review=row,
            case=case,
            context_authority=contexts,
        )
        errors.extend(f"row {index} ({sense_id}): {error}" for error in row_errors)
        if not row_errors:
            complete += 1
    return {
        "status": "PASS" if not errors else "FAIL",
        "row_count": len(rows),
        "complete_row_count": complete,
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--review-file", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    report = validate_review_file(
        batch_root=args.batch_root.resolve(),
        review_file=args.review_file.resolve(),
        dataset_root=args.dataset_root.resolve(),
        require_complete=args.require_complete,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
