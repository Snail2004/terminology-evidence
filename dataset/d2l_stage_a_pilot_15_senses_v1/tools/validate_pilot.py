from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.build_pilot import (
        ARTIFACT_NAME,
        INTEGRATION_TERMS,
        POLICY_ID,
        SCHEMA_ID,
        SELECTION_SPECS,
        _binding,
        _git,
        _is_real_positive,
        _review_slots,
    )
    from tools.common import (
        build_file_inventory,
        canonical_json_bytes,
        read_json,
        read_jsonl,
        sha256_bytes,
        sha256_file,
        verify_record,
    )
else:
    from .build_pilot import (
        ARTIFACT_NAME,
        INTEGRATION_TERMS,
        POLICY_ID,
        SCHEMA_ID,
        SELECTION_SPECS,
        _binding,
        _git,
        _is_real_positive,
        _review_slots,
    )
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        read_json,
        read_jsonl,
        sha256_bytes,
        sha256_file,
        verify_record,
    )


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _check_checksums(root: Path, errors: list[str]) -> None:
    expected: dict[str, str] = {}
    for line in (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines():
        digest, relative = line.split(" *", 1)
        expected[relative] = digest
    actual = {key: value["sha256"] for key, value in build_file_inventory(root, {"CHECKSUMS.sha256"}).items()}
    if expected != actual:
        errors.append("CHECKSUMS.sha256 mismatch")


def _expected_parent_bindings(repo_root: Path) -> dict[str, Any]:
    v1_root = repo_root / "dataset" / "d2l_dataset_fasttrack_glossary_first_v1" / "release" / "d2l_dataset_fasttrack_glossary_first_v1"
    v11_root = repo_root / "dataset" / "d2l_dataset_fasttrack_glossary_first_v1_1" / "release" / "d2l_dataset_fasttrack_glossary_first_v1_1"
    # The parent V1 and the repair companion are both local, immutable inputs.
    return {
        "immutable_fasttrack_v1": _binding(v1_root, "d2l_dataset_fasttrack_glossary_first_v1", _git(repo_root, "log", "-1", "--format=%H", "--", "dataset/d2l_dataset_fasttrack_glossary_first_v1")),
        "repair_companion_v1_1": _binding(v11_root, "d2l_dataset_fasttrack_glossary_first_v1_1", _git(repo_root, "log", "-1", "--format=%H", "--", "dataset/d2l_dataset_fasttrack_glossary_first_v1_1")),
    }


def _check_pack(pack_zip: Path, expected_hash: str, errors: list[str]) -> None:
    if not pack_zip.is_file():
        errors.append("review pack ZIP is missing")
        return
    if sha256_file(pack_zip) != expected_hash:
        errors.append("review pack ZIP hash mismatch")
    try:
        with zipfile.ZipFile(pack_zip) as archive:
            names = set(archive.namelist())
            root_prefix = "stage_a_review_pack_15_senses/"
            if not any(name.startswith(root_prefix) for name in names):
                errors.append("review pack root prefix missing")
                return
            pack_manifest = json.loads(archive.read(root_prefix + "pack_manifest.json"))
            listed = pack_manifest.get("files") or {}
            actual: dict[str, dict[str, Any]] = {}
            for name in sorted(names):
                if not name.startswith(root_prefix) or name.endswith("/"):
                    continue
                relative = name[len(root_prefix):]
                if relative in {"pack_manifest.json", "CHECKSUMS.sha256"}:
                    continue
                payload = archive.read(name)
                actual[relative] = {"sha256": sha256_bytes(payload), "size_bytes": len(payload)}
            if listed != actual:
                errors.append("review pack manifest inventory mismatch")
            checksum_text = archive.read(root_prefix + "CHECKSUMS.sha256").decode("ascii")
            expected_checksums = {}
            for line in checksum_text.splitlines():
                digest, relative = line.split(" *", 1)
                expected_checksums[relative] = digest
            physical_checksums = {
                relative: metadata["sha256"]
                for relative, metadata in {**actual, "pack_manifest.json": {"sha256": sha256_bytes(archive.read(root_prefix + "pack_manifest.json"))}}.items()
            }
            if expected_checksums != physical_checksums:
                errors.append("review pack checksums mismatch")
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"review pack unreadable: {exc}")


