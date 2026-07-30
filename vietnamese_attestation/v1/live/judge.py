"""Strict E Attestation Judge request/response and fixture routing."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from typing import Any, Mapping, Protocol

from .common import LIVE_TOOL_SCHEMA_VERSION, LiveSchemaError, canonical_bytes, canonical_sha256, require_exact_keys, require_sha256, require_string
from .schemas import (
    JUDGE_REQUEST_SCHEMA_ID,
    JUDGE_RESPONSE_SCHEMA_ID,
    validate_judge_request,
    validate_judge_response,
)


def make_judge_request(
    *,
    candidate_id: str,
    sense_id: str,
    evidence_id: str,
    term_en: str,
    candidate_vi: str,
    sense_definition: str,
    snippet_original: str,
    snippet_masked: str,
    source_id: str,
    source_tier: str,
    semantic_role: str = "PRIMARY_ATTESTATION_JUDGE",
) -> dict[str, Any]:
    request = {
        "schema_id": JUDGE_REQUEST_SCHEMA_ID,
        "schema_version": LIVE_TOOL_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "sense_id": sense_id,
        "evidence_id": evidence_id,
        "term_en": term_en,
        "candidate_vi": candidate_vi,
        "sense_definition": sense_definition,
        "snippet_original": snippet_original,
        "snippet_masked": snippet_masked,
        "source_id": source_id,
        "source_tier": source_tier,
        "semantic_role": semantic_role,
    }
    validate_judge_request(request)
    return request


def make_judge_response(
    *,
    concept_relation: str,
    domain_relation: str,
    usage_type: str,
    judgeability: str,
    evidence_span: str = "",
    reason_codes: list[str] | None = None,
    reason: str = "",
    machine_translation_suspected: bool = False,
    snippet: str | None = None,
) -> dict[str, Any]:
    response = {
        "schema_id": JUDGE_RESPONSE_SCHEMA_ID,
        "schema_version": LIVE_TOOL_SCHEMA_VERSION,
        "judgeability": judgeability,
        "concept_relation": concept_relation,
        "domain_relation": domain_relation,
        "usage_type": usage_type,
        "evidence_span": evidence_span,
        "reason_codes": list(reason_codes or ["FIXTURE_DECISION"]),
        "reason": reason or f"fixture relation: {concept_relation}",
        "machine_translation_suspected": machine_translation_suspected,
    }
    return validate_judge_response(response, snippet=snippet)


class FixtureJudge:
    """Deterministic primary/conditional-secondary router with zero calls."""

    def __init__(self, responses: Mapping[str, Mapping[str, Any] | Mapping[str, Mapping[str, Any]]], *, primary_role: str = "PRIMARY_ATTESTATION_JUDGE", secondary_role: str = "SECONDARY_ATTESTATION_JUDGE") -> None:
        self.responses = {str(key): value for key, value in responses.items()}
        self.primary_role = primary_role
        self.secondary_role = secondary_role
        self.provider_calls = 0

    def judge(self, request: Mapping[str, Any], *, role: str | None = None) -> dict[str, Any]:
        checked = validate_judge_request(request)
        evidence_id = checked["evidence_id"]
        if evidence_id not in self.responses:
            raise LiveSchemaError("fixture Judge response is missing")
        raw = self.responses[evidence_id]
        if isinstance(raw, Mapping) and role is not None and role in raw and isinstance(raw[role], Mapping):
            raw = raw[role]
        if not isinstance(raw, Mapping):
            raise LiveSchemaError("fixture Judge response is not an object")
        # Explicitly never call a provider: a fixture response is already sealed input.
        self.provider_calls += 0
        return validate_judge_response(raw, snippet=checked["snippet_original"])

    def route(self, request: Mapping[str, Any], *, primary_uncertain: bool = False, cluster_conflict: bool = False) -> tuple[str, dict[str, Any]]:
        primary = self.judge(request, role=self.primary_role)
        needs_secondary = primary["concept_relation"] == "UNCERTAIN" or primary_uncertain or cluster_conflict
        if not needs_secondary:
            return self.primary_role, primary
        try:
            secondary = self.judge(request, role=self.secondary_role)
        except LiveSchemaError:
            return self.primary_role, primary
        return self.secondary_role, secondary


class ProviderAdapter(Protocol):
    def invoke(self, request: Mapping[str, Any], *, role_config: Mapping[str, Any]) -> Mapping[str, Any]: ...


TRANSPORT_OUTCOMES = frozenset({"SUCCESS", "RETRYABLE_FAILURE", "TERMINAL_FAILURE", "UNKNOWN_PHYSICAL_OUTCOME"})


def validate_provider_transport_result(value: Mapping[str, Any], *, request_sha256: str) -> dict[str, Any]:
    require_exact_keys(value, {
        "provider_request_id", "outcome", "response", "request_sha256",
        "response_physical_sha256", "response_canonical_sha256", "started_at", "completed_at",
        "latency_ms", "input_tokens", "output_tokens", "reasoning_tokens", "total_tokens",
        "cost", "currency", "physical_request_count", "retry_index",
    })
    provider_request_id = require_string(value["provider_request_id"], path="$.provider_request_id")
    if provider_request_id.startswith("fixture-"):
        raise LiveSchemaError("production provider request ID uses forbidden fixture prefix")
    if value["outcome"] not in TRANSPORT_OUTCOMES:
        raise LiveSchemaError("unsupported provider transport outcome")
    if value["request_sha256"] != request_sha256:
        raise LiveSchemaError("provider transport request hash mismatch")
    for key in ("request_sha256", "response_physical_sha256", "response_canonical_sha256"):
        require_sha256(value[key], path=f"$.{key}")
    for key in ("started_at", "completed_at", "currency"):
        require_string(value[key], path=f"$.{key}")
    for key in ("latency_ms", "input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "physical_request_count", "retry_index"):
        if isinstance(value[key], bool) or not isinstance(value[key], int) or value[key] < 0:
            raise LiveSchemaError(f"provider transport {key} must be a nonnegative integer")
    if value["physical_request_count"] != 1:
        raise LiveSchemaError("one transport result must describe exactly one physical attempt")
    if value["total_tokens"] != value["input_tokens"] + value["output_tokens"] + value["reasoning_tokens"]:
        raise LiveSchemaError("provider transport token total mismatch")
    if isinstance(value["cost"], bool) or not isinstance(value["cost"], (int, float)) or value["cost"] < 0:
        raise LiveSchemaError("provider transport cost must be nonnegative")
    if value["outcome"] == "SUCCESS":
        if not isinstance(value["response"], Mapping):
            raise LiveSchemaError("successful provider transport lacks response")
        response = validate_judge_response(value["response"])
        if canonical_sha256(response) != value["response_canonical_sha256"]:
            raise LiveSchemaError("provider response canonical hash mismatch")
        if hashlib.sha256(canonical_bytes(response)).hexdigest() != value["response_physical_sha256"]:
            raise LiveSchemaError("provider response physical hash mismatch")
    elif value["response"] is not None:
        raise LiveSchemaError("failed provider transport must not claim a semantic response")
    else:
        null_sha = hashlib.sha256(canonical_bytes(None)).hexdigest()
        if value["response_physical_sha256"] != null_sha or value["response_canonical_sha256"] != canonical_sha256(None):
            raise LiveSchemaError("failed provider transport null-response hash mismatch")
    try:
        started = datetime.fromisoformat(value["started_at"].replace("Z", "+00:00"))
        completed = datetime.fromisoformat(value["completed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiveSchemaError("provider transport timestamps are invalid") from exc
    if started.tzinfo is None or completed.tzinfo is None or completed < started:
        raise LiveSchemaError("provider transport timestamp interval is invalid")
    if int((completed - started).total_seconds() * 1000) != value["latency_ms"]:
        raise LiveSchemaError("provider transport latency does not match timestamps")
    if not math.isfinite(float(value["cost"])):
        raise LiveSchemaError("provider transport cost must be finite")
    return dict(value)


class MockProviderAdapter:
    """Production-shaped deterministic adapter used only by zero-network tests."""

    def __init__(self, responses: Mapping[str, Any]) -> None:
        self.responses = {str(key): value for key, value in responses.items()}
        self.call_count = 0
        self.attempts_by_evidence: dict[str, int] = {}

    def invoke(self, request: Mapping[str, Any], *, role_config: Mapping[str, Any]) -> Mapping[str, Any]:
        if role_config.get("mode") != "LIVE_PROVIDER":
            raise LiveSchemaError("production provider adapter requires LIVE_PROVIDER role")
        evidence_id = str(request.get("evidence_id", ""))
        if evidence_id not in self.responses:
            raise LiveSchemaError("mock provider response is missing")
        configured = self.responses[evidence_id]
        if isinstance(configured, list):
            attempt = self.attempts_by_evidence.get(evidence_id, 0)
            if attempt >= len(configured):
                raise LiveSchemaError("mock provider result sequence exhausted")
            configured = configured[attempt]
            self.attempts_by_evidence[evidence_id] = attempt + 1
        self.call_count += 1
        if not isinstance(configured, Mapping):
            raise LiveSchemaError("mock provider transport result is invalid")
        return dict(configured)


def judge_request_sha256(request: Mapping[str, Any]) -> str:
    validate_judge_request(request)
    return canonical_sha256(request)


__all__ = ["FixtureJudge", "MockProviderAdapter", "ProviderAdapter", "judge_request_sha256", "make_judge_request", "make_judge_response", "validate_provider_transport_result"]
