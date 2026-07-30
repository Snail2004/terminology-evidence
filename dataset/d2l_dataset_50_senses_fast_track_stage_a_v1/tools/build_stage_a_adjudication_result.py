from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

try:
    from .adjudication_result import (
        ValidatedAdjudication,
        validate_completed_adjudication,
    )
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_loads,
        strict_json_object,
        strict_jsonl,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from .spec import CREATED_AT_DEFAULT
    from .validate_stage_a_review_intake import validate_intake
except ImportError:  # pragma: no cover - direct script execution
    from adjudication_result import (  # type: ignore
        ValidatedAdjudication,
        validate_completed_adjudication,
    )
    from common import (  # type: ignore
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_loads,
        strict_json_object,
        strict_jsonl,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from spec import CREATED_AT_DEFAULT  # type: ignore
    from validate_stage_a_review_intake import validate_intake  # type: ignore


ARTIFACT_NAME = "d2l_fast_track_stage_a_adjudication_result_v1"
POLICY_ID = "d2l-fast-track-stage-a-adjudication-result-v1.0"
STATUS = "ADJUDICATION_COMPLETE_R0_REPAIR_PENDING"
EXPECTED_BATCH_CASE_COUNTS = {
    "batch_001": 1,
    "batch_002": 2,
    "batch_003": 3,
    "batch_004": 3,
    "batch_005": 2,
    "batch_006": 3,
    "batch_007": 2,
    "batch_008": 4,
    "batch_009": 4,
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _result_name(batch_id: str) -> str:
    return f"{batch_id}_reviewer_3_completed.json"


def validate_canonical_intake_projection(intake_root: Path) -> list[str]:
    """Validate only the manifest-sealed intake bytes, leaving external results alone."""
    errors: list[str] = []
    intake_root = intake_root.resolve(strict=True)
    try:
        manifest = strict_json_object(intake_root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"canonical intake manifest: {exc}"]
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        return ["canonical intake manifest file inventory is invalid"]
    with tempfile.TemporaryDirectory() as temporary_name:
        snapshot = Path(temporary_name) / "intake"
        snapshot.mkdir()
        selected = ["manifest.json", "CHECKSUMS.sha256", *files.keys()]
        for relative in selected:
            if (
                not isinstance(relative, str)
                or not relative
                or "\\" in relative
                or Path(relative).is_absolute()
                or any(part in {"", ".", ".."} for part in relative.split("/"))
            ):
                errors.append(f"unsafe canonical intake path: {relative!r}")
                continue
            source = intake_root / relative
            try:
                resolved = source.resolve(strict=True)
            except OSError as exc:
                errors.append(f"canonical intake file missing: {relative}: {exc}")
                continue
            try:
                resolved.relative_to(intake_root)
            except ValueError:
                errors.append(f"canonical intake path escapes root: {relative}")
                continue
            if source.is_symlink() or not source.is_file():
                errors.append(f"unsafe canonical intake file: {relative}")
                continue
            metadata = files.get(relative)
            if isinstance(metadata, Mapping) and sha256_file(source) != metadata.get(
                "sha256"
            ):
                errors.append(f"canonical intake file hash mismatch: {relative}")
                continue
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        if errors:
            return errors
        return validate_intake(snapshot)


def load_canonical_adjudicator_input(
    intake_root: Path, batch_id: str
) -> tuple[dict[str, Any], str, str]:
    zip_path = intake_root / "handoff" / f"{batch_id}_reviewer_3_adjudication.zip"
    zip_sha = sha256_file(zip_path)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = [info.filename for info in archive.infolist()]
            expected = {
                "CHECKSUMS.sha256",
                "MESSAGE.md",
                "REVIEW_INSTRUCTIONS.md",
                "reviewer_3_input.json",
            }
            if len(names) != len(set(names)) or set(names) != expected:
                raise ValueError(f"canonical adjudicator ZIP entries mismatch: {batch_id}")
            raw = archive.read("reviewer_3_input.json")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"cannot read canonical adjudicator input: {batch_id}: {exc}") from exc
    try:
        payload = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"invalid canonical adjudicator input: {batch_id}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"canonical adjudicator input must be an object: {batch_id}")
    return payload, zip_sha, sha256_bytes(raw)


def _capture_and_validate_results(
    *,
    intake_root: Path,
    reviewer_3_root: Path,
    staging: Path,
) -> tuple[list[ValidatedAdjudication], dict[str, Any]]:
    reviewer_3_root = reviewer_3_root.resolve(strict=True)
    if reviewer_3_root.is_symlink():
        raise ValueError("Reviewer 3 result root must not be a symlink")
    expected_names = {_result_name(batch_id) for batch_id in EXPECTED_BATCH_CASE_COUNTS}
    ignored = sorted(entry.name for entry in reviewer_3_root.iterdir() if entry.name not in expected_names)
    resolved_paths: set[Path] = set()
    validated: list[ValidatedAdjudication] = []
    inventory_rows: list[dict[str, Any]] = []
    metric_totals: Counter[str] = Counter()
    for batch_id, expected_case_count in EXPECTED_BATCH_CASE_COUNTS.items():
        name = _result_name(batch_id)
        source_path = reviewer_3_root / name
        if not source_path.is_file() or source_path.is_symlink():
            raise ValueError(f"missing or unsafe Reviewer 3 result: {name}")
        resolved = source_path.resolve(strict=True)
        if resolved in resolved_paths:
            raise ValueError(f"Reviewer 3 result physical path reused: {source_path}")
        resolved_paths.add(resolved)
        canonical, canonical_zip_sha, canonical_input_physical_sha = (
            load_canonical_adjudicator_input(intake_root, batch_id)
        )
        before_sha = sha256_file(source_path)
        destination = staging / "raw_reviews" / "reviewer_3" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
        captured_sha = sha256_file(destination)
        after_sha = sha256_file(source_path)
        if before_sha != captured_sha or before_sha != after_sha:
            raise ValueError(f"Reviewer 3 result drift during capture: {name}")
        result, errors, metrics = validate_completed_adjudication(
            canonical,
            destination,
            expected_batch_id=batch_id,
        )
        if errors or result is None:
            raise ValueError(
                f"Reviewer 3 result validation failed for {name}: "
                + "; ".join(errors)
            )
        if metrics.get("case_count") != expected_case_count:
            raise ValueError(f"Reviewer 3 case count mismatch for {batch_id}")
        validated.append(result)
        metric_totals.update(metrics)
        inventory_rows.append(
            {
                "batch_id": batch_id,
                "reviewer_slot": "reviewer_3_adjudicator",
                "source_path": str(source_path.resolve()),
                "source_sha256": before_sha,
                "captured_relative_path": destination.relative_to(staging).as_posix(),
                "captured_sha256": captured_sha,
                "canonical_handoff_zip_sha256": canonical_zip_sha,
                "canonical_input_physical_sha256": canonical_input_physical_sha,
                "source_input_sha256": canonical["source_input_sha256"],
                "case_count": expected_case_count,
            }
        )
    if metric_totals["case_count"] != 24:
        raise ValueError(f"Reviewer 3 total case count mismatch: {metric_totals['case_count']}")
    inventory = seal_integrity(
        {
            "schema_id": "D2LFastTrackStageAAdjudicationInputInventoryV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "reviewer_slot": "reviewer_3_adjudicator",
            "result_file_count": len(inventory_rows),
            "case_count": metric_totals["case_count"],
            "metrics": dict(sorted(metric_totals.items())),
            "ignored_unconsumed_entries": ignored,
            "files": inventory_rows,
        }
    )
    return validated, inventory


def _build_result_records(
    validated: list[ValidatedAdjudication],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in validated:
        source_input_sha256 = result.payload["source_input_sha256"]
        for case in result.payload["cases"]:
            adjudication = case["adjudication"]
            records.append(
                seal_record(
                    {
                        "schema_id": "D2LFastTrackStageAAdjudicationResultRecordV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        "status": adjudication["sense_status"],
                        "batch_id": case["batch_id"],
                        "sense_id": case["sense_id"],
                        "source_term": case["source_term"],
                        "risk_class": case["risk_class"],
                        "routing_reason": case["routing_reason"],
                        "source_adjudication_case_id": case["adjudication_case_id"],
                        "source_adjudication_case_sha256": case[
                            "adjudication_case_sha256"
                        ],
                        "source_input_sha256": source_input_sha256,
                        "source_payload": case["source_payload"],
                        "source_payload_sha256": case["source_payload_sha256"],
                        "reviewer_1": case["reviewer_1"],
                        "reviewer_2": case["reviewer_2"],
                        "reviewer_3_result_file_sha256": result.sha256,
                        "adjudication": adjudication,
                        "candidate_replacement_count": len(
                            adjudication["candidate_replacements"]
                        ),
                        "provider_call_count": 0,
                        "stage_b_gold_label": None,
                        "final_glossary_decision": None,
                    },
                    "adjudication_result_sha256",
                )
            )
    records.sort(key=lambda row: (row["batch_id"], row["source_term"].casefold()))
    if len(records) != 24 or len({row["sense_id"] for row in records}) != 24:
        raise ValueError("adjudication output must contain 24 unique senses")
    return records


def _summarize(
    records: list[Mapping[str, Any]], comparison: Mapping[str, Any]
) -> dict[str, Any]:
    decisions: dict[str, Counter[str]] = {
        field: Counter() for field in (
            "definition_decision",
            "part_of_speech_decision",
            "scope_decision",
            "evidence_decision",
            "candidate_set_decision",
            "sense_status",
        )
    }
    risk = Counter()
    routing = Counter()
    replacement_count = 0
    for record in records:
        adjudication = record["adjudication"]
        for field in decisions:
            decisions[field][adjudication[field]] += 1
        risk[record["risk_class"]] += 1
        routing[record["routing_reason"]] += 1
        replacement_count += int(record["candidate_replacement_count"])
    summary = {
        "adjudicated_case_count": len(records),
        "ready_for_contract_construction_count": decisions["sense_status"][
            "READY_FOR_CONTRACT_CONSTRUCTION"
        ],
        "candidate_replacement_count": replacement_count,
        "decision_counts": {
            field: dict(sorted(counts.items())) for field, counts in decisions.items()
        },
        "risk_counts": dict(sorted(risk.items())),
        "routing_counts": dict(sorted(routing.items())),
        "stage_a_new_sense_funnel": {
            "new_sense_count": 44,
            "r0_ready_without_adjudication": comparison["r0_ready"],
            "r3_ready_by_two_reviewer_agreement": comparison["r3_agreement"],
            "ready_after_reviewer_3_adjudication": len(records),
            "ready_for_contract_construction_total": comparison["r0_ready"]
            + comparison["r3_agreement"]
            + len(records),
            "r0_repair_and_reaudit_pending": comparison["r0_repair_required"],
        },
        "pool_funnel": {
            "inherited_reviewed_senses": 16,
            "new_ready_senses": comparison["r0_ready"]
            + comparison["r3_agreement"]
            + len(records),
            "pending_r0_senses": comparison["r0_repair_required"],
            "pool_sense_count": 60,
        },
    }
    expected = {
        "adjudicated_case_count": 24,
        "ready_for_contract_construction_count": 24,
        "candidate_replacement_count": 26,
        "risk_counts": {"R3_AMBIGUOUS": 8, "R4_SPLIT_OR_POS_RISK": 16},
        "routing_counts": {
            "R3_REVIEWER_DISAGREEMENT": 8,
            "R4_MANDATORY_ADJUDICATION": 16,
        },
    }
    for field, value in expected.items():
        if summary[field] != value:
            raise ValueError(f"adjudication summary drift: {field}={summary[field]}")
    if summary["decision_counts"]["candidate_set_decision"] != {
        "ACCEPT": 6,
        "REVISE": 18,
    }:
        raise ValueError("candidate-set adjudication counts drift")
    return summary


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    files = (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/adjudication_result.py",
        "tools/build_stage_a_adjudication_result.py",
        "tools/validate_stage_a_adjudication_result.py",
        "tests/test_stage_a_adjudication_result.py",
    )
    for relative in files:
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"source bundle file is missing: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def build_adjudication_result(
    *,
    intake_root: Path,
    reviewer_3_root: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    intake_root = intake_root.resolve(strict=True)
    intake_errors = validate_canonical_intake_projection(intake_root)
    if intake_errors:
        raise ValueError("canonical intake validation failed: " + "; ".join(intake_errors))
    intake_manifest = strict_json_object(intake_root / "manifest.json")
    intake_report = strict_json_object(intake_root / "comparison_report.json")
    comparison = intake_report["comparison"]
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        validated, inventory = _capture_and_validate_results(
            intake_root=intake_root,
            reviewer_3_root=reviewer_3_root,
            staging=staging,
        )
        records = _build_result_records(validated)
        summary = _summarize(records, comparison)
        write_json(staging / "input_inventory.json", inventory)
        write_jsonl(staging / "adjudicated_stage_a_24.jsonl", records)
        r0_source = intake_root / "r0_repair_queue_4.jsonl"
        r0_records = strict_jsonl(r0_source)
        if len(r0_records) != 4:
            raise ValueError("canonical R0 repair queue count mismatch")
        pending_path = staging / "pending" / "r0_repair_queue_4.jsonl"
        pending_path.parent.mkdir(parents=True)
        shutil.copyfile(r0_source, pending_path)
        report = seal_integrity(
            {
                "schema_id": "D2LFastTrackStageAAdjudicationResultReportV1",
                "schema_version": "1.0.0",
                "artifact_name": ARTIFACT_NAME,
                "policy_id": POLICY_ID,
                "status": STATUS,
                "created_at": created_at,
                "canonical_intake_manifest_sha256": intake_manifest[
                    "manifest_sha256"
                ],
                "canonical_intake_manifest_physical_sha256": sha256_file(
                    intake_root / "manifest.json"
                ),
                "canonical_r0_repair_queue_sha256": sha256_file(r0_source),
                "summary": summary,
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            }
        )
        write_json(staging / "adjudication_report.json", report)
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L Fast-Track Stage A adjudication result\n\n"
            "- 9/9 Reviewer 3 files captured and validated against their sealed inputs.\n"
            "- 24/24 routed cases completed; all are ready for contract construction.\n"
            "- 6 candidate sets accepted; 18 revised with 26 candidate-bound replacements.\n"
            "- 40/44 new senses are ready when combined with prior R0/R3 routes.\n"
            "- 4 R0 senses remain in dataset repair and re-audit.\n"
            "- No Stage B gold, provider call, or final glossary decision was created.\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LFastTrackStageAAdjudicationResultManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "status": STATUS,
            "created_at": created_at,
            "canonical_intake_manifest_sha256": intake_manifest["manifest_sha256"],
            "reviewer_3_result_file_count": 9,
            "adjudicated_case_count": 24,
            "ready_for_contract_construction_count": 24,
            "candidate_set_accept_count": 6,
            "candidate_set_revise_count": 18,
            "candidate_replacement_count": 26,
            "r0_repair_queue_count": 4,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        try:
            from .validate_stage_a_adjudication_result import validate_result
        except ImportError:  # pragma: no cover
            from validate_stage_a_adjudication_result import validate_result  # type: ignore
        errors = validate_result(staging, intake_root=intake_root)
        if errors:
            raise ValueError("internal adjudication validation failed: " + "; ".join(errors))
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
            "summary": summary,
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    namespace = Path(__file__).resolve().parents[1]
    intake_default = namespace / "release" / "d2l_fast_track_stage_a_review_intake_v1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake-root", type=Path, default=intake_default)
    parser.add_argument(
        "--reviewer-3-root",
        type=Path,
        default=intake_default / "handoff" / "result-reviewer3",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default=CREATED_AT_DEFAULT)
    args = parser.parse_args()
    result = build_adjudication_result(
        intake_root=args.intake_root,
        reviewer_3_root=args.reviewer_3_root,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
