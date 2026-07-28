from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from validate_review import rows, validate

DECISION_FIELDS = (
    "definition_status", "effective_definition_en", "part_of_speech_status",
    "effective_part_of_speech", "scope_note",
)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

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
            {field: review[sense_id].get(field, "") for field in DECISION_FIELDS}
            for review in reviews
        ]
        keys = [canonical(value) for value in decisions]
        frequencies = Counter(keys)
        winning_key, winning_count = frequencies.most_common(1)[0]
        if winning_count == 3:
            resolution = "AGREEMENT_3_OF_3"
            effective = decisions[keys.index(winning_key)]
        elif winning_count == 2:
            resolution = "MAJORITY_2_OF_3"
            effective = decisions[keys.index(winning_key)]
        else:
            resolution = "ADJUDICATION_REQUIRED"
            effective = None
        counts[resolution] += 1
        record = {
            "schema_id": "D2LCSTMergedThreeReviewRecordV1",
            "term_id": source["term_id"],
            "sense_id": sense_id,
            "source_payload_sha256": source["source_payload_sha256"],
            "case_sha256": source["case_sha256"],
            "reviewer_1_decision": decisions[0],
            "reviewer_2_decision": decisions[1],
            "reviewer_3_decision": decisions[2],
            "resolution": resolution,
            "effective_decision": effective,
        }
        record["record_sha256"] = hashlib.sha256(canonical(record).encode("utf-8")).hexdigest()
        merged.append(record)
    args.output_dir.mkdir(parents=True)
    merged_path = args.output_dir / "merged_three_reviews.jsonl"
    merged_path.write_text("".join(canonical(row) + "\n" for row in merged), encoding="utf-8")
    summary = {
        "schema_id": "D2LCSTMergedThreeReviewSummaryV1",
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
