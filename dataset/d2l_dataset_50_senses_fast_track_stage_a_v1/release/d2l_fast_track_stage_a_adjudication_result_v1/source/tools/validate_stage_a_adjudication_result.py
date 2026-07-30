from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

try:
    from .adjudication_result import validate_completed_adjudication
    from .build_stage_a_adjudication_result import (
        ARTIFACT_NAME,
        EXPECTED_BATCH_CASE_COUNTS,
        POLICY_ID,
        STATUS,
        _manifest_self_hash,
        load_canonical_adjudicator_input,
        validate_canonical_intake_projection,
    )
    from .common import (
        build_file_inventory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from .validate_stage_a_review_intake import validate_intake
except ImportError:  # pragma: no cover - direct script execution
    from adjudication_result import validate_completed_adjudication  # type: ignore
    from build_stage_a_adjudication_result import (  # type: ignore
        ARTIFACT_NAME,
        EXPECTED_BATCH_CASE_COUNTS,
        POLICY_ID,
        STATUS,
        _manifest_self_hash,
        load_canonical_adjudicator_input,
        validate_canonical_intake_projection,
    )
    from common import (  # type: ignore
        build_file_inventory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from validate_stage_a_review_intake import validate_intake  # type: ignore


def _validate_manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"manifest: {exc}")
        return {}
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("manifest artifact name mismatch")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("manifest policy mismatch")
    if manifest.get("status") != STATUS:
        errors.append("manifest status mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self hash mismatch")
    if manifest.get("files") != build_file_inventory(
        root, {"manifest.json", "CHECKSUMS.sha256"}
    ):
        errors.append("manifest file inventory mismatch")
    expected_counts = {
        "reviewer_3_result_file_count": 9,
        "adjudicated_case_count": 24,
        "ready_for_contract_construction_count": 24,
        "candidate_set_accept_count": 6,
        "candidate_set_revise_count": 18,
        "candidate_replacement_count": 26,
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
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"checksums: {exc}")
        return
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(root, {"CHECKSUMS.sha256"}).items()
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


def _validate_inputs(
    root: Path,
    intake_root: Path,
    inventory: Mapping[str, Any],
    errors: list[str],
) -> dict[str, tuple[Mapping[str, Any], str, str]]:
    indexed: dict[str, tuple[Mapping[str, Any], str, str]] = {}
    if not verify_integrity(inventory):
        errors.append("input inventory self hash mismatch")
    if inventory.get("result_file_count") != 9 or inventory.get("case_count") != 24:
        errors.append("input inventory count mismatch")
    rows = inventory.get("files")
    if not isinstance(rows, list) or len(rows) != 9:
        errors.append("input inventory file rows mismatch")
        return indexed
    seen: set[str] = set()
    total = 0
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append("input inventory row is invalid")
            continue
        batch_id = str(row.get("batch_id"))
        if batch_id in seen or batch_id not in EXPECTED_BATCH_CASE_COUNTS:
            errors.append(f"duplicate or unknown batch binding: {batch_id}")
            continue
        seen.add(batch_id)
        captured = root / str(row.get("captured_relative_path"))
        try:
            captured_sha = sha256_file(captured)
            canonical, zip_sha, input_physical_sha = load_canonical_adjudicator_input(
                intake_root, batch_id
            )
        except (OSError, ValueError) as exc:
            errors.append(f"input {batch_id}: {exc}")
            continue
        if captured_sha != row.get("captured_sha256") or captured_sha != row.get(
            "source_sha256"
        ):
            errors.append(f"captured Reviewer 3 hash mismatch: {batch_id}")
        if zip_sha != row.get("canonical_handoff_zip_sha256"):
            errors.append(f"canonical handoff ZIP binding mismatch: {batch_id}")
        if input_physical_sha != row.get("canonical_input_physical_sha256"):
            errors.append(f"canonical input physical binding mismatch: {batch_id}")
        if canonical.get("source_input_sha256") != row.get("source_input_sha256"):
            errors.append(f"canonical input semantic binding mismatch: {batch_id}")
        validated, validation_errors, metrics = validate_completed_adjudication(
            canonical,
            captured,
            expected_batch_id=batch_id,
        )
        errors.extend(
            f"captured Reviewer 3 {batch_id}: {message}"
            for message in validation_errors
        )
        if validated is None:
            continue
        if metrics.get("case_count") != EXPECTED_BATCH_CASE_COUNTS[batch_id]:
            errors.append(f"captured Reviewer 3 case count mismatch: {batch_id}")
        total += metrics.get("case_count", 0)
        for case in validated.payload["cases"]:
            case_id = case["adjudication_case_id"]
            if case_id in indexed:
                errors.append(f"duplicate adjudication case ID: {case_id}")
            indexed[case_id] = (case, validated.sha256, validated.payload["source_input_sha256"])
    if seen != set(EXPECTED_BATCH_CASE_COUNTS) or total != 24:
        errors.append("captured Reviewer 3 batch/case coverage mismatch")
    return indexed


def _validate_records(
    root: Path,
    indexed: Mapping[str, tuple[Mapping[str, Any], str, str]],
    errors: list[str],
) -> dict[str, Any]:
    try:
        records = strict_jsonl(root / "adjudicated_stage_a_24.jsonl")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"adjudication records: {exc}")
        return {}
    if len(records) != 24 or len({row.get("sense_id") for row in records}) != 24:
        errors.append("adjudication records must contain 24 unique senses")
    candidate_decisions = Counter()
    sense_statuses = Counter()
    risks = Counter()
    routes = Counter()
    replacement_count = 0
    for row in records:
        sense_id = row.get("sense_id")
        if not verify_record(row, "adjudication_result_sha256"):
            errors.append(f"adjudication result self hash mismatch: {sense_id}")
        case_id = row.get("source_adjudication_case_id")
        binding = indexed.get(str(case_id))
        if binding is None:
            errors.append(f"adjudication result has unknown source case: {sense_id}")
            continue
        case, result_file_sha, source_input_sha = binding
        expected_bindings = {
            "batch_id": case["batch_id"],
            "sense_id": case["sense_id"],
            "source_term": case["source_term"],
            "risk_class": case["risk_class"],
            "routing_reason": case["routing_reason"],
            "source_adjudication_case_sha256": case["adjudication_case_sha256"],
            "source_input_sha256": source_input_sha,
            "source_payload": case["source_payload"],
            "source_payload_sha256": case["source_payload_sha256"],
            "reviewer_1": case["reviewer_1"],
            "reviewer_2": case["reviewer_2"],
            "reviewer_3_result_file_sha256": result_file_sha,
            "adjudication": case["adjudication"],
        }
        for field, expected in expected_bindings.items():
            if row.get(field) != expected:
                errors.append(f"adjudication result binding mismatch: {sense_id}/{field}")
        adjudication = case["adjudication"]
        replacements = adjudication["candidate_replacements"]
        if row.get("candidate_replacement_count") != len(replacements):
            errors.append(f"candidate replacement count mismatch: {sense_id}")
        if row.get("status") != adjudication["sense_status"]:
            errors.append(f"adjudication status projection mismatch: {sense_id}")
        if row.get("provider_call_count") != 0 or row.get(
            "stage_b_gold_label"
        ) is not None or row.get("final_glossary_decision") is not None:
            errors.append(f"adjudication result boundary violation: {sense_id}")
        candidate_decisions[adjudication["candidate_set_decision"]] += 1
        sense_statuses[adjudication["sense_status"]] += 1
        risks[case["risk_class"]] += 1
        routes[case["routing_reason"]] += 1
        replacement_count += len(replacements)
    summary = {
        "adjudicated_case_count": len(records),
        "ready_for_contract_construction_count": sense_statuses[
            "READY_FOR_CONTRACT_CONSTRUCTION"
        ],
        "candidate_set_decision_counts": dict(sorted(candidate_decisions.items())),
        "candidate_replacement_count": replacement_count,
        "risk_counts": dict(sorted(risks.items())),
        "routing_counts": dict(sorted(routes.items())),
    }
    expected = {
        "adjudicated_case_count": 24,
        "ready_for_contract_construction_count": 24,
        "candidate_set_decision_counts": {"ACCEPT": 6, "REVISE": 18},
        "candidate_replacement_count": 26,
        "risk_counts": {"R3_AMBIGUOUS": 8, "R4_SPLIT_OR_POS_RISK": 16},
        "routing_counts": {
            "R3_REVIEWER_DISAGREEMENT": 8,
            "R4_MANDATORY_ADJUDICATION": 16,
        },
    }
    if summary != expected:
        errors.append(f"adjudication record summary mismatch: {summary}")
    return summary


