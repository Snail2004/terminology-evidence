from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from ..contracts.judge import validate_judge_payload_for_snippet
from .base import (
    AllJudgeRoutesFailed,
    JudgeProvider,
    JudgeRequest,
    JudgeRouteResult,
    JudgeSchemaError,
    JudgeTransportError,
)


class FallbackJudgeRouter:
    def __init__(self, providers: Sequence[JudgeProvider]) -> None:
        if not providers:
            raise ValueError("at least one judge provider is required")
        route_ids = [provider.route_id for provider in providers]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("judge route IDs must be unique")
        self.providers = tuple(providers)

    @property
    def route_order(self) -> tuple[str, ...]:
        return tuple(provider.route_id for provider in self.providers)

    def judge(
        self, request: JudgeRequest
    ) -> tuple[JudgeRouteResult, tuple[dict[str, Any], ...]]:
        attempts: list[dict[str, Any]] = []
        for provider in self.providers:
            try:
                result = provider.judge(request)
            except JudgeTransportError as exc:
                attempts.append(
                    _failed_attempt(
                        request=request,
                        provider=provider,
                        outcome="TRANSPORT_FAILED",
                        error_code=exc.code,
                    )
                )
                continue
            except JudgeSchemaError as exc:
                attempts.append(
                    _failed_attempt(
                        request=request,
                        provider=provider,
                        outcome="SCHEMA_FAILED",
                        error_code=exc.code,
                        raw_response=exc.raw_response,
                    )
                )
                continue
            attempts.append(
                {
                    "evidence_id": request.evidence_id,
                    "route_id": result.route_id,
                    "model_id": result.model_id,
                    "outcome": "ACCEPTED",
                    "error_code": None,
                    "request_sha256": result.request_sha256,
                    "response_sha256": result.response_sha256,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "raw_response": result.raw_response,
                }
            )
            return result, tuple(attempts)
        raise AllJudgeRoutesFailed(tuple(attempts))


class StaticJudgeProvider:
    def __init__(
        self,
        *,
        route_id: str,
        model_id: str,
        payloads_by_evidence_id: Mapping[str, Mapping[str, Any] | Exception],
    ) -> None:
        self.route_id = route_id
        self.model_id = model_id
        self._payloads = dict(payloads_by_evidence_id)
        self.calls: list[str] = []

    def judge(self, request: JudgeRequest) -> JudgeRouteResult:
        self.calls.append(request.evidence_id)
        if request.evidence_id in self._payloads:
            value = self._payloads[request.evidence_id]
        else:
            value = self._payloads["*"]
        if isinstance(value, Exception):
            raise value
        try:
            payload = validate_judge_payload_for_snippet(
                value,
                snippet_original=request.snippet_original,
            )
        except Exception as exc:
            raise JudgeSchemaError(
                "static_schema_failed",
                f"{self.route_id} returned an invalid judge payload",
                raw_response=value,
            ) from exc
        request_payload = {
            "evidence_id": request.evidence_id,
            "definition_en": request.definition_en,
            "scope_id": request.scope_id,
            "candidate_vi": request.candidate_vi,
            "snippet_original": request.snippet_original,
            "snippet_masked": request.snippet_masked,
            "source_type": request.source_type,
        }
        return JudgeRouteResult(
            route_id=self.route_id,
            model_id=self.model_id,
            payload=payload,
            request_sha256=_sha(request_payload),
            response_sha256=_sha(payload),
            input_tokens=0,
            output_tokens=0,
            raw_response=payload,
        )

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": "StaticJudgeProvider",
            "route_id": self.route_id,
            "model_id": self.model_id,
        }


def _failed_attempt(
    *,
    request: JudgeRequest,
    provider: JudgeProvider,
    outcome: str,
    error_code: str,
    raw_response: Any | None = None,
) -> dict[str, Any]:
    request_payload = {
        "evidence_id": request.evidence_id,
        "definition_en": request.definition_en,
        "scope_id": request.scope_id,
        "candidate_vi": request.candidate_vi,
        "snippet_original": request.snippet_original,
        "snippet_masked": request.snippet_masked,
        "source_type": request.source_type,
    }
    return {
        "evidence_id": request.evidence_id,
        "route_id": provider.route_id,
        "model_id": provider.model_id,
        "outcome": outcome,
        "error_code": error_code,
        "request_sha256": _sha(request_payload),
        "response_sha256": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "raw_response": raw_response,
    }


def _sha(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = ["FallbackJudgeRouter", "StaticJudgeProvider"]
