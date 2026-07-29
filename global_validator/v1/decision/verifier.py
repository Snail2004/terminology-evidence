from __future__ import annotations

from pathlib import Path
from typing import Any

from terminology_contracts.bindings import calculate_replay_spec_sha256
from terminology_contracts.integrity import verify_self_hash
from terminology_contracts.validation import validate_instance

from ..authority import verify_authority
from ..config import ENGINE_VERSION, GLOBAL_RUN_SPEC_ID, RunConfig
from ..errors import DecisionReplayError, IntegrityValidationError
from ..gates import load_gate_action_policy, verify_gate_result_payload
from ..input import load_and_validate_global_input, verify_collision_index_binding
from ..jsonio import load_json_object
from .package_builder import build_execution_config_sha256


def verify_decision_artifact(
    decision_path: Path,
    *,
    global_input_path: Path,
    config: RunConfig,
    verify_run_config_binding: bool = False,
) -> dict[str, Any]:
    authority = verify_authority(
        config.authority_receipt_path,
        config.contracts_root,
        repository_root=config.repository_root,
    )
    global_input = load_and_validate_global_input(
        global_input_path,
        schema_dir=authority.schema_dir,
        gate_policy_path=authority.gate_policy_path,
        feature_registry_path=authority.feature_registry_path,
    )
    verify_collision_index_binding(global_input, config.collision_index_path)
    try:
        decision = load_json_object(decision_path)
        verify_self_hash(decision, path=str(decision_path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise IntegrityValidationError(str(exc)) from exc
    if decision.get("schema_id") != "GlobalDecisionPackageV1":
        raise DecisionReplayError("expected GlobalDecisionPackageV1")
    errors = validate_instance(
        decision,
        authority.schema_dir,
        calibration_path=config.calibration_path,
        feature_registry_path=authority.feature_registry_path,
        global_input_path=global_input_path,
        gate_policy_path=authority.gate_policy_path,
    )
    if errors:
        raise DecisionReplayError("decision verification failed: " + "; ".join(errors))
    _verify_decision_bindings(
        decision,
        global_input=global_input,
        config=config,
        verify_run_config_binding=verify_run_config_binding,
    )
    return decision


def _verify_decision_bindings(
    decision: dict[str, Any],
    *,
    global_input: dict[str, Any],
    config: RunConfig,
    verify_run_config_binding: bool,
) -> None:
    if decision.get("schema_version") != "1.1.0":
        raise DecisionReplayError("unsupported GlobalDecisionPackageV1 schema_version")
    if decision.get("candidate_key") != global_input.get("candidate_key"):
        raise DecisionReplayError("decision candidate_key differs from input")
    if decision.get("input_contract_sha256") != global_input.get(
        "input_contract_sha256"
    ):
        raise DecisionReplayError("decision input_contract_sha256 differs from input")

    gate_result = decision.get("gate_results")
    if not isinstance(gate_result, dict):
        raise DecisionReplayError("decision gate_results is missing")
    verify_gate_result_payload(
        gate_result,
        global_input=global_input,
        gate_policy_path=config.gate_policy_path,
        schema_dir=config.schema_dir,
    )

    metadata = decision.get("run_metadata")
    if not isinstance(metadata, dict):
        raise DecisionReplayError("decision run_metadata is missing")
    action_policy = load_gate_action_policy(
        config.gate_action_policy_path,
        gate_policy_path=config.gate_policy_path,
        schema_dir=config.schema_dir,
    )
    if verify_run_config_binding:
        expected_metadata = {
            "global_run_id": config.global_run_id,
            "global_run_spec_id": GLOBAL_RUN_SPEC_ID,
            "started_at": config.started_at,
            "completed_at": config.completed_at,
            "engine_version": ENGINE_VERSION,
        }
        for field, expected in expected_metadata.items():
            if metadata.get(field) != expected:
                raise DecisionReplayError(f"decision run_metadata.{field} mismatch")
        expected_execution = build_execution_config_sha256(
            config, action_policy=action_policy
        )
        if metadata.get("execution_config_sha256") != expected_execution:
            raise DecisionReplayError("decision execution_config_sha256 mismatch")
        if decision.get("decision_policy", {}).get("mode") != config.mode.value:
            raise DecisionReplayError("decision mode differs from replay spec")
    if calculate_replay_spec_sha256(decision) != metadata.get("replay_spec_sha256"):
        raise DecisionReplayError("decision replay_spec_sha256 mismatch")

    package_hashes = metadata.get("input_package_hashes")
    if not isinstance(package_hashes, dict):
        raise DecisionReplayError("decision input_package_hashes is missing")
    expected_hashes = {
        "global_validator_input_sha256": _self_hash(global_input),
        "context_evidence_sha256": _self_hash(global_input["context_evidence"]),
        "attestation_evidence_sha256": _self_hash(
            global_input["attestation_evidence"]
        ),
        "effective_sense_contract_sha256": _self_hash(
            global_input["effective_sense_contract"]
        ),
        "frozen_candidate_contract_sha256": _self_hash(
            global_input["frozen_candidate_contract"]
        ),
        "constraint_evidence_sha256": _self_hash(
            global_input["constraint_evidence"]
        ),
        "gate_result_sha256": _self_hash(gate_result),
        "gate_policy_artifact_sha256": action_policy.gate_policy_artifact_sha256,
    }
    for field, expected in expected_hashes.items():
        if package_hashes.get(field) != expected:
            raise DecisionReplayError(f"decision input_package_hashes.{field} mismatch")
    if decision.get("context_evidence_sha256") != expected_hashes[
        "context_evidence_sha256"
    ]:
        raise DecisionReplayError("decision context_evidence_sha256 mismatch")
    if decision.get("attestation_evidence_sha256") != expected_hashes[
        "attestation_evidence_sha256"
    ]:
        raise DecisionReplayError("decision attestation_evidence_sha256 mismatch")


def _self_hash(value: dict[str, Any]) -> str:
    result = value.get("integrity", {}).get("self_sha256")
    if not isinstance(result, str):
        raise DecisionReplayError("bound artifact self hash is missing")
    return result
