from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Mapping

from .base import ContractValidationError
from .frozen_candidate import seal_frozen_candidate
from .output import PACKAGE_SCHEMA_VERSION, validate_attestation_package


SHARED_FROZEN_CANDIDATE_SCHEMA_ID = "FrozenCandidateContractV1"
SHARED_ATTESTATION_PACKAGE_SCHEMA_ID = "AttestationEvidencePackageV1"
SHARED_SCHEMA_VERSION = "1.1.0"

_GATE_SIGNAL_IDS = (
    "concept_mismatch",
    "contradiction",
    "judge_disagreement",
    "insufficient_evidence",
    "attestation_unjudgeable",
)

_DEFAULT_RUN_POLICY = {
    "attestation_policy_version": "attestation-v1.1",
    "query_policy_version": "query-v1",
    "source_policy_version": "source-tier-v2",
    "dedup_policy_version": "dedup-v2",
    "judge_policy_version": "attestation-judge-v1",
}


def validate_shared_frozen_candidate(
    payload: Mapping[str, Any],
    *,
    schema_dir: Path | None = None,
) -> dict[str, Any]:
    return _validate_shared_contract(
        payload,
        expected_schema_id=SHARED_FROZEN_CANDIDATE_SCHEMA_ID,
        expected_schema_version=SHARED_SCHEMA_VERSION,
        schema_dir=schema_dir,
    )


def validate_shared_attestation_package(
    payload: Mapping[str, Any],
    *,
    schema_dir: Path | None = None,
) -> dict[str, Any]:
    return _validate_shared_contract(
        payload,
        expected_schema_id=SHARED_ATTESTATION_PACKAGE_SCHEMA_ID,
        expected_schema_version=SHARED_SCHEMA_VERSION,
        schema_dir=schema_dir,
    )


