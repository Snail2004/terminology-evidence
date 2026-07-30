"""Deterministic E-local aggregation and evidence-package projection."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .common import LIVE_TOOL_SCHEMA_VERSION, LiveSchemaError, canonical_sha256, require_sha256, seal, verify_seal
from .schemas import LOCAL_STATUSES


POSITIVE_DOMAIN_RELATIONS = frozenset({"MATCH"})
INELIGIBLE_USAGE_TYPES = frozenset(
    {"GENERAL_LANGUAGE", "MENTION_ONLY", "METALINGUISTIC_REFERENCE"}
)


def positive_evidence_eligible(judge: Mapping[str, Any]) -> bool:
    """The single reviewed predicate for positive/accepted E evidence."""
    return (
        judge.get("judgeability") == "JUDGEABLE"
        and judge.get("concept_relation") == "SAME"
        and judge.get("domain_relation") in POSITIVE_DOMAIN_RELATIONS
        and judge.get("usage_type") == "TECHNICAL_TERM"
    )


def supporting_evidence_eligible(judge: Mapping[str, Any]) -> bool:
    """RELATED evidence may support a weak result, but is never accepted."""
    return (
        judge.get("judgeability") == "JUDGEABLE"
        and judge.get("concept_relation") == "RELATED"
        and judge.get("domain_relation") in POSITIVE_DOMAIN_RELATIONS
        and judge.get("usage_type") == "TECHNICAL_TERM"
    )


def contradictory_evidence_eligible(judge: Mapping[str, Any]) -> bool:
    return (
        judge.get("judgeability") == "JUDGEABLE"
        and judge.get("concept_relation") == "DIFFERENT"
        and judge.get("domain_relation") in POSITIVE_DOMAIN_RELATIONS
        and judge.get("usage_type") == "TECHNICAL_TERM"
    )


def aggregate_candidate(
    evidence_rows: Sequence[Mapping[str, Any]],
    judge_rows: Mapping[str, Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
    coverage_fraction: float | None = None,
    expected_evidence_count: int | None = None,
    coverage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the frozen status order; no glossary/global decision is made."""
    min_coverage = float(policy["min_coverage"])
    coverage_record = _coverage_record(
        coverage,
        coverage_fraction=coverage_fraction,
        minimum=min_coverage,
        observed=len(evidence_rows),
        expected=expected_evidence_count,
    )
    enriched: list[dict[str, Any]] = []
    for row in evidence_rows:
        evidence_id = str(row["evidence_id"])
        if evidence_id not in judge_rows:
            raise LiveSchemaError("missing Judge response for evidence")
        item = dict(row)
        item["judge"] = dict(judge_rows[evidence_id])
        enriched.append(item)
    judgeable = [row for row in enriched if row["judge"]["judgeability"] == "JUDGEABLE"]
    same = [row for row in enriched if positive_evidence_eligible(row["judge"])]
    related = [row for row in enriched if supporting_evidence_eligible(row["judge"])]
    different = [row for row in enriched if contradictory_evidence_eligible(row["judge"])]
    unresolved = [
        row
        for row in enriched
        if row["judge"]["judgeability"] != "JUDGEABLE"
        or row["judge"]["concept_relation"] == "UNCERTAIN"
    ]
    same_clusters = _clusters(same)
    related_clusters = _clusters(related)
    different_clusters = _clusters(different)
    organizations = {str(row.get("organization", row.get("source_id", ""))) for row in same}
    if not coverage_record["measured"] or not coverage_record["sufficient"] or unresolved:
        status = "ATTESTATION_UNJUDGEABLE"
    elif same_clusters and different_clusters:
        status = "CONFLICTING_ATTESTATION"
    elif len(same_clusters) >= int(policy["min_same_clusters_for_attested"]) and len(organizations) >= int(policy["min_organizations_for_attested"]):
        status = "ATTESTED"
    elif same or related:
        status = "WEAKLY_ATTESTED"
    else:
        status = "NOT_ATTESTED"
    if status not in LOCAL_STATUSES:
        raise LiveSchemaError("aggregation produced unsupported local status")
    counts = {
        "evidence_count": len(enriched),
        "judgeable_count": len(judgeable),
        "same_count": len(same),
        "related_count": len(related),
        "different_count": len(different),
        "uncertain_count": sum(1 for row in enriched if row["judge"]["concept_relation"] == "UNCERTAIN"),
        "independent_same_cluster_count": len(same_clusters),
        "independent_organization_count": len(organizations),
        "expected_evidence_count": expected_evidence_count,
        "positive_eligible_count": len(same),
        "supporting_eligible_count": len(related),
        "contradictory_eligible_count": len(different),
        "ineligible_count": len(enriched) - len(same) - len(related) - len(different),
    }
    return {
        "status": status,
        "coverage": coverage_record,
        "counts": counts,
        "evidence_rows": enriched,
        "clusters": _cluster_summary(enriched),
        "flags": _flags(status, enriched),
        "recommendation_to_global_validator": {
            "ATTESTED": "EVIDENCE_AVAILABLE",
            "WEAKLY_ATTESTED": "WEAK_EVIDENCE_AVAILABLE",
            "NOT_ATTESTED": "NO_ATTESTATION_OBSERVED",
            "CONFLICTING_ATTESTATION": "CONFLICTING_EVIDENCE",
            "ATTESTATION_UNJUDGEABLE": "EVIDENCE_UNJUDGEABLE",
        }[status],
    }


