"""Deterministic stage coverage derived from ledger events and artifacts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..common import LiveSchemaError, require_nonnegative_int

STAGE_NAMES = ("search", "fetch", "extraction", "language", "span", "judge")


def derive_coverage_from_ledger(
    events: Sequence[Mapping[str, Any]],
    *,
    counts: Mapping[str, Any],
) -> dict[str, Any]:
    """Build measured coverage; no stage receives an unconditional 1.0."""
    search_events = [row for row in events if row.get("event_kind") == "E_DISCOVERY_QUERY"]
    fetch_events = [
        row
        for row in events
        if row.get("event_kind") in {"E_DIRECT_FETCH_REQUEST", "E_FETCH_RETRY"}
    ]
    unique_fetches = {
        str(row.get("payload", {}).get("url", ""))
        for row in fetch_events
        if row.get("payload", {}).get("url")
    }
    raw = {
        "search": {
            "expected": counts.get("search_expected", 0),
            "attempted": len(search_events),
            "success": counts.get("search_success", len(search_events)),
            "required": bool(counts.get("search_required", False)),
        },
        "fetch": {
            "expected": counts.get("fetch_expected", 0),
            "attempted": len(unique_fetches),
            "success": counts.get("fetch_success", 0),
            "required": bool(counts.get("fetch_required", False)),
        },
        "extraction": {
            "expected": counts.get("extraction_expected", 0),
            "attempted": counts.get("extraction_attempted", 0),
            "success": counts.get("extraction_success", 0),
            "required": True,
        },
        "language": {
            "expected": counts.get("language_expected", 0),
            "attempted": counts.get("language_attempted", 0),
            "success": counts.get("language_success", 0),
            "required": True,
        },
        "span": {
            "expected": counts.get("span_expected", 0),
            "attempted": counts.get("span_attempted", 0),
            "success": counts.get("span_success", 0),
            "required": True,
        },
        "judge": {
            "expected": counts.get("judge_expected", 0),
            "attempted": counts.get("judge_attempted", 0),
            "success": counts.get("judge_success", 0),
            "required": True,
        },
    }
    stages = {name: _stage(name, **raw[name]) for name in STAGE_NAMES}
    required = [stage for stage in stages.values() if stage["required"]]
    measured = bool(required) and all(stage["measured"] for stage in required)
    overall = min((float(stage["fraction"]) for stage in required), default=0.0) if measured else 0.0
    return {
        "schema_id": "EAttestationCoverageV1",
        "schema_version": "1.0.0",
        "measured": measured,
        "overall_attestation_coverage": round(overall, 6),
        "stages": stages,
    }


def _stage(
    name: str,
    *,
    expected: Any,
    attempted: Any,
    success: Any,
    required: bool,
) -> dict[str, Any]:
    expected_i = require_nonnegative_int(expected, path=f"$.coverage.{name}.expected")
    attempted_i = require_nonnegative_int(attempted, path=f"$.coverage.{name}.attempted")
    success_i = require_nonnegative_int(success, path=f"$.coverage.{name}.success")
    if success_i > attempted_i or (expected_i and attempted_i > expected_i):
        raise LiveSchemaError(f"coverage counts are inconsistent for {name}")
    if expected_i == 0:
        measured = not required
        fraction = 1.0 if measured else 0.0
    else:
        measured = True
        fraction = min(1.0, success_i / expected_i)
    return {
        "expected": expected_i,
        "attempted": attempted_i,
        "success": success_i,
        "required": bool(required),
        "measured": measured,
        "fraction": round(fraction, 6),
    }


__all__ = ["STAGE_NAMES", "derive_coverage_from_ledger"]
