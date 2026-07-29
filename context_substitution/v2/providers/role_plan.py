from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from context_substitution.v2.contracts.common import PROVIDER_ROLES, PROVIDER_ROUTE_IDS
from context_substitution.v2.jsonio import load_json_file
from context_substitution.v2.providers.base import ContextProviderRoute
from context_substitution.v2.providers.catalog import (
    CREDENTIALS_ROOT_ENV,
    ProviderCatalog,
    resolve_credentials_root,
)


ROLE_PLAN_SCHEMA_ID = "ContextSubstitutionProviderRolePlanV1"
ROLE_PLAN_SCHEMA_VERSION = "1.0.0"
DEFAULT_PROVIDER_ROLE_PLAN_PATH = Path(__file__).with_name(
    "provider_role_plan.v1.json"
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ESCALATION_KINDS = frozenset(
    {"SECONDARY_JUDGE_ESCALATION", "HARD_CASE_ESCALATION"}
)
_THINKING_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "MINIMAL"})
_REASONING_EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh"}
)
_PROTECTED_ENV_PREFIX = "CST_PROVIDER_"


@dataclass(frozen=True)
class RoleRouteProfile:
    profile_id: str
    provider_id: str
    route_id: str
    adapter: str
    model_id: str
    model_family: str
    model_profile: str
    independence_group: str
    role_equivalence_group: str
    thinking_level: str | None
    reasoning_effort: str | None
    temperature: float
    timeout_seconds: int
    transport_retry_cap: int
    retry_backoff_seconds: tuple[float, ...]

    @property
    def effective_generation_config(self) -> dict[str, Any]:
        return {
            "thinking_level": self.thinking_level,
            "reasoning_effort": self.reasoning_effort,
            "temperature": self.temperature,
        }


@dataclass(frozen=True)
class ProviderRole:
    role: str
    prompt_version: str
    response_contract_id: str
    max_output_tokens: int
    semantic_role_call_cap_per_run: int
    provider_request_cap_per_semantic_call: int
    escalation_kind: str | None
    route_profile_order: tuple[str, ...]


@dataclass(frozen=True)
class ProviderRolePlan:
    source_path: Path
    physical_sha256: str
    plan_id: str
    provider_catalog_physical_sha256: str
    candidate_replicate_cap: int
    provider_request_cap_per_run: int
    profile_order: tuple[str, ...]
    route_profiles: Mapping[str, RoleRouteProfile]
    role_order: tuple[str, ...]
    roles: Mapping[str, ProviderRole]
    payload: Mapping[str, Any]

    @property
    def self_sha256(self) -> str:
        return str(self.payload["integrity"]["self_sha256"])

    def role(self, role: str) -> ProviderRole:
        try:
            return self.roles[role]
        except KeyError as exc:
            raise ValueError(f"provider role is not sealed in the plan: {role}") from exc

    def build_role_routes(
        self,
        *,
        catalog: ProviderCatalog,
        credentials_root: Path | None = None,
    ) -> dict[str, tuple[ContextProviderRoute, ...]]:
        root = resolve_credentials_root(credentials_root)
        if _file_sha256(catalog.source_path) != self.provider_catalog_physical_sha256:
            raise ValueError("provider catalog physical SHA256 differs from role plan")
        catalog_by_id = {profile.provider_id: profile for profile in catalog.profiles}
        result: dict[str, tuple[ContextProviderRoute, ...]] = {}
        for role_name in self.role_order:
            role = self.roles[role_name]
            routes: list[ContextProviderRoute] = []
            for profile_id in role.route_profile_order:
                sealed = self.route_profiles[profile_id]
                transport = catalog_by_id.get(sealed.provider_id)
                if transport is None:
                    raise ValueError(
                        f"role plan references unknown provider catalog id: {sealed.provider_id}"
                    )
                if transport.route_id != sealed.route_id or transport.adapter != sealed.adapter:
                    raise ValueError(
                        f"provider catalog transport identity drift for {sealed.profile_id}"
                    )
                api_key = _read_credential(root, transport.credential_file)
                routes.append(
                    transport.build_route(
                        api_key=api_key,
                        model_id=sealed.model_id,
                        model_family=sealed.model_family,
                        model_profile=sealed.model_profile,
                        independence_group=sealed.independence_group,
                        role_equivalence_group=sealed.role_equivalence_group,
                        thinking_level=sealed.thinking_level,
                        reasoning_effort=sealed.reasoning_effort,
                        temperature=sealed.temperature,
                        timeout_seconds=sealed.timeout_seconds,
                        max_attempts=sealed.transport_retry_cap + 1,
                        retry_backoff_seconds=sealed.retry_backoff_seconds,
                        max_output_tokens=role.max_output_tokens,
                        role_plan_sha256=self.self_sha256,
                        escalation_kind=role.escalation_kind,
                    )
                )
            result[role_name] = tuple(routes)
        return result

    def public_summary(self) -> dict[str, Any]:
        return {
            "schema_id": ROLE_PLAN_SCHEMA_ID,
            "schema_version": ROLE_PLAN_SCHEMA_VERSION,
            "plan_id": self.plan_id,
            "physical_sha256": self.physical_sha256,
            "self_sha256": self.self_sha256,
            "provider_catalog_physical_sha256": self.provider_catalog_physical_sha256,
            "candidate_replicate_cap": self.candidate_replicate_cap,
            "provider_request_cap_per_run": self.provider_request_cap_per_run,
            "role_order": list(self.role_order),
            "provider_calls": 0,
        }


