from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_file_inventory,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_record,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_review_preflight import (
    ARTIFACT_NAME,
    POLICY_ID,
    STATUS,
    _analyze_reviews,
    _manifest_self_hash,
    _validate_source_artifact,
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


def _scan_runtime_guards(value: Any, path: str, errors: list[str]) -> None:
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
            _scan_runtime_guards(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_runtime_guards(child, f"{path}[{index}]", errors)


def _validate_handoff_zip(
    root: Path,
    *,
    zip_relative: str,
    input_name: str,
    expected: Mapping[str, Any],
    errors: list[str],
) -> None:
    try:
        with zipfile.ZipFile(root / zip_relative) as archive:
            names = set(archive.namelist())
            required = {input_name, "REVIEW_INSTRUCTIONS.md", "MESSAGE.md"}
            if names != required:
                errors.append(f"handoff ZIP inventory mismatch: {zip_relative}")
                return
            packaged = json.loads(archive.read(input_name).decode("utf-8"))
            if packaged != expected:
                errors.append(f"handoff payload mismatch: {zip_relative}")
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as exc:
        errors.append(str(exc))


def validate_artifact(root: Path, *, source_artifact_root: Path) -> list[str]:
    root = root.resolve()
    source_artifact_root = source_artifact_root.resolve()
    errors: list[str] = []
    try:
        source_manifest = _validate_source_artifact(source_artifact_root)
        manifest = strict_json_object(root / "manifest.json")
        if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
            errors.append("manifest self-hash mismatch")
        if (
            manifest.get("artifact_name") != ARTIFACT_NAME
            or manifest.get("policy_id") != POLICY_ID
            or manifest.get("status") != STATUS
        ):
            errors.append("manifest identity/status mismatch")
        if manifest.get("source_artifact_manifest_sha256") != source_manifest.get(
            "manifest_sha256"
        ):
            errors.append("source artifact binding mismatch")
        expected_files = manifest.get("files")
        actual_files = build_file_inventory(root, {"manifest.json"})
        if not isinstance(expected_files, Mapping) or expected_files != actual_files:
            errors.append("manifest file inventory mismatch")
        _validate_checksums(root, errors)

        analysis = _analyze_reviews(
            source_artifact_root,
            root / "raw_reviews" / "reviewer_1.json",
            root / "raw_reviews" / "reviewer_2.json",
        )
        pairs = strict_jsonl(root / "review_pairs_300.jsonl")
        if pairs != analysis["pairs"]:
            errors.append("review pair projection mismatch")
        if any(not verify_record(row, "review_pair_sha256") for row in pairs):
            errors.append("review pair self-hash mismatch")
        if len(pairs) != 300:
            errors.append("review pair count mismatch")

        report = strict_json_object(root / "agreement_report.json")
        if (
            report.get("status") != STATUS
            or report.get("case_count") != 300
            or report.get("agreement_count") != analysis["agreement_count"]
            or report.get("disagreement_count") != analysis["disagreement_count"]
            or report.get("reviewer_1_repair_case_count") != 1
        ):
            errors.append("agreement report mismatch")

        repair = strict_json_object(root / "reviewer_1_repair_input.json")
        if repair.get("case_count") != 1 or repair.get("cases") != analysis[
            "repair_cases"
        ]:
            errors.append("reviewer repair projection mismatch")
        repair_binding = [
            {
                "repair_case_id": row["repair_case_id"],
                "repair_case_sha256": row["repair_case_sha256"],
            }
            for row in analysis["repair_cases"]
        ]
        if repair.get("source_input_sha256") != sha256_bytes(
            canonical_json_bytes(repair_binding)
        ):
            errors.append("reviewer repair source binding mismatch")

        adjudication = strict_json_object(root / "reviewer_3_adjudication_input.json")
        if (
            adjudication.get("case_count") != analysis["disagreement_count"]
            or adjudication.get("cases") != analysis["adjudication_cases"]
        ):
            errors.append("adjudication projection mismatch")
        adjudication_binding = [
            {
                "adjudication_case_id": row["adjudication_case_id"],
                "adjudication_case_sha256": row["adjudication_case_sha256"],
            }
            for row in analysis["adjudication_cases"]
        ]
        if adjudication.get("source_input_sha256") != sha256_bytes(
            canonical_json_bytes(adjudication_binding)
        ):
            errors.append("adjudication source binding mismatch")

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
            "CONSENSUS_READY_NOT_FROZEN": analysis["agreement_count"] - 1,
            "PENDING_ADJUDICATION": analysis["disagreement_count"],
            "PENDING_REVIEWER_1_REPAIR": 1,
        }:
            errors.append("pending gold status distribution mismatch")

        validation = strict_json_object(root / "validation_report.json")
        if (
            validation.get("reviewer_1_valid_case_count") != 299
            or validation.get("reviewer_2_valid_case_count") != 300
            or validation.get("adjudication_case_count")
            != analysis["disagreement_count"]
            or validation.get("stage_b_gold_autofill_count") != 0
        ):
            errors.append("validation report mismatch")
        if validation.get("reviewer_1_source_sha256") != sha256_file(
            root / "raw_reviews" / "reviewer_1.json"
        ) or validation.get("reviewer_2_source_sha256") != sha256_file(
            root / "raw_reviews" / "reviewer_2.json"
        ):
            errors.append("captured review hash mismatch")

        _validate_handoff_zip(
            root,
            zip_relative=str(manifest["reviewer_1_repair_handoff_path"]),
            input_name="reviewer_1_repair_input.json",
            expected=repair,
            errors=errors,
        )
        _validate_handoff_zip(
            root,
            zip_relative=str(manifest["reviewer_3_handoff_path"]),
            input_name="reviewer_3_adjudication_input.json",
            expected=adjudication,
            errors=errors,
        )
        for name, value in (
            ("manifest", manifest),
            ("agreement_report", report),
            ("repair", repair),
            ("adjudication", adjudication),
            ("pending", pending),
        ):
            _scan_runtime_guards(value, name, errors)
    except (KeyError, OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--source-artifact-root", required=True, type=Path)
    args = parser.parse_args()
    errors = validate_artifact(
        args.artifact_root, source_artifact_root=args.source_artifact_root
    )
    print(
        json.dumps(
            {
                "status": "PASS" if not errors else "FAIL",
                "errors": errors,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
