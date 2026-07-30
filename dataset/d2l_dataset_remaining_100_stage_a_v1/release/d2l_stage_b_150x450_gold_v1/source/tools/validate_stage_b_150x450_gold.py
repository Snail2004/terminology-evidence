from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_file_inventory,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_record,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_stage_b_150x450_gold import (
    ARTIFACT_NAME,
    POLICY_ID,
    RELEASE_STATUS,
    _load_sources,
    _manifest_self_hash,
    _project_rows,
)


def _validate_checksums(root: Path, errors: list[str]) -> None:
    expected: dict[str, str] = {}
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(str(exc))
        return
    for line in lines:
        if " *" not in line:
            errors.append("malformed checksum row")
            continue
        digest, relative = line.split(" *", 1)
        if relative in expected:
            errors.append(f"duplicate checksum path: {relative}")
        expected[relative] = digest
    actual = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256", "manifest.json"}
        ).items()
    }
    if expected != actual:
        errors.append("checksum inventory does not match artifact files")


def _scan_guards(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == "provider_call_count" and child != 0:
                errors.append(f"nonzero provider call count: {child_path}")
            if key == "final_glossary_decision" and child is not None:
                errors.append(f"non-null final glossary decision: {child_path}")
            if key == "final_glossary_decision_count" and child != 0:
                errors.append(f"nonzero final glossary count: {child_path}")
            _scan_guards(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_guards(child, f"{path}[{index}]", errors)


def validate_artifact(
    root: Path,
    *,
    stage_a_complete_root: Path,
    baseline_gold_root: Path,
    remaining_gold_root: Path,
) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    try:
        sources = _load_sources(
            stage_a_complete_root=stage_a_complete_root.resolve(),
            baseline_gold_root=baseline_gold_root.resolve(),
            remaining_gold_root=remaining_gold_root.resolve(),
        )
        manifest = strict_json_object(root / "manifest.json")
        if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
            errors.append("manifest self-hash mismatch")
        if (
            manifest.get("artifact_name") != ARTIFACT_NAME
            or manifest.get("policy_id") != POLICY_ID
            or manifest.get("release_status") != RELEASE_STATUS
            or manifest.get("stage_a_complete_manifest_sha256")
            != sources["stage_a_manifest"]["manifest_sha256"]
            or manifest.get("baseline_stage_b_gold_manifest_sha256")
            != sources["baseline_manifest"]["manifest_sha256"]
            or manifest.get("remaining_stage_b_gold_manifest_sha256")
            != sources["remaining_manifest"]["manifest_sha256"]
        ):
            errors.append("manifest identity/lineage mismatch")
        if manifest.get("files") != build_file_inventory(root, {"manifest.json"}):
            errors.append("manifest file inventory mismatch")
        _validate_checksums(root, errors)

        expected_rows = _project_rows(sources)
        rows = strict_jsonl(root / "stage_b_gold_450.jsonl")
        if rows != expected_rows:
            errors.append("combined Stage B gold projection mismatch")
        if len(rows) != 450 or any(
            not verify_record(row, "stage_b_150x450_gold_sha256") for row in rows
        ):
            errors.append("combined Stage B gold count/self-hash mismatch")
        if (
            len({row["candidate_id"] for row in rows}) != 450
            or len({row["source_slot_sense_id"] for row in rows}) != 150
            or len({row["effective_sense_id"] for row in rows}) != 155
        ):
            errors.append("combined Dataset population mismatch")

        baseline_partition = root / "partitions" / "baseline_stage_b_gold_150.jsonl"
        remaining_partition = root / "partitions" / "remaining_stage_b_gold_300.jsonl"
        if sha256_file(baseline_partition) != sha256_file(
            baseline_gold_root / "stage_b_gold_150.jsonl"
        ):
            errors.append("baseline partition bytes changed")
        if sha256_file(remaining_partition) != sha256_file(
            remaining_gold_root / "stage_b_gold_300.jsonl"
        ):
            errors.append("remaining partition bytes changed")
        if sha256_file(root / "stage_a_source_slot_index_150.jsonl") != sha256_file(
            stage_a_complete_root / "stage_a_source_slot_index_150.jsonl"
        ):
            errors.append("Stage A source-slot index bytes changed")

        summary = strict_json_object(root / "stage_b_gold_summary.json")
        label_counts = dict(sorted(Counter(row["final_gold_label"] for row in rows).items()))
        resolution_counts = dict(
            sorted(Counter(row["review_resolution"] for row in rows).items())
        )
        if (
            summary.get("release_status") != RELEASE_STATUS
            or summary.get("source_slot_count") != 150
            or summary.get("effective_sense_count") != 155
            or summary.get("candidate_count") != 450
            or summary.get("final_gold_label_count") != 450
            or summary.get("final_gold_label_counts") != label_counts
            or summary.get("resolution_counts") != resolution_counts
            or summary.get("adjudication_count") != 74
            or summary.get("c_e_evaluation_status") != "READY_NOT_RUN"
            or summary.get("global_validator_status") != "NOT_RUN"
        ):
            errors.append("combined Stage B summary mismatch")
        if (
            manifest.get("source_slot_count") != 150
            or manifest.get("effective_sense_count") != 155
            or manifest.get("candidate_count") != 450
            or manifest.get("final_gold_label_count") != 450
            or manifest.get("adjudication_count") != 74
        ):
            errors.append("combined Stage B manifest counts mismatch")
        for name, value in (
            ("manifest", manifest),
            ("rows", rows),
            ("summary", summary),
        ):
            _scan_guards(value, name, errors)
    except (KeyError, OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--stage-a-complete-root", required=True, type=Path)
    parser.add_argument("--baseline-gold-root", required=True, type=Path)
    parser.add_argument("--remaining-gold-root", required=True, type=Path)
    args = parser.parse_args()
    errors = validate_artifact(
        args.artifact_root,
        stage_a_complete_root=args.stage_a_complete_root,
        baseline_gold_root=args.baseline_gold_root,
        remaining_gold_root=args.remaining_gold_root,
    )
    print(
        json.dumps(
            {"status": "PASS" if not errors else "FAIL", "errors": errors},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
