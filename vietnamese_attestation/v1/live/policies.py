"""Sealed local policy sidecars consumed by the E live service."""

from __future__ import annotations

import hashlib
import string
from pathlib import Path
from typing import Any, Mapping

from .common import LiveSchemaError, canonical_sha256, file_sha256, load_object, seal
from .schemas import (
    validate_aggregation_policy,
    validate_provider_role_plan,
    validate_query_templates,
    validate_retrieval_policy,
)


def make_retrieval_policy(
    *,
    max_queries_per_candidate: int = 2,
    max_direct_fetches: int = 8,
    max_redirect_hops: int = 3,
    max_fetch_retries: int = 2,
    max_download_bytes: int = 2_000_000,
    max_accepted_documents: int = 8,
    network_mode: str = "LOCAL_FIXTURE_ONLY",
) -> dict[str, Any]:
    return seal(
        {
            "schema_id": "ERetrievalPolicyV1",
            "schema_version": "1.0.0",
            "policy_id": "e-retrieval-policy-v1",
            "network_mode": network_mode,
            "max_queries_per_candidate": max_queries_per_candidate,
            "max_direct_fetches": max_direct_fetches,
            "max_redirect_hops": max_redirect_hops,
            "max_fetch_retries": max_fetch_retries,
            "max_download_bytes": max_download_bytes,
            "max_accepted_documents": max_accepted_documents,
            "allowed_content_types": [
                "text/html",
                "text/plain",
                "application/json",
                "application/xml",
                "application/pdf",
            ],
            "registry_required": True,
            "integrity": {},
        }
    )


def make_query_template_set(*, max_queries: int = 2) -> dict[str, Any]:
    return seal(
        {
            "schema_id": "EQueryTemplateSetV1",
            "schema_version": "1.0.0",
            "policy_id": "e-query-template-set-v1",
            "max_queries": max_queries,
            "templates": [
                {
                    "template_id": "exact_candidate",
                    "query_class": "EXACT_CANDIDATE",
                    "template": '"{candidate_vi}"',
                },
                {
                    "template_id": "candidate_definition",
                    "query_class": "CANDIDATE_DEFINITION",
                    "template": '"{candidate_vi}" "{sense_definition}"',
                },
            ],
            "integrity": {},
        }
    )


def make_provider_role_plan(
    *,
    primary_provider_id: str = "fixture-primary",
    secondary_provider_id: str = "fixture-secondary",
    primary_model_id: str = "fixture-judge-primary-v1",
    secondary_model_id: str = "fixture-judge-secondary-v1",
    producer_commit: str = "0000000000000000000000000000000000000000",
    producer_tree: str = "fixture-tree-v1",
    primary_max_semantic_calls: int = 8,
    secondary_max_semantic_calls: int = 8,
) -> dict[str, Any]:
    prompt_primary = canonical_sha256(
        {"role": "PRIMARY_ATTESTATION_JUDGE", "prompt_version": "v1"}
    )
    prompt_secondary = canonical_sha256(
        {"role": "SECONDARY_ATTESTATION_JUDGE", "prompt_version": "v1"}
    )
    return seal(
        {
            "schema_id": "EProviderRolePlanV1",
            "schema_version": "1.0.0",
            "policy_id": "e-provider-role-plan-v1",
            "roles": [
                {
                    "semantic_role": "PRIMARY_ATTESTATION_JUDGE",
                    "provider_id": primary_provider_id,
                    "model_id": primary_model_id,
                    "mode": "ZERO_PROVIDER_FIXTURE",
                    "prompt_sha256": prompt_primary,
                    "generation_config": {"temperature": 0, "reasoning": "none"},
                    "max_semantic_calls": primary_max_semantic_calls,
                    "max_physical_requests": primary_max_semantic_calls,
                    "max_retries": 0,
                    "same_family_group": "fixture-judge",
                },
                {
                    "semantic_role": "SECONDARY_ATTESTATION_JUDGE",
                    "provider_id": secondary_provider_id,
                    "model_id": secondary_model_id,
                    "mode": "ZERO_PROVIDER_FIXTURE",
                    "prompt_sha256": prompt_secondary,
                    "generation_config": {"temperature": 0, "reasoning": "none"},
                    "max_semantic_calls": secondary_max_semantic_calls,
                    "max_physical_requests": secondary_max_semantic_calls,
                    "max_retries": 0,
                    "same_family_group": "fixture-judge",
                },
            ],
            "secondary_condition": [
                "PRIMARY_CONCEPT_UNCERTAIN",
                "INDEPENDENT_CLUSTER_CONFLICT",
            ],
            "producer": {
                "producer_id": "e-live-role-plan-builder",
                "producer_commit": producer_commit,
                "producer_tree": producer_tree,
            },
            "external_provider_call_count": 0,
            "integrity": {},
        }
    )


