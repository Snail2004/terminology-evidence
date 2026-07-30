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


def blank_proposal_repair(proposal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "repair_notes": "",
        "repair_status": "",
        "revised_proposal": copy.deepcopy(dict(proposal)),
    }


def _write_repair_zip(
    handoff_root: Path,
    batch_id: str,
    payload: Mapping[str, Any],
    instructions: str,
) -> dict[str, Any]:
    batch_root = handoff_root.parent / "repair_batches" / batch_id
    batch_root.mkdir(parents=True, exist_ok=True)
    write_json(batch_root / "repair_input.json", payload)
    (batch_root / "REPAIR_INSTRUCTIONS.md").write_bytes(instructions.encode("utf-8"))
    with tempfile.TemporaryDirectory(prefix=f"{batch_id}-zip-") as temp_name:
        temporary = Path(temp_name)
        write_json(temporary / "repair_input.json", payload)
        (temporary / "REPAIR_INSTRUCTIONS.md").write_bytes(
            instructions.encode("utf-8")
        )
        zip_path = handoff_root / f"{batch_id}.zip"
        build_deterministic_zip(temporary, zip_path)
    return {
        "batch_id": batch_id,
        "case_count": len(payload["cases"]),
        "handoff_zip": zip_path.relative_to(handoff_root.parent).as_posix(),
        "input_path": (batch_root / "repair_input.json")
        .relative_to(handoff_root.parent)
        .as_posix(),
        "reviewer_slot": payload["reviewer_slot"],
    }


def build_proposal_repair_handoffs(
    records: Sequence[Mapping[str, Any]], handoff_root: Path
) -> list[dict[str, Any]]:
    by_reviewer: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        reviewer = str(record["source_result_role"])
        by_reviewer.setdefault(reviewer, []).append(record)
    outputs: list[dict[str, Any]] = []
    for reviewer in sorted(by_reviewer):
        rows = sorted(by_reviewer[reviewer], key=lambda row: str(row["sense_id"]))
        batch_id = f"high_risk_proposal_repair_{reviewer}"
        cases = []
        for row in rows:
            cases.append(
                {
                    "audit": copy.deepcopy(row["audit"]),
                    "audit_result_role": row["audit_result_role"],
                    "audit_result_sha256": row["audit_result_sha256"],
                    "batch_id": batch_id,
                    "case_id": stable_id(
                        "highrisk_proposal_repair_",
                        str(row["sense_id"]),
                        str(row["parent_proposal_record_sha256"]),
                    ),
                    "original_proposal": copy.deepcopy(row["proposal"]),
                    "policy_id": "d2l-remaining-100-high-risk-proposal-repair-v1.0",
                    "proposal_record_sha256": row["parent_proposal_record_sha256"],
                    "provider_call_count": 0,
                    "repair": blank_proposal_repair(row["proposal"]),
                    "schema_id": "D2LRemaining100HighRiskProposalRepairCaseV1",
                    "schema_version": "1.0",
                    "sense_id": row["sense_id"],
                    "source_payload": copy.deepcopy(row["source_payload"]),
                    "source_payload_sha256": row["source_payload_sha256"],
                    "source_result_role": reviewer,
                    "source_term": row["source_term"],
                }
            )
        payload = {
            "allowed_repair_status": ["COMPLETE"],
            "batch_id": batch_id,
            "case_count": len(cases),
            "cases": cases,
            "policy_id": "d2l-remaining-100-high-risk-proposal-repair-v1.0",
            "provider_call_count": 0,
            "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REPAIR_OBJECTS_FILLED",
            "reviewer_slot": reviewer,
            "schema_id": "D2LRemaining100HighRiskProposalRepairBatchV1",
            "schema_version": "1.0",
            "stage_b_gold_autofill_count": 0,
            "status": "AWAITING_NARROW_PROPOSAL_REPAIR",
        }
        instructions = (
            "# Narrow high-risk proposal repair\n\n"
            "Repair every case using only the supplied source payload and audit. Edit "
            "only each `repair` object. Keep `repair.revised_proposal` as a complete "
            "proposal, preserve temporary child IDs, and retain an exact one-time "
            "partition of source candidates and contexts. Change only the child fields "
            "identified by the audit, set `repair_status` to `COMPLETE`, and explain the "
            "change in `repair_notes`. Synthetic or boundary-only contexts are never "
            "positive evidence. Do not add Stage B gold, ranks, winners, or final "
            "glossary decisions. Return the completed JSON file only.\n"
        )
        outputs.append(
            _write_repair_zip(handoff_root, batch_id, payload, instructions)
        )
    return outputs
