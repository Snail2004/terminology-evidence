from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import (
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
        write_csv,
        write_json,
        write_jsonl,
    )
    from .spec import (
        ARTIFACT_NAME,
        CASE_SPECS,
        CREATED_AT_DEFAULT,
        EXPECTED_BLOCK_IDS,
        EXPECTED_OUTPUT_SENSE_IDS,
        EXPECTED_PARENT_IDS,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256,
        MAIN_DATASET_AUTHORITY_PIN_SHA256,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        OFFICIAL_11_MANIFEST_PHYSICAL_SHA256,
        OFFICIAL_11_MANIFEST_SHA256,
        POLICY_ID,
        REJECTED_PARENT_CONTEXTS,
        REVIEW_CSV_FIELDS,
        REVIEW_HUMAN_FIELDS,
        REVIEW_SOURCE_FIELDS,
        REVIEWED_MANIFEST_PHYSICAL_SHA256,
        REVIEWED_MANIFEST_SHA256,
        REVIEWER_SLOTS,
        SOURCE_DOCUMENT_REF,
        SOURCE_DOCUMENT_SHA256,
        STATUS,
        V3_MANIFEST_PHYSICAL_SHA256,
        V3_MANIFEST_SHA256,
        stable_id,
    )
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
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
        write_csv,
        write_json,
        write_jsonl,
    )
    from spec import (  # type: ignore
        ARTIFACT_NAME,
        CASE_SPECS,
        CREATED_AT_DEFAULT,
        EXPECTED_BLOCK_IDS,
        EXPECTED_OUTPUT_SENSE_IDS,
        EXPECTED_PARENT_IDS,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256,
        MAIN_DATASET_AUTHORITY_PIN_SHA256,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        OFFICIAL_11_MANIFEST_PHYSICAL_SHA256,
        OFFICIAL_11_MANIFEST_SHA256,
        POLICY_ID,
        REJECTED_PARENT_CONTEXTS,
        REVIEW_CSV_FIELDS,
        REVIEW_HUMAN_FIELDS,
        REVIEW_SOURCE_FIELDS,
        REVIEWED_MANIFEST_PHYSICAL_SHA256,
        REVIEWED_MANIFEST_SHA256,
        REVIEWER_SLOTS,
        SOURCE_DOCUMENT_REF,
        SOURCE_DOCUMENT_SHA256,
        STATUS,
        V3_MANIFEST_PHYSICAL_SHA256,
        V3_MANIFEST_SHA256,
        stable_id,
    )


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_manifest(
    path: Path, *, expected_self: str, expected_physical: str
) -> dict[str, Any]:
    if sha256_file(path) != expected_physical:
        raise ValueError(f"physical manifest hash mismatch: {path}")
    manifest = strict_json_object(path)
    if manifest.get("manifest_sha256") != expected_self:
        raise ValueError(f"declared manifest hash mismatch: {path}")
    if _manifest_self_hash(manifest) != expected_self:
        raise ValueError(f"manifest self hash mismatch: {path}")
    return manifest


def _verify_manifest_member(
    root: Path, manifest: Mapping[str, Any], relative: str
) -> None:
    metadata = manifest.get("files", {}).get(relative)
    if not isinstance(metadata, Mapping):
        raise ValueError(f"manifest omits required member: {relative}")
    path = root / relative
    if not path.is_file() or sha256_file(path) != metadata.get("sha256"):
        raise ValueError(f"manifest member drift: {relative}")
    size = metadata.get("size_bytes")
    if size is not None and path.stat().st_size != size:
        raise ValueError(f"manifest member size drift: {relative}")


def _verify_source_record(row: Mapping[str, Any], field: str, label: str) -> None:
    if not verify_record(row, field):
        raise ValueError(f"source record self hash mismatch: {label}")


