from __future__ import annotations

import os
import re
from importlib.util import find_spec
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from context_substitution.v2.contracts.common import PROVIDER_ROUTE_IDS
from context_substitution.v2.jsonio import load_json_file
from context_substitution.v2.providers.base import ContextProviderRoute
from context_substitution.v2.providers.google import GoogleRouteSettings
from context_substitution.v2.providers.openai_compatible import (
    OpenAICompatibleRouteSettings,
)


CATALOG_SCHEMA_ID = "ContextSubstitutionProviderCatalogV1"
CATALOG_SCHEMA_VERSION = "1.0.0"
CREDENTIALS_ROOT_ENV = "CST_CREDENTIALS_ROOT"
DEFAULT_PROVIDER_CATALOG_PATH = Path(__file__).with_name(
    "provider_catalog.v1.json"
)

_ADAPTERS = frozenset({"google_genai", "openai_compatible"})
_ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_PROVIDER_ID = re.compile(r"[a-z][a-z0-9_-]*\Z")
_TOP_LEVEL_KEYS = frozenset(
    {"schema_id", "schema_version", "default_route_order", "profiles"}
)
_PROFILE_KEYS = frozenset(
    {
        "provider_id",
        "route_id",
        "adapter",
        "model_id",
        "model_env",
        "base_url",
        "base_url_env",
        "credential_file",
        "timeout_seconds",
        "max_attempts",
        "max_attempts_env",
        "retry_backoff_seconds",
        "model_family",
        "model_family_env",
        "independence_group",
        "independence_group_env",
        "response_format_mode",
        "max_output_parameter",
    }
)


@dataclass(frozen=True)
class ProviderProfile:
    provider_id: str
    route_id: str
    adapter: str
    model_id: str
    base_url: str
    credential_file: str
    timeout_seconds: int
    max_attempts: int
    retry_backoff_seconds: tuple[float, ...]
    model_family: str
    independence_group: str
    response_format_mode: str | None
    max_output_parameter: str | None

    def build_route(
        self,
        *,
        api_key: str,
        model_id: str | None = None,
        model_family: str | None = None,
        model_profile: str | None = None,
        independence_group: str | None = None,
        role_equivalence_group: str | None = None,
        thinking_level: str | None = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.0,
        timeout_seconds: int | None = None,
        max_attempts: int | None = None,
        retry_backoff_seconds: tuple[float, ...] | None = None,
        max_output_tokens: int | None = None,
        role_plan_sha256: str | None = None,
        escalation_kind: str | None = None,
    ) -> ContextProviderRoute:
        common = {
            "route_id": self.route_id,
            "model_id": model_id or self.model_id,
            "api_key": api_key,
            "base_url": self.base_url,
            "timeout_seconds": timeout_seconds or self.timeout_seconds,
            "model_family": model_family or self.model_family,
            "model_profile": model_profile,
            "independence_group": independence_group or self.independence_group,
            "role_equivalence_group": role_equivalence_group,
            "temperature": temperature,
            "max_attempts": max_attempts or self.max_attempts,
            "retry_backoff_seconds": (
                self.retry_backoff_seconds
                if retry_backoff_seconds is None
                else retry_backoff_seconds
            ),
            "max_output_tokens": max_output_tokens,
            "role_plan_sha256": role_plan_sha256,
            "escalation_kind": escalation_kind,
        }
        if self.adapter == "google_genai":
            return GoogleRouteSettings(
                **common,
                thinking_level=thinking_level,
            ).build()
        if self.adapter == "openai_compatible":
            return OpenAICompatibleRouteSettings(
                **common,
                thinking_level=thinking_level,
                reasoning_effort=reasoning_effort,
                response_format_mode=str(self.response_format_mode),
                max_output_parameter=str(self.max_output_parameter),
            ).build()
        raise AssertionError("validated provider adapter is unreachable")


