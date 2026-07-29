"""Small deterministic integration report projection."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def build_report(
    *,
    candidates: int,
    joined: int,
    failures: Iterable[Mapping[str, Any]],
    execution_results: Iterable[Mapping[str, Any]],
    replay_pass_count: int = 0,
    authority_warnings: Iterable[str] = (),
) -> dict[str, Any]:
    results = list(execution_results)
    decisions = Counter(str(item.get("decision")) for item in results)
    return {
        "schema_id": "SystemIntegrationReportV1",
        "candidate_count": candidates,
        "joined_count": joined,
        "failed_count": len(list(failures)),
        "failure_codes": sorted({str(item.get("error_code")) for item in failures}),
        "decision_distribution": dict(sorted(decisions.items())),
        "gate_distribution": {},
        "auto_approved_count": sum(item.get("decision") == "AUTO_APPROVED" for item in results),
        "certificate_count": sum(bool(item.get("certificate_sha256")) for item in results),
        "provider_network_calls": 0,
        "replay_pass_count": replay_pass_count,
        "authority_warnings": sorted(authority_warnings),
    }
