from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class QuerySpec:
    query_id: str
    query_class: str
    query_text: str


@dataclass(frozen=True)
class QueryPlan:
    query_plan_id: str
    query_policy_version: str
    queries: tuple[QuerySpec, ...]


def build_query_plan(
    candidate: Mapping[str, Any],
    *,
    max_queries: int = 3,
    restricted_source_domains: tuple[str, ...] = (),
) -> QueryPlan:
    if max_queries < 1:
        raise ValueError("max_queries must be positive")
    candidate_vi = str(candidate["candidate_vi"]).strip()
    source_term = str(candidate["source_term"]).strip()
    domain = candidate["domain_profile"]
    vi_anchors = [str(item).strip() for item in domain["vi_anchors"] if str(item).strip()]
    anchors = " ".join(vi_anchors[:3])
    raw = [
        ("EXACT_CANDIDATE", f'"{candidate_vi}"'),
        (
            "CANDIDATE_DOMAIN",
            " ".join(part for part in (f'"{candidate_vi}"', anchors) if part),
        ),
        (
            "CANDIDATE_SOURCE_TERM",
            f'"{candidate_vi}" "{source_term}"',
        ),
    ]
    raw.extend(
        (
            "RESTRICTED_SOURCE",
            f'"{candidate_vi}" site:{domain}',
        )
        for domain in restricted_source_domains
    )
    raw = raw[:max_queries]
    queries = tuple(
        QuerySpec(
            query_id=_stable_id(
                "query",
                candidate["integrity"]["frozen_candidate_sha256"],
                query_class,
                query_text,
            ),
            query_class=query_class,
            query_text=query_text,
        )
        for query_class, query_text in raw
    )
    payload = {
        "frozen_candidate_sha256": candidate["integrity"][
            "frozen_candidate_sha256"
        ],
        "query_policy_version": candidate["run_policy"][
            "query_policy_version"
        ],
        "queries": [
            {
                "query_id": query.query_id,
                "query_class": query.query_class,
                "query_text": query.query_text,
            }
            for query in queries
        ],
    }
    return QueryPlan(
        query_plan_id=_stable_id("query_plan", _canonical_json(payload)),
        query_policy_version=candidate["run_policy"]["query_policy_version"],
        queries=queries,
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


__all__ = ["QueryPlan", "QuerySpec", "build_query_plan"]
