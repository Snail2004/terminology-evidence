from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import (
    load_verified_json_artifact,
)
from terminology_contracts.registries import GATE_IDS
from terminology_contracts.validation import validate_instance

from ..errors import GatePolicyError
from ..jsonio import assert_strict_json_file, load_json_object
from .action_policy_authority import verify_action_policy_authority


@dataclass(frozen=True)
class GateActionPolicy:
    policy_id: str
    policy_version: str
    gate_policy_artifact_sha256: str
    self_sha256: str
    authority_sha256: str
    authority_payload: dict[str, Any]
    actions: dict[str, str]
    payload: dict[str, Any]


def load_gate_action_policy(
    path: Path,
    *,
    gate_policy_path: Path,
    schema_dir: Path,
) -> GateActionPolicy:
    authority = verify_action_policy_authority()
    try:
        assert_strict_json_file(path)
        assert_strict_json_file(gate_policy_path)
        artifact = load_verified_json_artifact(path)
        gate_policy = load_verified_json_artifact(gate_policy_path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise GatePolicyError(str(exc)) from exc
    payload = artifact.payload
    if payload.get("schema_id") != "GlobalGateActionSelectionPolicyV1":
        raise GatePolicyError("unsupported gate action policy schema_id")
    if payload.get("schema_version") != "1.0.0":
        raise GatePolicyError("unsupported gate action policy schema_version")
    if payload.get("gate_policy_artifact_sha256") != gate_policy.self_sha256:
        raise GatePolicyError("action policy is bound to another GatePolicyArtifact")
    if artifact.self_sha256 != authority.approved_action_policy_sha256:
        raise GatePolicyError(
            "action policy differs from the reviewed Global authority pin"
        )
    gate_errors = validate_instance(gate_policy.payload, schema_dir)
    if gate_errors:
        raise GatePolicyError("invalid GatePolicyArtifact: " + "; ".join(gate_errors))
    actions = payload.get("actions")
    if not isinstance(actions, dict) or set(actions) != set(GATE_IDS):
        raise GatePolicyError("action policy must cover the gate registry exactly")
    rules = gate_policy.payload.get("rules", {})
    for gate_id in GATE_IDS:
        action = actions.get(gate_id)
        allowed = rules.get(gate_id, {}).get("allowed_actions", [])
        if action not in allowed:
            raise GatePolicyError(
                f"action policy selects forbidden action {action!r} for {gate_id}"
            )
    return GateActionPolicy(
        policy_id=str(payload.get("policy_id")),
        policy_version=str(payload.get("policy_version")),
        gate_policy_artifact_sha256=gate_policy.self_sha256,
        self_sha256=artifact.self_sha256,
        authority_sha256=authority.self_sha256,
        authority_payload=authority.payload,
        actions={gate_id: str(actions[gate_id]) for gate_id in GATE_IDS},
        payload=payload,
    )


def load_unverified_policy_payload(path: Path) -> dict[str, Any]:
    """Review helper that never grants runtime authority."""
    try:
        value = load_json_object(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise GatePolicyError(f"cannot load gate action policy: {exc}") from exc
    return value
