from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from terminology_contracts.integrity import seal_self_hash
from terminology_contracts.registries import GATE_IDS

from global_validator.v1.config import ExecutionMode
from global_validator.v1.decision import resolve_decision
from global_validator.v1.errors import GatePolicyError, GateProjectionError
from global_validator.v1.gates import build_gate_result_set, load_gate_action_policy

from .helpers import load_base_input


def _policy(config_factory):
    config = config_factory()
    return load_gate_action_policy(
        config.gate_action_policy_path,
        gate_policy_path=config.gate_policy_path,
        schema_dir=config.schema_dir,
    )


def _build(value, config_factory):
    config = config_factory()
    return build_gate_result_set(
        value,
        action_policy=_policy(config_factory),
        gate_policy_path=config.gate_policy_path,
        schema_dir=config.schema_dir,
    )


def test_gate_engine_emits_exact_registry_once(
    valid_input_path: Path, config_factory
) -> None:
    result = _build(load_base_input(valid_input_path), config_factory)
    observations = result["observations"]
    assert [item["gate_id"] for item in observations] == list(GATE_IDS)
    assert len({item["gate_id"] for item in observations}) == 12
    assert all(item["triggered"] is False for item in observations)
    assert all(item["action"] == "NONE" for item in observations)


@pytest.mark.parametrize(
    "producer_field,gate_id",
    [
        ("context_evidence", "concept_mismatch"),
        ("context_evidence", "wrong_sense"),
        ("context_evidence", "contradiction"),
        ("context_evidence", "judge_disagreement"),
        ("context_evidence", "missing_contrastive_context"),
        ("context_evidence", "incomplete_context_type_coverage"),
        ("attestation_evidence", "concept_mismatch"),
        ("attestation_evidence", "contradiction"),
        ("attestation_evidence", "judge_disagreement"),
    ],
)
def test_sensitive_producer_signal_requires_direct_evidence_reference(
    producer_field: str,
    gate_id: str,
    valid_input_path: Path,
    config_factory,
) -> None:
    value = load_base_input(valid_input_path)
    signal = next(
        item
        for item in value[producer_field]["gate_signals"]
        if item["gate_id"] == gate_id
    )
    signal.update(
        {
            "asserted": True,
            "reason_codes": [f"TEST_{gate_id.upper()}"],
            "evidence_refs": [],
        }
    )
    with pytest.raises(GateProjectionError, match="requires direct evidence_refs"):
        _build(value, config_factory)


def test_nonfatal_context_signal_may_use_sealed_package_fallback(
    valid_input_path: Path, config_factory
) -> None:
    value = load_base_input(valid_input_path)
    signal = next(
        item
        for item in value["context_evidence"]["gate_signals"]
        if item["gate_id"] == "insufficient_evidence"
    )
    signal.update(
        {
            "asserted": True,
            "reason_codes": ["INSUFFICIENT_CONTEXT_EVIDENCE"],
            "evidence_refs": [],
        }
    )
    result = _build(value, config_factory)
    observation = next(
        item
        for item in result["observations"]
        if item["gate_id"] == "insufficient_evidence"
    )
    assert observation["triggered"] is True
    assert observation["action"] == "CAP_PROVISIONAL"
    assert observation["source_modules"] == ["C"]
    assert observation["evidence_refs"][0]["uri"] == "artifact://global-input/c"


@pytest.mark.parametrize(
    "producer_field,module",
    [("context_evidence", "C"), ("attestation_evidence", "E")],
)
def test_every_registered_producer_signal_projects_without_loss(
    producer_field: str,
    module: str,
    valid_input_path: Path,
    config_factory,
) -> None:
    base = load_base_input(valid_input_path)
    gate_ids = [
        signal["gate_id"] for signal in base[producer_field]["gate_signals"]
    ]
    for gate_id in gate_ids:
        value = copy.deepcopy(base)
        signal = next(
            item
            for item in value[producer_field]["gate_signals"]
            if item["gate_id"] == gate_id
        )
        signal.update(
            {
                "asserted": True,
                "reason_codes": [f"TEST_{gate_id.upper()}"],
                "evidence_refs": [_producer_ref(value, producer_field)],
            }
        )
        result = _build(value, config_factory)
        observation = next(
            item for item in result["observations"] if item["gate_id"] == gate_id
        )
        assert observation["triggered"] is True
        assert module in observation["source_modules"]
        assert observation["reason_codes"] == [f"TEST_{gate_id.upper()}"]
        assert observation["evidence_refs"]


