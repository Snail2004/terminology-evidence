from __future__ import annotations

from typing import Any, Mapping

from vietnamese_attestation.v1.contracts.base import (
    CanonicalPolicy,
    ContractValidationError,
    canonicalize,
    require_enum,
    require_exact_keys,
    require_int,
    require_list,
    require_mapping,
    require_nullable_string,
    require_number,
    require_rfc3339,
    require_sha256,
    require_string,
    require_unique,
    seal_payload,
    verify_payload_hash,
)

from .judge import validate_judge_payload
from .evidence_policy import (
    MACHINE_TRANSLATION_POLICIES,
    is_related_supporting_evidence,
    is_strong_positive_evidence,
)


PACKAGE_SCHEMA_ID = "VietnameseAttestationPackageV1"
PACKAGE_SCHEMA_VERSION = "1.1.0"
PACKAGE_POLICY_ID = "vietnamese_attestation_package_v1_1"
HASH_PATH = ("integrity", "package_sha256")
FEATURE_KEYS = (
    "E_authority",
    "E_independence",
    "E_domain",
    "E_concept",
    "E_conventionality",
    "E_coverage",
)
COUNT_KEYS = (
    "query_count",
    "search_query_attempt_count",
    "search_query_success_count",
    "search_query_failure_count",
    "raw_result_count",
    "unique_url_count",
    "fetch_attempt_count",
    "fetch_success_count",
    "extraction_success_count",
    "language_eligible_count",
    "candidate_span_document_count",
    "candidate_occurrence_count",
    "pre_dedup_snippet_count",
    "post_dedup_cluster_count",
    "judged_cluster_count",
    "judgeable_cluster_count",
    "candidate_snippet_count",
    "unique_document_count",
    "duplicate_document_count",
    "duplicate_cluster_count",
    "independent_cluster_count",
    "independent_organization_count",
    "same_concept_cluster_count",
    "related_cluster_count",
    "different_cluster_count",
    "uncertain_cluster_count",
    "unique_organization_count",
)
LOCAL_STATUSES = frozenset(
    {
        "ATTESTED",
        "WEAKLY_ATTESTED",
        "NOT_ATTESTED",
        "CONFLICTING_ATTESTATION",
        "ATTESTATION_UNJUDGEABLE",
    }
)
RECOMMENDATIONS = frozenset(
    {
        "EVIDENCE_AVAILABLE",
        "WEAK_EVIDENCE_AVAILABLE",
        "NO_ATTESTATION_OBSERVED",
        "CONFLICTING_EVIDENCE",
        "EVIDENCE_UNJUDGEABLE",
    }
)
PACKAGE_POLICY = CanonicalPolicy(
    set_like_paths=frozenset(
        {
            ("attestation_evidence", "flags"),
            ("accepted_evidence",),
            ("accepted_evidence", "*", "query_ids"),
            ("accepted_evidence", "*", "rejection_reasons"),
            ("accepted_evidence", "*", "source_tier_reasons"),
            ("accepted_evidence", "*", "dedup_reasons"),
            ("rejected_evidence",),
            ("rejected_evidence", "*", "query_ids"),
            ("rejected_evidence", "*", "rejection_reasons"),
            ("rejected_evidence", "*", "source_tier_reasons"),
            ("rejected_evidence", "*", "dedup_reasons"),
            ("accepted_evidence", "*", "extraction", "section_titles"),
            ("rejected_evidence", "*", "extraction", "section_titles"),
            ("accepted_evidence", "*", "language", "reason_codes"),
            ("rejected_evidence", "*", "language", "reason_codes"),
            ("dedup_clusters",),
            ("dedup_clusters", "*", "member_evidence_ids"),
            ("dedup_clusters", "*", "member_content_sha256"),
            ("dedup_clusters", "*", "publisher_ids"),
            ("dedup_clusters", "*", "organization_ids"),
            ("dedup_clusters", "*", "dedup_reasons"),
            ("audit", "replay_modes"),
            ("cost_report", "judge_routes"),
            ("observed_variants",),
            ("observed_variants", "*", "evidence_ids"),
            ("provenance", "search_provider_ids"),
        }
    ),
    semantic_sequence_paths=frozenset(
        {
            ("provenance", "judge_route_order"),
            ("provenance", "judge_attempts"),
            ("accepted_evidence", "*", "provenance", "redirect_chain"),
            ("rejected_evidence", "*", "provenance", "redirect_chain"),
        }
    ),
)