def load_provider_role_plan(
    path: Path = DEFAULT_PROVIDER_ROLE_PLAN_PATH,
    *,
    expected_physical_sha256: str,
) -> ProviderRolePlan:
    source = Path(path)
    physical = _file_sha256(source)
    if not _SHA256.fullmatch(expected_physical_sha256):
        raise ValueError("expected provider role plan physical SHA256 is invalid")
    if physical != expected_physical_sha256:
        raise ValueError("provider role plan physical SHA256 mismatch")
    payload = load_json_file(source, require_object=True)
    normalized = validate_provider_role_plan(payload)
    return provider_role_plan_from_payload(
        normalized,
        physical_sha256=physical,
        source_path=source,
    )


def provider_role_plan_from_payload(
    payload: Mapping[str, Any],
    *,
    physical_sha256: str,
    source_path: Path = Path("<embedded-provider-role-plan>"),
) -> ProviderRolePlan:
    if not _SHA256.fullmatch(physical_sha256):
        raise ValueError("provider role plan physical SHA256 is invalid")
    normalized = validate_provider_role_plan(payload)
    profiles = {
        profile_id: _profile_from_payload(profile_id, normalized["route_profiles"][profile_id])
        for profile_id in normalized["profile_order"]
    }
    roles = {
        role_name: _role_from_payload(role_name, normalized["roles"][role_name])
        for role_name in normalized["role_order"]
    }
    return ProviderRolePlan(
        source_path=source_path,
        physical_sha256=physical_sha256,
        plan_id=str(normalized["plan_id"]),
        provider_catalog_physical_sha256=str(
            normalized["provider_catalog_physical_sha256"]
        ),
        candidate_replicate_cap=int(normalized["candidate_replicate_cap"]),
        provider_request_cap_per_run=int(normalized["provider_request_cap_per_run"]),
        profile_order=tuple(normalized["profile_order"]),
        route_profiles=profiles,
        role_order=tuple(normalized["role_order"]),
        roles=roles,
        payload=normalized,
    )