def _validate_pending_queue(root: Path, intake_root: Path, errors: list[str]) -> None:
    source = intake_root / "r0_repair_queue_4.jsonl"
    captured = root / "pending" / "r0_repair_queue_4.jsonl"
    try:
        if sha256_file(source) != sha256_file(captured):
            errors.append("R0 repair queue is not byte-identical to canonical intake")
        rows = strict_jsonl(captured)
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"R0 repair queue: {exc}")
        return
    if len(rows) != 4 or len({row.get("sense_id") for row in rows}) != 4:
        errors.append("R0 repair queue must contain four unique senses")
    for row in rows:
        if not verify_record(row, "repair_queue_record_sha256"):
            errors.append(f"R0 repair self hash mismatch: {row.get('sense_id')}")


def _validate_report(
    report: Mapping[str, Any], record_summary: Mapping[str, Any], errors: list[str]
) -> None:
    if not verify_integrity(report):
        errors.append("adjudication report self hash mismatch")
    if report.get("artifact_name") != ARTIFACT_NAME or report.get("policy_id") != POLICY_ID:
        errors.append("adjudication report identity mismatch")
    if report.get("status") != STATUS:
        errors.append("adjudication report status mismatch")
    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        errors.append("adjudication report summary is invalid")
        return
    for field in (
        "adjudicated_case_count",
        "ready_for_contract_construction_count",
        "candidate_replacement_count",
        "risk_counts",
        "routing_counts",
    ):
        if summary.get(field) != record_summary.get(field):
            errors.append(f"adjudication report record mismatch: {field}")
    if summary.get("decision_counts", {}).get("candidate_set_decision") != {
        "ACCEPT": 6,
        "REVISE": 18,
    }:
        errors.append("adjudication report candidate-set counts mismatch")
    if summary.get("stage_a_new_sense_funnel") != {
        "new_sense_count": 44,
        "r0_ready_without_adjudication": 9,
        "r3_ready_by_two_reviewer_agreement": 7,
        "ready_after_reviewer_3_adjudication": 24,
        "ready_for_contract_construction_total": 40,
        "r0_repair_and_reaudit_pending": 4,
    }:
        errors.append("adjudication report new-sense funnel mismatch")
    if summary.get("pool_funnel") != {
        "inherited_reviewed_senses": 16,
        "new_ready_senses": 40,
        "pending_r0_senses": 4,
        "pool_sense_count": 60,
    }:
        errors.append("adjudication report pool funnel mismatch")
    if report.get("provider_call_count") != 0 or report.get(
        "stage_b_gold_autofill_count"
    ) != 0 or report.get("final_glossary_decision") is not None:
        errors.append("adjudication report boundary violation")


