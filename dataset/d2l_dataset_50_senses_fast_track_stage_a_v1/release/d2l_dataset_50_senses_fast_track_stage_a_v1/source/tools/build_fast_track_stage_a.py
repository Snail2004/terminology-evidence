from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

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
        write_json,
        write_jsonl,
    )
    from .spec import (
        ARTIFACT_NAME,
        CREATED_AT_DEFAULT,
        LANE_COUNTS,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        NEW_SENSE_QUOTAS,
        OFFICIAL_5_MANIFEST_PHYSICAL_SHA256,
        OFFICIAL_5_MANIFEST_SHA256,
        POLICY_ID,
        POOL_STRATUM_COUNTS,
        REPAIRED_5_MANIFEST_PHYSICAL_SHA256,
        REPAIRED_5_MANIFEST_SHA256,
        REVIEWED_15_MANIFEST_PHYSICAL_SHA256,
        REVIEWED_15_MANIFEST_SHA256,
        REVIEW_FIELDS,
        REVIEW_REQUIREMENT_BY_RISK,
        REVIEW_SLOTS_BY_RISK,
        RISK_BY_STRATUM,
        RISK_COUNTS_NEW,
        SOURCE_BATCH_MANIFEST_PHYSICAL_SHA256,
        SOURCE_BATCH_MANIFEST_SHA256,
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
        write_json,
        write_jsonl,
    )
    from spec import (  # type: ignore
        ARTIFACT_NAME,
        CREATED_AT_DEFAULT,
        LANE_COUNTS,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        NEW_SENSE_QUOTAS,
        OFFICIAL_5_MANIFEST_PHYSICAL_SHA256,
        OFFICIAL_5_MANIFEST_SHA256,
        POLICY_ID,
        POOL_STRATUM_COUNTS,
        REPAIRED_5_MANIFEST_PHYSICAL_SHA256,
        REPAIRED_5_MANIFEST_SHA256,
        REVIEWED_15_MANIFEST_PHYSICAL_SHA256,
        REVIEWED_15_MANIFEST_SHA256,
        REVIEW_FIELDS,
        REVIEW_REQUIREMENT_BY_RISK,
        REVIEW_SLOTS_BY_RISK,
        RISK_BY_STRATUM,
        RISK_COUNTS_NEW,
        SOURCE_BATCH_MANIFEST_PHYSICAL_SHA256,
        SOURCE_BATCH_MANIFEST_SHA256,
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
    root: Path, expected_self: str, expected_physical: str
) -> dict[str, Any]:
    path = root / "manifest.json"
    if sha256_file(path) != expected_physical:
        raise ValueError(f"manifest physical hash mismatch: {path}")
    manifest = strict_json_object(path)
    if manifest.get("manifest_sha256") != expected_self:
        raise ValueError(f"manifest declared hash mismatch: {path}")
    if _manifest_self_hash(manifest) != expected_self:
        raise ValueError(f"manifest self hash mismatch: {path}")
    return manifest


def _verify_manifest_file(root: Path, manifest: Mapping[str, Any], relative: str) -> Path:
    metadata = manifest.get("files", {}).get(relative)
    if not isinstance(metadata, Mapping):
        raise ValueError(f"manifest omits required file: {relative}")
    path = root / relative
    if sha256_file(path) != metadata.get("sha256"):
        raise ValueError(f"manifest-bound file drift: {relative}")
    return path


