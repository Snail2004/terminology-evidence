"""Gemini official D0 adapter with an injectable zero-network transport."""

from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from ...strict_json import strict_json_loads
from ..authority_adapter.e05 import E05_PROVIDER_PLAN_SELF_SHA256
from ..common import (
    LiveSchemaError,
    canonical_bytes,
    canonical_sha256,
    require_exact_keys,
    require_string,
    seal,
    verify_seal,
)
from ..judge import judge_request_sha256, validate_provider_transport_result
from ..schemas import (
    CONCEPT_RELATIONS,
    DOMAIN_RELATIONS,
    JUDGEABILITY,
    JUDGE_RESPONSE_SCHEMA_ID,
    LIVE_TOOL_SCHEMA_VERSION,
    USAGE_TYPES,
    validate_judge_request,
    validate_judge_response,
    validate_provider_role_plan,
)


GEMINI_PROVIDER_ID = "gemini_official"
GEMINI_MODEL_ID = "gemini-3.5-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504})
_PRICING_SCHEMA_ID = "EGeminiPricingAuthorityV1"
_SYSTEM_PROMPT = (
    "You are the Vietnamese Attestation Judge. Compare the frozen English sense "
    "with the supplied Vietnamese evidence. Do not choose a glossary term or emit "
    "a final glossary decision. Return one strict JSON object only."
)


class GeminiTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


class GeminiUnknownPhysicalOutcome(RuntimeError):
    """The client cannot establish whether a physical request completed."""

    def __init__(
        self,
        message: str,
        *,
        started_at: str,
        completed_at: str,
        provider_request_id: str,
    ) -> None:
        super().__init__(message)
        self.started_at = started_at
        self.completed_at = completed_at
        self.provider_request_id = provider_request_id


