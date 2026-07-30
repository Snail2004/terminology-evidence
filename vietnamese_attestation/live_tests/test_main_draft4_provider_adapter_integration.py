from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import pytest

from vietnamese_attestation.v1.live.authority_adapter.e05 import (
    DRAFT4_COMMIT,
    DRAFT4_TREE,
    E05_BASE_COMMIT,
    E05_BASE_TREE,
    E05_DELIVERY_SHA256,
    load_e05_exact_integration_inputs,
    validate_e05_protocol_instance,
)
from vietnamese_attestation.v1.live.common import (
    LiveSchemaError,
    canonical_bytes,
    canonical_sha256,
)
from vietnamese_attestation.v1.live.protocol_adapter import Draft4LifecycleAdapter
from vietnamese_attestation.v1.live.judge import (
    make_judge_request,
    make_judge_response,
)
from vietnamese_attestation.v1.live.ledger import EventLedger
from vietnamese_attestation.v1.live.provider_adapters.gemini_official import (
    GEMINI_MODEL_ID,
    GEMINI_PROVIDER_ID,
    GeminiOfficialAdapter,
    GeminiUnknownPhysicalOutcome,
)
from vietnamese_attestation.v1.live.provider_adapters.token_accounting import (
    MAIN_GENERATION_CONTRACT_SELF_SHA256,
    MAIN_TOKEN_AUTHORITY_SELF_SHA256,
    TOKEN_ONLY_COST_UNAVAILABLE,
    canonical_generation_config,
    load_main_token_accounting_authority,
    make_recorded_token_accounting_authority,
)


DEFAULT_DELIVERY = Path(
    r"C:\work\terminology-evidence-artifacts\e05-exact-integration-input-v1\delivery.zip"
)
DEFAULT_TOKEN_PACKAGE = Path(
    r"C:\work\terminology-evidence-artifacts\D0_API_Execution_Plan_Operations_V1\main-token-accounting-v1\release\build-a.zip"
)


def test_exact_main_delivery_anchor_bindings_and_holds() -> None:
    inputs = _inputs()
    assert inputs.delivery_path == _delivery().resolve()
    assert inputs.main_profile["integrity"]["self_sha256"] == (
        "3f81ea9200c5d125602a286876baf25ac9ffb44ac8052e99e32f7fe8a0f89796"
    )
    assert inputs.profile_anchor["status"] == (
        "MAIN_SI_UNIFIED_AUTHORITY_PROFILE_ACCEPTED_ZERO_PROVIDER_NOT_LIVE"
    )
    assert inputs.integration_run_spec["e_integration_base"] == {
        "commit": E05_BASE_COMMIT,
        "review_package_sha256": (
            "7e97342fb634571345d5893ad0aab5abaa59977f0ceea67fff0650489033e2a7"
        ),
        "tree": E05_BASE_TREE,
    }
    assert inputs.integration_run_spec["draft4"]["commit"] == DRAFT4_COMMIT
    assert inputs.integration_run_spec["draft4"]["tree"] == DRAFT4_TREE
    assert set(inputs.protocol_schemas) == {
        "LIVE_AUTHORIZATION_RECEIPT",
        "LIVE_LEDGER_EVENT",
        "RUN_START_RECEIPT",
        "RUN_STOP_RECEIPT",
        "USAGE_SNAPSHOT",
    }
    assert inputs.authorization_receipt["authorization_status"] == "SYNTHETIC_TEST_ONLY"
    assert inputs.authorization_receipt["test_only"] is True
    assert "bindings" in inputs.authorization_receipt
    assert "e_execution_binding" not in inputs.authorization_receipt
    assert inputs.live_execution_authorized is False
    with pytest.raises(LiveSchemaError, match="zero-provider integration authority only"):
        inputs.require_live_execution_authority()


def test_exact_main_delivery_rejects_tamper_without_caller_hash_override(
    tmp_path: Path,
) -> None:
    raw = bytearray(_delivery().read_bytes())
    raw[-1] ^= 0x01
    tampered = tmp_path / "self-issued-delivery.zip"
    tampered.write_bytes(raw)
    with pytest.raises(LiveSchemaError, match="physical SHA-256 mismatch"):
        load_e05_exact_integration_inputs(tampered)
    assert E05_DELIVERY_SHA256 not in str(
        {"path": tampered, "caller_expected_hash": hashlib.sha256(raw).hexdigest()}
    )


