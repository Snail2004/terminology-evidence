from __future__ import annotations

import copy
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    write_json,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.spec import (
    ALLOWED_SENSE_STATUS,
    ALLOWED_STANDARD_DECISIONS,
    REVIEW_FIELDS,
)


def blank_standard_review() -> dict[str, Any]:
    review: dict[str, Any] = {field: "" for field in REVIEW_FIELDS}
    review["candidate_replacements"] = []
    review["invalid_evidence_context_ids"] = []
    review["proposed_split_labels"] = []
    return review


def blank_proposal_audit() -> dict[str, Any]:
    return {
        "audit_decision": "",
        "audit_notes": "",
        "audit_status": "",
        "invalid_child_sense_ids": [],
    }


def _write_handoff_zip(
    handoff_root: Path,
    batch_id: str,
    input_name: str,
    payload: Mapping[str, Any],
    instructions: str,
) -> dict[str, Any]:
    batch_root = handoff_root.parent / "review_batches" / batch_id
    batch_root.mkdir(parents=True, exist_ok=True)
    write_json(batch_root / input_name, payload)
    (batch_root / "REVIEW_INSTRUCTIONS.md").write_bytes(instructions.encode("utf-8"))
    with tempfile.TemporaryDirectory(prefix=f"{batch_id}-zip-") as temp_name:
        temp = Path(temp_name)
        write_json(temp / input_name, payload)
        (temp / "REVIEW_INSTRUCTIONS.md").write_bytes(instructions.encode("utf-8"))
        zip_path = handoff_root / f"{batch_id}.zip"
        build_deterministic_zip(temp, zip_path)
    return {
        "batch_id": batch_id,
        "case_count": len(payload["cases"]),
        "handoff_zip": zip_path.relative_to(handoff_root.parent).as_posix(),
        "input_path": (batch_root / input_name)
        .relative_to(handoff_root.parent)
        .as_posix(),
    }


def build_reaudit_handoffs(
    records: Sequence[Mapping[str, Any]], handoff_root: Path
) -> list[dict[str, Any]]:
    grouped = (records[:5], records[5:10], records[10:])
    outputs: list[dict[str, Any]] = []
    for index, group in enumerate(grouped, 1):
        if not group:
            continue
        batch_id = f"followup_reaudit_batch_{index:03d}"
        cases = []
        for row in group:
            cases.append(
                {
                    "batch_id": batch_id,
                    "case_id": row["reaudit_case_id"],
                    "policy_id": "d2l-remaining-100-followup-blind-reaudit-v1.0",
                    "provider_call_count": 0,
                    "repair_record_sha256": row["record_sha256"],
                    "review": blank_standard_review(),
                    "reviewer_slot": "followup_blind_reauditor",
                    "schema_id": "D2LRemaining100FollowupBlindReauditCaseV1",
                    "schema_version": "1.0",
                    "sense_id": row["sense_id"],
                    "source_payload": copy.deepcopy(row["blind_source_payload"]),
                    "source_payload_sha256": row["blind_source_payload_sha256"],
                }
            )
        payload = {
            "allowed_sense_status": list(ALLOWED_SENSE_STATUS),
            "allowed_standard_decisions": list(ALLOWED_STANDARD_DECISIONS),
            "batch_id": batch_id,
            "case_count": len(cases),
            "cases": cases,
            "independence_mode": "DISTINCT_FROM_SOURCE_REPAIR_OR_PRIOR_REVIEWER",
            "policy_id": "d2l-remaining-100-followup-blind-reaudit-v1.0",
            "provider_call_count": 0,
            "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_OBJECTS_FILLED",
            "reviewer_slot": "followup_blind_reauditor",
            "schema_id": "D2LRemaining100FollowupBlindReauditBatchV1",
            "schema_version": "1.0",
            "stage_b_gold_autofill_count": 0,
            "status": "AWAITING_INDEPENDENT_BLIND_REAUDIT",
        }
        instructions = (
            "# Independent blind re-audit\n\n"
            "Review every case only from the supplied source payload. Fill only each "
            "`review` object and preserve every other field. Synthetic or boundary-only "
            "contexts are never positive evidence. Do not add Stage B labels, ranks, "
            "winners, or final glossary decisions. The reviewer must be distinct from "
            "the person who supplied the repair or prior review. Return the completed "
            "JSON file only.\n"
        )
        outputs.append(
            _write_handoff_zip(
                handoff_root, batch_id, "reviewer_input.json", payload, instructions
            )
        )
    return outputs


def build_high_risk_audit_handoffs(
    records: Sequence[Mapping[str, Any]], handoff_root: Path
) -> list[dict[str, Any]]:
    groups = (records[:4], records[4:8], records[8:])
    outputs: list[dict[str, Any]] = []
    for index, group in enumerate(groups, 1):
        if not group:
            continue
        batch_id = f"high_risk_audit_batch_{index:03d}"
        cases = []
        for row in group:
            cases.append(
                {
                    "audit": blank_proposal_audit(),
                    "batch_id": batch_id,
                    "case_id": row["audit_case_id"],
                    "policy_id": "d2l-remaining-100-high-risk-proposal-audit-v1.0",
                    "proposal": copy.deepcopy(row["proposal"]),
                    "proposal_record_sha256": row["record_sha256"],
                    "provider_call_count": 0,
                    "schema_id": "D2LRemaining100HighRiskProposalAuditCaseV1",
                    "schema_version": "1.0",
                    "sense_id": row["sense_id"],
                    "source_payload": copy.deepcopy(row["blind_source_payload"]),
                    "source_payload_sha256": row["blind_source_payload_sha256"],
                    "source_term": row["source_term"],
                }
            )
        payload = {
            "allowed_audit_decisions": ["APPROVE", "REVISE", "BLOCK"],
            "batch_id": batch_id,
            "case_count": len(cases),
            "cases": cases,
            "independence_mode": "DISTINCT_FROM_PROPOSAL_AUTHOR",
            "policy_id": "d2l-remaining-100-high-risk-proposal-audit-v1.0",
            "provider_call_count": 0,
            "return_contract": "RETURN_THIS_JSON_WITH_ONLY_AUDIT_OBJECTS_FILLED",
            "schema_id": "D2LRemaining100HighRiskProposalAuditBatchV1",
            "schema_version": "1.0",
            "stage_b_gold_autofill_count": 0,
            "status": "AWAITING_INDEPENDENT_HIGH_RISK_PROPOSAL_AUDIT",
        }
        instructions = (
            "# Independent high-risk proposal audit\n\n"
            "Audit every proposal against the supplied source contexts and candidates. "
            "Fill only `audit`. Use APPROVE only when every corrected field or child "
            "sense is evidence-bound and no synthetic context is treated as positive "
            "proof. Use REVISE for a specifically repairable proposal and BLOCK when "
            "the supplied evidence cannot close it. For APPROVE, keep "
            "invalid_child_sense_ids empty. The auditor must be distinct from the "
            "proposal author. Do not add candidate rank, winner, Stage B gold, or final "
            "glossary decisions. Return the completed JSON file only.\n"
        )
        outputs.append(
            _write_handoff_zip(
                handoff_root, batch_id, "auditor_input.json", payload, instructions
            )
        )
    return outputs
