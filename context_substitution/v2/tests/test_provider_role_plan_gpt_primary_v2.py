from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import pytest

from context_substitution.v2.contracts.common import sha256_text
from context_substitution.v2.contracts.provenance import (
    build_block_source_provenance,
)
from context_substitution.v2.jsonio import load_json_file
from context_substitution.v2.providers.base import (
    ContextProviderRoute,
    ProviderRawResponse,
)
from context_substitution.v2.providers.role_plan import (
    DEFAULT_PROVIDER_ROLE_PLAN_PATH,
    ProviderRolePlan,
    load_provider_role_plan,
    validate_provider_role_plan,
)
from context_substitution.v2.providers.role_routing import (
    RoleRoutedStructuredModel,
)
from context_substitution.v2.runtime.engine import (
    _classify_and_select_contexts,
)


V2_ROOT = Path(__file__).resolve().parents[1]
PLAN_V2_PATH = (
    V2_ROOT / "providers" / "provider_role_plan.gpt_primary.v2.json"
)
FIXTURE_PATH = (
    Path(__file__).with_name("fixtures")
    / "provider_role_plan_gpt_primary_v2.zero_provider.json"
)
PLAN_V2_SELF_SHA256 = (
    "155261fc2c80e54b6e22e266104fa6a5a2040fa6faf4b8d7865bb970a763e815"
)
PLAN_V2_PHYSICAL_SHA256 = (
    "6a229435a2d84198dc88bee26c3b4bb5645b7b086849c4f5e1a13217a9152e61"
)
PLAN_V1_SELF_SHA256 = (
    "cff7bbfb59eb05a53b6db2b1548d1cf13d8eb573a95c65ca13e295cd2d3085d9"
)
PLAN_V1_PHYSICAL_SHA256 = (
    "1f62b9a2634c2f4bc779baf170e95886e8f673ae2058bd472e9be966a2a80315"
)
FIXTURE_SELF_SHA256 = (
    "5f28c9a4f869ff45938bf3dd80680c39e4e1d3f1881195056c9d20f2c3b7a334"
)


def test_gpt_primary_v2_matches_reviewed_hashes_and_exact_matrix() -> None:
    plan = _load_v2_plan()
    assert plan.plan_id == "cst_live_role_routing_gpt_primary_v2"
    assert plan.self_sha256 == PLAN_V2_SELF_SHA256
    assert plan.physical_sha256 == PLAN_V2_PHYSICAL_SHA256
    assert plan.candidate_replicate_cap == 1
    assert plan.payload["final_decision_owner"] == "GLOBAL_TERMINOLOGY_VALIDATOR"

    gemini_routes = (
        "ckey_gemini_3_5_flash_low",
        "shopapi_gemini_3_5_flash_low",
    )
    assert plan.role("context_selector").route_profile_order == gemini_routes
    assert plan.role("trial_translator").route_profile_order == gemini_routes
    assert plan.role("secondary_context_judge").route_profile_order == gemini_routes
    assert plan.role("trial_translation_quality_gate").route_profile_order == (
        "gateway_gpt_5_6_luna_none",
    )
    for role in ("context_judge", "contrastive_sense_judge"):
        assert plan.role(role).route_profile_order == (
            "gateway_gpt_5_6_terra_low",
        )
    assert plan.role("pairwise_tiebreaker").route_profile_order == (
        "gateway_gpt_5_6_terra_medium",
    )

    luna = plan.route_profiles["gateway_gpt_5_6_luna_none"]
    terra_low = plan.route_profiles["gateway_gpt_5_6_terra_low"]
    terra_medium = plan.route_profiles["gateway_gpt_5_6_terra_medium"]
    gemini = plan.route_profiles["ckey_gemini_3_5_flash_low"]
    assert luna.reasoning_effort == "none" and luna.thinking_level is None
    assert terra_low.reasoning_effort == "low" and terra_low.thinking_level is None
    assert terra_medium.reasoning_effort == "medium"
    assert gemini.thinking_level == "LOW" and gemini.reasoning_effort is None
    assert terra_low.model_family != gemini.model_family
    assert terra_low.independence_group != gemini.independence_group
    assert plan.role("secondary_context_judge").escalation_kind == (
        "SECONDARY_JUDGE_ESCALATION"
    )
    assert plan.role("pairwise_tiebreaker").escalation_kind == (
        "HARD_CASE_ESCALATION"
    )


