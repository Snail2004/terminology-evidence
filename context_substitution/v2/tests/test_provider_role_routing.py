from __future__ import annotations

import hashlib
import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from context_substitution.v2.jsonio import StrictJSONError, loads_strict
from context_substitution.v2.providers.base import (
    ContextExecutionError,
    ContextProviderRoute,
    ProviderRawResponse,
)
from context_substitution.v2.providers.role_plan import (
    DEFAULT_PROVIDER_ROLE_PLAN_PATH,
    ProviderRolePlan,
    load_provider_role_plan,
    reject_protected_provider_overrides,
    validate_provider_role_plan,
)
from context_substitution.v2.providers.role_routing import (
    RoleRoutedStructuredModel,
    _unwrap_complete_outer_json_fence,
)
from context_substitution.v2.providers.ledger import ProviderResponseLedger
from context_substitution.v2.dataset.reviewed_support import (
    reviewed_support_to_context_substitution_input,
)
from context_substitution.v2.integration.fake_provider import (
    _FakeSenderFactory,
    _SCENARIOS,
)
from context_substitution.v2.integration.replay import replay_context_run
from context_substitution.v2.runtime.engine import (
    audit_candidate_profile,
    blind_model_candidate_profile,
    run_d2l_context_substitution,
)
from context_substitution.v2.runtime.pairwise import _pairwise_candidate


ROOT = Path(__file__).resolve().parents[3]
PILOT = ROOT / "dataset" / "pilot_dev_only_v1_1"
V3 = ROOT / "dataset" / "d2l_context_support_set_validation_ready_v3"


def test_role_plan_seals_reviewed_matrix_and_ckey_primary() -> None:
    plan = _plan()
    assert plan.candidate_replicate_cap == 1
    assert plan.role("trial_translator").route_profile_order == (
        "gateway_gpt_5_6_luna_none",
    )
    assert plan.role("secondary_context_judge").escalation_kind == (
        "SECONDARY_JUDGE_ESCALATION"
    )
    assert plan.role("pairwise_tiebreaker").escalation_kind == (
        "HARD_CASE_ESCALATION"
    )
    for role in (
        "context_selector",
        "trial_translation_quality_gate",
        "context_judge",
        "contrastive_sense_judge",
    ):
        assert plan.role(role).route_profile_order == (
            "ckey_gemini_3_5_flash_low",
            "shopapi_gemini_3_5_flash_low",
        )


def test_role_plan_rejects_physical_hash_and_semantic_environment_drift() -> None:
    with pytest.raises(ValueError, match="physical SHA256 mismatch"):
        load_provider_role_plan(
            DEFAULT_PROVIDER_ROLE_PLAN_PATH,
            expected_physical_sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="semantic overrides"):
        reject_protected_provider_overrides(
            {"CST_PROVIDER_CKEY_MODEL": "different-model"}
        )
    reject_protected_provider_overrides(
        {"CST_CREDENTIALS_ROOT": "C:/redacted"}
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["route_profiles"][
            "shopapi_gemini_3_5_flash_low"
        ].__setitem__("model_family", "gpt-5.6"),
        lambda value: value["roles"]["context_judge"][
            "route_profile_order"
        ].append("gateway_gpt_5_6_luna_none"),
        lambda value: value["roles"]["trial_translator"].__setitem__(
            "escalation_kind", "SECONDARY_JUDGE_ESCALATION"
        ),
    ],
)
def test_role_plan_rejects_cross_family_or_escalation_drift(mutation: Any) -> None:
    value = json.loads(DEFAULT_PROVIDER_ROLE_PLAN_PATH.read_text(encoding="utf-8"))
    mutation(value)
    _reseal_plan(value)
    with pytest.raises(ValueError):
        validate_provider_role_plan(value)


def test_equivalent_failover_retries_ckey_then_uses_shopapi_only() -> None:
    senders = _senders(
        ckey=[TimeoutError("timeout"), TimeoutError("timeout")],
        shop=[_ok()],
    )
    model = _model(senders)
    result, provenance = _call(model, "context_judge")
    assert result == {"ok": True}
    assert provenance["provider_route_id"] == "shopaikey_gemini"
    assert [row["provider_route_id"] for row in model.attempted_calls] == [
        "ckey_gemini",
        "ckey_gemini",
        "shopaikey_gemini",
    ]
    assert [row["failure_disposition"] for row in model.attempted_calls] == [
        "RETRY_SAME_ROUTE",
        "EQUIVALENT_FAILOVER",
        "ACCEPTED",
    ]
    assert model.attempted_calls[-1]["equivalent_failover_from"] == "ckey_gemini"
    assert all(
        row["role_equivalence_group"] == "gemini-3.5-flash-low-v1"
        for row in model.attempted_calls
    )
    assert set(senders["ckey"].system_prompts) == set(senders["shop"].system_prompts)
    assert "thinking_level=LOW" in senders["shop"].system_prompts[0]
    assert senders["local"].calls == 0


