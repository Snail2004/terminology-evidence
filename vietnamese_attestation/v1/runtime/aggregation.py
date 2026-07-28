from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..config import AttestationConfig
from ..contracts.evidence_policy import (
    is_related_supporting_evidence,
    is_strong_positive_evidence,
)


_TIER_WEIGHT = {"A": 1.0, "B": 0.75, "C": 0.40, "D": 0.10, "X": 0.0}
COVERAGE_POLICY_VERSION = "attestation-coverage-v1.1"
STATUS_POLICY_VERSION = "attestation-status-v1.1"


def aggregate_attestation(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: AttestationConfig,
    retrieval_counts: Mapping[str, int],
    judge_unavailable_count: int,
) -> dict[str, Any]:
    machine_translation_policy = (
        config.status.machine_translation_suspicion_policy
    )
    strong_rows = [
        row
        for row in rows
        if is_strong_positive_evidence(
            row,
            machine_translation_policy=machine_translation_policy,
        )
    ]
    related_rows = [
        row for row in rows if is_related_supporting_evidence(row)
    ]
    eligible_rows = [
        row
        for row in rows
        if row["judge"]["judgeability"] == "JUDGEABLE"
        and row["judge"]["candidate_role"] == "TECHNICAL_TERM"
        and row["source_tier"] != "X"
    ]
    different_rows = [
        row
        for row in eligible_rows
        if row["judge"]["concept_relation"] == "DIFFERENT"
        and row["judge"]["domain_match"]
    ]
    uncertain_rows = [
        row
        for row in eligible_rows
        if row["judge"]["concept_relation"] == "UNCERTAIN"
    ]
    organizations = {str(row["organization"]) for row in strong_rows}
    strong_source = any(
        row["source_tier"] in {"A", "B"} for row in strong_rows
    )
    fetch_attempts = retrieval_counts["fetch_attempt_count"]
    fetch_success = retrieval_counts["fetch_success_count"]
    extraction_success = retrieval_counts["extraction_success_count"]
    search_coverage = _ratio(
        retrieval_counts["search_query_success_count"],
        retrieval_counts["search_query_attempt_count"],
    )
    fetch_coverage = _ratio(fetch_success, fetch_attempts)
    extraction_coverage = _ratio(extraction_success, fetch_success)
    language_coverage = _ratio(
        retrieval_counts["language_eligible_count"], extraction_success
    )
    span_yield = _ratio(
        retrieval_counts["candidate_span_document_count"],
        retrieval_counts["language_eligible_count"],
    )
    judgeable = [row for row in rows if row["judge"]["judgeability"] == "JUDGEABLE"]
    judge_coverage = _ratio(
        retrieval_counts["judgeable_cluster_count"],
        retrieval_counts["judged_cluster_count"],
    )
    coverage_breakdown = {
        "search_coverage": round(search_coverage, 6),
        "fetch_coverage": round(fetch_coverage, 6),
        "extraction_coverage": round(extraction_coverage, 6),
        "language_coverage": round(language_coverage, 6),
        "span_yield": round(span_yield, 6),
        "judge_coverage": round(judge_coverage, 6),
    }
    coverage = min(coverage_breakdown.values())
    retrieval_health = min(
        search_coverage,
        fetch_coverage,
        extraction_coverage,
        language_coverage,
    )
    domain = (
        sum(bool(row["judge"]["domain_match"]) for row in eligible_rows)
        / len(eligible_rows)
        if eligible_rows
        else 0.0
    )
    concept_weights = {
        "SAME": 1.0,
        "RELATED": 0.5,
        "DIFFERENT": 0.0,
        "UNCERTAIN": 0.0,
    }
    concept = (
        sum(
            concept_weights[row["judge"]["concept_relation"]]
            for row in eligible_rows
        )
        / len(eligible_rows)
        if eligible_rows
        else 0.0
    )
    authority = (
        sum(
            _TIER_WEIGHT[str(row["source_tier"])]
            * _machine_translation_weight(
                row, policy=machine_translation_policy
            )
            for row in strong_rows
        )
        / len(strong_rows)
        if strong_rows
        else 0.0
    )
    independent_groups = {
        str(row["independence_group_id"]) for row in strong_rows
    }
    all_clusters = {str(row["duplicate_cluster_id"]) for row in rows}
    all_independence_groups = {
        str(row["independence_group_id"]) for row in rows
    }
    independence = min(1.0, len(independent_groups) / 3.0)
    conventionality = min(
        1.0,
        0.6 * min(1.0, len(organizations) / 3.0)
        + 0.4 * min(1.0, len(strong_rows) / 3.0),
    )
    status = _local_status(
        same_cluster_count=len(_clusters(strong_rows)),
        related_cluster_count=len(_clusters(related_rows)),
        different_cluster_count=len(_clusters(different_rows)),
        organization_count=len(organizations),
        strong_source=strong_source,
        domain=domain,
        retrieval_health=retrieval_health,
        judge_unavailable_count=judge_unavailable_count,
        config=config,
    )
    flags = _flags(
        rows=rows,
        coverage=coverage,
        judge_unavailable_count=judge_unavailable_count,
        duplicate_count=retrieval_counts.get("duplicate_document_count", 0),
    )
    counts = {
        "query_count": retrieval_counts["query_count"],
        "search_query_attempt_count": retrieval_counts[
            "search_query_attempt_count"
        ],
        "search_query_success_count": retrieval_counts[
            "search_query_success_count"
        ],
        "search_query_failure_count": retrieval_counts[
            "search_query_failure_count"
        ],
        "raw_result_count": retrieval_counts["raw_result_count"],
        "unique_url_count": retrieval_counts["unique_url_count"],
        "fetch_attempt_count": fetch_attempts,
        "fetch_success_count": fetch_success,
        "extraction_success_count": extraction_success,
        "language_eligible_count": retrieval_counts[
            "language_eligible_count"
        ],
        "candidate_span_document_count": retrieval_counts[
            "candidate_span_document_count"
        ],
        "candidate_occurrence_count": retrieval_counts[
            "candidate_occurrence_count"
        ],
        "pre_dedup_snippet_count": retrieval_counts[
            "pre_dedup_snippet_count"
        ],
        "post_dedup_cluster_count": retrieval_counts[
            "post_dedup_cluster_count"
        ],
        "judged_cluster_count": retrieval_counts["judged_cluster_count"],
        "judgeable_cluster_count": retrieval_counts[
            "judgeable_cluster_count"
        ],
        "candidate_snippet_count": retrieval_counts[
            "pre_dedup_snippet_count"
        ],
        "unique_document_count": retrieval_counts[
            "pre_dedup_snippet_count"
        ],
        "duplicate_document_count": retrieval_counts[
            "duplicate_document_count"
        ],
        "duplicate_cluster_count": retrieval_counts[
            "post_dedup_cluster_count"
        ],
        "independent_cluster_count": len(all_clusters),
        "independent_organization_count": len(all_independence_groups),
        "same_concept_cluster_count": len(_clusters(strong_rows)),
        "related_cluster_count": len(_clusters(related_rows)),
        "different_cluster_count": len(_clusters(different_rows)),
        "uncertain_cluster_count": len(_clusters(uncertain_rows)),
        "unique_organization_count": len(organizations),
    }
    return {
        "features": {
            "E_authority": round(authority, 6),
            "E_independence": round(independence, 6),
            "E_domain": round(domain, 6),
            "E_concept": round(concept, 6),
            "E_conventionality": round(conventionality, 6),
            "E_coverage": round(coverage, 6),
        },
        "coverage_breakdown": coverage_breakdown,
        "coverage_policy_version": COVERAGE_POLICY_VERSION,
        "status_policy": {
            "policy_version": STATUS_POLICY_VERSION,
            "min_same_clusters_for_attested": (
                config.status.min_same_clusters_for_attested
            ),
            "min_organizations_for_attested": (
                config.status.min_organizations_for_attested
            ),
            "require_tier_a_or_b": config.status.require_tier_a_or_b,
            "machine_translation_suspicion_policy": (
                machine_translation_policy
            ),
        },
        "counts": counts,
        "status": status,
        "flags": flags,
        "recommendation": _recommendation(status),
    }


