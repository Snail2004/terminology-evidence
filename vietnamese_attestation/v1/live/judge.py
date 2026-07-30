"""Strict E Attestation Judge request/response and fixture routing."""

from __future__ import annotations

from typing import Any, Mapping

from .common import LIVE_TOOL_SCHEMA_VERSION, LiveSchemaError, canonical_sha256, require_string
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


def judge_request_sha256(request: Mapping[str, Any]) -> str:
    validate_judge_request(request)
    return canonical_sha256(request)


__all__ = ["FixtureJudge", "judge_request_sha256", "make_judge_request", "make_judge_response"]
