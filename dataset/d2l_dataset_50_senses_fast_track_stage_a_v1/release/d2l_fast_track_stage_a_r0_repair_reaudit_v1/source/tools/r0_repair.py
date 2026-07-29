from __future__ import annotations

import copy
from typing import Any, Mapping

try:
    from .common import canonical_json_bytes, seal_record, sha256_bytes, verify_record
    from .spec import REVIEW_FIELDS
except ImportError:  # pragma: no cover - direct script execution
    from common import canonical_json_bytes, seal_record, sha256_bytes, verify_record  # type: ignore
    from spec import REVIEW_FIELDS  # type: ignore


R0_REPAIR_SPECS: dict[str, dict[str, Any]] = {
    "d2lce_4abd762bcd34d370b4fe6498": {
        "source_term": "BatchNorm",
        "definition_en": None,
        "candidate_replacements": (
            {
                "candidate_id": "candidate_7b163f794ee98b610f2c2b0d",
                "candidate_slot": "candidate_slot_1853a37287ac27499c8af902",
                "old_target_vi": "Chuẩn hóa theo lô",
                "new_target_vi": "lớp BatchNorm",
            },
        ),
    },
    "d2lce_499fa9391d57e930a19f1b19": {
        "source_term": "broadcasting",
        "definition_en": None,
        "candidate_replacements": (
            {
                "candidate_id": "candidate_8a85f35caa7da45f988ebe6e",
                "candidate_slot": "candidate_slot_8f0a0d4b9af498864495e9be",
                "old_target_vi": "phát quảng kích thước",
                "new_target_vi": "cơ chế mở rộng mảng",
            },
        ),
    },
    "d2lce_c01c503b792019c6e3827ac0": {
        "source_term": "interaction matrix",
        "definition_en": None,
        "candidate_replacements": (
            {
                "candidate_id": "candidate_bf03c5fe1fcc088419aae681",
                "candidate_slot": "candidate_slot_9b94922f0f088cc71d321b3b",
                "old_target_vi": "ma trận tương tác người-dùng–mặt-hàng",
                "new_target_vi": "ma trận tương tác người dùng–mặt hàng",
            },
            {
                "candidate_id": "candidate_3a2246627a7624c8d1d58bce",
                "candidate_slot": "candidate_slot_d687c811cf89c514650d2410",
                "old_target_vi": "ma trận tương tác người-mục",
                "new_target_vi": "ma trận tương tác người dùng–sản phẩm",
            },
        ),
    },
    "d2lce_e014da89e120449f8881dd5b": {
        "source_term": "single GPU",
        "definition_en": "One graphics processing unit used by itself for computation or training.",
        "candidate_replacements": (),
    },
}


def blank_review() -> dict[str, Any]:
    review: dict[str, Any] = {field: "" for field in REVIEW_FIELDS}
    review["invalid_evidence_context_ids"] = []
    review["candidate_replacements"] = []
    review["proposed_split_labels"] = []
    return review


