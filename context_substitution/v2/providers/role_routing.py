from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterable, Mapping, Sequence

from context_substitution.v2.contracts.common import sha256_text
from context_substitution.v2.contracts.validation import ContractValidationError
from context_substitution.v2.jsonio import StrictJSONError, loads_strict
from context_substitution.v2.providers.base import (
    ContextExecutionError,
    ContextProviderRoute,
    ProviderCallCollector,
    ProviderRawResponse,
    _attempt_audit,
    _utc_now,
    provider_failure_disposition,
    provider_provenance,
)
from context_substitution.v2.providers.ledger import (
    LEDGER_POLICY,
    ProviderResponseLedger,
)
from context_substitution.v2.providers.role_plan import ProviderRolePlan


_COMPLETE_OUTER_JSON_FENCE = re.compile(
    r"\A[ \t\r\n]*```json[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```[ \t\r\n]*\Z"
)


def _unwrap_complete_outer_json_fence(response_text: str) -> str:
    match = _COMPLETE_OUTER_JSON_FENCE.fullmatch(response_text)
    if match is None:
        return response_text
    body = match.group("body")
    if "```" in body:
        raise StrictJSONError(
            "provider response: nested Markdown fence is forbidden"
        )
    return body


def _normalize_known_top_level_response_key(value: Any) -> Any:
    if not isinstance(value, Mapping):
        if _contains_additional_properties_key(value):
            raise StrictJSONError(
                "provider response: nested additionalProperties is forbidden"
            )
        return value
    has_known_key = "additionalProperties" in value
    if has_known_key and value["additionalProperties"] is not False:
        raise StrictJSONError(
            "provider response: top-level additionalProperties must be false"
        )
    normalized = dict(value)
    if has_known_key:
        normalized.pop("additionalProperties")
    if _contains_additional_properties_key(normalized):
        raise StrictJSONError(
            "provider response: nested additionalProperties is forbidden"
        )
    return normalized if has_known_key else value


def _contains_additional_properties_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            key == "additionalProperties"
            or _contains_additional_properties_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_additional_properties_key(child) for child in value)
    return False