def seal_attestation_package(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(payload)
    row["schema_id"] = PACKAGE_SCHEMA_ID
    row["schema_version"] = PACKAGE_SCHEMA_VERSION
    row["policy_id"] = PACKAGE_POLICY_ID
    row.setdefault("integrity", {})
    sealed = seal_payload(row, policy=PACKAGE_POLICY, hash_path=HASH_PATH)
    return validate_attestation_package(sealed)


def validate_attestation_package(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = require_mapping(payload, path="$")
    require_exact_keys(
        root,
        required={
            "schema_id",
            "schema_version",
            "policy_id",
            "frozen_candidate_sha256",
            "candidate_id",
            "candidate_version",
            "term_id",
            "source_term",
            "candidate_vi",
            "sense_id",
            "scope_id",
            "sense_inventory_version",
            "attestation_evidence",
            "accepted_evidence",
            "rejected_evidence",
            "dedup_clusters",
            "audit",
            "cost_report",
            "observed_variants",
            "recommendation_to_global_validator",
            "final_glossary_decision",
            "provenance",
            "integrity",
        },
        path="$",
    )
    if root["final_glossary_decision"] is not None:
        raise ContractValidationError(
            "authority_boundary",
            "$.final_glossary_decision",
            "Vietnamese Attestation must not decide the glossary",
        )
    accepted = _evidence_rows(
        root["accepted_evidence"], path="$.accepted_evidence"
    )
    rejected = _evidence_rows(
        root["rejected_evidence"], path="$.rejected_evidence"
    )
    dedup_clusters = _dedup_clusters(root["dedup_clusters"])
    audit = _audit_descriptor(root["audit"])
    cost_report = _cost_report(root["cost_report"])
    attestation = _attestation_evidence(root["attestation_evidence"])
    accepted_ids = {row["evidence_id"] for row in accepted}
    rejected_ids = {row["evidence_id"] for row in rejected}
    if accepted_ids & rejected_ids:
        raise ContractValidationError(
            "evidence_partition",
            "$.accepted_evidence",
            "accepted and rejected evidence overlap",
        )
    if any(row["rejection_reasons"] for row in accepted):
        raise ContractValidationError(
            "accepted_rejection_reason",
            "$.accepted_evidence",
            "accepted evidence cannot carry rejection reasons",
        )
    machine_translation_policy = attestation["status_policy"][
        "machine_translation_suspicion_policy"
    ]
    if any(
        not is_strong_positive_evidence(
            row,
            machine_translation_policy=machine_translation_policy,
        )
        for row in accepted
    ):
        raise ContractValidationError(
            "strong_positive_invariant",
            "$.accepted_evidence",
            "accepted evidence must satisfy the strong-positive policy",
        )
    if any(not row["rejection_reasons"] for row in rejected):
        raise ContractValidationError(
            "missing_rejection_reason",
            "$.rejected_evidence",
            "rejected evidence must carry a rejection reason",
        )
    provenance = _provenance(root["provenance"])
    variants = _observed_variants(root["observed_variants"])
    all_ids = accepted_ids | rejected_ids
    for index, variant in enumerate(variants):
        if not set(variant["evidence_ids"]) <= all_ids:
            raise ContractValidationError(
                "foreign_evidence",
                f"$.observed_variants[{index}].evidence_ids",
                "variant references unknown evidence",
            )
    integrity = require_mapping(root["integrity"], path="$.integrity")
    require_exact_keys(
        integrity, required={"package_sha256"}, path="$.integrity"
    )
    normalized = {
        "schema_id": require_enum(
            root["schema_id"], {PACKAGE_SCHEMA_ID}, path="$.schema_id"
        ),
        "schema_version": require_enum(
            root["schema_version"],
            {PACKAGE_SCHEMA_VERSION},
            path="$.schema_version",
        ),
        "policy_id": require_enum(
            root["policy_id"], {PACKAGE_POLICY_ID}, path="$.policy_id"
        ),
        "frozen_candidate_sha256": require_sha256(
            root["frozen_candidate_sha256"],
            path="$.frozen_candidate_sha256",
        ),
        "candidate_id": require_string(
            root["candidate_id"], path="$.candidate_id"
        ),
        "candidate_version": require_string(
            root["candidate_version"], path="$.candidate_version"
        ),
        "term_id": require_string(root["term_id"], path="$.term_id"),
        "source_term": require_string(
            root["source_term"], path="$.source_term"
        ),
        "candidate_vi": require_string(
            root["candidate_vi"], path="$.candidate_vi"
        ),
        "sense_id": require_string(root["sense_id"], path="$.sense_id"),
        "scope_id": require_string(root["scope_id"], path="$.scope_id"),
        "sense_inventory_version": require_string(
            root["sense_inventory_version"],
            path="$.sense_inventory_version",
        ),
        "attestation_evidence": attestation,
        "accepted_evidence": accepted,
        "rejected_evidence": rejected,
        "dedup_clusters": dedup_clusters,
        "audit": audit,
        "cost_report": cost_report,
        "observed_variants": variants,
        "recommendation_to_global_validator": require_enum(
            root["recommendation_to_global_validator"],
            RECOMMENDATIONS,
            path="$.recommendation_to_global_validator",
        ),
        "final_glossary_decision": None,
        "provenance": provenance,
        "integrity": {
            "package_sha256": require_sha256(
                integrity["package_sha256"],
                path="$.integrity.package_sha256",
            )
        },
    }
    _validate_count_consistency(
        normalized["attestation_evidence"]["counts"],
        accepted=accepted,
        rejected=rejected,
        dedup_clusters=dedup_clusters,
        machine_translation_policy=machine_translation_policy,
    )
    _validate_coverage_consistency(attestation)
    if attestation["status"] == "ATTESTED" and not accepted:
        raise ContractValidationError(
            "attested_without_evidence",
            "$.attestation_evidence.status",
            "ATTESTED requires accepted strong-positive evidence",
        )
    if attestation["status"] == "ATTESTED":
        thresholds = attestation["status_policy"]
        if len({row["duplicate_cluster_id"] for row in accepted}) < thresholds[
            "min_same_clusters_for_attested"
        ]:
            raise ContractValidationError(
                "attested_threshold",
                "$.attestation_evidence.status",
                "ATTESTED has fewer accepted clusters than its sealed threshold",
            )
        if len({row["independence_group_id"] for row in accepted}) < thresholds[
            "min_organizations_for_attested"
        ]:
            raise ContractValidationError(
                "attested_threshold",
                "$.attestation_evidence.status",
                "ATTESTED has fewer independent organizations than required",
            )
        if thresholds["require_tier_a_or_b"] and not any(
            row["source_tier"] in {"A", "B"} for row in accepted
        ):
            raise ContractValidationError(
                "attested_threshold",
                "$.attestation_evidence.status",
                "ATTESTED requires at least one tier A or B source",
            )
    if provenance["frozen_candidate_sha256"] != normalized[
        "frozen_candidate_sha256"
    ]:
        raise ContractValidationError(
            "input_binding",
            "$.provenance.frozen_candidate_sha256",
            "provenance does not bind the package input",
        )
    if provenance["run_spec_id"] != audit["run_spec_id"]:
        raise ContractValidationError(
            "audit_binding",
            "$.audit.run_spec_id",
            "audit descriptor does not bind the run specification",
        )
    if provenance["attestation_execution_id"] != audit[
        "attestation_execution_id"
    ]:
        raise ContractValidationError(
            "audit_binding",
            "$.audit.attestation_execution_id",
            "audit descriptor does not bind the execution",
        )
    if cost_report["search_requests"] != attestation["counts"][
        "search_query_attempt_count"
    ]:
        raise ContractValidationError(
            "cost_binding",
            "$.cost_report.search_requests",
            "cost report search count differs from attestation counts",
        )
    if cost_report["fetch_count"] != attestation["counts"][
        "fetch_attempt_count"
    ]:
        raise ContractValidationError(
            "cost_binding",
            "$.cost_report.fetch_count",
            "cost report fetch count differs from attestation counts",
        )
    if cost_report["judge_attempt_count"] != len(
        provenance["judge_attempts"]
    ):
        raise ContractValidationError(
            "cost_binding",
            "$.cost_report.judge_attempt_count",
            "cost report Judge count differs from provenance",
        )
    if cost_report["search_successes"] != attestation["counts"][
        "search_query_success_count"
    ]:
        raise ContractValidationError(
            "cost_binding",
            "$.cost_report.search_successes",
            "cost report search successes differ from attestation counts",
        )
    if cost_report["judge_input_tokens"] != sum(
        attempt["input_tokens"] for attempt in provenance["judge_attempts"]
    ) or cost_report["judge_output_tokens"] != sum(
        attempt["output_tokens"] for attempt in provenance["judge_attempts"]
    ):
        raise ContractValidationError(
            "cost_binding",
            "$.cost_report",
            "cost report token totals differ from Judge attempts",
        )
    if not verify_payload_hash(
        normalized, policy=PACKAGE_POLICY, hash_path=HASH_PATH
    ):
        raise ContractValidationError(
            "self_hash",
            "$.integrity.package_sha256",
            "attestation package self-hash mismatch",
        )
    return canonicalize(normalized, policy=PACKAGE_POLICY)


def _attestation_evidence(value: Any) -> dict[str, Any]:
    row = require_mapping(value, path="$.attestation_evidence")
    require_exact_keys(
        row,
        required={
            "features",
            "coverage_breakdown",
            "coverage_policy_version",
            "status_policy",
            "counts",
            "status",
            "flags",
        },
        path="$.attestation_evidence",
    )
    features = require_mapping(
        row["features"], path="$.attestation_evidence.features"
    )
    require_exact_keys(
        features,
        required=FEATURE_KEYS,
        path="$.attestation_evidence.features",
    )
    normalized_features: dict[str, float] = {}
    for key in FEATURE_KEYS:
        number = float(
            require_number(
                features[key],
                path=f"$.attestation_evidence.features.{key}",
                minimum=0,
            )
        )
        if number > 1:
            raise ContractValidationError(
                "range",
                f"$.attestation_evidence.features.{key}",
                "feature must be <= 1",
            )
        normalized_features[key] = round(number, 6)
    counts = require_mapping(
        row["counts"], path="$.attestation_evidence.counts"
    )
    require_exact_keys(
        counts, required=COUNT_KEYS, path="$.attestation_evidence.counts"
    )
    flags = _string_set(
        row["flags"], path="$.attestation_evidence.flags"
    )
    coverage = require_mapping(
        row["coverage_breakdown"],
        path="$.attestation_evidence.coverage_breakdown",
    )
    coverage_keys = {
        "search_coverage",
        "fetch_coverage",
        "extraction_coverage",
        "language_coverage",
        "span_yield",
        "judge_coverage",
    }
    require_exact_keys(
        coverage,
        required=coverage_keys,
        path="$.attestation_evidence.coverage_breakdown",
    )
    normalized_coverage: dict[str, float] = {}
    for key in sorted(coverage_keys):
        number = float(
            require_number(
                coverage[key],
                path=f"$.attestation_evidence.coverage_breakdown.{key}",
                minimum=0,
            )
        )
        if number > 1:
            raise ContractValidationError(
                "range",
                f"$.attestation_evidence.coverage_breakdown.{key}",
                "coverage value must be <= 1",
            )
        normalized_coverage[key] = round(number, 6)
    status_policy = _status_policy(row["status_policy"])
    return {
        "features": normalized_features,
        "coverage_breakdown": normalized_coverage,
        "coverage_policy_version": require_string(
            row["coverage_policy_version"],
            path="$.attestation_evidence.coverage_policy_version",
        ),
        "status_policy": status_policy,
        "counts": {
            key: require_int(
                counts[key],
                path=f"$.attestation_evidence.counts.{key}",
                minimum=0,
            )
            for key in COUNT_KEYS
        },
        "status": require_enum(
            row["status"],
            LOCAL_STATUSES,
            path="$.attestation_evidence.status",
        ),
        "flags": flags,
    }


def _evidence_rows(value: Any, *, path: str) -> list[dict[str, Any]]:
    rows = [
        _evidence_row(item, path=f"{path}[{index}]")
        for index, item in enumerate(require_list(value, path=path))
    ]
    require_unique([row["evidence_id"] for row in rows], path=path)
    return rows


def _status_policy(value: Any) -> dict[str, Any]:
    path = "$.attestation_evidence.status_policy"
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "policy_version",
            "min_same_clusters_for_attested",
            "min_organizations_for_attested",
            "require_tier_a_or_b",
            "machine_translation_suspicion_policy",
        },
        path=path,
    )
    if not isinstance(row["require_tier_a_or_b"], bool):
        raise ContractValidationError(
            "type",
            f"{path}.require_tier_a_or_b",
            "expected a boolean",
        )
    return {
        "policy_version": require_enum(
            row["policy_version"],
            {"attestation-status-v1.1"},
            path=f"{path}.policy_version",
        ),
        "min_same_clusters_for_attested": require_int(
            row["min_same_clusters_for_attested"],
            path=f"{path}.min_same_clusters_for_attested",
            minimum=1,
        ),
        "min_organizations_for_attested": require_int(
            row["min_organizations_for_attested"],
            path=f"{path}.min_organizations_for_attested",
            minimum=1,
        ),
        "require_tier_a_or_b": row["require_tier_a_or_b"],
        "machine_translation_suspicion_policy": require_enum(
            row["machine_translation_suspicion_policy"],
            MACHINE_TRANSLATION_POLICIES,
            path=f"{path}.machine_translation_suspicion_policy",
        ),
    }


