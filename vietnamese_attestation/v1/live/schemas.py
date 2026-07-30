"""Versioned sidecar schemas for the zero-provider E live tooling."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .common import (
    LIVE_TOOL_SCHEMA_VERSION,
    LiveSchemaError,
    canonical_sha256,
    require_bool,
    require_exact_keys,
    require_identifier,
    require_keys,
    require_nonnegative_int,
    require_positive_int,
    require_sha256,
    require_string,
    seal,
    verify_seal,
)


REGISTRY_SCHEMA_ID = "ControlledVietnameseSourceRegistryV1"
SNAPSHOT_SCHEMA_ID = "EControlledCorpusSnapshotV1"
RETRIEVAL_POLICY_SCHEMA_ID = "ERetrievalPolicyV1"
QUERY_TEMPLATE_SCHEMA_ID = "EQueryTemplateSetV1"
PROVIDER_ROLE_PLAN_SCHEMA_ID = "EProviderRolePlanV1"
AGGREGATION_POLICY_SCHEMA_ID = "EAggregationPolicyV1"
RUN_REQUEST_SCHEMA_ID = "ERunRequestV1"
PREFLIGHT_RESPONSE_SCHEMA_ID = "EPreflightResponseV1"
JUDGE_REQUEST_SCHEMA_ID = "EAttestationJudgeRequestV1"
JUDGE_RESPONSE_SCHEMA_ID = "EAttestationJudgeResponseV1"
LIVE_EVENT_SCHEMA_ID = "ELiveLedgerEventV1"
LIVE_BUDGET_SCHEMA_ID = "ELiveBudgetSpecV1"
USAGE_SCHEMA_ID = "EUsageSnapshotV1"

EVENT_KINDS = frozenset(
    {
        "E_DISCOVERY_QUERY",
        "E_DIRECT_FETCH_REQUEST",
        "E_FETCH_RETRY",
        "E_REDIRECT_HOP",
        "E_SOURCE_DOCUMENT_ACCEPTED",
        "E_MODEL_REQUEST",
        "STOP_EVENT",
    }
)
CONCEPT_RELATIONS = frozenset({"SAME", "RELATED", "DIFFERENT", "UNCERTAIN"})
DOMAIN_RELATIONS = frozenset({"MATCH", "PARTIAL", "MISMATCH", "UNCERTAIN"})
USAGE_TYPES = frozenset(
    {
        "TECHNICAL_TERM",
        "GENERAL_LANGUAGE",
        "MENTION_ONLY",
        "METALINGUISTIC_REFERENCE",
        "UNCERTAIN",
    }
)
JUDGEABILITY = frozenset({"JUDGEABLE", "UNJUDGEABLE"})
LOCAL_STATUSES = frozenset(
    {
        "ATTESTED",
        "WEAKLY_ATTESTED",
        "NOT_ATTESTED",
        "CONFLICTING_ATTESTATION",
        "ATTESTATION_UNJUDGEABLE",
    }
)
FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "gold",
        "gold_label",
        "human_gold",
        "reviewer_label",
        "reviewer_result",
        "candidate_rank",
        "candidate_winner",
        "expected_answer",
        "expected_local_status",
        "auto_approved",
        "dev_identity",
        "test_identity",
        "validation_identity",
    }
)


def _schema_header(value: Mapping[str, Any], schema_id: str, *, path: str = "$") -> None:
    require_keys(value, {"schema_id", "schema_version"}, path=path)
    if value["schema_id"] != schema_id:
        raise LiveSchemaError(f"{path}.schema_id must be {schema_id}")
    if value["schema_version"] != LIVE_TOOL_SCHEMA_VERSION:
        raise LiveSchemaError(
            f"{path}.schema_version must be {LIVE_TOOL_SCHEMA_VERSION}"
        )


def _reject_forbidden(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_REQUEST_KEYS:
                raise LiveSchemaError(f"forbidden authority field: {path}.{key}")
            _reject_forbidden(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden(child, path=f"{path}[{index}]")


def validate_budget(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, LIVE_BUDGET_SCHEMA_ID)
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "max_replicates",
            "max_semantic_calls",
            "max_physical_requests",
            "max_retries",
            "max_queries",
            "max_fetches",
            "max_redirect_hops",
            "max_download_bytes",
            "max_cost",
            "currency",
            "integrity",
        },
    )
    _validate_integrity(value["integrity"], path="$.integrity")
    if not verify_seal(value):
        raise LiveSchemaError("budget self hash mismatch")
    result = dict(value)
    for key in (
        "max_replicates",
        "max_semantic_calls",
        "max_physical_requests",
        "max_retries",
        "max_queries",
        "max_fetches",
        "max_redirect_hops",
        "max_download_bytes",
    ):
        result[key] = require_positive_int(value[key], path=f"$.{key}")
    if not isinstance(value["max_cost"], (int, float)) or value["max_cost"] < 0:
        raise LiveSchemaError("$.max_cost must be nonnegative")
    result["max_cost"] = float(value["max_cost"])
    result["currency"] = require_string(value["currency"], path="$.currency")
    return result


def validate_retrieval_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, RETRIEVAL_POLICY_SCHEMA_ID)
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "policy_id",
            "network_mode",
            "max_queries_per_candidate",
            "max_direct_fetches",
            "max_redirect_hops",
            "max_fetch_retries",
            "max_download_bytes",
            "max_accepted_documents",
            "allowed_content_types",
            "registry_required",
            "integrity",
        },
    )
    _validate_integrity(value["integrity"], path="$.integrity")
    if value["network_mode"] not in {"LOCAL_FIXTURE_ONLY", "LIVE_AUTHORIZED"}:
        raise LiveSchemaError("unsupported retrieval network_mode")
    if not verify_seal(value):
        raise LiveSchemaError("retrieval policy self hash mismatch")
    result = dict(value)
    for key in (
        "max_queries_per_candidate",
        "max_direct_fetches",
        "max_redirect_hops",
        "max_fetch_retries",
        "max_download_bytes",
        "max_accepted_documents",
    ):
        result[key] = require_positive_int(value[key], path=f"$.{key}")
    types = value["allowed_content_types"]
    if not isinstance(types, list) or not types or any(
        not isinstance(item, str) or not item.strip() for item in types
    ):
        raise LiveSchemaError("$.allowed_content_types must be nonempty strings")
    result["allowed_content_types"] = sorted(set(str(item).casefold() for item in types))
    result["registry_required"] = require_bool(
        value["registry_required"], path="$.registry_required"
    )
    return result


def validate_query_templates(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, QUERY_TEMPLATE_SCHEMA_ID)
    require_exact_keys(value, {"schema_id", "schema_version", "policy_id", "max_queries", "templates", "integrity"})
    _validate_integrity(value["integrity"], path="$.integrity")
    if not verify_seal(value):
        raise LiveSchemaError("query template set self hash mismatch")
    templates = value["templates"]
    if not isinstance(templates, list) or not templates:
        raise LiveSchemaError("query templates must be nonempty")
    ids: set[str] = set()
    normalized: list[dict[str, str]] = []
    for index, raw in enumerate(templates):
        if not isinstance(raw, Mapping):
            raise LiveSchemaError(f"query template {index} must be an object")
        require_exact_keys(raw, {"template_id", "query_class", "template"}, path=f"$.templates[{index}]")
        template_id = require_string(raw["template_id"], path=f"$.templates[{index}].template_id")
        if template_id in ids:
            raise LiveSchemaError("duplicate query template_id")
        ids.add(template_id)
        normalized.append({key: require_string(raw[key], path=f"$.templates[{index}].{key}") for key in ("template_id", "query_class", "template")})
    result = dict(value)
    result["max_queries"] = require_positive_int(value["max_queries"], path="$.max_queries")
    result["templates"] = sorted(normalized, key=lambda row: row["template_id"])
    return result


def validate_provider_role_plan(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, PROVIDER_ROLE_PLAN_SCHEMA_ID)
    require_exact_keys(value, {"schema_id", "schema_version", "policy_id", "roles", "secondary_condition", "producer", "external_provider_call_count", "integrity"})
    _validate_integrity(value["integrity"], path="$.integrity")
    if not verify_seal(value):
        raise LiveSchemaError("provider role plan self hash mismatch")
    roles = value["roles"]
    if not isinstance(roles, list) or not roles:
        raise LiveSchemaError("provider role plan roles must be nonempty")
    seen: set[str] = set()
    if not isinstance(value["secondary_condition"], list) or any(not isinstance(item, str) or not item for item in value["secondary_condition"]):
        raise LiveSchemaError("secondary_condition must be a string list")
    producer = value["producer"]
    if not isinstance(producer, Mapping):
        raise LiveSchemaError("provider role plan producer binding is required")
    require_exact_keys(producer, {"producer_id", "producer_commit", "producer_tree"}, path="$.producer")
    require_string(producer["producer_id"], path="$.producer.producer_id")
    require_string(producer["producer_commit"], path="$.producer.producer_commit")
    require_string(producer["producer_tree"], path="$.producer.producer_tree")
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(roles):
        if not isinstance(raw, Mapping):
            raise LiveSchemaError("provider role must be an object")
        require_exact_keys(raw, {"semantic_role", "provider_id", "model_id", "mode", "prompt_sha256", "generation_config", "max_semantic_calls", "max_physical_requests", "max_retries", "same_family_group"}, path=f"$.roles[{index}]")
        role = require_string(raw["semantic_role"], path=f"$.roles[{index}].semantic_role")
        if role in seen:
            raise LiveSchemaError("duplicate semantic_role")
        seen.add(role)
        normalized.append(dict(raw))
        require_sha256(raw["prompt_sha256"], path=f"$.roles[{index}].prompt_sha256")
        for key in ("max_semantic_calls", "max_physical_requests"):
            require_positive_int(raw[key], path=f"$.roles[{index}].{key}")
        require_nonnegative_int(raw["max_retries"], path=f"$.roles[{index}].max_retries")
        if raw["mode"] not in {"ZERO_PROVIDER_FIXTURE", "LIVE_PROVIDER"}:
            raise LiveSchemaError("unsupported provider role mode")
        generation = raw["generation_config"]
        if not isinstance(generation, Mapping):
            raise LiveSchemaError("provider generation_config must be an object")
        require_exact_keys(generation, {"temperature", "reasoning"}, path=f"$.roles[{index}].generation_config")
    result = dict(value)
    result["roles"] = sorted(normalized, key=lambda row: row["semantic_role"])
    if value["external_provider_call_count"] != 0:
        raise LiveSchemaError("zero-provider role plan must bind zero calls")
    return result


def validate_aggregation_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, AGGREGATION_POLICY_SCHEMA_ID)
    require_exact_keys(value, {"schema_id", "schema_version", "policy_id", "min_same_clusters_for_attested", "min_organizations_for_attested", "min_coverage", "status_order", "integrity"})
    _validate_integrity(value["integrity"], path="$.integrity")
    if not verify_seal(value):
        raise LiveSchemaError("aggregation policy self hash mismatch")
    result = dict(value)
    result["min_same_clusters_for_attested"] = require_positive_int(value["min_same_clusters_for_attested"], path="$.min_same_clusters_for_attested")
    result["min_organizations_for_attested"] = require_positive_int(value["min_organizations_for_attested"], path="$.min_organizations_for_attested")
    if not isinstance(value["min_coverage"], (int, float)) or not 0 <= value["min_coverage"] <= 1:
        raise LiveSchemaError("$.min_coverage must be in [0,1]")
    result["min_coverage"] = float(value["min_coverage"])
    order = value["status_order"]
    if not isinstance(order, list) or set(order) != set(LOCAL_STATUSES):
        raise LiveSchemaError("status_order must contain exactly all local statuses")
    result["status_order"] = list(order)
    return result


def validate_run_request(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, RUN_REQUEST_SCHEMA_ID)
    _reject_forbidden(value)
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "run_id",
            "run_spec_id",
            "phase_id",
            "sense_id",
            "candidate_id",
            "term_en",
            "candidate_vi",
            "sense_definition",
            "domain",
            "candidate_variants",
            "query_template_ids",
            "authority_refs",
            "budget",
            "retrieval_policy_sha256",
            "query_template_set_sha256",
            "provider_role_plan_sha256",
            "aggregation_policy_sha256",
        },
    )
    result = dict(value)
    for key in ("run_id", "run_spec_id", "phase_id", "sense_id", "candidate_id"):
        result[key] = require_identifier(value[key], path=f"$.{key}")
    for key in ("term_en", "candidate_vi", "sense_definition"):
        result[key] = require_string(value[key], path=f"$.{key}")
    if not isinstance(value["domain"], Mapping):
        raise LiveSchemaError("$.domain must be an object")
    require_exact_keys(value["domain"], {"scope_id", "anchors"}, path="$.domain")
    require_string(value["domain"]["scope_id"], path="$.domain.scope_id")
    if not isinstance(value["domain"]["anchors"], list) or any(
        not isinstance(item, str) or not item.strip() for item in value["domain"]["anchors"]
    ):
        raise LiveSchemaError("$.domain.anchors must be nonempty strings")
    if not isinstance(value["candidate_variants"], list) or any(not isinstance(item, str) for item in value["candidate_variants"]):
        raise LiveSchemaError("$.candidate_variants must be a string list")
    if not isinstance(value["query_template_ids"], list) or not value["query_template_ids"] or any(
        not isinstance(item, str) or not item for item in value["query_template_ids"]
    ):
        raise LiveSchemaError("$.query_template_ids must be nonempty strings")
    if len(value["query_template_ids"]) != len(set(value["query_template_ids"])):
        raise LiveSchemaError("$.query_template_ids must be unique")
    if not isinstance(value["authority_refs"], Mapping):
        raise LiveSchemaError("$.authority_refs must be an object")
    require_exact_keys(
        value["authority_refs"],
        {
            "cohort_id",
            "registry_self_sha256",
            "snapshot_manifest_sha256",
            "candidate_key",
            "input_contract_sha256",
        },
        path="$.authority_refs",
    )
    require_string(value["authority_refs"]["cohort_id"], path="$.authority_refs.cohort_id")
    for key in ("registry_self_sha256", "snapshot_manifest_sha256", "input_contract_sha256"):
        require_sha256(value["authority_refs"][key], path=f"$.authority_refs.{key}")
    candidate_key = value["authority_refs"]["candidate_key"]
    if not isinstance(candidate_key, Mapping):
        raise LiveSchemaError("$.authority_refs.candidate_key must be an object")
    require_exact_keys(
        candidate_key,
        {
            "candidate_id",
            "candidate_version",
            "source_term",
            "candidate_vi",
            "sense_id",
            "scope_id",
            "sense_inventory_version",
            "dataset_manifest_sha256",
            "effective_sense_contract_sha256",
        },
        path="$.authority_refs.candidate_key",
    )
    for key in (
        "candidate_id",
        "source_term",
        "candidate_vi",
        "sense_id",
        "scope_id",
        "sense_inventory_version",
    ):
        require_string(candidate_key[key], path=f"$.authority_refs.candidate_key.{key}")
    for key in ("candidate_version", "dataset_manifest_sha256"):
        require_sha256(candidate_key[key], path=f"$.authority_refs.candidate_key.{key}")
    effective_contract = candidate_key["effective_sense_contract_sha256"]
    if effective_contract is not None:
        require_sha256(
            effective_contract,
            path="$.authority_refs.candidate_key.effective_sense_contract_sha256",
        )
    expected_join = {
        "candidate_id": value["candidate_id"],
        "candidate_vi": value["candidate_vi"],
        "sense_id": value["sense_id"],
        "scope_id": value["domain"]["scope_id"],
    }
    for key, expected in expected_join.items():
        if candidate_key[key] != expected:
            raise LiveSchemaError(f"$.authority_refs.candidate_key.{key} join mismatch")
    if not isinstance(value["budget"], Mapping):
        raise LiveSchemaError("$.budget must be an object")
    for key in ("retrieval_policy_sha256", "query_template_set_sha256", "provider_role_plan_sha256", "aggregation_policy_sha256"):
        result[key] = require_sha256(value[key], path=f"$.{key}")
    validate_budget(value["budget"])
    return result


def compute_run_spec_id(value: Mapping[str, Any]) -> str:
    identity = {key: value[key] for key in sorted(value) if key not in {"run_id", "run_spec_id"}}
    return "e_run_spec_" + canonical_sha256(identity)[:32]


def validate_preflight_response(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, PREFLIGHT_RESPONSE_SCHEMA_ID)
    require_exact_keys(value, {"schema_id", "schema_version", "status", "run_id", "run_spec_id", "provider_calls", "blockers", "checks", "integrity"})
    _validate_integrity(value["integrity"], path="$.integrity")
    if value["status"] not in {"READY", "BLOCKED"}:
        raise LiveSchemaError("preflight status is unsupported")
    if value["provider_calls"] != 0:
        raise LiveSchemaError("preflight provider_calls must be zero")
    if not isinstance(value["blockers"], list) or not isinstance(value["checks"], Mapping):
        raise LiveSchemaError("preflight blockers/checks shape is invalid")
    require_exact_keys(
        value["checks"],
        {
            "request_schema",
            "authorized_cohort",
            "registry_snapshot",
            "policy_bundle",
            "authorization_receipt",
            "authority_adapter",
            "policy_bindings",
            "credentials_readiness",
            "provider_calls",
            "network_calls",
        },
        path="$.checks",
    )
    if not verify_seal(value):
        raise LiveSchemaError("preflight response self hash mismatch")
    return dict(value)


def validate_judge_request(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, JUDGE_REQUEST_SCHEMA_ID)
    exact = {"schema_id", "schema_version", "candidate_id", "sense_id", "evidence_id", "term_en", "candidate_vi", "sense_definition", "snippet_original", "snippet_masked", "source_id", "source_tier", "semantic_role"}
    require_exact_keys(value, exact)
    if set(value) != exact:
        raise LiveSchemaError("Judge request contains unsupported fields")
    _reject_forbidden(value)
    return dict(value)


def validate_judge_response(value: Mapping[str, Any], *, snippet: str | None = None) -> dict[str, Any]:
    _schema_header(value, JUDGE_RESPONSE_SCHEMA_ID)
    exact = {"schema_id", "schema_version", "judgeability", "concept_relation", "domain_relation", "usage_type", "evidence_span", "reason_codes", "reason", "machine_translation_suspected"}
    extra = sorted(set(value) - exact)
    if extra:
        raise LiveSchemaError(
            "Judge response contains unsupported final/action fields: " + ", ".join(extra)
        )
    require_exact_keys(value, exact)
    if set(value) != exact:
        raise LiveSchemaError("Judge response contains unsupported final/action fields")
    if value["judgeability"] not in JUDGEABILITY or value["concept_relation"] not in CONCEPT_RELATIONS or value["domain_relation"] not in DOMAIN_RELATIONS or value["usage_type"] not in USAGE_TYPES:
        raise LiveSchemaError("unsupported Judge enum")
    require_bool(value["machine_translation_suspected"], path="$.machine_translation_suspected")
    if not isinstance(value["reason_codes"], list) or any(not isinstance(item, str) or not item for item in value["reason_codes"]):
        raise LiveSchemaError("reason_codes must be nonempty strings")
    require_string(value["reason"], path="$.reason")
    span = require_string(value["evidence_span"], path="$.evidence_span", allow_empty=True)
    if value["judgeability"] == "JUDGEABLE":
        if not span or (snippet is not None and span.casefold() not in snippet.casefold()):
            raise LiveSchemaError("judgeable response has no valid evidence span")
    elif span:
        raise LiveSchemaError("unjudgeable response must not contain an evidence span")
    if value["judgeability"] == "UNJUDGEABLE" and (
        value["concept_relation"] != "UNCERTAIN"
        or value["domain_relation"] != "UNCERTAIN"
        or value["usage_type"] != "UNCERTAIN"
    ):
        raise LiveSchemaError("unjudgeable response must use UNCERTAIN labels")
    return dict(value)


def validate_event(value: Mapping[str, Any]) -> dict[str, Any]:
    _schema_header(value, LIVE_EVENT_SCHEMA_ID)
    require_exact_keys(value, {"schema_id", "schema_version", "event_index", "previous_event_sha256", "event_sha256", "event_kind", "run_id", "phase_id", "candidate_replicate_id", "semantic_role", "semantic_call_id", "transport_attempt_id", "retry_of", "payload", "failure_disposition", "usage", "created_at"})
    if value["event_kind"] not in EVENT_KINDS:
        raise LiveSchemaError("unsupported ledger event kind")
    require_nonnegative_int(value["event_index"], path="$.event_index")
    require_sha256(value["previous_event_sha256"], path="$.previous_event_sha256")
    require_sha256(value["event_sha256"], path="$.event_sha256")
    if not isinstance(value["payload"], Mapping) or not isinstance(value["usage"], Mapping):
        raise LiveSchemaError("event payload/usage must be objects")
    require_exact_keys(value["usage"], {"input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "cost", "currency"}, path="$.usage")
    for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
        require_nonnegative_int(value["usage"][key], path=f"$.usage.{key}")
    if not isinstance(value["usage"]["cost"], (int, float)) or value["usage"]["cost"] < 0:
        raise LiveSchemaError("$.usage.cost must be nonnegative")
    require_string(value["usage"]["currency"], path="$.usage.currency")
    if value["event_kind"] == "E_MODEL_REQUEST":
        require_exact_keys(value["payload"], {"candidate_id", "sense_id", "semantic_role", "semantic_call_id", "provider_request_id", "retry_index", "provider_id", "model_id", "route", "prompt_sha256", "request_sha256", "response_sha256", "raw_response_locator"}, path="$.payload")
    elif value["event_kind"] == "E_DISCOVERY_QUERY":
        require_exact_keys(value["payload"], {"template_id", "query_class", "template_sha256", "rendered_query", "rendered_query_sha256", "result_count", "lead_urls", "is_evidence"}, path="$.payload")
        if value["payload"].get("is_evidence") is not False:
            raise LiveSchemaError("discovery lead must never be marked as evidence")
    elif value["event_kind"] in {"E_DIRECT_FETCH_REQUEST", "E_FETCH_RETRY"}:
        require_exact_keys(value["payload"], {"url", "retry_index"}, path="$.payload")
    elif value["event_kind"] == "E_REDIRECT_HOP":
        require_exact_keys(value["payload"], {"url"}, path="$.payload")
    elif value["event_kind"] == "E_SOURCE_DOCUMENT_ACCEPTED":
        require_exact_keys(value["payload"], {"document_id", "source_id", "content_sha256", "document_ref", "snapshot_manifest_sha256"}, path="$.payload")
    elif value["event_kind"] == "STOP_EVENT":
        require_exact_keys(value["payload"], {"code", "message", "details"}, path="$.payload")
        if not isinstance(value["payload"]["details"], Mapping):
            raise LiveSchemaError("STOP_EVENT details must be an object")
    return dict(value)


def _validate_integrity(value: Any, *, path: str) -> None:
    if not isinstance(value, Mapping):
        raise LiveSchemaError(f"{path} must be an object")
    require_exact_keys(value, {"self_sha256"}, path=path)
    require_sha256(value["self_sha256"], path=f"{path}.self_sha256")


__all__ = [
    "AGGREGATION_POLICY_SCHEMA_ID",
    "CONCEPT_RELATIONS",
    "DOMAIN_RELATIONS",
    "EVENT_KINDS",
    "JUDGEABILITY",
    "JUDGE_REQUEST_SCHEMA_ID",
    "JUDGE_RESPONSE_SCHEMA_ID",
    "LOCAL_STATUSES",
    "PREFLIGHT_RESPONSE_SCHEMA_ID",
    "PROVIDER_ROLE_PLAN_SCHEMA_ID",
    "QUERY_TEMPLATE_SCHEMA_ID",
    "REGISTRY_SCHEMA_ID",
    "RETRIEVAL_POLICY_SCHEMA_ID",
    "RUN_REQUEST_SCHEMA_ID",
    "SNAPSHOT_SCHEMA_ID",
    "USAGE_SCHEMA_ID",
    "compute_run_spec_id",
    "validate_aggregation_policy",
    "validate_budget",
    "validate_event",
    "validate_judge_request",
    "validate_judge_response",
    "validate_preflight_response",
    "validate_provider_role_plan",
    "validate_query_templates",
    "validate_retrieval_policy",
    "validate_run_request",
]
