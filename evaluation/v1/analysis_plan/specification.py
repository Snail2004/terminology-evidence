"""Result-independent specification for the frozen 50/150 analysis plan."""

from __future__ import annotations

from typing import Any


PLAN_ID = "evaluation-analysis-plan-50-senses-150-candidates-v1"
FROZEN_AT = "2026-07-30T00:00:00+07:00"
BOOTSTRAP_SEED = 20260730
BOOTSTRAP_REPLICATES = 2000
STAGE_ORDER = ("D0", "D1", "V1", "T1")


def _metric(
    metric_id: str,
    *,
    family: str,
    unit: str,
    definition: str,
    denominator: str,
    interval: str,
    primary: bool = False,
) -> dict[str, Any]:
    return {
        "id": metric_id,
        "family": family,
        "unit": unit,
        "definition": definition,
        "denominator": denominator,
        "interval": interval,
        "primary": primary,
    }


def metric_specification() -> dict[str, list[dict[str, Any]]]:
    proportion = "wilson_95"
    grouped = "sense_cluster_bootstrap_95"
    descriptive = "descriptive_no_inferential_claim"
    return {
        "dataset_human_review": [
            _metric("gold_label_distribution", family="human", unit="count_and_proportion", definition="Count and share of each frozen gold label.", denominator="all reviewed candidates", interval=proportion),
            _metric("raw_reviewer_agreement", family="human", unit="proportion", definition="Share of reviewer pairs assigning the same raw label before adjudication.", denominator="candidate-reviewer pairs with both labels", interval=grouped),
            _metric("cohen_kappa", family="human", unit="score", definition="Pairwise Cohen kappa on the frozen label set.", denominator="candidate-reviewer pairs with both labels", interval=grouped),
            _metric("agreement_by_clarity_stratum", family="human", unit="proportion", definition="Raw agreement reported separately for clear, ambiguous and risk strata.", denominator="candidates in each preregistered stratum", interval=grouped),
            _metric("adjudication_rate", family="human", unit="proportion", definition="Share requiring adjudication after independent review.", denominator="all reviewed candidates", interval=proportion),
            _metric("human_unjudgeable_rate", family="human", unit="proportion", definition="Share finalized as HUMAN_UNJUDGEABLE.", denominator="all reviewed candidates", interval=proportion),
        ],
        "context_substitution_c": [
            _metric("c_trial_validity", family="context", unit="proportion", definition="Share of planned candidate-context trials with schema-valid judge output.", denominator="all planned C trials", interval=grouped),
            _metric("c_evidence_coverage", family="context", unit="proportion", definition="Share of candidates with the preregistered minimum eligible context evidence.", denominator="all C candidates", interval=grouped),
            _metric("c_support_mixed_contradiction_distribution", family="context", unit="count_and_proportion", definition="Distribution of support, mixed and contradiction outcomes.", denominator="eligible C candidate-context trials", interval=grouped),
            _metric("c_critical_gate_frequency", family="context", unit="proportion", definition="Share of candidates triggering any producer-owned critical gate.", denominator="all C candidates", interval=grouped),
            _metric("c_within_sense_top1_accuracy", family="context", unit="proportion", definition="Share of senses whose highest-ranked candidate matches the gold-accepted candidate set.", denominator="eligible senses with a judgeable gold target", interval=grouped),
            _metric("c_gold_cross_tab", family="context", unit="count", definition="Cross-tabulation of frozen C outcome and frozen gold label.", denominator="exactly joined C and gold candidates", interval=descriptive),
            _metric("c_escalation_rate", family="context", unit="proportion", definition="Share routed to human review by C evidence.", denominator="all C candidates", interval=grouped),
            _metric("c_request_token_cost", family="efficiency", unit="count_and_cost", definition="Requests, input/output/total tokens and sealed provider cost when present.", denominator="all recorded C attempts", interval=descriptive),
        ],
        "vietnamese_attestation_e": [
            _metric("e_controlled_corpus_coverage", family="attestation", unit="proportion", definition="Share with at least one eligible controlled-corpus source.", denominator="all E candidates", interval=grouped),
            _metric("e_brave_fallback_rate", family="attestation", unit="proportion", definition="Share requiring the preregistered Brave fallback route.", denominator="all E candidates", interval=grouped),
            _metric("e_eligible_source_count", family="attestation", unit="count_distribution", definition="Distribution of eligible source counts per candidate.", denominator="all E candidates", interval=grouped),
            _metric("e_independent_source_count", family="attestation", unit="count_distribution", definition="Distribution of independent source-cluster counts per candidate.", denominator="all E candidates", interval=grouped),
            _metric("e_sense_match_rate", family="attestation", unit="proportion", definition="Share of accepted source evidence judged to match the frozen sense.", denominator="eligible E evidence units", interval=grouped),
            _metric("e_domain_match_rate", family="attestation", unit="proportion", definition="Share of accepted source evidence matching the preregistered domain.", denominator="eligible E evidence units", interval=grouped),
            _metric("e_attestation_status_distribution", family="attestation", unit="count_and_proportion", definition="Distribution of ATTESTED_STRONG, ATTESTED_LIMITED, NO_EVIDENCE, UNJUDGEABLE and CONFLICTING.", denominator="all E candidates", interval=grouped),
        ],
        "global_pipeline": [
            _metric("auto_approved_precision", family="global", unit="proportion", definition="Gold ACCEPT share among AUTO_APPROVED candidates.", denominator="AUTO_APPROVED candidates with eligible gold", interval=proportion, primary=True),
            _metric("auto_approved_coverage", family="global", unit="proportion", definition="AUTO_APPROVED share of eligible candidates.", denominator="all candidates with eligible primary gold", interval=proportion, primary=True),
            _metric("false_approval_count", family="global", unit="count", definition="AUTO_APPROVED candidates with REJECT or SPLIT_REQUIRED gold.", denominator="AUTO_APPROVED candidates with eligible gold", interval=descriptive, primary=True),
            _metric("human_review_rate", family="global", unit="proportion", definition="Share routed to HUMAN_REVIEW.", denominator="all Global candidates", interval=proportion, primary=True),
            _metric("hard_rejection_accuracy", family="global", unit="proportion", definition="Gold-negative share among hard Global rejections.", denominator="hard-rejected candidates with eligible gold", interval=proportion, primary=True),
            _metric("global_development_status_distribution", family="global", unit="count_and_proportion", definition="Distribution of Global development statuses.", denominator="all Global development candidates", interval=grouped),
            _metric("global_gate_routing_distribution", family="gate", unit="count_and_proportion", definition="Distribution of sealed action-policy routes and triggering gates.", denominator="all Global candidates", interval=grouped),
            _metric("identity_join_success", family="pipeline", unit="proportion", definition="Share joining exactly on candidate, sense and scope identities.", denominator="all planned candidate identities", interval=proportion),
            _metric("replay_success", family="pipeline", unit="proportion", definition="Share reproducing exact persisted decisions under offline replay.", denominator="all persisted Global packages", interval=proportion),
            _metric("auto_approved_count_invariant", family="safety", unit="count", definition="AUTO_APPROVED count; preregistered expected value is zero before production calibration.", denominator="all Global candidates", interval=descriptive),
            _metric("certificate_count_invariant", family="safety", unit="count", definition="Production certificate count; preregistered expected value is zero.", denominator="all Global candidates", interval=descriptive),
        ],
    }