def _evidence_row(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "evidence_id",
            "canonical_url",
            "title",
            "publisher",
            "organization",
            "source_type",
            "source_tier",
            "source_tier_reasons",
            "source_policy_version",
            "query_ids",
            "content_sha256",
            "independent_cluster_id",
            "duplicate_cluster_id",
            "publisher_id",
            "organization_id",
            "independence_group_id",
            "dedup_reasons",
            "extraction",
            "language",
            "snippet",
            "judge",
            "rejection_reasons",
            "provenance",
        },
        path=path,
    )
    snippet = require_mapping(row["snippet"], path=f"{path}.snippet")
    require_exact_keys(
        snippet,
        required={
            "original",
            "masked",
            "span_start",
            "span_end",
            "matched_surface",
            "occurrence_count",
        },
        path=f"{path}.snippet",
    )
    original = require_string(
        snippet["original"], path=f"{path}.snippet.original", maximum=10000
    )
    masked = require_string(
        snippet["masked"], path=f"{path}.snippet.masked", maximum=10000
    )
    start = require_int(
        snippet["span_start"], path=f"{path}.snippet.span_start", minimum=0
    )
    end = require_int(
        snippet["span_end"], path=f"{path}.snippet.span_end", minimum=1
    )
    if end <= start or end > len(original):
        raise ContractValidationError(
            "span", f"{path}.snippet", "candidate span is outside snippet"
        )
    matched_surface = require_string(
        snippet["matched_surface"],
        path=f"{path}.snippet.matched_surface",
    )
    if original[start:end] != matched_surface:
        raise ContractValidationError(
            "span_text",
            f"{path}.snippet.matched_surface",
            "matched surface differs from the original snippet slice",
        )
    if masked != original[:start] + "[TERM]" + original[end:]:
        raise ContractValidationError(
            "masked_snippet",
            f"{path}.snippet.masked",
            "masked snippet does not replace the exact candidate span",
        )
    extraction = _extraction_record(row["extraction"], path=f"{path}.extraction")
    language = _language_record(row["language"], path=f"{path}.language")
    if language["label"] not in {"VIETNAMESE", "MIXED_VI_EN"}:
        raise ContractValidationError(
            "language_gate",
            f"{path}.language.label",
            "packaged Judge evidence must be Vietnamese-eligible",
        )
    provenance = require_mapping(
        row["provenance"], path=f"{path}.provenance"
    )
    require_exact_keys(
        provenance,
        required={
            "search_provider_id",
            "fetched_at",
            "fetch_from_cache",
            "fetch_http_status",
            "fetch_policy_version",
            "robots_status",
            "redirect_chain",
            "judge_route_id",
            "judge_model_id",
            "judge_prompt_sha256",
            "judge_response_sha256",
        },
        path=f"{path}.provenance",
    )
    if not isinstance(provenance["fetch_from_cache"], bool):
        raise ContractValidationError(
            "type",
            f"{path}.provenance.fetch_from_cache",
            "expected a boolean",
        )
    return {
        "evidence_id": require_string(
            row["evidence_id"], path=f"{path}.evidence_id"
        ),
        "canonical_url": require_string(
            row["canonical_url"], path=f"{path}.canonical_url"
        ),
        "title": require_string(
            row["title"], path=f"{path}.title", allow_empty=True
        ),
        "publisher": require_string(
            row["publisher"], path=f"{path}.publisher", allow_empty=True
        ),
        "organization": require_string(
            row["organization"], path=f"{path}.organization"
        ),
        "source_type": require_string(
            row["source_type"], path=f"{path}.source_type"
        ),
        "source_tier": require_enum(
            row["source_tier"],
            {"A", "B", "C", "D", "X"},
            path=f"{path}.source_tier",
        ),
        "source_tier_reasons": _string_set(
            row["source_tier_reasons"],
            path=f"{path}.source_tier_reasons",
        ),
        "source_policy_version": require_string(
            row["source_policy_version"],
            path=f"{path}.source_policy_version",
        ),
        "query_ids": _string_set(
            row["query_ids"], path=f"{path}.query_ids"
        ),
        "content_sha256": require_sha256(
            row["content_sha256"], path=f"{path}.content_sha256"
        ),
        "independent_cluster_id": require_string(
            row["independent_cluster_id"],
            path=f"{path}.independent_cluster_id",
        ),
        "duplicate_cluster_id": require_string(
            row["duplicate_cluster_id"],
            path=f"{path}.duplicate_cluster_id",
        ),
        "publisher_id": require_string(
            row["publisher_id"], path=f"{path}.publisher_id"
        ),
        "organization_id": require_string(
            row["organization_id"], path=f"{path}.organization_id"
        ),
        "independence_group_id": require_string(
            row["independence_group_id"],
            path=f"{path}.independence_group_id",
        ),
        "dedup_reasons": _string_set(
            row["dedup_reasons"], path=f"{path}.dedup_reasons"
        ),
        "extraction": extraction,
        "language": language,
        "snippet": {
            "original": original,
            "masked": masked,
            "span_start": start,
            "span_end": end,
            "matched_surface": matched_surface,
            "occurrence_count": require_int(
                snippet["occurrence_count"],
                path=f"{path}.snippet.occurrence_count",
                minimum=1,
            ),
        },
        "judge": validate_judge_payload(row["judge"]),
        "rejection_reasons": _string_set(
            row["rejection_reasons"],
            path=f"{path}.rejection_reasons",
        ),
        "provenance": {
            "search_provider_id": require_string(
                provenance["search_provider_id"],
                path=f"{path}.provenance.search_provider_id",
            ),
            "fetched_at": require_rfc3339(
                provenance["fetched_at"],
                path=f"{path}.provenance.fetched_at",
            ),
            "fetch_from_cache": provenance["fetch_from_cache"],
            "fetch_http_status": require_int(
                provenance["fetch_http_status"],
                path=f"{path}.provenance.fetch_http_status",
                minimum=100,
            ),
            "fetch_policy_version": require_string(
                provenance["fetch_policy_version"],
                path=f"{path}.provenance.fetch_policy_version",
            ),
            "robots_status": require_string(
                provenance["robots_status"],
                path=f"{path}.provenance.robots_status",
            ),
            "redirect_chain": _string_sequence(
                provenance["redirect_chain"],
                path=f"{path}.provenance.redirect_chain",
            ),
            "judge_route_id": require_string(
                provenance["judge_route_id"],
                path=f"{path}.provenance.judge_route_id",
            ),
            "judge_model_id": require_string(
                provenance["judge_model_id"],
                path=f"{path}.provenance.judge_model_id",
            ),
            "judge_prompt_sha256": require_sha256(
                provenance["judge_prompt_sha256"],
                path=f"{path}.provenance.judge_prompt_sha256",
            ),
            "judge_response_sha256": require_sha256(
                provenance["judge_response_sha256"],
                path=f"{path}.provenance.judge_response_sha256",
            ),
        },
    }