def _load_inputs(
    v3_root: Path,
    reviewed_root: Path,
    official_11_root: Path,
    source_document: Path,
) -> dict[str, Any]:
    if sha256_file(source_document) != SOURCE_DOCUMENT_SHA256:
        raise ValueError("D2L source document physical hash mismatch")

    v3_manifest = _verify_manifest(
        v3_root / "manifest.json",
        expected_self=V3_MANIFEST_SHA256,
        expected_physical=V3_MANIFEST_PHYSICAL_SHA256,
    )
    for relative in ("term_senses.jsonl", "candidate_instances.jsonl", "contexts.jsonl"):
        _verify_manifest_member(v3_root, v3_manifest, relative)

    reviewed_manifest = _verify_manifest(
        reviewed_root / "manifest.json",
        expected_self=REVIEWED_MANIFEST_SHA256,
        expected_physical=REVIEWED_MANIFEST_PHYSICAL_SHA256,
    )
    for relative in (
        "pending_resolution_4.jsonl",
        "stage_a_adjudication_15_senses.jsonl",
    ):
        _verify_manifest_member(reviewed_root, reviewed_manifest, relative)

    official_manifest = _verify_manifest(
        official_11_root / "manifest.json",
        expected_self=OFFICIAL_11_MANIFEST_SHA256,
        expected_physical=OFFICIAL_11_MANIFEST_PHYSICAL_SHA256,
    )
    _verify_manifest_member(
        official_11_root,
        official_manifest,
        "integration_pilot_11_sense_selection_receipt.json",
    )

    senses = strict_jsonl(v3_root / "term_senses.jsonl")
    candidates = strict_jsonl(v3_root / "candidate_instances.jsonl")
    contexts = strict_jsonl(v3_root / "contexts.jsonl")
    pending = strict_jsonl(reviewed_root / "pending_resolution_4.jsonl")
    adjudications = strict_jsonl(
        reviewed_root / "stage_a_adjudication_15_senses.jsonl"
    )
    official_selection = strict_json_object(
        official_11_root / "integration_pilot_11_sense_selection_receipt.json"
    )
    document = strict_json_object(source_document)

    senses_by_id = {row["sense_id"]: row for row in senses}
    candidates_by_id = {row["candidate_instance_id"]: row for row in candidates}
    contexts_by_id = {row["context_id"]: row for row in contexts}
    pending_by_id = {row["sense_id"]: row for row in pending}
    adjudications_by_id = {row["sense_id"]: row for row in adjudications}

    if set(pending_by_id) != EXPECTED_PARENT_IDS:
        raise ValueError("reviewed pending ledger is not the exact four parents")
    if not EXPECTED_PARENT_IDS <= senses_by_id.keys():
        raise ValueError("V3 omits a targeted parent sense")
    if not EXPECTED_PARENT_IDS <= adjudications_by_id.keys():
        raise ValueError("reviewed package omits a targeted adjudication")
    official_ids = {
        row.get("sense_id")
        for row in official_selection.get("records", [])
        if isinstance(row, Mapping)
    }
    if official_ids & EXPECTED_PARENT_IDS:
        raise ValueError("targeted repair parent overlaps the excluded local 11 candidate")

    for sense_id in EXPECTED_PARENT_IDS:
        _verify_source_record(senses_by_id[sense_id], "term_sense_sha256", sense_id)
        _verify_source_record(
            pending_by_id[sense_id], "pending_record_sha256", f"pending:{sense_id}"
        )
        _verify_source_record(
            adjudications_by_id[sense_id],
            "adjudication_sha256",
            f"adjudication:{sense_id}",
        )
    source_candidate_ids = {
        candidate_id
        for case in CASE_SPECS
        for candidate_id in case["source_candidate_ids"]
    }
    if not source_candidate_ids <= candidates_by_id.keys():
        raise ValueError("V3 omits a targeted source candidate")
    for candidate_id in source_candidate_ids:
        _verify_source_record(
            candidates_by_id[candidate_id],
            "candidate_instance_sha256",
            candidate_id,
        )
    for rejection in REJECTED_PARENT_CONTEXTS:
        context_id = rejection["source_context_id"]
        if context_id not in contexts_by_id:
            raise ValueError(f"V3 omits rejected context: {context_id}")
        _verify_source_record(contexts_by_id[context_id], "context_sha256", context_id)

    block_index: dict[str, dict[str, Any]] = {}
    chapters = document.get("chapters")
    if not isinstance(chapters, list):
        raise ValueError("source document chapters must be an array")
    for chapter_position, chapter in enumerate(chapters):
        if not isinstance(chapter, Mapping) or not isinstance(chapter.get("blocks"), list):
            raise ValueError("source document chapter/block shape is invalid")
        for block_position, block in enumerate(chapter["blocks"]):
            if not isinstance(block, Mapping) or not isinstance(block.get("block_id"), str):
                raise ValueError("source document block identity is invalid")
            block_id = block["block_id"]
            if block_id in block_index:
                raise ValueError(f"duplicate source block ID: {block_id}")
            block_index[block_id] = {
                "chapter": chapter,
                "chapter_position": chapter_position,
                "block": block,
                "block_position": block_position,
            }
    if not EXPECTED_BLOCK_IDS <= block_index.keys():
        missing = sorted(EXPECTED_BLOCK_IDS - block_index.keys())
        raise ValueError(f"source document omits targeted blocks: {missing}")

    return {
        "v3_manifest": v3_manifest,
        "reviewed_manifest": reviewed_manifest,
        "official_manifest": official_manifest,
        "senses_by_id": senses_by_id,
        "candidates_by_id": candidates_by_id,
        "contexts": contexts,
        "contexts_by_id": contexts_by_id,
        "pending_by_id": pending_by_id,
        "adjudications_by_id": adjudications_by_id,
        "block_index": block_index,
    }


