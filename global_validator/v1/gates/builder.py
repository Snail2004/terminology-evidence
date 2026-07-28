from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from terminology_contracts.integrity import canonical_sha256, seal_self_hash
from terminology_contracts.registries import (
    ATTESTATION_GATE_SIGNAL_IDS,
    CONTEXT_GATE_SIGNAL_IDS,
    GATE_IDS,
)
from terminology_contracts.validation import validate_gate_result_with_policy

from ..errors import GateProjectionError
from .policy_loader import GateActionPolicy

_OWNER_MODULES: dict[str, list[str]] = {
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
_MODULE_ORDER = {name: index for index, name in enumerate(
    ("CONTRACT", "SENSE", "C", "E", "GLOBAL", "HUMAN_REVIEW")
)}


def build_gate_result_set(
    global_input: Mapping[str, Any],
    *,
    action_policy: GateActionPolicy,
    gate_policy_path: Any,
    schema_dir: Any,
) -> dict[str, Any]:
    accumulated: dict[str, dict[str, list[Any]]] = {
        gate_id: {"modules": [], "reasons": [], "refs": []}
        for gate_id in GATE_IDS
    }
    _project_producer_signals(
        global_input.get("context_evidence"),
        module="C",
        expected_ids=CONTEXT_GATE_SIGNAL_IDS,
        accumulated=accumulated,
    )
    _project_producer_signals(
        global_input.get("attestation_evidence"),
        module="E",
        expected_ids=ATTESTATION_GATE_SIGNAL_IDS,
        accumulated=accumulated,
    )
    _project_constraints(global_input, accumulated)

    observations: list[dict[str, Any]] = []
    for gate_id in GATE_IDS:
        item = accumulated[gate_id]
        triggered = bool(item["reasons"])
        modules = item["modules"] if triggered else _OWNER_MODULES[gate_id]
        observations.append(
            {
                "gate_id": gate_id,
                "triggered": triggered,
                "action": action_policy.actions[gate_id] if triggered else "NONE",
                "reason_codes": sorted(set(item["reasons"])) if triggered else [],
                "evidence_refs": _stable_refs(item["refs"]) if triggered else [],
                "source_modules": sorted(set(modules), key=_module_sort_key),
            }
        )

    result = seal_self_hash(
        {
            "schema_id": "GateResultSetV1",
            "schema_version": "1.1.0",
            "candidate_key": copy.deepcopy(global_input.get("candidate_key")),
            "input_contract_sha256": global_input.get("input_contract_sha256"),
            "gate_policy_version": "1.0.0",
            "observations": observations,
            "binding_status": "COMPLETE",
            "gate_policy_artifact_sha256": (
                action_policy.gate_policy_artifact_sha256
            ),
            "integrity": {"self_sha256": "0" * 64},
        }
    )
    errors = validate_gate_result_with_policy(
        result,
        schema_dir,
        gate_policy_path=gate_policy_path,
    )
    if errors:
        raise GateProjectionError("GateResultSet validation failed: " + "; ".join(errors))
    return result


def _project_producer_signals(
    package: Any,
    *,
    module: str,
    expected_ids: tuple[str, ...],
    accumulated: dict[str, dict[str, list[Any]]],
) -> None:
    if not isinstance(package, Mapping):
        raise GateProjectionError(f"{module} evidence package is missing")
    signals = package.get("gate_signals")
    if not isinstance(signals, list):
        raise GateProjectionError(f"{module} gate_signals are missing")
    by_id = {
        signal.get("gate_id"): signal
        for signal in signals
        if isinstance(signal, Mapping)
    }
    if set(by_id) != set(expected_ids):
        raise GateProjectionError(f"{module} gate_signals do not cover registry")
    package_ref = _package_ref(package, module)
    for gate_id in expected_ids:
        signal = by_id[gate_id]
        if signal.get("asserted") is not True:
            continue
        target = accumulated[gate_id]
        target["modules"].append(module)
        target["reasons"].extend(signal.get("reason_codes", []))
        refs = signal.get("evidence_refs", [])
        target["refs"].extend(refs if refs else [package_ref])


def _project_constraints(
    global_input: Mapping[str, Any],
    accumulated: dict[str, dict[str, list[Any]]],
) -> None:
    constraint = global_input.get("constraint_evidence")
    if not isinstance(constraint, Mapping):
        raise GateProjectionError("ConstraintEvidencePackageV1 is missing")
    fallback = _package_ref(constraint, "CONSTRAINT")

    sense = constraint.get("sense_review", {})
    if sense.get("status") != "VERIFIED":
        _append_constraint(
            accumulated["sense_definition_unverified"],
            "SENSE",
            "SENSE_DEFINITION_UNVERIFIED",
            sense.get("review_artifact_ref") or fallback,
        )

    polysemy = constraint.get("polysemy_resolution", {})
    if polysemy.get("status") == "UNRESOLVED":
        _append_constraint(
            accumulated["unresolved_polysemy"],
            "SENSE",
            "UNRESOLVED_POLYSEMY",
            polysemy.get("authority_ref") or fallback,
        )

    collision = constraint.get("target_collision", {})
    if collision.get("status") != "CLEAR":
        reason = (
            "TARGET_COLLISION"
            if collision.get("status") == "COLLISION"
            else "TARGET_COLLISION_UNJUDGEABLE"
        )
        refs = list(collision.get("evidence_refs", []))
        if collision.get("collision_index_ref"):
            refs.append(collision["collision_index_ref"])
        if not refs:
            refs.append(fallback)
        target = accumulated["target_collision"]
        target["modules"].append("GLOBAL")
        target["reasons"].append(reason)
        target["refs"].extend(refs)


def _append_constraint(
    target: dict[str, list[Any]],
    module: str,
    reason: str,
    reference: Mapping[str, Any],
) -> None:
    target["modules"].append(module)
    target["reasons"].append(reason)
    target["refs"].append(reference)


def _package_ref(package: Mapping[str, Any], module: str) -> dict[str, str]:
    self_hash = package.get("integrity", {}).get("self_sha256")
    if not isinstance(self_hash, str):
        raise GateProjectionError(f"{module} package self hash is missing")
    return {
        "evidence_id": f"sealed-package:{module.lower()}:{self_hash[:16]}",
        "evidence_type": (
            "CONSTRAINT_EVIDENCE" if module == "CONSTRAINT" else "OTHER"
        ),
        "uri": f"artifact://global-input/{module.lower()}",
        "sha256": self_hash,
    }


def _stable_refs(refs: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for reference in refs:
        if not isinstance(reference, Mapping):
            raise GateProjectionError("gate evidence reference must be an object")
        marker = canonical_sha256(reference)
        if marker not in seen:
            seen.add(marker)
            result.append(copy.deepcopy(dict(reference)))
    return result


def _module_sort_key(module: str) -> int:
    return _MODULE_ORDER.get(module, len(_MODULE_ORDER))
