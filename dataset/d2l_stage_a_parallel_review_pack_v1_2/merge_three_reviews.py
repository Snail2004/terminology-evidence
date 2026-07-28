from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from validate_review import rows, validate

CORE_DECISION_FIELDS = (
    "definition_status",
    "effective_definition_en",
    "part_of_speech_status",
    "effective_part_of_speech",
)
AUDIT_DECISION_FIELDS = CORE_DECISION_FIELDS + ("scope_note",)
MERGED_RECORD_SCHEMA_ID = "D2LCSTMergedThreeReviewRecordV2"
MERGED_SUMMARY_SCHEMA_ID = "D2LCSTMergedThreeReviewSummaryV2"
MERGE_POLICY_ID = "d2l_cst_core_decision_consensus_v1"

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def resolve_decisions(decisions):
    """Resolve semantic agreement while retaining explanatory note variants."""
    core_decisions = [
        {field: decision[field] for field in CORE_DECISION_FIELDS}
        for decision in decisions
    ]
    keys = [canonical(value) for value in core_decisions]
    frequencies = Counter(keys)
    winning_key, winning_count = frequencies.most_common(1)[0]
    winner_index = keys.index(winning_key)
    scope_note_variants = sorted({
        decision["scope_note"] for decision in decisions if decision["scope_note"]
    })
    winning_scope_note_variants = sorted({
        decisions[index]["scope_note"]
        for index, key in enumerate(keys)
        if key == winning_key and decisions[index]["scope_note"]
    })
    if winning_count == 3:
        resolution = "AGREEMENT_3_OF_3"
        effective = dict(core_decisions[winner_index])
    elif winning_count == 2:
        resolution = "MAJORITY_2_OF_3"
        effective = dict(core_decisions[winner_index])
    else:
        resolution = "ADJUDICATION_REQUIRED"
        effective = None
    if effective is not None:
        effective["scope_note"] = (
            winning_scope_note_variants[0] if winning_scope_note_variants else ""
        )
        effective["scope_note_resolution"] = (
            "EXACT_WINNING_SET" if len(winning_scope_note_variants) == 1
            else "NON_BLOCKING_TEXT_VARIANTS"
        )
    return resolution, effective, scope_note_variants, winning_scope_note_variants

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pack_root", type=Path)
    parser.add_argument("review_1", type=Path)
    parser.add_argument("review_2", type=Path)
    parser.add_argument("review_3", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"Output already exists: {args.output_dir}")
    paths = [args.review_1, args.review_2, args.review_3]
    reports = [validate(args.pack_root, path, True) for path in paths]
    if any(report["status"] != "PASS" for report in reports):
        print(json.dumps({"status": "FAIL", "validation_reports": reports}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    reviews = [{row["sense_id"]: row for row in rows(path)} for path in paths]
    sense_ids = sorted(reviews[0])
    merged = []
    counts = Counter()
    for sense_id in sense_ids:
        source = reviews[0][sense_id]
        decisions = [
            {field: review[sense_id].get(field, "") for field in AUDIT_DECISION_FIELDS}
            for review in reviews
        ]
        (
            resolution,
            effective,
            scope_note_variants,
            winning_scope_note_variants,
        ) = resolve_decisions(decisions)
        counts[resolution] += 1
        record = {
            "schema_id": MERGED_RECORD_SCHEMA_ID,
            "merge_policy_id": MERGE_POLICY_ID,
            "term_id": source["term_id"],
            "sense_id": sense_id,
            "source_payload_sha256": source["source_payload_sha256"],
            "case_sha256": source["case_sha256"],
            "reviewer_1_decision": decisions[0],
            "reviewer_2_decision": decisions[1],
            "reviewer_3_decision": decisions[2],
            "scope_note_variants": scope_note_variants,
            "winning_scope_note_variants": winning_scope_note_variants,
            "resolution": resolution,
            "effective_decision": effective,
        }
        record["record_sha256"] = hashlib.sha256(canonical(record).encode("utf-8")).hexdigest()
        merged.append(record)
    args.output_dir.mkdir(parents=True)
    merged_path = args.output_dir / "merged_three_reviews.jsonl"
    merged_path.write_text("".join(canonical(row) + "\n" for row in merged), encoding="utf-8")
    summary = {
        "schema_id": MERGED_SUMMARY_SCHEMA_ID,
        "merge_policy_id": MERGE_POLICY_ID,
        "consensus_fields": list(CORE_DECISION_FIELDS),
        "non_voting_audit_fields": ["scope_note"],
        "status": "PASS",
        "review_file_sha256": {f"reviewer_{index}": digest(path) for index, path in enumerate(paths, 1)},
        "sense_count": len(merged),
        "resolution_counts": dict(sorted(counts.items())),
        "adjudication_required": counts["ADJUDICATION_REQUIRED"],
        "merged_output": str(merged_path),
    }
    (args.output_dir / "review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
