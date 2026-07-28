from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path
from typing import Any

from case_projection import (
    BATCH_POLICY_ID,
    CASE_CSV_FIELDS,
    CONTEXT_CSV_FIELDS,
    REVIEW_CSV_FIELDS,
    blank_review_row,
    build_case,
    case_csv_row,
    flattened_context_rows,
)
from common import (
    file_bindings,
    read_json,
    read_jsonl,
    seal,
    sha256_file,
    sha256_object,
    validate_self_hash,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)
from render import (
    batch_readme,
    casebook,
    review_instructions,
    reviewer_message,
)


SPLIT_ORDER = ("development", "validation", "test")
EXPECTED_SPLITS = {"development": 100, "validation": 25, "test": 25}
MAX_BATCH_SENSES = 10


def _validate_source(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    errors: list[str] = []
    manifest = read_json(source_root / "manifest.json")
    validate_self_hash(manifest, "manifest_sha256", "source manifest", errors)
    if manifest.get("schema_id") != "D2LContextSupportSetValidationReadyV3":
        errors.append("unexpected source schema")
    for filename in ("term_senses.jsonl", "contexts.jsonl"):
        binding = manifest.get("files", {}).get(filename, {})
        if sha256_file(source_root / filename) != binding.get("sha256"):
            errors.append(f"source file hash mismatch: {filename}")

    senses = read_jsonl(source_root / "term_senses.jsonl")
    contexts_list = read_jsonl(source_root / "contexts.jsonl")
    contexts = {row["context_id"]: row for row in contexts_list}
    if len(contexts) != len(contexts_list):
        errors.append("source context IDs are duplicated")
    for sense in senses:
        identity = dict(sense)
        expected = identity.pop("term_sense_sha256", None)
        if expected != sha256_object(identity):
            errors.append(f"term-sense hash mismatch: {sense.get('sense_id')}")
        for field in (
            "primary_context_ids",
            "backup_context_ids",
            "contrastive_context_ids",
        ):
            for context_id in sense.get(field) or []:
                if context_id not in contexts:
                    errors.append(
                        f"missing context {context_id} for {sense.get('sense_id')}"
                    )
        for field in (
            "definition_evidence_context_ids",
            "part_of_speech_evidence_context_ids",
        ):
            available = [
                context_id
                for context_id in sense.get(field) or []
                if context_id in contexts
            ]
            if not available:
                errors.append(
                    f"no available {field} for {sense.get('sense_id')}"
                )
    for context in contexts_list:
        identity = dict(context)
        expected = identity.pop("context_sha256", None)
        if expected != sha256_object(identity):
            errors.append(f"context hash mismatch: {context.get('context_id')}")

    counts = Counter(str(row.get("split")) for row in senses)
    if len(senses) != 150 or dict(counts) != EXPECTED_SPLITS:
        errors.append(f"unexpected source split counts: {dict(counts)}")
    if errors:
        raise ValueError("; ".join(errors[:20]))
    return senses, contexts, manifest


def _chunks(values: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _build_batch(
    batch_root: Path,
    batch_id: str,
    split: str,
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    batch_root.mkdir(parents=True)
    case_rows = [case_csv_row(case) for case in cases]
    context_rows = [
        row for case in cases for row in flattened_context_rows(case)
    ]
    review_rows = [blank_review_row(case) for case in cases]
    readable_casebook = casebook(cases, batch_id)

    write_text(batch_root / "README.md", batch_readme(batch_id, split, len(cases)))
    write_text(batch_root / "REVIEW_INSTRUCTIONS_CSV.md", review_instructions())
    write_text(batch_root / "SENSE_CASEBOOK.md", readable_casebook)
    write_jsonl(batch_root / "sense_review_cases.jsonl", cases)
    write_csv(batch_root / "sense_review_cases.csv", CASE_CSV_FIELDS, case_rows)
    write_csv(
        batch_root / "sense_review_contexts.csv", CONTEXT_CSV_FIELDS, context_rows
    )
    for slot in (1, 2, 3):
        write_csv(batch_root / f"ai_{slot}.csv", REVIEW_CSV_FIELDS, review_rows)
        write_text(
            batch_root / f"MESSAGE_TO_REVIEWER_{slot}.md",
            reviewer_message(slot, len(cases), batch_id),
        )

    manifest = seal(
        {
            "schema_id": "D2LCSTStageAReviewBatchV1",
            "policy_id": BATCH_POLICY_ID,
            "batch_id": batch_id,
            "split": split,
            "sense_count": len(cases),
            "context_row_count": len(context_rows),
            "sense_ids": [case["sense_id"] for case in cases],
            "case_sha256": [case["case_sha256"] for case in cases],
            "missing_optional_evidence_reference_count": sum(
                len(context_ids)
                for case in cases
                for context_ids in (
                    case.get("missing_evidence_context_ids") or {}
                ).values()
            ),
            "approx_input_tokens": math.ceil(len(readable_casebook) / 4),
            "files": file_bindings(batch_root),
        },
        "batch_manifest_sha256",
    )
    write_json(batch_root / "batch_manifest.json", manifest)
    return manifest


def build_release(source_root: Path, output_root: Path) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    senses, contexts, source_manifest = _validate_source(source_root)
    output_root.mkdir(parents=True)
    batch_rows: list[dict[str, Any]] = []
    batch_manifests: list[dict[str, Any]] = []
    source_gap_rows: list[dict[str, Any]] = []

    for split in SPLIT_ORDER:
        split_senses = sorted(
            (sense for sense in senses if sense["split"] == split),
            key=lambda value: (str(value["source_term"]).casefold(), value["sense_id"]),
        )
        for sequence, chunk in enumerate(
            _chunks(split_senses, MAX_BATCH_SENSES), start=1
        ):
            batch_id = f"{split}_{sequence:03d}"
            cases = [build_case(sense, contexts) for sense in chunk]
            source_gap_rows.extend(
                {
                    "sense_id": case["sense_id"],
                    "source_term": case["source_term"],
                    "split": case["split"],
                    "missing_evidence_context_ids": case[
                        "missing_evidence_context_ids"
                    ],
                }
                for case in cases
                if case.get("missing_evidence_context_ids")
            )
            manifest = _build_batch(
                output_root / "batches" / batch_id,
                batch_id,
                split,
                cases,
            )
            batch_manifests.append(manifest)
            batch_rows.append(
                {
                    "batch_id": batch_id,
                    "split": split,
                    "sequence": sequence,
                    "sense_count": len(cases),
                    "context_row_count": manifest["context_row_count"],
                    "approx_input_tokens": manifest["approx_input_tokens"],
                    "first_source_term": cases[0]["source_term"],
                    "last_source_term": cases[-1]["source_term"],
                    "batch_manifest_sha256": manifest["batch_manifest_sha256"],
                }
            )

    write_csv(
        output_root / "batch_index.csv",
        [
            "batch_id",
            "split",
            "sequence",
            "sense_count",
            "context_row_count",
            "approx_input_tokens",
            "first_source_term",
            "last_source_term",
            "batch_manifest_sha256",
        ],
        batch_rows,
    )
    release_readme = """# D2L Stage A review release

This release contains 16 split-safe review batches for all 150 term-senses.
Open `batch_index.csv`, select one batch, then send one reviewer the four shared
source files and only that reviewer's blank CSV.
"""
    write_text(output_root / "README.md", release_readme)
    source_gaps = seal(
        {
            "schema_id": "D2LCSTStageASourceGapReportV1",
            "policy_id": BATCH_POLICY_ID,
            "status": "SOURCE_GAPS_RETAINED_WITHOUT_MUTATING_V3",
            "sense_count": len(source_gap_rows),
            "missing_reference_count": sum(
                len(context_ids)
                for row in source_gap_rows
                for context_ids in row["missing_evidence_context_ids"].values()
            ),
            "rows": source_gap_rows,
        },
        "source_gaps_sha256",
    )
    write_json(output_root / "source_gaps.json", source_gaps)
    split_counts = Counter(row["split"] for row in senses)
    manifest = seal(
        {
            "schema_id": "D2LCSTStageAReviewBatchReleaseV1",
            "policy_id": BATCH_POLICY_ID,
            "source": {
                "schema_id": source_manifest["schema_id"],
                "dataset_version": source_manifest["dataset_version"],
                "manifest_sha256": source_manifest["manifest_sha256"],
                "manifest_file_sha256": sha256_file(source_root / "manifest.json"),
            },
            "sense_count": len(senses),
            "split_counts": dict(split_counts),
            "batch_count": len(batch_manifests),
            "reviewer_slots": 3,
            "expected_review_outputs": len(batch_manifests) * 3,
            "max_senses_per_batch": MAX_BATCH_SENSES,
            "missing_optional_evidence_reference_count": sum(
                manifest["missing_optional_evidence_reference_count"]
                for manifest in batch_manifests
            ),
            "source_gaps": {
                "ref": "source_gaps.json",
                "source_gaps_sha256": source_gaps["source_gaps_sha256"],
            },
            "batch_manifest_sha256": {
                manifest["batch_id"]: manifest["batch_manifest_sha256"]
                for manifest in batch_manifests
            },
            "files": file_bindings(output_root),
        },
        "manifest_sha256",
    )
    write_json(output_root / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_release(args.source_root.resolve(), args.output_root.resolve())
    print(
        f"PASS: {manifest['sense_count']} senses, "
        f"{manifest['batch_count']} batches, "
        f"{manifest['expected_review_outputs']} review outputs"
    )


if __name__ == "__main__":
    main()
