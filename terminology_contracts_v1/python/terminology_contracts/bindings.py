from __future__ import annotations

import copy
import unicodedata
from typing import Any, Mapping

from .canonical import calculate_binding_sha256
from .integrity import canonical_sha256, seal_self_hash


def calculate_input_contract_sha256(value: Mapping[str, Any]) -> str:
    """Bind every Frozen Candidate field except the hash being calculated."""
    return calculate_binding_sha256(
        dict(value), excluded_fields=("input_contract_sha256",)
    )


def seal_frozen_candidate_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    result["binding_status"] = "COMPLETE"
    result["input_contract_sha256"] = calculate_input_contract_sha256(result)
    return seal_self_hash(result)


def verify_frozen_candidate_binding(value: Mapping[str, Any]) -> bool:
    expected = value.get("input_contract_sha256")
    return isinstance(expected, str) and expected == calculate_input_contract_sha256(
        value
    )


def replay_spec_payload(decision: Mapping[str, Any]) -> dict[str, Any]:
    metadata = decision.get("run_metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    gates = decision.get("gate_results")
    if not isinstance(gates, Mapping):
        gates = {}
    return {
        "candidate_key": decision.get("candidate_key"),
        "input_contract_sha256": decision.get("input_contract_sha256"),
        "decision_policy": decision.get("decision_policy"),
        "decision_features": decision.get("decision_features"),
        "gate_policy_version": gates.get("gate_policy_version"),
        "input_package_hashes": metadata.get("input_package_hashes"),
        "global_run_spec_id": metadata.get("global_run_spec_id"),
        "engine_version": metadata.get("engine_version"),
        "execution_config_sha256": metadata.get("execution_config_sha256"),
        "feature_contract_version": metadata.get("feature_contract_version"),
    }


def calculate_replay_spec_sha256(decision: Mapping[str, Any]) -> str:
    return canonical_sha256(replay_spec_payload(decision))


def normalize_term(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())