def test_v1_replay_authority_remains_byte_identical_and_loadable() -> None:
    assert _physical_sha256(DEFAULT_PROVIDER_ROLE_PLAN_PATH) == PLAN_V1_PHYSICAL_SHA256
    plan = load_provider_role_plan(
        DEFAULT_PROVIDER_ROLE_PLAN_PATH,
        expected_physical_sha256=PLAN_V1_PHYSICAL_SHA256,
    )
    assert plan.self_sha256 == PLAN_V1_SELF_SHA256
    assert plan.plan_id == "cst_live_role_routing_v1"
    assert plan.role("trial_translator").route_profile_order == (
        "gateway_gpt_5_6_luna_none",
    )


def test_v2_rejects_automatic_cross_family_fallback() -> None:
    value = load_json_file(PLAN_V2_PATH, require_object=True)
    value["roles"]["trial_translator"]["route_profile_order"].append(
        "gateway_gpt_5_6_luna_none"
    )
    value["roles"]["trial_translator"][
        "provider_request_cap_per_semantic_call"
    ] = 6
    _reseal(value)
    with pytest.raises(ValueError, match="semantically equivalent"):
        validate_provider_role_plan(value)


def test_frozen_human_reviewed_selection_makes_zero_selector_calls() -> None:
    source_text = "A framework provides a reusable structure for software design."
    context = {
        "context_id": "context-frozen-1",
        "document_id": "d2l",
        "chapter_id": "chapter-1",
        "block_id": "block-1",
        "block_type": "paragraph",
        "source_text": source_text,
        "source_text_sha256": sha256_text(source_text),
        "source_provenance": build_block_source_provenance(
            document_id="d2l",
            chapter_id="chapter-1",
            block_id="block-1",
            source_text=source_text,
        ),
        "reviewed_selection": {
            "sense_relation": "SAME_SENSE",
            "context_type": "definition",
            "judgeability": "JUDGEABLE",
            "reason": "Frozen Dataset annotation.",
        },
    }
    term = {
        "term_id": "term-framework",
        "sense_id": "sense-framework-software",
        "scope_id": "scope-d2l",
        "contexts": [context],
    }
    model = _ForbiddenModel()
    result = _classify_and_select_contexts(
        model=model,  # type: ignore[arg-type]
        term=term,
        selection_contract={
            "selector_mode": "FROZEN_HUMAN_REVIEWED_SELECTION"
        },
    )
    assert model.calls == 0
    assert result["provenance"] is None
    assert [row["context_id"] for row in result["same_sense"]] == [
        "context-frozen-1"
    ]


@pytest.mark.parametrize(
    "case_id",
    [
        "one_candidate",
        "one_sense_three_candidates",
        "official_scale_five_senses_fifteen_candidates",
    ],
)
def test_zero_provider_fixture_call_graph_is_exact(case_id: str) -> None:
    fixture = _load_fixture()
    case = next(row for row in fixture["cases"] if row["case_id"] == case_id)
    plan = _load_v2_plan()
    senders = {
        "ckey_gemini": _RecordingSender(),
        "shopaikey_gemini": _RecordingSender(),
        "local_gpt_gateway": _RecordingSender(),
    }
    model = _build_model(plan, senders)
    expected_by_role = case["mandatory_semantic_calls"]
    for role in plan.role_order:
        for index in range(int(expected_by_role[role])):
            _call(model, role, tag=f"{case_id}:{role}:{index}")

    attempts = model.attempted_calls
    assert Counter(row["role"] for row in attempts) == Counter(expected_by_role)
    assert Counter(row["model_family"] for row in attempts) == Counter(
        case["mandatory_family_calls"]
    )
    assert len(attempts) == sum(expected_by_role.values())
    assert sum(sender.calls for sender in senders.values()) == len(attempts)
    assert all(row["candidate_replicate_index"] == 0 for row in attempts)
    assert all(row["transport_retry_index"] == 0 for row in attempts)
    assert case["mandatory_physical_request_ceiling"] == sum(
        int(count) * plan.role(role).provider_request_cap_per_semantic_call
        for role, count in expected_by_role.items()
    )
    assert fixture["external_provider_calls"] == 0
    assert fixture["network_calls"] == 0