def adapt_shared_frozen_candidate(
    payload: Mapping[str, Any],
    *,
    schema_dir: Path | None = None,
    run_policy: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    shared = validate_shared_frozen_candidate(payload, schema_dir=schema_dir)
    key = shared["candidate_key"]
    input_sha256 = shared["integrity"]["self_sha256"]
    policy = dict(run_policy or _DEFAULT_RUN_POLICY)
    return seal_frozen_candidate(
        {
            "source_contract_ref": {
                "schema_id": shared["schema_id"],
                "schema_version": shared["schema_version"],
                "artifact_ref": (
                    "artifact://terminology-contracts/frozen-candidate/"
                    f"{key['candidate_id']}/{input_sha256}"
                ),
                "artifact_sha256": input_sha256,
            },
            "candidate_id": key["candidate_id"],
            "candidate_version": key["candidate_version"],
            # The shared key has no separate term_id. This deterministic alias is
            # internal only and never changes the shared candidate key.
            "term_id": key["candidate_id"],
            "source_term": key["source_term"],
            "candidate_vi": key["candidate_vi"],
            "sense_id": key["sense_id"],
            "scope_id": key["scope_id"],
            "sense_contract": {
                "definition_en": shared["effective_definition_en"],
                "definition_review_status": "VERIFIED",
                "definition_provenance": [
                    key["effective_sense_contract_sha256"]
                ],
                "sense_inventory_version": key["sense_inventory_version"],
            },
            "known_surfaces": {
                "canonical": shared["surfaces"]["canonical_vi"],
                "validated_variants": shared["surfaces"][
                    "validated_variants_vi"
                ],
                "rejected_variants": shared["surfaces"][
                    "rejected_variants_vi"
                ],
            },
            "domain_profile": {
                "domain_name": shared["domain_profile"]["domain_id"],
                "vi_anchors": shared["domain_profile"]["anchors_vi"],
                "en_anchors": shared["domain_profile"]["anchors_en"],
            },
            "run_policy": policy,
        }
    )


def project_shared_attestation_package(
    internal_package: Mapping[str, Any],
    shared_frozen_candidate: Mapping[str, Any],
    *,
    schema_dir: Path | None = None,
) -> dict[str, Any]:
    shared_input = validate_shared_frozen_candidate(
        shared_frozen_candidate, schema_dir=schema_dir
    )
    rich = validate_attestation_package(internal_package)
    expected_internal = adapt_shared_frozen_candidate(
        shared_input, schema_dir=schema_dir
    )
    _require_internal_binding(rich, expected_internal)

    attestation = rich["attestation_evidence"]
    counts = attestation["counts"]
    evidence_rows = rich["accepted_evidence"] + rich["rejected_evidence"]
    refs_by_id = {
        row["evidence_id"]: _evidence_ref(row) for row in evidence_rows
    }
    package_sha256 = rich["integrity"]["package_sha256"]
    provenance = rich["provenance"]
    ledger_ref = {
        "evidence_id": f"attestation-ledger-{package_sha256[:24]}",
        "evidence_type": "OTHER",
        "uri": (
            "artifact://vietnamese-attestation/internal/"
            f"{package_sha256}"
        ),
        "sha256": package_sha256,
    }
    gate_signals = _gate_signals(
        rich, refs_by_id=refs_by_id, ledger_ref=ledger_ref
    )
    package = {
        "schema_id": SHARED_ATTESTATION_PACKAGE_SCHEMA_ID,
        "schema_version": SHARED_SCHEMA_VERSION,
        "candidate_key": copy.deepcopy(shared_input["candidate_key"]),
        "input_contract_sha256": shared_input["input_contract_sha256"],
        "features": copy.deepcopy(attestation["features"]),
        "stage_metrics": {
            **copy.deepcopy(attestation["coverage_breakdown"]),
            "unique_document_count": counts["unique_document_count"],
            "duplicate_cluster_count": counts["duplicate_cluster_count"],
            "independent_organization_count": counts[
                "independent_organization_count"
            ],
        },
        "flags": _shared_flags(attestation["flags"], gate_signals),
        "local_status": attestation["status"],
        "accepted_evidence_refs": [
            refs_by_id[row["evidence_id"]]
            for row in rich["accepted_evidence"]
        ],
        "rejected_evidence_refs": [
            refs_by_id[row["evidence_id"]]
            for row in rich["rejected_evidence"]
        ],
        "observed_variants": [
            {
                "surface_vi": row["surface"],
                "status": "PROPOSE_FOR_CST_VARIANT_CHECK",
                "evidence_refs": [
                    refs_by_id[evidence_id]
                    for evidence_id in row["evidence_ids"]
                ],
            }
            for row in rich["observed_variants"]
        ],
        "provenance": {
            "run_id": provenance["attestation_execution_id"],
            "started_at": provenance["started_at"],
            "completed_at": provenance["completed_at"],
            "component_id": "vietnamese-attestation",
            "component_version": PACKAGE_SCHEMA_VERSION,
            "policy_version": provenance["attestation_policy_version"],
            "prompt_hashes": {
                "judge": provenance["judge_prompt_sha256"]
            },
            "model_routes": _model_routes(provenance["judge_attempts"]),
            "source_artifact_hashes": {
                "dataset": shared_input["candidate_key"][
                    "dataset_manifest_sha256"
                ],
                "frozen_candidate": shared_input["integrity"][
                    "self_sha256"
                ],
                "input_contract": shared_input["input_contract_sha256"],
                "rich_attestation_ledger": package_sha256,
            },
            "raw_ledger_ref": ledger_ref,
            "notes": (
                "Shared projection of VietnameseAttestationPackageV1; "
                "the raw ledger reference binds the full replay package."
            ),
            "run_spec_id": provenance["run_spec_id"],
            "execution_config_sha256": provenance[
                "execution_config_sha256"
            ],
        },
        "gate_signals": gate_signals,
        "diagnostics": {
            "strong_positive_cluster_count": counts[
                "same_concept_cluster_count"
            ],
            "conflict_ratio": _conflict_ratio(counts),
        },
        "final_glossary_decision": None,
        "integrity": {"self_sha256": "0" * 64},
    }
    _, calculate_self_sha256 = _shared_api()
    package["integrity"]["self_sha256"] = calculate_self_sha256(package)
    return validate_shared_attestation_package(package, schema_dir=schema_dir)


def _require_internal_binding(
    package: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    expected_identity = {
        key: expected[key]
        for key in (
            "candidate_id",
            "candidate_version",
            "source_term",
            "candidate_vi",
            "sense_id",
            "scope_id",
        )
    }
    expected_identity["sense_inventory_version"] = expected[
        "sense_contract"
    ]["sense_inventory_version"]
    actual_identity = {key: package[key] for key in expected_identity}
    expected_sha256 = expected["integrity"]["frozen_candidate_sha256"]
    if (
        actual_identity != expected_identity
        or package["frozen_candidate_sha256"] != expected_sha256
    ):
        raise ContractValidationError(
            "shared_input_binding",
            "$.frozen_candidate_sha256",
            "internal package is not bound to the shared frozen candidate",
        )


def _evidence_ref(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": row["evidence_id"],
        "evidence_type": "ATTESTATION_SOURCE",
        "uri": row["canonical_url"],
        "sha256": row["content_sha256"],
    }


def _model_routes(attempts: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    routes: dict[tuple[str, str], dict[str, Any]] = {}
    for attempt in attempts:
        route_id = str(attempt["route_id"])
        model_id = str(attempt["model_id"])
        routes[(route_id, model_id)] = {
            "provider_id": route_id,
            "model_id": model_id,
            "model_family": model_id,
            "independence_group": route_id,
        }
    return [routes[key] for key in sorted(routes)]


def _gate_signals(
    package: Mapping[str, Any],
    *,
    refs_by_id: Mapping[str, Mapping[str, Any]],
    ledger_ref: Mapping[str, Any],
) -> list[dict[str, Any]]:
    attestation = package["attestation_evidence"]
    status = attestation["status"]
    counts = attestation["counts"]
    coverage = attestation["coverage_breakdown"]
    operational_flags = set(attestation["flags"])
    accepted_refs = [
        refs_by_id[row["evidence_id"]]
        for row in package["accepted_evidence"]
    ]
    different_refs = [
        refs_by_id[row["evidence_id"]]
        for row in package["rejected_evidence"]
        if row["judge"]["judgeability"] == "JUDGEABLE"
        and row["judge"]["candidate_role"] == "TECHNICAL_TERM"
        and row["judge"]["concept_relation"] == "DIFFERENT"
        and row["judge"]["domain_match"] is True
    ]
    all_refs = _unique_refs([*accepted_refs, *refs_by_id.values()])
    operational_coverage_keys = (
        "search_coverage",
        "fetch_coverage",
        "extraction_coverage",
        "language_coverage",
        "judge_coverage",
    )
    incomplete_coverage = [
        key for key in operational_coverage_keys if coverage[key] < 1
    ]
    insufficient = status == "WEAKLY_ATTESTED" or (
        status != "ATTESTED" and bool(incomplete_coverage)
    )
    insufficient_reasons = []
    if status == "WEAKLY_ATTESTED":
        insufficient_reasons.append("ATTESTATION_THRESHOLD_NOT_MET")
    insufficient_reasons.extend(
        f"{key.upper()}_INCOMPLETE" for key in incomplete_coverage
    )
    if insufficient and not insufficient_reasons:
        insufficient_reasons.append("INSUFFICIENT_EVIDENCE")

    unjudgeable = status == "ATTESTATION_UNJUDGEABLE"
    unjudgeable_reasons = sorted(
        operational_flags
        & {
            "JUDGE_ROUTE_EXHAUSTED",
            "PARTIAL_RETRIEVAL_COVERAGE",
            "SEARCH_PROVIDER_FAILED",
        }
    )
    if unjudgeable and not unjudgeable_reasons:
        unjudgeable_reasons = ["ATTESTATION_UNJUDGEABLE"]

    signal_rows = {
        "concept_mismatch": _signal(
            "concept_mismatch",
            asserted=bool(different_refs),
            reason_codes=["DOMAIN_MATCHED_DIFFERENT_CONCEPT"],
            evidence_refs=different_refs,
        ),
        "contradiction": _signal(
            "contradiction",
            asserted=status == "CONFLICTING_ATTESTATION",
            reason_codes=["SAME_AND_DIFFERENT_ATTESTATION"],
            evidence_refs=_unique_refs([*accepted_refs, *different_refs]),
        ),
        # The current E engine accepts the first schema-valid semantic result;
        # transport fallback is not semantic Judge disagreement.
        "judge_disagreement": _signal(
            "judge_disagreement",
            asserted=False,
            reason_codes=[],
            evidence_refs=[],
        ),
        "insufficient_evidence": _signal(
            "insufficient_evidence",
            asserted=insufficient,
            reason_codes=insufficient_reasons,
            evidence_refs=all_refs or [dict(ledger_ref)],
        ),
        "attestation_unjudgeable": _signal(
            "attestation_unjudgeable",
            asserted=unjudgeable,
            reason_codes=unjudgeable_reasons,
            evidence_refs=all_refs or [dict(ledger_ref)],
        ),
    }
    return [signal_rows[gate_id] for gate_id in _GATE_SIGNAL_IDS]


def _signal(
    gate_id: str,
    *,
    asserted: bool,
    reason_codes: list[str],
    evidence_refs: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "asserted": asserted,
        "reason_codes": sorted(set(reason_codes)) if asserted else [],
        "evidence_refs": _unique_refs(evidence_refs) if asserted else [],
    }


def _shared_flags(
    operational_flags: list[str],
    gate_signals: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    flags = {
        code: {
            "code": code,
            "severity": "WARNING",
            "message": None,
            "evidence_refs": [],
        }
        for code in operational_flags
    }
    for signal in gate_signals:
        if signal["asserted"] is not True:
            continue
        gate_id = str(signal["gate_id"])
        flags[gate_id] = {
            "code": gate_id,
            "severity": (
                "WARNING"
                if gate_id in {"insufficient_evidence", "judge_disagreement"}
                else "ERROR"
            ),
            "message": ", ".join(signal["reason_codes"]),
            "evidence_refs": copy.deepcopy(signal["evidence_refs"]),
        }
    return [flags[key] for key in sorted(flags)]


def _unique_refs(
    rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> list[dict[str, Any]]:
    refs: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row["evidence_id"]),
            str(row["evidence_type"]),
            str(row["uri"]),
            str(row["sha256"]),
        )
        refs[key] = dict(row)
    return [refs[key] for key in sorted(refs)]


def _conflict_ratio(counts: Mapping[str, int]) -> float:
    same = counts["same_concept_cluster_count"]
    different = counts["different_cluster_count"]
    denominator = same + different
    return round(different / denominator, 6) if denominator else 0.0


def _validate_shared_contract(
    payload: Mapping[str, Any],
    *,
    expected_schema_id: str,
    expected_schema_version: str,
    schema_dir: Path | None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ContractValidationError(
            "shared_contract_type", "$", "shared contract must be an object"
        )
    row = copy.deepcopy(dict(payload))
    if row.get("schema_id") != expected_schema_id:
        raise ContractValidationError(
            "shared_schema_id",
            "$.schema_id",
            f"expected {expected_schema_id}",
        )
    if row.get("schema_version") != expected_schema_version:
        raise ContractValidationError(
            "shared_schema_version",
            "$.schema_version",
            f"expected {expected_schema_version}",
        )
    validate_instance, _ = _shared_api()
    errors = validate_instance(row, schema_dir or _default_schema_dir())
    if errors:
        raise ContractValidationError(
            "shared_contract",
            "$",
            "; ".join(errors),
        )
    return row


def _default_schema_dir() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "terminology_contracts_v1"
        / "schemas"
    )


def _shared_api() -> tuple[
    Callable[[dict[str, Any], Path], list[str]],
    Callable[[dict[str, Any]], str],
]:
    try:
        from terminology_contracts.canonical import calculate_self_sha256
        from terminology_contracts.validation import validate_instance
    except ModuleNotFoundError:
        from terminology_contracts_v1.python.terminology_contracts.canonical import (
            calculate_self_sha256,
        )
        from terminology_contracts_v1.python.terminology_contracts.validation import (
            validate_instance,
        )
    return validate_instance, calculate_self_sha256


__all__ = [
    "SHARED_ATTESTATION_PACKAGE_SCHEMA_ID",
    "SHARED_FROZEN_CANDIDATE_SCHEMA_ID",
    "SHARED_SCHEMA_VERSION",
    "adapt_shared_frozen_candidate",
    "project_shared_attestation_package",
    "validate_shared_attestation_package",
    "validate_shared_frozen_candidate",
]
