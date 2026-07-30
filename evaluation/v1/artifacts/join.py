"""Exact candidate joins and split leakage checks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from ..identities import CandidateKey, IdentityError, evidence_source_ids, row_candidate_key, source_block_ids


class JoinError(ValueError):
    """Raised for ambiguous, missing or mismatched candidate joins."""


def _index(rows: Iterable[Mapping[str, Any]], label: str) -> dict[CandidateKey, Mapping[str, Any]]:
    result: dict[CandidateKey, Mapping[str, Any]] = {}
    for row in rows:
        try:
            key = row_candidate_key(row)
        except IdentityError as exc:
            raise JoinError(f"{label}: {exc}") from exc
        if key in result:
            raise JoinError(f"{label}: duplicate candidate key {key.as_string()}")
        result[key] = row
    return result


def exact_join(
    base_rows: Iterable[Mapping[str, Any]],
    *,
    gold_rows: Iterable[Mapping[str, Any]] | None = None,
    c_rows: Iterable[Mapping[str, Any]] | None = None,
    e_rows: Iterable[Mapping[str, Any]] | None = None,
    global_rows: Iterable[Mapping[str, Any]] | None = None,
    require_gold: bool = True,
) -> list[dict[str, Any]]:
    base = _index(base_rows, "base")
    indexes = {
        "gold": _index(gold_rows or (), "gold"),
        "c": _index(c_rows or (), "c"),
        "e": _index(e_rows or (), "e"),
        "global": _index(global_rows or (), "global"),
    }
    result: list[dict[str, Any]] = []
    for key, base_row in base.items():
        merged: dict[str, Any] = dict(base_row)
        merged["candidate_key"] = key.as_dict()
        for label, index in indexes.items():
            if key not in index:
                if label == "gold" and require_gold:
                    raise JoinError(f"missing gold for {key.as_string()}")
                merged[label] = None
            else:
                merged[label] = dict(index[key])
        result.append(merged)
    base_keys = set(base)
    for label, index in indexes.items():
        extras = set(index) - base_keys
        if extras:
            rendered = sorted(key.as_string() for key in extras)
            raise JoinError(f"{label} contains candidates absent from base: {rendered}")
    return result


def validate_split_leakage(rows: Iterable[Mapping[str, Any]]) -> None:
    by_group: dict[str, set[str]] = defaultdict(set)
    by_sense: dict[str, set[str]] = defaultdict(set)
    by_candidate: dict[CandidateKey, str] = {}
    evidence_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        key = row_candidate_key(row)
        split = row.get("split")
        if split not in {"development", "validation", "test", "synthetic"}:
            raise JoinError(f"invalid split for {key.as_string()}: {split}")
        if key in by_candidate and by_candidate[key] != split:
            raise JoinError(f"candidate appears in multiple splits: {key.as_string()}")
        by_candidate[key] = split
        by_sense[key.sense_id].add(split)
        cluster = row.get("source_block_cluster")
        if cluster:
            by_group[str(cluster)].add(split)
        for source_id in evidence_source_ids(row):
            evidence_splits[source_id].add(split)
    leaked_senses = {key: sorted(value) for key, value in by_sense.items() if len(value) > 1}
    if leaked_senses:
        raise JoinError(f"sense leakage: {leaked_senses}")
    leaked_clusters = {key: sorted(value) for key, value in by_group.items() if len(value) > 1}
    if leaked_clusters:
        raise JoinError(f"source-block cluster leakage: {leaked_clusters}")
    leaked_sources = {key: sorted(value) for key, value in evidence_splits.items() if len(value) > 1}
    if leaked_sources:
        raise JoinError(f"evidence-source leakage: {leaked_sources}")