@dataclass(frozen=True)
class ProviderCatalog:
    source_path: Path
    profiles: tuple[ProviderProfile, ...]
    default_route_order: tuple[str, ...]

    def selected_profiles(
        self, provider_ids: Sequence[str] | None = None
    ) -> tuple[ProviderProfile, ...]:
        selected = tuple(provider_ids or self.default_route_order)
        if not selected:
            raise ValueError("provider selection must not be empty")
        if len(set(selected)) != len(selected):
            raise ValueError("provider selection must not contain duplicates")
        by_id = {profile.provider_id: profile for profile in self.profiles}
        unknown = [provider_id for provider_id in selected if provider_id not in by_id]
        if unknown:
            raise ValueError(f"unknown provider selection: {', '.join(unknown)}")
        return tuple(by_id[provider_id] for provider_id in selected)

    def build_routes(
        self,
        *,
        credentials_root: Path | None = None,
        provider_ids: Sequence[str] | None = None,
    ) -> tuple[ContextProviderRoute, ...]:
        root = resolve_credentials_root(credentials_root)
        return tuple(
            profile.build_route(
                api_key=_read_credential(root, profile.credential_file)
            )
            for profile in self.selected_profiles(provider_ids)
        )

    def preflight_summary(
        self,
        *,
        credentials_root: Path | None = None,
        provider_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        root = resolve_credentials_root(credentials_root)
        rows: list[dict[str, Any]] = []
        for profile in self.selected_profiles(provider_ids):
            api_key = _read_credential(root, profile.credential_file)
            route = profile.build_route(api_key=api_key)
            dependency = _adapter_dependency(profile.adapter)
            if not _dependency_available(dependency):
                raise ValueError(
                    f"{profile.provider_id}: Python dependency is unavailable: "
                    f"{dependency}"
                )
            rows.append(
                {
                    "provider_id": profile.provider_id,
                    "route_id": route.route_id,
                    "adapter": profile.adapter,
                    "adapter_dependency": dependency,
                    "dependency_available": True,
                    "model_id": route.model_id,
                    "base_url": profile.base_url,
                    "credential_file": profile.credential_file,
                    "credential_loaded": True,
                    "timeout_seconds": profile.timeout_seconds,
                    "max_attempts": profile.max_attempts,
                    "retry_backoff_seconds": list(
                        profile.retry_backoff_seconds
                    ),
                }
            )
        return {
            "status": "PASS",
            "read_only": True,
            "provider_calls": 0,
            "schema_id": CATALOG_SCHEMA_ID,
            "schema_version": CATALOG_SCHEMA_VERSION,
            "catalog": self.source_path.name,
            "credentials_root": "<redacted-credentials-root>",
            "providers": rows,
        }


def load_provider_catalog(
    path: Path = DEFAULT_PROVIDER_CATALOG_PATH,
    *,
    environment: Mapping[str, str] | None = None,
) -> ProviderCatalog:
    source = Path(path)
    payload = load_json_file(source, require_object=True)
    _require_exact_keys(payload, _TOP_LEVEL_KEYS, "provider catalog")
    if payload["schema_id"] != CATALOG_SCHEMA_ID:
        raise ValueError("provider catalog schema_id is unsupported")
    if payload["schema_version"] != CATALOG_SCHEMA_VERSION:
        raise ValueError("provider catalog schema_version is unsupported")
    raw_profiles = payload["profiles"]
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ValueError("provider catalog profiles must be a nonempty list")
    env = os.environ if environment is None else environment
    profiles = tuple(
        _load_profile(row, index=index, environment=env)
        for index, row in enumerate(raw_profiles)
    )
    provider_ids = tuple(profile.provider_id for profile in profiles)
    route_ids = tuple(profile.route_id for profile in profiles)
    if len(set(provider_ids)) != len(provider_ids):
        raise ValueError("provider catalog contains duplicate provider_id")
    if len(set(route_ids)) != len(route_ids):
        raise ValueError("provider catalog contains duplicate route_id")
    order = _string_list(
        payload["default_route_order"],
        "provider catalog default_route_order",
    )
    if len(set(order)) != len(order):
        raise ValueError("default_route_order must not contain duplicates")
    if set(order) != set(provider_ids):
        raise ValueError("default_route_order must contain every provider exactly once")
    return ProviderCatalog(
        source_path=source,
        profiles=profiles,
        default_route_order=order,
    )


def resolve_credentials_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        candidate = Path(explicit)
    elif os.environ.get(CREDENTIALS_ROOT_ENV):
        candidate = Path(os.environ[CREDENTIALS_ROOT_ENV])
    else:
        cwd_candidate = Path.cwd() / "API-Key"
        repository_candidate = Path(__file__).resolve().parents[3] / "API-Key"
        candidate = (
            cwd_candidate if cwd_candidate.is_dir() else repository_candidate
        )
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            f"credential root is unavailable; set {CREDENTIALS_ROOT_ENV} or "
            "pass --credentials-root"
        ) from exc
    if not resolved.is_dir():
        raise ValueError("credential root must be a directory")
    return resolved


