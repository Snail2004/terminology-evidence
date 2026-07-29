from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.common import (
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        read_json,
        read_jsonl,
        sha256_bytes,
        sha256_file,
        verify_record,
    )
    from tools.review_contract import (
        SOURCE_DATASET_FILES,
        SOURCE_MANIFEST_FILE_SHA256,
        SOURCE_MANIFEST_SHA256,
    )
else:
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        read_json,
        read_jsonl,
        sha256_bytes,
        sha256_file,
        verify_record,
    )
    from .review_contract import (
        SOURCE_DATASET_FILES,
        SOURCE_MANIFEST_FILE_SHA256,
        SOURCE_MANIFEST_SHA256,
    )


def _checksum_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split(" *", 1)
        result[relative] = digest
    return result


def _safe_zip_name(name: str) -> bool:
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _check_zip(artifact: Path, zip_path: Path, errors: list[str]) -> None:
    if not zip_path.is_file():
        errors.append("reviewer handoff ZIP is missing")
        return
    expected = {
        relative: (artifact / relative).read_bytes()
        for relative in build_file_inventory(artifact, set())
    }
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            if any(not _safe_zip_name(name) for name in names):
                errors.append("ZIP contains unsafe path")
            if set(names) != set(expected):
                errors.append("ZIP file set differs from artifact")
            for name, content in expected.items():
                if name in names and archive.read(name) != content:
                    errors.append(f"ZIP content mismatch: {name}")
    except zipfile.BadZipFile:
        errors.append("reviewer handoff ZIP is invalid")