def _local_status(
    *,
    same_cluster_count: int,
    related_cluster_count: int,
    different_cluster_count: int,
    organization_count: int,
    strong_source: bool,
    domain: float,
    retrieval_health: float,
    judge_unavailable_count: int,
    config: AttestationConfig,
) -> str:
    if same_cluster_count and different_cluster_count:
        return "CONFLICTING_ATTESTATION"
    if (
        retrieval_health < config.retrieval.min_fetch_coverage
        or (judge_unavailable_count and not same_cluster_count and not related_cluster_count)
    ):
        return "ATTESTATION_UNJUDGEABLE"
    source_gate = strong_source or not config.status.require_tier_a_or_b
    if (
        same_cluster_count
        >= config.status.min_same_clusters_for_attested
        and organization_count
        >= config.status.min_organizations_for_attested
        and source_gate
        and domain >= 0.5
    ):
        return "ATTESTED"
    if same_cluster_count or related_cluster_count:
        return "WEAKLY_ATTESTED"
    return "NOT_ATTESTED"


def _flags(
    *,
    rows: Sequence[Mapping[str, Any]],
    coverage: float,
    judge_unavailable_count: int,
    duplicate_count: int,
) -> list[str]:
    flags: set[str] = set()
    if coverage < 1:
        flags.add("PARTIAL_RETRIEVAL_COVERAGE")
    if duplicate_count:
        flags.add("DUPLICATE_ECHO_COLLAPSED")
    if judge_unavailable_count:
        flags.add("JUDGE_ROUTE_EXHAUSTED")
    if any(
        row["judge"]["machine_translation_suspected"] for row in rows
    ):
        flags.add("MACHINE_TRANSLATION_SUSPECTED")
    if any(
        row["extraction"]["method"] == "FALLBACK_VISIBLE_TEXT"
        for row in rows
    ):
        flags.add("FALLBACK_EXTRACTION_REVIEW")
    return sorted(flags)


def _recommendation(status: str) -> str:
    return {
        "ATTESTED": "EVIDENCE_AVAILABLE",
        "WEAKLY_ATTESTED": "WEAK_EVIDENCE_AVAILABLE",
        "NOT_ATTESTED": "NO_ATTESTATION_OBSERVED",
        "CONFLICTING_ATTESTATION": "CONFLICTING_EVIDENCE",
        "ATTESTATION_UNJUDGEABLE": "EVIDENCE_UNJUDGEABLE",
    }[status]


def _clusters(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {str(row["duplicate_cluster_id"]) for row in rows}


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _machine_translation_weight(
    row: Mapping[str, Any], *, policy: str
) -> float:
    if (
        policy == "DOWNWEIGHT"
        and row["judge"]["machine_translation_suspected"]
    ):
        return 0.5
    return 1.0


__all__ = [
    "COVERAGE_POLICY_VERSION",
    "STATUS_POLICY_VERSION",
    "aggregate_attestation",
]
