from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_r0_reaudit_result import ARTIFACT_NAME, STATUS, _manifest_self_hash
    from .common import (
        build_file_inventory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from .r0_result import EXPECTED_TERMS, RESULT_POLICY_ID
except ImportError:  # pragma: no cover - direct script execution
    from build_r0_reaudit_result import ARTIFACT_NAME, STATUS, _manifest_self_hash  # type: ignore
    from common import (  # type: ignore
        build_file_inventory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from r0_result import EXPECTED_TERMS, RESULT_POLICY_ID  # type: ignore


def _validate_checksums(root: Path, errors: list[str]) -> None:
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"checksums: {exc}")
        return
    actual: dict[str, str] = {}
    for line in lines:
        if " *" not in line:
            errors.append("malformed checksum line")
            continue
        digest, relative = line.split(" *", 1)
        if relative in actual:
            errors.append(f"duplicate checksum path: {relative}")
        actual[relative] = digest
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(root, {"CHECKSUMS.sha256"}).items()
    }
    if actual != expected:
        errors.append("checksum inventory mismatch")


def validate_artifact(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
        manifest = strict_json_object(root / "manifest.json")
        report = strict_json_object(root / "result_report.json")
        records = strict_jsonl(root / "r0_reaudit_results_4.jsonl")
    except (OSError, UnicodeError, ValueError) as exc:
        return [str(exc)]
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("manifest artifact name mismatch")
    if manifest.get("policy_id") != RESULT_POLICY_ID or report.get("policy_id") != RESULT_POLICY_ID:
        errors.append("R0 result policy mismatch")
    if manifest.get("status") != STATUS or report.get("status") != STATUS:
        errors.append("R0 result status mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self hash mismatch")
    if manifest.get("files") != build_file_inventory(
        root, {"manifest.json", "CHECKSUMS.sha256"}
    ):
        errors.append("manifest file inventory mismatch")
    if not verify_integrity(report):
        errors.append("R0 result report self hash mismatch")
    if len(records) != 4 or {row.get("source_term") for row in records} != set(EXPECTED_TERMS):
        errors.append("R0 result record set mismatch")
    for row in records:
        if not verify_record(row, "result_record_sha256"):
            errors.append(f"R0 result record self hash mismatch: {row.get('sense_id')}")
        if row.get("stage_a_status") != "READY_FOR_CONTRACT_CONSTRUCTION":
            errors.append(f"R0 result is not ready: {row.get('sense_id')}")
        review = row.get("review")
        if not isinstance(review, Mapping) or review.get("review_status") != "COMPLETE":
            errors.append(f"R0 review is incomplete: {row.get('sense_id')}")
        if row.get("provider_call_count") != 0 or row.get("stage_b_gold_label") is not None:
            errors.append(f"R0 result boundary violation: {row.get('sense_id')}")
        if row.get("final_glossary_decision") is not None:
            errors.append(f"R0 result final decision must remain null: {row.get('sense_id')}")
    raw = root / str(report.get("source_completed_review_path"))
    if not raw.is_file() or sha256_file(raw) != report.get("source_completed_review_sha256"):
        errors.append("captured completed R0 review hash mismatch")
    if report.get("case_count") != 4 or report.get("ready_count") != 4:
        errors.append("R0 result report counts mismatch")
    if report.get("currently_ready_pool_count") != 60 or not report.get(
        "exact_50_gate_unlocked"
    ):
        errors.append("exact-50 gate was not unlocked")
    if report.get("provider_call_count") != 0 or report.get("stage_b_gold_autofill_count") != 0:
        errors.append("R0 report boundary counts mismatch")
    if report.get("final_glossary_decision") is not None:
        errors.append("R0 report final decision must remain null")
    _validate_checksums(root, errors)
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
            if any(name.startswith("/") or "\\" in name or ".." in Path(name).parts for name in names):
                errors.append("release ZIP contains an unsafe path")
            actual = {info.filename: sha256_bytes(archive.read(info)) for info in infos}
            if actual != expected:
                errors.append("release ZIP differs from artifact directory")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"release ZIP: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root.resolve(strict=True)))
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
