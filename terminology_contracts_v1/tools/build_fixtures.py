from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from terminology_contracts.bindings import (  # noqa: E402
    calculate_replay_spec_sha256,
    seal_frozen_candidate_contract,
)
from terminology_contracts.integrity import (  # noqa: E402
    canonical_sha256,
    seal_self_hash,
    strict_json_loads,
)
from terminology_contracts.registries import (  # noqa: E402
    FEATURE_CONTRACT_VERSION,
    GATE_IDS,
    PACKAGE_VERSION,
    load_registry,
)
from terminology_contracts.scoring import (  # noqa: E402
    assemble_decision_features,
    evaluate_calibration_model,
    expected_decision,
    select_model_features,
)


VALID = ROOT / "examples" / "valid" / "v1.1.0"
FEATURE_REGISTRY = ROOT / "registries" / "feature_contract_v1.1.0.json"

GATE_SOURCES = {
    "input_contract_mismatch": ["CONTRACT"],
    "sense_definition_unverified": ["SENSE"],
    "unresolved_polysemy": ["SENSE"],
    "concept_mismatch": ["C", "E"],
    "wrong_sense": ["C"],
    "contradiction": ["C", "E"],
    "target_collision": ["GLOBAL"],
    "judge_disagreement": ["C", "E"],
    "insufficient_evidence": ["C", "E"],
    "missing_contrastive_context": ["C"],
    "incomplete_context_type_coverage": ["C"],
    "attestation_unjudgeable": ["E"],
}


def _load(name: str) -> dict:
    return strict_json_loads((VALID / name).read_text(encoding="utf-8"))


def _write(name: str, value: dict) -> None:
    path = VALID / name
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _native_provenance(value: dict, component_id: str) -> None:
    provenance = value.get("provenance") or value.get("input_provenance")
    if not isinstance(provenance, dict):
        return
    provenance.update(
        {
            "run_id": f"fixture-{component_id}-run-001",
            "run_spec_id": f"fixture-{component_id}-spec-001",
            "component_id": component_id,
            "component_version": PACKAGE_VERSION,
            "execution_config_sha256": canonical_sha256(
                {
                    "component_id": component_id,
                    "component_version": PACKAGE_VERSION,
                    "policy_version": provenance.get("policy_version"),
                }
            ),
        }
    )


def _bind_producer(
    value: dict,
    *,
    key: dict,
    input_contract_sha256: str,
    component_id: str,
) -> dict:
    value["candidate_key"] = copy.deepcopy(key)
    value["input_contract_sha256"] = input_contract_sha256
    _native_provenance(value, component_id)
    return seal_self_hash(value)