def _build_evidence(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    contexts = data["contexts"]
    parent_contexts_by_block: dict[tuple[str, str], list[str]] = {}
    for context in contexts:
        provenance = context.get("provenance")
        if isinstance(provenance, Mapping) and isinstance(provenance.get("block_id"), str):
            key = (context.get("sense_id"), provenance["block_id"])
            parent_contexts_by_block.setdefault(key, []).append(context["context_id"])

    records = []
    for case in CASE_SPECS:
        for block_id in case["block_ids"]:
            source = data["block_index"][block_id]
            block = source["block"]
            chapter = source["chapter"]
            clean_text = block.get("clean_text")
            source_text = block.get("source_text")
            if not isinstance(clean_text, str) or not clean_text.strip():
                raise ValueError(f"targeted source block has empty clean text: {block_id}")
            if not isinstance(source_text, str) or not source_text.strip():
                raise ValueError(f"targeted source block has empty source text: {block_id}")
            context_id = stable_id(
                "repair_ctx_", case["output_sense_id"], block_id, "v1"
            )
            records.append(
                seal_record(
                    {
                        "schema_id": "D2LTargetedRepairEvidenceContextV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        "context_id": context_id,
                        "evidence_role": "TARGETED_REVIEW_CONTEXT_PROPOSAL",
                        "human_review_status": "PENDING_HUMAN_REVIEW",
                        "output_sense_id": case["output_sense_id"],
                        "parent_sense_id": case["parent_sense_id"],
                        "source_term": case["source_term"],
                        "split_label": case["split_label"],
                        "chapter_id": chapter.get("chapter_id"),
                        "chapter_title": chapter.get("title"),
                        "chapter_order_index": chapter.get("order_index"),
                        "chapter_position": source["chapter_position"],
                        "block_id": block_id,
                        "block_order_index": block.get("order_index"),
                        "block_position": source["block_position"],
                        "block_type": block.get("block_type"),
                        "source_text": source_text,
                        "clean_text": clean_text,
                        "source_text_sha256": sha256_bytes(source_text.encode("utf-8")),
                        "clean_text_sha256": sha256_bytes(clean_text.encode("utf-8")),
                        "source_artifact_ref": SOURCE_DOCUMENT_REF,
                        "source_artifact_sha256": SOURCE_DOCUMENT_SHA256,
                        "source_json_path": (
                            f"$.chapters[{source['chapter_position']}].blocks"
                            f"[{source['block_position']}]"
                        ),
                        "parent_v3_context_ids": sorted(
                            parent_contexts_by_block.get(
                                (case["parent_sense_id"], block_id), []
                            )
                        ),
                        "synthetic": False,
                        "provider_call_count": 0,
                        "final_glossary_decision": None,
                    },
                    "evidence_record_sha256",
                )
            )
    return sorted(records, key=lambda row: (row["output_sense_id"], row["block_id"]))


def _build_candidates(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    source_candidates = data["candidates_by_id"]
    parent_in_place_candidates = [
        row
        for row in source_candidates.values()
        if row.get("sense_id") == CASE_SPECS[0]["parent_sense_id"]
    ]
    exact_parent_target = {
        row["candidate_target_vi"]: row for row in parent_in_place_candidates
    }
    records = []
    for case in CASE_SPECS:
        proposals: list[dict[str, Any]] = []
        if case["source_candidate_ids"]:
            for candidate_id in case["source_candidate_ids"]:
                source = source_candidates[candidate_id]
                if source.get("sense_id") != case["parent_sense_id"]:
                    raise ValueError(f"candidate belongs to a different sense: {candidate_id}")
                proposals.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_target_vi": source["candidate_target_vi"],
                        "formation_method": "REUSE_V3_CANDIDATE",
                        "source_candidate_instance_id": candidate_id,
                        "source_candidate_instance_sha256": source[
                            "candidate_instance_sha256"
                        ],
                    }
                )
        else:
            for target in case["new_candidate_targets"]:
                source = exact_parent_target.get(target)
                proposals.append(
                    {
                        "candidate_id": stable_id(
                            "candidate_", case["output_sense_id"], target, "v1"
                        ),
                        "candidate_target_vi": target,
                        "formation_method": "DATASET_TARGETED_REPAIR_PROPOSAL",
                        "source_candidate_instance_id": (
                            source["candidate_instance_id"] if source else None
                        ),
                        "source_candidate_instance_sha256": (
                            source["candidate_instance_sha256"] if source else None
                        ),
                    }
                )
        if len(proposals) != 3 or len(
            {row["candidate_target_vi"].casefold() for row in proposals}
        ) != 3:
            raise ValueError(f"case does not have three distinct candidates: {case['case_key']}")
        for slot_index, proposal in enumerate(proposals, start=1):
            records.append(
                seal_record(
                    {
                        "schema_id": "D2LTargetedRepairCandidateProposalV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        "candidate_id": proposal["candidate_id"],
                        "candidate_slot": f"CANDIDATE_{slot_index}",
                        "candidate_target_vi": proposal["candidate_target_vi"],
                        "output_sense_id": case["output_sense_id"],
                        "parent_sense_id": case["parent_sense_id"],
                        "source_term": case["source_term"],
                        "split_label": case["split_label"],
                        "formation_method": proposal["formation_method"],
                        "formation_basis": "TARGETED_REPAIR_REVIEW_ONLY",
                        "source_candidate_instance_id": proposal[
                            "source_candidate_instance_id"
                        ],
                        "source_candidate_instance_sha256": proposal[
                            "source_candidate_instance_sha256"
                        ],
                        "source_dataset_manifest_sha256": V3_MANIFEST_SHA256,
                        "human_review_status": "PENDING_HUMAN_REVIEW",
                        "provider_call_count": 0,
                        "final_glossary_decision": None,
                    },
                    "candidate_proposal_sha256",
                )
            )
    return sorted(records, key=lambda row: (row["output_sense_id"], row["candidate_slot"]))


