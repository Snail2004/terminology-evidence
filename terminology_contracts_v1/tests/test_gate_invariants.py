from __future__ import annotations

import copy

import pytest

from conftest import load_v11, reseal_decision, validate_payload
from terminology_contracts.integrity import seal_self_hash


NEW_GATES = (
    ("missing_contrastive_context", "C"),
    ("incomplete_context_type_coverage", "C"),
    ("attestation_unjudgeable", "E"),
)


def test_three_v11_gates_are_schema_valid() -> None:
    gates = load_v11("gate_result_set.json")
    for gate_id, source in NEW_GATES:
        gates["observations"].append(
            {
                "gate_id": gate_id,
                "triggered": False,
                "action": "NONE",
                "source_modules": [source],
                "reason_codes": [],
                "evidence_refs": [],
            }
        )
    assert validate_payload(seal_self_hash(gates)) == []


@pytest.mark.parametrize(
    ("triggered", "action", "needle"),
    [
        (False, "FATAL_REJECT", "non-triggered gate must use action NONE"),
        (True, "NONE", "triggered gate cannot use action NONE"),
    ],
)
def test_trigger_action_invariants(triggered: bool, action: str, needle: str) -> None:
    gates = load_v11("gate_result_set.json")
    gates["observations"][0].update(triggered=triggered, action=action)
    assert any(needle in error for error in validate_payload(seal_self_hash(gates)))


def test_gate_severity_alias_is_rejected() -> None:
    gates = load_v11("gate_result_set.json")
    gates["observations"][0]["severity"] = gates["observations"][0].pop("action")
    errors = validate_payload(seal_self_hash(gates))
    assert any("action" in error or "severity" in error for error in errors)


@pytest.mark.parametrize(
    ("action", "decision"),
    [
        ("FATAL_SPLIT", "SPLIT_REQUIRED"),
        ("FATAL_REJECT", "REJECTED"),
        ("ESCALATE_HUMAN", "HUMAN_REVIEW"),
        ("CAP_PROVISIONAL", "PROVISIONAL"),
    ],
)
def test_gate_precedence_resolves_to_allowed_decision(action: str, decision: str) -> None:
    package = load_v11("global_decision_package.json")
    package["decision_policy"].update(
        mode="DEVELOPMENT_HEURISTIC",
        calibration_artifact_sha256=None,
        threshold=None,
    )
    package["approval_score"] = None
    package["certificate_ref"] = None
    package["decision"] = decision
    package["gate_results"]["observations"] = [
        {
            "gate_id": "wrong_sense",
            "triggered": True,
            "action": action,
            "source_modules": ["C"],
            "reason_codes": ["TEST_GATE"],
            "evidence_refs": [],
        }
    ]
    package["gate_results"] = seal_self_hash(package["gate_results"])
    assert validate_payload(reseal_decision(package), calibration_path=None) == []


def test_fatal_split_has_highest_precedence() -> None:
    package = load_v11("global_decision_package.json")
    package["decision"] = "REJECTED"
    package["gate_results"]["observations"] = [
        {
            "gate_id": "wrong_sense",
            "triggered": True,
            "action": "FATAL_REJECT",
            "source_modules": ["C"],
            "reason_codes": ["WRONG_SENSE"],
            "evidence_refs": [],
        },
        {
            "gate_id": "unresolved_polysemy",
            "triggered": True,
            "action": "FATAL_SPLIT",
            "source_modules": ["SENSE"],
            "reason_codes": ["SPLIT"],
            "evidence_refs": [],
        },
    ]
    package["gate_results"] = seal_self_hash(package["gate_results"])
    errors = validate_payload(reseal_decision(package))
    assert any("FATAL_SPLIT must resolve to SPLIT_REQUIRED" in error for error in errors)
