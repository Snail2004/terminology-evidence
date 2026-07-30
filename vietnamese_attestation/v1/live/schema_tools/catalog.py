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
    return _object(
        "EControlledCorpusSnapshotV1",
        [
            "snapshot_id",
            "mode",
            "documents",
            "member_manifest",
            "registry_binding",
            "retrieval_policy_binding",
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
            "documents": {"type": "array", "items": {"type": "object"}},
            "member_manifest": {"type": "array", "items": {"type": "object"}},
            "registry_binding": {"type": "object"},
            "retrieval_policy_binding": {"type": "object"},
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
                    "required": ["template_id", "query_class", "template"],
                },
            },
            "integrity": INTEGRITY,
        },
    )


def _provider_plan_schema() -> dict[str, Any]:
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
            "roles": {"type": "array", "minItems": 2, "items": {"type": "object"}},
            "secondary_condition": {"type": "array", "items": STRING},
            "producer": {"type": "object"},
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
    return _object(
        "ERunRequestV1",
        [*identity, "domain", "candidate_variants", "authority_refs", "budget", *hashes],
        {
            **identity,
            "domain": {"type": "object"},
            "candidate_variants": {"type": "array", "items": STRING},
            "authority_refs": {"type": "object"},
            "budget": {"type": "object"},
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
            "payload": {"type": "object"},
            "failure_disposition": STRING,
            "usage": {"type": "object"},
            "created_at": STRING,
        },
    )


SCHEMA_CATALOG: dict[str, dict[str, Any]] = {
    schema["title"]: schema
    for schema in (
        _registry_schema(),
        _snapshot_schema(),
        _retrieval_policy_schema(),
        _query_schema(),
        _provider_plan_schema(),
        _aggregation_schema(),
        _run_request_schema(),
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
