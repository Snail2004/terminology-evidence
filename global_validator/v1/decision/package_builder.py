from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from terminology_contracts.bindings import calculate_replay_spec_sha256
from terminology_contracts.integrity import canonical_sha256, seal_self_hash, sha256_file
from terminology_contracts.validation import validate_instance

from ..calibration import FrozenScore
from ..config import ENGINE_VERSION, GLOBAL_RUN_SPEC_ID, ExecutionMode, RunConfig
from ..errors import DecisionReplayError
from ..gates import GateActionPolicy
from .resolver import DecisionResolution


def build_execution_config_sha256(
    config: RunConfig,
    *,
    action_policy: GateActionPolicy,
) -> str:
    return canonical_sha256(
        {
            "engine_version": ENGINE_VERSION,
            "global_run_spec_id": GLOBAL_RUN_SPEC_ID,
            "mode": config.mode.value,
            "gate_action_policy_sha256": action_policy.self_sha256,
            "gate_policy_artifact_sha256": (
                action_policy.gate_policy_artifact_sha256
            ),
            "feature_registry_physical_sha256": sha256_file(
                config.feature_registry_path
            ),
            "calibration_self_sha256": (
                None
                if config.calibration_path is None
                else _loaded_self_hash(config.calibration_path)
            ),
            "allow_example_calibration": config.allow_example_calibration,
            "expected_calibration_sha256": config.expected_calibration_sha256,
        }
    )


def build_decision_package(
    *,
    global_input: Mapping[str, Any],
    gate_results: Mapping[str, Any],
    assembled_features: Mapping[str, float],
    resolution: DecisionResolution,
    config: RunConfig,
    action_policy: GateActionPolicy,
    frozen_score: FrozenScore | None,
    global_input_path: Path,
) -> dict[str, Any]:
    if config.mode is ExecutionMode.DEVELOPMENT_HEURISTIC:
        decision_features: dict[str, float] = {}
        approval_score = None
        calibration_hash = None
        threshold = None
    else:
        if frozen_score is None:
            raise DecisionReplayError("frozen mode requires verified calibration")
        decision_features = frozen_score.decision_features
        approval_score = frozen_score.approval_score
        calibration_hash = frozen_score.verified.artifact.self_sha256
        threshold = frozen_score.verified.threshold

    input_hashes = _input_hashes(global_input, gate_results, action_policy)
    decision = {
        "schema_id": "GlobalDecisionPackageV1",
        "schema_version": "1.1.0",
        "candidate_key": copy.deepcopy(global_input.get("candidate_key")),
        "input_contract_sha256": global_input.get("input_contract_sha256"),
        "context_evidence_sha256": input_hashes["context_evidence_sha256"],
        "attestation_evidence_sha256": input_hashes[
            "attestation_evidence_sha256"
        ],
        "gate_results": copy.deepcopy(dict(gate_results)),
        "decision_features": copy.deepcopy(decision_features),
        "approval_score": approval_score,
        "decision": resolution.decision,
        "decision_reasons": list(resolution.reasons),
        "decision_policy": {
            "policy_id": "global-validator",
            "policy_version": "global-v1.1.0",
            "mode": config.mode.value,
            "calibration_artifact_sha256": calibration_hash,
            "threshold": threshold,
            "feature_contract_version": "1.1.0",
            "gate_policy_artifact_sha256": (
                action_policy.gate_policy_artifact_sha256
            ),
        },
        "certificate_ref": None,
        "run_metadata": {
            "binding_status": "COMPLETE",
            "global_run_id": config.global_run_id,
            "global_run_spec_id": GLOBAL_RUN_SPEC_ID,
            "started_at": config.started_at,
            "completed_at": config.completed_at,
            "engine_version": ENGINE_VERSION,
            "execution_config_sha256": build_execution_config_sha256(
                config, action_policy=action_policy
            ),
            "feature_contract_version": "1.1.0",
            "gate_policy_version": "1.0.0",
            "gate_policy_artifact_sha256": (
                action_policy.gate_policy_artifact_sha256
            ),
            "input_package_hashes": input_hashes,
            "replay_spec_sha256": "0" * 64,
        },
        "integrity": {"self_sha256": "0" * 64},
    }
    decision["run_metadata"]["replay_spec_sha256"] = (
        calculate_replay_spec_sha256(decision)
    )
    sealed = seal_self_hash(decision)
    errors = validate_instance(
        sealed,
        config.schema_dir,
        calibration_path=config.calibration_path,
        feature_registry_path=config.feature_registry_path,
        global_input_path=global_input_path,
        gate_policy_path=config.gate_policy_path,
    )
    if errors:
        raise DecisionReplayError("GlobalDecisionPackage invalid: " + "; ".join(errors))
    return sealed


def _input_hashes(
    global_input: Mapping[str, Any],
    gate_results: Mapping[str, Any],
    action_policy: GateActionPolicy,
) -> dict[str, Any]:
    return {
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
        "gate_result_sha256": _self_hash(gate_results),
        "gate_policy_artifact_sha256": action_policy.gate_policy_artifact_sha256,
    }


def _self_hash(value: Mapping[str, Any]) -> str:
    result = value.get("integrity", {}).get("self_sha256")
    if not isinstance(result, str):
        raise DecisionReplayError("artifact self hash is missing")
    return result


def _loaded_self_hash(path: Path) -> str:
    from terminology_contracts.integrity import load_verified_json_artifact

    return load_verified_json_artifact(path).self_sha256
