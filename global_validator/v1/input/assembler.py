from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from terminology_contracts.integrity import seal_self_hash
from terminology_contracts.validation import validate_instance

from ..errors import InputValidationError, JoinValidationError
from .joiner import verify_exact_join


def assemble_global_input(
    *,
    effective_sense_contract: Mapping[str, Any],
    frozen_candidate_contract: Mapping[str, Any],
    constraint_evidence: Mapping[str, Any],
    context_evidence: Mapping[str, Any],
    attestation_evidence: Mapping[str, Any],
    optional_probes: Sequence[Mapping[str, Any]] = (),
    assembler_id: str = "global-validator-input-assembler",
    assembler_version: str = "1.1.0",
    assembled_at: str | None = None,
    schema_dir: Any | None = None,
    gate_policy_path: Any | None = None,
    feature_registry_path: Any | None = None,
) -> dict[str, Any]:
    frozen = copy.deepcopy(dict(frozen_candidate_contract))
    payloads: dict[str, Mapping[str, Any]] = {
        "frozen_candidate_contract": frozen,
        "constraint_evidence": constraint_evidence,
        "context_evidence": context_evidence,
        "attestation_evidence": attestation_evidence,
    }
    for index, probe in enumerate(optional_probes):
        payloads[f"optional_probes[{index}]"] = probe
    verify_exact_join(payloads)

    effective_hash = _self_hash(effective_sense_contract)
    candidate_key = copy.deepcopy(frozen.get("candidate_key"))
    if effective_hash != candidate_key.get("effective_sense_contract_sha256"):
        raise JoinValidationError("Effective Sense Contract hash mismatch")
    input_hash = frozen.get("input_contract_sha256")
    result = {
        "schema_id": "GlobalValidatorInputV1",
        "schema_version": "1.1.0",
        "candidate_key": candidate_key,
        "input_contract_sha256": input_hash,
        "context_evidence": copy.deepcopy(dict(context_evidence)),
        "attestation_evidence": copy.deepcopy(dict(attestation_evidence)),
        "optional_probes": [copy.deepcopy(dict(probe)) for probe in optional_probes],
        "effective_sense_contract": copy.deepcopy(dict(effective_sense_contract)),
        "frozen_candidate_contract": frozen,
        "constraint_evidence": copy.deepcopy(dict(constraint_evidence)),
        "assembly_metadata": {
            "assembler_id": assembler_id,
            "assembler_version": assembler_version,
            "assembled_at": assembled_at,
            "source_package_hashes": {
                "context_evidence_sha256": _self_hash(context_evidence),
                "attestation_evidence_sha256": _self_hash(attestation_evidence),
                "effective_sense_contract_sha256": effective_hash,
                "frozen_candidate_contract_sha256": _self_hash(frozen),
                "constraint_evidence_sha256": _self_hash(constraint_evidence),
            },
            "binding_status": "COMPLETE",
        },
        "integrity": {"self_sha256": "0" * 64},
    }
    sealed = seal_self_hash(result)
    if schema_dir is not None:
        errors = validate_instance(
            sealed,
            schema_dir,
            gate_policy_path=gate_policy_path,
            feature_registry_path=feature_registry_path,
        )
        if errors:
            raise InputValidationError("assembled Global Input: " + "; ".join(errors))
    return sealed


def _self_hash(value: Mapping[str, Any]) -> str:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping):
        raise JoinValidationError("nested artifact integrity is missing")
    result = integrity.get("self_sha256")
    if not isinstance(result, str):
        raise JoinValidationError("nested artifact self hash is missing")
    return result
