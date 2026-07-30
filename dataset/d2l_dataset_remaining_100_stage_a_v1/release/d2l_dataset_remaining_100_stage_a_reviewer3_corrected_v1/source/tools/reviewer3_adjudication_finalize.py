from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.adjudication_result import (
    validate_completed_adjudication,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    replace_directory,
    seal_integrity,
    sha256_bytes,
    sha256_file,
    strict_json_loads,
    strict_json_object,
    write_checksums,
    write_json,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.reviewer3_adjudication_repair import (
    EXPECTED_BATCH_COUNT,
    EXPECTED_CASE_COUNT,
    EXPECTED_REPAIR_CASE_COUNT,
    apply_repair_response,
    validate_repair_response,
)


ARTIFACT_NAME = "d2l_dataset_remaining_100_stage_a_reviewer3_corrected_v1"
POLICY_ID = "d2l-remaining-100-stage-a-reviewer3-corrected-v1.0"
STATUS = "REVIEWER_3_ADJUDICATION_CORRECTED_ZERO_PROVIDER"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _capture_file(source: Path, destination: Path) -> dict[str, Any]:
    source = source.resolve(strict=True)
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"missing or unsafe input file: {source}")
    before_sha = sha256_file(source)
    before_size = source.stat().st_size
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    captured_sha = sha256_file(destination)
    after_sha = sha256_file(source)
    if before_sha != captured_sha or before_sha != after_sha:
        raise ValueError(f"input drift during capture: {source}")
    return {
        "source_file_name": source.name,
        "size_bytes": before_size,
        "source_sha256": before_sha,
        "captured_sha256": captured_sha,
    }


def _batch_rows(intake_root: Path) -> list[dict[str, Any]]:
    payload = strict_json_object(intake_root / "reviewer_3_batch_index.json")
    rows = payload.get("batches")
    if not isinstance(rows, list):
        raise ValueError("reviewer_3_batch_index.json: batches must be an array")
    if payload.get("batch_count") != EXPECTED_BATCH_COUNT:
        raise ValueError("reviewer_3_batch_index.json: unexpected batch count")
    if payload.get("case_count") != EXPECTED_CASE_COUNT:
        raise ValueError("reviewer_3_batch_index.json: unexpected case count")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("reviewer_3_batch_index.json: batch row is not an object")
        batch_id = row.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id or batch_id in seen:
            raise ValueError("reviewer_3_batch_index.json: invalid batch identity")
        seen.add(batch_id)
        result.append(dict(row))
    return result


def _canonical_payload(intake_root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    zip_path = intake_root / str(row["zip_path"])
    if sha256_file(zip_path) != row.get("zip_sha256"):
        raise ValueError(f"{row['batch_id']}: canonical handoff ZIP hash mismatch")
    try:
        with zipfile.ZipFile(zip_path) as archive:
            raw = archive.read("reviewer_3_input.json")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"{row['batch_id']}: invalid canonical handoff ZIP") from exc
    payload = strict_json_loads(raw.decode("utf-8", errors="strict"))
    if not isinstance(payload, dict):
        raise ValueError(f"{row['batch_id']}: canonical input is not an object")
    return payload


def _source_result_path(reviewer_3_root: Path, batch_id: str) -> Path:
    return reviewer_3_root / batch_id / "reviewer_3_input.json"


def _assert_exact_patch(
    *,
    source_payload: Mapping[str, Any],
    corrected_payload: Mapping[str, Any],
    patches: Mapping[tuple[str, str], Mapping[str, Any]],
    batch_id: str,
) -> int:
    source_cases = source_payload.get("cases")
    corrected_cases = corrected_payload.get("cases")
    if not isinstance(source_cases, list) or not isinstance(corrected_cases, list):
        raise ValueError(f"{batch_id}: cases must be arrays")
    if len(source_cases) != len(corrected_cases):
        raise ValueError(f"{batch_id}: corrected case count changed")
    changed = 0
    for source_case, corrected_case in zip(source_cases, corrected_cases):
        if not isinstance(source_case, Mapping) or not isinstance(
            corrected_case, Mapping
        ):
            raise ValueError(f"{batch_id}: case must be an object")
        expected = copy.deepcopy(source_case)
        case_id = source_case.get("adjudication_case_id")
        patch = patches.get((batch_id, str(case_id)))
        if patch is not None:
            adjudication = expected.get("adjudication")
            if not isinstance(adjudication, dict):
                raise ValueError(f"{batch_id}/{case_id}: missing adjudication")
            adjudication["evidence_decision"] = patch["evidence_decision"]
            adjudication["invalid_evidence_context_ids"] = copy.deepcopy(
                patch["invalid_evidence_context_ids"]
            )
            changed += 1
        if corrected_case != expected:
            raise ValueError(f"{batch_id}/{case_id}: corrected bytes exceed repair scope")
    return changed