def planned_tables() -> list[dict[str, Any]]:
    return [
        {"id": "T01", "title": "Cohort and artifact availability", "splits": list(STAGE_ORDER), "rows": "artifact and exclusion reason", "columns": ["planned_n", "available_n", "missing_n", "excluded_n"]},
        {"id": "T02", "title": "Gold label distribution", "splits": list(STAGE_ORDER), "rows": "gold label", "columns": ["count", "proportion", "wilson_95"]},
        {"id": "T03", "title": "Human-review agreement", "splits": ["D0", "D1"], "rows": "overall and clear/ambiguous/risk", "columns": ["raw_agreement", "cohen_kappa", "sense_bootstrap_95", "adjudication_rate", "human_unjudgeable_rate"]},
        {"id": "T04", "title": "Context Substitution evidence and gates", "splits": list(STAGE_ORDER), "rows": "C metric", "columns": ["eligible_n", "excluded_n", "estimate", "confidence_interval"]},
        {"id": "T05", "title": "Context Substitution versus gold", "splits": ["D0", "D1", "V1", "T1"], "rows": "C outcome", "columns": ["ACCEPT", "CONDITIONAL", "REJECT", "SPLIT_REQUIRED", "HUMAN_UNJUDGEABLE"]},
        {"id": "T06", "title": "Vietnamese Attestation coverage and status", "splits": list(STAGE_ORDER), "rows": "E metric/status", "columns": ["eligible_n", "excluded_n", "estimate", "confidence_interval"]},
        {"id": "T07", "title": "Global statuses, gates and routing", "splits": list(STAGE_ORDER), "rows": "status, gate and route", "columns": ["count", "proportion", "confidence_interval"]},
        {"id": "T08", "title": "Primary gold-aligned performance", "splits": ["D1", "V1", "T1"], "rows": "primary metric", "columns": ["eligible_n", "excluded_n", "estimate", "wilson_95"]},
        {"id": "T09", "title": "Calibration and threshold stability", "splits": ["V1"], "rows": "bootstrap replicate summary", "columns": ["threshold", "median", "p2_5", "p97_5", "decision_flip_rate"]},
        {"id": "T10", "title": "Paired comparisons and decision flips", "splits": ["D1", "V1", "T1"], "rows": "preregistered paired comparison", "columns": ["discordant_a", "discordant_b", "mcnemar_p", "effect_size", "holm_adjusted_p"]},
        {"id": "T11", "title": "Requests, tokens and cost", "splits": list(STAGE_ORDER), "rows": "producer and route", "columns": ["requests", "input_tokens", "output_tokens", "total_tokens", "cost_or_NA"]},
        {"id": "T12", "title": "Missingness and exclusions audit", "splits": list(STAGE_ORDER), "rows": "frozen reason code", "columns": ["count", "share_of_planned", "artifact_refs_present", "reviewer_approval_present"]},
    ]


