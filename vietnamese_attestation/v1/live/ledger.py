"""Hash-chained E Live ledger with zero-provider accounting."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import LiveSchemaError, canonical_bytes, canonical_sha256, require_sha256, utc_now
from .schemas import LIVE_EVENT_SCHEMA_ID, LIVE_TOOL_SCHEMA_VERSION, validate_event

GENESIS_SHA256 = "0" * 64


class EventLedger:
    def __init__(self, *, run_id: str, phase_id: str, clock=utc_now) -> None:
        self.run_id = run_id
        self.phase_id = phase_id
        self.clock = clock
        self.events: list[dict[str, Any]] = []

    @property
    def last_sha256(self) -> str:
        return self.events[-1]["event_sha256"] if self.events else GENESIS_SHA256

    def append(
        self,
        event_kind: str,
        *,
        candidate_replicate_id: str,
        semantic_role: str,
        semantic_call_id: str,
        transport_attempt_id: str,
        payload: Mapping[str, Any] | None = None,
        retry_of: str | None = None,
        failure_disposition: str = "NONE",
        usage: Mapping[str, Any] | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "schema_id": LIVE_EVENT_SCHEMA_ID,
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "event_index": len(self.events),
            "previous_event_sha256": self.last_sha256,
            "event_sha256": "0" * 64,
            "event_kind": event_kind,
            "run_id": self.run_id,
            "phase_id": self.phase_id,
            "candidate_replicate_id": candidate_replicate_id,
            "semantic_role": semantic_role,
            "semantic_call_id": semantic_call_id,
            "transport_attempt_id": transport_attempt_id,
            "retry_of": retry_of,
            "payload": dict(payload or {}),
            "failure_disposition": failure_disposition,
            "usage": dict(usage or {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0, "cost": 0.0, "currency": "USD"}),
            "created_at": created_at or self.clock(),
        }
        event["event_sha256"] = _event_hash(event)
        validate_event(event)
        self.events.append(event)
        return dict(event)

    def append_model_request(
        self,
        *,
        candidate_id: str,
        sense_id: str,
        semantic_call_id: str,
        provider_request_id: str,
        provider_id: str,
        model_id: str,
        route: str,
        prompt_sha256: str,
        request_sha256: str,
        response_sha256: str,
        raw_response_locator: str,
        retry_index: int = 0,
        failure_disposition: str = "NONE",
        usage: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        for name, value in (("prompt_sha256", prompt_sha256), ("request_sha256", request_sha256), ("response_sha256", response_sha256)):
            require_sha256(value, path=f"$.payload.{name}")
        return self.append(
            "E_MODEL_REQUEST",
            candidate_replicate_id=candidate_id,
            semantic_role=route,
            semantic_call_id=semantic_call_id,
            transport_attempt_id=provider_request_id,
            failure_disposition=failure_disposition,
            usage=usage,
            payload={
                "candidate_id": candidate_id,
                "sense_id": sense_id,
                "semantic_role": route,
                "semantic_call_id": semantic_call_id,
                "provider_request_id": provider_request_id,
                "retry_index": retry_index,
                "provider_id": provider_id,
                "model_id": model_id,
                "route": route,
                "prompt_sha256": prompt_sha256,
                "request_sha256": request_sha256,
                "response_sha256": response_sha256,
                "raw_response_locator": raw_response_locator,
            },
        )

    def write_jsonl(self, path: str | Path) -> dict[str, Any]:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = b"".join(canonical_bytes(row) + b"\n" for row in self.events)
        destination.write_bytes(raw)
        return {"artifact_ref": destination.name, "artifact_sha256": hashlib.sha256(raw).hexdigest(), "event_count": len(self.events)}


def verify_event_chain(events: Sequence[Mapping[str, Any]], *, run_id: str | None = None) -> list[dict[str, Any]]:
    previous = GENESIS_SHA256
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(events):
        event = validate_event(raw)
        if event["event_index"] != index:
            raise LiveSchemaError("ledger event index is not contiguous")
        if event["previous_event_sha256"] != previous:
            raise LiveSchemaError("ledger previous hash mismatch")
        if run_id is not None and event["run_id"] != run_id:
            raise LiveSchemaError("ledger run_id mismatch")
        if event["event_sha256"] != _event_hash(event):
            raise LiveSchemaError("ledger event hash mismatch")
        previous = event["event_sha256"]
        normalized.append(dict(event))
    return normalized


def _event_hash(event: Mapping[str, Any]) -> str:
    body = {key: value for key, value in event.items() if key != "event_sha256"}
    return canonical_sha256(body)


__all__ = ["EventLedger", "GENESIS_SHA256", "verify_event_chain"]