def _validate_corrected_tree(
    *,
    intake_root: Path,
    reviewer_3_root: Path,
    corrected_root: Path,
    response: Mapping[str, Any],
) -> dict[str, Any]:
    patches = {
        (case["batch_id"], case["adjudication_case_id"]): case["repair"]
        for case in response["cases"]
    }
    if len(patches) != EXPECTED_REPAIR_CASE_COUNT:
        raise ValueError("repair response must bind exactly eight unique cases")

    source_before = {
        row["batch_id"]: sha256_file(
            _source_result_path(reviewer_3_root, row["batch_id"])
        )
        for row in _batch_rows(intake_root)
    }
    corrected_inventory: list[dict[str, Any]] = []
    total_cases = 0
    corrected_cases = 0
    for row in _batch_rows(intake_root):
        batch_id = row["batch_id"]
        source_path = _source_result_path(reviewer_3_root, batch_id)
        corrected_path = corrected_root / batch_id / "reviewer_3_input.json"
        source_payload = strict_json_object(source_path)
        corrected_payload = strict_json_object(corrected_path)
        canonical = _canonical_payload(intake_root, row)
        _, errors, metrics = validate_completed_adjudication(
            canonical,
            corrected_path,
            expected_batch_id=batch_id,
        )
        if errors:
            raise ValueError(
                f"{batch_id}: corrected adjudication is invalid: " + "; ".join(errors)
            )
        total_cases += int(metrics.get("case_count", 0))
        corrected_cases += _assert_exact_patch(
            source_payload=source_payload,
            corrected_payload=corrected_payload,
            patches=patches,
            batch_id=batch_id,
        )
        corrected_inventory.append(
            {
                "batch_id": batch_id,
                "case_count": metrics.get("case_count"),
                "source_sha256": source_before[batch_id],
                "corrected_sha256": sha256_file(corrected_path),
                "relative_path": corrected_path.relative_to(
                    corrected_root.parent.parent
                ).as_posix(),
            }
        )
    source_after = {
        row["batch_id"]: sha256_file(
            _source_result_path(reviewer_3_root, row["batch_id"])
        )
        for row in _batch_rows(intake_root)
    }
    if source_before != source_after:
        raise ValueError("Reviewer 3 source results drifted during finalization")
    if total_cases != EXPECTED_CASE_COUNT:
        raise ValueError(f"corrected case total mismatch: {total_cases}")
    if corrected_cases != EXPECTED_REPAIR_CASE_COUNT:
        raise ValueError(f"corrected repair total mismatch: {corrected_cases}")
    return {
        "validated_batch_count": len(corrected_inventory),
        "validated_case_count": total_cases,
        "corrected_case_count": corrected_cases,
        "source_result_files_unchanged": True,
        "corrected_inventory": corrected_inventory,
    }