def make_aggregation_policy(
    *,
    min_same_clusters_for_attested: int = 2,
    min_organizations_for_attested: int = 2,
    min_coverage: float = 0.5,
) -> dict[str, Any]:
    return seal(
        {
            "schema_id": "EAggregationPolicyV1",
            "schema_version": "1.0.0",
            "policy_id": "e-aggregation-policy-v1",
            "min_same_clusters_for_attested": min_same_clusters_for_attested,
            "min_organizations_for_attested": min_organizations_for_attested,
            "min_coverage": min_coverage,
            "status_order": [
                "ATTESTATION_UNJUDGEABLE",
                "CONFLICTING_ATTESTATION",
                "ATTESTED",
                "WEAKLY_ATTESTED",
                "NOT_ATTESTED",
            ],
            "integrity": {},
        }
    )


def make_budget(*, max_semantic_calls: int = 4, max_physical_requests: int = 8) -> dict[str, Any]:
    return seal(
        {
            "schema_id": "ELiveBudgetSpecV1",
            "schema_version": "1.0.0",
            "max_replicates": 1,
            "max_semantic_calls": max_semantic_calls,
            "max_physical_requests": max_physical_requests,
            "max_retries": 2,
            "max_queries": 2,
            "max_fetches": 8,
            "max_redirect_hops": 3,
            "max_download_bytes": 2_000_000,
            "max_cost": 0,
            "currency": "USD",
            "integrity": {},
        }
    )


def validate_policy_bundle(bundle: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    validators = {
        "retrieval_policy": validate_retrieval_policy,
        "query_template_set": validate_query_templates,
        "provider_role_plan": validate_provider_role_plan,
        "aggregation_policy": validate_aggregation_policy,
    }
    result: dict[str, str] = {}
    for name, validator in validators.items():
        if name not in bundle:
            raise LiveSchemaError(f"missing policy: {name}")
        validated = validator(bundle[name])
        result[name] = str(validated["integrity"]["self_sha256"])
    return result


def render_query_plan(
    template_set: Mapping[str, Any],
    *,
    selected_template_ids: list[str],
    request: Mapping[str, Any],
    max_queries: int,
) -> list[dict[str, str]]:
    checked = validate_query_templates(template_set)
    if not selected_template_ids or len(selected_template_ids) > max_queries:
        raise LiveSchemaError("selected query template count exceeds the approved cap")
    if len(selected_template_ids) != len(set(selected_template_ids)):
        raise LiveSchemaError("selected query template IDs must be unique")
    templates = {row["template_id"]: row for row in checked["templates"]}
    anchors = request.get("domain", {}).get("anchors", [])
    if not isinstance(anchors, list) or any(not isinstance(item, str) for item in anchors):
        raise LiveSchemaError("request domain anchors must be strings")
    values = {
        "candidate_vi": str(request["candidate_vi"]),
        "sense_definition": str(request["sense_definition"]),
        "term_en": str(request["term_en"]),
        "source_term_en": str(request["term_en"]),
        **{f"anchor_{index + 1}_vi": value for index, value in enumerate(anchors[:3])},
    }
    rendered: list[dict[str, str]] = []
    for template_id in selected_template_ids:
        if template_id not in templates:
            raise LiveSchemaError(f"unapproved query template ID: {template_id}")
        template = templates[template_id]
        fields = {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(template["template"])
            if field_name
        }
        missing = sorted(field for field in fields if field not in values)
        if missing:
            raise LiveSchemaError(
                "query template cannot be rendered from frozen request fields: "
                + ", ".join(missing)
            )
        query_text = template["template"].format_map(values).strip()
        if not query_text:
            raise LiveSchemaError("rendered query is empty")
        rendered.append(
            {
                "template_id": template_id,
                "query_class": str(template["query_class"]),
                "template_sha256": canonical_sha256(template),
                "rendered_query": query_text,
                "rendered_query_sha256": hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
            }
        )
    return rendered


def provider_roles_by_name(plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    checked = validate_provider_role_plan(plan)
    return {str(row["semantic_role"]): dict(row) for row in checked["roles"]}


def policy_file_binding(path: str | Path) -> dict[str, str]:
    resolved = Path(path).resolve(strict=True)
    value = load_object(resolved)
    if not isinstance(value.get("integrity"), Mapping) or not value["integrity"].get("self_sha256"):
        raise LiveSchemaError(f"policy is not sealed: {path}")
    return {
        "artifact_ref": resolved.name,
        "self_sha256": str(value["integrity"]["self_sha256"]),
        "physical_sha256": file_sha256(resolved),
    }


__all__ = [
    "make_aggregation_policy",
    "make_budget",
    "make_provider_role_plan",
    "make_query_template_set",
    "make_retrieval_policy",
    "policy_file_binding",
    "provider_roles_by_name",
    "render_query_plan",
    "validate_policy_bundle",
]