class UrllibGeminiTransport:
    """Actual HTTP transport. E-05 tests inject a recorder and never call this."""

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        started_ms = int(time.time() * 1000)
        started_at = _timestamp_from_ms(started_ms)
        request = urllib.request.Request(
            url=url,
            data=canonical_bytes(payload),
            headers={"Content-Type": "application/json", **dict(headers)},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body_raw = response.read()
                status_code = int(response.status)
                response_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            body_raw = exc.read()
            status_code = int(exc.code)
            response_headers = {str(k).lower(): str(v) for k, v in exc.headers.items()}
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as exc:
            completed_ms = max(started_ms, int(time.time() * 1000))
            raise GeminiUnknownPhysicalOutcome(
                "Gemini transport ended with an ambiguous physical outcome",
                started_at=started_at,
                completed_at=_timestamp_from_ms(completed_ms),
                provider_request_id=f"gemini-unknown-{hashlib.sha256(canonical_bytes(payload)).hexdigest()[:24]}",
            ) from exc
        completed_ms = max(started_ms, int(time.time() * 1000))
        body = _decode_provider_body(body_raw)
        return {
            "status_code": status_code,
            "headers": response_headers,
            "body": body,
            "started_at": started_at,
            "completed_at": _timestamp_from_ms(completed_ms),
        }


class GeminiOfficialAdapter:
    """Map one exact E role-plan attempt to the strict transport contract."""

    def __init__(
        self,
        *,
        role_plan: Mapping[str, Any],
        api_key: str,
        pricing_authority: Mapping[str, Any],
        transport: GeminiTransport | None = None,
        base_url: str = GEMINI_BASE_URL,
        timeout_seconds: float = 120.0,
    ) -> None:
        checked_plan = validate_provider_role_plan(role_plan)
        if checked_plan["integrity"]["self_sha256"] != E05_PROVIDER_PLAN_SELF_SHA256:
            raise LiveSchemaError("Gemini adapter requires the exact E-05 provider role plan")
        if not api_key:
            raise LiveSchemaError("Gemini official API key is missing")
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise LiveSchemaError("Gemini timeout must be positive")
        checked_pricing = _validate_pricing_authority(pricing_authority)
        if transport is None and checked_pricing["status"] != "MAIN_PINNED_APPROVED":
            raise LiveSchemaError("real Gemini transport requires Main-approved pricing authority")
        self._roles = {
            str(row["semantic_role"]): dict(row) for row in checked_plan["roles"]
        }
        self._api_key = api_key
        self._pricing = checked_pricing
        self._transport = transport or UrllibGeminiTransport()
        self.zero_network = transport is not None
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = float(timeout_seconds)
        self._attempts: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(provider={GEMINI_PROVIDER_ID!r}, "
            f"model={GEMINI_MODEL_ID!r})"
        )

    def invoke(
        self, request: Mapping[str, Any], *, role_config: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        checked_request = validate_judge_request(request)
        role = str(checked_request["semantic_role"])
        expected_role = self._roles.get(role)
        if expected_role is None or dict(role_config) != expected_role:
            raise LiveSchemaError("Gemini role/config differs from the exact E-05 plan")
        if (
            expected_role["provider_id"] != GEMINI_PROVIDER_ID
            or expected_role["model_id"] != GEMINI_MODEL_ID
            or expected_role["mode"] != "LIVE_PROVIDER"
            or expected_role["generation_config"]
            != {"temperature": 0, "reasoning": "none"}
            or expected_role["max_retries"] != 1
        ):
            raise LiveSchemaError("Gemini role route/model/generation contract mismatch")

        attempt_key = (role, str(checked_request["evidence_id"]))
        with self._lock:
            retry_index = self._attempts.get(attempt_key, 0)
            self._attempts[attempt_key] = retry_index + 1
        if retry_index > int(expected_role["max_retries"]):
            raise LiveSchemaError("Gemini adapter retry budget exceeded")

        request_sha = judge_request_sha256(checked_request)
        api_payload = _api_payload(checked_request, expected_role)
        endpoint = f"{self._base_url}/models/{GEMINI_MODEL_ID}:generateContent"
        try:
            exchange = self._transport.post_json(
                url=endpoint,
                headers={"x-goog-api-key": self._api_key},
                payload=api_payload,
                timeout_seconds=self._timeout_seconds,
            )
        except GeminiUnknownPhysicalOutcome as exc:
            result = _failure_result(
                provider_request_id=exc.provider_request_id,
                outcome="UNKNOWN_PHYSICAL_OUTCOME",
                request_sha=request_sha,
                started_at=exc.started_at,
                completed_at=exc.completed_at,
                retry_index=retry_index,
            )
            return validate_provider_transport_result(result, request_sha256=request_sha)
        except Exception as exc:
            now = _timestamp_from_ms(int(time.time() * 1000))
            result = _failure_result(
                provider_request_id=f"gemini-unknown-{request_sha[:24]}",
                outcome="UNKNOWN_PHYSICAL_OUTCOME",
                request_sha=request_sha,
                started_at=now,
                completed_at=now,
                retry_index=retry_index,
            )
            # An unclassified transport exception is physically ambiguous. Its
            # type is intentionally not serialized because it may contain
            # credential-bearing client details.
            _ = exc
            return validate_provider_transport_result(
                result, request_sha256=request_sha
            )

        normalized = _validate_exchange(exchange)
        provider_request_id = _provider_request_id(
            normalized, fallback=f"gemini-request-id-missing-{request_sha[:16]}-{retry_index}"
        )
        status_code = normalized["status_code"]
        if status_code in _RETRYABLE_HTTP:
            outcome = "RETRYABLE_FAILURE"
        elif not 200 <= status_code < 300:
            outcome = "TERMINAL_FAILURE" if 400 <= status_code < 500 else "UNKNOWN_PHYSICAL_OUTCOME"
        else:
            try:
                response, usage = _semantic_response(normalized["body"], checked_request)
            except LiveSchemaError:
                outcome = "TERMINAL_FAILURE"
            else:
                if provider_request_id.startswith("gemini-request-id-missing-"):
                    outcome = "TERMINAL_FAILURE"
                else:
                    cost = _cost(usage, self._pricing)
                    result = {
                        "provider_request_id": provider_request_id,
                        "outcome": "SUCCESS",
                        "response": response,
                        "request_sha256": request_sha,
                        "response_physical_sha256": hashlib.sha256(
                            canonical_bytes(response)
                        ).hexdigest(),
                        "response_canonical_sha256": canonical_sha256(response),
                        "started_at": normalized["started_at"],
                        "completed_at": normalized["completed_at"],
                        "latency_ms": _latency_ms(
                            normalized["started_at"], normalized["completed_at"]
                        ),
                        "input_tokens": usage["input_tokens"],
                        "output_tokens": usage["output_tokens"],
                        "reasoning_tokens": usage["reasoning_tokens"],
                        "total_tokens": usage["total_tokens"],
                        "cost": cost,
                        "currency": self._pricing["currency"],
                        "physical_request_count": 1,
                        "retry_index": retry_index,
                    }
                    return validate_provider_transport_result(
                        result, request_sha256=request_sha
                    )

        result = _failure_result(
            provider_request_id=provider_request_id,
            outcome=outcome,
            request_sha=request_sha,
            started_at=normalized["started_at"],
            completed_at=normalized["completed_at"],
            retry_index=retry_index,
        )
        return validate_provider_transport_result(result, request_sha256=request_sha)


def make_recorded_pricing_authority(
    *,
    input_per_million: float = 0.1,
    output_per_million: float = 0.4,
    reasoning_per_million: float = 0.4,
) -> dict[str, Any]:
    """Create an explicitly test-only price table for recorded transport fixtures."""

    return seal(
        {
            "schema_id": _PRICING_SCHEMA_ID,
            "schema_version": "1.0.0",
            "status": "TEST_ONLY_RECORDED",
            "currency": "USD",
            "rates_per_million": {
                "input": float(input_per_million),
                "output": float(output_per_million),
                "reasoning": float(reasoning_per_million),
            },
            "integrity": {},
        }
    )


def _api_payload(
    request: Mapping[str, Any], role_config: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        f"{_SYSTEM_PROMPT} Semantic role: "
                        f"{role_config['semantic_role']}."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "prompt_identity_sha256": role_config["prompt_sha256"],
                                "judge_request": dict(request),
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "thinkingConfig": {"thinkingBudget": 0},
            "responseMimeType": "application/json",
            "responseJsonSchema": _judge_response_json_schema(),
        },
    }


def _judge_response_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_id",
            "schema_version",
            "judgeability",
            "concept_relation",
            "domain_relation",
            "usage_type",
            "evidence_span",
            "reason_codes",
            "reason",
            "machine_translation_suspected",
        ],
        "properties": {
            "schema_id": {"const": JUDGE_RESPONSE_SCHEMA_ID},
            "schema_version": {"const": LIVE_TOOL_SCHEMA_VERSION},
            "judgeability": {"enum": sorted(JUDGEABILITY)},
            "concept_relation": {"enum": sorted(CONCEPT_RELATIONS)},
            "domain_relation": {"enum": sorted(DOMAIN_RELATIONS)},
            "usage_type": {"enum": sorted(USAGE_TYPES)},
            "evidence_span": {"type": "string"},
            "reason_codes": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "reason": {"type": "string", "minLength": 1},
            "machine_translation_suspected": {"type": "boolean"},
        },
    }


