from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Callable

import pytest

import context_substitution.v2.providers.catalog as catalog_module
from context_substitution.v2.cli import main
from context_substitution.v2.providers.base import (
    ContextProviderRoute,
    FailoverStructuredModel,
    ProviderRawResponse,
)
from context_substitution.v2.providers.catalog import (
    DEFAULT_PROVIDER_CATALOG_PATH,
    load_provider_catalog,
)
from context_substitution.v2.providers.google import GoogleGenAISender
from context_substitution.v2.providers.openai_compatible import (
    OpenAICompatibleRouteSettings,
    OpenAICompatibleSender,
)
from context_substitution.v2.providers.role_plan import (
    DEFAULT_PROVIDER_ROLE_PLAN_PATH,
)


SECRETS = {
    "GEMINI-KEY.txt": "shop-secret-not-for-output",
    "CKEY.txt": "ckey-secret-not-for-output",
    "LOCAL-GPT-GATEWAY.txt": "gateway-secret-not-for-output",
}


def test_default_catalog_builds_three_routes_without_exposing_keys(
    tmp_path: Path,
) -> None:
    credentials = _credentials(tmp_path)
    catalog = load_provider_catalog(environment={})
    routes = catalog.build_routes(credentials_root=credentials)
    assert [route.route_id for route in routes] == [
        "ckey_gemini",
        "shopaikey_gemini",
        "local_gpt_gateway",
    ]
    assert isinstance(routes[0].sender, OpenAICompatibleSender)
    assert isinstance(routes[1].sender, OpenAICompatibleSender)
    assert isinstance(routes[2].sender, OpenAICompatibleSender)
    assert routes[0].model_id == "vuduythanh2023/gemini-3.5-flash"
    assert [route.max_attempts for route in routes] == [2, 2, 2]

    summary = catalog.preflight_summary(credentials_root=credentials)
    rendered = json.dumps(summary, sort_keys=True)
    assert summary["provider_calls"] == 0
    assert summary["read_only"] is True
    assert all(secret not in rendered for secret in SECRETS.values())


def test_catalog_environment_overrides_are_centralized(tmp_path: Path) -> None:
    catalog = load_provider_catalog(
        environment={
            "CST_PROVIDER_GATEWAY_MODEL": "gpt-5.5-pinned-2026-07",
            "CST_PROVIDER_GATEWAY_MODEL_FAMILY": "gpt-5.5-pinned",
            "CST_PROVIDER_GATEWAY_INDEPENDENCE_GROUP": "gateway-pinned",
            "CST_PROVIDER_GATEWAY_BASE_URL": "http://127.0.0.1:9999/v1",
            "CST_PROVIDER_GATEWAY_MAX_ATTEMPTS": "3",
        }
    )
    route = catalog.build_routes(
        credentials_root=_credentials(tmp_path),
        provider_ids=("gateway",),
    )[0]
    assert route.model_id == "gpt-5.5-pinned-2026-07"
    assert route.model_family == "gpt-5.5-pinned"
    assert route.independence_group == "gateway-pinned"
    assert route.max_attempts == 3
    assert route.retry_backoff_seconds == (0.5, 0.5)
    assert (  # type: ignore[attr-defined]
        route.sender._settings.base_url == "http://127.0.0.1:9999/v1"
    )


