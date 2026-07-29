from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import verify_self_hash
from terminology_contracts.validation import validate_gate_result_with_policy

from ..errors import DecisionReplayError, IntegrityValidationError
from ..jsonio import load_json_object


def verify_gate_result_artifact(
    path: Path,
    *,
    global_input: Mapping[str, Any],
    gate_policy_path: Path,
    schema_dir: Path,
) -> dict[str, Any]:
    try:
        gate_result = load_json_object(path)
        verify_self_hash(gate_result, path=str(path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise IntegrityValidationError(str(exc)) from exc
    verify_gate_result_payload(
        gate_result,
        global_input=global_input,
        gate_policy_path=gate_policy_path,
        schema_dir=schema_dir,
    )
    return gate_result


def verify_gate_result_payload(
    gate_result: Mapping[str, Any],
    *,
    global_input: Mapping[str, Any],
    gate_policy_path: Path,
    schema_dir: Path,
) -> None:
    if gate_result.get("schema_id") != "GateResultSetV1":
        raise DecisionReplayError("expected GateResultSetV1")
    if gate_result.get("schema_version") != "1.1.0":
        raise DecisionReplayError("unsupported GateResultSetV1 schema_version")
    try:
        verify_self_hash(gate_result, path="GateResultSetV1")
    except ValueError as exc:
        raise IntegrityValidationError(str(exc)) from exc
    errors = validate_gate_result_with_policy(
        dict(gate_result),
        schema_dir,
        gate_policy_path=gate_policy_path,
    )
    if errors:
        raise DecisionReplayError(
            "gate result verification failed: " + "; ".join(errors)
        )
    if gate_result.get("candidate_key") != global_input.get("candidate_key"):
        raise DecisionReplayError("gate result candidate_key differs from input")
    if gate_result.get("input_contract_sha256") != global_input.get(
        "input_contract_sha256"
    ):
        raise DecisionReplayError(
            "gate result input_contract_sha256 differs from input"
        )
