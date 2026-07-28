from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from case_projection import REVIEW_POLICY_ID, REVIEW_SCHEMA_ID
from common import canonical_json, read_csv, read_jsonl, seal, sha256_file, write_json, write_jsonl


DEFINITION_LABELS = {"ACCEPTED", "CORRECTED", "REJECTED"}
POS_LABELS = {"ACCEPTED", "CORRECTED", "UNCERTAIN", "REJECTED"}
CORE_FIELDS = (
    "definition_status",
    "effective_definition_en",
    "part_of_speech_status",
    "effective_part_of_speech",
)


def _list_field(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(";") if item.strip()]


def normalized_review_rows(path: Path) -> list[dict[str, Any]]:
    values = []
    for row in read_csv(path):
        values.append(
            {
                **row,
                "evidence_context_ids": _list_field(row.get("evidence_context_ids", "")),
                "risk_flags": _list_field(row.get("risk_flags", "")),
            }
        )
    return values


def validate_review(
    batch_root: Path,
    output: Path,
    require_complete: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    cases = {
        row["sense_id"]: row
        for row in read_jsonl(batch_root / "sense_review_cases.jsonl")
    }
    values = normalized_review_rows(output)
    ids = [str(row.get("sense_id", "")) for row in values]
    if len(ids) != len(set(ids)):
        errors.append("output sense IDs are duplicated")
    if set(ids) != set(cases):
        errors.append("output sense IDs differ from review cases")
    complete = 0
    for index, row in enumerate(values, start=1):
        sense_id = str(row.get("sense_id", ""))
        case = cases.get(sense_id)
        if case is None:
            continue
        prefix = f"row {index} ({sense_id})"
        expected = {
            "schema_id": REVIEW_SCHEMA_ID,
            "policy_id": REVIEW_POLICY_ID,
            "term_id": case["term_id"],
            "sense_id": case["sense_id"],
            "source_payload_sha256": case["source_payload_sha256"],
            "case_sha256": case["case_sha256"],
        }
        for field, value in expected.items():
            if row.get(field) != value:
                errors.append(f"{prefix}: immutable field differs: {field}")
        populated = any(
            row.get(field) not in ("", [], None)
            for field in (
                "definition_status",
                "effective_definition_en",
                "part_of_speech_status",
                "effective_part_of_speech",
                "scope_note",
                "evidence_context_ids",
                "confidence",
                "rationale",
                "risk_flags",
            )
        )
        if not populated and not require_complete:
            continue
        definition_status = row.get("definition_status")
        pos_status = row.get("part_of_speech_status")
        definition = str(row.get("effective_definition_en", ""))
        pos = str(row.get("effective_part_of_speech", ""))
        if definition_status not in DEFINITION_LABELS:
            errors.append(f"{prefix}: invalid definition_status")
        if pos_status not in POS_LABELS:
            errors.append(f"{prefix}: invalid part_of_speech_status")
        if definition_status == "ACCEPTED" and definition != case["model_definition_en"]:
            errors.append(f"{prefix}: accepted definition must equal model definition")
        if definition_status == "CORRECTED" and not definition.strip():
            errors.append(f"{prefix}: corrected definition is blank")
        if definition_status == "REJECTED" and definition:
            errors.append(f"{prefix}: rejected definition must be blank")
        if pos_status == "ACCEPTED" and pos != case["model_part_of_speech"]:
            errors.append(f"{prefix}: accepted POS must equal model POS")
        if pos_status == "CORRECTED" and not pos.strip():
            errors.append(f"{prefix}: corrected POS is blank")
        if pos_status in {"UNCERTAIN", "REJECTED"} and pos:
            errors.append(f"{prefix}: unresolved POS must be blank")
        if not str(row.get("rationale", "")).strip():
            errors.append(f"{prefix}: rationale is blank")
        try:
            confidence = float(row.get("confidence"))
            if not 0 <= confidence <= 1:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{prefix}: confidence must be between 0 and 1")
        evidence = row.get("evidence_context_ids")
        allowed = {
            context["context_id"]
            for group in case["evidence_contexts"].values()
            for context in group
        }
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix}: evidence_context_ids must be nonempty")
        elif any(value not in allowed for value in evidence):
            errors.append(f"{prefix}: evidence context is outside the case")
        elif len(evidence) != len(set(evidence)):
            errors.append(f"{prefix}: evidence_context_ids contains duplicates")
        if not any(error.startswith(prefix) for error in errors):
            complete += 1
    return {
        "status": "PASS" if not errors else "FAIL",
        "row_count": len(values),
        "complete_row_count": complete,
        "error_count": len(errors),
        "errors": errors,
    }


