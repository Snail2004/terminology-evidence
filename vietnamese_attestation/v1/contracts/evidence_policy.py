"""Shared acceptance semantics for Evidence E contracts and aggregation."""

from __future__ import annotations

from typing import Any, Mapping


STRONG_POSITIVE_POLICY_VERSION = "strong-positive-v1"
ATTESTATION_POLICY_VERSION = "attestation-v1.1"
MACHINE_TRANSLATION_POLICIES = frozenset(
    {"FLAG_ONLY", "DOWNWEIGHT", "EXCLUDE_FROM_STRONG_POSITIVE"}
)


def is_strong_positive_evidence(
    row: Mapping[str, Any],
    *,
    machine_translation_policy: str = "FLAG_ONLY",
) -> bool:
    if machine_translation_policy not in MACHINE_TRANSLATION_POLICIES:
        raise ValueError("unsupported machine-translation suspicion policy")
    judge = row["judge"]
    return bool(
        judge["judgeability"] == "JUDGEABLE"
        and judge["concept_relation"] == "SAME"
        and judge["domain_match"] is True
        and judge["candidate_role"] == "TECHNICAL_TERM"
        and row["source_tier"] != "X"
        and not (
            machine_translation_policy == "EXCLUDE_FROM_STRONG_POSITIVE"
            and judge["machine_translation_suspected"]
        )
    )


def is_related_supporting_evidence(row: Mapping[str, Any]) -> bool:
    judge = row["judge"]
    return bool(
        judge["judgeability"] == "JUDGEABLE"
        and judge["concept_relation"] == "RELATED"
        and judge["domain_match"] is True
        and judge["candidate_role"] == "TECHNICAL_TERM"
        and row["source_tier"] != "X"
    )


def rejection_reasons(row: Mapping[str, Any]) -> list[str]:
    judge = row["judge"]
    reasons: list[str] = []
    if judge["judgeability"] != "JUDGEABLE":
        reasons.append("JUDGE_UNAVAILABLE")
    if not judge["domain_match"]:
        reasons.append("DOMAIN_MISMATCH")
    if judge["candidate_role"] != "TECHNICAL_TERM":
        reasons.append("NON_TECHNICAL_ROLE")
    if judge["concept_relation"] != "SAME":
        reasons.append(f"CONCEPT_{judge['concept_relation']}")
    if row["source_tier"] == "X":
        reasons.append("SOURCE_UNUSABLE")
    return sorted(set(reasons))


__all__ = [
    "ATTESTATION_POLICY_VERSION",
    "MACHINE_TRANSLATION_POLICIES",
    "STRONG_POSITIVE_POLICY_VERSION",
    "is_related_supporting_evidence",
    "is_strong_positive_evidence",
    "rejection_reasons",
]