def validate_release(
    release_root: Path,
    *,
    intake_root: Path,
    reviewer_3_root: Path,
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = strict_json_object(release_root / "manifest.json")
        if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
            errors.append("manifest self hash mismatch")
        response = strict_json_object(
            release_root / "audit" / "reviewer_3_repair_response.json"
        )
        report = _validate_corrected_tree(
            intake_root=intake_root,
            reviewer_3_root=reviewer_3_root,
            corrected_root=release_root / "corrected_reviews" / "reviewer_3",
            response=response,
        )
        for key in (
            "validated_batch_count",
            "validated_case_count",
            "corrected_case_count",
        ):
            if manifest.get(key) != report[key]:
                errors.append(f"manifest {key} mismatch")
        actual_files = build_file_inventory(
            release_root, {"manifest.json", "CHECKSUMS.sha256"}
        )
        if manifest.get("files") != actual_files:
            errors.append("manifest file inventory mismatch")
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        errors.append(str(exc))
    return errors


def build_corrected_release(
    *,
    intake_root: Path,
    reviewer_3_root: Path,
    repair_source_root: Path,
    response_path: Path,
    output_root: Path,
    zip_path: Path,
) -> dict[str, Any]:
    intake_root = intake_root.resolve(strict=True)
    reviewer_3_root = reviewer_3_root.resolve(strict=True)
    repair_source_root = repair_source_root.resolve(strict=True)
    response_path = response_path.resolve(strict=True)
    output_root = output_root.resolve()
    zip_path = zip_path.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=".d2l-r3-final-", dir=output_root.parent
    ) as temp_dir:
        temporary = Path(temp_dir)
        staging = temporary / ARTIFACT_NAME
        staging.mkdir()
        audit = staging / "audit"
        captured_input = audit / "reviewer_3_repair_input.json"
        captured_preflight = audit / "preflight_report.json"
        captured_response = audit / "reviewer_3_repair_response.json"
        captures = []
        for role, source, destination in (
            (
                "repair_input",
                repair_source_root / "reviewer_3_repair_input.json",
                captured_input,
            ),
            (
                "repair_preflight",
                repair_source_root / "preflight_report.json",
                captured_preflight,
            ),
            ("repair_response", response_path, captured_response),
        ):
            metadata = _capture_file(source, destination)
            metadata["input_role"] = role
            metadata["captured_relative_path"] = destination.relative_to(
                staging
            ).as_posix()
            captures.append(metadata)

        response, response_errors = validate_repair_response(
            captured_input, captured_response
        )
        if response_errors or response is None:
            raise ValueError(
                "repair response validation failed: " + "; ".join(response_errors)
            )
        corrected_root = staging / "corrected_reviews" / "reviewer_3"
        apply_repair_response(
            intake_root=intake_root,
            reviewer_3_root=reviewer_3_root,
            repair_input_path=captured_input,
            response_path=captured_response,
            output_root=corrected_root,
        )
        validation = _validate_corrected_tree(
            intake_root=intake_root,
            reviewer_3_root=reviewer_3_root,
            corrected_root=corrected_root,
            response=response,
        )
        validation_report = seal_integrity(
            {
                "schema_id": "D2LRemaining100StageAReviewer3CorrectedReportV1",
                "schema_version": "1.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "input_captures": captures,
                **validation,
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            }
        )
        write_json(staging / "validation_report.json", validation_report)
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L remaining-100 Reviewer 3 corrected release\n\n"
            "- Reviewer 3 repair response: 8/8 cases accepted.\n"
            "- Corrected Reviewer 3 batch results: 10/10 files.\n"
            "- Corrected adjudication validation: 45/45 cases.\n"
            "- Original Reviewer 3 result bytes remain unchanged.\n"
            "- Provider calls: 0.\n"
            "- Stage B gold autofill: 0.\n"
            "- Final glossary decision: null.\n",
            encoding="utf-8",
            newline="\n",
        )
        namespace = Path(__file__).resolve().parents[1]
        for relative in (
            "tools/reviewer3_adjudication_repair.py",
            "tools/reviewer3_adjudication_finalize.py",
            "tests/test_reviewer3_adjudication_repair.py",
            "tests/test_reviewer3_adjudication_finalize.py",
        ):
            source = namespace / relative
            destination = staging / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)

        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LRemaining100StageAReviewer3CorrectedManifestV1",
            "schema_version": "1.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "status": STATUS,
            "validated_batch_count": validation["validated_batch_count"],
            "validated_case_count": validation["validated_case_count"],
            "corrected_case_count": validation["corrected_case_count"],
            "source_result_files_unchanged": True,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")

        release_errors = validate_release(
            staging,
            intake_root=intake_root,
            reviewer_3_root=reviewer_3_root,
        )
        if release_errors:
            raise ValueError("corrected release validation failed: " + "; ".join(release_errors))

        temporary_zip = temporary / zip_path.name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        os.replace(temporary_zip, zip_path)

    zip_sha = sha256_file(zip_path)
    zip_path.with_suffix(zip_path.suffix + ".sha256").write_text(
        f"{zip_sha} *{zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        "status": STATUS,
        "artifact_root": str(output_root),
        "manifest_sha256": strict_json_object(output_root / "manifest.json")[
            "manifest_sha256"
        ],
        "zip_path": str(zip_path),
        "zip_sha256": zip_sha,
        **{
            key: strict_json_object(output_root / "manifest.json")[key]
            for key in (
                "validated_batch_count",
                "validated_case_count",
                "corrected_case_count",
            )
        },
        "provider_call_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake-root", type=Path, required=True)
    parser.add_argument("--reviewer-3-root", type=Path, required=True)
    parser.add_argument("--repair-source-root", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path, required=True)
    args = parser.parse_args()
    result = build_corrected_release(
        intake_root=args.intake_root,
        reviewer_3_root=args.reviewer_3_root,
        repair_source_root=args.repair_source_root,
        response_path=args.response,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
