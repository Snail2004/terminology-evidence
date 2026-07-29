from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from context_substitution.v2.providers.base import (
    ContextProviderRoute,
    ProviderRawResponse,
)


_RESPONSE_FORMAT_MODES = frozenset({"json_schema", "json_object", "prompt_only"})
_MAX_OUTPUT_PARAMETERS = frozenset({"max_completion_tokens", "max_tokens"})
_REASONING_EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh"}
)
_THINKING_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "MINIMAL"})


@dataclass(frozen=True)
class OpenAICompatibleRouteSettings:
    route_id: str
    model_id: str
    api_key: str = field(repr=False)
    base_url: str = "http://localhost:8317/v1"
    timeout_seconds: int = 300
    response_format_mode: str = "json_schema"
    max_output_parameter: str = "max_completion_tokens"
    model_family: str | None = None
    model_profile: str | None = None
    independence_group: str | None = None
    role_equivalence_group: str | None = None
    thinking_level: str | None = None
    reasoning_effort: str | None = None
    temperature: float = 0.0
    max_output_tokens: int | None = None
    role_plan_sha256: str | None = None
    escalation_kind: str | None = None
    max_attempts: int = 1
    retry_backoff_seconds: tuple[float, ...] = ()

    def build(self) -> ContextProviderRoute:
        if not self.api_key.strip():
            raise ValueError(f"{self.route_id}: API key must not be empty")
        if self.response_format_mode not in _RESPONSE_FORMAT_MODES:
            raise ValueError("unsupported OpenAI-compatible response format mode")
        if self.max_output_parameter not in _MAX_OUTPUT_PARAMETERS:
            raise ValueError("unsupported OpenAI-compatible output-token parameter")
        if self.reasoning_effort not in {None, *_REASONING_EFFORTS}:
            raise ValueError("unsupported OpenAI-compatible reasoning effort")
        if self.thinking_level not in {None, *_THINKING_LEVELS}:
            raise ValueError("unsupported OpenAI-compatible thinking level")
        if self.thinking_level is not None and self.reasoning_effort is not None:
            raise ValueError(
                "OpenAI-compatible route must not mix thinking and reasoning controls"
            )
        return ContextProviderRoute(
            route_id=self.route_id,
            model_id=self.model_id,
            sender=OpenAICompatibleSender(self),
            model_family=self.model_family,
            model_profile=self.model_profile,
            independence_group=self.independence_group,
            role_equivalence_group=self.role_equivalence_group,
            thinking_level=self.thinking_level,
            reasoning_effort=self.reasoning_effort,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            timeout_seconds=self.timeout_seconds,
            role_plan_sha256=self.role_plan_sha256,
            escalation_kind=self.escalation_kind,
            max_attempts=self.max_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
        )


class OpenAICompatibleSender:
    """OpenAI Chat Completions adapter for compatible provider transports."""

    def __init__(self, settings: OpenAICompatibleRouteSettings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def __call__(
        self,
        *,
        system_prompt: str,
        user_payload_json: str,
        response_schema: Mapping[str, Any],
        max_output_tokens: int,
        tag: str,
    ) -> ProviderRawResponse:
        request = self._request(
            system_prompt=system_prompt,
            user_payload_json=user_payload_json,
            response_schema=response_schema,
            max_output_tokens=max_output_tokens,
        )
        started = time.perf_counter()
        response = self._get_client().chat.completions.create(**request)
        latency_ms = round((time.perf_counter() - started) * 1_000)
        text = _response_text(response)
        usage = _usage_counts(getattr(response, "usage", None))
        return ProviderRawResponse(
            text=text,
            payload=None,
            request_id=getattr(response, "id", None),
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            reasoning_tokens=usage["reasoning_tokens"],
            cached=usage["cached"],
            latency_ms=latency_ms,
        )

    def _request(
        self,
        *,
        system_prompt: str,
        user_payload_json: str,
        response_schema: Mapping[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        mode = self._settings.response_format_mode
        rendered_system = system_prompt
        request: dict[str, Any] = {
            "model": self._settings.model_id,
            "temperature": self._settings.temperature,
            "messages": [
                {"role": "system", "content": rendered_system},
                {"role": "user", "content": user_payload_json},
            ],
        }
        if self._settings.reasoning_effort is not None:
            request["reasoning_effort"] = self._settings.reasoning_effort
        if mode == "json_schema":
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "context_substitution_response",
                    "strict": True,
                    "schema": dict(response_schema),
                },
            }
        else:
            rendered_schema = json.dumps(
                dict(response_schema),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            request["messages"][0]["content"] = (
                f"{system_prompt}\nReturn exactly one JSON object matching this schema:"
                f"\n{rendered_schema}"
            )
            if mode == "json_object":
                request["response_format"] = {"type": "json_object"}
        request[self._settings.max_output_parameter] = max_output_tokens
        return request

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self._settings.api_key,
                base_url=self._settings.base_url,
                timeout=self._settings.timeout_seconds,
            )
        return self._client


def _response_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("gateway response has no choices")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "".join(parts)
    raise ValueError("gateway response has no text content")


def _usage_counts(usage: Any) -> dict[str, int | bool]:
    if usage is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cached": False,
        }
    prompt = _nonnegative(getattr(usage, "prompt_tokens", 0))
    output = _nonnegative(getattr(usage, "completion_tokens", 0))
    completion_details = getattr(usage, "completion_tokens_details", None)
    reasoning = _nonnegative(
        getattr(completion_details, "reasoning_tokens", 0)
    )
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    cached = _nonnegative(getattr(prompt_details, "cached_tokens", 0)) > 0
    return {
        "input_tokens": prompt,
        "output_tokens": max(output, reasoning),
        "reasoning_tokens": reasoning,
        "cached": cached,
    }


def _nonnegative(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return max(result, 0)


__all__ = [
    "OpenAICompatibleRouteSettings",
    "OpenAICompatibleSender",
]
