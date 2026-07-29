"""Cross-producer policy checks performed before Global execution."""

from __future__ import annotations

from typing import Any

from .authority import (
    CONTRACTS_R1_HISTORICAL_REPLAY,
    CONTRACTS_R2_CURRENT,
    SYNTHETIC_LOCAL_CONFORMANCE,
    AuthoritySet,
)
from .errors import PolicyError
from .join import JoinedCandidate


def validate_preflight(
    candidates: tuple[JoinedCandidate, ...], *, mode: str, authority: AuthoritySet
) -> dict[str, Any]:
    if mode not in {"FIXTURE_CONFORMANCE", "REAL_DEVELOPMENT_ZERO_NETWORK", "REAL_DEVELOPMENT_REPLAY"}:
        raise PolicyError(f"unsupported V1 mode: {mode}")
    if authority.authority_mode == CONTRACTS_R1_HISTORICAL_REPLAY:
        raise PolicyError("historical R1 authority cannot start a new run")
    if mode == "FIXTURE_CONFORMANCE":
        if authority.authority_mode != SYNTHETIC_LOCAL_CONFORMANCE:
            raise PolicyError("fixture conformance requires synthetic authority")
        authority_status = "SYNTHETIC_LOCAL_CONFORMANCE"
    else:
        if authority.authority_mode != CONTRACTS_R2_CURRENT or authority.approval is None:
            raise PolicyError("real development requires exact R2 plus detached AR-1 approval")
        if authority.approval.payload.get("approval_status") != "ACCEPTED_FOR_AUTHORITY_PROMOTION":
            raise PolicyError("detached AR-1 approval is not accepted")
        authority_status = "R2_APPROVED_BY_DETACHED_AR1"
    report: dict[str, Any] = {
        "schema_id": "IntegrationPreflightReportV1",
        "mode": mode,
        "candidate_count": len(candidates),
        "authority_binding": {
            "authority_mode": authority.authority_mode,
            "compatibility_mode": authority.compatibility_mode,
            "authority_status": authority_status,
            "receipt_revision": authority.receipt_revision,
            "receipt_self_sha256": authority.receipt_self_sha256,
            "receipt_physical_sha256": authority.receipt_physical_sha256,
            "approval_binding_self_sha256": (
                authority.approval.binding_self_sha256 if authority.approval else None
            ),
            "approval_binding_physical_sha256": (
                authority.approval.binding_physical_sha256 if authority.approval else None
            ),
            "global_action_policy_sha256": authority.action_policy_sha256,
        },
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