def _load_profile(
    raw: Any,
    *,
    index: int,
    environment: Mapping[str, str],
) -> ProviderProfile:
    label = f"provider catalog profiles[{index}]"
    if not isinstance(raw, Mapping):
        raise ValueError(f"{label} must be an object")
    _require_exact_keys(raw, _PROFILE_KEYS, label)
    provider_id = _matched_string(raw["provider_id"], _PROVIDER_ID, f"{label}.provider_id")
    route_id = _nonempty_string(raw["route_id"], f"{label}.route_id")
    if route_id not in PROVIDER_ROUTE_IDS:
        raise ValueError(f"{label}.route_id is unsupported")
    adapter = _nonempty_string(raw["adapter"], f"{label}.adapter")
    if adapter not in _ADAPTERS:
        raise ValueError(f"{label}.adapter is unsupported")
    model_env = _env_name(raw["model_env"], f"{label}.model_env")
    model_family_env = _env_name(
        raw["model_family_env"], f"{label}.model_family_env"
    )
    independence_group_env = _env_name(
        raw["independence_group_env"],
        f"{label}.independence_group_env",
    )
    base_url_env = _env_name(raw["base_url_env"], f"{label}.base_url_env")
    attempts_env = _env_name(
        raw["max_attempts_env"], f"{label}.max_attempts_env"
    )
    model_id = _nonempty_string(
        environment.get(model_env, raw["model_id"]), f"{label}.model_id"
    )
    base_url = _validated_base_url(
        environment.get(base_url_env, raw["base_url"]), f"{label}.base_url"
    )
    credential_file = _credential_filename(
        raw["credential_file"], f"{label}.credential_file"
    )
    timeout_seconds = _bounded_integer(
        raw["timeout_seconds"], f"{label}.timeout_seconds", 1, 3_600
    )
    configured_attempts = _bounded_integer(
        raw["max_attempts"], f"{label}.max_attempts", 1, 5
    )
    max_attempts = _bounded_integer(
        environment.get(attempts_env, configured_attempts),
        f"environment {attempts_env}",
        1,
        5,
    )
    configured_backoff = _backoff_values(
        raw["retry_backoff_seconds"],
        f"{label}.retry_backoff_seconds",
        configured_attempts,
    )
    retry_backoff = _resize_backoff(configured_backoff, max_attempts)
    response_mode = _optional_string(
        raw["response_format_mode"], f"{label}.response_format_mode"
    )
    output_parameter = _optional_string(
        raw["max_output_parameter"], f"{label}.max_output_parameter"
    )
    if adapter == "google_genai" and (
        response_mode is not None or output_parameter is not None
    ):
        raise ValueError(f"{label}: Google adapter cannot use OpenAI response options")
    if adapter == "openai_compatible" and (
        response_mode not in {"json_schema", "json_object", "prompt_only"}
        or output_parameter not in {"max_completion_tokens", "max_tokens"}
    ):
        raise ValueError(f"{label}: OpenAI-compatible response options are invalid")
    return ProviderProfile(
        provider_id=provider_id,
        route_id=route_id,
        adapter=adapter,
        model_id=model_id,
        base_url=base_url,
        credential_file=credential_file,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        retry_backoff_seconds=retry_backoff,
        model_family=_nonempty_string(
            environment.get(model_family_env, raw["model_family"]),
            f"{label}.model_family",
        ),
        independence_group=_nonempty_string(
            environment.get(
                independence_group_env, raw["independence_group"]
            ),
            f"{label}.independence_group",
        ),
        response_format_mode=response_mode,
        max_output_parameter=output_parameter,
    )


