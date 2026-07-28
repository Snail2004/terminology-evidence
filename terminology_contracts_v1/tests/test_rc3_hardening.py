from __future__ import annotations

import copy
import json

import pytest

from conftest import (
    GATE_POLICY,
    GLOBAL_INPUT,
    load_json,
    load_v11,
    reseal_decision,
    validate_payload,
)
from terminology_contracts.integrity import seal_self_hash


EVIDENCE_REF = {
    "evidence_id": "rc3-review-repro",
    "evidence_type": "OTHER",
    "uri": "artifact://tests/rc3-review-repro",
    "sha256": "a" * 64,
}


def _reseal_global_input(global_input: dict) -> dict:
    for hash_field, package_field in (
        ("context_evidence_sha256", "context_evidence"),
        ("attestation_evidence_sha256", "attestation_evidence"),
        ("effective_sense_contract_sha256", "effective_sense_contract"),
        ("frozen_candidate_contract_sha256", "frozen_candidate_contract"),
        ("constraint_evidence_sha256", "constraint_evidence"),
    ):
        global_input["assembly_metadata"]["source_package_hashes"][hash_field] = (
            global_input[package_field]["integrity"]["self_sha256"]
        )
    return seal_self_hash(global_input)


def _reseal_decision_for(decision: dict, global_input: dict) -> dict:
    hashes = decision["run_metadata"]["input_package_hashes"]
    hashes.update(
        global_validator_input_sha256=global_input["integrity"]["self_sha256"],
        context_evidence_sha256=global_input["context_evidence"]["integrity"][
            "self_sha256"
        ],
        attestation_evidence_sha256=global_input["attestation_evidence"]["integrity"][
            "self_sha256"
        ],
        effective_sense_contract_sha256=global_input["effective_sense_contract"][
            "integrity"
        ]["self_sha256"],
        frozen_candidate_contract_sha256=global_input["frozen_candidate_contract"][
            "integrity"
        ]["self_sha256"],
        constraint_evidence_sha256=global_input["constraint_evidence"]["integrity"][
            "self_sha256"
        ],
    )
    decision["context_evidence_sha256"] = hashes["context_evidence_sha256"]
    decision["attestation_evidence_sha256"] = hashes[
        "attestation_evidence_sha256"
    ]
    return reseal_decision(decision)


def _write_global_input(tmp_path, global_input: dict):
    path = tmp_path / "global_validator_input.json"
    path.write_text(json.dumps(global_input), encoding="utf-8")
    return path


def _assert_context_signal(global_input: dict, gate_id: str) -> None:
    context = copy.deepcopy(global_input["context_evidence"])
    context["flags"] = [
        {
            "code": gate_id,
            "severity": "CRITICAL",
            "message": "RC3 regression fixture",
            "evidence_refs": [EVIDENCE_REF],
        }
    ]
    signal = next(row for row in context["gate_signals"] if row["gate_id"] == gate_id)
    signal.update(
        asserted=True,
        reason_codes=["RC3_REVIEW_REPRO"],
        evidence_refs=[EVIDENCE_REF],
    )
    global_input["context_evidence"] = seal_self_hash(context)


@pytest.mark.parametrize("gate_id", ["wrong_sense", "missing_contrastive_context"])
def test_context_signal_cannot_be_omitted_from_gate_result(tmp_path, gate_id: str) -> None:
    global_input = load_json(GLOBAL_INPUT)
    _assert_context_signal(global_input, gate_id)
    if gate_id == "missing_contrastive_context":
        context = global_input["context_evidence"]
        context["contrastive_status"] = "ABSENT"
        global_input["context_evidence"] = seal_self_hash(context)
    global_input = _reseal_global_input(global_input)
    decision = _reseal_decision_for(
        load_v11("global_decision_package.json"), global_input
    )
    errors = validate_payload(
        decision,
        global_input_path=_write_global_input(tmp_path, global_input),
    )
    assert any(f"gate {gate_id} disagrees with C/E gate signals" in e for e in errors)


def test_attestation_unjudgeable_cannot_be_omitted_from_gate_result(tmp_path) -> None:
    global_input = load_json(GLOBAL_INPUT)
    attestation = copy.deepcopy(global_input["attestation_evidence"])
    attestation["local_status"] = "ATTESTATION_UNJUDGEABLE"
    attestation["accepted_evidence_refs"] = []
    signal = next(
        row
        for row in attestation["gate_signals"]
        if row["gate_id"] == "attestation_unjudgeable"
    )
    signal.update(asserted=True, reason_codes=["ATTESTATION_UNJUDGEABLE"])
    global_input["attestation_evidence"] = seal_self_hash(attestation)
    global_input = _reseal_global_input(global_input)
    decision = _reseal_decision_for(
        load_v11("global_decision_package.json"), global_input
    )
    errors = validate_payload(
        decision,
        global_input_path=_write_global_input(tmp_path, global_input),
    )
    assert any("attestation_unjudgeable disagrees with C/E gate signals" in e for e in errors)


