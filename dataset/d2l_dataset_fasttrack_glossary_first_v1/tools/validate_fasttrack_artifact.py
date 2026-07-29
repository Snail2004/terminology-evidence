from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.artifact import ARTIFACT_NAME, POLICY_ID
    from tools.common import (
        build_file_inventory,
        canonical_json_bytes,
        read_json,
        read_jsonl,
        sha256_bytes,
        sha256_file,
        verify_record,
    )
    from tools.glossary import MATCH_STATUSES
    from tools.grounding import RISK_CLASSES, real_positive_context
else:
    from .artifact import ARTIFACT_NAME, POLICY_ID
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        read_json,
        read_jsonl,
        sha256_bytes,
        sha256_file,
        verify_record,
    )
    from .glossary import MATCH_STATUSES
    from .grounding import RISK_CLASSES, real_positive_context


REQUIRED_FILES = {
    "acceptance_gate_report.json",
    "candidate_generation_receipt.json",
    "candidate_provenance_450.jsonl",
    "CHECKSUMS.sha256",
    "controlled_vietnamese_source_registry.json",
    "d2l_vi_glossary_authority_receipt.json",
    "d2l_vi_glossary_snapshot/LICENSE",
    "d2l_vi_glossary_snapshot/LICENSE-SUMMARY",
    "d2l_vi_glossary_snapshot/glossary.md",
    "dataset_fasttrack_policy_v1_0.md",
    "effective_sense_contracts/official_effective_sense_contracts.jsonl",
    "effective_sense_contracts/pending_effective_sense_projection.jsonl",
    "glossary_mapping_150_senses.csv",
    "manifest.json",
    "pilot_15_readiness_report.json",
    "quarantined_cross_split_source_blocks.jsonl",
    "sense_risk_classification.csv",
    "source_bindings.json",
    "split_cluster_repair_report.json",
    "stage_a_adjudication_001_004.jsonl",
    "stage_a_blind_audit_pack.zip",
    "stage_a_blind_audit_result.zip",
    "stage_a_blind_audit_results.csv",
    "stage_a_source_grounding_report.json",
    "stage_b_annotation_template_450.csv",
    "stage_b_review_instructions.md",
    "stage_b_review_schema.json",
}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _verify_checksums(root: Path, errors: list[str]) -> None:
    checksums = root / "CHECKSUMS.sha256"
    expected: dict[str, str] = {}
    for line in checksums.read_text(encoding="ascii").splitlines():
        digest, relative = line.split(" *", 1)
        expected[relative] = digest
    actual = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(root, {"CHECKSUMS.sha256"}).items()
    }
    if expected != actual:
        errors.append("CHECKSUMS.sha256 does not match physical files")


def _verify_mapping_hash(row: dict[str, str]) -> bool:
    payload: dict[str, Any] = dict(row)
    claimed = payload.pop("mapping_sha256")
    payload["glossary_candidate_vi"] = payload["glossary_candidate_vi"] or None
    payload["glossary_entry_sha256"] = payload["glossary_entry_sha256"] or None
    payload["glossary_qualifier"] = payload["glossary_qualifier"] or None
    payload["glossary_source_entry"] = payload["glossary_source_entry"] or None
    payload["glossary_source_line"] = int(payload["glossary_source_line"]) if payload["glossary_source_line"] else None
    payload["matched_entry_count"] = int(payload["matched_entry_count"])
    return claimed == sha256_bytes(canonical_json_bytes(payload))


def _verify_risk_hash(row: dict[str, str]) -> bool:
    payload: dict[str, Any] = dict(row)
    claimed = payload.pop("risk_record_sha256")
    payload["active_real_positive_context_count"] = int(payload["active_real_positive_context_count"])
    return claimed == sha256_bytes(canonical_json_bytes(payload))