def _dedup_clusters(value: Any) -> list[dict[str, Any]]:
    path = "$.dedup_clusters"
    clusters: list[dict[str, Any]] = []
    for index, item in enumerate(require_list(value, path=path)):
        row_path = f"{path}[{index}]"
        row = require_mapping(item, path=row_path)
        require_exact_keys(
            row,
            required={
                "duplicate_cluster_id",
                "representative_evidence_id",
                "member_evidence_ids",
                "member_content_sha256",
                "publisher_ids",
                "organization_ids",
                "dedup_reasons",
            },
            path=row_path,
        )
        member_ids = _string_set(
            row["member_evidence_ids"],
            path=f"{row_path}.member_evidence_ids",
        )
        representative = require_string(
            row["representative_evidence_id"],
            path=f"{row_path}.representative_evidence_id",
        )
        if representative not in member_ids:
            raise ContractValidationError(
                "cluster_representative",
                f"{row_path}.representative_evidence_id",
                "representative must be a member of its duplicate cluster",
            )
        clusters.append(
            {
                "duplicate_cluster_id": require_string(
                    row["duplicate_cluster_id"],
                    path=f"{row_path}.duplicate_cluster_id",
                ),
                "representative_evidence_id": representative,
                "member_evidence_ids": member_ids,
                "member_content_sha256": [
                    require_sha256(
                        digest,
                        path=(
                            f"{row_path}.member_content_sha256[{digest_index}]"
                        ),
                    )
                    for digest_index, digest in enumerate(
                        require_list(
                            row["member_content_sha256"],
                            path=f"{row_path}.member_content_sha256",
                        )
                    )
                ],
                "publisher_ids": _string_set(
                    row["publisher_ids"],
                    path=f"{row_path}.publisher_ids",
                ),
                "organization_ids": _string_set(
                    row["organization_ids"],
                    path=f"{row_path}.organization_ids",
                ),
                "dedup_reasons": _string_set(
                    row["dedup_reasons"],
                    path=f"{row_path}.dedup_reasons",
                ),
            }
        )
    require_unique(
        [row["duplicate_cluster_id"] for row in clusters], path=path
    )
    all_members = [
        evidence_id
        for row in clusters
        for evidence_id in row["member_evidence_ids"]
    ]
    require_unique(all_members, path=f"{path}.*.member_evidence_ids")
    return clusters


