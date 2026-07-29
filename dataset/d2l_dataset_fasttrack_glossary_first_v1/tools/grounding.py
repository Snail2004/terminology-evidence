from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .common import seal_record, sha256_bytes, canonical_json_bytes


RISK_CLASSES = {
    "R0_CLEAR",
    "R1_QUALIFIED",
    "R2_MISSING",
    "R3_AMBIGUOUS",
    "R4_SPLIT_OR_POS_RISK",
}

KNOWN_R4_TERMS = {"in place"}
KNOWN_R3_TERMS = {"adam", "fully-connected layers", "contexts"}


def group_by(records: Iterable[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record[field])].append(record)
    return dict(grouped)


def real_positive_context(context: dict[str, Any]) -> bool:
    provenance = context.get("provenance") or {}
    return (
        str(context.get("context_id", "")).startswith("ctx_")
        and context.get("sense_relation") == "SAME_SENSE"
        and context.get("context_role") in {"PRIMARY", "BACKUP"}
        and bool(provenance.get("block_id"))
        and bool(context.get("source_text"))
    )


def active_positive_ids(
    sense: dict[str, Any],
    contexts_by_id: dict[str, dict[str, Any]],
    quarantined_blocks: set[str],
) -> list[str]:
    ordered_ids = list(dict.fromkeys(sense.get("primary_context_ids", []) + sense.get("backup_context_ids", [])))
    active: list[str] = []
    for context_id in ordered_ids:
        context = contexts_by_id.get(context_id)
        if not context or not real_positive_context(context):
            continue
        if context["provenance"]["block_id"] in quarantined_blocks:
            continue
        active.append(context_id)
    return active


def classify_risk(
    sense: dict[str, Any],
    mapping: dict[str, Any],
    active_context_count: int,
) -> tuple[str, list[str]]:
    term = str(sense["source_term"]).casefold()
    status = str(mapping["glossary_match_status"])
    reasons: list[str] = []
    if term in KNOWN_R4_TERMS:
        return "R4_SPLIT_OR_POS_RISK", ["KNOWN_SPLIT_OR_POS_CASE"]
    if term in KNOWN_R3_TERMS:
        return "R3_AMBIGUOUS", ["KNOWN_BLIND_OR_LEGACY_ADJUDICATION_CASE"]
    if active_context_count == 0:
        return "R4_SPLIT_OR_POS_RISK", ["NO_ACTIVE_REAL_POSITIVE_CONTEXT"]
    if status == "AMBIGUOUS_MULTI_SENSE":
        reasons.append("MULTIPLE_GLOSSARY_ENTRIES")
    if sense.get("stratum") in {"ambiguous", "collision_or_multi_target"}:
        reasons.append(f"V3_STRATUM_{str(sense['stratum']).upper()}")
    if reasons:
        return "R3_AMBIGUOUS", reasons
    if status == "GLOSSARY_MISSING":
        return "R2_MISSING", ["NO_GLOSSARY_MATCH"]
    if status == "GLOSSARY_QUALIFIED":
        return "R1_QUALIFIED", ["QUALIFIER_REQUIRES_CONFIRMATION"]
    if status in {"GLOSSARY_EXACT", "GLOSSARY_VARIANT"}:
        return "R0_CLEAR", ["CLEAR_V3_STRATUM_WITH_REAL_POSITIVE_CONTEXT"]
    raise ValueError(f"unsupported mapping status: {status}")


