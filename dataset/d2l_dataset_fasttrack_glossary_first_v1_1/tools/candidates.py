from __future__ import annotations

from collections import defaultdict
from typing import Any

from .common import seal_record
from .glossary import normalize_text


SOURCE_TYPE_BY_METHOD = {
    "RECORDED_PIPELINE_OUTPUT": "RECORDED_PIPELINE_OUTPUT",
    "MODEL_GENERATED_SUPPORT_SET_V2": "MODEL_PROPOSAL",
}


def normalize_candidates(
    candidates: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    mapping_by_sense: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    slot_by_candidate = {row["candidate_instance_id"]: row for row in slots}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["sense_id"]].append(candidate)

    output: list[dict[str, Any]] = []
    for sense_id in sorted(grouped):
        source = grouped[sense_id]
        if len(source) != 3:
            raise ValueError(f"{sense_id}: expected 3 candidates, found {len(source)}")
        glossary_target = mapping_by_sense[sense_id].get("glossary_candidate_vi")

        def priority(candidate: dict[str, Any]) -> tuple[int, int, str]:
            slot = slot_by_candidate[candidate["candidate_instance_id"]]
            matches_glossary = bool(
                glossary_target
                and normalize_text(candidate["candidate_target_vi"])
                == normalize_text(str(glossary_target))
            )
            recorded = candidate["formation_method"] == "RECORDED_PIPELINE_OUTPUT"
            return (0 if matches_glossary else 1 if recorded else 2, int(slot["slot_number"]), candidate["candidate_instance_id"])

        ordered = sorted(source, key=priority)
        for role, candidate in zip(("A", "B", "C"), ordered, strict=True):
            slot = slot_by_candidate[candidate["candidate_instance_id"]]
            formation_method = candidate["formation_method"]
            record = {
                "schema_id": "D2LFastTrackCandidateProvenanceV1",
                "policy_id": "dataset-fasttrack-glossary-first-v1.1",
                "term_id": candidate["term_id"],
                "sense_id": sense_id,
                "candidate_id": candidate["candidate_instance_id"],
                "candidate_role": role,
                "candidate_vi": candidate["candidate_target_vi"],
                "candidate_source_type": SOURCE_TYPE_BY_METHOD.get(formation_method, "MODEL_PROPOSAL"),
                "candidate_source_ref": candidate.get("formation_provenance", []),
                "source_candidate_slot_number": slot["slot_number"],
                "source_candidate_instance_sha256": candidate["candidate_instance_sha256"],
                "source_candidate_slot_sha256": slot["candidate_slot_sha256"],
                "glossary_target_match": bool(
                    glossary_target
                    and normalize_text(candidate["candidate_target_vi"])
                    == normalize_text(str(glossary_target))
                ),
                "model_provider": None,
                "prompt_sha256": None,
                "generation_run_id": None,
                "generation_timestamp": candidate.get("created_at"),
                "candidate_gold_label": None,
                "final_glossary_decision": None,
            }
            output.append(seal_record(record, "candidate_provenance_sha256"))
    return output