def _extraction_record(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={"method", "author", "published_at", "section_titles"},
        path=path,
    )
    return {
        "method": require_enum(
            row["method"],
            {
                "MAIN_CONTENT_EXTRACTED",
                "FALLBACK_VISIBLE_TEXT",
                "PLAIN_TEXT",
                "PDF_TEXT_EXTRACTED",
            },
            path=f"{path}.method",
        ),
        "author": require_string(
            row["author"], path=f"{path}.author", allow_empty=True
        ),
        "published_at": require_string(
            row["published_at"],
            path=f"{path}.published_at",
            allow_empty=True,
        ),
        "section_titles": _string_set(
            row["section_titles"], path=f"{path}.section_titles"
        ),
    }


def _language_record(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={"label", "confidence", "detector_version", "reason_codes"},
        path=path,
    )
    confidence = float(
        require_number(
            row["confidence"], path=f"{path}.confidence", minimum=0
        )
    )
    if confidence > 1:
        raise ContractValidationError(
            "range", f"{path}.confidence", "confidence must be <= 1"
        )
    return {
        "label": require_enum(
            row["label"],
            {"VIETNAMESE", "MIXED_VI_EN", "NON_VIETNAMESE", "UNCERTAIN"},
            path=f"{path}.label",
        ),
        "confidence": round(confidence, 6),
        "detector_version": require_string(
            row["detector_version"], path=f"{path}.detector_version"
        ),
        "reason_codes": _string_set(
            row["reason_codes"], path=f"{path}.reason_codes"
        ),
    }


def _audit_descriptor(value: Any) -> dict[str, Any]:
    path = "$.audit"
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "schema_id",
            "schema_version",
            "run_spec_id",
            "attestation_execution_id",
            "store_mode",
            "manifest_ref",
            "manifest_sha256",
            "replay_modes",
        },
        path=path,
    )
    return {
        "schema_id": require_enum(
            row["schema_id"],
            {"VietnameseAttestationAuditManifestV1"},
            path=f"{path}.schema_id",
        ),
        "schema_version": require_enum(
            row["schema_version"], {"1.1.0"}, path=f"{path}.schema_version"
        ),
        "run_spec_id": require_string(
            row["run_spec_id"], path=f"{path}.run_spec_id"
        ),
        "attestation_execution_id": require_string(
            row["attestation_execution_id"],
            path=f"{path}.attestation_execution_id",
        ),
        "store_mode": require_enum(
            row["store_mode"], {"FILE", "MEMORY"}, path=f"{path}.store_mode"
        ),
        "manifest_ref": require_string(
            row["manifest_ref"], path=f"{path}.manifest_ref"
        ),
        "manifest_sha256": require_sha256(
            row["manifest_sha256"], path=f"{path}.manifest_sha256"
        ),
        "replay_modes": _string_set(
            row["replay_modes"], path=f"{path}.replay_modes"
        ),
    }


