from __future__ import annotations

from typing import Any, Mapping, Sequence

from context_substitution.v2.contracts.run import validate_context_substitution_run
from context_substitution.v2.integration.common import seal_object


PROJECTION_SCHEMA_ID = "ContextEvidenceProjectionDraftV2_2"
PROJECTION_SCHEMA_VERSION = "2.2.0"
PROJECTION_STATUS = "WAITING_FOR_CONTEXT_EVIDENCE_PACKAGE_V1_1"

_GATE_MAP = {
    "wrong_sense": {"WRONG_SENSE", "CONTEXT_WRONG_SENSE"},
    "concept_mismatch": {
        "SEMANTIC_EQUIVALENCE_LTE_2",
        "DOMAIN_SENSE_FIT_ZERO",
        "CONTEXT_SEMANTIC_MISMATCH",
    },
    "contradiction": {"SEMANTIC_CONTRADICTION", "CONTEXT_CONTRADICTION"},
    "missing_contrastive_context": {"MISSING_CONTRASTIVE_CONTEXT"},
    "incomplete_context_type_coverage": {"INCOMPLETE_CONTEXT_TYPE_COVERAGE"},
    "insufficient_evidence": {
        "INSUFFICIENT_VALID_SAME_SENSE_CONTEXTS",
        "CONTEXT_EVIDENCE_INSUFFICIENT",
    },
    "judge_disagreement": {"JUDGE_DISAGREEMENT"},
}


def project_context_evidence_draft(value: Mapping[str, Any]) -> dict[str, Any]:
    run = validate_context_substitution_run(value)
    packages = [_project_candidate(run, candidate) for candidate in run["candidates"]]
    report = {
        "schema_id": "ContextEvidenceProjectionReportV1",
        "schema_version": "1.0.0",
        "agent": "CONTEXT_SUBSTITUTION_C",
        "projection_schema_id": PROJECTION_SCHEMA_ID,
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "contract_target": "ContextEvidencePackageV1.1",
        "contract_authority_status": PROJECTION_STATUS,
        "input_contract_sha256": run["input_sha256"],
        "source_run_sha256": run["integrity"]["run_sha256"],
        "package_count": len(packages),
        "packages": packages,
        "final_glossary_decision": None,
        "integrity": {},
    }
    return seal_object(report, integrity_key="report_sha256")


def _project_candidate(
    run: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    if candidate["final_glossary_decision"] is not None:
        raise ValueError("Context Substitution cannot project a final glossary decision")
    package = {
        "schema_id": PROJECTION_SCHEMA_ID,
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "contract_target": "ContextEvidencePackageV1.1",
        "contract_authority_status": PROJECTION_STATUS,
        "candidate_id": candidate["candidate_id"],
        "sense_id": candidate["sense_id"],
        "scope_id": candidate["scope_id"],
        "input_contract_sha256": run["input_sha256"],
        "source_run_sha256": run["integrity"]["run_sha256"],
        "contextual_evidence": candidate["contextual_evidence"],
        "gate_signals": _gate_signals(candidate),
        "evidence_refs": _evidence_refs(candidate),
        "support_set_refs": _support_refs(candidate),
        "source_module": "CONTEXT_SUBSTITUTION_C",
        "final_glossary_decision": None,
        "integrity": {},
    }
    return seal_object(package, integrity_key="package_sha256")


def _gate_signals(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidate_flags = set(str(flag) for flag in candidate["context_flags"])
    context_flags = {
        str(flag)
        for row in candidate["context_results"]
        for flag in row["local_hard_flags"]
    }
    all_flags = candidate_flags | context_flags
    refs = _evidence_refs(candidate)
    return [
        {
            "gate_id": gate_id,
            "asserted": bool(all_flags & source_flags),
            "reason_codes": sorted(all_flags & source_flags),
            "evidence_refs": refs if all_flags & source_flags else [],
            "source_module": "CONTEXT_SUBSTITUTION_C",
        }
        for gate_id, source_flags in sorted(_GATE_MAP.items())
    ]


def _evidence_refs(candidate: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            f"context://{row['context_id']}"
            for row in candidate["context_results"]
        }
        | {
            f"context://{row['context_id']}"
            for row in candidate["excluded_contexts"]
        }
    )


def _support_refs(candidate: Mapping[str, Any]) -> list[str]:
    support = candidate["certificate_support_set"]
    refs: Sequence[str] = support.get("context_ids", ())
    return [f"context://{context_id}" for context_id in sorted(refs)]
