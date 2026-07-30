"""Frozen EV-01/EV-02 policies with no observed producer output."""

from __future__ import annotations

from typing import Any


D0_PREPARATION_ID = "evaluation-d0-preparation-5-senses-15-candidates-v1"
D0_AMENDMENT_ID = "evaluation-pre-d0-aggregate-limitation-v1"
D0_FROZEN_AT = "2026-07-30T10:00:00+07:00"
D0_SELECTION_POLICY_ID = "evaluation_d0_blind_hash_rank_v1"
D0_COHORT_SIZE = 5
D0_CANDIDATE_COUNT = 15
D0_CANDIDATES_PER_SENSE = 3


def aggregate_distribution() -> dict[str, dict[str, int]]:
    return {
        "development": {"ACCEPT": 68, "CONDITIONAL": 20, "REJECT": 2},
        "validation": {"ACCEPT": 26, "CONDITIONAL": 4, "REJECT": 0},
        "test": {"ACCEPT": 23, "CONDITIONAL": 7, "REJECT": 0},
    }


def non_estimable_natural_metrics() -> list[str]:
    return [
        "critical_error_recall",
        "false_auto_approval_rate_against_strict_negatives",
        "hard_rejection_accuracy",
        "negative_recall",
        "negative_challenge_production_threshold_claims",
        "specificity",
    ]


def development_metric_policy() -> dict[str, str]:
    return {
        "AUTO_APPROVED_coverage": "NOT_ESTIMABLE_IN_DEVELOPMENT_MODE",
        "AUTO_APPROVED_precision": "NOT_ESTIMABLE_IN_DEVELOPMENT_MODE",
        "certificate_metrics": "NOT_APPLICABLE",
        "hard_rejection_accuracy_without_eligible_negatives": "NOT_ESTIMABLE",
        "undefined_numeric_coercion": "FORBIDDEN_NEVER_ZERO",
    }


def adversarial_companion_protocol() -> dict[str, Any]:
    return {
        "schema_id": "EvaluationD0AdversarialCompanionProtocolV1",
        "schema_version": "1.0.0",
        "protocol_id": "evaluation-d0-adversarial-negative-companion-v1",
        "status": "PROTOCOL_FROZEN_CASE_SET_NOT_YET_AUTHORIZED",
        "required_case_families": [
            "candidate_induced_contradiction",
            "concept_mismatch",
            "insufficient_evidence",
            "popular_incorrect_calque",
            "split_required",
            "target_collision",
            "wrong_sense",
        ],
        "case_source": "SEPARATELY_REVIEWED_AUTHORITY_REQUIRED",
        "case_count": 0,
        "fabricated_cases": 0,
        "natural_and_adversarial_metrics_separate": True,
        "natural_prevalence_applied_to_adversarial": False,
        "gold_access_authorized": False,
    }


def result_table_shells() -> list[dict[str, Any]]:
    return [
        {"id": "D0-T01", "title": "Run inventory", "rows": "candidate and producer", "columns": ["planned", "attempted", "sealed", "missing"]},
        {"id": "D0-T02", "title": "Context Substitution metrics", "rows": "registered C metric", "columns": ["eligible_n", "estimate", "interval", "status"]},
        {"id": "D0-T03", "title": "Vietnamese Attestation metrics", "rows": "registered E metric", "columns": ["eligible_n", "estimate", "interval", "status"]},
        {"id": "D0-T04", "title": "Global development outputs", "rows": "status, gate and route", "columns": ["count", "proportion", "status"]},
        {"id": "D0-T05", "title": "Calls, retries and malformed responses", "rows": "producer and route", "columns": ["calls", "retries", "malformed", "sealed"]},
        {"id": "D0-T06", "title": "Latency, tokens and cost", "rows": "producer and route", "columns": ["latency_ms", "input_tokens", "output_tokens", "total_tokens", "cost_or_NA"]},
        {"id": "D0-T07", "title": "Status distribution", "rows": "producer status", "columns": ["count", "proportion", "missing"]},
        {"id": "D0-T08", "title": "Human agreement after authorized gold access", "rows": "agreement stratum", "columns": ["eligible_n", "raw_agreement", "cohen_kappa", "status"]},
        {"id": "D0-T09", "title": "Manual-review rate", "rows": "route", "columns": ["eligible_n", "manual_review_n", "rate", "interval"]},
        {"id": "D0-T10", "title": "Candidate error analysis", "rows": "frozen error category", "columns": ["count", "share", "evidence_refs_present"]},
    ]
