from __future__ import annotations

from collections import OrderedDict
from typing import Any

from common import sha256_object


CASE_SCHEMA_ID = "D2LCSTAIStageAPreReviewCaseV1"
CASE_POLICY_ID = "d2l_cst_ai_stage_a_prereview_v1_2"
REVIEW_SCHEMA_ID = "D2LCSTParallelReviewRecordV1"
REVIEW_POLICY_ID = "d2l_cst_parallel_three_review_files_v1_1"
STAGE_A_WORKFLOW_POLICY_ID = "d2l_cst_three_reviewer_human_review_v1_4"
BATCH_POLICY_ID = "d2l_cst_stage_a_split_safe_batches_v1"

SOURCE_FIELDS = [
    "workflow_policy_id",
    "annotation_unit",
    "term_id",
    "sense_id",
    "split",
    "stratum",
    "source_term",
    "model_definition_en",
    "model_definition_confidence",
    "model_part_of_speech",
    "model_part_of_speech_confidence",
    "definition_evidence_context_ids",
    "part_of_speech_evidence_context_ids",
    "source_record_sha256",
]

GROUP_FIELDS = OrderedDict(
    (
        ("primary", "primary_context_ids"),
        ("backup", "backup_context_ids"),
        ("contrastive", "contrastive_context_ids"),
        ("definition", "definition_evidence_context_ids"),
        ("part_of_speech", "part_of_speech_evidence_context_ids"),
    )
)

CASE_CSV_FIELDS = [
    "schema_id",
    "policy_id",
    "case_sha256",
    "source_payload_sha256",
    "scope_id",
    "term_id",
    "sense_id",
    "source_term",
    "split",
    "model_definition_en",
    "model_definition_confidence",
    "model_part_of_speech",
    "model_part_of_speech_confidence",
    "surfaces",
]

CONTEXT_CSV_FIELDS = [
    "case_sha256",
    "term_id",
    "sense_id",
    "context_id",
    "context_groups",
    "block_id",
    "chapter_id",
    "sentence_id",
    "context_role",
    "context_slot",
    "context_type_proposal",
    "sense_relation",
    "matched_surface_exact",
    "content_sha256",
    "context_sha256",
    "source_text",
]

REVIEW_CSV_FIELDS = [
    "schema_id",
    "policy_id",
    "case_sha256",
    "source_payload_sha256",
    "term_id",
    "sense_id",
    "definition_status",
    "effective_definition_en",
    "part_of_speech_status",
    "effective_part_of_speech",
    "scope_note",
    "evidence_context_ids",
    "confidence",
    "rationale",
    "risk_flags",
]


def source_payload(sense: dict[str, Any]) -> dict[str, str]:
    return {
        "workflow_policy_id": STAGE_A_WORKFLOW_POLICY_ID,
        "annotation_unit": "SENSE_CONTRACT",
        "term_id": str(sense["term_id"]),
        "sense_id": str(sense["sense_id"]),
        "split": str(sense["split"]),
        "stratum": str(sense["stratum"]),
        "source_term": str(sense["source_term"]),
        "model_definition_en": str(sense["definition"]),
        "model_definition_confidence": str(sense["definition_confidence"]),
        "model_part_of_speech": str(sense["part_of_speech"]),
        "model_part_of_speech_confidence": str(
            sense["part_of_speech_confidence"]
        ),
        "definition_evidence_context_ids": "|".join(
            sense.get("definition_evidence_context_ids") or []
        ),
        "part_of_speech_evidence_context_ids": "|".join(
            sense.get("part_of_speech_evidence_context_ids") or []
        ),
        "source_record_sha256": str(sense["term_sense_sha256"]),
    }


