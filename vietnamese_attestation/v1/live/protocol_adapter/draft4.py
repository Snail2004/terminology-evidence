"""Deterministic projection of E ledger and lifecycle facts into exact Draft4."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...strict_json import canonical_relative_ref, reject_link
from ..authority_adapter.e05 import (
    E05ExactIntegrationInputs,
    validate_e05_protocol_instance,
)
from ..common import (
    LiveSchemaError,
    canonical_bytes,
    canonical_sha256,
    require_sha256,
    seal,
)
from ..ledger import verify_event_chain


DRAFT4_SCHEMA_VERSION = "1.1.0-draft.4"
EXTERNAL_HOLD_PRICE_TABLE_SHA256 = canonical_sha256(
    {"schema_id": "EExternalPricingHoldV1", "status": "EXTERNAL_HOLD"}
)
_MODEL_EVENTS = frozenset({"C_MODEL_REQUEST", "E_MODEL_REQUEST"})
_PHYSICAL_EVENTS = frozenset(
    {"C_MODEL_REQUEST", "E_MODEL_REQUEST", "E_DISCOVERY_QUERY", "E_DIRECT_FETCH_REQUEST"}
)


class Draft4LifecycleAdapter:
    """Project verified internal facts without granting execution authority."""

    def __init__(self, inputs: E05ExactIntegrationInputs) -> None:
        self.inputs = inputs
        rows = inputs.candidate_set["ordered_candidates"]
        self._candidates = {str(row["candidate_id"]): dict(row) for row in rows}

    def adapt_events(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        artifact_root: str | Path,
    ) -> list[dict[str, Any]]:
        checked = verify_event_chain(events)
        root = _artifact_root(artifact_root)
        previous: str | None = None
        projected: list[dict[str, Any]] = []
        for index, source in enumerate(checked, start=1):
            event = self._adapt_event(source, index=index, previous=previous, root=root)
            event["event_sha256"] = canonical_sha256(
                {key: value for key, value in event.items() if key != "event_sha256"}
            )
            validate_e05_protocol_instance(
                self.inputs, role="LIVE_LEDGER_EVENT", value=event
            )
            previous = event["event_sha256"]
            projected.append(event)
        return self.validate_event_chain(projected)

    def validate_event_chain(
        self, events: Sequence[Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        previous: str | None = None
        result: list[dict[str, Any]] = []
        for expected_index, raw in enumerate(events, start=1):
            event = validate_e05_protocol_instance(
                self.inputs, role="LIVE_LEDGER_EVENT", value=raw
            )
            if event["event_index"] != expected_index:
                raise LiveSchemaError("Draft4 event index is not contiguous")
            if event["previous_event_sha256"] != previous:
                raise LiveSchemaError("Draft4 previous event hash mismatch")
            expected_sha = canonical_sha256(
                {key: value for key, value in event.items() if key != "event_sha256"}
            )
            if event["event_sha256"] != expected_sha:
                raise LiveSchemaError("Draft4 event self hash mismatch")
            previous = event["event_sha256"]
            result.append(dict(event))
        return result

    def make_usage_snapshot(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        rate_window_seconds: float = 60.0,
    ) -> dict[str, Any]:
        checked = self.validate_event_chain(events)
        usages = [event["usage"] for event in checked if event.get("usage") is not None]
        token_authorities = {
            str(usage["token_accounting_authority_sha256"]) for usage in usages
        }
        expected_token_authority = self.inputs.token_accounting.authority["integrity"][
            "self_sha256"
        ]
        if token_authorities and token_authorities != {expected_token_authority}:
            raise LiveSchemaError("Draft4 usage events have mixed token authority")
        if any(
            usage["currency"] is not None
            or usage["cost"] is not None
            or usage["usage_status"] != "TOKEN_ONLY_COST_UNAVAILABLE"
            for usage in usages
        ):
            raise LiveSchemaError("Draft4 token-only usage contains a cost claim")
        rate_windows: dict[str, dict[str, int]] = {}
        for event in checked:
            window = event.get("rate_window_id")
            usage = event.get("usage")
            if not isinstance(window, str) or usage is None:
                continue
            row = rate_windows.setdefault(window, {"requests": 0, "tokens": 0})
            if event["event_kind"] in _PHYSICAL_EVENTS:
                row["requests"] += 1
            row["tokens"] += int(usage["total_tokens"] or 0)
        model_events = [event for event in checked if event["event_kind"] in _MODEL_EVENTS]
        physical_events = [event for event in checked if event["event_kind"] in _PHYSICAL_EVENTS]
        snapshot = seal(
            {
                "schema_id": "UsageSnapshotV1",
                "schema_version": DRAFT4_SCHEMA_VERSION,
                "phase_id": self.inputs.integration_run_spec["phase_id"],
                "accounting_mode": "TOKEN_ONLY",
                "currency": None,
                "cost_status": "TOKEN_ONLY_COST_UNAVAILABLE",
                "token_accounting_authority_sha256": expected_token_authority,
                "rate_window_seconds": float(rate_window_seconds),
                "totals": {
                    "replicates": len(
                        {
                            str(event["candidate_replicate_id"])
                            for event in checked
                            if event.get("candidate_replicate_id") is not None
                        }
                    ),
                    "semantic_calls": len(
                        {
                            (str(event.get("semantic_role")), str(event.get("semantic_call_id")))
                            for event in model_events
                        }
                    ),
                    "transport_retries": sum(
                        1 for event in physical_events if event.get("transport_retry_id") is not None
                    ),
                    "physical_requests": len(physical_events),
                    "network_requests": _sum_usage(
                        [event["usage"] for event in physical_events],
                        "network_request_count",
                    ),
                    "c_model_requests": sum(
                        1 for event in checked if event["event_kind"] == "C_MODEL_REQUEST"
                    ),
                    "e_model_requests": sum(
                        1 for event in checked if event["event_kind"] == "E_MODEL_REQUEST"
                    ),
                    "e_discovery_queries": sum(
                        1 for event in checked if event["event_kind"] == "E_DISCOVERY_QUERY"
                    ),
                    "e_direct_fetches": sum(
                        1 for event in checked if event["event_kind"] == "E_DIRECT_FETCH_REQUEST"
                    ),
                    "e_fetch_retries": sum(
                        1
                        for event in checked
                        if event["event_kind"] == "E_DIRECT_FETCH_REQUEST"
                        and event.get("retry_of") is not None
                    ),
                    "e_redirect_hops": sum(
                        1 for event in checked if event["event_kind"] == "E_REDIRECT_HOP"
                    ),
                    "accepted_documents": sum(
                        1
                        for event in checked
                        if event["event_kind"] == "E_SOURCE_DOCUMENT_ACCEPTED"
                    ),
                    "usage_unjudgeable_requests": sum(
                        1
                        for usage in usages
                        if usage["usage_status"] == "USAGE_UNJUDGEABLE"
                    ),
                    "input_tokens": _sum_usage(usages, "input_tokens"),
                    "output_tokens": _sum_usage(usages, "output_tokens"),
                    "reasoning_tokens": _sum_usage(usages, "reasoning_tokens"),
                    "cached_input_tokens": _sum_usage(usages, "cached_input_tokens"),
                    "total_tokens": _sum_usage(usages, "total_tokens"),
                    "download_bytes": _sum_usage(usages, "download_bytes"),
                    "cost": None,
                    "max_request_duration_seconds": max(
                        (float(event.get("request_duration_seconds") or 0.0) for event in checked),
                        default=0.0,
                    ),
                    "max_requests_per_rate_window": max(
                        (row["requests"] for row in rate_windows.values()), default=0
                    ),
                    "max_tokens_per_rate_window": max(
                        (row["tokens"] for row in rate_windows.values()), default=0
                    ),
                },
                "integrity": {},
            }
        )
        return validate_e05_protocol_instance(
            self.inputs, role="USAGE_SNAPSHOT", value=snapshot
        )

    def make_run_start_receipt(
        self,
        *,
        issued_at: str,
        initial_ledger_head: str | None = None,
    ) -> dict[str, Any]:
        authorization = self.inputs.authorization_receipt
        bindings = authorization["bindings"]
        receipt = seal(
            {
                "schema_id": "LiveRunStartReceiptV1_1",
                "schema_version": DRAFT4_SCHEMA_VERSION,
                "receipt_id": "e05-d0-zero-provider-run-start-v1",
                "phase_id": authorization["phase_id"],
                "issued_at": issued_at,
                "authorization_receipt_self_sha256": authorization["integrity"][
                    "self_sha256"
                ],
                "authorization_receipt_physical_sha256": hashlib.sha256(
                    self.inputs.profile_member_bytes[
                        "main_run/main_live_authorization.json"
                    ]
                ).hexdigest(),
                "run_spec_self_sha256": bindings["run_spec_self_sha256"],
                "run_spec_physical_sha256": bindings["run_spec_physical_sha256"],
                "phase_authorized_candidate_set_self_sha256": bindings[
                    "phase_authorized_candidate_set_self_sha256"
                ],
                "phase_authorized_candidate_set_physical_sha256": bindings[
                    "phase_authorized_candidate_set_physical_sha256"
                ],
                "budget_spec_sha256": authorization["budget_spec_sha256"],
                "secret_readiness_receipt_sha256": authorization[
                    "secret_readiness_receipt_sha256"
                ],
                "secret_readiness_receipt_self_sha256": authorization[
                    "secret_readiness_receipt_self_sha256"
                ],
                "initial_ledger_head": initial_ledger_head,
                "integrity": {},
            }
        )
        return validate_e05_protocol_instance(
            self.inputs, role="RUN_START_RECEIPT", value=receipt
        )

    def make_run_stop_receipt(
        self,
        *,
        run_start_receipt: Mapping[str, Any],
        events: Sequence[Mapping[str, Any]],
        usage_snapshot: Mapping[str, Any],
        preserved_artifact_manifest_sha256: str,
        issued_at: str,
        terminal_status: str,
        stop_reason: str,
    ) -> dict[str, Any]:
        checked_events = self.validate_event_chain(events)
        if not checked_events:
            raise LiveSchemaError("Draft4 RUN_STOP requires a nonempty ledger")
        start = validate_e05_protocol_instance(
            self.inputs, role="RUN_START_RECEIPT", value=run_start_receipt
        )
        usage = validate_e05_protocol_instance(
            self.inputs, role="USAGE_SNAPSHOT", value=usage_snapshot
        )
        require_sha256(
            preserved_artifact_manifest_sha256,
            path="$.preserved_artifact_manifest_sha256",
        )
        receipt = seal(
            {
                "schema_id": "LiveRunStopReceiptV1_1",
                "schema_version": DRAFT4_SCHEMA_VERSION,
                "receipt_id": "e05-d0-zero-provider-run-stop-v1",
                "phase_id": self.inputs.integration_run_spec["phase_id"],
                "issued_at": issued_at,
                "terminal_status": terminal_status,
                "stop_reason": stop_reason,
                "authorization_receipt_self_sha256": self.inputs.authorization_receipt[
                    "integrity"
                ]["self_sha256"],
                "run_start_receipt_self_sha256": start["integrity"]["self_sha256"],
                "final_ledger_head_sha256": checked_events[-1]["event_sha256"],
                "usage_snapshot_self_sha256": usage["integrity"]["self_sha256"],
                "usage_snapshot_physical_sha256": hashlib.sha256(
                    canonical_bytes(usage)
                ).hexdigest(),
                "preserved_artifact_manifest_sha256": preserved_artifact_manifest_sha256,
                "integrity": {},
            }
        )
        return validate_e05_protocol_instance(
            self.inputs, role="RUN_STOP_RECEIPT", value=receipt
        )

    def _adapt_event(
        self,
        source: Mapping[str, Any],
        *,
        index: int,
        previous: str | None,
        root: Path,
    ) -> dict[str, Any]:
        source_kind = str(source["event_kind"])
        event_kind = "E_DIRECT_FETCH_REQUEST" if source_kind == "E_FETCH_RETRY" else source_kind
        payload = source.get("payload")
        if not isinstance(payload, Mapping):
            payload = {}
        event: dict[str, Any] = {
            "event_kind": event_kind,
            "event_index": index,
            "previous_event_sha256": previous,
            "event_sha256": "0" * 64,
            "phase_id": self.inputs.integration_run_spec["phase_id"],
            "run_id": self.inputs.integration_run_spec["run_id"],
            "producer": "vietnamese_attestation_e",
            "issued_at": source["created_at"],
        }
        candidate_id = payload.get("candidate_id") or source.get("candidate_replicate_id")
        candidate = self._candidates.get(str(candidate_id))
        if candidate is not None:
            event["candidate_id"] = candidate["candidate_id"]
            event["candidate_version"] = candidate["candidate_version"]
            event["sense_id"] = candidate["sense_id"]
            event["candidate_replicate_id"] = source.get("candidate_replicate_id")

        if event_kind in _PHYSICAL_EVENTS:
            self._add_physical_fields(event, source=source, payload=payload, root=root)
        elif event_kind == "E_REDIRECT_HOP":
            event["redirect_from_sha256"] = payload.get("redirect_from_sha256")
            event["redirect_to_sha256"] = payload.get("redirect_to_sha256")
        elif event_kind == "E_SOURCE_DOCUMENT_ACCEPTED":
            event["document_id"] = payload.get("document_id")
            event["registry_source_id"] = payload.get("registry_source_id") or payload.get(
                "source_id"
            )
            event["content_sha256"] = payload.get("content_sha256")
            event["normalized_text_sha256"] = payload.get(
                "normalized_text_sha256", payload.get("content_sha256")
            )
        elif event_kind == "BUDGET_WARNING":
            event["budget_dimension"] = payload.get("budget_dimension") or payload.get("code")
        elif event_kind == "STOP_EVENT":
            event["stop_reason"] = payload.get("code") or payload.get("message") or str(
                source.get("failure_disposition")
            )
        return event

    def _add_physical_fields(
        self,
        event: dict[str, Any],
        *,
        source: Mapping[str, Any],
        payload: Mapping[str, Any],
        root: Path,
    ) -> None:
        retry_index = int(payload.get("retry_index", 0))
        event.update(
            {
                "semantic_role": source.get("semantic_role"),
                "semantic_call_id": source.get("semantic_call_id"),
                "transport_attempt_id": source.get("transport_attempt_id"),
                "transport_retry_id": (
                    f"retry-{retry_index}" if retry_index > 0 else None
                ),
                "retry_of": source.get("retry_of"),
                "provider_request_id_internal": source.get("transport_attempt_id"),
                "provider_request_id": payload.get("provider_request_id"),
                "provider": payload.get("provider_id"),
                "rate_window_id": f"{event['run_id']}:{event['phase_id']}",
                "request_duration_seconds": float(payload.get("latency_ms", 0)) / 1000.0,
                "failure_disposition": _failure_disposition(source, payload),
                "usage": _draft4_usage(
                    source.get("usage"),
                    network_request_count=int(payload.get("network_request_count", 0)),
                    token_accounting_authority_sha256=self.inputs.token_accounting.authority[
                        "integrity"
                    ]["self_sha256"],
                ),
            }
        )
        if event["event_kind"] in _MODEL_EVENTS:
            event["model_identifier"] = payload.get("model_id")
            event["request_sha256"] = payload.get("request_sha256")
            event["response_artifact"] = _response_artifact(root, payload)
        elif event["event_kind"] == "E_DISCOVERY_QUERY":
            event["query_sha256"] = payload.get("query_sha256") or payload.get(
                "rendered_query_sha256"
            )
            event["response_artifact"] = _response_artifact(root, payload)
        elif event["event_kind"] == "E_DIRECT_FETCH_REQUEST":
            event["canonical_url"] = payload.get("canonical_url")
            event["response_artifact"] = _response_artifact(root, payload)


def _draft4_usage(
    usage: Any,
    *,
    network_request_count: int,
    token_accounting_authority_sha256: str,
) -> dict[str, Any]:
    if not isinstance(usage, Mapping):
        usage = {}
    return {
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "reasoning_tokens": int(usage.get("reasoning_tokens", 0)),
        "cached_input_tokens": 0,
        "total_tokens": int(usage.get("total_tokens", 0)),
        "download_bytes": 0,
        "network_request_count": network_request_count,
        "cost": None,
        "currency": None,
        "usage_status": "TOKEN_ONLY_COST_UNAVAILABLE",
        "token_accounting_authority_sha256": token_accounting_authority_sha256,
    }


def _failure_disposition(
    source: Mapping[str, Any], payload: Mapping[str, Any]
) -> str:
    outcome = str(payload.get("outcome", "SUCCESS"))
    if outcome == "SUCCESS" and source.get("failure_disposition") in {None, "NONE"}:
        return "ACCEPTED"
    if outcome in {"RETRYABLE_FAILURE", "UNKNOWN_PHYSICAL_OUTCOME"}:
        return "TRANSPORT_FAILURE"
    if outcome == "TERMINAL_FAILURE":
        return "PROVIDER_REJECTED"
    return "EXTERNAL_HOLD"


def _response_artifact(root: Path, payload: Mapping[str, Any]) -> dict[str, Any] | None:
    raw_ref = payload.get("raw_response_locator")
    if not isinstance(raw_ref, str) or not raw_ref:
        return None
    ref, _ = canonical_relative_ref(raw_ref)
    path = root.joinpath(*ref.split("/"))
    try:
        reject_link(path)
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
        reject_link(resolved)
    except (OSError, ValueError) as exc:
        raise LiveSchemaError("Draft4 response artifact path is unsafe") from exc
    if not resolved.is_file():
        raise LiveSchemaError("Draft4 response artifact is not a regular file")
    raw = resolved.read_bytes()
    physical = hashlib.sha256(raw).hexdigest()
    claimed = payload.get("response_physical_sha256")
    if claimed is not None and claimed != physical:
        raise LiveSchemaError("Draft4 response artifact physical hash mismatch")
    return {
        "artifact_id": f"response-{physical[:24]}",
        "artifact_path": ref,
        "physical_sha256": physical,
        "byte_length": len(raw),
        "media_type": "application/json",
    }


def _sum_usage(usages: Sequence[Mapping[str, Any]], key: str) -> int:
    return sum(int(usage[key] or 0) for usage in usages)


def _artifact_root(path: str | Path) -> Path:
    supplied = Path(path).absolute()
    try:
        reject_link(supplied)
        resolved = supplied.resolve(strict=True)
        reject_link(resolved)
    except (OSError, ValueError) as exc:
        raise LiveSchemaError("Draft4 artifact root is unsafe or missing") from exc
    if not resolved.is_dir():
        raise LiveSchemaError("Draft4 artifact root must be a directory")
    return resolved


__all__ = [
    "DRAFT4_SCHEMA_VERSION",
    "Draft4LifecycleAdapter",
    "EXTERNAL_HOLD_PRICE_TABLE_SHA256",
]