def _adapter_dependency(adapter: str) -> str:
    if adapter == "google_genai":
        return "google.genai"
    if adapter == "openai_compatible":
        return "openai"
    raise AssertionError("validated provider adapter is unreachable")


def _dependency_available(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, AttributeError):
        return False


def _read_credential(root: Path, filename: str) -> str:
    target = root / filename
    try:
        physical = target.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"credential file is unavailable: {filename}") from exc
    if physical.parent != root or not physical.is_file():
        raise ValueError(f"credential file escapes credential root: {filename}")
    try:
        lines = [
            line.strip()
            for line in physical.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"credential file cannot be read: {filename}") from exc
    if len(lines) != 1 or any(character.isspace() for character in lines[0]):
        raise ValueError(f"credential file must contain exactly one token: {filename}")
    return lines[0]


def _require_exact_keys(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{label} keys mismatch; missing={missing}, unknown={unknown}")


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be a nonempty trimmed string")
    return value


def _optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, label)


def _matched_string(value: Any, pattern: re.Pattern[str], label: str) -> str:
    rendered = _nonempty_string(value, label)
    if pattern.fullmatch(rendered) is None:
        raise ValueError(f"{label} has invalid characters")
    return rendered


def _env_name(value: Any, label: str) -> str:
    return _matched_string(value, _ENV_NAME, label)


def _credential_filename(value: Any, label: str) -> str:
    rendered = _nonempty_string(value, label)
    if (
        Path(rendered).name != rendered
        or "/" in rendered
        or "\\" in rendered
        or rendered in {".", ".."}
        or not rendered.casefold().endswith(".txt")
    ):
        raise ValueError(f"{label} must be one plain .txt filename")
    return rendered


def _validated_base_url(value: Any, label: str) -> str:
    rendered = _nonempty_string(value, label).rstrip("/")
    parsed = urlsplit(rendered)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must be a plain HTTP(S) base URL")
    return rendered


def _bounded_integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if str(result) != str(value) and not isinstance(value, int):
        raise ValueError(f"{label} must be a canonical integer")
    if not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return result


def _backoff_values(value: Any, label: str, max_attempts: int) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != max_attempts - 1:
        raise ValueError(f"{label} must contain max_attempts - 1 values")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{label} values must be numbers")
        rendered = float(item)
        if not 0 <= rendered <= 60:
            raise ValueError(f"{label} values must be between 0 and 60")
        result.append(rendered)
    return tuple(result)


def _resize_backoff(values: tuple[float, ...], max_attempts: int) -> tuple[float, ...]:
    desired = max_attempts - 1
    if desired <= len(values):
        return values[:desired]
    fill = values[-1] if values else 0.0
    return values + (fill,) * (desired - len(values))


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty list")
    return tuple(_nonempty_string(item, label) for item in value)


__all__ = [
    "CATALOG_SCHEMA_ID",
    "CATALOG_SCHEMA_VERSION",
    "CREDENTIALS_ROOT_ENV",
    "DEFAULT_PROVIDER_CATALOG_PATH",
    "ProviderCatalog",
    "ProviderProfile",
    "load_provider_catalog",
    "resolve_credentials_root",
]