def test_exact_provider_plan_authorizes_only_gemini_official() -> None:
    plan = _inputs().provider_role_plan
    assert {row["provider_id"] for row in plan["roles"]} == {GEMINI_PROVIDER_ID}
    assert {row["model_id"] for row in plan["roles"]} == {GEMINI_MODEL_ID}
    assert all(row["generation_config"] == {"temperature": 0, "reasoning": "none"} for row in plan["roles"])
    assert all(row["max_retries"] == 1 for row in plan["roles"])
    serialized = json.dumps(plan, sort_keys=True)
    assert "shopai" not in serialized.casefold()
    assert "ckey" not in serialized.casefold()


def test_exact_main_token_accounting_package_and_generation_contract() -> None:
    token = load_main_token_accounting_authority(DEFAULT_TOKEN_PACKAGE)
    assert token.authority["integrity"]["self_sha256"] == MAIN_TOKEN_AUTHORITY_SELF_SHA256
    assert token.generation_contract["integrity"]["self_sha256"] == MAIN_GENERATION_CONTRACT_SELF_SHA256
    assert token.authority["unknown_cost_representation"] == {
        "cost": None,
        "cost_status": TOKEN_ONLY_COST_UNAVAILABLE,
        "currency": None,
    }
    assert token.anchor["run_authorized"] is False


def test_exact_main_token_accounting_package_rejects_tamper(tmp_path: Path) -> None:
    raw = bytearray(DEFAULT_TOKEN_PACKAGE.read_bytes())
    raw[-1] ^= 1
    path = tmp_path / "token-accounting-self-issued.zip"
    path.write_bytes(raw)
    with pytest.raises(LiveSchemaError, match="physical SHA-256 mismatch"):
        load_main_token_accounting_authority(path)


def test_exact_draft4_authorization_rejects_legacy_e_execution_binding() -> None:
    inputs = _inputs()
    drifted = copy.deepcopy(inputs.authorization_receipt)
    drifted["e_execution_binding"] = {}
    with pytest.raises(LiveSchemaError, match="Additional properties"):
        validate_e05_protocol_instance(
            inputs,
            role="LIVE_AUTHORIZATION_RECEIPT",
            value=drifted,
        )


def test_exact_draft4_ledger_rejects_internal_event_shape() -> None:
    inputs = _inputs()
    internal = {
        "schema_id": "ELiveLedgerEventV1",
        "schema_version": "1.0.0",
        "event_kind": "STOP_EVENT",
        "event_index": 0,
        "previous_event_sha256": "0" * 64,
        "event_sha256": "1" * 64,
        "phase_id": "D0_ONE_CANDIDATE",
        "run_id": "RUN-D0",
        "created_at": "2026-07-30T10:00:00Z",
        "payload": {"code": "HOLD"},
    }
    with pytest.raises(LiveSchemaError, match="Additional properties"):
        validate_e05_protocol_instance(
            inputs,
            role="LIVE_LEDGER_EVENT",
            value=internal,
        )