def _semantic_response(
    body: Any, request: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    if not isinstance(body, Mapping):
        raise LiveSchemaError("Gemini response body must be an object")
    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LiveSchemaError("Gemini response lacks candidate JSON") from exc
    if isinstance(text, Mapping):
        parsed = dict(text)
    elif isinstance(text, str):
        try:
            parsed = strict_json_loads(text)
        except ValueError as exc:
            raise LiveSchemaError("Gemini candidate text is not strict JSON") from exc
    else:
        raise LiveSchemaError("Gemini candidate JSON has an unsupported type")
    if not isinstance(parsed, Mapping):
        raise LiveSchemaError("Gemini candidate JSON must be an object")
    response = validate_judge_response(
        parsed, snippet=str(request["snippet_original"])
    )
    usage = body.get("usageMetadata")
    if not isinstance(usage, Mapping):
        raise LiveSchemaError("Gemini response lacks usage metadata")
    input_tokens = _token(usage, "promptTokenCount", required=True)
    output_tokens = _token(usage, "candidatesTokenCount", required=True)
    reasoning_tokens = _token(usage, "thoughtsTokenCount", required=False)
    total_tokens = _token(usage, "totalTokenCount", required=True)
    if reasoning_tokens != 0:
        raise LiveSchemaError("Gemini returned reasoning tokens under reasoning=none")
    if total_tokens != input_tokens + output_tokens + reasoning_tokens:
        raise LiveSchemaError("Gemini usage token total is inconsistent")
    return response, {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def _validate_exchange(value: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        value,
        {"status_code", "headers", "body", "started_at", "completed_at"},
        path="$.gemini_exchange",
    )
    if isinstance(value["status_code"], bool) or not isinstance(value["status_code"], int):
        raise LiveSchemaError("Gemini status_code must be an integer")
    if not isinstance(value["headers"], Mapping) or any(
        not isinstance(key, str) or not isinstance(item, str)
        for key, item in value["headers"].items()
    ):
        raise LiveSchemaError("Gemini response headers must be strings")
    if value["body"] is not None and not isinstance(value["body"], Mapping):
        raise LiveSchemaError("Gemini response body must be an object or null")
    for key in ("started_at", "completed_at"):
        require_string(value[key], path=f"$.gemini_exchange.{key}")
    _latency_ms(value["started_at"], value["completed_at"])
    return {
        "status_code": value["status_code"],
        "headers": {str(key).lower(): str(item) for key, item in value["headers"].items()},
        "body": value["body"],
        "started_at": value["started_at"],
        "completed_at": value["completed_at"],
    }


def _provider_request_id(exchange: Mapping[str, Any], *, fallback: str) -> str:
    headers = exchange["headers"]
    for key in ("x-goog-request-id", "x-request-id"):
        value = headers.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    body = exchange.get("body")
    if isinstance(body, Mapping):
        value = body.get("responseId")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _failure_result(
    *,
    provider_request_id: str,
    outcome: str,
    request_sha: str,
    started_at: str,
    completed_at: str,
    retry_index: int,
) -> dict[str, Any]:
    null_sha = canonical_sha256(None)
    return {
        "provider_request_id": provider_request_id,
        "outcome": outcome,
        "response": None,
        "request_sha256": request_sha,
        "response_physical_sha256": hashlib.sha256(canonical_bytes(None)).hexdigest(),
        "response_canonical_sha256": null_sha,
        "started_at": started_at,
        "completed_at": completed_at,
        "latency_ms": _latency_ms(started_at, completed_at),
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
        "currency": "USD",
        "physical_request_count": 1,
        "retry_index": retry_index,
    }


def _validate_pricing_authority(value: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "status",
            "currency",
            "rates_per_million",
            "integrity",
        },
        path="$.pricing_authority",
    )
    if value["schema_id"] != _PRICING_SCHEMA_ID or value["schema_version"] != "1.0.0":
        raise LiveSchemaError("Gemini pricing authority identity mismatch")
    if value["status"] not in {"TEST_ONLY_RECORDED", "MAIN_PINNED_APPROVED"}:
        raise LiveSchemaError("Gemini pricing authority status is unsupported")
    if value["currency"] != "USD":
        raise LiveSchemaError("Gemini pricing currency must be USD")
    rates = value["rates_per_million"]
    if not isinstance(rates, Mapping):
        raise LiveSchemaError("Gemini pricing rates must be an object")
    require_exact_keys(rates, {"input", "output", "reasoning"}, path="$.rates_per_million")
    for key, item in rates.items():
        if isinstance(item, bool) or not isinstance(item, (int, float)) or item < 0:
            raise LiveSchemaError(f"Gemini pricing rate is invalid: {key}")
    if not verify_seal(value):
        raise LiveSchemaError("Gemini pricing authority self hash mismatch")
    return dict(value)


def _cost(usage: Mapping[str, int], pricing: Mapping[str, Any]) -> float:
    rates = pricing["rates_per_million"]
    amount = (
        usage["input_tokens"] * float(rates["input"])
        + usage["output_tokens"] * float(rates["output"])
        + usage["reasoning_tokens"] * float(rates["reasoning"])
    ) / 1_000_000.0
    return round(amount, 12)


def _token(value: Mapping[str, Any], key: str, *, required: bool) -> int:
    if key not in value and not required:
        return 0
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise LiveSchemaError(f"Gemini usage field is invalid: {key}")
    return item


def _decode_provider_body(raw: bytes) -> Mapping[str, Any] | None:
    if not raw:
        return None
    try:
        value = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, ValueError):
        # The physical request completed, so preserve a non-semantic marker
        # that the adapter will classify as a terminal malformed response.
        return {"malformed_body_sha256": hashlib.sha256(raw).hexdigest()}
    if not isinstance(value, Mapping):
        raise LiveSchemaError("Gemini HTTP body must be an object")
    return dict(value)


def _latency_ms(started_at: str, completed_at: str) -> int:
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiveSchemaError("Gemini transport timestamp is invalid") from exc
    if started.tzinfo is None or completed.tzinfo is None or completed < started:
        raise LiveSchemaError("Gemini transport timestamp interval is invalid")
    return int((completed - started).total_seconds() * 1000)


def _timestamp_from_ms(value: int) -> str:
    return (
        datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


__all__ = [
    "GEMINI_MODEL_ID",
    "GEMINI_PROVIDER_ID",
    "GeminiOfficialAdapter",
    "GeminiTransport",
    "GeminiUnknownPhysicalOutcome",
    "UrllibGeminiTransport",
    "make_recorded_pricing_authority",
]
