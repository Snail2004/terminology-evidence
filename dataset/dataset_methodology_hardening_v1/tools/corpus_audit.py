from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hardening_common import sha256_file, sha256_text


TRANSFORMATION_ID = "d2l_methodology_corpus_origin_audit"
TRANSFORMATION_VERSION = "1.0.0"
CORPUS_REQUIRED_PROVENANCE = (
    "document_id",
    "chapter_id",
    "block_id",
    "sentence_id",
    "source_artifact_sha256",
    "block_text_sha256",
    "source_start",
    "source_end",
)


def load_source_blocks(source_document: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    document = json.loads(source_document.read_text(encoding="utf-8"))
    document_sha256 = sha256_file(source_document)
    blocks: dict[str, dict[str, Any]] = {}
    for chapter_index, chapter in enumerate(document["chapters"]):
        for block_index, block in enumerate(chapter["blocks"]):
            block_id = block["block_id"]
            source_text = block.get("source_text", block.get("clean_text", ""))
            blocks[block_id] = {
                "schema_id": "D2LMethodologySourceBlockV1",
                "document_id": document.get("doc_id", "document"),
                "chapter_id": chapter["chapter_id"],
                "chapter_index": chapter_index,
                "chapter_title": chapter.get("title", ""),
                "block_id": block_id,
                "block_index": block_index,
                "source_text": source_text,
                "block_text_sha256": sha256_text(source_text),
                "source_document_sha256": document_sha256,
                "parent_record_id": block_id,
                "parent_record_sha256": sha256_text(source_text),
                "transformation_id": "d2l_methodology_source_block_registry",
                "transformation_version": TRANSFORMATION_VERSION,
            }
    return document_sha256, blocks


def _valid_offsets(context: dict[str, Any]) -> bool:
    source_text = context.get("source_text", "")
    start = context.get("match_start")
    end = context.get("match_end")
    source_start = context.get("provenance", {}).get("source_start")
    source_end = context.get("provenance", {}).get("source_end")
    absolute_start = context.get("source_match_start_absolute")
    absolute_end = context.get("source_match_end_absolute")
    if not all(isinstance(value, int) for value in (start, end, source_start, source_end)):
        return False
    if not (0 <= start < end <= len(source_text)):
        return False
    if source_end - source_start != len(source_text):
        return False
    if absolute_start != source_start + start or absolute_end != source_start + end:
        return False
    matched = str(context.get("matched_surface", ""))
    return source_text[start:end].casefold() == matched.casefold()


def audit_contexts(
    contexts: list[dict[str, Any]],
    source_document_sha256: str,
    source_blocks: dict[str, dict[str, Any]],
    sense_scope_ids: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    referenced_blocks: set[str] = set()
    for context in sorted(contexts, key=lambda row: row["context_id"]):
        provenance = context.get("provenance", {})
        synthetic = (
            context.get("binding_kind") == "SYNTHETIC_BOUNDARY_PROBE"
            or provenance.get("source_kind") == "MODEL_GENERATED_SYNTHETIC"
        )
        origin = "SYNTHETIC_CONTROLLED" if synthetic else "CORPUS_EXTRACTED"
        status = "PASS_CORPUS_EXTRACTED"
        reason = "Exact source substring, hashes, provenance, and offsets verified."
        block = source_blocks.get(provenance.get("block_id", ""))
        if synthetic:
            status = "FAIL_SYNTHETIC"
            reason = "Synthetic boundary probe retained for audit but excluded from C."
        elif any(provenance.get(field) in (None, "") for field in CORPUS_REQUIRED_PROVENANCE):
            status = "FAIL_PROVENANCE_INCOMPLETE"
            reason = "Required corpus provenance is incomplete."
        elif provenance.get("source_artifact_sha256") != source_document_sha256:
            status = "FAIL_SOURCE_HASH_MISMATCH"
            reason = "Source document hash does not match the bound document."
        elif block is None or provenance.get("block_text_sha256") != block["block_text_sha256"]:
            status = "FAIL_SOURCE_HASH_MISMATCH"
            reason = "Source block is missing or its hash does not match."
        elif sha256_text(context.get("source_text", "")) != context.get("content_sha256"):
            status = "FAIL_SOURCE_HASH_MISMATCH"
            reason = "Context content hash does not match source_text."
        elif context.get("source_text", "") not in block["source_text"]:
            status = "FAIL_REWRITTEN"
            reason = "Context text is not a verbatim substring of the source block."
        elif not _valid_offsets(context):
            status = "FAIL_OFFSET_INVALID"
            reason = "Local or absolute term offsets are invalid."
        if status == "PASS_CORPUS_EXTRACTED":
            referenced_blocks.add(provenance["block_id"])
        selected_role = context.get("context_role") in {
            "PRIMARY",
            "BACKUP",
            "CONTRASTIVE",
        }
        rows.append(
            {
                "context_id": context["context_id"],
                "document_id": provenance.get("document_id"),
                "chapter_id": provenance.get("chapter_id"),
                "block_id": provenance.get("block_id"),
                "sentence_id": provenance.get("sentence_id"),
                "source_text": context.get("source_text", ""),
                "source_start_offset": provenance.get("source_start"),
                "source_end_offset": provenance.get("source_end"),
                "term_start_offset": context.get("match_start"),
                "term_end_offset": context.get("match_end"),
                "source_hash": provenance.get("source_artifact_sha256"),
                "origin": origin,
                "extraction_method": (
                    "SYNTHETIC_MODEL_PROBE" if synthetic else "EXACT_SOURCE_SUBSTRING"
                ),
                "context_role": context.get("context_role"),
                "context_type": context.get("context_type"),
                "sense_id": context["sense_id"],
                "scope_id": sense_scope_ids[context["sense_id"]],
                "audit_status": status,
                "audit_reason": reason,
                "eligible_for_c_primary_support": (
                    status == "PASS_CORPUS_EXTRACTED"
                    and context.get("context_role") in {"PRIMARY", "CONTRASTIVE"}
                ),
                "eligible_for_c_support": status == "PASS_CORPUS_EXTRACTED" and selected_role,
                "parent_record_id": context["context_id"],
                "parent_record_sha256": context["context_sha256"],
                "transformation_id": TRANSFORMATION_ID,
                "transformation_version": TRANSFORMATION_VERSION,
            }
        )
    registry = [source_blocks[block_id] for block_id in sorted(referenced_blocks)]
    return rows, registry
