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
from .prompt import SYSTEM_PROMPT, build_judge_messages, judge_json_schema


class GeminiOfficialJudgeProvider:
    route_id = "gemini_official"

    def __init__(
        self,
        *,
        api_key: str,
        model_id: str = "gemini-3.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 120,
        json_post: JsonPost | None = None,
    ) -> None:
        if not api_key or not model_id:
            raise ValueError("Gemini official configuration is incomplete")
        self.model_id = model_id
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._json_post = json_post or default_json_post

    def judge(self, request: JudgeRequest) -> JudgeRouteResult:
        messages, _ = build_judge_messages(request)
        user_content = messages[1]["content"]
        api_request = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [
                {"role": "user", "parts": [{"text": user_content}]}
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": judge_json_schema(),
            },
        }
        request_sha = _sha(api_request)
        endpoint = f"{self._base_url}/models/{self.model_id}:generateContent"
        try:
            response = self._json_post(
                endpoint,
                {"x-goog-api-key": self._api_key},
                api_request,
                self._timeout_seconds,
            )
        except Exception as exc:
            raise JudgeTransportError(
                "gemini_official_transport_failed",
                "Gemini official transport failed",
            ) from exc
        response_sha = _sha(response)
        try:
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            parsed = text if isinstance(text, Mapping) else json.loads(text)
            payload = validate_judge_payload_for_snippet(
                parsed,
                snippet_original=request.snippet_original,
            )
        except Exception as exc:
            raise JudgeSchemaError(
                "gemini_official_schema_failed",
                "Gemini official returned an invalid judge payload",
                raw_response=response,
            ) from exc
        usage = response.get("usageMetadata", {})
        return JudgeRouteResult(
            route_id=self.route_id,
            model_id=self.model_id,
            payload=payload,
            request_sha256=request_sha,
            response_sha256=response_sha,
            input_tokens=_token(usage, "promptTokenCount"),
            output_tokens=_token(usage, "candidatesTokenCount"),
            raw_response=response,
        )

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": type(self).__name__,
            "route_id": self.route_id,
            "model_id": self.model_id,
            "base_url": self._base_url,
            "timeout_seconds": self._timeout_seconds,
            "schema_mode": "response_json_schema",
        }


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


__all__ = ["GeminiOfficialJudgeProvider"]
