from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from common import (
    file_bindings,
    read_json,
    read_jsonl,
    seal,
    sha256_file,
    write_json,
    write_jsonl,
)
from review_workflow import merge_reviews, validate_review


REVIEW_SLOTS = ("ai_1.csv", "ai_2.csv", "ai_3.csv")
INTAKE_SCHEMA_ID = "D2LCSTStageAReviewIntakeV1"
INTAKE_POLICY_ID = "d2l_cst_stage_a_review_intake_v1"


def _batch_index(release_root: Path) -> list[dict[str, str]]:
    with (release_root / "batch_index.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def _expected_paths(
    release_root: Path, intake_root: Path
) -> list[tuple[dict[str, str], str, Path]]:
    return [
        (batch, slot, intake_root / batch["batch_id"] / slot)
        for batch in _batch_index(release_root)
        for slot in REVIEW_SLOTS
    ]


def inventory_reviews(release_root: Path, intake_root: Path) -> dict[str, Any]:
    release_root = release_root.resolve(strict=True)
    intake_root = intake_root.resolve(strict=False)
    expected = _expected_paths(release_root, intake_root)
    expected_keys = {
        path.relative_to(intake_root).as_posix().casefold()
        for _, _, path in expected
    }
    actual_csv = sorted(intake_root.rglob("*.csv")) if intake_root.is_dir() else []
    unexpected = [
        path.relative_to(intake_root).as_posix()
        for path in actual_csv
        if path.relative_to(intake_root).as_posix().casefold() not in expected_keys
    ]

    errors: list[str] = []
    records: list[dict[str, Any]] = []
    missing = 0
    valid = 0
    batch_paths: dict[str, list[Path]] = {}
    for batch, slot, path in expected:
        relative = path.relative_to(intake_root).as_posix()
        if not path.is_file():
            missing += 1
            records.append(
                {
                    "batch_id": batch["batch_id"],
                    "split": batch["split"],
                    "review_slot": slot.removesuffix(".csv"),
                    "review_ref": relative,
                    "status": "MISSING",
                    "review_sha256": None,
                    "errors": [],
                }
            )
            continue
        report = validate_review(
            release_root / "batches" / batch["batch_id"], path, True
        )
        status = report["status"]
        if status == "PASS":
            valid += 1
            batch_paths.setdefault(batch["batch_id"], []).append(path)
        else:
            errors.append(f"Invalid completed review: {relative}")
        records.append(
            {
                "batch_id": batch["batch_id"],
                "split": batch["split"],
                "review_slot": slot.removesuffix(".csv"),
                "review_ref": relative,
                "status": status,
                "review_sha256": sha256_file(path),
                "errors": report["errors"],
            }
        )

    duplicate_physical_batches: list[str] = []
    for batch_id, paths in sorted(batch_paths.items()):
        if len(paths) != 3:
            continue
        resolved = [path.resolve(strict=True) for path in paths]
        if any(
            left.samefile(right)
            for index, left in enumerate(resolved)
            for right in resolved[index + 1 :]
        ):
            duplicate_physical_batches.append(batch_id)
            errors.append(f"Reviewer files are not physically distinct: {batch_id}")

    if unexpected:
        errors.append(f"Unexpected CSV files: {len(unexpected)}")
    status = "PASS" if not errors and missing == 0 else "FAIL"
    return {
        "schema_id": "D2LCSTStageAReviewInventoryV1",
        "policy_id": INTAKE_POLICY_ID,
        "status": status,
        "batch_count": len(_batch_index(release_root)),
        "expected_review_file_count": len(expected),
        "present_review_file_count": len(expected) - missing,
        "valid_review_file_count": valid,
        "missing_review_file_count": missing,
        "unexpected_review_files": unexpected,
        "duplicate_physical_batches": duplicate_physical_batches,
        "error_count": len(errors),
        "errors": errors,
        "records": records,
    }