def _cost_report(value: Any) -> dict[str, Any]:
    path = "$.cost_report"
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "schema_id",
            "schema_version",
            "pricing_policy_version",
            "currency",
            "effective_date",
            "search_requests",
            "search_successes",
            "search_estimated_cost",
            "judge_routes",
            "judge_attempt_count",
            "judge_input_tokens",
            "judge_output_tokens",
            "fetch_count",
            "elapsed_seconds",
            "estimated_total_cost",
            "cost_per_candidate",
            "cost_per_judged_cluster",
            "cost_per_accepted_cluster",
            "price_status",
        },
        path=path,
    )
    routes: list[dict[str, Any]] = []
    for index, item in enumerate(require_list(row["judge_routes"], path=f"{path}.judge_routes")):
        route_path = f"{path}.judge_routes[{index}]"
        route = require_mapping(item, path=route_path)
        require_exact_keys(
            route,
            required={
                "route_id",
                "attempt_count",
                "accepted_count",
                "input_tokens",
                "output_tokens",
                "estimated_cost",
                "price_status",
            },
            path=route_path,
        )
        routes.append(
            {
                "route_id": require_string(
                    route["route_id"], path=f"{route_path}.route_id"
                ),
                "attempt_count": require_int(
                    route["attempt_count"],
                    path=f"{route_path}.attempt_count",
                    minimum=0,
                ),
                "accepted_count": require_int(
                    route["accepted_count"],
                    path=f"{route_path}.accepted_count",
                    minimum=0,
                ),
                "input_tokens": require_int(
                    route["input_tokens"],
                    path=f"{route_path}.input_tokens",
                    minimum=0,
                ),
                "output_tokens": require_int(
                    route["output_tokens"],
                    path=f"{route_path}.output_tokens",
                    minimum=0,
                ),
                "estimated_cost": _nullable_nonnegative_number(
                    route["estimated_cost"],
                    path=f"{route_path}.estimated_cost",
                ),
                "price_status": require_enum(
                    route["price_status"],
                    {"KNOWN", "UNKNOWN"},
                    path=f"{route_path}.price_status",
                ),
            }
        )
    require_unique([route["route_id"] for route in routes], path=f"{path}.judge_routes")
    return {
        "schema_id": require_enum(
            row["schema_id"],
            {"VietnameseAttestationCostReportV1"},
            path=f"{path}.schema_id",
        ),
        "schema_version": require_enum(
            row["schema_version"], {"1.0.0"}, path=f"{path}.schema_version"
        ),
        "pricing_policy_version": require_string(
            row["pricing_policy_version"],
            path=f"{path}.pricing_policy_version",
        ),
        "currency": require_string(row["currency"], path=f"{path}.currency"),
        "effective_date": require_string(
            row["effective_date"], path=f"{path}.effective_date"
        ),
        "search_requests": require_int(
            row["search_requests"], path=f"{path}.search_requests", minimum=0
        ),
        "search_successes": require_int(
            row["search_successes"], path=f"{path}.search_successes", minimum=0
        ),
        "search_estimated_cost": _nullable_nonnegative_number(
            row["search_estimated_cost"], path=f"{path}.search_estimated_cost"
        ),
        "judge_routes": routes,
        "judge_attempt_count": require_int(
            row["judge_attempt_count"],
            path=f"{path}.judge_attempt_count",
            minimum=0,
        ),
        "judge_input_tokens": require_int(
            row["judge_input_tokens"],
            path=f"{path}.judge_input_tokens",
            minimum=0,
        ),
        "judge_output_tokens": require_int(
            row["judge_output_tokens"],
            path=f"{path}.judge_output_tokens",
            minimum=0,
        ),
        "fetch_count": require_int(
            row["fetch_count"], path=f"{path}.fetch_count", minimum=0
        ),
        "elapsed_seconds": float(
            require_number(
                row["elapsed_seconds"],
                path=f"{path}.elapsed_seconds",
                minimum=0,
            )
        ),
        "estimated_total_cost": _nullable_nonnegative_number(
            row["estimated_total_cost"], path=f"{path}.estimated_total_cost"
        ),
        "cost_per_candidate": _nullable_nonnegative_number(
            row["cost_per_candidate"], path=f"{path}.cost_per_candidate"
        ),
        "cost_per_judged_cluster": _nullable_nonnegative_number(
            row["cost_per_judged_cluster"],
            path=f"{path}.cost_per_judged_cluster",
        ),
        "cost_per_accepted_cluster": _nullable_nonnegative_number(
            row["cost_per_accepted_cluster"],
            path=f"{path}.cost_per_accepted_cluster",
        ),
        "price_status": require_enum(
            row["price_status"],
            {"KNOWN", "UNKNOWN"},
            path=f"{path}.price_status",
        ),
    }


def _nullable_nonnegative_number(value: Any, *, path: str) -> float | None:
    if value is None:
        return None
    return float(require_number(value, path=path, minimum=0))


def _observed_variants(value: Any) -> list[dict[str, Any]]:
    path = "$.observed_variants"
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(require_list(value, path=path)):
        row_path = f"{path}[{index}]"
        row = require_mapping(item, path=row_path)
        require_exact_keys(
            row,
            required={"surface", "observation_count", "evidence_ids"},
            path=row_path,
        )
        rows.append(
            {
                "surface": require_string(
                    row["surface"], path=f"{row_path}.surface"
                ),
                "observation_count": require_int(
                    row["observation_count"],
                    path=f"{row_path}.observation_count",
                    minimum=1,
                ),
                "evidence_ids": _string_set(
                    row["evidence_ids"], path=f"{row_path}.evidence_ids"
                ),
            }
        )
    require_unique([row["surface"].casefold() for row in rows], path=path)
    return rows