def test_unknown_provider_outcome_is_recorded_then_hard_stops() -> None:
    senders = _senders(ckey=[RuntimeError("unknown physical outcome")])
    model = _model(senders)
    with pytest.raises(ContextExecutionError, match="ambiguous provider outcome"):
        _call(model, "context_judge")
    assert len(model.attempted_calls) == 1
    row = model.attempted_calls[0]
    assert row["failure_disposition"] == "HARD_STOP"
    assert row["safe_error_code"] == "RUNTIMEERROR"
    assert senders["shop"].calls == 0
    assert senders["local"].calls == 0


def test_single_complete_json_fence_is_unwrapped_after_raw_capture(
    tmp_path: Path,
) -> None:
    response_text = " \r\n```json\r\n{\"ok\":true}\r\n```\t\r\n"
    senders = _senders(
        ckey=[ProviderRawResponse(text=response_text, payload=None)]
    )
    ledger_root = tmp_path / "ledger"
    model = _model(
        senders,
        response_ledger=ProviderResponseLedger(ledger_root),
    )

    result, _ = _call(model, "context_judge")

    assert result == {"ok": True}
    attempt = model.attempted_calls[0]
    assert attempt["raw_response_sha256"] == hashlib.sha256(
        response_text.encode("utf-8")
    ).hexdigest()
    assert (ledger_root / attempt["raw_response_ref"]).read_bytes() == (
        response_text.encode("utf-8")
    )


@pytest.mark.parametrize(
    "response_text",
    [
        "prose\n```json\n{\"ok\":true}\n```",
        "```json\n{\"ok\":true}\n```\ntrailing",
        "```json\n{\"ok\":true}\n```\n```json\n{\"ok\":true}\n```",
        "```json\n{\"ok\":true}",
        "```json\n{\"nested\":{\"value\":1,\"value\":2}}\n```",
        "```json\n{\"value\":NaN}\n```",
        "```json\n{\"value\":Infinity}\n```",
    ],
)
def test_fenced_json_normalization_remains_fail_closed(
    response_text: str,
) -> None:
    with pytest.raises(StrictJSONError):
        loads_strict(
            _unwrap_complete_outer_json_fence(response_text),
            source="provider:test",
            require_object=True,
        )


def test_cross_family_roles_are_explicit_and_generation_bound() -> None:
    model = _model(_senders(local=[_ok(), _ok()]))
    _call(model, "secondary_context_judge")
    _call(model, "pairwise_tiebreaker")
    secondary, hard_case = model.attempted_calls
    assert secondary["model_profile"] == "TERRA"
    assert secondary["effective_generation_config"]["reasoning_effort"] == "low"
    assert secondary["escalation_kind"] == "SECONDARY_JUDGE_ESCALATION"
    assert hard_case["model_profile"] == "TERRA"
    assert hard_case["effective_generation_config"]["reasoning_effort"] == "medium"
    assert hard_case["escalation_kind"] == "HARD_CASE_ESCALATION"


@pytest.mark.parametrize(
    ("sense_count", "candidate_count", "expected_requests"),
    [(1, 1, 5), (1, 3, 13), (5, 15, 65)],
)
def test_zero_provider_happy_path_request_counts_are_exact(
    sense_count: int,
    candidate_count: int,
    expected_requests: int,
) -> None:
    model = _model(_senders(default_success=True))
    for _ in range(sense_count):
        _call(model, "context_selector")
    for _ in range(candidate_count):
        _call(model, "trial_translator")
        _call(model, "trial_translation_quality_gate")
        _call(model, "context_judge")
        _call(model, "contrastive_sense_judge")
    assert len(model.attempted_calls) == expected_requests
    assert [row["provider_request_index"] for row in model.attempted_calls] == list(
        range(1, expected_requests + 1)
    )
    assert all(row["candidate_replicate_index"] == 0 for row in model.attempted_calls)