def test_provider_preflight_cli_is_zero_api_and_secret_free(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    credentials = _credentials(tmp_path)
    assert main(
        [
            "provider-preflight",
            "--credentials-root",
            str(credentials),
            "--provider-role-plan-sha256",
            hashlib.sha256(DEFAULT_PROVIDER_ROLE_PLAN_PATH.read_bytes()).hexdigest(),
        ]
    ) == 0
    output = capsys.readouterr().out
    assert '"provider_calls": 0' in output
    assert '"provider_id": "shopapi"' in output
    assert '"provider_id": "gateway"' in output
    assert str(credentials) not in output
    assert all(secret not in output for secret in SECRETS.values())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["profiles"][0].__setitem__(
                "credential_file", "../GEMINI-KEY.txt"
            ),
            "plain .txt filename",
        ),
        (
            lambda value: value["profiles"][0].__setitem__("unknown", True),
            "keys mismatch",
        ),
        (
            lambda value: value["profiles"][1].__setitem__(
                "provider_id", "shopapi"
            ),
            "duplicate provider_id",
        ),
        (
            lambda value: value["profiles"][1].__setitem__(
                "route_id", "shopaikey_gemini"
            ),
            "duplicate route_id",
        ),
    ],
)
def test_catalog_rejects_ambiguous_or_unsafe_configuration(
    tmp_path: Path,
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    value = json.loads(DEFAULT_PROVIDER_CATALOG_PATH.read_text(encoding="utf-8"))
    mutation(value)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_provider_catalog(path, environment={})


def test_catalog_rejects_missing_credential(tmp_path: Path) -> None:
    credentials = _credentials(tmp_path)
    (credentials / "CKEY.txt").unlink()
    catalog = load_provider_catalog(environment={})
    with pytest.raises(ValueError, match="credential file is unavailable"):
        catalog.build_routes(credentials_root=credentials)


def test_preflight_reports_missing_adapter_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = load_provider_catalog(environment={})
    monkeypatch.setattr(catalog_module, "find_spec", lambda _: None)
    with pytest.raises(ValueError, match="Python dependency is unavailable"):
        catalog.preflight_summary(
            credentials_root=_credentials(tmp_path),
            provider_ids=("gateway",),
        )


def test_malformed_response_retries_same_route_before_failover() -> None:
    first = _SequenceSender(
        [
            ProviderRawResponse(text="{", payload=None),
            ProviderRawResponse(text='{"ok":true}', payload=None),
        ]
    )
    second = _SequenceSender([ProviderRawResponse(text='{"ok":true}', payload=None)])
    model = FailoverStructuredModel(
        [
            _route("shopaikey_gemini", first, attempts=2),
            _route("ckey_gemini", second),
        ],
        sleep=lambda _: None,
    )
    result, provenance = _call(model)
    assert result == {"ok": True}
    assert provenance["provider_route_id"] == "shopaikey_gemini"
    assert first.calls == 2
    assert second.calls == 0


def test_auth_failure_switches_provider_without_same_route_retry() -> None:
    first = _SequenceSender([_HTTPFailure(401)])
    second = _SequenceSender([ProviderRawResponse(text='{"ok":true}', payload=None)])
    model = FailoverStructuredModel(
        [
            _route("shopaikey_gemini", first, attempts=3),
            _route("ckey_gemini", second),
        ],
        sleep=lambda _: None,
    )
    _, provenance = _call(model)
    assert provenance["provider_route_id"] == "ckey_gemini"
    assert first.calls == 1
    assert second.calls == 1


def test_timeout_retries_then_fails_over() -> None:
    first = _SequenceSender([TimeoutError("timeout"), TimeoutError("timeout")])
    second = _SequenceSender([ProviderRawResponse(text='{"ok":true}', payload=None)])
    model = FailoverStructuredModel(
        [
            _route("shopaikey_gemini", first, attempts=2),
            _route("ckey_gemini", second),
        ],
        sleep=lambda _: None,
    )
    _, provenance = _call(model)
    assert provenance["provider_route_id"] == "ckey_gemini"
    assert first.calls == 2
    assert second.calls == 1


def test_unknown_provider_failure_does_not_replay_or_fail_over() -> None:
    first = _SequenceSender([RuntimeError("unknown physical outcome")])
    second = _SequenceSender([ProviderRawResponse(text='{"ok":true}', payload=None)])
    model = FailoverStructuredModel(
        [_route("shopaikey_gemini", first), _route("ckey_gemini", second)],
        sleep=lambda _: None,
    )
    with pytest.raises(RuntimeError, match="unknown physical outcome"):
        _call(model)
    assert first.calls == 1
    assert second.calls == 0


def test_gateway_request_uses_configurable_structured_output_contract() -> None:
    sender = OpenAICompatibleSender(
        OpenAICompatibleRouteSettings(
            route_id="local_gpt_gateway",
            model_id="gpt-5.5",
            api_key="hidden",
            response_format_mode="json_schema",
            max_output_parameter="max_completion_tokens",
            reasoning_effort="low",
            temperature=0.2,
        )
    )
    request = sender._request(
        system_prompt="judge",
        user_payload_json='{"candidate":"x"}',
        response_schema={"type": "object", "additionalProperties": False},
        max_output_tokens=1234,
    )
    assert request["model"] == "gpt-5.5"
    assert request["max_completion_tokens"] == 1234
    assert request["response_format"]["type"] == "json_schema"
    assert request["reasoning_effort"] == "low"
    assert request["temperature"] == 0.2


def test_shop_request_uses_prompt_json_with_gemini_generation_binding() -> None:
    settings = OpenAICompatibleRouteSettings(
        route_id="shopaikey_gemini",
        model_id="gemini-3.5-flash",
        api_key="hidden",
        base_url="https://api.shopaikey.com/v1",
        response_format_mode="prompt_only",
        max_output_parameter="max_completion_tokens",
        thinking_level="LOW",
    )
    route = settings.build()
    request = route.sender._request(  # type: ignore[attr-defined]
        system_prompt=(
            "judge\n\nSealed generation configuration: "
            "thinking_level=LOW; reasoning_effort=null; temperature=0."
        ),
        user_payload_json='{"candidate":"x"}',
        response_schema={"type": "object", "additionalProperties": False},
        max_output_tokens=1536,
    )
    assert route.thinking_level == "LOW"
    assert route.reasoning_effort is None
    assert request["model"] == "gemini-3.5-flash"
    assert request["max_completion_tokens"] == 1536
    assert "response_format" not in request
    assert "Return exactly one JSON object" in request["messages"][0]["content"]


class _HTTPFailure(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class _SequenceSender:
    def __init__(self, outcomes: list[ProviderRawResponse | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, **_: Any) -> ProviderRawResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _route(
    route_id: str,
    sender: _SequenceSender,
    *,
    attempts: int = 1,
) -> ContextProviderRoute:
    return ContextProviderRoute(
        route_id=route_id,
        model_id=f"model-{route_id}",
        sender=sender,
        model_family=f"family-{route_id}",
        independence_group=f"group-{route_id}",
        max_attempts=attempts,
        retry_backoff_seconds=(0.0,) * (attempts - 1),
    )


def _call(model: FailoverStructuredModel) -> tuple[dict[str, Any], dict[str, Any]]:
    return model.call(
        role="context_judge",
        prompt_version="context-judge-test-v1",
        system_prompt="Return JSON.",
        payload={"candidate": "x"},
        response_schema={"type": "object"},
        validator=lambda value: dict(value),
        tag="candidate-x",
    )


def _credentials(tmp_path: Path) -> Path:
    root = tmp_path / "API-Key"
    root.mkdir()
    for name, secret in SECRETS.items():
        (root / name).write_text(secret + "\n", encoding="utf-8")
    return root
