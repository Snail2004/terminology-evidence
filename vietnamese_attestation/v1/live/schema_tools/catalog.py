"""Machine-readable JSON Schema catalog for E Live sidecars and API payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..common import (
    LIVE_TOOL_SCHEMA_VERSION,
    LiveSchemaError,
    canonical_bytes,
    file_sha256,
    seal,
)

STRING = {"type": "string", "minLength": 1}
SHA256 = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
NONNEGATIVE = {"type": "integer", "minimum": 0}
POSITIVE = {"type": "integer", "minimum": 1}
INTEGRITY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["self_sha256"],
    "properties": {"self_sha256": SHA256},
}


def _object(
    schema_id: str,
    required: list[str],
    properties: dict[str, Any],
    *,
    additional: bool = False,
) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://thesis.local/e-live/v1/{schema_id}.schema.json",
        "title": schema_id,
        "type": "object",
        "additionalProperties": additional,
        "required": ["schema_id", "schema_version", *required],
        "properties": {
            "schema_id": {"const": schema_id},
            "schema_version": {"const": LIVE_TOOL_SCHEMA_VERSION},
            **properties,
        },
    }


def _registry_schema() -> dict[str, Any]:
    record = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "source_id",
            "host_pattern",
            "source_tier",
            "source_type",
            "allowed_content_types",
            "allowed",
            "domain_tags",
        ],
        "properties": {
            "source_id": STRING,
            "host_pattern": STRING,
            "source_tier": {"enum": ["A", "B", "C", "D"]},
            "source_type": {
                "enum": ["OFFICIAL", "ACADEMIC", "PUBLISHER", "REFERENCE", "FIXTURE"]
            },
            "allowed_content_types": {
                "type": "array",
                "minItems": 1,
                "items": STRING,
            },
            "allowed": {"type": "boolean"},
            "domain_tags": {"type": "array", "items": STRING},
        },
    }
    authority = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "approval_status",
            "approval_id",
            "approved_by",
            "authority_receipt_ref",
            "authority_receipt_sha256",
        ],
        "properties": {
            "approval_status": {"const": "APPROVED_EXTERNALLY"},
            "approval_id": STRING,
            "approved_by": STRING,
            "authority_receipt_ref": STRING,
            "authority_receipt_sha256": SHA256,
        },
    }
    return _object(
        "ControlledVietnameseSourceRegistryV1",
        ["registry_id", "records", "authority", "integrity"],
        {
            "registry_id": STRING,
            "records": {"type": "array", "minItems": 1, "items": record},
            "authority": authority,
            "integrity": INTEGRITY,
        },
    )


def _snapshot_schema() -> dict[str, Any]:
    admission = {
        "type": "object",
        "additionalProperties": False,
        "required": ["source_id", "host_pattern", "source_tier", "source_type", "domain_tags", "content_type", "final_url", "redirect_chain", "registry_self_sha256", "authority_receipt_sha256"],
        "properties": {
            "source_id": STRING,
            "host_pattern": STRING,
            "source_tier": {"enum": ["A", "B", "C", "D"]},
            "source_type": {"enum": ["OFFICIAL", "ACADEMIC", "PUBLISHER", "REFERENCE", "FIXTURE"]},
            "domain_tags": {"type": "array", "items": STRING},
            "content_type": STRING,
            "final_url": STRING,
            "redirect_chain": {"type": "array", "items": STRING},
            "registry_self_sha256": SHA256,
            "authority_receipt_sha256": SHA256,
        },
    }
    document = {
        "type": "object",
        "additionalProperties": False,
        "required": ["document_id", "source_id", "canonical_url", "final_url", "content_type", "content_size_bytes", "content_physical_sha256", "retrieved_at_utc", "text_extraction_sha256", "extractor_id", "extractor_version", "document_ref", "extraction_ref", "redirect_chain", "registry_admission"],
        "properties": {
            "document_id": STRING,
            "source_id": STRING,
            "canonical_url": STRING,
            "final_url": STRING,
            "content_type": STRING,
            "content_size_bytes": NONNEGATIVE,
            "content_physical_sha256": SHA256,
            "retrieved_at_utc": STRING,
            "text_extraction_sha256": SHA256,
            "extractor_id": STRING,
            "extractor_version": STRING,
            "document_ref": STRING,
            "extraction_ref": STRING,
            "redirect_chain": {"type": "array", "items": STRING},
            "registry_admission": admission,
        },
    }
    member = {
        "type": "object",
        "additionalProperties": False,
        "required": ["path", "sha256", "size"],
        "properties": {"path": STRING, "sha256": SHA256, "size": NONNEGATIVE},
    }
    external_receipt = {
        "type": "object",
        "additionalProperties": False,
        "required": ["role", "artifact_ref", "artifact_physical_sha256", "artifact_self_sha256"],
        "properties": {"role": STRING, "artifact_ref": STRING, "artifact_physical_sha256": SHA256, "artifact_self_sha256": SHA256},
    }
    authority_binding = {
        "type": "object",
        "additionalProperties": False,
        "required": ["mode", "acquisition_receipt_source_kind", "acquisition_receipt_original_ref", "acquisition_receipt_physical_sha256", "acquisition_receipt_self_sha256", "authority_profile_ref", "authority_profile_physical_sha256", "authority_bundle_ref", "authority_bundle_physical_sha256", "authority_bundle_self_sha256", "external_receipts"],
        "properties": {
            "mode": {"enum": ["LOCAL_FIXTURE_ONLY", "PRODUCTION_AUTHORITY"]},
            "acquisition_receipt_source_kind": STRING,
            "acquisition_receipt_original_ref": STRING,
            "acquisition_receipt_physical_sha256": SHA256,
            "acquisition_receipt_self_sha256": SHA256,
            "authority_profile_ref": {"type": ["string", "null"]},
            "authority_profile_physical_sha256": {"oneOf": [SHA256, {"type": "null"}]},
            "authority_bundle_ref": {"type": ["string", "null"]},
            "authority_bundle_physical_sha256": {"oneOf": [SHA256, {"type": "null"}]},
            "authority_bundle_self_sha256": {"oneOf": [SHA256, {"type": "null"}]},
            "external_receipts": {"type": "array", "items": external_receipt},
        },
    }
    return _object(
        "EControlledCorpusSnapshotV1",
        [
            "snapshot_id",
            "mode",
            "documents",
            "member_manifest",
            "registry_binding",
            "retrieval_policy_binding",
            "authority_binding",
            "document_count",
            "total_document_bytes",
            "physical_inventory_sha256",
            "acquisition_receipt_sha256",
            "producer",
            "ordered_document_ids",
            "integrity",
        ],
        {
            "snapshot_id": STRING,
            "mode": {"const": "LOCAL_FIXTURE_ONLY"},
            "documents": {"type": "array", "items": document},
            "member_manifest": {"type": "array", "items": member},
            "registry_binding": {"type": "object", "additionalProperties": False, "required": ["registry_self_sha256", "registry_physical_sha256"], "properties": {"registry_self_sha256": SHA256, "registry_physical_sha256": SHA256}},
            "retrieval_policy_binding": {"type": "object", "additionalProperties": False, "required": ["retrieval_policy_self_sha256", "retrieval_policy_physical_sha256"], "properties": {"retrieval_policy_self_sha256": SHA256, "retrieval_policy_physical_sha256": SHA256}},
            "authority_binding": authority_binding,
            "document_count": NONNEGATIVE,
            "total_document_bytes": NONNEGATIVE,
            "physical_inventory_sha256": SHA256,
            "acquisition_receipt_sha256": SHA256,
            "producer": {"type": "object"},
            "ordered_document_ids": {"type": "array", "items": STRING},
            "integrity": INTEGRITY,
        },
    )


def _retrieval_policy_schema() -> dict[str, Any]:
    numeric = {
        key: POSITIVE
        for key in (
            "max_queries_per_candidate",
            "max_direct_fetches",
            "max_redirect_hops",
            "max_fetch_retries",
            "max_download_bytes",
            "max_accepted_documents",
        )
    }
    return _object(
        "ERetrievalPolicyV1",
        ["policy_id", "network_mode", *numeric, "allowed_content_types", "registry_required", "integrity"],
        {
            "policy_id": STRING,
            "network_mode": {"enum": ["LOCAL_FIXTURE_ONLY", "LIVE_AUTHORIZED"]},
            **numeric,
            "allowed_content_types": {"type": "array", "minItems": 1, "items": STRING},
            "registry_required": {"const": True},
            "integrity": INTEGRITY,
        },
    )


def _acquisition_schema() -> dict[str, Any]:
    row = {
        "type": "object",
        "additionalProperties": False,
        "required": ["file_ref", "source_id", "canonical_url", "content_type"],
        "properties": {
            "file_ref": STRING,
            "source_id": STRING,
            "canonical_url": STRING,
            "final_url": STRING,
            "content_type": STRING,
            "redirect_chain": {"type": "array", "items": STRING},
            "retrieved_at_utc": STRING,
            "http_status": POSITIVE,
        },
    }
    return _object(
        "EControlledAcquisitionReceiptV1",
        ["mode", "rows", "integrity"],
        {
            "mode": {"const": "LOCAL_FIXTURE_ONLY"},
            "rows": {"type": "array", "minItems": 1, "items": row},
            "integrity": INTEGRITY,
        },
    )


def _budget_schema() -> dict[str, Any]:
    numeric = ["max_replicates", "max_semantic_calls", "max_physical_requests", "max_retries", "max_queries", "max_fetches", "max_redirect_hops", "max_download_bytes"]
    return _object(
        "ELiveBudgetSpecV1",
        [*numeric, "max_cost", "currency", "integrity"],
        {
            **{key: POSITIVE for key in numeric},
            "max_cost": {"type": "number", "minimum": 0},
            "currency": STRING,
            "integrity": INTEGRITY,
        },
    )


def _preflight_schema() -> dict[str, Any]:
    checks = {
        "type": "object",
        "additionalProperties": False,
        "required": ["request_schema", "authorized_cohort", "registry_snapshot", "policy_bundle", "authorization_receipt", "authority_adapter", "policy_bindings", "credentials_readiness", "provider_calls", "network_calls"],
        "properties": {
            "request_schema": STRING,
            "authorized_cohort": STRING,
            "registry_snapshot": STRING,
            "policy_bundle": STRING,
            "authorization_receipt": STRING,
            "authority_adapter": STRING,
            "policy_bindings": STRING,
            "credentials_readiness": STRING,
            "provider_calls": {"const": 0},
            "network_calls": {"const": 0},
        },
    }
    return _object(
        "EPreflightResponseV1",
        ["status", "run_id", "run_spec_id", "provider_calls", "blockers", "checks", "integrity"],
        {
            "status": {"enum": ["READY", "BLOCKED"]},
            "run_id": STRING,
            "run_spec_id": STRING,
            "provider_calls": {"const": 0},
            "blockers": {"type": "array", "items": STRING},
            "checks": checks,
            "integrity": INTEGRITY,
        },
    )


def _external_receipt_schema() -> dict[str, Any]:
    return _object(
        "EExternalAuthorityReceiptV1",
        ["receipt_id", "role", "status", "issuer_id", "authority_id", "subject_self_sha256", "subject_physical_sha256", "integrity"],
        {
            "receipt_id": STRING,
            "role": {"enum": ["REGISTRY_APPROVAL", "POLICY_APPROVAL", "CORPUS_ACQUISITION_AUTHORIZATION"]},
            "status": {"enum": ["DRAFT_FIXTURE_ONLY", "MAIN_PINNED_APPROVED"]},
            "issuer_id": STRING,
            "authority_id": STRING,
            "subject_self_sha256": SHA256,
            "subject_physical_sha256": SHA256,
            "integrity": INTEGRITY,
        },
    )


def _authority_profile_schema() -> dict[str, Any]:
    binding = {"type": "object", "additionalProperties": False, "required": ["role", "artifact_ref", "artifact_physical_sha256", "artifact_self_sha256"], "properties": {"role": STRING, "artifact_ref": STRING, "artifact_physical_sha256": SHA256, "artifact_self_sha256": SHA256}}
    return _object(
        "ETrustedAuthorityProfileV1",
        ["profile_id", "status", "trusted_issuers", "trusted_authorities", "receipt_bindings", "protocol_schema_bindings", "integrity"],
        {
            "profile_id": STRING,
            "status": {"enum": ["DRAFT_FIXTURE_ONLY", "MAIN_PINNED_RUNTIME_AUTHORITY"]},
            "trusted_issuers": {"type": "array", "minItems": 1, "items": STRING},
            "trusted_authorities": {"type": "array", "minItems": 1, "items": STRING},
            "receipt_bindings": {"type": "array", "minItems": 3, "maxItems": 3, "items": binding},
            "protocol_schema_bindings": {"type": "array", "items": binding},
            "integrity": INTEGRITY,
        },
    )


def _query_schema() -> dict[str, Any]:
    return _object(
        "EQueryTemplateSetV1",
        ["policy_id", "max_queries", "templates", "integrity"],
        {
            "policy_id": STRING,
            "max_queries": POSITIVE,
            "templates": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["template_id", "query_class", "template"],
                    "properties": {
                        "template_id": STRING,
                        "query_class": STRING,
                        "template": STRING,
                    },
                },
            },
            "integrity": INTEGRITY,
        },
    )


def _provider_plan_schema() -> dict[str, Any]:
    role = {
        "type": "object",
        "additionalProperties": False,
        "required": ["semantic_role", "provider_id", "model_id", "mode", "prompt_sha256", "generation_config", "max_semantic_calls", "max_physical_requests", "max_retries", "same_family_group"],
        "properties": {
            "semantic_role": STRING,
            "provider_id": STRING,
            "model_id": STRING,
            "mode": {"enum": ["ZERO_PROVIDER_FIXTURE", "LIVE_PROVIDER"]},
            "prompt_sha256": SHA256,
            "generation_config": {"type": "object", "additionalProperties": False, "required": ["temperature", "reasoning"], "properties": {"temperature": {"type": "number"}, "reasoning": STRING}},
            "max_semantic_calls": POSITIVE,
            "max_physical_requests": POSITIVE,
            "max_retries": NONNEGATIVE,
            "same_family_group": STRING,
        },
    }
    producer = {"type": "object", "additionalProperties": False, "required": ["producer_id", "producer_commit", "producer_tree"], "properties": {"producer_id": STRING, "producer_commit": STRING, "producer_tree": STRING}}
    return _object(
        "EProviderRolePlanV1",
        [
            "policy_id",
            "roles",
            "secondary_condition",
            "producer",
            "external_provider_call_count",
            "integrity",
        ],
        {
            "policy_id": STRING,
            "roles": {"type": "array", "minItems": 2, "items": role},
            "secondary_condition": {"type": "array", "items": STRING},
            "producer": producer,
            "external_provider_call_count": {"const": 0},
            "integrity": INTEGRITY,
        },
    )


def _aggregation_schema() -> dict[str, Any]:
    return _object(
        "EAggregationPolicyV1",
        [
            "policy_id",
            "min_same_clusters_for_attested",
            "min_organizations_for_attested",
            "min_coverage",
            "status_order",
            "integrity",
        ],
        {
            "policy_id": STRING,
            "min_same_clusters_for_attested": POSITIVE,
            "min_organizations_for_attested": POSITIVE,
            "min_coverage": {"type": "number", "minimum": 0, "maximum": 1},
            "status_order": {
                "type": "array",
                "minItems": 5,
                "maxItems": 5,
                "items": STRING,
            },
            "integrity": INTEGRITY,
        },
    )


def _run_request_schema() -> dict[str, Any]:
    identity = {
        key: STRING
        for key in (
            "run_id",
            "run_spec_id",
            "phase_id",
            "sense_id",
            "candidate_id",
            "term_en",
            "candidate_vi",
            "sense_definition",
        )
    }
    hashes = {
        key: SHA256
        for key in (
            "retrieval_policy_sha256",
            "query_template_set_sha256",
            "provider_role_plan_sha256",
            "aggregation_policy_sha256",
        )
    }
    candidate_key = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "candidate_id",
            "candidate_version",
            "source_term",
            "candidate_vi",
            "sense_id",
            "scope_id",
            "sense_inventory_version",
            "dataset_manifest_sha256",
            "effective_sense_contract_sha256",
        ],
        "properties": {
            "candidate_id": STRING,
            "candidate_version": SHA256,
            "source_term": STRING,
            "candidate_vi": STRING,
            "sense_id": STRING,
            "scope_id": STRING,
            "sense_inventory_version": STRING,
            "dataset_manifest_sha256": SHA256,
            "effective_sense_contract_sha256": {
                "anyOf": [SHA256, {"type": "null"}]
            },
        },
    }
    authority_refs = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "cohort_id",
            "registry_self_sha256",
            "snapshot_manifest_sha256",
            "candidate_key",
            "input_contract_sha256",
        ],
        "properties": {
            "cohort_id": STRING,
            "registry_self_sha256": SHA256,
            "snapshot_manifest_sha256": SHA256,
            "candidate_key": candidate_key,
            "input_contract_sha256": SHA256,
        },
    }
    budget = _budget_schema()
    return _object(
        "ERunRequestV1",
        [*identity, "domain", "candidate_variants", "query_template_ids", "authority_refs", "budget", *hashes],
        {
            **identity,
            "domain": {"type": "object", "additionalProperties": False, "required": ["scope_id", "anchors"], "properties": {"scope_id": STRING, "anchors": {"type": "array", "items": STRING}}},
            "candidate_variants": {"type": "array", "items": STRING},
            "query_template_ids": {"type": "array", "minItems": 1, "items": STRING},
            "authority_refs": authority_refs,
            "budget": budget,
            **hashes,
        },
    )


def _judge_request_schema() -> dict[str, Any]:
    keys = [
        "candidate_id",
        "sense_id",
        "evidence_id",
        "term_en",
        "candidate_vi",
        "sense_definition",
        "snippet_original",
        "snippet_masked",
        "source_id",
        "source_tier",
        "semantic_role",
    ]
    return _object("EAttestationJudgeRequestV1", keys, {key: STRING for key in keys})


def _judge_response_schema() -> dict[str, Any]:
    return _object(
        "EAttestationJudgeResponseV1",
        [
            "judgeability",
            "concept_relation",
            "domain_relation",
            "usage_type",
            "evidence_span",
            "reason_codes",
            "reason",
            "machine_translation_suspected",
        ],
        {
            "judgeability": {"enum": ["JUDGEABLE", "UNJUDGEABLE"]},
            "concept_relation": {"enum": ["SAME", "RELATED", "DIFFERENT", "UNCERTAIN"]},
            "domain_relation": {"enum": ["MATCH", "PARTIAL", "MISMATCH", "UNCERTAIN"]},
            "usage_type": {
                "enum": [
                    "TECHNICAL_TERM",
                    "GENERAL_LANGUAGE",
                    "MENTION_ONLY",
                    "METALINGUISTIC_REFERENCE",
                    "UNCERTAIN",
                ]
            },
            "evidence_span": {"type": "string"},
            "reason_codes": {"type": "array", "items": STRING},
            "reason": STRING,
            "machine_translation_suspected": {"type": "boolean"},
        },
    )


def _event_schema() -> dict[str, Any]:
    def payload(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
        return {"type": "object", "additionalProperties": False, "required": required, "properties": properties}

    payloads = [
        payload(["template_id", "query_class", "template_sha256", "rendered_query", "rendered_query_sha256", "result_count", "lead_urls", "is_evidence"], {"template_id": STRING, "query_class": STRING, "template_sha256": SHA256, "rendered_query": STRING, "rendered_query_sha256": SHA256, "result_count": NONNEGATIVE, "lead_urls": {"type": "array", "items": STRING}, "is_evidence": {"const": False}}),
        payload(["url", "retry_index"], {"url": STRING, "retry_index": NONNEGATIVE}),
        payload(["url"], {"url": STRING}),
        payload(["document_id", "source_id", "content_sha256", "document_ref", "snapshot_manifest_sha256"], {"document_id": STRING, "source_id": STRING, "content_sha256": SHA256, "document_ref": STRING, "snapshot_manifest_sha256": SHA256}),
        payload(
            ["candidate_id", "sense_id", "semantic_role", "semantic_call_id", "provider_request_id", "retry_index", "provider_id", "model_id", "route", "prompt_sha256", "request_sha256", "response_sha256", "response_physical_sha256", "raw_response_locator", "generation_config", "provider_role_plan_sha256", "outcome", "latency_ms", "physical_request_count", "started_at", "completed_at"],
            {"candidate_id": STRING, "sense_id": STRING, "semantic_role": STRING, "semantic_call_id": STRING, "provider_request_id": STRING, "retry_index": NONNEGATIVE, "provider_id": STRING, "model_id": STRING, "route": STRING, "prompt_sha256": SHA256, "request_sha256": SHA256, "response_sha256": SHA256, "response_physical_sha256": SHA256, "raw_response_locator": STRING, "generation_config": {"type": "object", "additionalProperties": False, "required": ["temperature", "reasoning"], "properties": {"temperature": {"type": "number", "minimum": 0, "maximum": 2}, "reasoning": STRING}}, "provider_role_plan_sha256": SHA256, "outcome": {"enum": ["SUCCESS", "RETRYABLE_FAILURE", "TERMINAL_FAILURE", "UNKNOWN_PHYSICAL_OUTCOME"]}, "latency_ms": NONNEGATIVE, "physical_request_count": {"type": "integer", "minimum": 1}, "started_at": STRING, "completed_at": STRING},
        ),
        payload(["code", "message", "details"], {"code": STRING, "message": STRING, "details": {"type": "object"}}),
    ]
    usage = {"type": "object", "additionalProperties": False, "required": ["input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "cost", "currency"], "properties": {"input_tokens": NONNEGATIVE, "output_tokens": NONNEGATIVE, "reasoning_tokens": NONNEGATIVE, "total_tokens": NONNEGATIVE, "cost": {"type": "number", "minimum": 0}, "currency": STRING}}
    return _object(
        "ELiveLedgerEventV1",
        [
            "event_index",
            "previous_event_sha256",
            "event_sha256",
            "event_kind",
            "run_id",
            "phase_id",
            "candidate_replicate_id",
            "semantic_role",
            "semantic_call_id",
            "transport_attempt_id",
            "retry_of",
            "payload",
            "failure_disposition",
            "usage",
            "created_at",
        ],
        {
            "event_index": NONNEGATIVE,
            "previous_event_sha256": SHA256,
            "event_sha256": SHA256,
            "event_kind": {
                "enum": [
                    "E_DISCOVERY_QUERY",
                    "E_DIRECT_FETCH_REQUEST",
                    "E_FETCH_RETRY",
                    "E_REDIRECT_HOP",
                    "E_SOURCE_DOCUMENT_ACCEPTED",
                    "E_MODEL_REQUEST",
                    "STOP_EVENT",
                ]
            },
            "run_id": STRING,
            "phase_id": STRING,
            "candidate_replicate_id": STRING,
            "semantic_role": STRING,
            "semantic_call_id": STRING,
            "transport_attempt_id": STRING,
            "retry_of": {"type": ["string", "null"]},
            "payload": {"oneOf": payloads},
            "failure_disposition": STRING,
            "usage": usage,
            "created_at": STRING,
        },
    )


SCHEMA_CATALOG: dict[str, dict[str, Any]] = {
    schema["title"]: schema
    for schema in (
        _registry_schema(),
        _snapshot_schema(),
        _acquisition_schema(),
        _retrieval_policy_schema(),
        _budget_schema(),
        _query_schema(),
        _provider_plan_schema(),
        _aggregation_schema(),
        _run_request_schema(),
        _preflight_schema(),
        _external_receipt_schema(),
        _authority_profile_schema(),
        _judge_request_schema(),
        _judge_response_schema(),
        _event_schema(),
    )
}


def export_schemas(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir).absolute()
    if root.exists() and any(root.iterdir()):
        raise LiveSchemaError("schema export directory must be empty")
    root.mkdir(parents=True, exist_ok=True)
    members = []
    for schema_id, schema in sorted(SCHEMA_CATALOG.items()):
        path = root / f"{schema_id}.schema.json"
        path.write_bytes(canonical_bytes(schema))
        members.append(
            {"path": path.name, "sha256": file_sha256(path), "size": path.stat().st_size}
        )
    manifest = seal(
        {
            "schema_id": "ELiveSchemaCatalogV1",
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "schema_count": len(members),
            "members": members,
            "integrity": {},
        }
    )
    manifest_path = root / "schema_catalog_manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    checksums = [
        f"{file_sha256(path)}  {path.name}"
        for path in sorted(root.iterdir())
        if path.is_file()
    ]
    (root / "CHECKSUMS").write_text(
        "\n".join(checksums) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


__all__ = ["SCHEMA_CATALOG", "export_schemas"]