def test_draft4_event_usage_and_lifecycle_projection(tmp_path: Path) -> None:
    inputs = _inputs()
    candidate = inputs.candidate_set["ordered_candidates"][0]
    raw_root = tmp_path / "run"
    response = make_judge_response(
        concept_relation="SAME",
        domain_relation="MATCH",
        usage_type="TECHNICAL_TERM",
        judgeability="JUDGEABLE",
        evidence_span="mạng nơ-ron",
        reason_codes=["RECORDED_CONFORMANCE"],
        reason="Recorded E-05 conformance response",
    )
    response_raw = canonical_bytes(response)
    response_sha = hashlib.sha256(response_raw).hexdigest()
    response_path = raw_root / "raw_responses" / f"{response_sha}.json"
    response_path.parent.mkdir(parents=True)
    response_path.write_bytes(response_raw)
    ledger = EventLedger(
        run_id="RUN-D0",
        phase_id="D0_ONE_CANDIDATE",
        clock=lambda: "2026-07-30T10:00:00Z",
    )
    primary = _role(inputs.provider_role_plan, "PRIMARY_ATTESTATION_JUDGE")
    ledger.append_model_request(
        candidate_id=candidate["candidate_id"],
        sense_id=candidate["sense_id"],
        semantic_call_id="semantic-call-1",
        provider_request_id="gemini-recorded-request-1",
        provider_id=primary["provider_id"],
        model_id=primary["model_id"],
        route=primary["semantic_role"],
        prompt_sha256=primary["prompt_sha256"],
        request_sha256="1" * 64,
        response_sha256=canonical_sha256(response),
        response_physical_sha256=response_sha,
        raw_response_locator=f"raw_responses/{response_sha}.json",
        generation_config=canonical_generation_config(),
        generation_contract_sha256=MAIN_GENERATION_CONTRACT_SELF_SHA256,
        token_accounting_authority_sha256=MAIN_TOKEN_AUTHORITY_SELF_SHA256,
        provider_role_plan_sha256=inputs.provider_role_plan["integrity"]["self_sha256"],
        outcome="SUCCESS",
        latency_ms=25,
        physical_request_count=1,
        started_at="2026-07-30T10:00:00.000Z",
        completed_at="2026-07-30T10:00:00.025Z",
        usage={
            "input_tokens": 10,
            "output_tokens": 5,
            "reasoning_tokens": 2,
            "total_tokens": 17,
            "cost": None,
            "currency": None,
            "cost_status": TOKEN_ONLY_COST_UNAVAILABLE,
        },
    )
    adapter = Draft4LifecycleAdapter(inputs)
    events = adapter.adapt_events(ledger.events, artifact_root=raw_root)
    assert len(events) == 1
    assert events[0]["event_kind"] == "E_MODEL_REQUEST"
    assert events[0]["event_index"] == 1
    assert events[0]["previous_event_sha256"] is None
    assert events[0]["candidate_version"] == candidate["candidate_version"]
    assert events[0]["provider"] == GEMINI_PROVIDER_ID
    usage = adapter.make_usage_snapshot(events)
    assert usage["totals"]["physical_requests"] == 1
    assert usage["totals"]["total_tokens"] == 17
    assert usage["totals"]["network_requests"] == 0
    assert usage["totals"]["cost"] is None
    assert usage["currency"] is None
    start = adapter.make_run_start_receipt(
        issued_at="2026-07-30T10:00:00Z"
    )
    stop = adapter.make_run_stop_receipt(
        run_start_receipt=start,
        events=events,
        usage_snapshot=usage,
        preserved_artifact_manifest_sha256=canonical_sha256(
            {"artifacts": ["raw_responses"]}
        ),
        issued_at="2026-07-30T10:00:01Z",
        terminal_status="COMPLETED",
        stop_reason="ZERO_PROVIDER_RECORDED_CONFORMANCE_COMPLETE",
    )
    validate_e05_protocol_instance(inputs, role="RUN_START_RECEIPT", value=start)
    validate_e05_protocol_instance(inputs, role="USAGE_SNAPSHOT", value=usage)
    validate_e05_protocol_instance(inputs, role="RUN_STOP_RECEIPT", value=stop)
    assert stop["final_ledger_head_sha256"] == events[-1]["event_sha256"]


def test_unknown_outcome_stop_event_is_exact_draft4_ledger_variant(
    tmp_path: Path,
) -> None:
    inputs = _inputs()
    candidate = inputs.candidate_set["ordered_candidates"][0]
    root = tmp_path / "run"
    root.mkdir()
    ledger = EventLedger(
        run_id="RUN-D0",
        phase_id="D0_ONE_CANDIDATE",
        clock=lambda: "2026-07-30T10:00:00Z",
    )
    ledger.append(
        "STOP_EVENT",
        candidate_replicate_id=candidate["candidate_id"],
        semantic_role="CONTROL",
        semantic_call_id="semantic-call-unknown",
        transport_attempt_id="gemini-unknown-request",
        failure_disposition="UNKNOWN_PHYSICAL_OUTCOME",
        payload={
            "code": "UNKNOWN_PHYSICAL_OUTCOME",
            "message": "ambiguous physical outcome",
            "details": {},
        },
    )
    event = Draft4LifecycleAdapter(inputs).adapt_events(
        ledger.events, artifact_root=root
    )[0]
    assert event["event_kind"] == "STOP_EVENT"
    assert event["stop_reason"] == "UNKNOWN_PHYSICAL_OUTCOME"
    assert set(event).isdisjoint({"schema_id", "schema_version", "payload", "created_at"})


