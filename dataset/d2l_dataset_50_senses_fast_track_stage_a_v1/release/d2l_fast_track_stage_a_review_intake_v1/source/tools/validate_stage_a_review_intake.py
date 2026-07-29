from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

try:
    from .build_stage_a_review_intake import (
        INTAKE_ARTIFACT_NAME,
        INTAKE_POLICY_ID,
        INTAKE_STATUS,
        _manifest_self_hash,
    )
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from .review_result import validate_completed_result
    from .spec import REVIEW_FIELDS
except ImportError:  # pragma: no cover - direct script execution
    from build_stage_a_review_intake import (  # type: ignore
        INTAKE_ARTIFACT_NAME,
        INTAKE_POLICY_ID,
        INTAKE_STATUS,
        _manifest_self_hash,
    )
    from common import (  # type: ignore
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from review_result import validate_completed_result  # type: ignore
    from spec import REVIEW_FIELDS  # type: ignore


def _validate_manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"manifest: {exc}")
        return {}
    if manifest.get("artifact_name") != INTAKE_ARTIFACT_NAME:
        errors.append("manifest artifact name mismatch")
    if manifest.get("policy_id") != INTAKE_POLICY_ID:
        errors.append("manifest policy mismatch")
    if manifest.get("status") != INTAKE_STATUS:
        errors.append("manifest status mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self hash mismatch")
    if manifest.get("files") != build_file_inventory(
        root, {"manifest.json", "CHECKSUMS.sha256"}
    ):
        errors.append("manifest file inventory mismatch")
    expected_counts = {
        "review_result_file_count": 18,
        "completed_review_decision_count": 75,
        "adjudication_case_count": 24,
        "r0_repair_queue_count": 4,
        "provider_call_count": 0,
        "stage_b_gold_autofill_count": 0,
    }
    for field, expected in expected_counts.items():
        if manifest.get(field) != expected:
            errors.append(f"manifest count mismatch: {field}")
    if manifest.get("final_glossary_decision") is not None:
        errors.append("manifest contains final glossary decision")
    return manifest


def _validate_checksums(root: Path, errors: list[str]) -> None:
    path = root / "CHECKSUMS.sha256"
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"checksums: {exc}")
        return
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256"}
        ).items()
    }
    actual: dict[str, str] = {}
    for line in lines:
        if " *" not in line:
            errors.append("malformed checksum line")
            continue
        digest, relative = line.split(" *", 1)
        if relative in actual:
            errors.append(f"duplicate checksum path: {relative}")
        actual[relative] = digest
    if actual != expected:
        errors.append("checksum inventory mismatch")


def _validate_raw_reviews(
    root: Path, canonical_root: Path, inventory: Mapping[str, Any], errors: list[str]
) -> None:
    if not verify_integrity(inventory):
        errors.append("input inventory self hash mismatch")
    if inventory.get("result_file_count") != 18 or inventory.get("review_counts") != {
        "reviewer_1": 44,
        "reviewer_2": 31,
    }:
        errors.append("input inventory counts mismatch")
    rows = inventory.get("files")
    if not isinstance(rows, list) or len(rows) != 18:
        errors.append("input inventory file rows mismatch")
        return
    seen: set[tuple[str, str]] = set()
    total = Counter()
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append("input inventory row is invalid")
            continue
        slot = str(row.get("reviewer_slot"))
        batch_id = str(row.get("batch_id"))
        key = (slot, batch_id)
        if key in seen:
            errors.append(f"duplicate raw result binding: {slot}/{batch_id}")
        seen.add(key)
        captured = root / str(row.get("captured_relative_path"))
        if sha256_file(captured) != row.get("captured_sha256") or row.get(
            "captured_sha256"
        ) != row.get("source_sha256"):
            errors.append(f"raw result copy hash mismatch: {slot}/{batch_id}")
        canonical = canonical_root / "batches" / batch_id / f"{slot}_input.json"
        _, validation_errors, metrics = validate_completed_result(
            canonical,
            captured,
            expected_batch_id=batch_id,
            expected_reviewer_slot=slot,
        )
        errors.extend(
            f"raw result {slot}/{batch_id}: {message}"
            for message in validation_errors
        )
        total[slot] += metrics["case_count"]
    if dict(total) != {"reviewer_1": 44, "reviewer_2": 31}:
        errors.append("raw result validated case totals mismatch")


