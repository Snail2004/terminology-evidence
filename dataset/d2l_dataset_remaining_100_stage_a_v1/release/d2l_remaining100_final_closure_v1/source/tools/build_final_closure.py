from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    replace_directory,
    seal_integrity,
    seal_record,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    write_checksums,
    write_json,
    write_jsonl,
)

from .final_reaudit_validation import FinalReauditSpec, capture_final_reaudits


ARTIFACT_NAME = "d2l_remaining100_final_closure_v1"
POLICY_ID = "d2l-remaining-100-stage-a-final-closure-v1.0"
CREATED_AT = "2026-07-30T00:00:00Z"
BASE_AUTHORITY_COMMIT = "0281ed3bfa4ebd10f950c2c639f98242285d1c62"
TARGET_TERMS = {"attention", "blocks", "inverse", "shape"}
EXPECTED_BATCHES = {
    "proposal_reaudit_reviewer_4": ("reviewer_4", 1),
    "proposal_reaudit_reviewer_5": ("reviewer_5", 3),
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_source_manifest(
    root: Path, allowed_extras: set[str]
) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError(f"{root.name}: source manifest self-hash mismatch")
    actual = {
        relative: metadata
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256", "manifest.json"}
        ).items()
        if relative not in allowed_extras
    }
    if manifest.get("files") != actual:
        raise ValueError(f"{root.name}: source manifest inventory mismatch")
    return manifest


def _reaudit_specs(
    proposal_root: Path,
    reviewer_4_response: Path,
    reviewer_5_response: Path,
) -> list[FinalReauditSpec]:
    supplied = [
        ("reviewer_4", reviewer_4_response),
        ("reviewer_5", reviewer_5_response),
    ]
    specs: list[FinalReauditSpec] = []
    seen: set[str] = set()
    for supplied_role, response_path in supplied:
        response_path = response_path.resolve(strict=True)
        payload = strict_json_object(response_path)
        batch_id = payload.get("batch_id")
        if not isinstance(batch_id, str) or batch_id not in EXPECTED_BATCHES:
            raise ValueError(f"unexpected final re-audit batch: {batch_id}")
        expected_role, expected_count = EXPECTED_BATCHES[batch_id]
        if supplied_role != expected_role:
            raise ValueError(f"{batch_id}: final re-audit reviewer mismatch")
        if payload.get("reviewer_slot") != expected_role:
            raise ValueError(f"{batch_id}: reviewer slot mismatch")
        if payload.get("case_count") != expected_count:
            raise ValueError(f"{batch_id}: case count mismatch")
        if batch_id in seen:
            raise ValueError(f"duplicate final re-audit batch: {batch_id}")
        specs.append(
            FinalReauditSpec(
                reviewer_role=expected_role,
                batch_id=batch_id,
                input_path=(
                    proposal_root
                    / "reaudit_batches"
                    / batch_id
                    / "auditor_input.json"
                ).resolve(strict=True),
                response_path=response_path,
            )
        )
        seen.add(batch_id)
    if seen != set(EXPECTED_BATCHES):
        raise ValueError("final re-audit responses do not match the assignment")
    return sorted(specs, key=lambda spec: spec.batch_id)


def _copy_source_bundle(staging: Path) -> None:
    source_root = staging / "source"
    module_root = Path(__file__).resolve().parent
    project_root = module_root.parent
    for name in (
        "build_final_closure.py",
        "final_reaudit_validation.py",
        "validate_final_closure.py",
    ):
        destination = source_root / "tools" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module_root / name, destination)
    destination = source_root / "tests" / "test_final_closure.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project_root / "tests" / "test_final_closure.py", destination)


def _approval_record(
    case: Mapping[str, Any],
    repair_record: Mapping[str, Any],
    result_sha256: str,
    reviewer_role: str,
) -> dict[str, Any]:
    child_ids = sorted(
        child["temporary_child_sense_id"]
        for child in case["repaired_proposal"]["child_sense_repairs"]
    )
    return seal_record(
        {
            "approved_child_sense_ids": child_ids,
            "approval_audit": case["audit"],
            "final_glossary_decision": None,
            "parent_repair_record_sha256": repair_record["record_sha256"],
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "reaudit_result_role": reviewer_role,
            "reaudit_result_sha256": result_sha256,
            "repaired_proposal": case["repaired_proposal"],
            "schema_id": "D2LRemaining100ApprovedProposalRepairV1",
            "schema_version": "1.0",
            "sense_id": case["sense_id"],
            "source_payload_sha256": case["source_payload_sha256"],
            "source_term": case["source_term"],
            "stage_b_gold_autofill_count": 0,
            "stage_b_gold_label": None,
        }
    )