@pytest.mark.parametrize(
    ("gate_id", "action", "decision_status"),
    [
        ("wrong_sense", "CAP_PROVISIONAL", "PROVISIONAL"),
        ("concept_mismatch", "CAP_PROVISIONAL", "PROVISIONAL"),
        ("insufficient_evidence", "FATAL_SPLIT", "SPLIT_REQUIRED"),
        ("target_collision", "FATAL_REJECT", "REJECTED"),
    ],
)
def test_sealed_policy_rejects_gate_action_drift(
    tmp_path, gate_id: str, action: str, decision_status: str
) -> None:
    global_input = load_json(GLOBAL_INPUT)
    if gate_id == "target_collision":
        constraint = copy.deepcopy(global_input["constraint_evidence"])
        conflicting = copy.deepcopy(constraint["candidate_key"])
        conflicting["candidate_id"] = "other-candidate"
        conflicting["candidate_vi"] = "ứng viên khác"
        constraint["target_collision"].update(
            status="COLLISION",
            conflicting_candidate_keys=[conflicting],
            evidence_refs=[EVIDENCE_REF],
        )
        global_input["constraint_evidence"] = seal_self_hash(constraint)
    else:
        _assert_context_signal(global_input, gate_id)
    global_input = _reseal_global_input(global_input)

    decision = load_v11("global_decision_package.json")
    decision["decision_policy"].update(
        mode="DEVELOPMENT_HEURISTIC",
        calibration_artifact_sha256=None,
        threshold=None,
    )
    decision["approval_score"] = None
    decision["decision"] = decision_status
    observation = next(
        row
        for row in decision["gate_results"]["observations"]
        if row["gate_id"] == gate_id
    )
    observation.update(
        triggered=True,
        action=action,
        reason_codes=["RC3_REVIEW_REPRO"],
        evidence_refs=[EVIDENCE_REF],
    )
    decision["gate_results"] = seal_self_hash(decision["gate_results"])
    decision = _reseal_decision_for(decision, global_input)
    errors = validate_payload(
        decision,
        calibration_path=None,
        global_input_path=_write_global_input(tmp_path, global_input),
    )
    assert any("is not allowed by the sealed gate policy" in error for error in errors)


def test_gate_policy_cannot_be_resealed_with_rule_drift() -> None:
    policy = load_json(GATE_POLICY)
    policy["rules"]["wrong_sense"]["allowed_actions"] = ["CAP_PROVISIONAL"]
    errors = validate_payload(seal_self_hash(policy))
    assert any("gate policy rule drift: wrong_sense" in error for error in errors)


def test_threshold_stability_interval_order_is_enforced() -> None:
    calibration = load_v11("calibration_artifact.json")
    calibration["threshold_stability"].update(
        threshold_ci_lower=0.9,
        threshold_median=0.84,
        threshold_ci_upper=0.8,
    )
    errors = validate_payload(seal_self_hash(calibration))
    assert any("ci_lower <= median <= ci_upper" in error for error in errors)


def test_complete_global_input_cannot_use_nested_legacy_signal_exemption() -> None:
    global_input = load_json(GLOBAL_INPUT)
    context = copy.deepcopy(global_input["context_evidence"])
    context["provenance"]["component_version"] = "1.0.0"
    context.pop("gate_signals")
    global_input["context_evidence"] = seal_self_hash(context)
    global_input = _reseal_global_input(global_input)

    errors = validate_payload(global_input, allow_legacy_migration=True)

    assert any("native C evidence requires gate_signals" in error for error in errors)


def test_complete_gate_set_cannot_spoof_legacy_decision_policy_exemption() -> None:
    decision = load_v11("global_decision_package.json")
    forged_policy_hash = "b" * 64
    decision["run_metadata"]["binding_status"] = "LEGACY_INCOMPLETE"
    decision["decision_policy"][
        "gate_policy_artifact_sha256"
    ] = forged_policy_hash
    decision["gate_results"][
        "gate_policy_artifact_sha256"
    ] = forged_policy_hash
    decision["gate_results"] = seal_self_hash(decision["gate_results"])
    decision["run_metadata"][
        "gate_policy_artifact_sha256"
    ] = forged_policy_hash
    decision["run_metadata"]["input_package_hashes"][
        "gate_policy_artifact_sha256"
    ] = forged_policy_hash
    decision = reseal_decision(decision)

    errors = validate_payload(decision, allow_legacy_migration=True)

    assert any("GatePolicyArtifact verification failed" in error for error in errors)
