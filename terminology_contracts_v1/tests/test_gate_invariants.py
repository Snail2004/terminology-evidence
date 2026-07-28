from __future__ import annotations

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
    by_id = {row["gate_id"]: row for row in gates["observations"]}
    for gate_id, source in NEW_GATES:
        assert by_id[gate_id]["source_modules"] == [source]
    assert validate_payload(gates) == []


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
    observation = next(
        row
        for row in package["gate_results"]["observations"]
        if row["gate_id"] == "wrong_sense"
    )
    observation.update(
        triggered=True,
        action=action,
        reason_codes=["TEST_GATE"],
        evidence_refs=[
            {
                "evidence_id": "gate-test-001",
                "evidence_type": "OTHER",
                "uri": "artifact://tests/gate-test-001",
                "sha256": "a" * 64,
            }
        ],
    )
    package["gate_results"] = seal_self_hash(package["gate_results"])
    assert validate_payload(reseal_decision(package), calibration_path=None) == []


def test_fatal_split_has_highest_precedence() -> None:
    package = load_v11("global_decision_package.json")
    package["decision"] = "REJECTED"
    by_id = {
        row["gate_id"]: row for row in package["gate_results"]["observations"]
    }
    for gate_id, action, reason in (
        ("wrong_sense", "FATAL_REJECT", "WRONG_SENSE"),
        ("unresolved_polysemy", "FATAL_SPLIT", "SPLIT"),
    ):
        by_id[gate_id].update(
            triggered=True,
            action=action,
            reason_codes=[reason],
            evidence_refs=[
                {
                    "evidence_id": f"{gate_id}-test",
                    "evidence_type": "OTHER",
                    "uri": f"artifact://tests/{gate_id}",
                    "sha256": "a" * 64,
                }
            ],
        )
    package["gate_results"] = seal_self_hash(package["gate_results"])
    errors = validate_payload(reseal_decision(package))
    assert any("FATAL_SPLIT must resolve to SPLIT_REQUIRED" in error for error in errors)
