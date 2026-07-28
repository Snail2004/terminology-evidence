from __future__ import annotations

from collections import defaultdict
from typing import Any

from hardening_common import stable_id


TRANSFORMATION_ID = "d2l_methodology_statistical_units"
TRANSFORMATION_VERSION = "1.0.0"


def build_statistical_units(
    audit_rows: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    senses: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    contexts_by_id = {row["context_id"]: row for row in contexts}
    senses_by_id = {row["sense_id"]: row for row in senses}
    candidates_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_sense[candidate["sense_id"]].append(candidate)

    rows: list[dict[str, Any]] = []
    for audit in audit_rows:
        if not audit["eligible_for_c_support"]:
            continue
        context = contexts_by_id[audit["context_id"]]
        sense = senses_by_id[context["sense_id"]]
        for candidate in sorted(
            candidates_by_sense[sense["sense_id"]],
            key=lambda row: row["candidate_instance_id"],
        ):
            candidate_id = candidate["candidate_instance_id"]
            occurrence_id = stable_id(
                "occurrence",
                candidate_id,
                context["context_id"],
                audit["document_id"],
                audit["block_id"],
            )
            pairing_id = stable_id(
                "pairing",
                sense["sense_id"],
                candidate["candidate_slot_id"],
                context["context_id"],
            )
            rows.append(
                {
                    "schema_id": "D2LMethodologyStatisticalUnitV1",
                    "candidate_id": candidate_id,
                    "candidate_slot_id": candidate["candidate_slot_id"],
                    "candidate_version": candidate["schema_version"],
                    "sense_id": sense["sense_id"],
                    "scope_id": sense["scope_id"],
                    "split": sense["split"],
                    "document_id": audit["document_id"],
                    "chapter_id": audit["chapter_id"],
                    "block_id": audit["block_id"],
                    "context_id": context["context_id"],
                    "context_role": context["context_role"],
                    "occurrence_id": occurrence_id,
                    "pairing_id": pairing_id,
                    "resampling_group_id": stable_id(
                        "resampling_group", sense["sense_id"]
                    ),
                    "source_block_cluster_id": stable_id(
                        "source_block_cluster", audit["document_id"], audit["block_id"]
                    ),
                    "parent_record_id": candidate_id,
                    "parent_record_sha256": candidate["candidate_instance_sha256"],
                    "parent_context_id": context["context_id"],
                    "parent_context_sha256": context["context_sha256"],
                    "transformation_id": TRANSFORMATION_ID,
                    "transformation_version": TRANSFORMATION_VERSION,
                }
            )
    rows.sort(key=lambda row: row["occurrence_id"])

    cluster_splits: dict[str, set[str]] = defaultdict(set)
    cluster_blocks: dict[str, str] = {}
    cluster_senses: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        cluster = row["source_block_cluster_id"]
        cluster_splits[cluster].add(row["split"])
        cluster_blocks[cluster] = row["block_id"]
        cluster_senses[cluster].add(row["sense_id"])
    leakage = [
        {
            "schema_id": "D2LMethodologySourceBlockLeakageV1",
            "source_block_cluster_id": cluster,
            "block_id": cluster_blocks[cluster],
            "splits": sorted(splits),
            "sense_ids": sorted(cluster_senses[cluster]),
            "status": "CROSS_SPLIT_SOURCE_BLOCK_CLUSTER",
        }
        for cluster, splits in sorted(cluster_splits.items())
        if len(splits) > 1
    ]
    return rows, leakage


def validate_statistical_ids(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    occurrence_ids: set[str] = set()
    for row in rows:
        expected_occurrence = stable_id(
            "occurrence",
            row["candidate_id"],
            row["context_id"],
            row["document_id"],
            row["block_id"],
        )
        expected_pairing = stable_id(
            "pairing",
            row["sense_id"],
            row.get("candidate_slot_id", ""),
            row["context_id"],
        )
        if row["occurrence_id"] != expected_occurrence:
            errors.append(f"Occurrence ID mismatch: {row['occurrence_id']}")
        if row["occurrence_id"] in occurrence_ids:
            errors.append(f"Duplicate occurrence ID: {row['occurrence_id']}")
        occurrence_ids.add(row["occurrence_id"])
        if not row.get("pairing_id"):
            errors.append(f"Missing pairing ID: {row['occurrence_id']}")
        if not row.get("resampling_group_id") or not row.get("source_block_cluster_id"):
            errors.append(f"Missing grouping ID: {row['occurrence_id']}")
        if "candidate_slot_id" in row and row["pairing_id"] != expected_pairing:
            errors.append(f"Pairing ID mismatch: {row['occurrence_id']}")
    return errors
