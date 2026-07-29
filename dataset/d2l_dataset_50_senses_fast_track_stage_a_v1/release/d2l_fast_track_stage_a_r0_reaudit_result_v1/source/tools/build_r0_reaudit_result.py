from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        sha256_bytes,
        sha256_file,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from .r0_result import (
        RESULT_POLICY_ID,
        load_canonical_input,
        validate_completed_r0_result,
    )
    from .validate_r0_repair_reaudit import validate_repair_reaudit
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        sha256_bytes,
        sha256_file,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from r0_result import (  # type: ignore
        RESULT_POLICY_ID,
        load_canonical_input,
        validate_completed_r0_result,
    )
    from validate_r0_repair_reaudit import validate_repair_reaudit  # type: ignore


ARTIFACT_NAME = "d2l_fast_track_stage_a_r0_reaudit_result_v1"
STATUS = "R0_REAUDIT_COMPLETE_EXACT_50_UNLOCKED"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _extract_release(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            name = info.filename
            if name.startswith("/") or "\\" in name or ".." in Path(name).parts:
                raise ValueError(f"unsafe release ZIP path: {name}")
        archive.extractall(destination)
    return destination


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    files = (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/r0_result.py",
        "tools/build_r0_reaudit_result.py",
        "tools/validate_r0_reaudit_result.py",
        "tests/test_r0_reaudit_result.py",
    )
    for relative in files:
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"missing source bundle file: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def build_r0_reaudit_result(
    *,
    repair_release_zip: Path,
    completed_review: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    repair_release_zip = repair_release_zip.resolve(strict=True)
    completed_review = completed_review.resolve(strict=True)
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    canonical_root = temporary / "canonical_repair"
    staging.mkdir()
    canonical_root.mkdir()
    try:
        _extract_release(repair_release_zip, canonical_root)
        canonical_errors = validate_repair_reaudit(canonical_root)
        if canonical_errors:
            raise ValueError("canonical R0 repair artifact failed: " + "; ".join(canonical_errors))
        canonical = load_canonical_input(canonical_root)
        validated, errors = validate_completed_r0_result(canonical, completed_review)
        if errors or validated is None:
            raise ValueError("completed R0 review failed: " + "; ".join(errors))

        raw_relative = "raw_review/r0_blind_reauditor_completed.json"
        raw_destination = staging / raw_relative
        raw_destination.parent.mkdir(parents=True)
        shutil.copyfile(completed_review, raw_destination)
        if sha256_file(raw_destination) != validated.sha256:
            raise ValueError("captured R0 result hash drift")
        write_jsonl(staging / "r0_reaudit_results_4.jsonl", validated.records)
        write_json(
            staging / "result_report.json",
            seal_integrity(
                {
                    "schema_id": "D2LFastTrackStageAR0ReauditResultReportV1",
                    "schema_version": "1.0.0",
                    "artifact_name": ARTIFACT_NAME,
                    "policy_id": RESULT_POLICY_ID,
                    "status": STATUS,
                    "created_at": created_at,
                    "source_repair_release_zip_sha256": sha256_file(repair_release_zip),
                    "source_completed_review_path": raw_relative,
                    "source_completed_review_sha256": validated.sha256,
                    "case_count": 4,
                    "ready_count": 4,
                    "currently_ready_pool_count": 60,
                    "exact_50_minimum_r0_acceptance": 1,
                    "exact_50_gate_unlocked": True,
                    "provider_call_count": 0,
                    "stage_b_gold_autofill_count": 0,
                    "final_glossary_decision": None,
                }
            ),
        )
        _write_source_bundle(staging)
        (staging / "commands.txt").write_text(
            "python -B tools/build_r0_reaudit_result.py --repair-release-zip <ZIP> "
            "--completed-review <RESULT> --output-root <OUTPUT>\n"
            "python -B tools/validate_r0_reaudit_result.py --artifact-root <OUTPUT>\n",
            encoding="utf-8",
            newline="\n",
        )
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LFastTrackStageAR0ReauditResultManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": RESULT_POLICY_ID,
            "status": STATUS,
            "created_at": created_at,
            "case_count": 4,
            "ready_count": 4,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        try:
            from .validate_r0_reaudit_result import validate_artifact
        except ImportError:  # pragma: no cover
            from validate_r0_reaudit_result import validate_artifact  # type: ignore
        artifact_errors = validate_artifact(staging)
        if artifact_errors:
            raise ValueError("internal R0 result validation failed: " + "; ".join(artifact_errors))
        zip_name = f"{ARTIFACT_NAME}_release.zip"
        temporary_zip = temporary / zip_name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temporary_zip, final_zip)
        zip_sha = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_sha} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "release_zip": str(final_zip),
            "release_zip_sha256": zip_sha,
            "source_completed_review_sha256": validated.sha256,
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    namespace = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repair-release-zip",
        type=Path,
        default=namespace
        / "release"
        / "d2l_fast_track_stage_a_r0_repair_reaudit_v1_release.zip",
    )
    parser.add_argument(
        "--completed-review",
        type=Path,
        default=namespace
        / "release"
        / "d2l_fast_track_stage_a_r0_repair_reaudit_v1"
        / "handoff"
        / "reviewer_input.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default="2026-07-29T16:00:00Z")
    args = parser.parse_args()
    result = build_r0_reaudit_result(
        repair_release_zip=args.repair_release_zip,
        completed_review=args.completed_review,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