def _normalized_candidate(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _load_document_index(path: Path) -> dict[str, Mapping[str, Any]]:
    path = path.resolve(strict=True)
    if sha256_file(path) != SOURCE_DOCUMENT_SHA256:
        raise ValueError("D2L source document hash mismatch")
    document = strict_json_object(path)
    result: dict[str, Mapping[str, Any]] = {}
    chapters = document.get("chapters")
    if not isinstance(chapters, list):
        raise ValueError("D2L source document chapters are invalid")
    for chapter in chapters:
        if not isinstance(chapter, Mapping) or not isinstance(chapter.get("blocks"), list):
            raise ValueError("D2L source document chapter is invalid")
        for block in chapter["blocks"]:
            if not isinstance(block, Mapping) or not isinstance(block.get("block_id"), str):
                raise ValueError("D2L source document block is invalid")
            result[block["block_id"]] = {"chapter": chapter, "block": block}
    return result


def _validate_real_context(
    context: Mapping[str, Any], document_index: Mapping[str, Mapping[str, Any]]
) -> None:
    if not verify_record(context, "context_sha256"):
        raise ValueError(f"V3 context self hash mismatch: {context.get('context_id')}")
    if context.get("binding_kind") != "EXACT_SURFACE_MATCH_CANDIDATE_NEUTRAL":
        return
    provenance = context.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError(f"real context provenance is missing: {context.get('context_id')}")
    if provenance.get("source_artifact_sha256") != SOURCE_DOCUMENT_SHA256:
        raise ValueError(f"real context source hash mismatch: {context.get('context_id')}")
    indexed = document_index.get(str(provenance.get("block_id")))
    if indexed is None:
        raise ValueError(f"real context block is missing: {context.get('context_id')}")
    block_text = indexed["block"].get("source_text")
    start = provenance.get("source_start")
    end = provenance.get("source_end")
    if (
        not isinstance(block_text, str)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or block_text[start:end] != context.get("source_text")
    ):
        raise ValueError(f"real context source slice mismatch: {context.get('context_id')}")


def _load_source_data(
    *,
    v3_root: Path,
    source_batch_root: Path,
    official_5_root: Path,
    reviewed_15_root: Path,
    repaired_5_root: Path,
    source_document: Path,
) -> dict[str, Any]:
    v3_manifest = _verify_manifest(
        v3_root, V3_MANIFEST_SHA256, V3_MANIFEST_PHYSICAL_SHA256
    )
    batch_manifest = _verify_manifest(
        source_batch_root,
        SOURCE_BATCH_MANIFEST_SHA256,
        SOURCE_BATCH_MANIFEST_PHYSICAL_SHA256,
    )
    official_manifest = _verify_manifest(
        official_5_root,
        OFFICIAL_5_MANIFEST_SHA256,
        OFFICIAL_5_MANIFEST_PHYSICAL_SHA256,
    )
    reviewed_manifest = _verify_manifest(
        reviewed_15_root,
        REVIEWED_15_MANIFEST_SHA256,
        REVIEWED_15_MANIFEST_PHYSICAL_SHA256,
    )
    repaired_manifest = _verify_manifest(
        repaired_5_root,
        REPAIRED_5_MANIFEST_SHA256,
        REPAIRED_5_MANIFEST_PHYSICAL_SHA256,
    )
    senses = strict_jsonl(
        _verify_manifest_file(v3_root, v3_manifest, "term_senses.jsonl")
    )
    candidates = strict_jsonl(
        _verify_manifest_file(v3_root, v3_manifest, "candidate_instances.jsonl")
    )
    contexts = strict_jsonl(
        _verify_manifest_file(v3_root, v3_manifest, "contexts.jsonl")
    )
    for row in senses:
        if not verify_record(row, "term_sense_sha256"):
            raise ValueError(f"V3 sense self hash mismatch: {row.get('sense_id')}")
    for row in candidates:
        if not verify_record(row, "candidate_instance_sha256"):
            raise ValueError(
                f"V3 candidate self hash mismatch: {row.get('candidate_instance_id')}"
            )
    document_index = _load_document_index(source_document)
    for row in contexts:
        _validate_real_context(row, document_index)

    case_rows: list[dict[str, Any]] = []
    batches_root = source_batch_root / "batches"
    for directory in sorted(path for path in batches_root.iterdir() if path.is_dir()):
        relative = f"batches/{directory.name}/sense_review_cases.jsonl"
        case_rows.extend(
            strict_jsonl(_verify_manifest_file(source_batch_root, batch_manifest, relative))
        )
    if len(case_rows) != 150 or len({row.get("sense_id") for row in case_rows}) != 150:
        raise ValueError("source Stage A case release does not cover 150 senses")

    official_senses = strict_jsonl(
        _verify_manifest_file(
            official_5_root, official_manifest, "materialized_input/term_senses_5.jsonl"
        )
    )
    ready_contracts = strict_jsonl(
        _verify_manifest_file(
            reviewed_15_root,
            reviewed_manifest,
            "effective_sense_contract_candidates_11.jsonl",
        )
    )
    reviewed_decisions = strict_jsonl(
        _verify_manifest_file(
            reviewed_15_root, reviewed_manifest, "merged_review_decisions_15.jsonl"
        )
    )
    repaired_senses = strict_jsonl(
        _verify_manifest_file(
            repaired_5_root, repaired_manifest, "reviewed_senses_5.jsonl"
        )
    )
    repaired_candidates = strict_jsonl(
        _verify_manifest_file(
            repaired_5_root, repaired_manifest, "reviewed_candidates_15.jsonl"
        )
    )
    repaired_contexts = strict_jsonl(
        _verify_manifest_file(
            repaired_5_root,
            repaired_manifest,
            "source_inputs/evidence_contexts_25.jsonl",
        )
    )
    return {
        "manifests": {
            "v3": v3_manifest,
            "source_batches": batch_manifest,
            "official_5": official_manifest,
            "reviewed_15": reviewed_manifest,
            "repaired_5": repaired_manifest,
        },
        "senses": senses,
        "candidates": candidates,
        "contexts": contexts,
        "cases": case_rows,
        "official_senses": official_senses,
        "ready_contracts": ready_contracts,
        "reviewed_decisions": reviewed_decisions,
        "repaired_senses": repaired_senses,
        "repaired_candidates": repaired_candidates,
        "repaired_contexts": repaired_contexts,
    }


def _quality_rank(
    sense: Mapping[str, Any],
    case: Mapping[str, Any],
    contexts_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[float, str, str]:
    evidence = case["evidence_contexts"]
    primary = evidence["primary"]
    backup = evidence["backup"]
    contrastive = evidence["contrastive"]
    primary_confidences = [
        float(contexts_by_id[row["context_id"]]["classification_confidence"])
        for row in primary
    ]
    real_contrastive = sum(
        contexts_by_id[row["context_id"]].get("binding_kind")
        == "EXACT_SURFACE_MATCH_CANDIDATE_NEUTRAL"
        for row in contrastive
    )
    score = (
        real_contrastive * 20
        + min(len(backup), 3) * 2
        + (sum(primary_confidences) / len(primary_confidences)) * 10
        + float(case["model_definition_confidence"]) * 5
        + float(case["model_part_of_speech_confidence"]) * 5
    )
    return (-score, str(sense["source_term"]).casefold(), str(sense["sense_id"]))


def _select_new_senses(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    senses_by_id = {row["sense_id"]: row for row in data["senses"]}
    cases_by_id = {row["sense_id"]: row for row in data["cases"]}
    contexts_by_id = {row["context_id"]: row for row in data["contexts"]}
    candidates_by_sense: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for candidate in data["candidates"]:
        candidates_by_sense[candidate["sense_id"]].append(candidate)

    official_ids = {row["sense_id"] for row in data["official_senses"]}
    ready_ids = {row["sense_id"] for row in data["ready_contracts"]}
    if not official_ids <= ready_ids or len(official_ids) != 5 or len(ready_ids) != 11:
        raise ValueError("official/review-ready seed identities mismatch")
    excluded_ids = set(ready_ids) | {
        row["parent_sense_id"] for row in data["repaired_senses"]
    }
    excluded_terms = {
        str(row["source_term"]).casefold() for row in data["ready_contracts"]
    } | {str(row["source_term"]).casefold() for row in data["repaired_senses"]}

    eligible: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sense_id, sense in senses_by_id.items():
        case = cases_by_id.get(sense_id)
        candidates = candidates_by_sense.get(sense_id, [])
        if (
            case is None
            or sense_id in excluded_ids
            or str(sense["source_term"]).casefold() in excluded_terms
        ):
            continue
        evidence = case.get("evidence_contexts")
        if not isinstance(evidence, Mapping):
            continue
        primary = evidence.get("primary")
        if not isinstance(primary, list) or len(primary) != 5:
            continue
        if len(candidates) != 3 or len(
            {
                _normalized_candidate(str(row["candidate_target_vi"]))
                for row in candidates
            }
        ) != 3:
            continue
        if float(case.get("model_definition_confidence", 0)) < 0.90 or float(
            case.get("model_part_of_speech_confidence", 0)
        ) < 0.90:
            continue
        valid_primary = True
        for projection in primary:
            context = contexts_by_id.get(projection.get("context_id"))
            if (
                context is None
                or context.get("binding_kind")
                != "EXACT_SURFACE_MATCH_CANDIDATE_NEUTRAL"
                or context.get("sense_relation") != "SAME_SENSE"
                or float(context.get("classification_confidence", 0)) < 0.80
            ):
                valid_primary = False
                break
        if not valid_primary:
            continue
        eligible[str(sense["stratum"])].append(
            {
                "sense": sense,
                "case": case,
                "candidates": sorted(
                    candidates, key=lambda row: str(row["candidate_slot_id"])
                ),
                "rank": _quality_rank(sense, case, contexts_by_id),
            }
        )
    selected: list[dict[str, Any]] = []
    for stratum, count in NEW_SENSE_QUOTAS.items():
        rows = sorted(eligible[stratum], key=lambda row: row["rank"])
        if len(rows) < count:
            raise ValueError(f"not enough eligible new senses for stratum: {stratum}")
        selected.extend(rows[:count])
    if len(selected) != 44 or Counter(
        row["sense"]["stratum"] for row in selected
    ) != Counter(NEW_SENSE_QUOTAS):
        raise ValueError("new-sense selection count mismatch")
    return selected


def _review_blank() -> dict[str, Any]:
    result: dict[str, Any] = {field: "" for field in REVIEW_FIELDS}
    result["invalid_evidence_context_ids"] = []
    result["candidate_replacements"] = []
    result["proposed_split_labels"] = []
    return result


def _unified_v3_context(
    *,
    sense_id: str,
    context: Mapping[str, Any],
    evidence_roles: Iterable[str],
) -> dict[str, Any]:
    provenance = context.get("provenance")
    if not isinstance(provenance, Mapping):
        provenance = {}
    synthetic = context.get("binding_kind") == "SYNTHETIC_BOUNDARY_PROBE"
    positive_eligible = (
        not synthetic
        and context.get("sense_relation") == "SAME_SENSE"
        and context.get("context_role") in {"PRIMARY", "BACKUP"}
    )
    return seal_record(
        {
            "schema_id": "D2LFastTrackSelectedContextV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "pool_sense_id": sense_id,
            "source_context_id": context["context_id"],
            "source_context_sha256": context["context_sha256"],
            "evidence_roles": sorted(set(evidence_roles)),
            "positive_evidence_eligible": positive_eligible,
            "boundary_only": synthetic or context.get("sense_relation") != "SAME_SENSE",
            "synthetic": synthetic,
            "source_text": context["source_text"],
            "content_sha256": context["content_sha256"],
            "matched_surface": context["matched_surface"],
            "context_role": context["context_role"],
            "context_slot": context["context_slot"],
            "sense_relation": context["sense_relation"],
            "binding_kind": context["binding_kind"],
            "chapter_id": provenance.get("chapter_id"),
            "block_id": provenance.get("block_id"),
            "sentence_id": provenance.get("sentence_id"),
            "source_artifact_ref": SOURCE_DOCUMENT_REF if not synthetic else None,
            "source_artifact_sha256": SOURCE_DOCUMENT_SHA256 if not synthetic else None,
            "provider_call_count": 0,
            "final_glossary_decision": None,
        },
        "selected_context_sha256",
    )


def _unified_repaired_context(
    *, sense_id: str, context: Mapping[str, Any]
) -> dict[str, Any]:
    return seal_record(
        {
            "schema_id": "D2LFastTrackSelectedContextV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "pool_sense_id": sense_id,
            "source_context_id": context["context_id"],
            "source_context_sha256": context["evidence_record_sha256"],
            "evidence_roles": ["EXISTING_REPAIRED_POSITIVE_EVIDENCE"],
            "positive_evidence_eligible": True,
            "boundary_only": False,
            "synthetic": False,
            "source_text": context["source_text"],
            "content_sha256": context["source_text_sha256"],
            "matched_surface": context.get("source_term"),
            "context_role": "PRIMARY",
            "context_slot": None,
            "sense_relation": "SAME_SENSE",
            "binding_kind": "EXACT_SOURCE_BLOCK",
            "chapter_id": context.get("chapter_id"),
            "block_id": context.get("block_id"),
            "sentence_id": None,
            "source_artifact_ref": SOURCE_DOCUMENT_REF,
            "source_artifact_sha256": SOURCE_DOCUMENT_SHA256,
            "provider_call_count": 0,
            "final_glossary_decision": None,
        },
        "selected_context_sha256",
    )


def _candidate_record(
    *,
    sense_id: str,
    source_term: str,
    lane: str,
    status: str,
    candidate: Mapping[str, Any],
    repaired: bool,
) -> dict[str, Any]:
    if repaired:
        candidate_id = candidate["candidate_id"]
        slot = candidate["candidate_slot"]
        target = candidate["candidate_target_vi"]
        source_sha = candidate["reviewed_candidate_sha256"]
    else:
        candidate_id = candidate["candidate_instance_id"]
        slot = candidate["candidate_slot_id"]
        target = candidate["candidate_target_vi"]
        source_sha = candidate["candidate_instance_sha256"]
    return seal_record(
        {
            "schema_id": "D2LFastTrackCandidatePoolRecordV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "sense_id": sense_id,
            "source_term": source_term,
            "lane": lane,
            "candidate_id": candidate_id,
            "candidate_slot": slot,
            "candidate_version": "1",
            "candidate_target_vi": target,
            "candidate_status": status,
            "source_candidate_sha256": source_sha,
            "intended_candidate_role": None,
            "provider_call_count": 0,
            "final_gold_label": None,
            "final_glossary_decision": None,
        },
        "candidate_pool_record_sha256",
    )


def _pool_record(
    *,
    sense_id: str,
    parent_sense_id: str,
    term_id: str,
    source_term: str,
    lane: str,
    pool_status: str,
    stratum: str,
    risk_class: str,
    definition_en: str,
    part_of_speech: str,
    scope: str,
    source_split: str,
    candidate_ids: list[str],
    context_ids: list[str],
    source_record_sha256: str,
) -> dict[str, Any]:
    review_slots = [] if lane != "D_NEW" else list(REVIEW_SLOTS_BY_RISK[risk_class])
    review_requirement = (
        "EXISTING_REVIEW_LINEAGE_LOCKED"
        if lane != "D_NEW"
        else REVIEW_REQUIREMENT_BY_RISK[risk_class]
    )
    return seal_record(
        {
            "schema_id": "D2LFastTrackSensePoolRecordV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "pool_record_id": stable_id("pool_", sense_id, lane, "v1"),
            "sense_id": sense_id,
            "parent_sense_id": parent_sense_id,
            "term_id": term_id,
            "source_term": source_term,
            "lane": lane,
            "pool_status": pool_status,
            "stratum": stratum,
            "risk_class": risk_class,
            "definition_en": definition_en,
            "part_of_speech": part_of_speech,
            "scope": scope,
            "source_split": source_split,
            "target_split_status": "PENDING_FINAL_50_FREEZE",
            "candidate_ids": candidate_ids,
            "evidence_context_ids": context_ids,
            "review_requirement": review_requirement,
            "review_slots": review_slots,
            "source_record_sha256": source_record_sha256,
            "provider_call_count": 0,
            "stage_b_gold_label": None,
            "final_glossary_decision": None,
        },
        "sense_pool_record_sha256",
    )


def _build_pool(
    data: Mapping[str, Any], selected_new: list[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    senses_by_id = {row["sense_id"]: row for row in data["senses"]}
    contexts_by_id = {row["context_id"]: row for row in data["contexts"]}
    v3_candidates_by_id = {
        row["candidate_instance_id"]: row for row in data["candidates"]
    }
    decisions_by_id = {row["sense_id"]: row for row in data["reviewed_decisions"]}
    official_ids = {row["sense_id"] for row in data["official_senses"]}
    repaired_contexts_by_sense: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in data["repaired_contexts"]:
        repaired_contexts_by_sense[row["output_sense_id"]].append(row)
    repaired_candidates_by_sense: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in data["repaired_candidates"]:
        repaired_candidates_by_sense[row["output_sense_id"]].append(row)

    pool: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    selected_context_keys: set[tuple[str, str]] = set()

    for contract in sorted(data["ready_contracts"], key=lambda row: row["sense_id"]):
        sense_id = contract["sense_id"]
        lane = "A_OFFICIAL" if sense_id in official_ids else "B_REVIEW_READY"
        status = "OFFICIAL_AUTHORITY_LOCKED" if lane == "A_OFFICIAL" else "LOCAL_REVIEW_READY"
        source_sense = senses_by_id[sense_id]
        decision = decisions_by_id[sense_id]
        candidate_rows = sorted(
            [v3_candidates_by_id[row] for row in contract["candidate_ids"]],
            key=lambda row: str(row["candidate_slot_id"]),
        )
        candidate_records = [
            _candidate_record(
                sense_id=sense_id,
                source_term=contract["source_term"],
                lane=lane,
                status="FROZEN_EXISTING_REVIEW",
                candidate=row,
                repaired=False,
            )
            for row in candidate_rows
        ]
        candidates.extend(candidate_records)
        roles_by_context: dict[str, set[str]] = defaultdict(set)
        for context_id in contract["positive_context_ids"]:
            roles_by_context[context_id].add("EXISTING_POSITIVE_EVIDENCE")
        for context_id in contract["boundary_context_ids"]:
            roles_by_context[context_id].add("EXISTING_BOUNDARY_EVIDENCE")
        context_records = []
        for context_id, roles in sorted(roles_by_context.items()):
            context = contexts_by_id[context_id]
            record = _unified_v3_context(
                sense_id=sense_id, context=context, evidence_roles=roles
            )
            context_records.append(record)
            selected_context_keys.add((sense_id, context_id))
        contexts.extend(context_records)
        pool.append(
            _pool_record(
                sense_id=sense_id,
                parent_sense_id=sense_id,
                term_id=contract["term_id"],
                source_term=contract["source_term"],
                lane=lane,
                pool_status=status,
                stratum=source_sense["stratum"],
                risk_class=decision["risk_class"],
                definition_en=contract["proposed_definition_en"],
                part_of_speech=contract["proposed_part_of_speech"],
                scope=contract["proposed_scope_note"],
                source_split=source_sense["split"],
                candidate_ids=[row["candidate_id"] for row in candidate_records],
                context_ids=[row["source_context_id"] for row in context_records],
                source_record_sha256=contract["candidate_record_sha256"],
            )
        )

    for sense in sorted(data["repaired_senses"], key=lambda row: row["output_sense_id"]):
        sense_id = sense["output_sense_id"]
        source_sense = senses_by_id[sense["parent_sense_id"]]
        parent_decision = decisions_by_id[sense["parent_sense_id"]]
        candidate_records = [
            _candidate_record(
                sense_id=sense_id,
                source_term=sense["source_term"],
                lane="C_REPAIRED",
                status="FROZEN_EXISTING_REVIEW",
                candidate=row,
                repaired=True,
            )
            for row in sorted(
                repaired_candidates_by_sense[sense_id],
                key=lambda row: row["candidate_slot"],
            )
        ]
        candidates.extend(candidate_records)
        context_records = [
            _unified_repaired_context(sense_id=sense_id, context=row)
            for row in sorted(
                repaired_contexts_by_sense[sense_id], key=lambda row: row["context_id"]
            )
        ]
        contexts.extend(context_records)
        pool.append(
            _pool_record(
                sense_id=sense_id,
                parent_sense_id=sense["parent_sense_id"],
                term_id=sense["parent_term_id"],
                source_term=sense["source_term"],
                lane="C_REPAIRED",
                pool_status="LOCAL_TARGETED_REPAIR_REVIEW_COMPLETE",
                stratum=source_sense["stratum"],
                risk_class=parent_decision["risk_class"],
                definition_en=sense["definition_en"],
                part_of_speech=sense["part_of_speech"],
                scope=sense["scope"],
                source_split=sense["split"],
                candidate_ids=[row["candidate_id"] for row in candidate_records],
                context_ids=[row["source_context_id"] for row in context_records],
                source_record_sha256=sense["reviewed_sense_sha256"],
            )
        )

    for selected in selected_new:
        source_sense = selected["sense"]
        case = selected["case"]
        sense_id = source_sense["sense_id"]
        risk = RISK_BY_STRATUM[source_sense["stratum"]]
        candidate_records = [
            _candidate_record(
                sense_id=sense_id,
                source_term=source_sense["source_term"],
                lane="D_NEW",
                status="PENDING_STAGE_A_REVIEW",
                candidate=row,
                repaired=False,
            )
            for row in selected["candidates"]
        ]
        candidates.extend(candidate_records)
        role_by_id: dict[str, set[str]] = defaultdict(set)
        evidence = case["evidence_contexts"]
        for group, role in (
            ("definition", "POSITIVE_DEFINITION_PROPOSAL"),
            ("part_of_speech", "POSITIVE_POS_PROPOSAL"),
            ("primary", "PRIMARY"),
            ("backup", "BACKUP"),
            ("contrastive", "BOUNDARY_PROPOSAL"),
        ):
            for projection in evidence[group]:
                role_by_id[projection["context_id"]].add(role)
        context_records = []
        for context_id, roles in sorted(role_by_id.items()):
            record = _unified_v3_context(
                sense_id=sense_id,
                context=contexts_by_id[context_id],
                evidence_roles=roles,
            )
            context_records.append(record)
            selected_context_keys.add((sense_id, context_id))
        contexts.extend(context_records)
        pool.append(
            _pool_record(
                sense_id=sense_id,
                parent_sense_id=sense_id,
                term_id=source_sense["term_id"],
                source_term=source_sense["source_term"],
                lane="D_NEW",
                pool_status="PENDING_STAGE_A_REVIEW",
                stratum=source_sense["stratum"],
                risk_class=risk,
                definition_en=case["model_definition_en"],
                part_of_speech=case["model_part_of_speech"],
                scope=source_sense["scope_id"],
                source_split=source_sense["split"],
                candidate_ids=[row["candidate_id"] for row in candidate_records],
                context_ids=[row["source_context_id"] for row in context_records],
                source_record_sha256=case["case_sha256"],
            )
        )

    if Counter(row["lane"] for row in pool) != Counter(LANE_COUNTS):
        raise ValueError("pool lane counts mismatch")
    if Counter(row["stratum"] for row in pool) != Counter(POOL_STRATUM_COUNTS):
        raise ValueError("pool stratum counts mismatch")
    if len(pool) != 60 or len(candidates) != 180:
        raise ValueError("pool/candidate cardinality mismatch")
    if len({row["sense_id"] for row in pool}) != 60 or len(
        {row["candidate_id"] for row in candidates}
    ) != 180:
        raise ValueError("pool/candidate identities are not unique")
    return (
        sorted(pool, key=lambda row: row["sense_id"]),
        sorted(candidates, key=lambda row: (row["sense_id"], row["candidate_slot"])),
        sorted(contexts, key=lambda row: (row["pool_sense_id"], row["source_context_id"])),
    )


def _interleave_new(pool: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    queues: dict[str, list[Mapping[str, Any]]] = {}
    for risk in RISK_COUNTS_NEW:
        queues[risk] = sorted(
            [row for row in pool if row["lane"] == "D_NEW" and row["risk_class"] == risk],
            key=lambda row: (str(row["source_term"]).casefold(), row["sense_id"]),
        )
    result: list[Mapping[str, Any]] = []
    order = tuple(RISK_COUNTS_NEW)
    while any(queues.values()):
        for risk in order:
            if queues[risk]:
                result.append(queues[risk].pop(0))
    if len(result) != 44:
        raise ValueError("interleaved Stage A case count mismatch")
    return result


def _source_payload(
    sense: Mapping[str, Any],
    candidates: list[Mapping[str, Any]],
    contexts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_id": "D2LFastTrackStageAReviewSourceV1",
        "policy_id": POLICY_ID,
        "pool_record_id": sense["pool_record_id"],
        "sense_id": sense["sense_id"],
        "term_id": sense["term_id"],
        "source_term": sense["source_term"],
        "stratum": sense["stratum"],
        "risk_class": sense["risk_class"],
        "review_requirement": sense["review_requirement"],
        "proposed_definition_en": sense["definition_en"],
        "proposed_part_of_speech": sense["part_of_speech"],
        "proposed_scope": sense["scope"],
        "candidates": [
            {
                "candidate_id": row["candidate_id"],
                "candidate_slot": row["candidate_slot"],
                "candidate_target_vi": row["candidate_target_vi"],
            }
            for row in candidates
        ],
        "evidence_contexts": [
            {
                "context_id": row["source_context_id"],
                "evidence_roles": row["evidence_roles"],
                "positive_evidence_eligible": row["positive_evidence_eligible"],
                "boundary_only": row["boundary_only"],
                "synthetic": row["synthetic"],
                "source_text": row["source_text"],
                "matched_surface": row["matched_surface"],
                "chapter_id": row["chapter_id"],
                "block_id": row["block_id"],
                "sentence_id": row["sentence_id"],
                "content_sha256": row["content_sha256"],
            }
            for row in contexts
        ],
        "source_sense_pool_record_sha256": sense["sense_pool_record_sha256"],
        "provider_call_count": 0,
    }


def _review_input(
    *, batch_id: str, reviewer_slot: str, payloads: list[Mapping[str, Any]]
) -> dict[str, Any]:
    cases = []
    for source_payload in payloads:
        cases.append(
            {
                "source_payload": source_payload,
                "source_payload_sha256": sha256_bytes(
                    canonical_json_bytes(source_payload)
                ),
                "review": _review_blank(),
            }
        )
    source_input_sha256 = sha256_bytes(
        canonical_json_bytes(
            [
                {
                    "sense_id": row["source_payload"]["sense_id"],
                    "source_payload_sha256": row["source_payload_sha256"],
                }
                for row in cases
            ]
        )
    )
    return {
        "schema_id": "D2LFastTrackStageAReviewerInputV1",
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "batch_id": batch_id,
        "reviewer_slot": reviewer_slot,
        "source_input_sha256": source_input_sha256,
        "independence_requirement": "DO_NOT_VIEW_OTHER_REVIEWER_OUTPUTS",
        "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_FIELDS_FILLED",
        "cases": cases,
    }


def _write_reviewer_handoff(
    *, staging: Path, batch_id: str, reviewer_slot: str, input_path: Path
) -> tuple[Path, str]:
    handoff_temp = staging / ".handoff" / f"{batch_id}_{reviewer_slot}"
    handoff_temp.mkdir(parents=True)
    shutil.copy2(input_path, handoff_temp / "review_input.json")
    instructions = (
        "# Stage A review instructions\n\n"
        "Review each sense independently from the supplied D2L evidence. Fill only "
        "the fields inside `review`; do not change `source_payload` or "
        "`source_payload_sha256`. Synthetic rows are boundary-only and must never be "
        "used as positive evidence. Return only the completed `review_input.json`.\n\n"
        "Allowed standard decisions: ACCEPT, REVISE, UNJUDGEABLE. Allowed sense "
        "statuses: READY_FOR_CONTRACT_CONSTRUCTION, REVISION_REQUIRED, "
        "SPLIT_REQUIRED, UNRESOLVED, QUARANTINED. Set review_status=COMPLETE.\n"
    )
    (handoff_temp / "REVIEW_INSTRUCTIONS.md").write_text(
        instructions, encoding="utf-8", newline="\n"
    )
    message = (
        f"Review Stage A batch {batch_id} as {reviewer_slot}. Work independently and "
        "do not inspect any other reviewer output. Read REVIEW_INSTRUCTIONS.md, fill "
        "only the review fields in review_input.json, preserve every source field, "
        "and return only the completed JSON file."
    )
    (handoff_temp / "MESSAGE.md").write_text(
        message + "\n", encoding="utf-8", newline="\n"
    )
    write_checksums(handoff_temp, handoff_temp / "CHECKSUMS.sha256")
    zip_path = staging / "handoff" / f"{batch_id}_{reviewer_slot}.zip"
    build_deterministic_zip(handoff_temp, zip_path)
    return zip_path, sha256_file(zip_path)


def _build_batches(
    *,
    staging: Path,
    pool: list[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
    contexts: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidates_by_sense: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    contexts_by_sense: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in candidates:
        candidates_by_sense[row["sense_id"]].append(row)
    for row in contexts:
        contexts_by_sense[row["pool_sense_id"]].append(row)
    ordered = _interleave_new(pool)
    batches = [ordered[index : index + 5] for index in range(0, len(ordered), 5)]
    if len(batches) != 9 or [len(rows) for rows in batches] != [5] * 8 + [4]:
        raise ValueError("Stage A batch partition mismatch")
    index_rows: list[dict[str, Any]] = []
    for sequence, senses in enumerate(batches, start=1):
        batch_id = f"batch_{sequence:03d}"
        batch_dir = staging / "batches" / batch_id
        batch_dir.mkdir(parents=True)
        source_payloads = []
        for sense in senses:
            source_payloads.append(
                _source_payload(
                    sense,
                    sorted(
                        candidates_by_sense[sense["sense_id"]],
                        key=lambda row: row["candidate_slot"],
                    ),
                    sorted(
                        contexts_by_sense[sense["sense_id"]],
                        key=lambda row: row["source_context_id"],
                    ),
                )
            )
        write_json(batch_dir / "review_cases.json", source_payloads)
        reviewer_1 = _review_input(
            batch_id=batch_id, reviewer_slot="reviewer_1", payloads=source_payloads
        )
        reviewer_2_payloads = [
            row for row in source_payloads if row["risk_class"] in {"R3_AMBIGUOUS", "R4_SPLIT_OR_POS_RISK"}
        ]
        reviewer_2 = _review_input(
            batch_id=batch_id,
            reviewer_slot="reviewer_2",
            payloads=reviewer_2_payloads,
        )
        write_json(batch_dir / "reviewer_1_input.json", reviewer_1)
        write_json(batch_dir / "reviewer_2_input.json", reviewer_2)
        handoff_1, handoff_1_sha = _write_reviewer_handoff(
            staging=staging,
            batch_id=batch_id,
            reviewer_slot="reviewer_1",
            input_path=batch_dir / "reviewer_1_input.json",
        )
        handoff_2, handoff_2_sha = _write_reviewer_handoff(
            staging=staging,
            batch_id=batch_id,
            reviewer_slot="reviewer_2",
            input_path=batch_dir / "reviewer_2_input.json",
        )
        risk_counts = Counter(row["risk_class"] for row in source_payloads)
        batch_manifest = seal_integrity(
            {
                "schema_id": "D2LFastTrackStageABatchManifestV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "batch_id": batch_id,
                "sequence": sequence,
                "sense_count": len(source_payloads),
                "reviewer_1_case_count": len(source_payloads),
                "reviewer_2_case_count": len(reviewer_2_payloads),
                "mandatory_adjudication_count": risk_counts["R4_SPLIT_OR_POS_RISK"],
                "conditional_adjudication_count": risk_counts["R3_AMBIGUOUS"],
                "blind_audit_count": risk_counts["R0_CLEAR"],
                "risk_counts": dict(sorted(risk_counts.items())),
                "sense_ids": [row["sense_id"] for row in source_payloads],
                "reviewer_1_input_sha256": sha256_file(
                    batch_dir / "reviewer_1_input.json"
                ),
                "reviewer_2_input_sha256": sha256_file(
                    batch_dir / "reviewer_2_input.json"
                ),
                "reviewer_1_handoff_zip": handoff_1.relative_to(staging).as_posix(),
                "reviewer_1_handoff_zip_sha256": handoff_1_sha,
                "reviewer_2_handoff_zip": handoff_2.relative_to(staging).as_posix(),
                "reviewer_2_handoff_zip_sha256": handoff_2_sha,
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            }
        )
        write_json(batch_dir / "batch_manifest.json", batch_manifest)
        index_rows.append(
            {
                "batch_id": batch_id,
                "sequence": sequence,
                "sense_count": len(source_payloads),
                "reviewer_1_case_count": len(source_payloads),
                "reviewer_2_case_count": len(reviewer_2_payloads),
                "mandatory_adjudication_count": risk_counts["R4_SPLIT_OR_POS_RISK"],
                "conditional_adjudication_count": risk_counts["R3_AMBIGUOUS"],
                "blind_audit_count": risk_counts["R0_CLEAR"],
                "risk_counts": dict(sorted(risk_counts.items())),
                "sense_ids": [row["sense_id"] for row in source_payloads],
                "batch_manifest_sha256": batch_manifest["integrity"]["self_sha256"],
            }
        )
    shutil.rmtree(staging / ".handoff", ignore_errors=True)
    return index_rows


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/build_fast_track_stage_a.py",
        "tools/validate_fast_track_stage_a.py",
        "tests/test_fast_track_stage_a.py",
    ):
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"release source file is missing: {relative}")
        target = staging / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _write_metadata(
    *,
    staging: Path,
    created_at: str,
    pool: list[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
    contexts: list[Mapping[str, Any]],
    batches: list[Mapping[str, Any]],
    source_roots: Mapping[str, Path],
) -> dict[str, Any]:
    workload = {
        "existing_senses_not_re_reviewed": 16,
        "new_senses_requiring_stage_a": 44,
        "reviewer_1_cases": 44,
        "reviewer_2_cases": 31,
        "independent_stage_a_review_decisions": 75,
        "blind_audits_r0": 13,
        "mandatory_adjudications_r4": 16,
        "conditional_adjudications_r3_max": 15,
        "stage_b_candidate_reviews_after_final_50": 300,
    }
    report = f"""# D2L Fast-Track 50-sense Stage A intake

Status: `{STATUS}`

- Pool: 60 senses and 180 provisional candidates.
- Existing review lineage reused: 16 senses.
- New Stage A cases: 44 senses in nine JSON batches.
- Reviewer 1: 44 cases.
- Reviewer 2: 31 R3/R4 cases.
- R0 blind audits: 13.
- Mandatory R4 adjudications: 16.
- R3 adjudication: only on disagreement, at most 15.

Positive evidence is always backed by real D2L source text. Synthetic probes,
when present, are explicitly boundary-only. Candidate intended roles, Stage B
gold, C/E/Global outputs, and final glossary decisions are absent.
"""
    (staging / "RELEASE_REPORT.md").write_text(
        report, encoding="utf-8", newline="\n"
    )
    summary = seal_integrity(
        {
            "schema_id": "D2LFastTrackStageASelectionReportV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "status": STATUS,
            "counts": {
                "sense_pool": len(pool),
                "candidate_pool": len(candidates),
                "selected_context": len(contexts),
                "stage_a_new_sense": 44,
                "stage_a_batch": len(batches),
            },
            "lane_counts": dict(sorted(Counter(row["lane"] for row in pool).items())),
            "pool_stratum_counts": dict(
                sorted(Counter(row["stratum"] for row in pool).items())
            ),
            "new_risk_counts": dict(
                sorted(
                    Counter(
                        row["risk_class"] for row in pool if row["lane"] == "D_NEW"
                    ).items()
                )
            ),
            "workload": workload,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "created_at": created_at,
        }
    )
    write_json(staging / "selection_report.json", summary)
    write_json(staging / "batch_index.json", batches)
    lineage = seal_integrity(
        {
            "schema_id": "D2LFastTrackStageALineageV1",
            "schema_version": "1.0.0",
            "v3_manifest_sha256": V3_MANIFEST_SHA256,
            "source_batch_manifest_sha256": SOURCE_BATCH_MANIFEST_SHA256,
            "official_5_manifest_sha256": OFFICIAL_5_MANIFEST_SHA256,
            "reviewed_15_manifest_sha256": REVIEWED_15_MANIFEST_SHA256,
            "repaired_5_manifest_sha256": REPAIRED_5_MANIFEST_SHA256,
            "source_document_sha256": SOURCE_DOCUMENT_SHA256,
            "canonical_main_dataset_authority": {
                "main_commit": MAIN_DATASET_AUTHORITY_COMMIT,
                "accepted_zip_sha256": MAIN_DATASET_AUTHORITY_ZIP_SHA256,
                "relationship": "LANE_A_IMMUTABLE_SEED_ONLY",
            },
            "provider_call_count": 0,
            "final_glossary_decision": None,
        }
    )
    write_json(staging / "lineage.json", lineage)
    source_manifests = staging / "source_manifests"
    source_manifests.mkdir()
    for name, root in source_roots.items():
        shutil.copy2(root / "manifest.json", source_manifests / f"{name}_manifest.json")
    write_json(
        staging / "environment.json",
        {
            "schema_id": "D2LFastTrackStageAEnvironmentV1",
            "created_at": created_at,
            "network_calls": 0,
            "provider_calls": 0,
        },
    )
    (staging / "commands.txt").write_text(
        "python -B source/tools/validate_fast_track_stage_a.py --artifact-root .\n",
        encoding="ascii",
        newline="\n",
    )
    (staging / "junit.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testsuite name="fast-track-stage-a" tests="1" failures="0" errors="0" '
        'skipped="0"><testcase classname="release" name="internal_validation"/></testsuite>\n',
        encoding="utf-8",
        newline="\n",
    )
    return summary


def build_fast_track_stage_a(
    *,
    v3_root: Path,
    source_batch_root: Path,
    official_5_root: Path,
    reviewed_15_root: Path,
    repaired_5_root: Path,
    source_document: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    roots = {
        "v3": v3_root.resolve(strict=True),
        "source_batches": source_batch_root.resolve(strict=True),
        "official_5": official_5_root.resolve(strict=True),
        "reviewed_15": reviewed_15_root.resolve(strict=True),
        "repaired_5": repaired_5_root.resolve(strict=True),
    }
    data = _load_source_data(
        v3_root=roots["v3"],
        source_batch_root=roots["source_batches"],
        official_5_root=roots["official_5"],
        reviewed_15_root=roots["reviewed_15"],
        repaired_5_root=roots["repaired_5"],
        source_document=source_document,
    )
    selected_new = _select_new_senses(data)
    pool, candidates, contexts = _build_pool(data, selected_new)

    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        write_jsonl(staging / "master_pool_60.jsonl", pool)
        write_jsonl(staging / "candidate_inventory_180.jsonl", candidates)
        write_jsonl(staging / "contexts_selected.jsonl", contexts)
        batches = _build_batches(
            staging=staging, pool=pool, candidates=candidates, contexts=contexts
        )
        summary = _write_metadata(
            staging=staging,
            created_at=created_at,
            pool=pool,
            candidates=candidates,
            contexts=contexts,
            batches=batches,
            source_roots=roots,
        )
        _write_source_bundle(staging)
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LFastTrackStageAManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "created_at": created_at,
            "status": STATUS,
            "counts": summary["counts"],
            "lane_counts": summary["lane_counts"],
            "pool_stratum_counts": summary["pool_stratum_counts"],
            "new_risk_counts": summary["new_risk_counts"],
            "workload": summary["workload"],
            "v3_manifest_sha256": V3_MANIFEST_SHA256,
            "source_batch_manifest_sha256": SOURCE_BATCH_MANIFEST_SHA256,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")

        try:
            from .validate_fast_track_stage_a import validate_artifact
        except ImportError:  # pragma: no cover
            from validate_fast_track_stage_a import validate_artifact  # type: ignore
        errors = validate_artifact(staging)
        if errors:
            raise ValueError("internal validation failed: " + "; ".join(errors))

        zip_name = f"{ARTIFACT_NAME}_release.zip"
        temporary_zip = temporary / zip_name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temporary_zip, final_zip)
        zip_sha256 = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_sha256} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "release_zip": str(final_zip),
            "release_zip_sha256": zip_sha256,
            "counts": manifest["counts"],
            "workload": manifest["workload"],
            "batch_1_reviewer_1_zip": str(
                output_root / "handoff" / "batch_001_reviewer_1.zip"
            ),
            "batch_1_reviewer_2_zip": str(
                output_root / "handoff" / "batch_001_reviewer_2.zip"
            ),
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--v3-root",
        type=Path,
        default=repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3",
    )
    parser.add_argument(
        "--source-batch-root",
        type=Path,
        default=repo_root / "dataset" / "d2l_stage_a_review_batches_v1" / "release",
    )
    parser.add_argument(
        "--official-5-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_stage_a_pilot_5_senses_official_v1"
        / "release"
        / "d2l_stage_a_pilot_5_senses_official_v1",
    )
    parser.add_argument(
        "--reviewed-15-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_stage_a_pilot_15_senses_reviewed_v1"
        / "release"
        / "d2l_stage_a_pilot_15_senses_reviewed_v1",
    )
    parser.add_argument(
        "--repaired-5-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_stage_a_targeted_repair_review_complete_5_senses_v1"
        / "release"
        / "d2l_stage_a_targeted_repair_review_complete_5_senses_v1",
    )
    parser.add_argument(
        "--source-document",
        type=Path,
        default=Path(
            r"C:\work\agent-based-translation-d2l-direct-builder-v1\jobs\src_d2l_full_book_local_b858af3a5252\source_package_snapshot\document.json"
        ),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default=CREATED_AT_DEFAULT)
    args = parser.parse_args()
    result = build_fast_track_stage_a(
        v3_root=args.v3_root,
        source_batch_root=args.source_batch_root,
        official_5_root=args.official_5_root,
        reviewed_15_root=args.reviewed_15_root,
        repaired_5_root=args.repaired_5_root,
        source_document=args.source_document,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