def apply_r0_repair(queue_record: Mapping[str, Any], policy_id: str) -> dict[str, Any]:
    sense_id = queue_record.get("sense_id")
    spec = R0_REPAIR_SPECS.get(str(sense_id))
    if spec is None:
        raise ValueError(f"unsupported R0 repair sense: {sense_id}")
    if not verify_record(queue_record, "repair_queue_record_sha256"):
        raise ValueError(f"R0 queue record hash mismatch: {sense_id}")
    source = queue_record.get("source_payload")
    if not isinstance(source, Mapping):
        raise ValueError(f"R0 source payload is invalid: {sense_id}")
    if source.get("source_term") != spec["source_term"]:
        raise ValueError(f"R0 source term binding mismatch: {sense_id}")
    if queue_record.get("source_payload_sha256") != sha256_bytes(
        canonical_json_bytes(source)
    ):
        raise ValueError(f"R0 source payload hash mismatch: {sense_id}")
    review = queue_record.get("reviewer_1_review")
    if not isinstance(review, Mapping) or review.get("review_status") != "COMPLETE":
        raise ValueError(f"R0 Reviewer 1 decision is incomplete: {sense_id}")
    if review.get("sense_status") != "REVISION_REQUIRED":
        raise ValueError(f"R0 repair must originate from REVISION_REQUIRED: {sense_id}")
    expected_targets = [
        replacement["new_target_vi"] for replacement in spec["candidate_replacements"]
    ]
    if review.get("candidate_replacements") != expected_targets:
        raise ValueError(f"R0 candidate repair instruction drift: {sense_id}")
    expected_definition = spec["definition_en"]
    if expected_definition is None:
        if review.get("definition_decision") != "ACCEPT":
            raise ValueError(f"R0 definition decision drift: {sense_id}")
    elif review.get("definition_decision") != "REVISE" or review.get(
        "corrected_definition_en"
    ) != expected_definition:
        raise ValueError(f"R0 corrected definition drift: {sense_id}")
    repaired = copy.deepcopy(dict(source))
    operations: list[dict[str, Any]] = []
    if expected_definition is not None:
        old_definition = repaired["proposed_definition_en"]
        repaired["proposed_definition_en"] = expected_definition
        operations.append(
            {
                "operation": "REPLACE_DEFINITION",
                "field": "proposed_definition_en",
                "old_value": old_definition,
                "new_value": expected_definition,
            }
        )
    candidates = {
        (row["candidate_id"], row["candidate_slot"]): row
        for row in repaired.get("candidates", [])
        if isinstance(row, dict)
    }
    for replacement in spec["candidate_replacements"]:
        binding = (replacement["candidate_id"], replacement["candidate_slot"])
        candidate = candidates.get(binding)
        if candidate is None or candidate.get("candidate_target_vi") != replacement[
            "old_target_vi"
        ]:
            raise ValueError(f"R0 candidate binding drift: {sense_id}/{binding[0]}")
        candidate["candidate_target_vi"] = replacement["new_target_vi"]
        operations.append(
            {
                "operation": "REPLACE_CANDIDATE_TARGET",
                "candidate_id": replacement["candidate_id"],
                "candidate_slot": replacement["candidate_slot"],
                "old_target_vi": replacement["old_target_vi"],
                "new_target_vi": replacement["new_target_vi"],
            }
        )
    effective_targets = [
        row["candidate_target_vi"].strip().casefold() for row in repaired["candidates"]
    ]
    if len(effective_targets) != 3 or len(set(effective_targets)) != 3:
        raise ValueError(f"R0 repaired candidates must remain three distinct values: {sense_id}")
    for context in repaired.get("evidence_contexts", []):
        if context.get("synthetic") and context.get("positive_evidence_eligible"):
            raise ValueError(f"R0 synthetic context cannot be positive evidence: {sense_id}")
    repaired_sha = sha256_bytes(canonical_json_bytes(repaired))
    return seal_record(
        {
            "schema_id": "D2LFastTrackStageAR0RepairRecordV1",
            "schema_version": "1.0.0",
            "policy_id": policy_id,
            "repair_status": "PENDING_BLIND_REAUDIT",
            "repair_case_id": f"r0_repair_{sense_id.removeprefix('d2lce_')}",
            "sense_id": sense_id,
            "source_term": source["source_term"],
            "stratum": source["stratum"],
            "risk_class": source["risk_class"],
            "parent_repair_queue_record_sha256": queue_record[
                "repair_queue_record_sha256"
            ],
            "parent_source_payload_sha256": queue_record["source_payload_sha256"],
            "reviewer_1_result_sha256": queue_record["reviewer_1_result_sha256"],
            "repair_operations": operations,
            "repaired_source_payload": repaired,
            "repaired_source_payload_sha256": repaired_sha,
            "provider_call_count": 0,
            "stage_b_gold_label": None,
            "final_glossary_decision": None,
        },
        "repair_record_sha256",
    )
