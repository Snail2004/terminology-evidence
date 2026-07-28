from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class JudgeTransportError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class JudgeSchemaError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, raw_response: Any | None = None
    ) -> None:
        self.code = code
        self.raw_response = raw_response
        super().__init__(message)


class AllJudgeRoutesFailed(RuntimeError):
    def __init__(self, attempts: tuple[dict[str, Any], ...]) -> None:
        self.attempts = attempts
        super().__init__("all attestation judge routes failed")


@dataclass(frozen=True)
class JudgeRequest:
    evidence_id: str
    definition_en: str
    scope_id: str
    candidate_vi: str
    snippet_original: str
    snippet_masked: str
    source_type: str


@dataclass(frozen=True)
class JudgeRouteResult:
    route_id: str
    model_id: str
    payload: Mapping[str, Any]
    request_sha256: str
    response_sha256: str
    input_tokens: int
    output_tokens: int
    raw_response: Any


class JudgeProvider(Protocol):
    route_id: str
    model_id: str

    def judge(self, request: JudgeRequest) -> JudgeRouteResult: ...


__all__ = [
    "AllJudgeRoutesFailed",
    "JudgeProvider",
    "JudgeRequest",
    "JudgeRouteResult",
    "JudgeSchemaError",
    "JudgeTransportError",
]
