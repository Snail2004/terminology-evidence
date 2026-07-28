from __future__ import annotations

import copy
import json

import pytest

from conftest import (
    FEATURE_REGISTRY,
    SCHEMAS,
    load_v11,
    reseal_decision,
    validate_payload,
)
from terminology_contracts.bindings import calculate_replay_spec_sha256
from terminology_contracts.calibration import (
    CalibrationVerificationError,
    verify_calibration_artifact,
)
from terminology_contracts.integrity import seal_self_hash
from terminology_contracts.registries import load_registry
from terminology_contracts.scoring import assemble_decision_features
from terminology_contracts.validation import validate_file


def test_frozen_candidate_rejects_stale_input_binding() -> None:
    frozen = load_v11("frozen_candidate_contract.json")
    frozen["effective_definition_en"] = "A different definition."
    errors = validate_payload(seal_self_hash(frozen))
    assert any("does not bind FrozenCandidateContract content" in error for error in errors)


@pytest.mark.parametrize(
    "missing_field",
    [
        "effective_sense_contract",
        "frozen_candidate_contract",
        "constraint_evidence",
    ],
)
def test_complete_global_input_requires_constraint_bindings(missing_field: str) -> None:
    global_input = load_v11("global_validator_input.json")
    global_input.pop(missing_field)
    errors = validate_payload(seal_self_hash(global_input))
    assert errors


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "unknown",
        "missing",
    ],
)
def test_frozen_decision_requires_exact_mapped_feature_set(mutation: str) -> None:
    decision = load_v11("global_decision_package.json")
    if mutation == "empty":
        decision["decision_features"] = {}
    elif mutation == "unknown":
        decision["decision_features"]["BOGUS"] = 999.0
    else:
        decision["decision_features"].pop("C_mean")
    errors = validate_payload(reseal_decision(decision))
    assert any("decision feature set mismatch" in error for error in errors)


def test_frozen_decision_recomputes_approval_score() -> None:
    decision = load_v11("global_decision_package.json")
    decision["approval_score"] = 0.99
    errors = validate_payload(reseal_decision(decision))
    assert any("approval_score differs from replayed" in error for error in errors)


def test_feature_registry_assembles_machine_readable_vector() -> None:
    global_input = load_v11("global_validator_input.json")
    registry = load_registry(FEATURE_REGISTRY)
    features = assemble_decision_features(global_input, registry)
    assert features["C_evidence_coverage"] == 1.0
    assert features["C_required_context_type_coverage"] == 1.0
    assert features["C_mean"] == 0.88
    assert features["E_concept"] == 0.83


def test_replay_hash_binds_features_inputs_and_gate_result() -> None:
    decision = load_v11("global_decision_package.json")
    baseline = calculate_replay_spec_sha256(decision)

    changed_feature = copy.deepcopy(decision)
    changed_feature["decision_features"]["C_mean"] = 0.1
    assert calculate_replay_spec_sha256(changed_feature) != baseline

    changed_input = copy.deepcopy(decision)
    changed_input["run_metadata"]["input_package_hashes"][
        "global_validator_input_sha256"
    ] = "f" * 64
    assert calculate_replay_spec_sha256(changed_input) != baseline

    changed_gate = copy.deepcopy(decision)
    changed_gate["run_metadata"]["input_package_hashes"][
        "gate_result_sha256"
    ] = "e" * 64
    assert calculate_replay_spec_sha256(changed_gate) != baseline


def test_duplicate_gate_id_with_different_payload_rejects() -> None:
    gates = load_v11("gate_result_set.json")
    gates["observations"][1]["gate_id"] = gates["observations"][0]["gate_id"]
    errors = validate_payload(seal_self_hash(gates))
    assert any("unique gate_id" in error for error in errors)


def test_complete_gate_set_requires_registry_coverage() -> None:
    gates = load_v11("gate_result_set.json")
    gates["observations"].pop()
    errors = validate_payload(seal_self_hash(gates))
    assert any("cover registry exactly" in error for error in errors)


def test_triggered_gate_requires_reason_and_evidence() -> None:
    gates = load_v11("gate_result_set.json")
    gates["observations"][0].update(triggered=True, action="FATAL_REJECT")
    errors = validate_payload(seal_self_hash(gates))
    assert any("requires reason_codes" in error for error in errors)
    assert any("requires evidence_refs" in error for error in errors)


def test_constraint_gate_projection_rejects_disagreement() -> None:
    decision = load_v11("global_decision_package.json")
    decision["decision_policy"].update(
        mode="DEVELOPMENT_HEURISTIC",
        calibration_artifact_sha256=None,
        threshold=None,
    )
    decision["approval_score"] = None
    decision["decision"] = "REJECTED"
    observation = next(
        row
        for row in decision["gate_results"]["observations"]
        if row["gate_id"] == "sense_definition_unverified"
    )
    observation.update(
        triggered=True,
        action="FATAL_REJECT",
        reason_codes=["TEST_DRIFT"],
        evidence_refs=[
            {
                "evidence_id": "test-drift",
                "evidence_type": "OTHER",
                "uri": "artifact://tests/drift",
                "sha256": "a" * 64,
            }
        ],
    )
    decision["gate_results"] = seal_self_hash(decision["gate_results"])
    errors = validate_payload(reseal_decision(decision), calibration_path=None)
    assert any("disagrees with declared constraint evidence" in error for error in errors)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_constants_reject_before_validation(tmp_path, constant: str) -> None:
    decision = load_v11("global_decision_package.json")
    raw = json.dumps(decision, sort_keys=True).replace(
        str(decision["approval_score"]), constant, 1
    )
    path = tmp_path / "nonfinite.json"
    path.write_text(raw, encoding="utf-8")
    errors = validate_file(path, SCHEMAS)
    assert any("non-finite JSON number" in error for error in errors)


@pytest.mark.parametrize("model_type", ["RULE_SET", "ISOTONIC"])
def test_undefined_calibration_model_types_reject(tmp_path, model_type: str) -> None:
    calibration = load_v11("calibration_artifact.json")
    calibration["model"] = {
        "model_type": model_type,
        "feature_names": ["C_mean"],
        "parameters": {"rules": [{"feature": "C_mean"}]},
    }
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(seal_self_hash(calibration)), encoding="utf-8")
    with pytest.raises(CalibrationVerificationError):
        verify_calibration_artifact(
            path,
            schema_dir=SCHEMAS,
            feature_registry_path=FEATURE_REGISTRY,
        )


def test_empty_calibration_results_reject(tmp_path) -> None:
    calibration = load_v11("calibration_artifact.json")
    calibration["calibration_results"] = {}
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(seal_self_hash(calibration)), encoding="utf-8")
    with pytest.raises(CalibrationVerificationError):
        verify_calibration_artifact(
            path,
            schema_dir=SCHEMAS,
            feature_registry_path=FEATURE_REGISTRY,
        )


def test_native_fixture_metadata_is_not_migration_metadata() -> None:
    metadata = load_v11("global_decision_package.json")["run_metadata"]
    assert not metadata["global_run_id"].startswith("migrated-")
    assert "migration" not in metadata["engine_version"]
