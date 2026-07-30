from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

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
    verify_record,
    write_checksums,
    write_json,
    write_jsonl,
)

from .followup_result_handoffs import build_proposal_repair_handoffs
from .followup_validation import ReviewFileSpec, capture_review_files


ARTIFACT_NAME = "d2l_dataset_remaining_100_stage_a_followup_result_v1"
POLICY_ID = "d2l-remaining-100-stage-a-followup-result-v1.0"
CREATED_AT = "2026-07-30T00:00:00Z"
BASE_AUTHORITY_COMMIT = "d748fcd8e7c26f48d760cbfbd2ae5ad75aac7787"
EXPECTED_ASSIGNMENTS = {
    "followup_reaudit_batch_001": ("followup_reaudit", "reviewer_4"),
    "followup_reaudit_batch_002": ("followup_reaudit", "reviewer_5"),
    "followup_reaudit_batch_003": ("followup_reaudit", "reviewer_4"),
    "high_risk_audit_batch_001": ("high_risk_audit", "reviewer_4"),
    "high_risk_audit_batch_002": ("high_risk_audit", "reviewer_5"),
    "high_risk_audit_batch_003": ("high_risk_audit", "reviewer_5"),
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_manifest(
    root: Path, allowed_extra_prefixes: Sequence[str] = ()
) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError(f"manifest self-hash mismatch: {root.name}")
    actual = {
        relative: metadata
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256", "manifest.json"}
        ).items()
        if not any(relative.startswith(prefix) for prefix in allowed_extra_prefixes)
    }
    if manifest.get("files") != actual:
        raise ValueError(f"manifest inventory mismatch: {root.name}")
    return manifest


def _result_specs(
    followup_root: Path,
    reviewer_4_responses: Sequence[Path],
    reviewer_5_responses: Sequence[Path],
) -> list[ReviewFileSpec]:
    supplied = [
        *(('reviewer_4', path) for path in reviewer_4_responses),
        *(('reviewer_5', path) for path in reviewer_5_responses),
    ]
    if len(supplied) != 6:
        raise ValueError("exactly six follow-up response files are required")
    specs: list[ReviewFileSpec] = []
    seen: set[str] = set()
    for supplied_role, response_path in supplied:
        response_path = response_path.resolve(strict=True)
        payload = strict_json_object(response_path)
        batch_id = payload.get("batch_id")
        if not isinstance(batch_id, str) or batch_id not in EXPECTED_ASSIGNMENTS:
            raise ValueError(f"unexpected follow-up batch: {batch_id}")
        if batch_id in seen:
            raise ValueError(f"duplicate follow-up batch: {batch_id}")
        kind, expected_role = EXPECTED_ASSIGNMENTS[batch_id]
        if supplied_role != expected_role:
            raise ValueError(f"{batch_id}: assigned reviewer mismatch")
        input_name = (
            "reviewer_input.json"
            if kind == "followup_reaudit"
            else "auditor_input.json"
        )
        specs.append(
            ReviewFileSpec(
                kind=kind,
                reviewer_role=supplied_role,
                batch_id=batch_id,
                input_path=(followup_root / "review_batches" / batch_id / input_name)
                .resolve(strict=True),
                response_path=response_path,
            )
        )
        seen.add(batch_id)
    if seen != set(EXPECTED_ASSIGNMENTS):
        raise ValueError("follow-up response batches do not match the frozen assignment")
    return sorted(specs, key=lambda spec: spec.batch_id)