def _provenance(value: Any) -> dict[str, Any]:
    path = "$.provenance"
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "run_spec_id",
            "attestation_execution_id",
            "frozen_candidate_sha256",
            "source_contract_ref",
            "attestation_policy_version",
            "query_policy_version",
            "source_policy_version",
            "dedup_policy_version",
            "judge_policy_version",
            "query_plan_id",
            "execution_config_sha256",
            "judge_prompt_sha256",
            "search_provider_ids",
            "judge_route_order",
            "judge_attempts",
            "extractor_version",
            "started_at",
            "completed_at",
        },
        path=path,
    )
    attempts: list[dict[str, Any]] = []
    for index, item in enumerate(require_list(row["judge_attempts"], path=f"{path}.judge_attempts")):
        attempt_path = f"{path}.judge_attempts[{index}]"
        attempt = require_mapping(item, path=attempt_path)
        require_exact_keys(
            attempt,
            required={
                "evidence_id",
                "route_id",
                "model_id",
                "outcome",
                "error_code",
                "request_sha256",
                "response_sha256",
                "input_tokens",
                "output_tokens",
            },
            path=attempt_path,
        )
        attempts.append(
            {
                "evidence_id": require_string(
                    attempt["evidence_id"], path=f"{attempt_path}.evidence_id"
                ),
                "route_id": require_string(
                    attempt["route_id"], path=f"{attempt_path}.route_id"
                ),
                "model_id": require_string(
                    attempt["model_id"], path=f"{attempt_path}.model_id"
                ),
                "outcome": require_enum(
                    attempt["outcome"],
                    {"ACCEPTED", "TRANSPORT_FAILED", "SCHEMA_FAILED"},
                    path=f"{attempt_path}.outcome",
                ),
                "error_code": require_nullable_string(
                    attempt["error_code"], path=f"{attempt_path}.error_code"
                ),
                "request_sha256": require_sha256(
                    attempt["request_sha256"],
                    path=f"{attempt_path}.request_sha256",
                ),
                "response_sha256": (
                    None
                    if attempt["response_sha256"] is None
                    else require_sha256(
                        attempt["response_sha256"],
                        path=f"{attempt_path}.response_sha256",
                    )
                ),
                "input_tokens": require_int(
                    attempt["input_tokens"],
                    path=f"{attempt_path}.input_tokens",
                    minimum=0,
                ),
                "output_tokens": require_int(
                    attempt["output_tokens"],
                    path=f"{attempt_path}.output_tokens",
                    minimum=0,
                ),
            }
        )
    source_ref = require_mapping(
        row["source_contract_ref"], path=f"{path}.source_contract_ref"
    )
    require_exact_keys(
        source_ref,
        required={
            "schema_id",
            "schema_version",
            "artifact_ref",
            "artifact_sha256",
        },
        path=f"{path}.source_contract_ref",
    )
    return {
        "run_spec_id": require_string(
            row["run_spec_id"], path=f"{path}.run_spec_id"
        ),
        "attestation_execution_id": require_string(
            row["attestation_execution_id"],
            path=f"{path}.attestation_execution_id",
        ),
        "frozen_candidate_sha256": require_sha256(
            row["frozen_candidate_sha256"],
            path=f"{path}.frozen_candidate_sha256",
        ),
        "source_contract_ref": {
            "schema_id": require_string(
                source_ref["schema_id"],
                path=f"{path}.source_contract_ref.schema_id",
            ),
            "schema_version": require_string(
                source_ref["schema_version"],
                path=f"{path}.source_contract_ref.schema_version",
            ),
            "artifact_ref": require_string(
                source_ref["artifact_ref"],
                path=f"{path}.source_contract_ref.artifact_ref",
            ),
            "artifact_sha256": require_sha256(
                source_ref["artifact_sha256"],
                path=f"{path}.source_contract_ref.artifact_sha256",
            ),
        },
        "attestation_policy_version": require_string(
            row["attestation_policy_version"],
            path=f"{path}.attestation_policy_version",
        ),
        "query_policy_version": require_string(
            row["query_policy_version"], path=f"{path}.query_policy_version"
        ),
        "source_policy_version": require_string(
            row["source_policy_version"], path=f"{path}.source_policy_version"
        ),
        "dedup_policy_version": require_string(
            row["dedup_policy_version"], path=f"{path}.dedup_policy_version"
        ),
        "judge_policy_version": require_string(
            row["judge_policy_version"], path=f"{path}.judge_policy_version"
        ),
        "query_plan_id": require_string(
            row["query_plan_id"], path=f"{path}.query_plan_id"
        ),
        "execution_config_sha256": require_sha256(
            row["execution_config_sha256"],
            path=f"{path}.execution_config_sha256",
        ),
        "judge_prompt_sha256": require_sha256(
            row["judge_prompt_sha256"],
            path=f"{path}.judge_prompt_sha256",
        ),
        "search_provider_ids": _string_set(
            row["search_provider_ids"], path=f"{path}.search_provider_ids"
        ),
        "judge_route_order": _string_sequence(
            row["judge_route_order"], path=f"{path}.judge_route_order"
        ),
        "judge_attempts": attempts,
        "extractor_version": require_string(
            row["extractor_version"], path=f"{path}.extractor_version"
        ),
        "started_at": require_rfc3339(
            row["started_at"], path=f"{path}.started_at"
        ),
        "completed_at": require_rfc3339(
            row["completed_at"], path=f"{path}.completed_at"
        ),
    }


