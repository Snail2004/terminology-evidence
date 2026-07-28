from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from ..contracts.judge import validate_judge_payload_for_snippet
from .base import (
    JudgeRequest,
    JudgeRouteResult,
    JudgeSchemaError,
    JudgeTransportError,
)
from .http import JsonPost, default_json_post
from .prompt import build_judge_messages, judge_json_schema


class OpenAiCompatibleJudgeProvider:
    def __init__(
        self,
        *,
        route_id: str,
        model_id: str,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 120,
        json_post: JsonPost | None = None,
    ) -> None:
        if not route_id or not model_id or not base_url or not api_key:
            raise ValueError("judge provider configuration is incomplete")
        self.route_id = route_id
        self.model_id = model_id
        self._endpoint = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._json_post = json_post or default_json_post

    def judge(self, request: JudgeRequest) -> JudgeRouteResult:
        messages, _ = build_judge_messages(request)
        api_request = {
            "model": self.model_id,
            "messages": messages,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "vietnamese_attestation_judge_v1",
                    "strict": True,
                    "schema": judge_json_schema(),
                },
            },
        }
        request_sha = _sha(api_request)
        try:
            response = self._json_post(
                self._endpoint,
                {"Authorization": f"Bearer {self._api_key}"},
                api_request,
                self._timeout_seconds,
            )
        except Exception as exc:
            raise JudgeTransportError(
                "openai_compatible_transport_failed",
                f"{self.route_id} transport failed",
            ) from exc
        response_sha = _sha(response)
        try:
            choices = response["choices"]
            content = choices[0]["message"]["content"]
            parsed = content if isinstance(content, Mapping) else json.loads(content)
            payload = validate_judge_payload_for_snippet(
                parsed,
                snippet_original=request.snippet_original,
            )
        except Exception as exc:
            raise JudgeSchemaError(
                "openai_compatible_schema_failed",
                f"{self.route_id} returned an invalid judge payload",
                raw_response=response,
            ) from exc
        usage = response.get("usage", {})
        return JudgeRouteResult(
            route_id=self.route_id,
            model_id=self.model_id,
            payload=payload,
            request_sha256=request_sha,
            response_sha256=response_sha,
            input_tokens=_token(usage, "prompt_tokens"),
            output_tokens=_token(usage, "completion_tokens"),
            raw_response=response,
        )

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": type(self).__name__,
            "route_id": self.route_id,
            "model_id": self.model_id,
            "endpoint": self._endpoint,
            "timeout_seconds": self._timeout_seconds,
            "schema_mode": "json_schema_strict",
        }


class ShopAiJudgeProvider(OpenAiCompatibleJudgeProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model_id: str = "gemini-3.5-flash",
        base_url: str = "https://api.shopaikey.com/v1",
        timeout_seconds: float = 120,
        json_post: JsonPost | None = None,
    ) -> None:
        super().__init__(
            route_id="shopai",
            model_id=model_id,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            json_post=json_post,
        )


class CKeyJudgeProvider(OpenAiCompatibleJudgeProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_id: str = "google/gemini-3.5-flash",
        timeout_seconds: float = 120,
        json_post: JsonPost | None = None,
    ) -> None:
        super().__init__(
            route_id="ckey",
            model_id=model_id,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            json_post=json_post,
        )


def _sha(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _token(value: Any, key: str) -> int:
    if not isinstance(value, Mapping):
        return 0
    token = value.get(key, 0)
    return int(token) if isinstance(token, int) and not isinstance(token, bool) else 0


__all__ = [
    "CKeyJudgeProvider",
    "OpenAiCompatibleJudgeProvider",
    "ShopAiJudgeProvider",
]
