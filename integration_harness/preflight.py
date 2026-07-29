"""Cross-producer policy checks performed before Global execution."""

from __future__ import annotations

from typing import Any

from .errors import PolicyError
from .join import JoinedCandidate


def validate_preflight(candidates: tuple[JoinedCandidate, ...], *, mode: str) -> dict[str, Any]:
    if mode not in {"FIXTURE_CONFORMANCE", "REAL_DEVELOPMENT_ZERO_NETWORK", "REAL_DEVELOPMENT_REPLAY"}:
        raise PolicyError(f"unsupported V1 mode: {mode}")
    report: dict[str, Any] = {
        "schema_id": "IntegrationPreflightReportV1",
        "mode": mode,
        "candidate_count": len(candidates),
        "checks": [],
    }
    for candidate in candidates:
        for role in ("frozen_candidate", "constraints"):
            value = candidate.packages[role].value
            if value.get("binding_status") != "COMPLETE":
                raise PolicyError(f"{role} is not COMPLETE for {candidate.identity.candidate_id}")
        for role in ("context_evidence", "attestation_evidence"):
            value = candidate.packages[role].value
            if value.get("final_glossary_decision") is not None:
                raise PolicyError(f"{role} is not decision-neutral")
            if any(key in value for key in ("global_action", "global_decision", "action_policy")):
                raise PolicyError(f"{role} contains a Global-owned action field")
        report["checks"].append({"candidate_id": candidate.identity.candidate_id, "status": "PASS"})
    report["development_invariants"] = {
        "network_policy": "FORBIDDEN",
        "approval_score_must_be_null": True,
        "auto_approved_count": 0,
        "certificate_count": 0,
    }
    return report