def finalize_reviews(
    release_root: Path,
    intake_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    release_root = release_root.resolve(strict=True)
    intake_root = intake_root.resolve(strict=True)
    output_root = output_root.resolve(strict=False)
    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    inventory = inventory_reviews(release_root, intake_root)
    if inventory["status"] != "PASS":
        raise ValueError(json.dumps(inventory, ensure_ascii=False))

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=output_root.parent)
    )
    staging_root = temporary_root / "artifact"
    staging_root.mkdir()
    try:
        merged_rows: list[dict[str, Any]] = []
        batch_summaries: list[dict[str, Any]] = []
        split_counts: Counter[str] = Counter()
        for batch in _batch_index(release_root):
            batch_id = batch["batch_id"]
            review_paths = [intake_root / batch_id / slot for slot in REVIEW_SLOTS]
            batch_output = staging_root / "batches" / batch_id
            summary = merge_reviews(
                release_root / "batches" / batch_id,
                review_paths,
                batch_output,
            )
            rows = read_jsonl(batch_output / "merged_three_reviews.jsonl")
            for row in rows:
                row["batch_id"] = batch_id
                row["split"] = batch["split"]
            merged_rows.extend(rows)
            split_counts[batch["split"]] += len(rows)
            batch_summaries.append(
                {
                    "batch_id": batch_id,
                    "split": batch["split"],
                    "sense_count": len(rows),
                    "summary_ref": f"batches/{batch_id}/review_summary.json",
                    "summary_sha256": sha256_file(
                        batch_output / "review_summary.json"
                    ),
                    "resolution_counts": summary["resolution_counts"],
                }
            )

        sense_ids = [row["sense_id"] for row in merged_rows]
        if len(sense_ids) != 150 or len(set(sense_ids)) != 150:
            raise ValueError("Final review merge must contain 150 unique senses")
        merged_rows.sort(key=lambda row: (row["split"], row["sense_id"]))
        adjudication = [
            row for row in merged_rows if row["resolution"] == "ADJUDICATION_REQUIRED"
        ]
        resolution_counts = Counter(row["resolution"] for row in merged_rows)
        write_jsonl(staging_root / "merged_all_batches.jsonl", merged_rows)
        write_jsonl(staging_root / "adjudication_queue.jsonl", adjudication)
        write_jsonl(
            staging_root / "review_file_inventory.jsonl", inventory["records"]
        )
        release_manifest = read_json(release_root / "manifest.json")
        global_summary = {
            "schema_id": "D2LCSTStageAReviewFinalizationSummaryV1",
            "policy_id": INTAKE_POLICY_ID,
            "status": "PASS",
            "source_release_manifest_sha256": release_manifest["manifest_sha256"],
            "source_release_manifest_file_sha256": sha256_file(
                release_root / "manifest.json"
            ),
            "batch_count": len(batch_summaries),
            "review_file_count": 48,
            "sense_count": len(merged_rows),
            "split_counts": dict(sorted(split_counts.items())),
            "resolution_counts": dict(sorted(resolution_counts.items())),
            "adjudication_required": len(adjudication),
            "batch_summaries": batch_summaries,
        }
        write_json(staging_root / "review_intake_summary.json", global_summary)
        manifest = seal(
            {
                "schema_id": INTAKE_SCHEMA_ID,
                "schema_version": "1.0.0",
                "policy_id": INTAKE_POLICY_ID,
                "status": "PASS",
                "source_release_manifest_sha256": release_manifest[
                    "manifest_sha256"
                ],
                "batch_count": len(batch_summaries),
                "review_file_count": 48,
                "sense_count": len(merged_rows),
                "files": file_bindings(staging_root),
            },
            "manifest_sha256",
        )
        write_json(staging_root / "manifest.json", manifest)
        os.replace(staging_root, output_root)
        return global_summary
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "finalize"):
        child = subparsers.add_parser(command)
        child.add_argument("--release-root", type=Path, required=True)
        child.add_argument("--intake-root", type=Path, required=True)
        if command == "finalize":
            child.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "status":
        result = inventory_reviews(args.release_root, args.intake_root)
    else:
        result = finalize_reviews(
            args.release_root, args.intake_root, args.output_root
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