def validate_pilot(artifact_root: Path, repo_root: Path) -> dict[str, Any]:
    root = artifact_root.resolve()
    errors: list[str] = []
    required = {
        "CHECKSUMS.sha256", "manifest.json", "pilot_15_sense_selection_receipt.json",
        "selected_senses_15.jsonl", "candidate_instances_45.jsonl", "contexts_selected.jsonl",
        "stage_a_review_results_15_senses.csv", "review_provenance_15_senses.jsonl",
        "stage_a_adjudication_15_senses.jsonl", "effective_sense_contracts_15/README.md",
        "stage_a_blind_audit_template_3.csv", "stage_a_review_instructions.md",
        "stage_a_pilot_15_acceptance_gate_report.json", "stage_a_pilot_15_summary.json",
        "integration_pilot_5_sense_selection_receipt.json", "integration_pilot_effective_sense_contracts_5/README.md",
        "integration_pilot_frozen_candidates_15/README.md", "integration_pilot_constraint_packages_15/README.md",
        "candidate_index_15.json", "pilot_release_receipt.json", "stage_b_annotation_template_45.csv",
        "lineage.json", "commands.txt", "environment.json", "ownership_scan.json", "credential_scan.json",
        "git_commit_receipt.json",
    }
    actual = set(build_file_inventory(root).keys())
    if not required <= actual:
        errors.append(f"required files missing: {sorted(required - actual)}")
    if any(path.endswith(".pyc") or "__pycache__" in path for path in actual):
        errors.append("release contains Python cache files")
    manifest = read_json(root / "manifest.json")
    payload = dict(manifest)
    claimed_manifest = payload.pop("manifest_sha256", None)
    if claimed_manifest != sha256_bytes(canonical_json_bytes(payload)):
        errors.append("manifest self hash mismatch")
    if manifest.get("schema_id") != SCHEMA_ID or manifest.get("artifact_name") != ARTIFACT_NAME or manifest.get("policy_id") != POLICY_ID:
        errors.append("manifest identity mismatch")
    if manifest.get("status") != "BLOCKED_BY_HUMAN_REVIEW":
        errors.append("manifest must remain blocked by human review")
    if manifest.get("files") != build_file_inventory(root, {"manifest.json", "CHECKSUMS.sha256"}):
        errors.append("manifest file inventory mismatch")
    _check_checksums(root, errors)

    expected_bindings = _expected_parent_bindings(repo_root)
    bindings = manifest.get("source_bindings") or {}
    for key, expected in expected_bindings.items():
        if bindings.get(key) != expected:
            errors.append(f"parent binding mismatch: {key}")
    if bindings.get("terminology_contracts", {}).get("authority_tag") != "contracts-v1.1.0":
        errors.append("terminology contract authority binding missing")

    v1_root = repo_root / "dataset" / "d2l_dataset_fasttrack_glossary_first_v1" / "release" / "d2l_dataset_fasttrack_glossary_first_v1"
    parent_projections = {row["sense_id"]: row for row in read_jsonl(v1_root / "effective_sense_contracts" / "pending_effective_sense_projection.jsonl")}
    parent_candidates = {row["candidate_id"]: row for row in read_jsonl(v1_root / "candidate_provenance_450.jsonl")}

    selected = read_jsonl(root / "selected_senses_15.jsonl")
    if len(selected) != 15 or len({row.get("sense_id") for row in selected}) != 15:
        errors.append("selected sense cardinality/uniqueness mismatch")
    group_counts = Counter(row.get("selection_group") for row in selected)
    if dict(group_counts) != {"CLEAR_LOW_RISK": 5, "AMBIGUOUS_POLYSEMOUS": 5, "GATE_ADJUDICATION_RISK": 5}:
        errors.append("selection group distribution mismatch")
    if any(row.get("split") != "development" for row in selected):
        errors.append("selection contains non-development sense")
    if any(not verify_record(row, "selected_sense_sha256") for row in selected):
        errors.append("selected sense self hash mismatch")
    for row in selected:
        spec = SELECTION_SPECS.get(row.get("source_term"))
        if not spec or row.get("selection_group") != spec["group"] or row.get("coverage_tags") != spec["tags"]:
            errors.append(f"selection policy mismatch: {row.get('source_term')}")
        parent = parent_projections.get(row.get("sense_id"))
        if not parent or row.get("parent_projection_sha256") != parent.get("effective_sense_projection_sha256") or row.get("source_payload_sha256") != parent.get("source_payload_sha256"):
            errors.append(f"selected sense parent projection binding mismatch: {row.get('sense_id')}")
        elif any(row.get(field) != parent.get(parent_field) for field, parent_field in {
            "proposed_definition_en": "effective_definition_en",
            "proposed_part_of_speech": "effective_part_of_speech",
            "proposed_scope_note": "scope_note",
            "glossary_match_status": "glossary_match_status",
            "glossary_candidate_vi": "glossary_candidate_vi",
        }.items()):
            errors.append(f"selected sense source projection mismatch: {row.get('sense_id')}")

    contexts = {row["context_id"]: row for row in read_jsonl(root / "contexts_selected.jsonl")}
    v3_root = repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3"
    v3_contexts = {row["context_id"]: row for row in read_jsonl(v3_root / "contexts.jsonl")}
    quarantine_path = repo_root / "dataset" / "d2l_dataset_fasttrack_glossary_first_v1_1" / "release" / "d2l_dataset_fasttrack_glossary_first_v1_1" / "quarantined_cross_split_source_blocks.jsonl"
    quarantined = {row["block_id"] for row in read_jsonl(quarantine_path)}
    positive_ids: set[str] = set()
    boundary_ids: set[str] = set()
    for row in selected:
        definition_ids = set(row.get("positive_definition_evidence_ids", []))
        pos_ids = set(row.get("positive_pos_evidence_ids", []))
        local_positive = definition_ids | pos_ids
        local_boundary = set(row.get("boundary_context_ids", []))
        if local_positive & local_boundary:
            errors.append(f"positive/boundary overlap: {row['sense_id']}")
        positive_ids |= local_positive
        boundary_ids |= local_boundary
        for context_id in local_positive:
            context = contexts.get(context_id)
            source_context = v3_contexts.get(context_id)
            if not context or not source_context or not _is_real_positive(source_context, row["sense_id"]):
                errors.append(f"invalid positive context: {row['sense_id']} / {context_id}")
            if context and context.get("provenance", {}).get("block_id") in quarantined:
                errors.append(f"quarantined positive context: {context_id}")
        for context_id in local_boundary:
            if context_id not in contexts:
                errors.append(f"missing boundary context: {row['sense_id']} / {context_id}")
    for context_id, context in contexts.items():
        source_context = v3_contexts.get(context_id)
        projected = dict(context)
        projected.pop("pilot_evidence_roles", None)
        projected.pop("pilot_context_sha256", None)
        if not source_context or projected != source_context:
            errors.append(f"context source projection mismatch: {context_id}")
    if positive_ids & boundary_ids:
        errors.append("cross-sense positive/boundary context overlap")

    candidates = read_jsonl(root / "candidate_instances_45.jsonl")
    if len(candidates) != 45 or len({row.get("candidate_id") for row in candidates}) != 45:
        errors.append("candidate cardinality/uniqueness mismatch")
    by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        if not verify_record(row, "candidate_projection_sha256"):
            errors.append(f"candidate projection self hash mismatch: {row.get('candidate_id')}")
        by_sense[row.get("sense_id")].append(row)
        if row.get("candidate_gold_label") is not None:
            errors.append("candidate gold label was prefilled")
        parent = row.get("parent_candidate_record") or {}
        source_parent = parent_candidates.get(row.get("candidate_id"))
        if parent.get("candidate_id") != row.get("candidate_id") or parent.get("candidate_provenance_sha256") != row.get("parent_candidate_provenance_sha256") or source_parent != parent:
            errors.append(f"candidate parent identity mismatch: {row.get('candidate_id')}")
    for sense_id, rows in by_sense.items():
        if sorted(row.get("candidate_role") for row in rows) != ["A", "B", "C"]:
            errors.append(f"candidate roles mismatch: {sense_id}")
        selected_row = next((item for item in selected if item["sense_id"] == sense_id), None)
        if selected_row and "WRONG_SENSE_CANDIDATE" in selected_row.get("coverage_tags", []) and len({row.get("candidate_vi") for row in rows}) < 2:
            errors.append(f"wrong-sense coverage lacks competing candidate values: {sense_id}")
        if selected_row and "TARGET_COLLISION" in selected_row.get("coverage_tags", []) and selected_row.get("stratum") != "collision_or_multi_target":
            errors.append(f"target-collision coverage is not backed by collision stratum: {sense_id}")
        if selected_row and "INSUFFICIENT_POSITIVE_EVIDENCE" in selected_row.get("coverage_tags", []) and selected_row.get("positive_context_count", 0) > 2:
            errors.append(f"insufficient-evidence case has too many positive contexts: {sense_id}")
        if selected_row and "E_UNJUDGEABLE_SCENARIO" in selected_row.get("coverage_tags", []) and selected_row.get("positive_context_count") != 1:
            errors.append(f"E-unjudgeable case is not the one-context case: {sense_id}")
    if set(by_sense) != {row["sense_id"] for row in selected}:
        errors.append("candidate/sense join mismatch")

    review_rows = _csv_rows(root / "stage_a_review_results_15_senses.csv")
    if len(review_rows) != 15:
        errors.append("review result cardinality mismatch")
    human_columns = [column for column in (review_rows[0].keys() if review_rows else []) if column.startswith("reviewer_") or column.startswith("adjudicator_") or column in {"completed_at"}]
    if any(row.get(column, "").strip() for row in review_rows for column in human_columns):
        errors.append("human review fields must remain blank")
    if any(row.get("review_status") != "PENDING_HUMAN_REVIEW" for row in review_rows):
        errors.append("review result status is not pending")

    blind_rows = _csv_rows(root / "stage_a_blind_audit_template_3.csv")
    if len(blind_rows) != 3 or len({row.get("sense_id") for row in blind_rows}) != 3:
        errors.append("blind audit template must contain the three R0 cases")
    if any(
        row.get("blind_reviewer_id", "").strip()
        or row.get("blind_reviewer_type", "").strip()
        or row.get("consensus_split_decision", "").strip()
        or row.get("consensus_part_of_speech", "").strip()
        or row.get("consensus_definition_en", "").strip()
        or row.get("review_artifact_sha256", "").strip()
        for row in blind_rows
    ):
        errors.append("blind audit human fields must remain blank")

    provenance = read_jsonl(root / "review_provenance_15_senses.jsonl")
    if any(not verify_record(row, "review_provenance_sha256") for row in provenance):
        errors.append("review provenance self hash mismatch")
    if any(row.get("reviewer_id") is not None or row.get("reviewer_type") is not None or row.get("human_authority_present") is not False for row in provenance):
        errors.append("review provenance fabricates human authority")
    required_slots = Counter()
    for sense in selected:
        for slot, _ in _review_slots(sense["risk_class"], sense["coverage_tags"]):
            required_slots[(sense["sense_id"], slot)] += 1
    actual_slots = Counter((row.get("sense_id"), row.get("reviewer_slot")) for row in provenance)
    if actual_slots != required_slots:
        errors.append("review provenance slot coverage mismatch")
    adjudication = read_jsonl(root / "stage_a_adjudication_15_senses.jsonl")
    if any(not verify_record(row, "adjudication_sha256") for row in adjudication):
        errors.append("adjudication template self hash mismatch")
    if any(row.get("adjudicator_id") is not None or row.get("final_decision") is not None or row.get("human_authority_present") is not False for row in adjudication):
        errors.append("adjudication template fabricates authority")

    stage_b = _csv_rows(root / "stage_b_annotation_template_45.csv")
    if len(stage_b) != 45:
        errors.append("Stage B cardinality mismatch")
    for row in stage_b:
        if row.get("candidate_gold_label", "").strip() or row.get("allowed_scope", "").strip() or row.get("reason_codes", "").strip() or row.get("vietnamese_evidence_refs", "").strip():
            errors.append("Stage B gold/human fields are not blank")
    if set((row.get("candidate_id") for row in stage_b)) != {row.get("candidate_id") for row in candidates}:
        errors.append("Stage B candidate join mismatch")

    for directory in ["effective_sense_contracts_15", "integration_pilot_effective_sense_contracts_5", "integration_pilot_frozen_candidates_15", "integration_pilot_constraint_packages_15"]:
        files = set(build_file_inventory(root / directory).keys())
        if files != {"README.md"}:
            errors.append(f"official/pending contract directory contains unexpected files: {directory}")

    integration = read_json(root / "integration_pilot_5_sense_selection_receipt.json")
    if not verify_record(integration, "receipt_sha256"):
        errors.append("integration selection receipt self hash mismatch")
    if [row.get("source_term") for row in integration.get("records", [])] != INTEGRATION_TERMS:
        errors.append("integration selection terms mismatch")
    if integration.get("selection_status") != "PENDING_STAGE_A_FINALIZATION":
        errors.append("integration selection must remain provisional")

    gate = read_json(root / "stage_a_pilot_15_acceptance_gate_report.json")
    if gate.get("status") != "BLOCKED_BY_HUMAN_REVIEW":
        errors.append("acceptance gate must be blocked")
    if gate.get("selected_sense_count") != 15 or gate.get("stage_b_open_row_count") != 45:
        errors.append("acceptance gate counts mismatch")
    if gate.get("final_glossary_decision") is not None:
        errors.append("final glossary decision must remain null")
    expected_blockers = {name for name, value in gate.get("checks", {}).items() if value is False}
    if set(gate.get("blockers", [])) != expected_blockers:
        errors.append("acceptance gate blocker list mismatch")

    receipt = read_json(root / "pilot_release_receipt.json")
    if not verify_record(receipt, "receipt_sha256"):
        errors.append("pilot release receipt self hash mismatch")
    pack_zip = root.parent / "stage_a_review_pack_15_senses.zip"
    _check_pack(pack_zip, receipt.get("review_pack_zip_sha256"), errors)

    report = {
        "schema_id": "D2LStageAPilotValidationReportV1",
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
        "counts": {
            "selected_sense": len(selected),
            "candidate": len(candidates),
            "context": len(contexts),
            "review_provenance_template": len(provenance),
            "adjudication_template": len(adjudication),
            "blind_audit_case": len(blind_rows),
            "stage_b_rows": len(stage_b),
            "positive_context": len(positive_ids),
            "boundary_context": len(boundary_ids),
        },
        "manifest_sha256": claimed_manifest,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_pilot(args.artifact_root, args.repo_root)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
