from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from build_batches import EXPECTED_SPLITS, MAX_BATCH_SENSES, _validate_source
from case_projection import blank_review_row, build_case
from common import (
    read_csv,
    read_json,
    read_jsonl,
    sha256_file,
    sha256_object,
    validate_file_bindings,
    validate_self_hash,
)


def validate_release(source_root: Path, release_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        senses, contexts, source_manifest = _validate_source(source_root)
    except (OSError, ValueError) as error:
        return {"status": "FAIL", "error_count": 1, "errors": [str(error)]}

    manifest = read_json(release_root / "manifest.json")
    validate_self_hash(manifest, "manifest_sha256", "release manifest", errors)
    validate_file_bindings(release_root, manifest.get("files", {}), "release", errors)
    if manifest.get("source", {}).get("manifest_sha256") != source_manifest.get(
        "manifest_sha256"
    ):
        errors.append("release source semantic hash mismatch")
    if manifest.get("source", {}).get("manifest_file_sha256") != sha256_file(
        source_root / "manifest.json"
    ):
        errors.append("release source physical hash mismatch")

    source_senses = {sense["sense_id"]: sense for sense in senses}
    index_rows = read_csv(release_root / "batch_index.csv")
    batch_ids = [row.get("batch_id", "") for row in index_rows]
    if len(batch_ids) != 16 or len(batch_ids) != len(set(batch_ids)):
        errors.append("batch index must contain 16 unique batch IDs")

    seen_senses: list[str] = []
    observed_splits: Counter[str] = Counter()
    observed_source_gaps: list[dict[str, Any]] = []
    for index_row in index_rows:
        batch_id = index_row["batch_id"]
        batch_root = release_root / "batches" / batch_id
        batch_manifest = read_json(batch_root / "batch_manifest.json")
        validate_self_hash(
            batch_manifest,
            "batch_manifest_sha256",
            f"batch {batch_id}",
            errors,
        )
        validate_file_bindings(
            batch_root,
            batch_manifest.get("files", {}),
            f"batch {batch_id}",
            errors,
        )
        if batch_manifest.get("batch_manifest_sha256") != index_row.get(
            "batch_manifest_sha256"
        ):
            errors.append(f"batch index hash mismatch: {batch_id}")
        cases = read_jsonl(batch_root / "sense_review_cases.jsonl")
        if not 1 <= len(cases) <= MAX_BATCH_SENSES:
            errors.append(f"invalid batch size: {batch_id}")
        split = batch_manifest.get("split")
        if any(case.get("split") != split for case in cases):
            errors.append(f"mixed split in batch: {batch_id}")

        case_ids = [case.get("sense_id", "") for case in cases]
        if case_ids != batch_manifest.get("sense_ids"):
            errors.append(f"case order differs from batch manifest: {batch_id}")
        if len(case_ids) != len(set(case_ids)):
            errors.append(f"duplicate case in batch: {batch_id}")
        for case in cases:
            identity = dict(case)
            expected_hash = identity.pop("case_sha256", None)
            if expected_hash != sha256_object(identity):
                errors.append(f"case hash mismatch: {case.get('sense_id')}")
                continue
            source_sense = source_senses.get(case["sense_id"])
            if source_sense is None:
                errors.append(f"unknown source sense: {case['sense_id']}")
                continue
            expected_case = build_case(source_sense, contexts)
            if case != expected_case:
                errors.append(f"case differs from source projection: {case['sense_id']}")
            if case.get("missing_evidence_context_ids"):
                observed_source_gaps.append(
                    {
                        "sense_id": case["sense_id"],
                        "source_term": case["source_term"],
                        "split": case["split"],
                        "missing_evidence_context_ids": case[
                            "missing_evidence_context_ids"
                        ],
                    }
                )
            seen_senses.append(case["sense_id"])
            observed_splits[case["split"]] += 1

        csv_case_ids = [
            row.get("sense_id", "")
            for row in read_csv(batch_root / "sense_review_cases.csv")
        ]
        if csv_case_ids != case_ids:
            errors.append(f"case CSV differs from JSONL: {batch_id}")
        allowed_context_ids = {
            context["context_id"]
            for case in cases
            for group in case["evidence_contexts"].values()
            for context in group
        }
        csv_context_ids = {
            row.get("context_id", "")
            for row in read_csv(batch_root / "sense_review_contexts.csv")
        }
        if csv_context_ids != allowed_context_ids:
            errors.append(f"context CSV closure mismatch: {batch_id}")
        expected_rows = [blank_review_row(case) for case in cases]
        for slot in (1, 2, 3):
            if read_csv(batch_root / f"ai_{slot}.csv") != [
                {field: str(value) for field, value in row.items()}
                for row in expected_rows
            ]:
                errors.append(f"review template differs: {batch_id}/ai_{slot}.csv")

    if set(seen_senses) != set(source_senses) or len(seen_senses) != len(
        source_senses
    ):
        errors.append("release does not cover every source sense exactly once")
    if dict(observed_splits) != EXPECTED_SPLITS:
        errors.append(f"release split counts differ: {dict(observed_splits)}")
    if manifest.get("sense_count") != 150 or manifest.get("batch_count") != 16:
        errors.append("release summary counts differ")
    source_gaps = read_json(release_root / "source_gaps.json")
    validate_self_hash(
        source_gaps, "source_gaps_sha256", "source gaps", errors
    )
    if source_gaps.get("rows") != observed_source_gaps:
        errors.append("source gap report differs from projected cases")
    if source_gaps.get("missing_reference_count") != manifest.get(
        "missing_optional_evidence_reference_count"
    ):
        errors.append("source gap count differs from release manifest")
    if manifest.get("source_gaps", {}).get(
        "source_gaps_sha256"
    ) != source_gaps.get("source_gaps_sha256"):
        errors.append("source gap semantic hash differs from release manifest")
    return {
        "status": "PASS" if not errors else "FAIL",
        "sense_count": len(seen_senses),
        "batch_count": len(index_rows),
        "split_counts": dict(observed_splits),
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--release-root", type=Path, required=True)
    args = parser.parse_args()
    result = validate_release(args.source_root.resolve(), args.release_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