class RoleRoutedStructuredModel:
    """Execute only routes sealed for the requested semantic role."""

    def __init__(
        self,
        *,
        plan: ProviderRolePlan,
        role_routes: Mapping[str, Sequence[ContextProviderRoute]],
        response_ledger: ProviderResponseLedger | None = None,
        audit_run_id: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if set(role_routes) != set(plan.role_order):
            raise ValueError("role route inventory differs from the sealed role plan")
        normalized: dict[str, tuple[ContextProviderRoute, ...]] = {}
        unique_routes: dict[str, ContextProviderRoute] = {}
        for role_name in plan.role_order:
            routes = tuple(role_routes[role_name])
            role = plan.role(role_name)
            if not routes or len(routes) != len(role.route_profile_order):
                raise ValueError(f"{role_name}: route count differs from role plan")
            for route, profile_id in zip(routes, role.route_profile_order, strict=True):
                profile = plan.route_profiles[profile_id]
                if (
                    route.route_id != profile.route_id
                    or route.model_id != profile.model_id
                    or route.model_family != profile.model_family
                    or route.model_profile != profile.model_profile
                    or route.independence_group != profile.independence_group
                    or route.role_equivalence_group != profile.role_equivalence_group
                    or route.effective_generation_config
                    != {
                        **profile.effective_generation_config,
                        "max_output_tokens": role.max_output_tokens,
                        "timeout_seconds": profile.timeout_seconds,
                    }
                    or route.role_plan_sha256 != plan.self_sha256
                    or route.escalation_kind != role.escalation_kind
                ):
                    raise ValueError(f"{role_name}: built route differs from sealed profile")
                unique_routes.setdefault(route.route_id, route)
            normalized[role_name] = routes
        self.plan = plan
        self.role_routes = normalized
        self.routes = tuple(unique_routes.values())
        self.response_ledger = response_ledger
        self.audit_run_id = audit_run_id
        self._sleep = sleep
        self.successful_calls: list[dict[str, Any]] = []
        self.attempted_calls: list[dict[str, Any]] = []
        self._semantic_role_calls = {role: 0 for role in plan.role_order}
        self._provider_request_count = 0
        self._active_collector: ContextVar[ProviderCallCollector | None] = ContextVar(
            f"context_role_provider_collector_{id(self)}", default=None
        )

    @property
    def raw_response_ledger_policy(self) -> str:
        return LEDGER_POLICY if self.response_ledger is not None else "NOT_CONFIGURED_DEVELOPMENT"

    @property
    def provider_role_plan_payload(self) -> dict[str, Any]:
        return dict(self.plan.payload)

    @property
    def provider_role_plan_physical_sha256(self) -> str:
        return self.plan.physical_sha256

    @contextmanager
    def collect_calls(self) -> Iterable[ProviderCallCollector]:
        if self._active_collector.get() is not None:
            raise RuntimeError("provider call collector is already active")
        collector = ProviderCallCollector(successful_calls=[], attempted_calls=[])
        token = self._active_collector.set(collector)
        try:
            yield collector
        finally:
            self._active_collector.reset(token)

    def call(
        self,
        *,
        role: str,
        prompt_version: str,
        system_prompt: str,
        payload: Mapping[str, Any],
        response_schema: Mapping[str, Any],
        validator: Callable[[Any], dict[str, Any]],
        tag: str,
        max_output_tokens: int = 2_048,
        excluded_routes: Iterable[str] = (),
        excluded_independence_groups: Iterable[str] = (),
        excluded_model_families: Iterable[str] = (),
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sealed_role = self.plan.role(role)
        if prompt_version != sealed_role.prompt_version:
            raise ContextExecutionError(f"{role}: prompt version differs from sealed role plan")
        if max_output_tokens != sealed_role.max_output_tokens:
            raise ContextExecutionError(f"{role}: output budget differs from sealed role plan")
        semantic_index = self._next_semantic_role_call(role, sealed_role.semantic_role_call_cap_per_run)
        excluded = frozenset(excluded_routes)
        excluded_groups = {str(value).casefold() for value in excluded_independence_groups}
        excluded_families = {str(value).casefold() for value in excluded_model_families}
        available = [
            route
            for route in self.role_routes[role]
            if route.route_id not in excluded
            and route.independence_group not in excluded_groups
            and route.model_family not in excluded_families
        ]
        if not available:
            raise ContextExecutionError(f"{role}: no sealed provider route remains")
        if len({route.role_equivalence_group for route in available}) != 1:
            raise ContextExecutionError(f"{role}: automatic cross-family failover is forbidden")

        effective_system_prompt = _sealed_system_prompt(system_prompt, available[0])
        user_payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        schema_json = json.dumps(
            response_schema,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        prompt_sha256 = sha256_text(
            "\n".join(
                (prompt_version, effective_system_prompt, user_payload_json, schema_json)
            )
        )
        request_sha256 = sha256_text(user_payload_json)
        failures: list[str] = []
        requests_for_call = 0

        for route_index, route in enumerate(available):
            failover_from = None if route_index == 0 else available[route_index - 1].route_id
            for transport_retry_index in range(route.max_attempts):
                requests_for_call += 1
                if requests_for_call > sealed_role.provider_request_cap_per_semantic_call:
                    raise ContextExecutionError(f"{role}: provider request cap exhausted")
                request_index = self._next_provider_request()
                started_at = _utc_now()
                raw: ProviderRawResponse | None = None
                raw_fields: dict[str, Any] = {
                    "raw_response_ref": None,
                    "raw_response_sha256": None,
                    "raw_response_storage_status": "UNAVAILABLE",
                }
                response_text: str | None = None
                try:
                    raw = route.sender(
                        system_prompt=effective_system_prompt,
                        user_payload_json=user_payload_json,
                        response_schema=response_schema,
                        max_output_tokens=max_output_tokens,
                        tag=tag,
                    )
                    response_text = raw.text or json.dumps(
                        dict(raw.payload or {}),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    raw_fields = self._capture(response_text)
                    parsed: Any = (
                        dict(raw.payload)
                        if raw.payload is not None
                        else loads_strict(
                            _unwrap_complete_outer_json_fence(response_text),
                            source=f"provider:{role}:{tag}",
                        )
                    )
                    parsed = _normalize_known_top_level_response_key(parsed)
                    validated = validator(parsed)
                    provenance = provider_provenance(
                        route=route,
                        role=role,
                        prompt_version=prompt_version,
                        prompt_sha256=prompt_sha256,
                        response_text=response_text,
                        raw=raw,
                    )
                    self._record_success(provenance)
                    self._record_attempt(
                        {
                            **provenance,
                            **raw_fields,
                            **self._role_attempt_fields(
                                route=route,
                                role=role,
                                route_attempt_index=route_index,
                                transport_retry_index=transport_retry_index,
                                equivalent_failover_from=failover_from,
                                semantic_role_call_index=semantic_index,
                                provider_request_index=request_index,
                                provider_status_code=_provider_status_code(raw),
                                failure_disposition="ACCEPTED",
                                safe_error_code=None,
                            ),
                            "accepted": True,
                            "failure_kind": None,
                        },
                        audit=self._audit(
                            tag=tag,
                            request_sha256=request_sha256,
                            request_index=request_index,
                            started_at=started_at,
                        ),
                    )
                    return validated, provenance
                except (
                    ContractValidationError,
                    ContextExecutionError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    failures.append(f"{route.route_id}:{exc.__class__.__name__}")
                    disposition = _next_disposition(
                        route_index=route_index,
                        route_count=len(available),
                        transport_retry_index=transport_retry_index,
                        max_attempts=route.max_attempts,
                    )
                    self._record_rejection(
                        route=route,
                        role=role,
                        prompt_version=prompt_version,
                        prompt_sha256=prompt_sha256,
                        response_text=response_text,
                        raw=raw,
                        raw_fields=raw_fields,
                        failure=exc,
                        failure_disposition=disposition,
                        route_attempt_index=route_index,
                        transport_retry_index=transport_retry_index,
                        equivalent_failover_from=failover_from,
                        semantic_role_call_index=semantic_index,
                        provider_request_index=request_index,
                        audit=self._audit(
                            tag=tag,
                            request_sha256=request_sha256,
                            request_index=request_index,
                            started_at=started_at,
                        ),
                    )
                    if transport_retry_index + 1 < route.max_attempts:
                        self._pause(route, transport_retry_index)
                        continue
                    break
                except Exception as exc:
                    classified = provider_failure_disposition(exc)
                    failures.append(f"{route.route_id}:{exc.__class__.__name__}")
                    if classified == "RAISE":
                        disposition = "HARD_STOP"
                    elif transport_retry_index + 1 < route.max_attempts and classified == "RETRY_ROUTE":
                        disposition = "RETRY_SAME_ROUTE"
                    elif route_index + 1 < len(available):
                        disposition = "EQUIVALENT_FAILOVER"
                    else:
                        disposition = "EXHAUSTED"
                    self._record_rejection(
                        route=route,
                        role=role,
                        prompt_version=prompt_version,
                        prompt_sha256=prompt_sha256,
                        response_text=response_text,
                        raw=raw,
                        raw_fields=raw_fields,
                        failure=exc,
                        failure_disposition=disposition,
                        route_attempt_index=route_index,
                        transport_retry_index=transport_retry_index,
                        equivalent_failover_from=failover_from,
                        semantic_role_call_index=semantic_index,
                        provider_request_index=request_index,
                        audit=self._audit(
                            tag=tag,
                            request_sha256=request_sha256,
                            request_index=request_index,
                            started_at=started_at,
                        ),
                    )
                    if disposition == "HARD_STOP":
                        raise ContextExecutionError(
                            f"{role}: ambiguous provider outcome; automatic replay forbidden"
                        ) from exc
                    if disposition == "RETRY_SAME_ROUTE":
                        self._pause(route, transport_retry_index)
                        continue
                    break
        rendered = ", ".join(failures) if failures else "no route attempted"
        raise ContextExecutionError(
            f"{role}: sealed provider routes exhausted ({rendered})"
        )

    def _capture(self, text: str) -> dict[str, Any]:
        if self.response_ledger is not None:
            return self.response_ledger.capture(text)
        return {
            "raw_response_ref": None,
            "raw_response_sha256": sha256_text(text),
            "raw_response_storage_status": "NOT_CONFIGURED",
        }

    def _next_semantic_role_call(self, role: str, cap: int) -> int:
        current = self._semantic_role_calls[role] + 1
        if current > cap:
            raise ContextExecutionError(f"{role}: semantic role call cap exhausted")
        self._semantic_role_calls[role] = current
        return current

    def _next_provider_request(self) -> int:
        current = self._provider_request_count + 1
        if current > self.plan.provider_request_cap_per_run:
            raise ContextExecutionError("provider request cap per run exhausted")
        self._provider_request_count = current
        return current

    def _record_success(self, provenance: Mapping[str, Any]) -> None:
        row = dict(provenance)
        self.successful_calls.append(row)
        collector = self._active_collector.get()
        if collector is not None:
            collector.successful_calls.append(dict(row))

    def _record_attempt(
        self,
        attempt: Mapping[str, Any],
        *,
        audit: Mapping[str, Any],
    ) -> None:
        row = dict(attempt)
        self.attempted_calls.append(row)
        if self.response_ledger is not None:
            self.response_ledger.record_attempt(row, audit=audit)
        collector = self._active_collector.get()
        if collector is not None:
            collector.attempted_calls.append(dict(row))

    def _record_rejection(
        self,
        *,
        route: ContextProviderRoute,
        role: str,
        prompt_version: str,
        prompt_sha256: str,
        response_text: str | None,
        raw: ProviderRawResponse | None,
        raw_fields: Mapping[str, Any],
        failure: Exception,
        failure_disposition: str,
        route_attempt_index: int,
        transport_retry_index: int,
        equivalent_failover_from: str | None,
        semantic_role_call_index: int,
        provider_request_index: int,
        audit: Mapping[str, Any],
    ) -> None:
        if raw is not None and response_text is not None:
            base = provider_provenance(
                route=route,
                role=role,
                prompt_version=prompt_version,
                prompt_sha256=prompt_sha256,
                response_text=response_text,
                raw=raw,
            )
        else:
            base = {
                "provider_route_id": route.route_id,
                "model_id": route.model_id,
                "model_family": route.model_family,
                "independence_group": route.independence_group,
                "role": role,
                "prompt_version": prompt_version,
                "prompt_sha256": prompt_sha256,
                "response_sha256": None,
                "request_id": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "total_tokens": 0,
                "cached": False,
                "latency_ms": 0,
            }
        self._record_attempt(
            {
                **base,
                **dict(raw_fields),
                **self._role_attempt_fields(
                    route=route,
                    role=role,
                    route_attempt_index=route_attempt_index,
                    transport_retry_index=transport_retry_index,
                    equivalent_failover_from=equivalent_failover_from,
                    semantic_role_call_index=semantic_role_call_index,
                    provider_request_index=provider_request_index,
                    provider_status_code=_exception_status_code(failure),
                    failure_disposition=failure_disposition,
                    safe_error_code=_safe_error_code(failure),
                ),
                "accepted": False,
                "failure_kind": failure.__class__.__name__,
            },
            audit=audit,
        )

    def _role_attempt_fields(
        self,
        *,
        route: ContextProviderRoute,
        role: str,
        route_attempt_index: int,
        transport_retry_index: int,
        equivalent_failover_from: str | None,
        semantic_role_call_index: int,
        provider_request_index: int,
        provider_status_code: int | None,
        failure_disposition: str,
        safe_error_code: str | None,
    ) -> dict[str, Any]:
        return {
            "model_profile": route.model_profile,
            "role_equivalence_group": route.role_equivalence_group,
            "role_plan_sha256": self.plan.self_sha256,
            "effective_generation_config": route.effective_generation_config,
            "escalation_kind": self.plan.role(role).escalation_kind,
            "candidate_replicate_index": 0,
            "semantic_role_call_index": semantic_role_call_index,
            "provider_request_index": provider_request_index,
            "route_attempt_index": route_attempt_index,
            "transport_retry_index": transport_retry_index,
            "equivalent_failover_from": equivalent_failover_from,
            "provider_status_code": provider_status_code,
            "failure_disposition": failure_disposition,
            "safe_error_code": safe_error_code,
            "budget_units_consumed": 1,
        }

    def _audit(
        self,
        *,
        tag: str,
        request_sha256: str,
        request_index: int,
        started_at: str,
    ) -> dict[str, Any]:
        return _attempt_audit(
            audit_run_id=self.audit_run_id,
            tag=tag,
            request_sha256=request_sha256,
            retry_index=request_index - 1,
            started_at=started_at,
            completed_at=_utc_now(),
        )

    def _pause(self, route: ContextProviderRoute, retry_index: int) -> None:
        delay = route.retry_backoff_seconds[retry_index]
        if delay:
            self._sleep(delay)


def _sealed_system_prompt(
    system_prompt: str,
    route: ContextProviderRoute,
) -> str:
    config = route.effective_generation_config
    thinking = config["thinking_level"] or "null"
    reasoning = config["reasoning_effort"] or "null"
    temperature = format(float(config["temperature"]), ".15g")
    return (
        f"{system_prompt.rstrip()}\n\n"
        "Sealed generation configuration: "
        f"thinking_level={thinking}; reasoning_effort={reasoning}; "
        f"temperature={temperature}."
    )


def _next_disposition(
    *,
    route_index: int,
    route_count: int,
    transport_retry_index: int,
    max_attempts: int,
) -> str:
    if transport_retry_index + 1 < max_attempts:
        return "RETRY_SAME_ROUTE"
    if route_index + 1 < route_count:
        return "EQUIVALENT_FAILOVER"
    return "EXHAUSTED"


def _exception_status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(exc, "code", None)
    return status if isinstance(status, int) and not isinstance(status, bool) else None


def _provider_status_code(raw: ProviderRawResponse) -> int | None:
    del raw
    return None


def _safe_error_code(exc: Exception) -> str:
    status = _exception_status_code(exc)
    suffix = "" if status is None else f"_{status}"
    return f"{exc.__class__.__name__.upper()}{suffix}"[:120]


__all__ = ["RoleRoutedStructuredModel"]