def build_attestation_package(
    *,
    request: Mapping[str, Any],
    aggregation: Mapping[str, Any],
    snapshot_manifest_sha256: str,
    ledger_refs: Mapping[str, Any],
    authority_refs: Mapping[str, Any],
    run_spec_id: str,
    started_at: str,
    completed_at: str,
    provider_role_plan_sha256: str,
    provider_role_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the official shared ``AttestationEvidencePackageV1`` shape.

    The projection intentionally retains ``final_glossary_decision = null``;
    only the Global Terminology Validator can make a glossary decision.
    """
    rows = [dict(row) for row in aggregation["evidence_rows"]]
    accepted = [row for row in rows if positive_evidence_eligible(row["judge"])]
    rejected = [row for row in rows if row not in accepted]
    candidate_key = authority_refs.get("candidate_key")
    input_contract_sha256 = authority_refs.get("input_contract_sha256")
    if not isinstance(candidate_key, Mapping) or not isinstance(input_contract_sha256, str):
        raise LiveSchemaError("shared candidate_key/input_contract_sha256 authority is required")
    expected_candidate_keys = {"candidate_id", "candidate_version", "source_term", "candidate_vi", "sense_id", "scope_id", "sense_inventory_version", "dataset_manifest_sha256", "effective_sense_contract_sha256"}
    if set(candidate_key) != expected_candidate_keys:
        raise LiveSchemaError("shared candidate_key shape is invalid")
    if candidate_key["candidate_id"] != request["candidate_id"] or candidate_key["sense_id"] != request["sense_id"] or candidate_key["candidate_vi"] != request["candidate_vi"] or candidate_key["source_term"] != request["term_en"]:
        raise LiveSchemaError("shared candidate_key differs from E run request")
    accepted_refs = [_evidence_ref(row) for row in accepted]
    rejected_refs = [_evidence_ref(row) for row in rejected]
    counts = aggregation["counts"]
    evidence_count = max(1, counts["evidence_count"])
    judgeable_count = counts["judgeable_count"]
    domain_match_count = sum(
        1
        for row in rows
        if row["judge"]["judgeability"] == "JUDGEABLE"
        and row["judge"]["domain_relation"] == "MATCH"
        and row["judge"]["usage_type"] == "TECHNICAL_TERM"
    )
    concept_score = (
        sum(1.0 for row in rows if positive_evidence_eligible(row["judge"]))
        + sum(0.5 for row in rows if supporting_evidence_eligible(row["judge"]))
    ) / evidence_count
    independent_clusters = len({str(row.get("independent_cluster_id", row["evidence_id"])) for row in rows})
    independent_orgs = len({str(row.get("organization_id", row.get("organization", ""))) for row in rows})
    strong_tier_count = sum(1 for row in accepted if row.get("source_tier") in {"A", "B"})
    coverage_fraction = float(aggregation["coverage"]["fraction"])
    features = {
        "E_authority": round(strong_tier_count / max(1, len(accepted)), 6),
        "E_independence": round(min(1.0, independent_clusters / 3.0), 6),
        "E_domain": round(domain_match_count / evidence_count, 6),
        "E_concept": round(concept_score, 6),
        "E_conventionality": round(min(1.0, independent_orgs / 3.0), 6),
        "E_coverage": round(coverage_fraction, 6),
    }
    stages = aggregation["coverage"].get("stages", {})
    stage_metrics = {
        "search_coverage": _stage_fraction(stages, "search"),
        "fetch_coverage": _stage_fraction(stages, "fetch"),
        "extraction_coverage": _stage_fraction(stages, "extraction"),
        "language_coverage": _stage_fraction(stages, "language"),
        "span_yield": _stage_fraction(stages, "span"),
        "judge_coverage": _stage_fraction(stages, "judge"),
        "unique_document_count": len({str(row.get("document_id", "")) for row in rows}),
        "duplicate_cluster_count": len({str(row.get("duplicate_cluster_id", row["evidence_id"])) for row in rows}),
        "independent_organization_count": independent_orgs,
    }
    raw_ledger_sha = str(ledger_refs.get("artifact_sha256", snapshot_manifest_sha256))
    ledger_evidence_ref = {"evidence_id": "ledger_" + canonical_sha256({"run_id": request["run_id"]})[:24], "evidence_type": "OTHER", "uri": f"artifact://e-live/{request['run_id']}/{ledger_refs.get('artifact_ref', 'evidence_ledger.json')}", "sha256": raw_ledger_sha}
    different_refs = [_evidence_ref(row) for row in rows if contradictory_evidence_eligible(row["judge"])]
    gate_signals = _gate_signals(aggregation["status"], accepted_refs, rejected_refs, different_refs, ledger_evidence_ref)
    flags = [_flag(code, accepted_refs + rejected_refs) for code in aggregation["flags"]]
    flags.extend(
        {"code": signal["gate_id"], "severity": "ERROR" if signal["gate_id"] in {"concept_mismatch", "contradiction", "attestation_unjudgeable"} else "WARNING", "message": ", ".join(signal["reason_codes"]), "evidence_refs": signal["evidence_refs"]}
        for signal in gate_signals
        if signal["asserted"]
    )
    package = {
        "schema_id": "AttestationEvidencePackageV1",
        "schema_version": "1.1.0",
        "candidate_key": dict(candidate_key),
        "input_contract_sha256": input_contract_sha256,
        "features": features,
        "stage_metrics": stage_metrics,
        "flags": flags,
        "local_status": aggregation["status"],
        "accepted_evidence_refs": accepted_refs,
        "rejected_evidence_refs": rejected_refs,
        "observed_variants": [],
        "provenance": {
            "run_id": request["run_id"],
            "started_at": started_at,
            "completed_at": completed_at,
            "component_id": "vietnamese-attestation",
            "component_version": "1.1.0",
            "policy_version": "e-live-controlled-corpus-v1",
            "prompt_hashes": {
                str(row["semantic_role"]): str(row["prompt_sha256"])
                for row in provider_role_plan["roles"]
            },
            "model_routes": [
                {
                    "provider_id": str(row["provider_id"]),
                    "model_id": str(row["model_id"]),
                    "model_family": str(row["same_family_group"]),
                    "independence_group": str(row["same_family_group"]),
                }
                for row in provider_role_plan["roles"]
            ],
            "source_artifact_hashes": {"dataset": candidate_key["dataset_manifest_sha256"], "input_contract": input_contract_sha256, "controlled_corpus_snapshot": snapshot_manifest_sha256, "evidence_ledger": raw_ledger_sha},
            "raw_ledger_ref": ledger_evidence_ref,
            "notes": "Zero-provider local-fixture E Live projection; no global decision.",
            "run_spec_id": run_spec_id,
            "execution_config_sha256": canonical_sha256({"request": run_spec_id, "provider_role_plan": provider_role_plan_sha256, "snapshot": snapshot_manifest_sha256}),
        },
        "gate_signals": gate_signals,
        "diagnostics": {
            "strong_positive_cluster_count": counts["independent_same_cluster_count"],
            "conflict_ratio": round(counts["different_count"] / evidence_count, 6),
        },
        "final_glossary_decision": None,
        "integrity": {},
    }
    return validate_attestation_evidence_package(seal(package))


def validate_attestation_evidence_package(value: Mapping[str, Any]) -> dict[str, Any]:
    exact = {"schema_id", "schema_version", "candidate_key", "input_contract_sha256", "features", "stage_metrics", "flags", "local_status", "accepted_evidence_refs", "rejected_evidence_refs", "observed_variants", "provenance", "gate_signals", "diagnostics", "final_glossary_decision", "integrity"}
    if set(value) != exact:
        raise LiveSchemaError("AttestationEvidencePackageV1 top-level shape mismatch")
    if value["schema_id"] != "AttestationEvidencePackageV1" or value["schema_version"] != "1.1.0":
        raise LiveSchemaError("AttestationEvidencePackageV1 identity mismatch")
    if value["local_status"] not in LOCAL_STATUSES or value["final_glossary_decision"] is not None:
        raise LiveSchemaError("attestation local/global status boundary is invalid")
    require_sha256(value["input_contract_sha256"], path="$.input_contract_sha256")
    gate_ids = [row.get("gate_id") for row in value["gate_signals"]]
    if gate_ids != ["concept_mismatch", "contradiction", "judge_disagreement", "insufficient_evidence", "attestation_unjudgeable"]:
        raise LiveSchemaError("attestation gate signal set/order mismatch")
    for feature in value["features"].values():
        if not isinstance(feature, (int, float)) or not 0 <= feature <= 1:
            raise LiveSchemaError("attestation feature is outside [0,1]")
    if not verify_seal(value):
        raise LiveSchemaError("AttestationEvidencePackageV1 self hash mismatch")
    return dict(value)


def _evidence_ref(row: Mapping[str, Any]) -> dict[str, Any]:
    return {"evidence_id": str(row["evidence_id"]), "evidence_type": "ATTESTATION_SOURCE", "uri": str(row.get("final_url", row.get("canonical_url", "artifact://e-live/evidence"))), "sha256": str(row["content_sha256"])}


def _flag(code: str, evidence_refs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"code": code, "severity": "WARNING", "message": None, "evidence_refs": [dict(row) for row in evidence_refs]}


def _gate_signals(status: str, accepted: Sequence[Mapping[str, Any]], rejected: Sequence[Mapping[str, Any]], different: Sequence[Mapping[str, Any]], fallback: Mapping[str, Any]) -> list[dict[str, Any]]:
    all_refs = [dict(row) for row in [*accepted, *rejected]]
    definitions = [
        ("concept_mismatch", bool(different), "DIFFERENT_CONCEPT_OBSERVED", different),
        ("contradiction", status == "CONFLICTING_ATTESTATION", "SAME_AND_DIFFERENT_ATTESTATION", all_refs),
        ("judge_disagreement", False, "JUDGE_DISAGREEMENT", []),
        ("insufficient_evidence", status in {"WEAKLY_ATTESTED", "NOT_ATTESTED"}, "ATTESTATION_THRESHOLD_NOT_MET", all_refs),
        ("attestation_unjudgeable", status == "ATTESTATION_UNJUDGEABLE", "ATTESTATION_UNJUDGEABLE", all_refs),
    ]
    return [
        {"gate_id": gate_id, "asserted": asserted, "reason_codes": [reason] if asserted else [], "evidence_refs": [dict(row) for row in (refs or [fallback])] if asserted else []}
        for gate_id, asserted, reason, refs in definitions
    ]


def _clusters(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {str(row.get("independent_cluster_id", row.get("duplicate_cluster_id", row["evidence_id"]))) for row in rows}


def _cluster_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        cluster = str(row.get("independent_cluster_id", row.get("duplicate_cluster_id", row["evidence_id"])))
        groups[cluster].append(row)
    return [
        {
            "independent_cluster_id": cluster,
            "member_evidence_ids": sorted(str(row["evidence_id"]) for row in members),
            "organization_ids": sorted({str(row.get("organization_id", row.get("organization", ""))) for row in members}),
            "concept_relations": sorted({str(row["judge"]["concept_relation"]) for row in members}),
        }
        for cluster, members in sorted(groups.items())
    ]


def _flags(status: str, rows: Sequence[Mapping[str, Any]]) -> list[str]:
    flags = {f"LOCAL_STATUS_{status}"}
    if any(row["judge"]["judgeability"] == "UNJUDGEABLE" for row in rows):
        flags.add("JUDGE_UNJUDGEABLE")
    if any(row["judge"]["concept_relation"] == "DIFFERENT" for row in rows):
        flags.add("DIFFERENT_CONCEPT_OBSERVED")
    if any(row["judge"].get("usage_type") in INELIGIBLE_USAGE_TYPES for row in rows):
        flags.add("NON_TECHNICAL_USAGE_REJECTED")
    if any(row["judge"].get("domain_relation") == "MISMATCH" for row in rows):
        flags.add("DOMAIN_MISMATCH_REJECTED")
    return sorted(flags)


def _coverage_record(
    coverage: Mapping[str, Any] | None,
    *,
    coverage_fraction: float | None,
    minimum: float,
    observed: int,
    expected: int | None,
) -> dict[str, Any]:
    if coverage is None:
        measured = coverage_fraction is not None
        fraction = float(coverage_fraction or 0.0)
        stages: dict[str, Any] = {}
    else:
        fraction = float(coverage.get("overall_attestation_coverage", -1))
        measured = bool(coverage.get("measured", False))
        stages = {str(key): dict(value) for key, value in dict(coverage.get("stages", {})).items()}
    if not 0 <= fraction <= 1:
        raise LiveSchemaError("coverage fraction must be in [0,1]")
    return {
        "observed": observed,
        "expected": expected,
        "fraction": round(fraction, 6),
        "minimum": minimum,
        "measured": measured,
        "sufficient": measured and fraction >= minimum,
        "stages": stages,
    }


def _stage_fraction(stages: Mapping[str, Any], name: str) -> float:
    stage = stages.get(name)
    if not isinstance(stage, Mapping) or not stage.get("measured"):
        return 0.0
    value = float(stage.get("fraction", 0.0))
    if not 0 <= value <= 1:
        raise LiveSchemaError(f"coverage stage {name} is outside [0,1]")
    return round(value, 6)


__all__ = [
    "aggregate_candidate",
    "build_attestation_package",
    "contradictory_evidence_eligible",
    "positive_evidence_eligible",
    "supporting_evidence_eligible",
    "validate_attestation_evidence_package",
]
