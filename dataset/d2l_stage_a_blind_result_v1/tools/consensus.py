from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from common import read_jsonl, seal, validate_self_hash
from intake import normalize_part_of_speech


ADJUDICATION_REASONS = {
    "contexts": ["SPLIT_DECISION_2_OF_3"],
    "fully-connected layers": ["DEFINITION_DETAIL_REQUIRES_EVIDENCE_ADJUDICATION"],
    "in place": ["CHILD_SENSE_AND_POS_RESOLUTION_REQUIRED"],
}


def _vote(values: list[str]) -> tuple[str, int, bool]:
    counts = Counter(values)
    winner, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return winner, count, len(counts) == 1


def resolve_blind_consensus(
    *,
    cases: list[dict[str, str]],
    normalized_by_slot: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_slot = {
        slot: {row["blind_case_id"]: row for row in rows}
        for slot, rows in normalized_by_slot.items()
    }
    records: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda value: value["blind_case_id"]):
        case_id = case["blind_case_id"]
        reviews = [by_slot[slot][case_id] for slot in (1, 2, 3)]
        split_winner, split_count, split_unanimous = _vote(
            [row["split_recommendation"] for row in reviews]
        )
        pos_winner, pos_count, pos_unanimous = _vote(
            [row["blind_part_of_speech_normalized"] for row in reviews]
        )
        definition_values = [row["blind_definition_normalized"] for row in reviews]
        reasons = ADJUDICATION_REASONS.get(case["source_term"], [])
        records.append(
            seal(
                {
                    "schema_id": "D2LCSTBlindConsensusRecordV1",
                    "policy_id": "d2l_cst_stage_a_blind_result_consensus_v1",
                    "blind_case_id": case_id,
                    "case_sha256": case["case_sha256"],
                    "term_id": case["term_id"],
                    "sense_id": case["sense_id"],
                    "source_term": case["source_term"],
                    "selection_stratum": case["selection_stratum"],
                    "review_record_sha256s": [row["record_sha256"] for row in reviews],
                    "split_vote": {
                        "winner": split_winner,
                        "count": split_count,
                        "unanimous": split_unanimous,
                        "values": [row["split_recommendation"] for row in reviews],
                    },
                    "part_of_speech_vote": {
                        "winner": pos_winner if pos_count >= 2 else None,
                        "count": pos_count,
                        "unanimous": pos_unanimous,
                        "values": [row["blind_part_of_speech_normalized"] for row in reviews],
                    },
                    "definition_exact_agreement": len(set(definition_values)) == 1,
                    "blind_definitions": [row["blind_definition_en"] for row in reviews],
                    "mean_confidence": round(
                        sum(float(row["confidence"]) for row in reviews) / 3,
                        6,
                    ),
                    "adjudication_reason_codes": reasons,
                    "stage_a_status": (
                        "ADJUDICATION_REQUIRED"
                        if reasons
                        else "PAIRED_COMPARISON_READY_PENDING_PROVENANCE"
                    ),
                    "reviewer_provenance_status": "PENDING_OWNER_ATTESTATION",
                    "final_glossary_decision": None,
                },
                "record_sha256",
            )
        )
    return records


def load_anchor_records(
    *,
    anchor_reference_path: Path,
    anchored_consensus_path: Path,
) -> dict[str, dict[str, Any]]:
    references = read_jsonl(anchor_reference_path)
    anchored_records = read_jsonl(anchored_consensus_path)
    by_hash: dict[str, dict[str, Any]] = {}
    for record in anchored_records:
        if not validate_self_hash(record, "record_sha256"):
            raise ValueError("Anchored consensus contains an invalid record self-hash")
        by_hash[record["record_sha256"]] = record
    result: dict[str, dict[str, Any]] = {}
    for reference in references:
        if not validate_self_hash(reference, "record_sha256"):
            raise ValueError("Anchor reference contains an invalid record self-hash")
        anchored = by_hash.get(reference["anchored_consensus_record_sha256"])
        if anchored is None:
            raise ValueError("Anchor reference points to a missing consensus record")
        if anchored.get("sense_id") != reference.get("sense_id"):
            raise ValueError("Anchor reference sense binding mismatch")
        result[reference["sense_id"]] = {
            "reference": reference,
            "anchored": anchored,
        }
    return result


def compare_with_anchors(
    *,
    consensus_records: list[dict[str, Any]],
    anchors: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for blind in consensus_records:
        binding = anchors.get(blind["sense_id"])
        if binding is None:
            raise ValueError(f"Missing anchored record for {blind['sense_id']}")
        anchor = binding["anchored"]
        proposal = anchor.get("consensus_proposal") or {}
        directive = anchor.get("semantic_directive") or {}
        anchored_split = "SPLIT" if directive.get("directive") == "SPLIT_REQUIRED" else "NO_SPLIT"
        anchored_pos = normalize_part_of_speech(str(proposal.get("effective_part_of_speech", "")))
        blind_pos = (blind.get("part_of_speech_vote") or {}).get("winner")
        reasons = blind["adjudication_reason_codes"]
        comparisons.append(
            seal(
                {
                    "schema_id": "D2LCSTBlindAnchoredComparisonV1",
                    "policy_id": "d2l_cst_stage_a_blind_anchored_comparison_v1",
                    "blind_consensus_record_sha256": blind["record_sha256"],
                    "anchor_reference_record_sha256": binding["reference"]["record_sha256"],
                    "anchored_consensus_record_sha256": anchor["record_sha256"],
                    "term_id": blind["term_id"],
                    "sense_id": blind["sense_id"],
                    "source_term": blind["source_term"],
                    "selection_stratum": blind["selection_stratum"],
                    "blind_split_majority": blind["split_vote"]["winner"],
                    "anchored_split": anchored_split,
                    "split_majority_matches_anchor": (
                        blind["split_vote"]["winner"] == anchored_split
                    ),
                    "blind_pos_consensus": blind_pos,
                    "anchored_pos": anchored_pos,
                    "pos_consensus_matches_anchor": (
                        blind_pos == anchored_pos if blind_pos is not None else None
                    ),
                    "anchored_definition_en": proposal.get("effective_definition_en"),
                    "blind_definitions": blind["blind_definitions"],
                    "definition_comparison_status": (
                        "STAGE_A_ADJUDICATION_REQUIRED"
                        if reasons
                        else "SEMANTIC_EQUIVALENCE_NOT_AUTO_ASSERTED"
                    ),
                    "adjudication_reason_codes": reasons,
                    "anchoring_assessment_status": (
                        "INCONCLUSIVE_PENDING_PROVENANCE_AND_SEMANTIC_ADJUDICATION"
                    ),
                    "final_glossary_decision": None,
                },
                "record_sha256",
            )
        )
    return comparisons
