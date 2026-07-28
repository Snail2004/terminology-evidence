from __future__ import annotations

from pathlib import Path
from typing import Any

from terminology_contracts.integrity import verify_self_hash
from terminology_contracts.validation import validate_instance

from ..authority import verify_authority
from ..config import RunConfig
from ..errors import DecisionReplayError, IntegrityValidationError
from ..input import load_and_validate_global_input, verify_collision_index_binding
from ..jsonio import load_json_object


def verify_decision_artifact(
    decision_path: Path,
    *,
    global_input_path: Path,
    config: RunConfig,
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
    return decision