def validate_provider_role_plan(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_id",
        "schema_version",
        "plan_id",
        "provider_catalog_physical_sha256",
        "candidate_replicate_cap",
        "provider_request_cap_per_run",
        "profile_order",
        "route_profiles",
        "role_order",
        "roles",
        "final_decision_owner",
        "integrity",
    }
    _exact_keys(value, required, "provider role plan")
    if value["schema_id"] != ROLE_PLAN_SCHEMA_ID:
        raise ValueError("provider role plan schema_id is unsupported")
    if value["schema_version"] != ROLE_PLAN_SCHEMA_VERSION:
        raise ValueError("provider role plan schema_version is unsupported")
    plan_id = _string(value["plan_id"], "provider role plan plan_id")
    catalog_sha = value["provider_catalog_physical_sha256"]
    if not isinstance(catalog_sha, str) or not _SHA256.fullmatch(catalog_sha):
        raise ValueError("provider catalog physical SHA256 is invalid")
    candidate_cap = _integer(value["candidate_replicate_cap"], 1, 1, "candidate_replicate_cap")
    request_cap = _integer(value["provider_request_cap_per_run"], 1, 100_000, "provider_request_cap_per_run")
    profile_order = _string_sequence(value["profile_order"], "profile_order")
    role_order = _string_sequence(value["role_order"], "role_order")
    raw_profiles = _mapping(value["route_profiles"], "route_profiles")
    raw_roles = _mapping(value["roles"], "roles")
    if set(profile_order) != set(raw_profiles):
        raise ValueError("profile_order must contain every route profile exactly once")
    if set(role_order) != set(raw_roles):
        raise ValueError("role_order must contain every role exactly once")
    if set(role_order) != set(PROVIDER_ROLES):
        raise ValueError("provider role plan must seal every Context Substitution role")
    profiles = {
        profile_id: _validate_profile(profile_id, raw_profiles[profile_id])
        for profile_id in profile_order
    }
    roles = {
        role_name: _validate_role(role_name, raw_roles[role_name], profiles=profiles)
        for role_name in role_order
    }
    if value["final_decision_owner"] != "GLOBAL_TERMINOLOGY_VALIDATOR":
        raise ValueError("provider role plan cannot assign final glossary authority to C")
    integrity = _mapping(value["integrity"], "integrity")
    _exact_keys(integrity, {"self_sha256"}, "provider role plan integrity")
    recorded = integrity["self_sha256"]
    if not isinstance(recorded, str) or not _SHA256.fullmatch(recorded):
        raise ValueError("provider role plan self_sha256 is invalid")
    unhashed = copy.deepcopy(dict(value))
    unhashed["integrity"] = {}
    if _object_sha256(unhashed) != recorded:
        raise ValueError("provider role plan self-hash mismatch")
    return {
        "schema_id": ROLE_PLAN_SCHEMA_ID,
        "schema_version": ROLE_PLAN_SCHEMA_VERSION,
        "plan_id": plan_id,
        "provider_catalog_physical_sha256": catalog_sha,
        "candidate_replicate_cap": candidate_cap,
        "provider_request_cap_per_run": request_cap,
        "profile_order": list(profile_order),
        "route_profiles": profiles,
        "role_order": list(role_order),
        "roles": roles,
        "final_decision_owner": "GLOBAL_TERMINOLOGY_VALIDATOR",
        "integrity": {"self_sha256": recorded},
    }


def reject_protected_provider_overrides(
    environment: Mapping[str, str] | None = None,
) -> None:
    env = os.environ if environment is None else environment
    forbidden = sorted(
        key
        for key in env
        if key.startswith(_PROTECTED_ENV_PREFIX) and key != CREDENTIALS_ROOT_ENV
    )
    if forbidden:
        raise ValueError(
            "authorized role-plan run rejects provider semantic overrides: "
            + ", ".join(forbidden)
        )


