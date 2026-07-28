"""Versioned cost telemetry without assuming unavailable provider prices."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Mapping, Sequence

from ..config import PricingConfig


COST_REPORT_SCHEMA_ID = "VietnameseAttestationCostReportV1"
COST_REPORT_SCHEMA_VERSION = "1.0.0"


def build_cost_report(
    *,
    pricing: PricingConfig,
    search_provider_ids: Sequence[str],
    search_attempts: int,
    search_successes: int,
    judge_attempts: Sequence[Mapping[str, Any]],
    fetch_count: int,
    judged_cluster_count: int,
    accepted_cluster_count: int,
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    search_prices = dict(pricing.search_cost_per_request)
    input_prices = dict(pricing.judge_input_cost_per_million)
    output_prices = dict(pricing.judge_output_cost_per_million)
    by_route: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "attempt_count": 0,
            "accepted_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
    )
    for attempt in judge_attempts:
        route = str(attempt["route_id"])
        row = by_route[route]
        row["attempt_count"] += 1
        row["accepted_count"] += int(attempt["outcome"] == "ACCEPTED")
        row["input_tokens"] += int(attempt["input_tokens"])
        row["output_tokens"] += int(attempt["output_tokens"])
    route_rows: list[dict[str, Any]] = []
    known_costs: list[float] = []
    unknown_price = False
    for route, row in sorted(by_route.items()):
        if route in input_prices and route in output_prices:
            estimated = (
                row["input_tokens"] * input_prices[route]
                + row["output_tokens"] * output_prices[route]
            ) / 1_000_000
            estimated_value: float | None = round(estimated, 9)
            known_costs.append(estimated)
            price_status = "KNOWN"
        else:
            estimated_value = None
            price_status = "UNKNOWN"
            unknown_price = True
        route_rows.append(
            {
                "route_id": route,
                **row,
                "estimated_cost": estimated_value,
                "price_status": price_status,
            }
        )
    search_known = all(
        provider_id in search_prices for provider_id in search_provider_ids
    )
    search_cost = (
        round(
            sum(search_prices[provider_id] for provider_id in search_provider_ids)
            * search_attempts
            / max(1, len(search_provider_ids)),
            9,
        )
        if search_known
        else None
    )
    if search_cost is None:
        unknown_price = True
    else:
        known_costs.append(search_cost)
    total_cost = None if unknown_price else round(sum(known_costs), 9)
    return {
        "schema_id": COST_REPORT_SCHEMA_ID,
        "schema_version": COST_REPORT_SCHEMA_VERSION,
        "pricing_policy_version": pricing.policy_version,
        "currency": pricing.currency,
        "effective_date": pricing.effective_date,
        "search_requests": search_attempts,
        "search_successes": search_successes,
        "search_estimated_cost": search_cost,
        "judge_routes": route_rows,
        "judge_attempt_count": len(judge_attempts),
        "judge_input_tokens": sum(
            int(row["input_tokens"]) for row in judge_attempts
        ),
        "judge_output_tokens": sum(
            int(row["output_tokens"]) for row in judge_attempts
        ),
        "fetch_count": fetch_count,
        "elapsed_seconds": _elapsed_seconds(started_at, completed_at),
        "estimated_total_cost": total_cost,
        "cost_per_candidate": total_cost,
        "cost_per_judged_cluster": (
            None
            if total_cost is None or judged_cluster_count == 0
            else round(total_cost / judged_cluster_count, 9)
        ),
        "cost_per_accepted_cluster": (
            None
            if total_cost is None or accepted_cluster_count == 0
            else round(total_cost / accepted_cluster_count, 9)
        ),
        "price_status": "UNKNOWN" if unknown_price else "KNOWN",
    }


def _elapsed_seconds(started_at: str, completed_at: str) -> float:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    return round(max(0.0, (end - start).total_seconds()), 6)


__all__ = [
    "COST_REPORT_SCHEMA_ID",
    "COST_REPORT_SCHEMA_VERSION",
    "build_cost_report",
]