def _child_records(approval: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for child in approval["repaired_proposal"]["child_sense_repairs"]:
        records.append(
            seal_record(
                {
                    "child_sense_payload": child,
                    "final_glossary_decision": None,
                    "parent_approval_record_sha256": approval["record_sha256"],
                    "parent_source_sense_id": approval["sense_id"],
                    "parent_source_term": approval["source_term"],
                    "policy_id": POLICY_ID,
                    "provider_call_count": 0,
                    "schema_id": "D2LRemaining100ApprovedChildSenseProjectionV1",
                    "schema_version": "1.0",
                    "source_payload_sha256": approval["source_payload_sha256"],
                    "stage_a_status": "APPROVED_SPLIT_CHILD",
                    "stage_b_gold_autofill_count": 0,
                    "stage_b_gold_label": None,
                    "temporary_child_sense_id": child[
                        "temporary_child_sense_id"
                    ],
                }
            )
        )
    return records


def _closure_record(
    prior: Mapping[str, Any], approval: Mapping[str, Any] | None
) -> dict[str, Any]:
    if approval is None:
        authority_kind = prior["authority_kind"]
        authority_record_sha256 = prior["authority_record_sha256"]
        child_ids: list[str] = []
        status = prior["stage_a_status"]
    else:
        authority_kind = "APPROVED_REPAIRED_SPLIT_PROPOSAL_REAUDIT"
        authority_record_sha256 = approval["record_sha256"]
        child_ids = approval["approved_child_sense_ids"]
        status = "READY"
    return seal_record(
        {
            "approved_child_sense_ids": child_ids,
            "authority_kind": authority_kind,
            "authority_record_sha256": authority_record_sha256,
            "final_glossary_decision": None,
            "parent_closure_record_sha256": prior["record_sha256"],
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "schema_id": "D2LRemaining100FinalClosureIndexRecordV1",
            "schema_version": "1.0",
            "sense_id": prior["sense_id"],
            "source_payload_sha256": prior["source_payload_sha256"],
            "source_term": prior["source_term"],
            "stage_a_status": status,
            "stage_b_gold_label": None,
        }
    )


def build_final_closure(
    *,
    proposal_root: Path,
    prior_closure_root: Path,
    reviewer_4_response: Path,
    reviewer_5_response: Path,
    output_root: Path,
    zip_path: Path,
    after_inventory: Callable[[], None] | None = None,
) -> dict[str, Any]:
    proposal_root = proposal_root.resolve(strict=True)
    prior_closure_root = prior_closure_root.resolve(strict=True)
    output_root = output_root.resolve()
    zip_path = zip_path.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    proposal_manifest = _verify_source_manifest(
        proposal_root,
        {
            "handoff/proposal_reaudit_reviewer_5.json",
            "handoff/result-reviewer4/proposal_reaudit_reviewer_4.json",
        },
    )
    prior_manifest = _verify_source_manifest(
        prior_closure_root,
        {
            "handoff/high_risk_proposal_repair_reviewer_2.json",
            "handoff/high_risk_proposal_repair_reviewer_3.json",
        },
    )
    specs = _reaudit_specs(
        proposal_root, reviewer_4_response, reviewer_5_response
    )
    repair_records = {
        row["sense_id"]: row
        for row in strict_jsonl(
            proposal_root / "proposal_repairs_pending_reaudit_4.jsonl"
        )
    }
    prior_closure = strict_jsonl(prior_closure_root / "closure_index_100.jsonl")
    with tempfile.TemporaryDirectory(
        prefix="remaining100-final-closure-", dir=output_root.parent
    ) as name:
        staging = Path(name) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        capture_root = staging / "captures"
        inventory = capture_final_reaudits(
            specs, capture_root, after_inventory=after_inventory
        )
        inventory_by_batch = {row["batch_id"]: row for row in inventory}
        approvals: list[dict[str, Any]] = []
        for spec in specs:
            inventory_row = inventory_by_batch[spec.batch_id]
            payload = strict_json_object(
                capture_root / inventory_row["captured_relative_path"]
            )
            for case in payload["cases"]:
                if case["audit"]["audit_decision"] != "APPROVE":
                    raise ValueError(
                        f"{case['source_term']}: final re-audit is not APPROVE"
                    )
                repair = repair_records.get(case["sense_id"])
                if repair is None:
                    raise ValueError(f"{case['sense_id']}: missing repair authority")
                if (
                    case["parent_repair_record_sha256"] != repair["record_sha256"]
                    or case["repaired_proposal"] != repair["repaired_proposal"]
                    or case["proposal_repair"] != repair["proposal_repair"]
                    or case["source_payload_sha256"]
                    != repair["source_payload_sha256"]
                ):
                    raise ValueError(f"{case['sense_id']}: repair binding mismatch")
                if spec.reviewer_role == repair["repair_result_role"]:
                    raise ValueError(
                        f"{case['sense_id']}: repair author performed re-audit"
                    )
                approvals.append(
                    _approval_record(
                        case,
                        repair,
                        inventory_row["sha256"],
                        spec.reviewer_role,
                    )
                )
        approvals.sort(key=lambda row: row["sense_id"])
        if len(approvals) != 4 or {row["source_term"] for row in approvals} != TARGET_TERMS:
            raise ValueError("approved proposal set must contain the exact four terms")
        approval_by_sense = {row["sense_id"]: row for row in approvals}
        write_jsonl(staging / "approved_repaired_split_proposals_4.jsonl", approvals)

        children = sorted(
            [child for approval in approvals for child in _child_records(approval)],
            key=lambda row: row["temporary_child_sense_id"],
        )
        if len(children) != 9 or len(
            {row["temporary_child_sense_id"] for row in children}
        ) != 9:
            raise ValueError("approved child-sense projection must contain nine IDs")
        write_jsonl(staging / "approved_child_sense_projections_9.jsonl", children)

        closure = sorted(
            [
                _closure_record(row, approval_by_sense.get(row["sense_id"]))
                for row in prior_closure
            ],
            key=lambda row: row["sense_id"],
        )
        if len(closure) != 100 or len({row["sense_id"] for row in closure}) != 100:
            raise ValueError("final closure must contain 100 unique source senses")
        status_counts = {
            status: sum(row["stage_a_status"] == status for row in closure)
            for status in {row["stage_a_status"] for row in closure}
        }
        if status_counts != {"BLOCKED": 1, "READY": 99}:
            raise ValueError(f"unexpected final closure counts: {status_counts}")
        blocked = [row for row in closure if row["stage_a_status"] == "BLOCKED"]
        if len(blocked) != 1 or blocked[0]["source_term"] != "switch":
            raise ValueError("switch must remain the sole blocked source sense")
        write_jsonl(staging / "closure_index_100.jsonl", closure)
        write_json(
            staging / "switch_resolution_required.json",
            seal_integrity(
                {
                    "allowed_next_actions": [
                        "ADD_REAL_POSITIVE_CORPUS_EVIDENCE_AND_REVIEW",
                        "REPLACE_SOURCE_SLOT_WITH_FROZEN_ELIGIBLE_SENSE",
                    ],
                    "final_glossary_decision": None,
                    "forbidden_positive_evidence": [
                        "SYNTHETIC_CONTEXT",
                        "BOUNDARY_ONLY_CONTEXT",
                    ],
                    "parent_closure_record_sha256": blocked[0][
                        "parent_closure_record_sha256"
                    ],
                    "policy_id": POLICY_ID,
                    "provider_call_count": 0,
                    "schema_id": "D2LRemaining100SwitchResolutionRequirementV1",
                    "schema_version": "1.0",
                    "sense_id": blocked[0]["sense_id"],
                    "source_payload_sha256": blocked[0]["source_payload_sha256"],
                    "source_term": "switch",
                    "stage_a_status": "BLOCKED",
                    "stage_b_gold_autofill_count": 0,
                    "stage_b_gold_label": None,
                    "status": "REAL_POSITIVE_EVIDENCE_OR_REPLACEMENT_REQUIRED",
                }
            ),
        )
        write_json(
            staging / "authority.json",
            seal_integrity(
                {
                    "base_authority_commit": BASE_AUTHORITY_COMMIT,
                    "policy_id": POLICY_ID,
                    "prior_closure_manifest_physical_sha256": sha256_file(
                        prior_closure_root / "manifest.json"
                    ),
                    "prior_closure_manifest_self_sha256": prior_manifest[
                        "manifest_sha256"
                    ],
                    "proposal_manifest_physical_sha256": sha256_file(
                        proposal_root / "manifest.json"
                    ),
                    "proposal_manifest_self_sha256": proposal_manifest[
                        "manifest_sha256"
                    ],
                    "schema_id": "D2LRemaining100FinalClosureAuthorityV1",
                    "schema_version": "1.0",
                }
            ),
        )
        write_json(
            staging / "input_inventory.json",
            seal_integrity(
                {
                    "file_count": len(inventory),
                    "files": inventory,
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LRemaining100FinalReauditInputInventoryV1",
                    "schema_version": "1.0",
                }
            ),
        )
        write_json(
            staging / "validation_report.json",
            seal_integrity(
                {
                    "approved_child_sense_count": len(children),
                    "approved_repaired_proposal_count": len(approvals),
                    "blocked_source_sense_count": 1,
                    "created_at": CREATED_AT,
                    "final_glossary_decision": None,
                    "policy_id": POLICY_ID,
                    "provider_call_count": 0,
                    "ready_source_sense_count": 99,
                    "schema_id": "D2LRemaining100FinalClosureReportV1",
                    "schema_version": "1.0",
                    "stage_b_gold_autofill_count": 0,
                    "status": "REMAINING_100_STAGE_A_99_READY_1_BLOCKED_ZERO_PROVIDER",
                    "validated_final_reaudit_file_count": len(inventory),
                }
            ),
        )
        (staging / "RELEASE_REPORT.md").write_bytes(
            (
                "# D2L remaining-100 final Stage A closure\n\n"
                "- Final independent re-audit files validated: 2/2.\n"
                "- Approved repaired split proposals: 4/4.\n"
                "- Approved child-sense projections: 9.\n"
                "- Remaining-100 source slots READY: 99/100.\n"
                "- BLOCKED: 1 (`switch`).\n"
                "- `switch` requires real positive corpus evidence or a frozen replacement slot.\n"
                "- Provider calls: 0.\n"
                "- Stage B gold autofill: 0.\n"
                "- Final glossary decision: null.\n"
            ).encode("utf-8")
        )
        _copy_source_bundle(staging)
        files = build_file_inventory(
            staging, excluded={"CHECKSUMS.sha256", "manifest.json"}
        )
        manifest = {
            "artifact_name": ARTIFACT_NAME,
            "base_authority_commit": BASE_AUTHORITY_COMMIT,
            "created_at": CREATED_AT,
            "file_count": len(files),
            "files": files,
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "schema_id": "D2LRemaining100FinalClosureManifestV1",
            "schema_version": "1.0",
            "status": "REMAINING_100_STAGE_A_99_READY_1_BLOCKED_ZERO_PROVIDER",
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from .validate_final_closure import validate_artifact

        errors = validate_artifact(staging)
        if errors:
            raise ValueError("; ".join(errors))
        replace_directory(staging, output_root)
    build_deterministic_zip(output_root, zip_path)
    return {
        "artifact_root": str(output_root),
        "manifest_sha256": strict_json_object(output_root / "manifest.json")[
            "manifest_sha256"
        ],
        "status": "REMAINING_100_STAGE_A_99_READY_1_BLOCKED_ZERO_PROVIDER",
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal-root", type=Path, required=True)
    parser.add_argument("--prior-closure-root", type=Path, required=True)
    parser.add_argument("--reviewer-4-response", type=Path, required=True)
    parser.add_argument("--reviewer-5-response", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path, required=True)
    args = parser.parse_args()
    result = build_final_closure(
        proposal_root=args.proposal_root,
        prior_closure_root=args.prior_closure_root,
        reviewer_4_response=args.reviewer_4_response,
        reviewer_5_response=args.reviewer_5_response,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