def _adjudication_is_blank(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    expected = set(REVIEW_FIELDS) | {"adjudication_rationale", "adjudication_status"}
    if set(value) != expected:
        return False
    for key, item in value.items():
        if key in {
            "invalid_evidence_context_ids",
            "candidate_replacements",
            "proposed_split_labels",
        }:
            if item != []:
                return False
        elif item != "":
            return False
    return True


def _validate_routes(root: Path, report: Mapping[str, Any], errors: list[str]) -> None:
    try:
        adjudication = strict_jsonl(root / "adjudication_cases_24.jsonl")
        repair = strict_jsonl(root / "r0_repair_queue_4.jsonl")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"route data: {exc}")
        return
    if len(adjudication) != 24 or len({row.get("sense_id") for row in adjudication}) != 24:
        errors.append("adjudication route must contain 24 unique senses")
    if Counter(row.get("routing_reason") for row in adjudication) != {
        "R4_MANDATORY_ADJUDICATION": 16,
        "R3_REVIEWER_DISAGREEMENT": 8,
    }:
        errors.append("adjudication routing counts mismatch")
    for row in adjudication:
        if not verify_record(row, "adjudication_case_sha256"):
            errors.append(f"adjudication case self hash mismatch: {row.get('sense_id')}")
        if not _adjudication_is_blank(row.get("adjudication")):
            errors.append(f"adjudication case is prefilled: {row.get('sense_id')}")
        if row.get("provider_call_count") != 0 or row.get(
            "stage_b_gold_label"
        ) is not None or row.get("final_glossary_decision") is not None:
            errors.append(f"adjudication boundary violation: {row.get('sense_id')}")
        claimed = row.get("source_payload_sha256")
        if claimed != sha256_bytes(canonical_json_bytes(row.get("source_payload"))):
            errors.append(f"adjudication source hash mismatch: {row.get('sense_id')}")
    if len(repair) != 4 or len({row.get("sense_id") for row in repair}) != 4:
        errors.append("R0 repair queue must contain 4 unique senses")
    for row in repair:
        if not verify_record(row, "repair_queue_record_sha256"):
            errors.append(f"R0 repair record self hash mismatch: {row.get('sense_id')}")
        if row.get("route") != "DATASET_REPAIR_THEN_REAUDIT":
            errors.append(f"R0 repair route mismatch: {row.get('sense_id')}")
    comparison = report.get("comparison")
    if comparison != {
        "r0_ready": 9,
        "r0_repair_required": 4,
        "r3_agreement": 7,
        "r3_disagreement": 8,
        "r4_mandatory": 16,
        "r4_with_agreement": 5,
        "r4_with_disagreement": 11,
        "reviewer_3_adjudication_cases": 24,
    }:
        errors.append("comparison report counts mismatch")


def _validate_handoffs(root: Path, report: Mapping[str, Any], errors: list[str]) -> None:
    handoffs = report.get("reviewer_3_handoffs")
    if not isinstance(handoffs, list) or len(handoffs) != 9:
        errors.append("Reviewer 3 handoff index mismatch")
        return
    total = 0
    for sequence, row in enumerate(handoffs, start=1):
        batch_id = f"batch_{sequence:03d}"
        if row.get("batch_id") != batch_id:
            errors.append(f"Reviewer 3 handoff order mismatch: {batch_id}")
        total += int(row.get("case_count", -999))
        path = root / str(row.get("zip_path"))
        if sha256_file(path) != row.get("zip_sha256"):
            errors.append(f"Reviewer 3 handoff ZIP hash mismatch: {batch_id}")
        try:
            with zipfile.ZipFile(path) as archive:
                names = [info.filename for info in archive.infolist()]
                if set(names) != {
                    "CHECKSUMS.sha256",
                    "MESSAGE.md",
                    "REVIEW_INSTRUCTIONS.md",
                    "reviewer_3_input.json",
                }:
                    errors.append(f"Reviewer 3 handoff entries mismatch: {batch_id}")
                for info in archive.infolist():
                    relative = PurePosixPath(info.filename)
                    if relative.is_absolute() or ".." in relative.parts or "\\" in info.filename:
                        errors.append(f"unsafe Reviewer 3 ZIP path: {info.filename}")
                payload = json.loads(archive.read("reviewer_3_input.json"))
                if payload.get("batch_id") != batch_id or payload.get(
                    "reviewer_slot"
                ) != "reviewer_3_adjudicator":
                    errors.append(f"Reviewer 3 input identity mismatch: {batch_id}")
                if payload.get("case_count") != row.get("case_count"):
                    errors.append(f"Reviewer 3 input case count mismatch: {batch_id}")
        except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"Reviewer 3 handoff {batch_id}: {exc}")
    if total != 24:
        errors.append("Reviewer 3 handoffs must contain 24 total cases")


def validate_intake(root: Path, *, canonical_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        return [f"artifact root: {exc}"]
    if canonical_root is None:
        namespace = Path(__file__).resolve().parents[1]
        canonical_root = namespace / "release" / "d2l_dataset_50_senses_fast_track_stage_a_v1"
    canonical_root = canonical_root.resolve(strict=True)
    _validate_manifest(root, errors)
    _validate_checksums(root, errors)
    try:
        inventory = strict_json_object(root / "input_inventory.json")
        report = strict_json_object(root / "comparison_report.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"intake metadata: {exc}")
        return errors
    if not verify_integrity(report):
        errors.append("comparison report self hash mismatch")
    if report.get("status") != INTAKE_STATUS or report.get("validated_result_files") != 18:
        errors.append("comparison report status/count mismatch")
    if report.get("completed_review_decisions") != 75:
        errors.append("comparison report review count mismatch")
    if report.get("provider_call_count") != 0 or report.get(
        "stage_b_gold_autofill_count"
    ) != 0 or report.get("final_glossary_decision") is not None:
        errors.append("comparison report boundary violation")
    _validate_raw_reviews(root, canonical_root, inventory, errors)
    _validate_routes(root, report, errors)
    _validate_handoffs(root, report, errors)
    required = {
        "source/.gitattributes",
        "source/README.md",
        "source/tools/common.py",
        "source/tools/spec.py",
        "source/tools/review_result.py",
        "source/tools/build_stage_a_review_intake.py",
        "source/tools/validate_stage_a_review_intake.py",
        "source/tests/test_stage_a_review_intake.py",
    }
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    for relative in sorted(required - actual):
        errors.append(f"source bundle file missing: {relative}")
    return errors


def validate_zip(zip_path: Path, artifact_root: Path) -> list[str]:
    expected = {
        path.relative_to(artifact_root).as_posix(): sha256_file(path)
        for path in artifact_root.rglob("*")
        if path.is_file()
    }
    errors: list[str] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                errors.append("release ZIP contains duplicate entries")
            actual = {info.filename: sha256_bytes(archive.read(info)) for info in infos}
            if actual != expected:
                errors.append("release ZIP differs from artifact directory")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"release ZIP: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--canonical-root", type=Path)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_intake(args.artifact_root, canonical_root=args.canonical_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root))
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
