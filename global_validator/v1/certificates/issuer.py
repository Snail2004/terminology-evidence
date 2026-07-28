from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from terminology_contracts.integrity import seal_self_hash
from terminology_contracts.registries import GATE_IDS
from terminology_contracts.validation import validate_instance

from ..calibration import FrozenScore
from ..config import ExecutionMode, RunConfig
from ..errors import CertificateBindingError


def build_certificate(
    *,
    global_input: Mapping[str, Any],
    gate_results: Mapping[str, Any],
    decision: Mapping[str, Any],
    config: RunConfig,
    frozen_score: FrozenScore | None,
) -> dict[str, Any] | None:
    if config.mode is ExecutionMode.DEVELOPMENT_HEURISTIC:
        return None
    if decision.get("decision") not in {"AUTO_APPROVED", "PROVISIONAL"}:
        return None
    if frozen_score is None:
        raise CertificateBindingError("certificate requires verified calibration")

    frozen = global_input["frozen_candidate_contract"]
    context = global_input["context_evidence"]
    attestation = global_input["attestation_evidence"]
    hashes = decision["run_metadata"]["input_package_hashes"]
    triggered = {
        item.get("gate_id")
        for item in gate_results.get("observations", [])
        if item.get("triggered") is True
    }
    certificate = {
        "schema_id": "TerminologyCertificateV1",
        "schema_version": "1.1.0",
        "certificate_id": f"{config.global_run_id}-certificate",
        "certificate_version": "1.1.0",
        "candidate_key": copy.deepcopy(global_input["candidate_key"]),
        "status": decision["decision"],
        "allowed_variants": copy.deepcopy(
            frozen["surfaces"]["validated_variants_vi"]
        ),
        "forbidden_candidates": copy.deepcopy(
            frozen["surfaces"]["rejected_variants_vi"]
        ),
        "scope_note": frozen["scope_note"],
        "validity_context_refs": copy.deepcopy(
            context["support_set"]["positive_support_refs"]
        ),
        "evidence_summary": {
            "context_evidence_sha256": hashes["context_evidence_sha256"],
            "attestation_evidence_sha256": hashes[
                "attestation_evidence_sha256"
            ],
            "C_mean": context["features"]["C_mean"],
            "E_features": copy.deepcopy(attestation["features"]),
        },
        "gate_summary": [gate_id for gate_id in GATE_IDS if gate_id in triggered],
        "decision_package_sha256": _self_hash(decision),
        "policy_version": decision["decision_policy"]["policy_version"],
        "issued_at": config.certificate_issued_at,
        "binding_status": "COMPLETE",
        "attestation_evidence_refs": copy.deepcopy(
            attestation["accepted_evidence_refs"]
        ),
        "threshold_version": frozen_score.verified.artifact.payload[
            "operating_point"
        ]["operating_point_id"],
        "sense_inventory_version": global_input["candidate_key"][
            "sense_inventory_version"
        ],
        "effective_sense_contract_sha256": hashes[
            "effective_sense_contract_sha256"
        ],
        "input_contract_sha256": global_input["input_contract_sha256"],
        "context_evidence_sha256": hashes["context_evidence_sha256"],
        "attestation_evidence_sha256": hashes["attestation_evidence_sha256"],
        "gate_result_sha256": hashes["gate_result_sha256"],
        "calibration_artifact_sha256": frozen_score.verified.artifact.self_sha256,
        "global_validator_input_sha256": hashes[
            "global_validator_input_sha256"
        ],
        "frozen_candidate_contract_sha256": hashes[
            "frozen_candidate_contract_sha256"
        ],
        "constraint_evidence_sha256": hashes["constraint_evidence_sha256"],
        "gate_policy_artifact_sha256": hashes[
            "gate_policy_artifact_sha256"
        ],
        "integrity": {"self_sha256": "0" * 64},
    }
    sealed = seal_self_hash(certificate)
    errors = validate_instance(sealed, config.schema_dir)
    if errors:
        raise CertificateBindingError(
            "TerminologyCertificate invalid: " + "; ".join(errors)
        )
    return sealed


def _self_hash(value: Mapping[str, Any]) -> str:
    result = value.get("integrity", {}).get("self_sha256")
    if not isinstance(result, str):
        raise CertificateBindingError("decision self hash is missing")
    return result