def validate_result(root: Path, *, intake_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        return [f"artifact root: {exc}"]
    if intake_root is None:
        namespace = Path(__file__).resolve().parents[1]
        intake_root = namespace / "release" / "d2l_fast_track_stage_a_review_intake_v1"
    intake_root = intake_root.resolve(strict=True)
    intake_errors = validate_canonical_intake_projection(intake_root)
    errors.extend(f"canonical intake: {message}" for message in intake_errors)
    manifest = _validate_manifest(root, errors)
    _validate_checksums(root, errors)
    try:
        inventory = strict_json_object(root / "input_inventory.json")
        report = strict_json_object(root / "adjudication_report.json")
        intake_manifest = strict_json_object(intake_root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"adjudication metadata: {exc}")
        return errors
    if manifest.get("canonical_intake_manifest_sha256") != intake_manifest.get(
        "manifest_sha256"
    ):
        errors.append("manifest canonical intake binding mismatch")
    if report.get("canonical_intake_manifest_sha256") != intake_manifest.get(
        "manifest_sha256"
    ) or report.get("canonical_intake_manifest_physical_sha256") != sha256_file(
        intake_root / "manifest.json"
    ):
        errors.append("report canonical intake binding mismatch")
    indexed = _validate_inputs(root, intake_root, inventory, errors)
    record_summary = _validate_records(root, indexed, errors)
    _validate_pending_queue(root, intake_root, errors)
    _validate_report(report, record_summary, errors)
    required = {
        "source/.gitattributes",
        "source/README.md",
        "source/tools/common.py",
        "source/tools/spec.py",
        "source/tools/adjudication_result.py",
        "source/tools/build_stage_a_adjudication_result.py",
        "source/tools/validate_stage_a_adjudication_result.py",
        "source/tests/test_stage_a_adjudication_result.py",
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
    parser.add_argument("--intake-root", type=Path)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_result(args.artifact_root, intake_root=args.intake_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root))
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