def test_gemini_adapter_success_uses_exact_route_and_redacts_credential() -> None:
    inputs = _inputs()
    request = _judge_request(inputs, "PRIMARY_ATTESTATION_JUDGE")
    response = _judge_response()
    transport = RecordedTransport(
        [
            _exchange(
                status_code=200,
                request_id="gemini-provider-request-1",
                body=_gemini_body(response),
            )
        ]
    )
    adapter = GeminiOfficialAdapter(
        role_plan=inputs.provider_role_plan,
        api_key="recorded-secret-google",
        token_accounting_authority=make_recorded_token_accounting_authority(),
        transport=transport,
    )
    result = adapter.invoke(
        request,
        role_config=_role(inputs.provider_role_plan, "PRIMARY_ATTESTATION_JUDGE"),
    )
    assert result["outcome"] == "SUCCESS"
    assert result["provider_request_id"] == "gemini-provider-request-1"
    assert result["total_tokens"] == 17
    assert result["reasoning_tokens"] == 2
    assert result["cost"] is None
    assert result["currency"] is None
    assert result["cost_status"] == TOKEN_ONLY_COST_UNAVAILABLE
    assert result["network_request_count"] == 0
    assert transport.calls[0]["url"].endswith(
        "/models/gemini-3.5-flash:generateContent"
    )
    assert transport.calls[0]["headers"]["x-goog-api-key"] == "recorded-secret-google"
    generation = transport.calls[0]["payload"]["generationConfig"]
    assert generation["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert set(generation).isdisjoint(
        {"temperature", "top_p", "topP", "top_k", "topK", "thinkingBudget"}
    )
    assert "recorded-secret-google" not in repr(adapter)
    assert "recorded-secret-google" not in json.dumps(result, sort_keys=True)


def test_gemini_adapter_known_retry_is_bounded_to_one() -> None:
    inputs = _inputs()
    request = _judge_request(inputs, "PRIMARY_ATTESTATION_JUDGE")
    transport = RecordedTransport(
        [
            _exchange(status_code=429, request_id="gemini-retry-1", body={}),
            _exchange(
                status_code=200,
                request_id="gemini-success-2",
                body=_gemini_body(_judge_response()),
            ),
        ]
    )
    adapter = _gemini_adapter(inputs, transport)
    role = _role(inputs.provider_role_plan, "PRIMARY_ATTESTATION_JUDGE")
    first = adapter.invoke(request, role_config=role)
    second = adapter.invoke(request, role_config=role)
    assert first["outcome"] == "RETRYABLE_FAILURE"
    assert first["retry_index"] == 0
    assert second["outcome"] == "SUCCESS"
    assert second["retry_index"] == 1
    with pytest.raises(LiveSchemaError, match="retry budget exceeded"):
        adapter.invoke(request, role_config=role)
    assert len(transport.calls) == 2


def test_gemini_adapter_unknown_physical_outcome_never_retries_implicitly() -> None:
    inputs = _inputs()
    transport = UnknownTransport()
    adapter = _gemini_adapter(inputs, transport)
    result = adapter.invoke(
        _judge_request(inputs, "PRIMARY_ATTESTATION_JUDGE"),
        role_config=_role(inputs.provider_role_plan, "PRIMARY_ATTESTATION_JUDGE"),
    )
    assert result["outcome"] == "UNKNOWN_PHYSICAL_OUTCOME"
    assert result["retry_index"] == 0
    assert transport.calls == 1


def test_gemini_real_transport_requires_exact_main_token_authority() -> None:
    inputs = _inputs()
    with pytest.raises(LiveSchemaError, match="exact Main token-accounting authority"):
        GeminiOfficialAdapter(
            role_plan=inputs.provider_role_plan,
            api_key="never-used-secret",
            token_accounting_authority=make_recorded_token_accounting_authority(),
        )


def test_gemini_real_transport_accepts_pinned_authority_without_calling_network() -> None:
    inputs = _inputs()
    adapter = GeminiOfficialAdapter(
        role_plan=inputs.provider_role_plan,
        api_key="never-used-secret",
        token_accounting_authority=load_main_token_accounting_authority(
            DEFAULT_TOKEN_PACKAGE
        ),
    )
    assert adapter.zero_network is False


def test_gemini_missing_provider_request_id_is_terminal() -> None:
    inputs = _inputs()
    exchange = _exchange(
        status_code=200,
        request_id="temporary",
        body=_gemini_body(_judge_response()),
    )
    exchange["headers"] = {}
    exchange["body"].pop("responseId")
    result = _gemini_adapter(inputs, RecordedTransport([exchange])).invoke(
        _judge_request(inputs, "PRIMARY_ATTESTATION_JUDGE"),
        role_config=_role(inputs.provider_role_plan, "PRIMARY_ATTESTATION_JUDGE"),
    )
    assert result["outcome"] == "TERMINAL_FAILURE"
    assert result["response"] is None