def main() -> int:
    effective = _load("effective_sense_contract.json")
    _native_provenance(effective, "sense-review")
    effective = seal_self_hash(effective)
    _write("effective_sense_contract.json", effective)

    frozen = _load("frozen_candidate_contract.json")
    key = copy.deepcopy(frozen["candidate_key"])
    key["candidate_version"] = "fixture-candidate-v1"
    key["effective_sense_contract_sha256"] = effective["integrity"][
        "self_sha256"
    ]
    frozen["candidate_key"] = copy.deepcopy(key)
    for field in (
        "effective_definition_en",
        "effective_part_of_speech",
        "scope_note",
        "domain_profile",
    ):
        frozen[field] = copy.deepcopy(effective[field])
    _native_provenance(frozen, "candidate-freezer")
    frozen = seal_frozen_candidate_contract(frozen)
    _write("frozen_candidate_contract.json", frozen)
    input_hash = frozen["input_contract_sha256"]

    context = _bind_producer(
        _load("context_evidence_package.json"),
        key=key,
        input_contract_sha256=input_hash,
        component_id="context-substitution",
    )
    _write("context_evidence_package.json", context)

    attestation = _bind_producer(
        _load("attestation_evidence_package.json"),
        key=key,
        input_contract_sha256=input_hash,
        component_id="vietnamese-attestation",
    )
    _write("attestation_evidence_package.json", attestation)

    review_ref = {
        "evidence_id": "sense-review-fixture-001",
        "evidence_type": "OTHER",
        "uri": "artifact://fixtures/sense-review-001",
        "sha256": effective["review_artifact_sha256"],
    }
    constraint = {
        "schema_id": "ConstraintEvidencePackageV1",
        "schema_version": PACKAGE_VERSION,
        "candidate_key": copy.deepcopy(key),
        "input_contract_sha256": input_hash,
        "binding_status": "COMPLETE",
        "sense_review": {
            "status": "VERIFIED",
            "effective_sense_contract_sha256": effective["integrity"][
                "self_sha256"
            ],
            "review_artifact_ref": review_ref,
        },
        "polysemy_resolution": {
            "status": "RESOLVED_SINGLE",
            "related_sense_ids": [key["sense_id"]],
            "authority_ref": review_ref,
        },
        "target_collision": {
            "status": "CLEAR",
            "collision_index_sha256": "3" * 64,
            "conflicting_candidate_keys": [],
            "evidence_refs": [],
        },
        "provenance": copy.deepcopy(context["provenance"]),
        "integrity": {"self_sha256": ""},
    }
    _native_provenance(constraint, "global-constraint-assembler")
    constraint = seal_self_hash(constraint)
    _write("constraint_evidence_package.json", constraint)

    global_input = _load("global_validator_input.json")
    global_input.update(
        {
            "candidate_key": copy.deepcopy(key),
            "input_contract_sha256": input_hash,
            "effective_sense_contract": copy.deepcopy(effective),
            "frozen_candidate_contract": copy.deepcopy(frozen),
            "constraint_evidence": copy.deepcopy(constraint),
            "context_evidence": copy.deepcopy(context),
            "attestation_evidence": copy.deepcopy(attestation),
            "optional_probes": [],
            "assembly_metadata": {
                "assembler_id": "global-input-assembler",
                "assembler_version": PACKAGE_VERSION,
                "assembled_at": "2026-07-28T11:00:00+00:00",
                "binding_status": "COMPLETE",
                "source_package_hashes": {
                    "effective_sense_contract_sha256": effective["integrity"][
                        "self_sha256"
                    ],
                    "frozen_candidate_contract_sha256": frozen["integrity"][
                        "self_sha256"
                    ],
                    "constraint_evidence_sha256": constraint["integrity"][
                        "self_sha256"
                    ],
                    "context_evidence_sha256": context["integrity"][
                        "self_sha256"
                    ],
                    "attestation_evidence_sha256": attestation["integrity"][
                        "self_sha256"
                    ],
                },
            },
        }
    )
    global_input = seal_self_hash(global_input)
    _write("global_validator_input.json", global_input)

    gates = {
        "schema_id": "GateResultSetV1",
        "schema_version": PACKAGE_VERSION,
        "candidate_key": copy.deepcopy(key),
        "input_contract_sha256": input_hash,
        "binding_status": "COMPLETE",
        "gate_policy_version": "gates-v1",
        "observations": [
            {
                "gate_id": gate_id,
                "triggered": False,
                "action": "NONE",
                "source_modules": GATE_SOURCES[gate_id],
                "reason_codes": [],
                "evidence_refs": [],
            }
            for gate_id in GATE_IDS
        ],
        "integrity": {"self_sha256": ""},
    }
    gates = seal_self_hash(gates)
    _write("gate_result_set.json", gates)

    calibration = _load("calibration_artifact.json")
    feature_names = [
        "C_mean",
        "C_min",
        "E_authority",
        "E_independence",
        "E_domain",
        "E_concept",
        "E_conventionality",
        "E_coverage",
    ]
    calibration.update(
        {
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "verification_status": "SEALED",
            "numerical_tolerance": 1e-12,
            "model": {
                "model_type": "LOGISTIC_REGRESSION",
                "feature_names": feature_names,
                "parameters": {
                    "link_function": "LOGIT",
                    "intercept": -0.5,
                    "coefficients": {
                        name: (
                            1.8
                            if name == "C_mean"
                            else 1.1
                            if name == "E_concept"
                            else 0.0
                        )
                        for name in feature_names
                    },
                },
            },
            "operating_point": {
                "operating_point_id": "fixture-op-v1",
                "threshold": 0.84,
                "observed_precision": 0.97,
                "coverage": 0.42,
                "precision_lower_bound": 0.95,
            },
            "calibration_results": {
                "development_sample_count": 225,
                "validation_sample_count": 75,
                "uncertainty_method": "WILSON_SCORE",
                "selected_operating_point_id": "fixture-op-v1",
            },
        }
    )
    calibration = seal_self_hash(calibration)
    _write("calibration_artifact.json", calibration)

    feature_registry = load_registry(FEATURE_REGISTRY)
    assembled = assemble_decision_features(global_input, feature_registry)
    decision_features = select_model_features(assembled, feature_names)
    approval_score = evaluate_calibration_model(calibration, decision_features)
    decision_status = expected_decision(approval_score, 0.84, "NONE")
    input_hashes = {
        "global_validator_input_sha256": global_input["integrity"][
            "self_sha256"
        ],
        "context_evidence_sha256": context["integrity"]["self_sha256"],
        "attestation_evidence_sha256": attestation["integrity"]["self_sha256"],
        "effective_sense_contract_sha256": effective["integrity"]["self_sha256"],
        "frozen_candidate_contract_sha256": frozen["integrity"]["self_sha256"],
        "constraint_evidence_sha256": constraint["integrity"]["self_sha256"],
        "gate_result_sha256": gates["integrity"]["self_sha256"],
    }
    decision = {
        "schema_id": "GlobalDecisionPackageV1",
        "schema_version": PACKAGE_VERSION,
        "candidate_key": copy.deepcopy(key),
        "input_contract_sha256": input_hash,
        "context_evidence_sha256": context["integrity"]["self_sha256"],
        "attestation_evidence_sha256": attestation["integrity"]["self_sha256"],
        "gate_results": copy.deepcopy(gates),
        "decision_features": decision_features,
        "decision_policy": {
            "mode": "FROZEN_CALIBRATED",
            "policy_id": "global-validator",
            "policy_version": "global-v1",
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "calibration_artifact_sha256": calibration["integrity"][
                "self_sha256"
            ],
            "threshold": 0.84,
        },
        "approval_score": approval_score,
        "decision": decision_status,
        "decision_reasons": ["CALIBRATED_SCORE_ABOVE_THRESHOLD"],
        "certificate_ref": None,
        "run_metadata": {
            "binding_status": "COMPLETE",
            "global_run_id": "gv-fixture-run-001",
            "global_run_spec_id": "gv-fixture-spec-001",
            "started_at": "2026-07-28T11:00:00+00:00",
            "completed_at": "2026-07-28T11:01:00+00:00",
            "engine_version": "global-validator-fixture-1.1.0-rc2",
            "execution_config_sha256": canonical_sha256(
                {
                    "engine_version": "global-validator-fixture-1.1.0-rc2",
                    "policy_version": "global-v1",
                    "calibration_artifact_sha256": calibration["integrity"][
                        "self_sha256"
                    ],
                }
            ),
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "gate_policy_version": "gates-v1",
            "input_package_hashes": input_hashes,
            "replay_spec_sha256": "0" * 64,
        },
        "integrity": {"self_sha256": ""},
    }
    decision["run_metadata"][
        "replay_spec_sha256"
    ] = calculate_replay_spec_sha256(decision)
    decision = seal_self_hash(decision)
    _write("global_decision_package.json", decision)

    certificate = _load("terminology_certificate.json")
    certificate.update(
        {
            "candidate_key": copy.deepcopy(key),
            "binding_status": "COMPLETE",
            "status": decision_status,
            "sense_inventory_version": key["sense_inventory_version"],
            "effective_sense_contract_sha256": effective["integrity"][
                "self_sha256"
            ],
            "input_contract_sha256": input_hash,
            "context_evidence_sha256": context["integrity"]["self_sha256"],
            "attestation_evidence_sha256": attestation["integrity"][
                "self_sha256"
            ],
            "gate_result_sha256": gates["integrity"]["self_sha256"],
            "calibration_artifact_sha256": calibration["integrity"][
                "self_sha256"
            ],
            "global_validator_input_sha256": global_input["integrity"][
                "self_sha256"
            ],
            "frozen_candidate_contract_sha256": frozen["integrity"][
                "self_sha256"
            ],
            "constraint_evidence_sha256": constraint["integrity"][
                "self_sha256"
            ],
            "decision_package_sha256": decision["integrity"]["self_sha256"],
            "threshold_version": "calibration-fixture-v1.1.0-rc2",
            "validity_context_refs": [
                copy.deepcopy(context["support_set"]["positive_support_refs"][0])
            ],
            "attestation_evidence_refs": [
                copy.deepcopy(attestation["accepted_evidence_refs"][0])
            ],
            "gate_summary": [],
            "evidence_summary": {
                "C_mean": context["features"]["C_mean"],
                "E_features": copy.deepcopy(attestation["features"]),
                "context_evidence_sha256": context["integrity"]["self_sha256"],
                "attestation_evidence_sha256": attestation["integrity"][
                    "self_sha256"
                ],
            },
        }
    )
    certificate = seal_self_hash(certificate)
    _write("terminology_certificate.json", certificate)

    tac = _load("tac_occurrence_input.json")
    tac["certificate"] = copy.deepcopy(certificate)
    tac["offset_unit"] = "UNICODE_CODEPOINT"
    tac = seal_self_hash(tac)
    _write("tac_occurrence_input.json", tac)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