def build_projection(
    sense: dict[str, Any],
    mapping: dict[str, Any],
    risk_class: str,
    risk_reasons: list[str],
    active_ids: list[str],
    contexts_by_id: dict[str, dict[str, Any]],
    parent_dataset_manifest_sha256: str,
    blind_case_refs: dict[str, str],
) -> dict[str, Any]:
    if risk_class not in RISK_CLASSES:
        raise ValueError(risk_class)
    definition_ids = [
        context_id
        for context_id in sense.get("definition_evidence_context_ids", [])
        if context_id in active_ids
    ]
    pos_ids = [
        context_id
        for context_id in sense.get("part_of_speech_evidence_context_ids", [])
        if context_id in active_ids
    ]
    if not definition_ids:
        definition_ids = active_ids[: min(3, len(active_ids))]
    if not pos_ids:
        pos_ids = active_ids[: min(2, len(active_ids))]
    boundary_ids = [
        context_id
        for context_id in sense.get("contrastive_context_ids", [])
        if context_id in contexts_by_id
    ]
    source_payload = {
        "definition": sense["definition"],
        "part_of_speech": sense["part_of_speech"],
        "positive_definition_evidence_ids": definition_ids,
        "positive_pos_evidence_ids": pos_ids,
        "source_term": sense["source_term"],
        "term_sense_sha256": sense["term_sense_sha256"],
    }
    record = {
        "schema_id": "D2LFastTrackEffectiveSenseProjectionV1",
        "schema_version": "1.0.0",
        "policy_id": "dataset-fasttrack-glossary-first-v1.0",
        "term_id": sense["term_id"],
        "sense_id": sense["sense_id"],
        "scope_id": sense["scope_id"],
        "split": sense["split"],
        "source_term": sense["source_term"],
        "effective_definition_en": sense["definition"],
        "effective_part_of_speech": sense["part_of_speech"],
        "scope_note": None,
        "positive_definition_evidence_ids": definition_ids,
        "positive_pos_evidence_ids": pos_ids,
        "boundary_context_ids": boundary_ids,
        "glossary_match_status": mapping["glossary_match_status"],
        "glossary_candidate_vi": mapping["glossary_candidate_vi"],
        "risk_class": risk_class,
        "risk_reasons": risk_reasons,
        "review_status": "UNRESOLVED",
        "review_artifact_ref": blind_case_refs.get(sense["sense_id"]),
        "source_payload_sha256": sha256_bytes(canonical_json_bytes(source_payload)),
        "parent_dataset_manifest_sha256": parent_dataset_manifest_sha256,
        "parent_term_sense_sha256": sense["term_sense_sha256"],
        "official_effective_sense_contract_emitted": False,
        "final_glossary_decision": None,
    }
    return seal_record(record, "effective_sense_projection_sha256")


def build_source_grounding_report(
    mappings: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    leakage_records: list[dict[str, Any]],
) -> dict[str, Any]:
    mapping_counts = Counter(row["glossary_match_status"] for row in mappings)
    risk_counts = Counter(row["risk_class"] for row in risk_rows)
    zero_context = [row["sense_id"] for row in risk_rows if int(row["active_real_positive_context_count"]) == 0]
    report = {
        "schema_id": "D2LFastTrackSourceGroundingReportV1",
        "policy_id": "dataset-fasttrack-glossary-first-v1.0",
        "artifact_status": "BLOCKED_PENDING_RISK_REVIEW_AND_ADJUDICATION",
        "sense_count": len(mappings),
        "mapping_counts": dict(sorted(mapping_counts.items())),
        "risk_counts": dict(sorted(risk_counts.items())),
        "real_positive_context_coverage_count": len(projections) - len(zero_context),
        "real_positive_context_zero_sense_ids": zero_context,
        "synthetic_positive_context_count": 0,
        "quarantined_cross_split_cluster_count": len(leakage_records),
        "official_effective_sense_contract_count": 0,
        "unresolved_sense_count": sum(row["review_status"] == "UNRESOLVED" for row in projections),
        "final_glossary_decision": None,
    }
    return seal_record(report, "report_sha256")


def build_adjudication_records(senses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_term = {str(sense["source_term"]).casefold(): sense for sense in senses}
    specifications = [
        (
            "adam",
            "LEGACY_DEFINITION_CORRECTION_REQUIRES_FORMAL_PROVENANCE",
            "An optimization algorithm used to train models.",
            "ADJUDICATED_PROPOSED_PENDING_PROVENANCE",
        ),
        (
            "fully-connected layers",
            "SYNTHETIC_CONTRASTIVE_CANNOT_SUPPORT_ALL_TO_ALL_DETAIL",
            None,
            "ADJUDICATION_REQUIRED",
        ),
        (
            "in place",
            "CHILD_SENSE_AND_POS_RESOLUTION_REQUIRED",
            None,
            "SPLIT_REQUIRED",
        ),
        (
            "contexts",
            "BLIND_REVIEW_SPLIT_DISAGREEMENT_2_OF_3",
            None,
            "ADJUDICATION_REQUIRED",
        ),
    ]
    records: list[dict[str, Any]] = []
    for term, reason, proposed_definition, status in specifications:
        sense = by_term.get(term)
        record = {
            "schema_id": "D2LFastTrackStageAAdjudicationRecordV1",
            "policy_id": "dataset-fasttrack-glossary-first-v1.0",
            "source_term": term,
            "term_id": sense.get("term_id") if sense else None,
            "sense_id": sense.get("sense_id") if sense else None,
            "reason_code": reason,
            "proposed_effective_definition_en": proposed_definition,
            "adjudication_status": status,
            "official_contract_emitted": False,
            "final_glossary_decision": None,
        }
        records.append(seal_record(record))
    return records