def validate_artifact(root: Path, repo_root: Path) -> dict[str, Any]:
    root = root.resolve()
    repo_root = repo_root.resolve()
    errors: list[str] = []

    physical_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    missing = sorted(REQUIRED_FILES - physical_files)
    if missing:
        errors.append(f"missing required files: {missing}")

    manifest = read_json(root / "manifest.json")
    if manifest.get("artifact_name") != ARTIFACT_NAME or manifest.get("policy_id") != POLICY_ID:
        errors.append("manifest identity mismatch")
    claimed_manifest = manifest.get("manifest_sha256")
    manifest_payload = dict(manifest)
    manifest_payload.pop("manifest_sha256", None)
    if claimed_manifest != sha256_bytes(canonical_json_bytes(manifest_payload)):
        errors.append("manifest self hash mismatch")
    actual_manifest_files = build_file_inventory(root, {"manifest.json", "CHECKSUMS.sha256"})
    if manifest.get("files") != actual_manifest_files:
        errors.append("manifest file inventory mismatch")
    _verify_checksums(root, errors)

    receipt = read_json(root / "d2l_vi_glossary_authority_receipt.json")
    if not verify_record(receipt, "receipt_sha256"):
        errors.append("glossary receipt self hash mismatch")
    snapshot = root / "d2l_vi_glossary_snapshot"
    if receipt.get("physical_sha256") != sha256_file(snapshot / "glossary.md"):
        errors.append("glossary snapshot hash mismatch")
    if receipt.get("license_sha256") != sha256_file(snapshot / "LICENSE"):
        errors.append("glossary license hash mismatch")
    if receipt.get("license_summary_sha256") != sha256_file(snapshot / "LICENSE-SUMMARY"):
        errors.append("glossary license summary hash mismatch")
    if receipt.get("auto_approval_permitted") is not False:
        errors.append("D2L-VI glossary must not auto-approve")

    mappings = _csv_rows(root / "glossary_mapping_150_senses.csv")
    risks = _csv_rows(root / "sense_risk_classification.csv")
    if len(mappings) != 150 or len({row["sense_id"] for row in mappings}) != 150:
        errors.append("mapping cardinality mismatch")
    if any(row["glossary_match_status"] not in MATCH_STATUSES for row in mappings):
        errors.append("invalid glossary match status")
    if any(not _verify_mapping_hash(row) for row in mappings):
        errors.append("mapping record hash mismatch")
    if len(risks) != 150 or len({row["sense_id"] for row in risks}) != 150:
        errors.append("risk cardinality mismatch")
    if any(row["risk_class"] not in RISK_CLASSES for row in risks):
        errors.append("invalid risk class")
    if any(not _verify_risk_hash(row) for row in risks):
        errors.append("risk record hash mismatch")

    projections = read_jsonl(root / "effective_sense_contracts" / "pending_effective_sense_projection.jsonl")
    official_path = root / "effective_sense_contracts" / "official_effective_sense_contracts.jsonl"
    if len(projections) != 150 or len({row["sense_id"] for row in projections}) != 150:
        errors.append("pending projection cardinality mismatch")
    if any(not verify_record(row, "effective_sense_projection_sha256") for row in projections):
        errors.append("pending projection self hash mismatch")
    if any(row.get("review_status") != "UNRESOLVED" for row in projections):
        errors.append("unreviewed projection was finalized")
    if any(row.get("official_effective_sense_contract_emitted") is not False for row in projections):
        errors.append("official effective sense contract was falsely emitted")
    if official_path.read_bytes():
        errors.append("official effective sense contract file must remain empty")

    v3_root = repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3"
    contexts = {row["context_id"]: row for row in read_jsonl(v3_root / "contexts.jsonl")}
    quarantined = read_jsonl(root / "quarantined_cross_split_source_blocks.jsonl")
    quarantined_blocks = {row["block_id"] for row in quarantined}
    if len(quarantined) != 45 or len(quarantined_blocks) != 45:
        errors.append("quarantine cardinality mismatch")
    for projection in projections:
        positive_ids = list(dict.fromkeys(
            projection["positive_definition_evidence_ids"] + projection["positive_pos_evidence_ids"]
        ))
        if not positive_ids:
            errors.append(f"{projection['sense_id']}: no active positive evidence")
            continue
        for context_id in positive_ids:
            context = contexts.get(context_id)
            if not context or not real_positive_context(context):
                errors.append(f"{projection['sense_id']}: invalid positive context {context_id}")
                continue
            if context["provenance"]["block_id"] in quarantined_blocks:
                errors.append(f"{projection['sense_id']}: quarantined block used as positive evidence")

    candidates = read_jsonl(root / "candidate_provenance_450.jsonl")
    if len(candidates) != 450 or len({row["candidate_id"] for row in candidates}) != 450:
        errors.append("candidate cardinality mismatch")
    if any(not verify_record(row, "candidate_provenance_sha256") for row in candidates):
        errors.append("candidate provenance self hash mismatch")
    roles: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        roles[candidate["sense_id"]].append(candidate["candidate_role"])
        if candidate.get("candidate_gold_label") is not None:
            errors.append("candidate gold label was prefilled")
    if len(roles) != 150 or any(sorted(value) != ["A", "B", "C"] for value in roles.values()):
        errors.append("candidate A/B/C role invariant failed")

    stage_b = _csv_rows(root / "stage_b_annotation_template_450.csv")
    if len(stage_b) != 450:
        errors.append("Stage B template cardinality mismatch")
    human_fields = [
        "candidate_gold_label",
        "allowed_scope",
        "validated_variants",
        "rejected_variants",
        "reason_codes",
        "vietnamese_evidence_refs",
        "reviewer_provenance_ref",
        "adjudication_ref",
    ]
    if any(row[field].strip() for row in stage_b for field in human_fields):
        errors.append("Stage B human field is not blank")

    blind_rows = _csv_rows(root / "stage_a_blind_audit_results.csv")
    if len(blind_rows) != 13:
        errors.append("blind audit result cardinality mismatch")
    adjudication = read_jsonl(root / "stage_a_adjudication_001_004.jsonl")
    if {row["source_term"] for row in adjudication} != {"adam", "fully-connected layers", "in place", "contexts"}:
        errors.append("adjudication closure set mismatch")
    if any(not verify_record(row) for row in adjudication):
        errors.append("adjudication record self hash mismatch")

    pilot = read_json(root / "pilot_15_readiness_report.json")
    if pilot.get("selected_sense_count") != 15:
        errors.append("pilot selection must contain 15 senses")
    if pilot.get("official_frozen_candidate_contract_count") != 0:
        errors.append("pilot Frozen Candidate count must remain zero")
    if pilot.get("complete_constraint_evidence_package_count") != 0:
        errors.append("pilot COMPLETE Constraint Evidence count must remain zero")
    acceptance = read_json(root / "acceptance_gate_report.json")
    if acceptance.get("status") != "BLOCKED_BEFORE_REAL_CE_PILOT":
        errors.append("acceptance gate must remain blocked")
    if acceptance.get("final_glossary_decision") is not None:
        errors.append("dataset artifact must not make final glossary decision")

    report = {
        "schema_id": "D2LFastTrackArtifactValidationReportV1",
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
        "counts": {
            "sense": len(projections),
            "candidate": len(candidates),
            "stage_b_rows": len(stage_b),
            "blind_case": len(blind_rows),
            "quarantined_cross_split_cluster": len(quarantined),
            "mapping_status": dict(sorted(Counter(row["glossary_match_status"] for row in mappings).items())),
            "risk_class": dict(sorted(Counter(row["risk_class"] for row in risks).items())),
        },
        "manifest_sha256": claimed_manifest,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_artifact(args.artifact_root, args.repo_root)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