def resolve_decisions(decisions: list[dict[str, str]]) -> tuple[str, dict[str, str] | None]:
    keys = [canonical_json({field: value[field] for field in CORE_FIELDS}) for value in decisions]
    winning_key, count = Counter(keys).most_common(1)[0]
    if count == 1:
        return "ADJUDICATION_REQUIRED", None
    winner = decisions[keys.index(winning_key)]
    effective = {field: winner[field] for field in CORE_FIELDS}
    winning_notes = sorted(
        {
            decision.get("scope_note", "")
            for decision, key in zip(decisions, keys)
            if key == winning_key and decision.get("scope_note", "")
        }
    )
    effective["scope_note"] = winning_notes[0] if winning_notes else ""
    return ("AGREEMENT_3_OF_3" if count == 3 else "MAJORITY_2_OF_3"), effective


def merge_reviews(
    batch_root: Path,
    review_paths: list[Path],
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    reports = [validate_review(batch_root, path, True) for path in review_paths]
    if any(report["status"] != "PASS" for report in reports):
        raise ValueError(json.dumps(reports, ensure_ascii=False))
    reviews = [
        {row["sense_id"]: row for row in normalized_review_rows(path)}
        for path in review_paths
    ]
    merged = []
    counts: Counter[str] = Counter()
    for sense_id in sorted(reviews[0]):
        source = reviews[0][sense_id]
        decisions = [
            {
                **{field: review[sense_id].get(field, "") for field in CORE_FIELDS},
                "scope_note": review[sense_id].get("scope_note", ""),
            }
            for review in reviews
        ]
        resolution, effective = resolve_decisions(decisions)
        counts[resolution] += 1
        merged.append(
            seal(
                {
                    "schema_id": "D2LCSTMergedThreeReviewRecordV2",
                    "merge_policy_id": "d2l_cst_core_decision_consensus_v1",
                    "term_id": source["term_id"],
                    "sense_id": sense_id,
                    "source_payload_sha256": source["source_payload_sha256"],
                    "case_sha256": source["case_sha256"],
                    "reviewer_decisions": decisions,
                    "resolution": resolution,
                    "effective_decision": effective,
                },
                "record_sha256",
            )
        )
    output_dir.mkdir(parents=True)
    write_jsonl(output_dir / "merged_three_reviews.jsonl", merged)
    summary = {
        "schema_id": "D2LCSTMergedThreeReviewSummaryV2",
        "merge_policy_id": "d2l_cst_core_decision_consensus_v1",
        "status": "PASS",
        "review_file_sha256": {
            f"reviewer_{index}": sha256_file(path)
            for index, path in enumerate(review_paths, start=1)
        },
        "sense_count": len(merged),
        "resolution_counts": dict(sorted(counts.items())),
        "adjudication_required": counts["ADJUDICATION_REQUIRED"],
    }
    write_json(output_dir / "review_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--batch-root", type=Path, required=True)
    validate_parser.add_argument("--review-file", type=Path, required=True)
    validate_parser.add_argument("--require-complete", action="store_true")
    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("--batch-root", type=Path, required=True)
    merge_parser.add_argument("--review-1", type=Path, required=True)
    merge_parser.add_argument("--review-2", type=Path, required=True)
    merge_parser.add_argument("--review-3", type=Path, required=True)
    merge_parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        result = validate_review(
            args.batch_root.resolve(),
            args.review_file.resolve(),
            args.require_complete,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["status"] == "PASS" else 1)
    summary = merge_reviews(
        args.batch_root.resolve(),
        [args.review_1.resolve(), args.review_2.resolve(), args.review_3.resolve()],
        args.output_dir.resolve(),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