def _validate_count_consistency(
    counts: Mapping[str, int],
    *,
    accepted: list[Mapping[str, Any]],
    rejected: list[Mapping[str, Any]],
    dedup_clusters: list[Mapping[str, Any]],
    machine_translation_policy: str,
) -> None:
    all_rows = accepted + rejected
    cluster_members = [
        evidence_id
        for cluster in dedup_clusters
        for evidence_id in cluster["member_evidence_ids"]
    ]
    representative_ids = {
        str(cluster["representative_evidence_id"])
        for cluster in dedup_clusters
    }
    if representative_ids != {str(row["evidence_id"]) for row in all_rows}:
        raise ContractValidationError(
            "cluster_partition",
            "$.dedup_clusters",
            "cluster representatives differ from packaged evidence rows",
        )
    for row in all_rows:
        matching = [
            cluster
            for cluster in dedup_clusters
            if cluster["duplicate_cluster_id"]
            == row["duplicate_cluster_id"]
        ]
        if len(matching) != 1 or matching[0][
            "representative_evidence_id"
        ] != row["evidence_id"]:
            raise ContractValidationError(
                "cluster_binding",
                "$.dedup_clusters",
                "evidence row is not bound to its duplicate cluster",
            )
    if counts["candidate_snippet_count"] != counts[
        "pre_dedup_snippet_count"
    ]:
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.candidate_snippet_count",
            "candidate snippet count differs from pre-dedup count",
        )
    if counts["post_dedup_cluster_count"] != len(all_rows):
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.post_dedup_cluster_count",
            "post-dedup count differs from evidence rows",
        )
    if counts["duplicate_cluster_count"] != len(dedup_clusters):
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.duplicate_cluster_count",
            "duplicate cluster count differs from cluster ledger",
        )
    if counts["pre_dedup_snippet_count"] != len(cluster_members):
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.pre_dedup_snippet_count",
            "pre-dedup count differs from cluster members",
        )
    if counts["unique_document_count"] != len(cluster_members):
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.unique_document_count",
            "unique document count differs from cluster members",
        )
    if counts["duplicate_document_count"] != (
        len(cluster_members) - len(dedup_clusters)
    ):
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.duplicate_document_count",
            "duplicate document count differs from cluster ledger",
        )
    if counts["judged_cluster_count"] != len(all_rows):
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.judged_cluster_count",
            "judged count differs from evidence rows",
        )
    if counts["post_dedup_cluster_count"] > counts[
        "pre_dedup_snippet_count"
    ]:
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.post_dedup_cluster_count",
            "post-dedup count exceeds pre-dedup snippets",
        )
    if counts["independent_cluster_count"] != len(
        {row["duplicate_cluster_id"] for row in all_rows}
    ):
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.independent_cluster_count",
            "count differs from evidence clusters",
        )
    if counts["independent_organization_count"] != len(
        {row["independence_group_id"] for row in all_rows}
    ):
        raise ContractValidationError(
            "count_mismatch",
            "$.attestation_evidence.counts.independent_organization_count",
            "count differs from independence groups",
        )
    relations = [row["judge"]["concept_relation"] for row in all_rows]
    expected = {
        "same_concept_cluster_count": len(
                {
                row["duplicate_cluster_id"]
                for row in all_rows
                if is_strong_positive_evidence(
                    row,
                    machine_translation_policy=machine_translation_policy,
                )
            }
        ),
        "related_cluster_count": len(
            {
                row["duplicate_cluster_id"]
                for row in all_rows
                if is_related_supporting_evidence(row)
            }
        ),
        "different_cluster_count": _eligible_relation_cluster_count(
            all_rows, "DIFFERENT", require_domain_match=True
        ),
        "uncertain_cluster_count": _eligible_relation_cluster_count(
            all_rows, "UNCERTAIN"
        ),
    }
    del relations
    for key, value in expected.items():
        if counts[key] != value:
            raise ContractValidationError(
                "count_mismatch",
                f"$.attestation_evidence.counts.{key}",
                "count differs from evidence relations",
            )


def _eligible_relation_cluster_count(
    rows: list[Mapping[str, Any]],
    relation: str,
    *,
    require_domain_match: bool = False,
) -> int:
    return len(
        {
            row["duplicate_cluster_id"]
            for row in rows
            if row["judge"]["judgeability"] == "JUDGEABLE"
            and row["judge"]["candidate_role"] == "TECHNICAL_TERM"
            and row["source_tier"] != "X"
            and row["judge"]["concept_relation"] == relation
            and (
                not require_domain_match
                or bool(row["judge"]["domain_match"])
            )
        }
    )


def _validate_coverage_consistency(
    attestation: Mapping[str, Any],
) -> None:
    counts = attestation["counts"]
    expected = {
        "search_coverage": _ratio_for_contract(
            counts["search_query_success_count"],
            counts["search_query_attempt_count"],
        ),
        "fetch_coverage": _ratio_for_contract(
            counts["fetch_success_count"], counts["fetch_attempt_count"]
        ),
        "extraction_coverage": _ratio_for_contract(
            counts["extraction_success_count"],
            counts["fetch_success_count"],
        ),
        "language_coverage": _ratio_for_contract(
            counts["language_eligible_count"],
            counts["extraction_success_count"],
        ),
        "span_yield": _ratio_for_contract(
            counts["candidate_span_document_count"],
            counts["language_eligible_count"],
        ),
        "judge_coverage": _ratio_for_contract(
            counts["judgeable_cluster_count"],
            counts["judged_cluster_count"],
        ),
    }
    if attestation["coverage_breakdown"] != expected:
        raise ContractValidationError(
            "coverage_mismatch",
            "$.attestation_evidence.coverage_breakdown",
            "coverage values do not match stage counts",
        )
    expected_e = round(min(expected.values()), 6)
    if attestation["features"]["E_coverage"] != expected_e:
        raise ContractValidationError(
            "coverage_mismatch",
            "$.attestation_evidence.features.E_coverage",
            "E_coverage does not match the versioned minimum policy",
        )
    monotonic_pairs = (
        ("unique_url_count", "raw_result_count"),
        ("fetch_attempt_count", "unique_url_count"),
        ("fetch_success_count", "fetch_attempt_count"),
        ("extraction_success_count", "fetch_success_count"),
        ("language_eligible_count", "extraction_success_count"),
        ("candidate_span_document_count", "language_eligible_count"),
        ("candidate_span_document_count", "candidate_occurrence_count"),
        ("post_dedup_cluster_count", "pre_dedup_snippet_count"),
        ("judgeable_cluster_count", "judged_cluster_count"),
    )
    for child, parent in monotonic_pairs:
        if counts[child] > counts[parent]:
            raise ContractValidationError(
                "count_order",
                f"$.attestation_evidence.counts.{child}",
                f"{child} cannot exceed {parent}",
            )


def _ratio_for_contract(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _string_set(value: Any, *, path: str) -> list[str]:
    rows = [
        require_string(item, path=f"{path}[{index}]")
        for index, item in enumerate(require_list(value, path=path))
    ]
    require_unique(rows, path=path)
    return sorted(rows)


def _string_sequence(value: Any, *, path: str) -> list[str]:
    rows = [
        require_string(item, path=f"{path}[{index}]")
        for index, item in enumerate(require_list(value, path=path))
    ]
    require_unique(rows, path=path)
    return rows


__all__ = [
    "COUNT_KEYS",
    "FEATURE_KEYS",
    "LOCAL_STATUSES",
    "PACKAGE_POLICY_ID",
    "PACKAGE_SCHEMA_ID",
    "PACKAGE_SCHEMA_VERSION",
    "RECOMMENDATIONS",
    "seal_attestation_package",
    "validate_attestation_package",
]