def test_v2_retry_and_equivalent_failover_remain_one_semantic_call() -> None:
    ckey = _RecordingSender([TimeoutError("timeout"), TimeoutError("timeout")])
    shop = _RecordingSender([_ok()])
    local = _RecordingSender()
    model = _build_model(
        _load_v2_plan(),
        {
            "ckey_gemini": ckey,
            "shopaikey_gemini": shop,
            "local_gpt_gateway": local,
        },
    )
    _call(model, "trial_translator", tag="retry-is-not-replicate")
    attempts = model.attempted_calls
    assert [row["failure_disposition"] for row in attempts] == [
        "RETRY_SAME_ROUTE",
        "EQUIVALENT_FAILOVER",
        "ACCEPTED",
    ]
    assert [row["provider_request_index"] for row in attempts] == [1, 2, 3]
    assert [row["transport_retry_index"] for row in attempts] == [0, 1, 0]
    assert {row["semantic_role_call_index"] for row in attempts} == {1}
    assert {row["candidate_replicate_index"] for row in attempts} == {0}
    assert {row["model_family"] for row in attempts} == {"gemini-3.5-flash"}
    assert local.calls == 0


class _ForbiddenModel:
    def __init__(self) -> None:
        self.calls = 0

    def call(self, **_: Any) -> None:
        self.calls += 1
        raise AssertionError("frozen selector must not call a model")


class _RecordingSender:
    def __init__(
        self,
        outcomes: list[ProviderRawResponse | Exception] | None = None,
    ) -> None:
        self.outcomes = list(outcomes or [])
        self.calls = 0

    def __call__(self, **_: Any) -> ProviderRawResponse:
        self.calls += 1
        if not self.outcomes:
            return _ok()
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _ok() -> ProviderRawResponse:
    return ProviderRawResponse(
        text='{"ok":true}',
        payload={"ok": True},
        request_id="zero-provider-v2-fixture",
        input_tokens=3,
        output_tokens=2,
        latency_ms=1,
    )


def _load_v2_plan() -> ProviderRolePlan:
    return load_provider_role_plan(
        PLAN_V2_PATH,
        expected_physical_sha256=PLAN_V2_PHYSICAL_SHA256,
    )


def _load_fixture() -> dict[str, Any]:
    value = load_json_file(FIXTURE_PATH, require_object=True)
    recorded = value["integrity"]["self_sha256"]
    assert recorded == FIXTURE_SELF_SHA256
    unhashed = copy.deepcopy(value)
    unhashed["integrity"] = {}
    assert _canonical_sha256(unhashed) == recorded
    assert value["provider_role_plan_self_sha256"] == PLAN_V2_SELF_SHA256
    assert value["provider_role_plan_physical_sha256"] == PLAN_V2_PHYSICAL_SHA256
    return value


def _build_model(
    plan: ProviderRolePlan,
    senders: Mapping[str, _RecordingSender],
) -> RoleRoutedStructuredModel:
    role_routes: dict[str, tuple[ContextProviderRoute, ...]] = {}
    for role_name in plan.role_order:
        role = plan.role(role_name)
        routes: list[ContextProviderRoute] = []
        for profile_id in role.route_profile_order:
            profile = plan.route_profiles[profile_id]
            routes.append(
                ContextProviderRoute(
                    route_id=profile.route_id,
                    model_id=profile.model_id,
                    sender=senders[profile.route_id],
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
    return RoleRoutedStructuredModel(
        plan=plan,
        role_routes=role_routes,
        audit_run_id="gpt-primary-v2-zero-provider",
        sleep=lambda _: None,
    )


def _call(
    model: RoleRoutedStructuredModel,
    role_name: str,
    *,
    tag: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    role = model.plan.role(role_name)
    return model.call(
        role=role_name,
        prompt_version=role.prompt_version,
        system_prompt="Return strict JSON.",
        payload={"candidate": "blind"},
        response_schema={"type": "object"},
        validator=lambda value: dict(value),
        tag=tag,
        max_output_tokens=role.max_output_tokens,
    )


def _physical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reseal(value: dict[str, Any]) -> None:
    unhashed = copy.deepcopy(value)
    unhashed["integrity"] = {}
    value["integrity"] = {"self_sha256": _canonical_sha256(unhashed)}
