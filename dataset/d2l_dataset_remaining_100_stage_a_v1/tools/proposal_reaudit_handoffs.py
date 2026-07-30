from __future__ import annotations

import copy
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    write_json,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.spec import stable_id

from .followup_handoffs import blank_proposal_audit


def _write_reaudit_zip(
    handoff_root: Path,
    batch_id: str,
    payload: Mapping[str, Any],
    instructions: str,
) -> dict[str, Any]:
    batch_root = handoff_root.parent / "reaudit_batches" / batch_id
    batch_root.mkdir(parents=True, exist_ok=True)
    write_json(batch_root / "auditor_input.json", payload)
    (batch_root / "INSTRUCTIONS.md").write_bytes(
        instructions.encode("utf-8")
    )
    with tempfile.TemporaryDirectory(prefix=f"{batch_id}-zip-") as temp_name:
        temporary = Path(temp_name)
        write_json(temporary / "auditor_input.json", payload)
        (temporary / "INSTRUCTIONS.md").write_bytes(
            instructions.encode("utf-8")
        )
        zip_path = handoff_root / f"{batch_id}.zip"
        build_deterministic_zip(temporary, zip_path)
    return {
        "batch_id": batch_id,
        "case_count": len(payload["cases"]),
        "handoff_zip": zip_path.relative_to(handoff_root.parent).as_posix(),
        "input_path": (batch_root / "auditor_input.json")
        .relative_to(handoff_root.parent)
        .as_posix(),
        "reviewer_slot": payload["reviewer_slot"],
    }


def build_proposal_reaudit_handoffs(
    records: Sequence[Mapping[str, Any]], handoff_root: Path
) -> list[dict[str, Any]]:
    by_reviewer: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        reviewer = str(record["reaudit_reviewer_role"])
        by_reviewer.setdefault(reviewer, []).append(record)
    outputs: list[dict[str, Any]] = []
    for reviewer in sorted(by_reviewer):
        rows = sorted(by_reviewer[reviewer], key=lambda row: str(row["sense_id"]))
        batch_id = f"proposal_reaudit_{reviewer}"
        cases = []
        for row in rows:
            cases.append(
                {
                    "audit": blank_proposal_audit(),
                    "batch_id": batch_id,
                    "case_id": stable_id(
                        "highrisk_proposal_reaudit_",
                        str(row["sense_id"]),
                        str(row["record_sha256"]),
                    ),
                    "parent_repair_record_sha256": row["record_sha256"],
                    "policy_id": "d2l-remaining-100-high-risk-proposal-reaudit-v1.0",
                    "prior_audit": copy.deepcopy(row["prior_audit"]),
                    "proposal_repair": copy.deepcopy(row["proposal_repair"]),
                    "provider_call_count": 0,
                    "repaired_proposal": copy.deepcopy(row["repaired_proposal"]),
                    "schema_id": "D2LRemaining100HighRiskProposalReauditCaseV1",
                    "schema_version": "1.0",
                    "sense_id": row["sense_id"],
                    "source_payload": copy.deepcopy(row["source_payload"]),
                    "source_payload_sha256": row["source_payload_sha256"],
                    "source_term": row["source_term"],
                }
            )
        payload = {
            "allowed_audit_decisions": ["APPROVE", "REVISE", "BLOCK"],
            "batch_id": batch_id,
            "case_count": len(cases),
            "cases": cases,
            "independence_mode": "DISTINCT_FROM_PROPOSAL_REPAIR_AUTHOR",
            "policy_id": "d2l-remaining-100-high-risk-proposal-reaudit-v1.0",
            "provider_call_count": 0,
            "return_contract": "RETURN_THIS_JSON_WITH_ONLY_AUDIT_OBJECTS_FILLED",
            "reviewer_slot": reviewer,
            "schema_id": "D2LRemaining100HighRiskProposalReauditBatchV1",
            "schema_version": "1.0",
            "stage_b_gold_autofill_count": 0,
            "status": "AWAITING_DISTINCT_PROPOSAL_REAUDIT",
        }
        instructions = (
            "# Independent repaired-proposal re-audit\n\n"
            "Re-audit every repaired proposal against the supplied real source contexts, "
            "the prior audit, and the narrow repair. Fill only `audit` and preserve every "
            "other field. Use APPROVE only if the prior issue is fully closed, child IDs "
            "and the exact candidate/context partition remain valid, and no synthetic or "
            "boundary-only context is treated as positive evidence. Use REVISE for a "
            "specific remaining repairable issue and BLOCK if the supplied real evidence "
            "cannot close it. Do not add Stage B gold, ranks, winners, or final glossary "
            "decisions. Return the completed JSON file only.\n"
        )
        outputs.append(_write_reaudit_zip(handoff_root, batch_id, payload, instructions))
    return outputs
