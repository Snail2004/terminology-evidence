"""Deterministic duplicate clustering independent of source ownership."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Mapping, Sequence


DEDUP_POLICY_VERSION = "dedup-v2"


def cluster_evidence_documents(
    rows: Sequence[Mapping[str, Any]],
    *,
    near_duplicate_threshold: float = 0.90,
) -> list[dict[str, Any]]:
    if not 0 <= near_duplicate_threshold <= 1:
        raise ValueError("near_duplicate_threshold must be in [0, 1]")
    normalized = [dict(row) for row in rows]
    parent = list(range(len(normalized)))
    token_sets = [_token_set(str(row["document_text"])) for row in normalized]
    fingerprints = [
        hashlib.sha256(
            _normalized_text(str(row["document_text"])).encode("utf-8")
        ).hexdigest()
        for row in normalized
    ]

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for left in range(len(normalized)):
        for right in range(left + 1, len(normalized)):
            exact = fingerprints[left] == fingerprints[right]
            near = _jaccard(token_sets[left], token_sets[right]) >= (
                near_duplicate_threshold
            )
            if exact or near:
                union(left, right)

    groups: dict[int, list[int]] = {}
    for index in range(len(normalized)):
        groups.setdefault(find(index), []).append(index)
    cluster_ids: dict[int, str] = {}
    cluster_reasons: dict[int, tuple[str, ...]] = {}
    for root, indices in groups.items():
        seed = "\0".join(
            sorted(
                str(normalized[index]["canonical_url"])
                for index in indices
            )
        )
        cluster_ids[root] = "cluster_" + hashlib.sha256(
            seed.encode("utf-8")
        ).hexdigest()[:24]
        reasons: set[str] = set()
        for left_position, left in enumerate(indices):
            for right in indices[left_position + 1 :]:
                if fingerprints[left] == fingerprints[right]:
                    reasons.add("EXACT_CONTENT_HASH")
                elif _jaccard(token_sets[left], token_sets[right]) >= (
                    near_duplicate_threshold
                ):
                    reasons.add("NEAR_DUPLICATE_CONTENT")
        cluster_reasons[root] = tuple(sorted(reasons))
    for index, row in enumerate(normalized):
        root = find(index)
        row["duplicate_cluster_id"] = cluster_ids[root]
        # Retained in V1.1 as a compatibility alias for the document cluster.
        row["independent_cluster_id"] = cluster_ids[root]
        row["publisher_id"] = _identity_id(
            "publisher", str(row.get("publisher", ""))
        )
        row["organization_id"] = _identity_id(
            "organization", str(row.get("organization", ""))
        )
        row["independence_group_id"] = row["organization_id"]
        row["dedup_reasons"] = list(cluster_reasons[root])
        row["document_fingerprint_sha256"] = fingerprints[index]
    return normalized


def build_duplicate_cluster_ledger(
    rows: Sequence[Mapping[str, Any]],
    representatives: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    representative_by_cluster = {
        str(row["duplicate_cluster_id"]): str(row["evidence_id"])
        for row in representatives
    }
    members_by_cluster: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        members_by_cluster.setdefault(
            str(row["duplicate_cluster_id"]), []
        ).append(row)
    ledger: list[dict[str, Any]] = []
    for cluster_id, members in sorted(members_by_cluster.items()):
        member_ids = sorted(str(row["evidence_id"]) for row in members)
        reasons = sorted(
            {
                str(reason)
                for row in members
                for reason in row.get("dedup_reasons", ())
            }
        )
        ledger.append(
            {
                "duplicate_cluster_id": cluster_id,
                "representative_evidence_id": representative_by_cluster[
                    cluster_id
                ],
                "member_evidence_ids": member_ids,
                "member_content_sha256": sorted(
                    {str(row["content_sha256"]) for row in members}
                ),
                "publisher_ids": sorted(
                    {str(row["publisher_id"]) for row in members}
                ),
                "organization_ids": sorted(
                    {str(row["organization_id"]) for row in members}
                ),
                "dedup_reasons": reasons,
            }
        )
    return ledger


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).casefold()
    return re.sub(r"\W+", " ", normalized, flags=re.UNICODE).strip()


def _token_set(value: str) -> frozenset[str]:
    return frozenset(_normalized_text(value).split())


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _identity_id(kind: str, value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).strip().casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{kind}_{digest}"


__all__ = [
    "DEDUP_POLICY_VERSION",
    "build_duplicate_cluster_ledger",
    "cluster_evidence_documents",
]