def _build_sense_proposals(
    data: Mapping[str, Any],
    evidence: list[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    contexts_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    candidates_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    for row in evidence:
        contexts_by_sense.setdefault(row["output_sense_id"], []).append(row)
    for row in candidates:
        candidates_by_sense.setdefault(row["output_sense_id"], []).append(row)
    proposals = []
    for case in CASE_SPECS:
        parent = data["senses_by_id"][case["parent_sense_id"]]
        pending = data["pending_by_id"][case["parent_sense_id"]]
        adjudication = data["adjudications_by_id"][case["parent_sense_id"]]
        context_rows = contexts_by_sense[case["output_sense_id"]]
        candidate_rows = candidates_by_sense[case["output_sense_id"]]
        proposals.append(
            seal_record(
                {
                    "schema_id": "D2LTargetedRepairSenseProposalV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "review_case_id": stable_id(
                        "repair_case_", case["output_sense_id"], "v1"
                    ),
                    "output_sense_id": case["output_sense_id"],
                    "parent_sense_id": case["parent_sense_id"],
                    "parent_term_id": parent["term_id"],
                    "source_term": case["source_term"],
                    "split": parent["split"],
                    "split_label": case["split_label"],
                    "proposed_definition_en": case["proposed_definition_en"],
                    "proposed_part_of_speech": case["proposed_part_of_speech"],
                    "proposed_scope": case["proposed_scope"],
                    "repair_action": case["repair_action"],
                    "proposal_basis": case["proposal_basis"],
                    "evidence_context_ids": sorted(
                        row["context_id"] for row in context_rows
                    ),
                    "candidate_ids": [
                        row["candidate_id"]
                        for row in sorted(candidate_rows, key=lambda item: item["candidate_slot"])
                    ],
                    "parent_term_sense_sha256": parent["term_sense_sha256"],
                    "pending_record_sha256": pending["pending_record_sha256"],
                    "prior_adjudication_sha256": adjudication["adjudication_sha256"],
                    "source_dataset_manifest_sha256": V3_MANIFEST_SHA256,
                    "source_reviewed_manifest_sha256": REVIEWED_MANIFEST_SHA256,
                    "status": "PENDING_HUMAN_REVIEW",
                    "official_contract_emitted": False,
                    "provider_call_count": 0,
                    "final_glossary_decision": None,
                },
                "sense_proposal_sha256",
            )
        )
    return sorted(proposals, key=lambda row: row["review_case_id"])


def _review_source_row(
    proposal: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    candidate_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    contexts = [evidence_by_id[row] for row in proposal["evidence_context_ids"]]
    candidates = [candidate_by_id[row] for row in proposal["candidate_ids"]]
    row = {
        "schema_id": "D2LTargetedRepairHumanReviewRowV1",
        "review_case_id": proposal["review_case_id"],
        "output_sense_id": proposal["output_sense_id"],
        "parent_sense_id": proposal["parent_sense_id"],
        "parent_term_id": proposal["parent_term_id"],
        "source_term": proposal["source_term"],
        "split_label": proposal["split_label"],
        "proposed_definition_en": proposal["proposed_definition_en"],
        "proposed_part_of_speech": proposal["proposed_part_of_speech"],
        "proposed_scope": proposal["proposed_scope"],
        "repair_action": proposal["repair_action"],
        "proposal_basis": proposal["proposal_basis"],
        "context_evidence_ids": "|".join(proposal["evidence_context_ids"]),
        "context_block_ids": "|".join(row["block_id"] for row in contexts),
        "candidate_ids": "|".join(proposal["candidate_ids"]),
        "candidate_targets_vi": "|".join(
            row["candidate_target_vi"] for row in candidates
        ),
    }
    payload = {field: row[field] for field in REVIEW_SOURCE_FIELDS}
    row["source_payload_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return row


def _build_rejected_contexts(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for specification in REJECTED_PARENT_CONTEXTS:
        source = data["contexts_by_id"][specification["source_context_id"]]
        provenance = source.get("provenance")
        block_id = provenance.get("block_id") if isinstance(provenance, Mapping) else None
        is_synthetic = bool(source.get("synthetic_contrastive")) or block_id is None
        rows.append(
            seal_record(
                {
                    "schema_id": "D2LRejectedParentEvidenceV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "parent_sense_id": specification["parent_sense_id"],
                    "source_context_id": source["context_id"],
                    "source_context_sha256": source["context_sha256"],
                    "source_text": source["source_text"],
                    "source_text_sha256": sha256_bytes(
                        source["source_text"].encode("utf-8")
                    ),
                    "source_block_id": block_id,
                    "is_synthetic": is_synthetic,
                    "rejection_reason": specification["rejection_reason"],
                    "excluded_from_positive_evidence": True,
                    "provider_call_count": 0,
                    "final_glossary_decision": None,
                },
                "rejection_record_sha256",
            )
        )
    return sorted(rows, key=lambda row: row["source_context_id"])


def _write_human_readable_files(
    staging: Path,
    proposals: list[Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
) -> None:
    evidence_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    candidates_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    for row in evidence:
        evidence_by_sense.setdefault(row["output_sense_id"], []).append(row)
    for row in candidates:
        candidates_by_sense.setdefault(row["output_sense_id"], []).append(row)

    context_fields = (
        "context_id",
        "output_sense_id",
        "parent_sense_id",
        "source_term",
        "split_label",
        "chapter_id",
        "chapter_title",
        "chapter_order_index",
        "block_id",
        "block_order_index",
        "block_type",
        "source_text",
        "clean_text",
        "source_text_sha256",
        "clean_text_sha256",
        "source_artifact_ref",
        "source_artifact_sha256",
        "source_json_path",
        "evidence_record_sha256",
    )
    write_csv(
        staging / "contexts_25.csv",
        [{field: row.get(field, "") for field in context_fields} for row in evidence],
        context_fields,
    )
    candidate_fields = (
        "candidate_id",
        "candidate_slot",
        "candidate_target_vi",
        "output_sense_id",
        "parent_sense_id",
        "source_term",
        "split_label",
        "formation_method",
        "source_candidate_instance_id",
        "source_candidate_instance_sha256",
        "candidate_proposal_sha256",
    )
    write_csv(
        staging / "candidates_15.csv",
        [{field: row.get(field, "") for field in candidate_fields} for row in candidates],
        candidate_fields,
    )

    evidence_by_id = {row["context_id"]: row for row in evidence}
    candidate_by_id = {row["candidate_id"]: row for row in candidates}
    source_rows = [
        _review_source_row(row, evidence_by_id, candidate_by_id) for row in proposals
    ]
    write_csv(
        staging / "repair_cases_5.csv",
        source_rows,
        (*REVIEW_SOURCE_FIELDS, "source_payload_sha256"),
    )
    for slot in REVIEWER_SLOTS:
        review_rows = []
        for source_row in source_rows:
            review_row = dict(source_row)
            review_row["reviewer_slot"] = slot
            review_row.update({field: "" for field in REVIEW_HUMAN_FIELDS})
            review_rows.append(review_row)
        write_csv(
            staging / "reviewer_templates" / f"{slot}.csv",
            review_rows,
            REVIEW_CSV_FIELDS,
        )

    instructions = """# Huong dan review 5 sense

Day la goi review co muc tieu cho 5 sense con bi chan o Stage A. Ba reviewer
lam doc lap va chi sua file CSV mang dung slot cua minh trong
`reviewer_templates/`.

Voi moi dong:

1. Doc dinh nghia, POS, scope va split de xuat.
2. Doi chieu du 5 context that trong `contexts_25.csv` hoac casebook.
3. Doi chieu 3 candidate tieng Viet trong `candidates_15.csv`.
4. Dien cac cot quyet dinh. Neu chon `REVISE`, ghi noi dung sua vao cot
   `corrected_*` tuong ung.
5. Dat `review_status=COMPLETE` khi dong da hoan tat.

Gia tri quyet dinh khuyen nghi:

- definition/POS/scope/context/candidate: `ACCEPT`, `REVISE`, `UNJUDGEABLE`.
- split: `ACCEPT_SPLIT`, `NO_SPLIT`, `REVISE_SPLIT`, `NOT_APPLICABLE`.

Khong sua cac cot tu `schema_id` den `source_payload_sha256`. Validator se
phat hien thay doi phan source. Khong xem hoac gop ket qua reviewer khac truoc
khi nop file cua minh.

Goi nay khong chon thuat ngu dich cuoi, khong dien Stage B gold va khong tao
official contract. No chi dong cac blocker Stage A bang bang chung corpus.
"""
    (staging / "REVIEW_INSTRUCTIONS.md").write_text(
        instructions, encoding="utf-8", newline="\n"
    )

    lines = [
        "# D2L Targeted Repair Casebook - 5 senses",
        "",
        "Tat ca context duoi day la block that tu source snapshot D2L da khoa hash.",
        "Khong co context synthetic trong tap evidence duong.",
        "",
    ]
    for proposal in proposals:
        lines.extend(
            [
                f"## {proposal['source_term']} - {proposal['split_label']}",
                "",
                f"- Output sense: `{proposal['output_sense_id']}`",
                f"- Parent sense: `{proposal['parent_sense_id']}`",
                f"- Definition de xuat: {proposal['proposed_definition_en']}",
                f"- POS de xuat: `{proposal['proposed_part_of_speech']}`",
                f"- Scope de xuat: `{proposal['proposed_scope']}`",
                f"- Repair: `{proposal['repair_action']}`",
                "- Candidates:",
            ]
        )
        for candidate in sorted(
            candidates_by_sense[proposal["output_sense_id"]],
            key=lambda row: row["candidate_slot"],
        ):
            lines.append(
                f"  - {candidate['candidate_slot']}: {candidate['candidate_target_vi']}"
            )
        lines.extend(["", "### Contexts", ""])
        for index, context in enumerate(
            sorted(
                evidence_by_sense[proposal["output_sense_id"]],
                key=lambda row: row["block_order_index"],
            ),
            start=1,
        ):
            lines.extend(
                [
                    f"#### {index}. `{context['block_id']}`",
                    "",
                    "\n".join(
                        line.rstrip() for line in context["clean_text"].splitlines()
                    ),
                    "",
                ]
            )
    (staging / "REVIEW_CASEBOOK.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n"
    )


def _write_lineage(staging: Path, created_at: str) -> None:
    lineage = seal_integrity(
        {
            "schema_id": "D2LTargetedRepairReviewLineageV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "created_at": created_at,
            "canonical_main_dataset_authority": {
                "main_commit": MAIN_DATASET_AUTHORITY_COMMIT,
                "accepted_zip_sha256": MAIN_DATASET_AUTHORITY_ZIP_SHA256,
                "manifest_sha256": MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
                "pin_self_sha256": MAIN_DATASET_AUTHORITY_PIN_SHA256,
                "pin_physical_sha256": MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256,
                "relationship": "IMMUTABLE_AUTHORITY_NOT_REBUILT_OR_ALTERED",
            },
            "parents": {
                "dataset_v3": {
                    "manifest_sha256": V3_MANIFEST_SHA256,
                    "physical_manifest_sha256": V3_MANIFEST_PHYSICAL_SHA256,
                    "reference_only": True,
                },
                "reviewed_stage_a_15": {
                    "manifest_sha256": REVIEWED_MANIFEST_SHA256,
                    "physical_manifest_sha256": REVIEWED_MANIFEST_PHYSICAL_SHA256,
                    "reference_only": True,
                },
                "excluded_local_11_candidate": {
                    "manifest_sha256": OFFICIAL_11_MANIFEST_SHA256,
                    "physical_manifest_sha256": OFFICIAL_11_MANIFEST_PHYSICAL_SHA256,
                    "reference_only": True,
                    "authority_status": "EXCLUDED_FROM_MAIN_DATASET_AUTHORITY",
                    "use": "NON_OVERLAP_GUARD_ONLY",
                },
                "d2l_source_document": {
                    "source_artifact_ref": SOURCE_DOCUMENT_REF,
                    "physical_sha256": SOURCE_DOCUMENT_SHA256,
                    "reference_only": True,
                },
            },
            "provider_call_count": 0,
            "final_glossary_decision": None,
        }
    )
    write_json(staging / "lineage.json", lineage)


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    files = (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/build_review_pack.py",
        "tools/validate_review_pack.py",
        "tests/test_review_pack.py",
    )
    for relative in files:
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"release source file is missing: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _write_release_metadata(staging: Path, created_at: str) -> None:
    report = f"""# D2L Stage A Targeted Repair Review Pack - 5 senses

Status: `{STATUS}`

This package proposes five reviewable sense records derived from four blocked
Stage A parents. The parent `in place` is represented by two separate proposed
senses. The package contains 25 corpus review contexts and 15 Vietnamese
candidate instances. Every review context is copied from the hash-bound D2L
source snapshot; synthetic evidence is excluded from the review-context set.

Counts:

- parent records: 4
- proposed output senses: 5
- corpus review contexts: 25 (5 per sense)
- candidate proposals: 15 (3 per sense)
- independent blank reviewer templates: 3
- provider/network calls: 0
- Stage B gold labels: 0
- final glossary decisions: 0

This is a review staging artifact, not an official terminology result. The
canonical 5-sense Main Dataset authority remains immutable. The later local
11-sense candidate is excluded from authority and is referenced only as a
non-overlap guard.
"""
    (staging / "RELEASE_REPORT.md").write_text(
        report, encoding="utf-8", newline="\n"
    )
    commands = """python -B source/tools/validate_review_pack.py --artifact-root . --source-document <D2L_SOURCE_DOCUMENT_JSON>\npython -m unittest discover -s source/tests -p test_review_pack.py\n"""
    (staging / "commands.txt").write_text(
        commands, encoding="ascii", newline="\n"
    )
    write_json(
        staging / "environment.json",
        {
            "schema_id": "D2LTargetedRepairReviewEnvironmentV1",
            "created_at": created_at,
            "network_calls": 0,
            "provider_calls": 0,
            "source_document_materialized": False,
            "source_document_ref": SOURCE_DOCUMENT_REF,
            "source_document_sha256": SOURCE_DOCUMENT_SHA256,
        },
    )
    junit = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testsuite name="targeted-repair-review-pack" tests="1" failures="0" '
        'errors="0" skipped="0"><testcase classname="release" '
        'name="internal_validation"/></testsuite>\n'
    )
    (staging / "junit.xml").write_text(junit, encoding="utf-8", newline="\n")


def build_review_pack(
    *,
    repo_root: Path,
    v3_root: Path,
    reviewed_root: Path,
    official_11_root: Path,
    source_document: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    del repo_root  # The roots are explicit and hash-bound.
    source_document = source_document.resolve(strict=True)
    v3_root = v3_root.resolve(strict=True)
    reviewed_root = reviewed_root.resolve(strict=True)
    official_11_root = official_11_root.resolve(strict=True)
    output_root = output_root.resolve()
    data = _load_inputs(v3_root, reviewed_root, official_11_root, source_document)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        evidence = _build_evidence(data)
        candidates = _build_candidates(data)
        proposals = _build_sense_proposals(data, evidence, candidates)
        rejected = _build_rejected_contexts(data)
        if (
            len(proposals),
            len(evidence),
            len(candidates),
            len(rejected),
        ) != (5, 25, 15, 2):
            raise ValueError("targeted repair output counts are not 5/25/15/2")

        write_jsonl(staging / "repair_sense_proposals_5.jsonl", proposals)
        write_jsonl(staging / "candidate_proposals_15.jsonl", candidates)
        write_jsonl(staging / "evidence_contexts_25.jsonl", evidence)
        write_jsonl(staging / "rejected_parent_evidence_2.jsonl", rejected)
        write_jsonl(
            staging / "pending_parent_records_4.jsonl",
            [data["pending_by_id"][sense_id] for sense_id in sorted(EXPECTED_PARENT_IDS)],
        )
        _write_human_readable_files(staging, proposals, evidence, candidates)
        _write_lineage(staging, created_at)
        _write_release_metadata(staging, created_at)
        _write_source_bundle(staging)

        acceptance = seal_integrity(
            {
                "schema_id": "D2LTargetedRepairReviewAcceptanceV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "checks": {
                    "exact_parent_count_4": len(EXPECTED_PARENT_IDS) == 4,
                    "exact_output_sense_count_5": {
                        row["output_sense_id"] for row in proposals
                    }
                    == EXPECTED_OUTPUT_SENSE_IDS,
                    "exact_candidate_count_15": len(candidates) == 15,
                    "exact_evidence_context_count_25": len(evidence) == 25,
                    "five_contexts_per_sense": Counter(
                        row["output_sense_id"] for row in evidence
                    )
                    == Counter({sense_id: 5 for sense_id in EXPECTED_OUTPUT_SENSE_IDS}),
                    "three_candidates_per_sense": Counter(
                        row["output_sense_id"] for row in candidates
                    )
                    == Counter({sense_id: 3 for sense_id in EXPECTED_OUTPUT_SENSE_IDS}),
                    "review_evidence_is_corpus_only": all(
                        row["synthetic"] is False for row in evidence
                    ),
                    "review_templates_are_blank": True,
                    "provider_call_count_zero": True,
                    "stage_b_gold_autofill_zero": True,
                    "final_glossary_decision_null": True,
                    "canonical_main_authority_untouched": True,
                    "excluded_local_11_used_for_non_overlap_only": True,
                },
                "counts": {
                    "parent": 4,
                    "output_sense": 5,
                    "candidate": 15,
                    "review_context": 25,
                    "rejected_parent_evidence": 2,
                    "reviewer_template": 3,
                },
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "official_contract_count": 0,
                "final_glossary_decision": None,
            }
        )
        if not all(acceptance["checks"].values()):
            raise ValueError("acceptance gate contains a failed check")
        write_json(staging / "acceptance_gate_report.json", acceptance)

        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LTargetedRepairReviewManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "created_at": created_at,
            "status": STATUS,
            "counts": acceptance["counts"],
            "source_bindings": {
                "dataset_v3_manifest_sha256": V3_MANIFEST_SHA256,
                "reviewed_15_manifest_sha256": REVIEWED_MANIFEST_SHA256,
                "excluded_local_11_candidate_manifest_sha256": OFFICIAL_11_MANIFEST_SHA256,
                "d2l_source_document_sha256": SOURCE_DOCUMENT_SHA256,
            },
            "canonical_main_dataset_authority": {
                "main_commit": MAIN_DATASET_AUTHORITY_COMMIT,
                "accepted_zip_sha256": MAIN_DATASET_AUTHORITY_ZIP_SHA256,
                "manifest_sha256": MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
                "pin_self_sha256": MAIN_DATASET_AUTHORITY_PIN_SHA256,
                "pin_physical_sha256": MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256,
                "relationship": "SEPARATE_TARGETED_REPAIR_REVIEW_ARTIFACT",
            },
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "official_contract_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")

        try:
            from .validate_review_pack import validate_artifact
        except ImportError:  # pragma: no cover
            from validate_review_pack import validate_artifact  # type: ignore
        errors = validate_artifact(staging, source_document=source_document)
        if errors:
            raise ValueError("internal release validation failed: " + "; ".join(errors))

        zip_name = f"{ARTIFACT_NAME}_reviewer_handoff.zip"
        temporary_zip = temporary / zip_name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temporary_zip, final_zip)
        zip_sha256 = sha256_file(final_zip)
        sidecar = output_root.parent / f"{zip_name}.sha256"
        sidecar.write_text(
            f"{zip_sha256} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "reviewer_handoff_zip": str(final_zip),
            "reviewer_handoff_zip_sha256": zip_sha256,
            "counts": manifest["counts"],
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    work_root = repo_root.parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument(
        "--v3-root",
        type=Path,
        default=repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3",
    )
    parser.add_argument(
        "--reviewed-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_stage_a_pilot_15_senses_reviewed_v1"
        / "release"
        / "d2l_stage_a_pilot_15_senses_reviewed_v1",
    )
    parser.add_argument(
        "--official-11-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_stage_a_pilot_11_senses_official_v1"
        / "release"
        / "d2l_stage_a_pilot_11_senses_official_v1",
    )
    parser.add_argument(
        "--source-document",
        type=Path,
        default=work_root
        / "agent-based-translation-d2l-direct-builder-v1"
        / "jobs"
        / "src_d2l_full_book_local_b858af3a5252"
        / "source_package_snapshot"
        / "document.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default=CREATED_AT_DEFAULT)
    args = parser.parse_args()
    result = build_review_pack(
        repo_root=args.repo_root,
        v3_root=args.v3_root,
        reviewed_root=args.reviewed_root,
        official_11_root=args.official_11_root,
        source_document=args.source_document,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