def _validate_profile(profile_id: str, value: Any) -> dict[str, Any]:
    row = _mapping(value, f"route_profiles.{profile_id}")
    required = {
        "provider_id",
        "route_id",
        "adapter",
        "model_id",
        "model_family",
        "model_profile",
        "independence_group",
        "role_equivalence_group",
        "thinking_level",
        "reasoning_effort",
        "temperature",
        "timeout_seconds",
        "transport_retry_cap",
        "retry_backoff_seconds",
    }
    _exact_keys(row, required, f"route_profiles.{profile_id}")
    route_id = _string(row["route_id"], f"{profile_id}.route_id")
    if route_id not in PROVIDER_ROUTE_IDS:
        raise ValueError(f"{profile_id}: unsupported route_id")
    adapter = _string(row["adapter"], f"{profile_id}.adapter")
    if adapter not in {"google_genai", "openai_compatible"}:
        raise ValueError(f"{profile_id}: unsupported adapter")
    model_id = _string(row["model_id"], f"{profile_id}.model_id")
    if "latest" in model_id.casefold():
        raise ValueError(f"{profile_id}: latest model aliases are forbidden")
    model_family = _string(row["model_family"], f"{profile_id}.model_family")
    thinking = _nullable_enum(row["thinking_level"], _THINKING_LEVELS, f"{profile_id}.thinking_level")
    reasoning = _nullable_enum(row["reasoning_effort"], _REASONING_EFFORTS, f"{profile_id}.reasoning_effort")
    if adapter == "google_genai" and (thinking is None or reasoning is not None):
        raise ValueError(f"{profile_id}: Google profile requires thinking and forbids reasoning_effort")
    if adapter == "openai_compatible":
        if model_family.casefold().startswith("gemini"):
            if thinking is None or reasoning is not None:
                raise ValueError(
                    f"{profile_id}: Gemini-compatible profile requires thinking "
                    "and forbids reasoning_effort"
                )
        elif reasoning is None or thinking is not None:
            raise ValueError(
                f"{profile_id}: GPT-compatible profile requires reasoning_effort "
                "and forbids thinking"
            )
    retries = _integer(row["transport_retry_cap"], 0, 4, f"{profile_id}.transport_retry_cap")
    backoff = _number_sequence(row["retry_backoff_seconds"], f"{profile_id}.retry_backoff_seconds")
    if len(backoff) != retries:
        raise ValueError(f"{profile_id}: retry_backoff_seconds must match transport_retry_cap")
    temperature = _number(row["temperature"], 0, 2, f"{profile_id}.temperature")
    return {
        "provider_id": _string(row["provider_id"], f"{profile_id}.provider_id"),
        "route_id": route_id,
        "adapter": adapter,
        "model_id": model_id,
        "model_family": model_family,
        "model_profile": _string(row["model_profile"], f"{profile_id}.model_profile"),
        "independence_group": _string(row["independence_group"], f"{profile_id}.independence_group"),
        "role_equivalence_group": _string(row["role_equivalence_group"], f"{profile_id}.role_equivalence_group"),
        "thinking_level": thinking,
        "reasoning_effort": reasoning,
        "temperature": temperature,
        "timeout_seconds": _integer(row["timeout_seconds"], 1, 3_600, f"{profile_id}.timeout_seconds"),
        "transport_retry_cap": retries,
        "retry_backoff_seconds": list(backoff),
    }