@pytest.mark.parametrize("failure", ["malformed", "missing_usage", "token_total_drift"])
def test_gemini_adapter_rejects_malformed_or_usage_drift(failure: str) -> None:
    inputs = _inputs()
    body = _gemini_body(_judge_response())
    if failure == "malformed":
        body["candidates"][0]["content"]["parts"][0]["text"] = "{not-json"
    elif failure == "missing_usage":
        body.pop("usageMetadata")
    else:
        body["usageMetadata"]["totalTokenCount"] = 18
    adapter = _gemini_adapter(
        inputs,
        RecordedTransport(
            [_exchange(status_code=200, request_id="gemini-invalid", body=body)]
        ),
    )
    result = adapter.invoke(
        _judge_request(inputs, "PRIMARY_ATTESTATION_JUDGE"),
        role_config=_role(inputs.provider_role_plan, "PRIMARY_ATTESTATION_JUDGE"),
    )
    assert result["outcome"] == "TERMINAL_FAILURE"
    assert result["response"] is None


def test_gemini_adapter_rejects_route_model_and_generation_drift() -> None:
    inputs = _inputs()
    request = _judge_request(inputs, "PRIMARY_ATTESTATION_JUDGE")
    transport = RecordedTransport([])
    adapter = _gemini_adapter(inputs, transport)
    exact = _role(inputs.provider_role_plan, "PRIMARY_ATTESTATION_JUDGE")
    for key, value in (
        ("provider_id", "ckey"),
        ("model_id", "another-model"),
        ("generation_config", {"temperature": 0.1, "reasoning": "none"}),
    ):
        drifted = copy.deepcopy(exact)
        drifted[key] = value
        with pytest.raises(LiveSchemaError, match="differs from the exact E-05 plan"):
            adapter.invoke(request, role_config=drifted)
    assert transport.calls == []


class RecordedTransport:
    networked = False

    def __init__(self, exchanges: list[Mapping[str, Any]]) -> None:
        self.exchanges = [dict(row) for row in exchanges]
        self.calls: list[dict[str, Any]] = []

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "payload": copy.deepcopy(payload),
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self.exchanges:
            raise AssertionError("unexpected recorded transport call")
        return self.exchanges.pop(0)


class UnknownTransport:
    networked = False

    def __init__(self) -> None:
        self.calls = 0

    def post_json(self, **_: Any) -> Mapping[str, Any]:
        self.calls += 1
        raise GeminiUnknownPhysicalOutcome(
            "recorded timeout after send",
            started_at="2026-07-30T10:00:00.000Z",
            completed_at="2026-07-30T10:00:00.025Z",
            provider_request_id="gemini-unknown-physical-1",
        )


def _delivery() -> Path:
    configured = os.environ.get("E05_EXACT_INPUT_DELIVERY")
    path = Path(configured) if configured else DEFAULT_DELIVERY
    if not path.is_file():
        raise RuntimeError(
            "Set E05_EXACT_INPUT_DELIVERY to the exact Main delivery ZIP"
        )
    return path


def _inputs():
    return load_e05_exact_integration_inputs(_delivery())


def _role(plan: Mapping[str, Any], name: str) -> dict[str, Any]:
    return next(dict(row) for row in plan["roles"] if row["semantic_role"] == name)


def _judge_request(inputs, role: str) -> dict[str, Any]:
    candidate = inputs.candidate_set["ordered_candidates"][0]
    return make_judge_request(
        candidate_id=candidate["candidate_id"],
        sense_id=candidate["sense_id"],
        evidence_id="evidence-recorded-1",
        term_en="neural network",
        candidate_vi="mạng nơ-ron",
        sense_definition="A connected computational model.",
        snippet_original="Mạng nơ-ron được huấn luyện trên dữ liệu.",
        snippet_masked="[TERM] được huấn luyện trên dữ liệu.",
        source_id="recorded-source-1",
        source_tier="A",
        semantic_role=role,
    )


def _judge_response() -> dict[str, Any]:
    return make_judge_response(
        concept_relation="SAME",
        domain_relation="MATCH",
        usage_type="TECHNICAL_TERM",
        judgeability="JUDGEABLE",
        evidence_span="Mạng nơ-ron",
        reason_codes=["RECORDED_CONFORMANCE"],
        reason="The snippet uses the candidate as the requested technical concept.",
    )


def _gemini_body(response: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "responseId": "gemini-body-request-id",
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                response,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                        }
                    ]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
            "thoughtsTokenCount": 2,
            "totalTokenCount": 17,
        },
    }


def _exchange(
    *, status_code: int, request_id: str, body: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "status_code": status_code,
        "headers": {"x-goog-request-id": request_id},
        "body": dict(body),
        "started_at": "2026-07-30T10:00:00.000Z",
        "completed_at": "2026-07-30T10:00:00.025Z",
    }


def _gemini_adapter(inputs, transport):
    return GeminiOfficialAdapter(
        role_plan=inputs.provider_role_plan,
        api_key="recorded-secret-google",
        token_accounting_authority=make_recorded_token_accounting_authority(),
        transport=transport,
    )
