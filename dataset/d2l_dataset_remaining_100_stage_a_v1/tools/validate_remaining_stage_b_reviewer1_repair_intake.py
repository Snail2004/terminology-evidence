from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_file_inventory,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_record,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_review_preflight import (
    _manifest_self_hash,
    _validate_source_artifact,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_reviewer1_repair_intake import (
    ARTIFACT_NAME,
    POLICY_ID,
    STATUS,
    _build_pairs,
    _validate_parent,
    _validate_repair_response,
    _validated_reviews,
)


def _validate_checksums(root: Path, errors: list[str]) -> None:
    expected: dict[str, str] = {}
    try:
        rows = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(str(exc))
        return
    for row in rows:
        if " *" not in row:
            errors.append("malformed checksum row")
            continue
        digest, relative = row.split(" *", 1)
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
            if key == "final_gold_label" and child is not None:
                errors.append(f"non-null final gold label: {child_path}")
            if key == "final_gold_label_count" and child != 0:
                errors.append(f"nonzero final gold count: {child_path}")
            if key == "final_glossary_decision" and child is not None:
                errors.append(f"non-null final glossary decision: {child_path}")
            _scan_guards(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_guards(child, f"{path}[{index}]", errors)


def _validate_single_field_application(
    parent_root: Path,
    repaired_path: Path,
    candidate_id: str,
    allowed_scope: str,
    errors: list[str],
) -> None:
    original = strict_json_object(parent_root / "raw_reviews" / "reviewer_1.json")
    repaired = strict_json_object(repaired_path)
    if set(original) != set(repaired):
        errors.append("repaired reviewer top-level keys changed")
        return
    for key, value in original.items():
        if key != "cases" and repaired.get(key) != value:
            errors.append(f"repaired reviewer immutable top-level changed: {key}")
    source_cases = original.get("cases")
    result_cases = repaired.get("cases")
    if not isinstance(source_cases, list) or not isinstance(result_cases, list):
        errors.append("repaired reviewer cases are invalid")
        return
    changed = 0
    for source_case, result_case in zip(source_cases, result_cases):
        source_id = source_case.get("source_payload", {}).get("candidate_id")
        if source_id != candidate_id:
            if result_case != source_case:
                errors.append(f"non-target reviewer case changed: {source_id}")
            continue
        expected = dict(source_case)
        expected_review = dict(source_case["review"])
        expected_review["allowed_scope"] = allowed_scope
        expected["review"] = expected_review
        if result_case != expected:
            errors.append("target reviewer case changed beyond allowed_scope")
        changed += 1
    if changed != 1:
        errors.append("repair candidate did not resolve exactly once")


def validate_artifact(
    root: Path,
    *,
    parent_artifact_root: Path,
    source_artifact_root: Path,
) -> list[str]:
    root = root.resolve()
    parent_artifact_root = parent_artifact_root.resolve()
    source_artifact_root = source_artifact_root.resolve()
    errors: list[str] = []
    try:
        parent_manifest = _validate_parent(parent_artifact_root)
        _validate_source_artifact(source_artifact_root)
        manifest = strict_json_object(root / "manifest.json")
        if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
            errors.append("manifest self-hash mismatch")
        if (
            manifest.get("artifact_name") != ARTIFACT_NAME
            or manifest.get("policy_id") != POLICY_ID
            or manifest.get("status") != STATUS
            or manifest.get("parent_manifest_sha256")
            != parent_manifest.get("manifest_sha256")
        ):
            errors.append("manifest identity/status/parent mismatch")
        expected_files = manifest.get("files")
        actual_files = build_file_inventory(root, {"manifest.json"})
        if not isinstance(expected_files, Mapping) or expected_files != actual_files:
            errors.append("manifest file inventory mismatch")
        _validate_checksums(root, errors)

        repair = _validate_repair_response(
            parent_artifact_root / "reviewer_1_repair_input.json",
            root / "raw_repair" / "reviewer_1_repair.json",
        )
        repair_case = repair["cases"][0]
        candidate_id = str(repair_case["candidate_id"])
        allowed_scope = str(repair_case["repair"]["allowed_scope"]).strip()
        if manifest.get("repair_response_sha256") != sha256_file(
            root / "raw_repair" / "reviewer_1_repair.json"
        ):
            errors.append("repair response hash mismatch")
        if manifest.get("repaired_candidate_id") != candidate_id:
            errors.append("repaired candidate binding mismatch")

        repaired_1 = root / "repaired_reviews" / "reviewer_1.json"
        reviewer_2 = root / "repaired_reviews" / "reviewer_2.json"
        _validate_single_field_application(
            parent_artifact_root,
            repaired_1,
            candidate_id,
            allowed_scope,
            errors,
        )
        validated = _validated_reviews(source_artifact_root, repaired_1, reviewer_2)
        analysis = _build_pairs(validated)
        pairs = strict_jsonl(root / "review_pairs_300.jsonl")
        if pairs != analysis["pairs"]:
            errors.append("review pair projection mismatch")
        if len(pairs) != 300 or any(
            not verify_record(row, "review_pair_sha256") for row in pairs
        ):
            errors.append("review pair count/self-hash mismatch")
        if (
            analysis["agreement_count"] != 245
            or analysis["disagreement_count"] != 55
        ):
            errors.append("agreement counts changed")

        report = strict_json_object(root / "agreement_report.json")
        if (
            report.get("status") != STATUS
            or report.get("agreement_count") != 245
            or report.get("disagreement_count") != 55
            or report.get("reviewer_1_repair_case_count") != 0
        ):
            errors.append("agreement report mismatch")
        pending = strict_jsonl(root / "stage_b_gold_pending_300.jsonl")
        if len(pending) != 300 or any(
            not verify_record(row, "gold_pending_sha256") for row in pending
        ):
            errors.append("pending gold projection invalid")
        status_counts: dict[str, int] = {}
        for row in pending:
            status = str(row.get("gold_freeze_status"))
            status_counts[status] = status_counts.get(status, 0) + 1
        if status_counts != {
            "CONSENSUS_READY_NOT_FROZEN": 245,
            "PENDING_ADJUDICATION": 55,
        }:
            errors.append("pending gold status distribution mismatch")

        validation = strict_json_object(root / "validation_report.json")
        if (
            validation.get("status") != STATUS
            or validation.get("repaired_candidate_id") != candidate_id
            or validation.get("repaired_field") != "allowed_scope"
            or validation.get("reviewer_1_valid_case_count") != 300
            or validation.get("reviewer_2_valid_case_count") != 300
            or validation.get("adjudication_case_count") != 55
            or validation.get("stage_b_gold_autofill_count") != 0
        ):
            errors.append("validation report mismatch")

        parent_input = parent_artifact_root / "reviewer_3_adjudication_input.json"
        parent_zip = parent_artifact_root / "handoff" / "reviewer_3.zip"
        if sha256_file(root / "reviewer_3_adjudication_input.json") != sha256_file(
            parent_input
        ):
            errors.append("Reviewer 3 input changed")
        if sha256_file(root / "handoff" / "reviewer_3.zip") != sha256_file(
            parent_zip
        ):
            errors.append("Reviewer 3 ZIP changed")
        if manifest.get("reviewer_3_handoff_sha256") != sha256_file(parent_zip):
            errors.append("Reviewer 3 handoff manifest binding mismatch")
        for name, value in (
            ("manifest", manifest),
            ("agreement", report),
            ("pending", pending),
            ("repair", repair),
            ("validation", validation),
        ):
            _scan_guards(value, name, errors)
    except (KeyError, OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--parent-artifact-root", required=True, type=Path)
    parser.add_argument("--source-artifact-root", required=True, type=Path)
    args = parser.parse_args()
    errors = validate_artifact(
        args.artifact_root,
        parent_artifact_root=args.parent_artifact_root,
        source_artifact_root=args.source_artifact_root,
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