def _validate_role(
    role_name: str,
    value: Any,
    *,
    profiles: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    row = _mapping(value, f"roles.{role_name}")
    required = {
        "prompt_version",
        "response_contract_id",
        "max_output_tokens",
        "semantic_role_call_cap_per_run",
        "provider_request_cap_per_semantic_call",
        "escalation_kind",
        "route_profile_order",
    }
    _exact_keys(row, required, f"roles.{role_name}")
    route_order = _string_sequence(row["route_profile_order"], f"roles.{role_name}.route_profile_order")
    if any(profile_id not in profiles for profile_id in route_order):
        raise ValueError(f"roles.{role_name} references an unknown route profile")
    equivalence_groups = {profiles[profile_id]["role_equivalence_group"] for profile_id in route_order}
    semantic_models = {
        (
            profiles[profile_id]["model_family"],
            profiles[profile_id]["model_profile"],
            profiles[profile_id]["thinking_level"],
            profiles[profile_id]["reasoning_effort"],
            profiles[profile_id]["temperature"],
        )
        for profile_id in route_order
    }
    if len(equivalence_groups) != 1 or len(semantic_models) != 1:
        raise ValueError(
            f"roles.{role_name}: automatic routes must be semantically equivalent"
        )
    escalation = _nullable_enum(row["escalation_kind"], _ESCALATION_KINDS, f"roles.{role_name}.escalation_kind")
    if role_name == "secondary_context_judge" and escalation != "SECONDARY_JUDGE_ESCALATION":
        raise ValueError("secondary_context_judge must seal SECONDARY_JUDGE_ESCALATION")
    if role_name == "pairwise_tiebreaker" and escalation != "HARD_CASE_ESCALATION":
        raise ValueError("pairwise_tiebreaker must seal HARD_CASE_ESCALATION")
    if role_name not in {"secondary_context_judge", "pairwise_tiebreaker"} and escalation is not None:
        raise ValueError(f"roles.{role_name}: cross-family escalation is not permitted")
    provider_cap = _integer(
        row["provider_request_cap_per_semantic_call"],
        1,
        20,
        f"roles.{role_name}.provider_request_cap_per_semantic_call",
    )
    maximum_requests = sum(
        int(profiles[profile_id]["transport_retry_cap"]) + 1
        for profile_id in route_order
    )
    if provider_cap != maximum_requests:
        raise ValueError(
            f"roles.{role_name}: request cap must equal sealed route/retry inventory"
        )
    return {
        "prompt_version": _string(row["prompt_version"], f"roles.{role_name}.prompt_version"),
        "response_contract_id": _string(row["response_contract_id"], f"roles.{role_name}.response_contract_id"),
        "max_output_tokens": _integer(row["max_output_tokens"], 1, 65_536, f"roles.{role_name}.max_output_tokens"),
        "semantic_role_call_cap_per_run": _integer(row["semantic_role_call_cap_per_run"], 1, 100_000, f"roles.{role_name}.semantic_role_call_cap_per_run"),
        "provider_request_cap_per_semantic_call": provider_cap,
        "escalation_kind": escalation,
        "route_profile_order": list(route_order),
    }


def _profile_from_payload(profile_id: str, row: Mapping[str, Any]) -> RoleRouteProfile:
    return RoleRouteProfile(
        profile_id=profile_id,
        provider_id=str(row["provider_id"]),
        route_id=str(row["route_id"]),
        adapter=str(row["adapter"]),
        model_id=str(row["model_id"]),
        model_family=str(row["model_family"]),
        model_profile=str(row["model_profile"]),
        independence_group=str(row["independence_group"]),
        role_equivalence_group=str(row["role_equivalence_group"]),
        thinking_level=row["thinking_level"],
        reasoning_effort=row["reasoning_effort"],
        temperature=float(row["temperature"]),
        timeout_seconds=int(row["timeout_seconds"]),
        transport_retry_cap=int(row["transport_retry_cap"]),
        retry_backoff_seconds=tuple(float(item) for item in row["retry_backoff_seconds"]),
    )


def _role_from_payload(role_name: str, row: Mapping[str, Any]) -> ProviderRole:
    return ProviderRole(
        role=role_name,
        prompt_version=str(row["prompt_version"]),
        response_contract_id=str(row["response_contract_id"]),
        max_output_tokens=int(row["max_output_tokens"]),
        semantic_role_call_cap_per_run=int(row["semantic_role_call_cap_per_run"]),
        provider_request_cap_per_semantic_call=int(row["provider_request_cap_per_semantic_call"]),
        escalation_kind=row["escalation_kind"],
        route_profile_order=tuple(str(item) for item in row["route_profile_order"]),
    )


def _read_credential(root: Path, filename: str) -> str:
    target = (root / filename).resolve(strict=True)
    if target.parent != root or not target.is_file():
        raise ValueError(f"credential file escapes credential root: {filename}")
    lines = [line.strip() for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 1 or any(character.isspace() for character in lines[0]):
        raise ValueError(f"credential file must contain exactly one token: {filename}")
    return lines[0]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _object_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(
            f"{label} keys mismatch; missing={sorted(expected - set(value))}, "
            f"unknown={sorted(set(value) - expected)}"
        )


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be a nonempty trimmed string")
    return value


def _string_sequence(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty list")
    result = tuple(_string(item, label) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must contain unique values")
    return result


def _number_sequence(value: Any, label: str) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return tuple(_number(item, 0, 60, label) for item in value)


def _integer(value: Any, minimum: int, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer between {minimum} and {maximum}")
    return value


def _number(value: Any, minimum: float, maximum: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return result


def _nullable_enum(value: Any, allowed: frozenset[str], label: str) -> str | None:
    if value is None:
        return None
    result = _string(value, label)
    if result not in allowed:
        raise ValueError(f"{label} is unsupported")
    return result


__all__ = [
    "DEFAULT_PROVIDER_ROLE_PLAN_PATH",
    "ProviderRole",
    "ProviderRolePlan",
    "ROLE_PLAN_SCHEMA_ID",
    "ROLE_PLAN_SCHEMA_VERSION",
    "RoleRouteProfile",
    "load_provider_role_plan",
    "provider_role_plan_from_payload",
    "reject_protected_provider_overrides",
    "validate_provider_role_plan",
]