def test_constraint_fallback_refs_cover_unverified_unresolved_unjudgeable(
    valid_input_path: Path, config_factory
) -> None:
    value = load_base_input(valid_input_path)
    constraint = value["constraint_evidence"]
    constraint["sense_review"].update(
        {"status": "UNVERIFIED", "review_artifact_ref": None}
    )
    constraint["polysemy_resolution"].update(
        {"status": "UNRESOLVED", "authority_ref": None}
    )
    constraint["target_collision"].update(
        {
            "status": "UNJUDGEABLE",
            "collision_index_ref": None,
            "collision_index_sha256": None,
            "evidence_refs": [],
        }
    )
    result = _build(value, config_factory)
    by_id = {item["gate_id"]: item for item in result["observations"]}
    for gate_id in (
        "sense_definition_unverified",
        "unresolved_polysemy",
        "target_collision",
    ):
        assert by_id[gate_id]["triggered"] is True
        assert by_id[gate_id]["evidence_refs"]
        assert by_id[gate_id]["evidence_refs"][0]["sha256"] == constraint[
            "integrity"
        ]["self_sha256"]


def test_signal_registry_gap_fails_closed(valid_input_path: Path, config_factory) -> None:
    value = load_base_input(valid_input_path)
    value["context_evidence"]["gate_signals"].pop()
    with pytest.raises(GateProjectionError, match="do not cover registry"):
        _build(value, config_factory)


@pytest.mark.parametrize(
    "actions,expected",
    [
        (["CAP_PROVISIONAL"], "PROVISIONAL"),
        (["CAP_PROVISIONAL", "ESCALATE_HUMAN"], "HUMAN_REVIEW"),
        (["FATAL_REJECT", "ESCALATE_HUMAN"], "REJECTED"),
        (["FATAL_SPLIT", "FATAL_REJECT"], "SPLIT_REQUIRED"),
    ],
)
def test_decision_precedence(actions: list[str], expected: str) -> None:
    observations = [
        {
            "gate_id": GATE_IDS[index],
            "triggered": True,
            "action": action,
            "reason_codes": [f"R{index}"],
        }
        for index, action in enumerate(actions)
    ]
    result = resolve_decision(
        observations,
        mode=ExecutionMode.DEVELOPMENT_HEURISTIC,
        approval_score=None,
        threshold=None,
    )
    assert result.decision == expected


def test_action_policy_rejects_forbidden_selection(
    config_factory, tmp_path: Path
) -> None:
    config = config_factory()
    payload = json.loads(
        config.gate_action_policy_path.read_text(encoding="utf-8")
    )
    payload["actions"]["input_contract_mismatch"] = "CAP_PROVISIONAL"
    tampered = tmp_path / "policy.json"
    tampered.write_text(
        json.dumps(seal_self_hash(payload), ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(GatePolicyError, match="reviewed Global authority pin"):
        load_gate_action_policy(
            tampered,
            gate_policy_path=config.gate_policy_path,
            schema_dir=config.schema_dir,
        )


def test_action_policy_rejects_alternate_allowed_selection(
    config_factory, tmp_path: Path
) -> None:
    config = config_factory()
    payload = json.loads(
        config.gate_action_policy_path.read_text(encoding="utf-8")
    )
    payload["actions"]["unresolved_polysemy"] = "ESCALATE_HUMAN"
    alternate = tmp_path / "alternate-policy.json"
    alternate.write_text(
        json.dumps(seal_self_hash(payload), ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(GatePolicyError, match="reviewed Global authority pin"):
        load_gate_action_policy(
            alternate,
            gate_policy_path=config.gate_policy_path,
            schema_dir=config.schema_dir,
        )


def _producer_ref(value: dict, producer_field: str) -> dict:
    if producer_field == "context_evidence":
        return copy.deepcopy(
            value[producer_field]["support_set"]["positive_support_refs"][0]
        )
    return copy.deepcopy(value[producer_field]["accepted_evidence_refs"][0])
