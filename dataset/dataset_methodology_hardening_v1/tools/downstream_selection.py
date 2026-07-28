from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


POLICY_ID = "d2l_downstream_one_high_risk_block_per_chapter_v1"
TRANSFORMATION_VERSION = "1.0.0"


def select_downstream_blocks(
    audit_rows: list[dict[str, Any]],
    senses: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    source_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    senses_by_id = {row["sense_id"]: row for row in senses}
    candidate_counts: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        candidate_counts[candidate["sense_id"]] += 1
    source_term_senses: dict[str, set[str]] = defaultdict(set)
    for sense in senses:
        source_term_senses[sense["source_term"].strip().casefold()].add(
            sense["sense_id"]
        )
    multi_sense_terms = {
        term for term, sense_ids in source_term_senses.items() if len(sense_ids) > 1
    }
    block_registry = {row["block_id"]: row for row in source_blocks}
    block_contexts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for audit in audit_rows:
        if audit["eligible_for_c_support"]:
            block_contexts[audit["block_id"]].append(audit)

    ranked_by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block_id, contexts in block_contexts.items():
        block = block_registry[block_id]
        sense_ids = {row["sense_id"] for row in contexts}
        word_count = max(1, len(re.findall(r"\w+", block["source_text"], re.UNICODE)))
        ambiguous = sum(
            senses_by_id[sense_id]["stratum"] == "ambiguous"
            for sense_id in sense_ids
        )
        collision = sum(
            senses_by_id[sense_id]["stratum"] == "collision_or_multi_target"
            for sense_id in sense_ids
        )
        multi_sense = sum(
            senses_by_id[sense_id]["source_term"].strip().casefold()
            in multi_sense_terms
            for sense_id in sense_ids
        )
        row = {
            "schema_id": "D2LMethodologyDownstreamBlockSelectionV1",
            "block_id": block_id,
            "document_id": block["document_id"],
            "chapter_id": block["chapter_id"],
            "terminology_density": round(len(sense_ids) / word_count, 8),
            "term_sense_count": len(sense_ids),
            "ambiguous_term_count": ambiguous,
            "multi_sense_term_count": multi_sense,
            "collision_risk_count": collision,
            "candidate_competition_count": sum(
                candidate_counts[sense_id] for sense_id in sense_ids
            ),
            "tail_context_count": sum(
                row.get("context_type") in {"C4", "C5"} for row in contexts
            ),
            "block_length": word_count,
            "domain_subsection": block["chapter_id"],
            "selection_reason": (
                "Highest deterministic risk-density rank within chapter before A-D runs."
            ),
            "block_selection_policy_version": POLICY_ID,
            "selected_before_model_run": True,
            "experiment_arms": ["A", "B", "C", "D"],
            "parent_record_id": block_id,
            "parent_record_sha256": block["block_text_sha256"],
            "transformation_id": "d2l_methodology_downstream_block_selection",
            "transformation_version": TRANSFORMATION_VERSION,
        }
        ranked_by_chapter[block["chapter_id"]].append(row)

    selected = []
    for chapter_id, rows in sorted(ranked_by_chapter.items()):
        rows.sort(
            key=lambda row: (
                -row["collision_risk_count"],
                -row["ambiguous_term_count"],
                -row["term_sense_count"],
                -row["terminology_density"],
                row["block_id"],
            )
        )
        selected.append(rows[0])
    return selected