def validate_artifact(artifact_root: Path, zip_path: Path | None = None) -> dict[str, Any]:
    artifact_root = artifact_root.resolve(strict=True)
    errors: list[str] = []
    required = [
        "manifest.json", "CHECKSUMS.sha256", "REVIEW_REPORT.md",
        "merged_review_decisions_15.jsonl", "effective_sense_contract_candidates_11.jsonl",
        "pending_resolution_4.jsonl", "review_provenance_15_senses.jsonl",
        "stage_a_adjudication_15_senses.jsonl", "stage_a_review_results_15_senses.csv",
        "stage_a_blind_audit_results_3.csv", "stage_b_annotation_template_45.csv",
        "stage_a_pilot_15_summary.json", "stage_a_pilot_15_acceptance_gate_report.json",
        "lineage.json", "source_dataset/manifest.json", "review_inputs/reviewer_1.csv",
        "review_inputs/reviewer_2.csv", "review_inputs/reviewer_2_blind_audit.csv",
        "review_inputs/adjudicator.csv", "source/tools/build_reviewed_pilot.py",
        "source/tools/validate_reviewed_pilot.py", "source/tools/review_contract.py",
        "source/tests/test_reviewed_pilot.py",
    ]
    for relative in required:
        if not (artifact_root / relative).is_file():
            errors.append(f"missing required file: {relative}")

    manifest: dict[str, Any] = {}
    if not errors[:]:
        manifest = read_json(artifact_root / "manifest.json")
        if manifest.get("manifest_sha256") != sha256_bytes(canonical_json_bytes({key: value for key, value in manifest.items() if key != "manifest_sha256"})):
            errors.append("manifest self hash mismatch")
        for relative, binding in manifest.get("files", {}).items():
            path = artifact_root / relative
            if not path.is_file():
                errors.append(f"manifest-bound file missing: {relative}")
            elif sha256_file(path) != binding.get("sha256") or path.stat().st_size != binding.get("size_bytes"):
                errors.append(f"manifest-bound file mismatch: {relative}")
        checksums = _checksum_map(artifact_root / "CHECKSUMS.sha256")
        actual = {
            relative: metadata["sha256"]
            for relative, metadata in build_file_inventory(artifact_root, set()).items()
            if relative != "CHECKSUMS.sha256"
        }
        if checksums != actual:
            errors.append("CHECKSUMS.sha256 does not bind the complete artifact")

    source_manifest_path = artifact_root / "source_dataset/manifest.json"
    if source_manifest_path.is_file():
        source_manifest = read_json(source_manifest_path)
        if source_manifest.get("manifest_sha256") != SOURCE_MANIFEST_SHA256:
            errors.append("embedded P0 manifest self hash mismatch")
        if sha256_file(source_manifest_path) != SOURCE_MANIFEST_FILE_SHA256:
            errors.append("embedded P0 manifest physical hash mismatch")
        for relative in SOURCE_DATASET_FILES:
            path = artifact_root / "source_dataset" / relative
            if not path.is_file():
                errors.append(f"embedded P0 file missing: {relative}")
            elif relative not in {"manifest.json", "CHECKSUMS.sha256"}:
                binding = source_manifest.get("files", {}).get(relative, {})
                if sha256_file(path) != binding.get("sha256"):
                    errors.append(f"embedded P0 file mismatch: {relative}")

    decisions = read_jsonl(artifact_root / "merged_review_decisions_15.jsonl") if (artifact_root / "merged_review_decisions_15.jsonl").is_file() else []
    if len(decisions) != 15 or len({row.get("sense_id") for row in decisions}) != 15:
        errors.append("merged decision count/identity mismatch")
    for row in decisions:
        if not verify_record(row, "review_record_sha256"):
            errors.append(f"merged decision self hash mismatch: {row.get('source_term')}")
        if row.get("final_glossary_decision") is not None:
            errors.append("merged decision contains final glossary decision")
    statuses = {row.get("resolution_status") for row in decisions}
    if statuses and not statuses <= {"READY_FOR_CONTRACT_CONSTRUCTION", "REVISION_REQUIRED", "SPLIT_REQUIRED", "UNRESOLVED"}:
        errors.append("invalid resolution status")
    if sum(row.get("resolution_status") == "READY_FOR_CONTRACT_CONSTRUCTION" for row in decisions) != 11:
        errors.append("expected 11 ready resolutions")
    if sum(row.get("resolution_status") != "READY_FOR_CONTRACT_CONSTRUCTION" for row in decisions) != 4:
        errors.append("expected four pending resolutions")

    effective = read_jsonl(artifact_root / "effective_sense_contract_candidates_11.jsonl") if (artifact_root / "effective_sense_contract_candidates_11.jsonl").is_file() else []
    pending = read_jsonl(artifact_root / "pending_resolution_4.jsonl") if (artifact_root / "pending_resolution_4.jsonl").is_file() else []
    if len(effective) != 11 or len(pending) != 4:
        errors.append("effective/pending projection cardinality mismatch")
    for row in effective:
        if not verify_record(row, "candidate_record_sha256") or row.get("official_contract_emitted") is not False or row.get("final_glossary_decision") is not None:
            errors.append(f"invalid effective candidate: {row.get('source_term')}")
    for row in pending:
        if not verify_record(row, "pending_record_sha256") or row.get("official_contract_emitted") is not False or row.get("final_glossary_decision") is not None:
            errors.append(f"invalid pending record: {row.get('source_term')}")

    provenance = read_jsonl(artifact_root / "review_provenance_15_senses.jsonl") if (artifact_root / "review_provenance_15_senses.jsonl").is_file() else []
    if len(provenance) != 25:
        errors.append("expected 25 reviewer provenance records")
    for row in provenance:
        if not verify_record(row, "review_provenance_sha256") or row.get("reviewer_type") != "HUMAN" or row.get("human_authority_present") is not True:
            errors.append("invalid reviewer provenance record")
    reviewer_ids = {row.get("reviewer_id") for row in provenance}
    if not {"diemphuong", "reviewer_2"} <= reviewer_ids:
        errors.append("reviewer provenance identities missing")

    adjudications = read_jsonl(artifact_root / "stage_a_adjudication_15_senses.jsonl") if (artifact_root / "stage_a_adjudication_15_senses.jsonl").is_file() else []
    if len(adjudications) != 4:
        errors.append("expected four adjudication records")
    for row in adjudications:
        if not verify_record(row, "adjudication_sha256") or row.get("adjudicator_id") != "snail" or row.get("human_authority_present") is not True:
            errors.append("invalid adjudication record")

    merged_csv = read_csv(artifact_root / "stage_a_review_results_15_senses.csv") if (artifact_root / "stage_a_review_results_15_senses.csv").is_file() else []
    if len(merged_csv) != 15:
        errors.append("merged CSV row count mismatch")
    blind_csv = read_csv(artifact_root / "stage_a_blind_audit_results_3.csv") if (artifact_root / "stage_a_blind_audit_results_3.csv").is_file() else []
    if len(blind_csv) != 3 or any(row.get("review_status") != "COMPLETE" for row in blind_csv):
        errors.append("blind audit result mismatch")
    stage_b = read_csv(artifact_root / "stage_b_annotation_template_45.csv") if (artifact_root / "stage_b_annotation_template_45.csv").is_file() else []
    if len(stage_b) != 45:
        errors.append("Stage B row count mismatch")
    for row in stage_b:
        if any(row.get(field, "") for field in (
            "candidate_gold_label", "allowed_scope", "validated_variants",
            "rejected_variants", "reason_codes", "vietnamese_evidence_refs",
            "reviewer_provenance_ref", "adjudication_ref",
        )):
            errors.append("Stage B contains an automatic gold or evidence label")
            break

    summary = read_json(artifact_root / "stage_a_pilot_15_summary.json") if (artifact_root / "stage_a_pilot_15_summary.json").is_file() else {}
    gate = read_json(artifact_root / "stage_a_pilot_15_acceptance_gate_report.json") if (artifact_root / "stage_a_pilot_15_acceptance_gate_report.json").is_file() else {}
    if summary.get("status") != "REVIEW_MERGED_PARTIAL_RESOLUTION" or gate.get("structural_status") != "PASS" or gate.get("review_status") != "COMPLETE":
        errors.append("summary/gate status mismatch")
    if manifest.get("final_glossary_decision") is not None or manifest.get("provider_call_count") != 0:
        errors.append("manifest final decision/provider binding mismatch")
    if manifest.get("status") != "REVIEW_MERGED_PARTIAL_RESOLUTION":
        errors.append("manifest status mismatch")

    if zip_path is not None:
        _check_zip(artifact_root, zip_path.resolve(), errors)
    report = {
        "status": "PASS" if not errors else "FAIL",
        "artifact_status": manifest.get("status"),
        "selected_sense_count": len(decisions),
        "ready_resolution_count": len(effective),
        "pending_resolution_count": len(pending),
        "review_provenance_count": len(provenance),
        "adjudication_count": len(adjudications),
        "blind_audit_count": len(blind_csv),
        "stage_b_open_row_count": len(stage_b),
        "error_count": len(errors),
        "errors": errors,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    report = validate_artifact(args.artifact_root, args.zip_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