def project_context(context: dict[str, Any]) -> dict[str, Any]:
    provenance = context.get("provenance") or {}
    source_text = str(context["source_text"])
    match_start = context.get("match_start")
    match_end = context.get("match_end")
    matched_surface_exact = context.get("matched_surface_exact")
    if (
        not matched_surface_exact
        and isinstance(match_start, int)
        and isinstance(match_end, int)
        and 0 <= match_start < match_end <= len(source_text)
    ):
        matched_surface_exact = source_text[match_start:match_end]
    if not matched_surface_exact:
        matched_surface_exact = context.get("matched_surface", "")
    return {
        "block_id": context.get("block_id", provenance.get("block_id", "")),
        "chapter_id": context.get(
            "chapter_id", provenance.get("chapter_id", "")
        ),
        "content_sha256": context["content_sha256"],
        "context_id": context["context_id"],
        "context_role": context["context_role"],
        "context_sha256": context["context_sha256"],
        "context_slot": context["context_slot"],
        "context_type_proposal": context.get("context_type", ""),
        "matched_surface_exact": matched_surface_exact,
        "sense_relation": context["sense_relation"],
        "sentence_id": context.get(
            "sentence_id", provenance.get("sentence_id", "")
        ),
        "source_text": source_text,
    }


def build_case(
    sense: dict[str, Any],
    contexts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload = source_payload(sense)
    source_payload_sha256 = sha256_object(
        {field: payload[field] for field in SOURCE_FIELDS}
    )
    evidence_contexts: dict[str, list[dict[str, Any]]] = {}
    missing_evidence_context_ids: dict[str, list[str]] = {}
    for group, field in GROUP_FIELDS.items():
        missing = [
            context_id
            for context_id in sense.get(field) or []
            if context_id not in contexts
        ]
        if missing:
            missing_evidence_context_ids[group] = missing
        evidence_contexts[group] = [
            project_context(contexts[context_id])
            for context_id in sense.get(field) or []
            if context_id in contexts
        ]
    case = {
        "schema_id": CASE_SCHEMA_ID,
        "policy_id": CASE_POLICY_ID,
        "scope_id": sense["scope_id"],
        "term_id": sense["term_id"],
        "sense_id": sense["sense_id"],
        "source_term": sense["source_term"],
        "surfaces": sense.get("surfaces") or [],
        "split": sense["split"],
        "model_definition_en": sense["definition"],
        "model_definition_confidence": sense["definition_confidence"],
        "model_part_of_speech": sense["part_of_speech"],
        "model_part_of_speech_confidence": sense["part_of_speech_confidence"],
        "source_term_sense_sha256": sense["term_sense_sha256"],
        "source_payload_sha256": source_payload_sha256,
        "evidence_contexts": evidence_contexts,
    }
    if missing_evidence_context_ids:
        case["missing_evidence_context_ids"] = missing_evidence_context_ids
    case["case_sha256"] = sha256_object(case)
    return case


def case_csv_row(case: dict[str, Any]) -> dict[str, Any]:
    return {
        **case,
        "surfaces": " | ".join(case.get("surfaces") or []),
    }


def flattened_context_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for group in GROUP_FIELDS:
        for context in case["evidence_contexts"][group]:
            context_id = context["context_id"]
            if context_id not in grouped:
                grouped[context_id] = {
                    "case_sha256": case["case_sha256"],
                    "term_id": case["term_id"],
                    "sense_id": case["sense_id"],
                    **context,
                    "context_groups": [],
                }
            grouped[context_id]["context_groups"].append(group)
    return [
        {
            **grouped[context_id],
            "context_groups": ";".join(grouped[context_id]["context_groups"]),
        }
        for context_id in sorted(grouped)
    ]


def blank_review_row(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": REVIEW_SCHEMA_ID,
        "policy_id": REVIEW_POLICY_ID,
        "case_sha256": case["case_sha256"],
        "source_payload_sha256": case["source_payload_sha256"],
        "term_id": case["term_id"],
        "sense_id": case["sense_id"],
        "definition_status": "",
        "effective_definition_en": "",
        "part_of_speech_status": "",
        "effective_part_of_speech": "",
        "scope_note": "",
        "evidence_context_ids": "",
        "confidence": "",
        "rationale": "",
        "risk_flags": "",
    }