def _captured_payload(captures_root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    return strict_json_object(captures_root / str(row["captured_relative_path"]))


def _reaudit_ready_record(
    case: Mapping[str, Any], result_sha256: str, reviewer_role: str
) -> dict[str, Any]:
    source = case["source_payload"]
    return seal_record(
        {
            "final_glossary_decision": None,
            "parent_repair_record_sha256": case["repair_record_sha256"],
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "review": case["review"],
            "review_result_role": reviewer_role,
            "review_result_sha256": result_sha256,
            "schema_id": "D2LRemaining100FollowupReauditReadyRecordV1",
            "schema_version": "1.0",
            "sense_id": source["sense_id"],
            "source_payload": source,
            "source_payload_sha256": case["source_payload_sha256"],
            "source_term": source["source_term"],
            "stage_b_gold_label": None,
            "status": "READY_FOR_EFFECTIVE_CONTRACT_CONSTRUCTION",
        }
    )


def _high_risk_result_record(
    *,
    case: Mapping[str, Any],
    source_route: Mapping[str, Any],
    result_sha256: str,
    reviewer_role: str,
) -> dict[str, Any]:
    decision = case["audit"]["audit_decision"]
    status = {
        "APPROVE": "READY_FOR_EFFECTIVE_CONTRACT_CONSTRUCTION",
        "REVISE": "PROPOSAL_REVISION_REQUIRED",
        "BLOCK": "BLOCKED_BY_INDEPENDENT_AUDIT",
    }[decision]
    return seal_record(
        {
            "audit": case["audit"],
            "audit_result_role": reviewer_role,
            "audit_result_sha256": result_sha256,
            "final_glossary_decision": None,
            "parent_proposal_record_sha256": case["proposal_record_sha256"],
            "policy_id": POLICY_ID,
            "proposal": case["proposal"],
            "provider_call_count": 0,
            "schema_id": "D2LRemaining100HighRiskAuditResultRecordV1",
            "schema_version": "1.0",
            "sense_id": case["sense_id"],
            "source_payload": case["source_payload"],
            "source_payload_sha256": case["source_payload_sha256"],
            "source_result_role": source_route["source_result_role"],
            "source_term": case["source_term"],
            "stage_b_gold_label": None,
            "status": status,
        }
    )


def _closure_record(
    *,
    authority_kind: str,
    authority_record_sha256: str,
    sense_id: str,
    source_payload_sha256: str,
    source_term: str,
    stage_a_status: str,
) -> dict[str, Any]:
    return seal_record(
        {
            "authority_kind": authority_kind,
            "authority_record_sha256": authority_record_sha256,
            "final_glossary_decision": None,
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "schema_id": "D2LRemaining100StageAClosureIndexRecordV1",
            "schema_version": "1.0",
            "sense_id": sense_id,
            "source_payload_sha256": source_payload_sha256,
            "source_term": source_term,
            "stage_a_status": stage_a_status,
            "stage_b_gold_label": None,
        }
    )


def _load_corrected_adjudications(root: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    paths = sorted(
        (root / "corrected_reviews" / "reviewer_3").glob(
            "batch_*/reviewer_3_input.json"
        )
    )
    for path in paths:
        payload = strict_json_object(path)
        cases.extend(payload.get("cases", []))
    if len(paths) != 10 or len(cases) != 45:
        raise ValueError("corrected Reviewer 3 authority must contain 10 batches/45 cases")
    sense_ids = [str(case.get("sense_id")) for case in cases]
    if len(set(sense_ids)) != 45:
        raise ValueError("corrected Reviewer 3 sense IDs must be unique")
    return cases


def _copy_source_bundle(staging: Path) -> None:
    source_root = staging / "source"
    module_root = Path(__file__).resolve().parent
    project_root = module_root.parent
    for name in (
        "build_followup_result.py",
        "followup_result_handoffs.py",
        "followup_validation.py",
        "validate_followup_result.py",
    ):
        destination = source_root / "tools" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module_root / name, destination)
    destination = source_root / "tests" / "test_followup_result.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project_root / "tests" / "test_followup_result.py", destination)


def build_followup_result(
    *,
    followup_root: Path,
    initial_intake_root: Path,
    reviewer_3_corrected_root: Path,
    reviewer_4_responses: Sequence[Path],
    reviewer_5_responses: Sequence[Path],
    output_root: Path,
    zip_path: Path,
) -> dict[str, Any]:
    followup_root = followup_root.resolve(strict=True)
    initial_intake_root = initial_intake_root.resolve(strict=True)
    reviewer_3_corrected_root = reviewer_3_corrected_root.resolve(strict=True)
    source_manifests = {
        "followup": _verify_manifest(
            followup_root,
            (
                "handoff/result-reviewer4/",
                "handoff/result-reviewer5/",
            ),
        ),
        "initial_intake": _verify_manifest(initial_intake_root),
        "reviewer_3_corrected": _verify_manifest(reviewer_3_corrected_root),
    }
    specs = _result_specs(
        followup_root, reviewer_4_responses, reviewer_5_responses
    )
    output_root = output_root.resolve()
    zip_path = zip_path.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{ARTIFACT_NAME}-", dir=output_root.parent
    ) as temp_name:
        staging = Path(temp_name) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        captures_root = staging / "captures"
        inventory = capture_review_files(specs, captures_root)
        inventory_by_batch = {row["batch_id"]: row for row in inventory}
        source_high_risk = {
            row["audit_case_id"]: row
            for row in strict_jsonl(
                followup_root / "routing" / "high_risk_audit_pending_10.jsonl"
            )
        }
        ready_reaudits: list[dict[str, Any]] = []
        approved_high_risk: list[dict[str, Any]] = []
        revised_high_risk: list[dict[str, Any]] = []
        blocked_high_risk: list[dict[str, Any]] = []
        for spec in specs:
            inventory_row = inventory_by_batch[spec.batch_id]
            payload = _captured_payload(captures_root, inventory_row)
            for case in payload["cases"]:
                if spec.kind == "followup_reaudit":
                    if case["review"]["sense_status"] != "READY_FOR_CONTRACT_CONSTRUCTION":
                        raise ValueError(f"{case['sense_id']}: re-audit did not close")
                    ready_reaudits.append(
                        _reaudit_ready_record(
                            case, inventory_row["sha256"], spec.reviewer_role
                        )
                    )
                    continue
                source_route = source_high_risk.get(case["case_id"])
                if source_route is None:
                    raise ValueError(f"{case['case_id']}: missing source proposal route")
                if source_route["record_sha256"] != case["proposal_record_sha256"]:
                    raise ValueError(f"{case['case_id']}: proposal binding mismatch")
                record = _high_risk_result_record(
                    case=case,
                    source_route=source_route,
                    result_sha256=inventory_row["sha256"],
                    reviewer_role=spec.reviewer_role,
                )
                decision = case["audit"]["audit_decision"]
                if decision == "APPROVE":
                    approved_high_risk.append(record)
                elif decision == "REVISE":
                    revised_high_risk.append(record)
                else:
                    blocked_high_risk.append(record)
        for rows in (
            ready_reaudits,
            approved_high_risk,
            revised_high_risk,
            blocked_high_risk,
        ):
            rows.sort(key=lambda row: str(row["sense_id"]))
        if tuple(map(len, (ready_reaudits, approved_high_risk, revised_high_risk, blocked_high_risk))) != (12, 6, 4, 0):
            raise ValueError("follow-up outcome counts do not match reviewed results")

        prior_accepted = strict_jsonl(
            followup_root / "routing" / "accepted_blind_23.jsonl"
        )
        prior_blocked = strict_jsonl(followup_root / "routing" / "blocked_1.jsonl")
        r3_agreements = strict_jsonl(
            initial_intake_root / "r3_dual_agreement_20.jsonl"
        )
        if len(r3_agreements) != 20:
            raise ValueError("R3 agreement authority must contain 20 cases")
        adjudications = _load_corrected_adjudications(reviewer_3_corrected_root)
        followup_adjudication_ids = {
            *(str(row["sense_id"]) for row in source_high_risk.values()),
            *(str(row["sense_id"]) for row in prior_blocked),
        }
        direct_r3_agreements = [
            row
            for row in r3_agreements
            if str(row["sense_id"]) not in followup_adjudication_ids
        ]
        if len(direct_r3_agreements) != 18 or any(
            row["reviewer_1_review"]["sense_status"]
            != "READY_FOR_CONTRACT_CONSTRUCTION"
            or row["reviewer_2_review"]["sense_status"]
            != "READY_FOR_CONTRACT_CONSTRUCTION"
            for row in direct_r3_agreements
        ):
            raise ValueError("direct R3 agreement closure count/status mismatch")
        if any(
            not verify_record(row, "agreement_record_sha256")
            for row in direct_r3_agreements
        ):
            raise ValueError("direct R3 agreement record hash mismatch")
        direct_adjudications = [
            case
            for case in adjudications
            if str(case["sense_id"]) not in followup_adjudication_ids
        ]
        if len(direct_adjudications) != 36 or any(
            case["adjudication"]["sense_status"]
            != "READY_FOR_CONTRACT_CONSTRUCTION"
            for case in direct_adjudications
        ):
            raise ValueError("direct adjudication closure count/status mismatch")

        closure: list[dict[str, Any]] = []
        for row in direct_r3_agreements:
            closure.append(
                _closure_record(
                    authority_kind="R3_DUAL_AGREEMENT",
                    authority_record_sha256=row["agreement_record_sha256"],
                    sense_id=row["sense_id"],
                    source_payload_sha256=row["source_payload_sha256"],
                    source_term=row["source_payload"]["source_term"],
                    stage_a_status="READY",
                )
            )
        for case in direct_adjudications:
            closure.append(
                _closure_record(
                    authority_kind="REVIEWER_3_ADJUDICATION",
                    authority_record_sha256=sha256_bytes(
                        canonical_json_bytes(case)
                    ),
                    sense_id=case["sense_id"],
                    source_payload_sha256=case["source_payload_sha256"],
                    source_term=case["source_term"],
                    stage_a_status="READY",
                )
            )
        for row in prior_accepted:
            closure.append(
                _closure_record(
                    authority_kind="PRIOR_BLIND_AUDIT",
                    authority_record_sha256=row["record_sha256"],
                    sense_id=row["sense_id"],
                    source_payload_sha256=row["source_payload_sha256"],
                    source_term=row["source_term"],
                    stage_a_status="READY",
                )
            )
        for row in ready_reaudits:
            closure.append(
                _closure_record(
                    authority_kind="FOLLOWUP_BLIND_REAUDIT",
                    authority_record_sha256=row["record_sha256"],
                    sense_id=row["sense_id"],
                    source_payload_sha256=row["source_payload_sha256"],
                    source_term=row["source_term"],
                    stage_a_status="READY",
                )
            )
        for row in approved_high_risk:
            closure.append(
                _closure_record(
                    authority_kind="HIGH_RISK_PROPOSAL_AUDIT",
                    authority_record_sha256=row["record_sha256"],
                    sense_id=row["sense_id"],
                    source_payload_sha256=row["source_payload_sha256"],
                    source_term=row["source_term"],
                    stage_a_status="READY",
                )
            )
        for row in revised_high_risk:
            closure.append(
                _closure_record(
                    authority_kind="HIGH_RISK_PROPOSAL_AUDIT",
                    authority_record_sha256=row["record_sha256"],
                    sense_id=row["sense_id"],
                    source_payload_sha256=row["source_payload_sha256"],
                    source_term=row["source_term"],
                    stage_a_status="REVISION_REQUIRED",
                )
            )
        for row in prior_blocked:
            closure.append(
                _closure_record(
                    authority_kind="PRIOR_INSUFFICIENT_EVIDENCE_BLOCK",
                    authority_record_sha256=row["record_sha256"],
                    sense_id=row["sense_id"],
                    source_payload_sha256=row["parent_source_payload_sha256"],
                    source_term=row["source_term"],
                    stage_a_status="BLOCKED",
                )
            )
        closure.sort(key=lambda row: str(row["sense_id"]))
        closure_ids = [str(row["sense_id"]) for row in closure]
        status_counts = {
            status: sum(row["stage_a_status"] == status for row in closure)
            for status in ("BLOCKED", "READY", "REVISION_REQUIRED")
        }
        if len(closure) != 100 or len(set(closure_ids)) != 100:
            raise ValueError("closure index must contain 100 unique source senses")
        if status_counts != {"BLOCKED": 1, "READY": 95, "REVISION_REQUIRED": 4}:
            raise ValueError("closure status counts do not match reviewed evidence")

        write_jsonl(staging / "routing" / "reaudit_ready_12.jsonl", ready_reaudits)
        write_jsonl(
            staging / "routing" / "high_risk_approved_6.jsonl",
            approved_high_risk,
        )
        write_jsonl(
            staging / "routing" / "high_risk_revision_required_4.jsonl",
            revised_high_risk,
        )
        write_jsonl(
            staging / "routing" / "prior_accepted_blind_23.jsonl", prior_accepted
        )
        write_jsonl(staging / "routing" / "prior_blocked_1.jsonl", prior_blocked)
        write_jsonl(staging / "closure_index_100.jsonl", closure)
        write_jsonl(
            staging / "references" / "direct_r3_agreement_18.jsonl",
            direct_r3_agreements,
        )
        write_jsonl(
            staging / "references" / "direct_adjudication_36.jsonl",
            direct_adjudications,
        )
        handoff_root = staging / "handoff"
        handoff_root.mkdir(parents=True)
        repair_handoffs = build_proposal_repair_handoffs(
            revised_high_risk, handoff_root
        )
        (handoff_root / "ASSIGNMENT.md").write_bytes(
            (
                "# Remaining-100 high-risk repair assignment\n\n"
                "## Reviewer 2\n\n"
                "- `high_risk_proposal_repair_reviewer_2.zip` (3 cases: blocks, attention, inverse)\n\n"
                "Return `high_risk_proposal_repair_reviewer_2.json`.\n\n"
                "## Reviewer 3\n\n"
                "- `high_risk_proposal_repair_reviewer_3.zip` (1 case: shape)\n\n"
                "Return `high_risk_proposal_repair_reviewer_3.json`.\n"
            ).encode("utf-8")
        )
        (handoff_root / "REVIEWER_2_MESSAGE.md").write_bytes(
            "Repair the three cases in the assigned ZIP. Follow REPAIR_INSTRUCTIONS.md, edit only each repair object, preserve all source/audit fields, and return high_risk_proposal_repair_reviewer_2.json only.\n".encode(
                "utf-8"
            )
        )
        (handoff_root / "REVIEWER_3_MESSAGE.md").write_bytes(
            "Repair the one shape case in the assigned ZIP. Follow REPAIR_INSTRUCTIONS.md, edit only the repair object, preserve all source/audit fields, and return high_risk_proposal_repair_reviewer_3.json only.\n".encode(
                "utf-8"
            )
        )
        authority = seal_integrity(
            {
                "base_authority_commit": BASE_AUTHORITY_COMMIT,
                "policy_id": POLICY_ID,
                "schema_id": "D2LRemaining100FollowupResultAuthorityV1",
                "schema_version": "1.0",
                "source_artifacts": {
                    name: {
                        "manifest_physical_sha256": sha256_file(root / "manifest.json"),
                        "manifest_self_sha256": source_manifests[name][
                            "manifest_sha256"
                        ],
                    }
                    for name, root in (
                        ("followup", followup_root),
                        ("initial_intake", initial_intake_root),
                        ("reviewer_3_corrected", reviewer_3_corrected_root),
                    )
                },
            }
        )
        write_json(staging / "authority.json", authority)
        write_json(
            staging / "input_inventory.json",
            seal_integrity(
                {
                    "file_count": len(inventory),
                    "files": sorted(
                        inventory, key=lambda row: row["captured_relative_path"]
                    ),
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LRemaining100FollowupResultInputInventoryV1",
                    "schema_version": "1.0",
                }
            ),
        )
        report = seal_integrity(
            {
                "blocked_case_count": 1,
                "created_at": CREATED_AT,
                "final_glossary_decision": None,
                "high_risk_approved_case_count": len(approved_high_risk),
                "high_risk_revision_required_case_count": len(revised_high_risk),
                "policy_id": POLICY_ID,
                "provider_call_count": 0,
                "ready_stage_a_source_sense_count": status_counts["READY"],
                "reaudit_ready_case_count": len(ready_reaudits),
                "repair_handoffs": repair_handoffs,
                "schema_id": "D2LRemaining100FollowupResultReportV1",
                "schema_version": "1.0",
                "stage_b_gold_autofill_count": 0,
                "status": "FOLLOWUP_RESULTS_ACCEPTED_REPAIR_REQUIRED_ZERO_PROVIDER",
                "total_source_sense_count": len(closure),
                "validated_followup_case_count": 22,
                "validated_result_file_count": len(inventory),
            }
        )
        write_json(staging / "validation_report.json", report)
        (staging / "RELEASE_REPORT.md").write_bytes(
            (
                "# D2L remaining-100 follow-up result\n\n"
                "- Reviewer 4/5 result files validated and captured: 6/6.\n"
                "- Follow-up cases validated: 22/22.\n"
                "- Re-audited cases ready: 12.\n"
                "- High-risk proposals approved: 6.\n"
                "- High-risk proposals requiring narrow repair: 4 (`blocks`, `attention`, `inverse`, `shape`).\n"
                "- Remaining-100 Stage A source senses ready: 95/100.\n"
                "- Evidence-blocked source senses: 1 (`switch`).\n"
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
            "schema_id": "D2LRemaining100FollowupResultManifestV1",
            "schema_version": "1.0",
            "status": "FOLLOWUP_RESULTS_ACCEPTED_REPAIR_REQUIRED_ZERO_PROVIDER",
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from .validate_followup_result import validate_artifact

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
        "status": "FOLLOWUP_RESULTS_ACCEPTED_REPAIR_REQUIRED_ZERO_PROVIDER",
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--followup-root", type=Path, required=True)
    parser.add_argument("--initial-intake-root", type=Path, required=True)
    parser.add_argument("--reviewer-3-corrected-root", type=Path, required=True)
    parser.add_argument("--reviewer-4-response", type=Path, action="append", required=True)
    parser.add_argument("--reviewer-5-response", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path, required=True)
    args = parser.parse_args()
    result = build_followup_result(
        followup_root=args.followup_root,
        initial_intake_root=args.initial_intake_root,
        reviewer_3_corrected_root=args.reviewer_3_corrected_root,
        reviewer_4_responses=args.reviewer_4_response,
        reviewer_5_responses=args.reviewer_5_response,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