def gold_access_templates() -> list[dict[str, Any]]:
    scopes = {
        "D0": "development_canary_gold_only",
        "D1": "development_gold_only",
        "V1": "validation_gold_only",
        "T1": "held_out_test_gold_only",
    }
    prerequisites = {
        "D0": ["producer_outputs_sealed", "dataset_split_manifest_sealed", "analysis_plan_freeze_verified"],
        "D1": ["D0_access_closed", "D0_report_sealed", "allowed_amendments_refrozen"],
        "V1": ["D1_access_closed", "D1_analysis_sealed", "policy_refrozen"],
        "T1": ["V1_access_closed", "validation_report_sealed", "calibration_artifact_frozen"],
    }
    return [
        {
            "stage": stage,
            "sequence_number": index,
            "authorized_scope": scopes[stage],
            "prerequisites": prerequisites[stage],
            "required_hash_fields": [
                "analysis_plan_freeze_receipt_sha256",
                "dataset_split_manifest_sha256",
                "producer_bundle_manifest_sha256",
                "gold_bundle_manifest_sha256",
                "authorized_scope_sha256",
            ],
            "requires_human_authorization": True,
            "result_fields_forbidden": True,
        }
        for index, stage in enumerate(STAGE_ORDER)
    ]


def missing_data_policy() -> dict[str, Any]:
    return {
        "policy_id": "evaluation-missing-data-50-150-v1",
        "imputation": "NONE",
        "silent_complete_case_drop": False,
        "producer_failure_is_negative_gold": False,
        "unknown_cost_is_zero": False,
        "unknown_cost_representation": "NA",
        "primary_gold_excluded_labels": ["CONDITIONAL", "HUMAN_UNJUDGEABLE"],
        "allowed_exclusion_reasons": [
            "CORRUPT_ARTIFACT",
            "MISSING_REQUIRED_GOLD",
            "INVALID_SCHEMA",
            "UNRESOLVED_SENSE_AUTHORITY",
            "HUMAN_UNJUDGEABLE",
            "PROTOCOL_VIOLATION",
        ],
        "reporting": [
            "planned_n",
            "available_n",
            "eligible_n",
            "excluded_n_by_reason",
            "missing_n_by_artifact",
        ],
        "sensitivity_analysis": "report secondary usable-vs-not-usable mapping without replacing primary",
    }


def confidence_interval_policy() -> dict[str, Any]:
    return {
        "confidence_level": 0.95,
        "proportions": "wilson",
        "grouped_metrics": "sense_cluster_bootstrap_percentile",
        "bootstrap_group": "sense_id",
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "paired_binary": "mcnemar_exact_two_sided",
        "continuous_paired": "paired_sense_bootstrap",
        "formal_secondary_correction": "holm",
        "effect_size_required": True,
        "p_value_alone_prohibited": True,
        "D0_inference": "DESCRIPTIVE_ONLY_NO_CONFIRMATORY_CLAIM",
    }


def e_status_reporting_mapping() -> dict[str, list[str]]:
    """Map Reviewer-facing buckets to the exact Contract V1.1 E enums."""
    return {
        "ATTESTED_STRONG": ["ATTESTED"],
        "ATTESTED_LIMITED": ["WEAKLY_ATTESTED"],
        "NO_EVIDENCE": ["NOT_ATTESTED"],
        "UNJUDGEABLE": ["ATTESTATION_UNJUDGEABLE"],
        "CONFLICTING": ["CONFLICTING_ATTESTATION"],
    }