def test_regeneration_secondary_hard_case_and_transport_counts_are_separate() -> None:
    senders = _senders(
        ckey=[_ok(), _ok(), ProviderRawResponse(text="{", payload=None), _ok()],
        local=[_ok(), _ok(), _ok(), _ok()],
        shop=[_ok()],
    )
    model = _model(senders)
    _call(model, "trial_translator")
    _call(model, "trial_translation_quality_gate")
    _call(model, "trial_translator")
    _call(model, "trial_translation_quality_gate")
    _call(model, "context_judge")
    _call(model, "secondary_context_judge")
    _call(model, "pairwise_tiebreaker")
    assert len(model.attempted_calls) == 8
    assert sum(row["role"] == "trial_translator" for row in model.attempted_calls) == 2
    assert sum(row["role"] == "trial_translation_quality_gate" for row in model.attempted_calls) == 2
    assert sum(row["failure_disposition"] == "RETRY_SAME_ROUTE" for row in model.attempted_calls) == 1
    assert sum(row["escalation_kind"] is not None for row in model.attempted_calls) == 2


def test_model_prompt_profile_is_blind_but_audit_profile_retains_lineage() -> None:
    candidate = {
        "candidate_id": "candidate-1",
        "source_term": "framework",
        "candidate_translation": "khung phần mềm",
        "sense_id": "sense-1",
        "scope_id": "scope-1",
        "sense_contract": {"definition_en": "x"},
        "part_of_speech": "noun",
        "source_occurrences": [],
        "candidate_generation": {
            "formation_method": "MODEL_GENERATED",
            "candidate_slot_id": "C1",
            "run_id": "generation-run",
        },
    }
    blind = blind_model_candidate_profile(candidate)
    audit = audit_candidate_profile(candidate)
    assert "candidate_generation" not in blind
    assert "candidate_generation" not in _pairwise_candidate(candidate)
    assert audit["candidate_generation"] == candidate["candidate_generation"]


def test_full_five_sense_role_bound_run_validates_and_replays_zero_provider(
    tmp_path: Path,
) -> None:
    if not PILOT.exists() or not V3.exists():
        pytest.skip("external pilot dataset is not materialized")
    input_payload = reviewed_support_to_context_substitution_input(
        PILOT,
        parent_v3_source=V3,
    )["input"]
    terms = list(input_payload["terms"])
    candidate_ids = sorted(
        target["candidate_target_id"]
        for term in terms
        for target in term["candidate_targets"]
    )
    factory = _FakeSenderFactory(
        scenario_by_candidate=dict(zip(candidate_ids, _SCENARIOS, strict=True)),
        term_index={str(term["term_id"]): index for index, term in enumerate(terms)},
    )
    plan = _plan()
    ckey_sender = _FailOnceSender(factory.sender("ckey_gemini"))
    role_routes = _role_routes(
        plan,
        sender_factory=lambda route_id: (
            ckey_sender
            if route_id == "ckey_gemini"
            else factory.sender(route_id)
        ),
    )
    ledger_root = tmp_path / "ledger"
    model = RoleRoutedStructuredModel(
        plan=plan,
        role_routes=role_routes,
        response_ledger=ProviderResponseLedger(ledger_root),
        audit_run_id="role-pilot:" + input_payload["integrity"]["input_sha256"][:24],
        sleep=lambda _: None,
    )
    run = run_d2l_context_substitution(input_payload, model)
    assert run["schema_version"] == "2.3.0"
    assert len(run["candidates"]) == 15
    assert run["execution_policy"]["provider_role_plan"]["integrity"][
        "self_sha256"
    ] == plan.self_sha256
    assert all(
        candidate["final_glossary_decision"] is None
        for candidate in run["candidates"]
    )
    assert run["provider_attempts"][0]["failure_disposition"] == "RETRY_SAME_ROUTE"
    report = replay_context_run(
        input_payload=input_payload,
        original_run=run,
        ledger_root=ledger_root,
    )
    assert report["status"] == "PASS"
    assert report["provider_call_count"] == 0


