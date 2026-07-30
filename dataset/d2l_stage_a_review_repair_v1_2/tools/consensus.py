from __future__ import annotations

from collections import Counter
from typing import Any

from common import canonical_json, seal


CORE_FIELDS = (
    "definition_status",
    "effective_definition_en",
    "part_of_speech_status",
    "effective_part_of_speech",
)

SEMANTIC_DIRECTIVES = {
    "Adam": {
        "directive": "ACCEPT_CORRECTION",
        "reason_code": "UNSUPPORTED_DEFINITION_DETAIL_REMOVED",
        "effective_definition_en": "An optimization algorithm used to train models.",
        "effective_part_of_speech": "proper_noun",
    },
    "fully-connected layers": {
        "directive": "ADJUDICATION_REQUIRED",
        "reason_code": "UNSUPPORTED_DETAIL_SYNTHETIC_ONLY",
        "blocked_definition_en": "layers in which each output unit is connected to all input units from the previous layer",
        "proposal_definition_en": "neural network layers, implemented here as Linear modules, that can be stacked to form multilayer perceptrons",
    },
    "in place": {
        "directive": "SPLIT_REQUIRED",
        "reason_code": "SENSE_AND_POS_CONFLATION",
        "proposed_children": [
            "direct modification without creating a replacement",
            "already established, available, or set up",
        ],
    },
}


def core_key(decision: dict[str, Any]) -> str:
    return canonical_json({field: decision.get(field, "") for field in CORE_FIELDS})


def resolve_evidence_aware_consensus(
    *,
    term: str,
    term_id: str,
    sense_id: str,
    case_sha256: str,
    decisions: list[dict[str, Any]],
    evidence_reports: list[dict[str, Any]],
    provenance_status: str,
) -> dict[str, Any]:
    keys = [core_key(decision) for decision in decisions]
    winning_key, count = Counter(keys).most_common(1)[0]
    agreement = (
        "AGREEMENT_3_OF_3"
        if count == 3
        else ("MAJORITY_2_OF_3" if count == 2 else "NO_MAJORITY")
    )
    winner = decisions[keys.index(winning_key)] if count >= 2 else None
    blockers: list[str] = []
    directive = SEMANTIC_DIRECTIVES.get(term)
    if directive:
        blockers.append(directive["reason_code"])
    if count < 3:
        blockers.append("NON_UNANIMOUS_CORE_DECISION")
    if provenance_status != "PASS":
        blockers.append("REVIEWER_PROVENANCE_INCOMPLETE")
    if any(report.get("blocker_codes") for report in evidence_reports):
        blockers.append("EVIDENCE_ROLE_CONFIRMATION_REQUIRED")
    if any(
        decision.get("definition_status") in {"REJECTED"}
        or decision.get("part_of_speech_status") in {"UNCERTAIN", "REJECTED"}
        for decision in decisions
    ):
        blockers.append("UNRESOLVED_REVIEW_STATUS")

    if directive and directive["directive"] == "SPLIT_REQUIRED":
        finalization_status = "SPLIT_REQUIRED"
    elif directive or count < 3:
        finalization_status = "ADJUDICATION_REQUIRED"
    elif blockers:
        finalization_status = "BLOCKED_PENDING_REPAIR_INPUTS"
    else:
        finalization_status = "AUTO_FINALIZATION_ELIGIBLE"

    return seal(
        {
            "schema_id": "D2LCSTEvidenceAwareConsensusRecordV1",
            "merge_policy_id": "d2l_cst_stage_a_evidence_aware_consensus_v1_2",
            "term_id": term_id,
            "sense_id": sense_id,
            "source_term": term,
            "case_sha256": case_sha256,
            "reviewer_decisions": [
                {field: decision.get(field, "") for field in CORE_FIELDS}
                for decision in decisions
            ],
            "agreement": agreement,
            "consensus_proposal": (
                {field: winner.get(field, "") for field in CORE_FIELDS}
                if winner is not None
                else None
            ),
            "semantic_directive": directive,
            "provenance_status": provenance_status,
            "finalization_status": finalization_status,
            "blocker_codes": sorted(set(blockers)),
            "final_glossary_decision": None,
        },
        "record_sha256",
    )