class _SequenceSender:
    def __init__(self, outcomes: list[ProviderRawResponse | Exception] | None = None) -> None:
        self.outcomes = list(outcomes or [])
        self.calls = 0
        self.system_prompts: list[str] = []

    def __call__(self, **kwargs: Any) -> ProviderRawResponse:
        self.calls += 1
        self.system_prompts.append(str(kwargs["system_prompt"]))
        if not self.outcomes:
            return _ok()
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FailOnceSender:
    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.failed = False

    def __call__(self, **kwargs: Any) -> ProviderRawResponse:
        if not self.failed:
            self.failed = True
            raise TimeoutError("zero-provider transport fixture")
        return self.delegate(**kwargs)


def _ok() -> ProviderRawResponse:
    return ProviderRawResponse(
        text='{"ok":true}',
        payload={"ok": True},
        request_id="zero-provider-fixture",
        input_tokens=3,
        output_tokens=2,
        latency_ms=1,
    )


def _senders(
    *,
    ckey: list[ProviderRawResponse | Exception] | None = None,
    shop: list[ProviderRawResponse | Exception] | None = None,
    local: list[ProviderRawResponse | Exception] | None = None,
    default_success: bool = False,
) -> dict[str, _SequenceSender]:
    del default_success
    return {
        "ckey": _SequenceSender(ckey),
        "shop": _SequenceSender(shop),
        "local": _SequenceSender(local),
    }


def _plan() -> ProviderRolePlan:
    return load_provider_role_plan(
        DEFAULT_PROVIDER_ROLE_PLAN_PATH,
        expected_physical_sha256=hashlib.sha256(
            DEFAULT_PROVIDER_ROLE_PLAN_PATH.read_bytes()
        ).hexdigest(),
    )


def _reseal_plan(value: dict[str, Any]) -> None:
    unhashed = copy.deepcopy(value)
    unhashed["integrity"] = {}
    encoded = json.dumps(
        unhashed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    value["integrity"] = {"self_sha256": hashlib.sha256(encoded).hexdigest()}


def _model(
    senders: Mapping[str, _SequenceSender],
    *,
    response_ledger: ProviderResponseLedger | None = None,
) -> RoleRoutedStructuredModel:
    plan = _plan()
    sender_by_provider = {
        "ckey": senders["ckey"],
        "shopapi": senders["shop"],
        "gateway": senders["local"],
    }
    role_routes = _role_routes(
        plan,
        sender_factory=lambda route_id: sender_by_provider[
            {
                "ckey_gemini": "ckey",
                "shopaikey_gemini": "shopapi",
                "local_gpt_gateway": "gateway",
            }[route_id]
        ],
    )
    return RoleRoutedStructuredModel(
        plan=plan,
        role_routes=role_routes,
        response_ledger=response_ledger,
        audit_run_id="zero-provider-role-routing",
        sleep=lambda _: None,
    )


def _role_routes(
    plan: ProviderRolePlan,
    *,
    sender_factory: Any,
) -> dict[str, tuple[ContextProviderRoute, ...]]:
    role_routes: dict[str, tuple[ContextProviderRoute, ...]] = {}
    for role_name in plan.role_order:
        role = plan.role(role_name)
        routes = []
        for profile_id in role.route_profile_order:
            profile = plan.route_profiles[profile_id]
            routes.append(
                ContextProviderRoute(
                    route_id=profile.route_id,
                    model_id=profile.model_id,
                    sender=sender_factory(profile.route_id),
                    model_family=profile.model_family,
                    model_profile=profile.model_profile,
                    independence_group=profile.independence_group,
                    role_equivalence_group=profile.role_equivalence_group,
                    thinking_level=profile.thinking_level,
                    reasoning_effort=profile.reasoning_effort,
                    temperature=profile.temperature,
                    max_output_tokens=role.max_output_tokens,
                    timeout_seconds=profile.timeout_seconds,
                    role_plan_sha256=plan.self_sha256,
                    escalation_kind=role.escalation_kind,
                    max_attempts=profile.transport_retry_cap + 1,
                    retry_backoff_seconds=(0.0,) * profile.transport_retry_cap,
                )
            )
        role_routes[role_name] = tuple(routes)
    return role_routes


def _call(
    model: RoleRoutedStructuredModel,
    role_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    role = model.plan.role(role_name)
    return model.call(
        role=role_name,
        prompt_version=role.prompt_version,
        system_prompt="Return strict JSON.",
        payload={"candidate": "blind"},
        response_schema={"type": "object"},
        validator=lambda value: dict(value),
        tag=f"test:{role_name}",
        max_output_tokens=role.max_output_tokens,
    )
