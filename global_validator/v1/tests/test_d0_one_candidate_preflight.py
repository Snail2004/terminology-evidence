from __future__ import annotations

import copy
import hashlib
import json
import socket
import subprocess
from pathlib import Path

import pytest
from terminology_contracts.integrity import seal_self_hash, verify_self_hash

from global_validator.v1.errors import InputValidationError, IntegrityValidationError
from global_validator.v1.preflight import (
    CANARY_CANDIDATE_ID,
    PROVISIONAL_PREFLIGHT_STATUS,
    load_d0_canary_preflight,
    validate_d0_canary_preflight,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "d0_one_candidate_provisional_preflight_v1.json"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _value() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _sealed(value: dict) -> dict:
    return seal_self_hash(value)


def _git_blob(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{commit}:{path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def test_exact_canary_preparation_is_zero_provider_and_ready_for_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbid_network(*_args, **_kwargs):
        raise AssertionError("network access is forbidden in D0 preparation")

    monkeypatch.setattr(socket, "create_connection", forbid_network)
    result = load_d0_canary_preflight(FIXTURE)

    assert result["candidate_id"] == CANARY_CANDIDATE_ID
    assert result["candidate_count"] == 1
    assert result["status"] == PROVISIONAL_PREFLIGHT_STATUS
    assert result["mode"] == "DEVELOPMENT_HEURISTIC"
    assert result["claims"] == {
        "e_token_only_provider_integration_accepted_for_zero_provider_canary_preparation": True,
        "e_live_runtime_authority_active": False,
        "global_d0_development_preflight_pass": False,
        "run_authorized": False,
    }
    assert result["invariants"]["approval_score"] is None
    assert result["invariants"]["auto_approved_count"] == 0
    assert result["invariants"]["certificate_count"] == 0
    assert sum(
        result["invariants"][field]
        for field in (
            "provider_calls",
            "network_calls",
            "gold_access",
            "corpus_access",
        )
    ) == 0


def test_preparation_pins_resolve_to_exact_accepted_surface_bytes() -> None:
    payload = _value()

    c_raw = _git_blob(
        payload["surfaces"]["c01"]["commit"],
        "context_substitution/v2/providers/provider_role_plan.gpt_primary.v2.json",
    )
    assert hashlib.sha256(c_raw).hexdigest() == (
        "6a229435a2d84198dc88bee26c3b4bb5645b7b086849c4f5e1a13217a9152e61"
    )
    c_plan = json.loads(c_raw)
    verify_self_hash(c_plan, path="C-01 provider role plan")
    assert c_plan["integrity"]["self_sha256"] == payload["surfaces"]["c01"][
        "provider_role_plan_self_sha256"
    ]
    assert c_plan["final_decision_owner"] == "GLOBAL_TERMINOLOGY_VALIDATOR"

    si_raw = _git_blob(
        payload["surfaces"]["si"]["commit"],
        "docs/integration/harness_producer_safe_cohort_authority_release_v1.schema.json",
    )
    si_schema = json.loads(si_raw)
    assert si_schema["properties"]["schema_id"]["const"] == payload["surfaces"][
        "si"
    ]["release_schema_id"]
    assert si_schema["properties"]["supported_candidate_counts"]["const"] == [1, 15]
    for field in ("provider_calls", "network_calls", "gold_access"):
        assert si_schema["properties"][field]["const"] == 0
    assert si_schema["properties"]["final_glossary_decision"]["type"] == "null"

    e_surface = payload["surfaces"]["e05"]
    tree = subprocess.run(
        ["git", "rev-parse", f"{e_surface['draft4_token_accounting_commit']}^{{tree}}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert tree == e_surface["draft4_token_accounting_tree"]

    final_e_metadata = subprocess.run(
        [
            "git",
            "show",
            "-s",
            "--format=%P%n%T",
            e_surface["final_e_narrow_child"],
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert final_e_metadata == [
        e_surface["final_e_narrow_parent"],
        e_surface["final_e_narrow_tree"],
    ]
    final_e_blobs = {
        "e05_authority_adapter_blob_oid": (
            "vietnamese_attestation/v1/live/authority_adapter/e05.py"
        ),
        "token_accounting_adapter_blob_oid": (
            "vietnamese_attestation/v1/live/provider_adapters/token_accounting.py"
        ),
    }
    for field, path in final_e_blobs.items():
        blob_oid = subprocess.run(
            ["git", "rev-parse", f"{e_surface['final_e_narrow_child']}:{path}"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert blob_oid == e_surface[field]

    authority_raw = _git_blob(
        e_surface["draft4_token_accounting_commit"],
        "docs/live-run-protocol/v1_1/authority_bindings/"
        "main_token_accounting_authority_v1.json",
    )
    assert hashlib.sha256(authority_raw).hexdigest() == e_surface[
        "token_accounting_authority_physical_sha256"
    ]
    authority = json.loads(authority_raw)
    verify_self_hash(authority, path="Draft4 token accounting authority")
    assert authority["integrity"]["self_sha256"] == e_surface[
        "token_accounting_authority_self_sha256"
    ]
    assert authority["bindings"]["canary_candidate_id"] == CANARY_CANDIDATE_ID
    assert authority["bindings"]["candidate_set_sha256"] == payload["surfaces"][
        "si"
    ]["candidate_set_sha256"]
    assert authority["bindings"]["e_base_commit"] == e_surface["surface_commit"]
    assert authority["bindings"]["si_commit"] == payload["surfaces"]["si"]["commit"]
    assert authority["token_fields"] == [
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    ]
    assert authority["unknown_cost_representation"] == {
        "cost": None,
        "cost_status": "TOKEN_ONLY_COST_UNAVAILABLE",
        "currency": None,
    }
    assert authority["run_authorized"] is False


def test_token_only_accounting_accepts_exact_component_sum() -> None:
    value = _value()
    value["token_accounting"].update(
        input_tokens=11,
        output_tokens=7,
        reasoning_tokens=3,
        total_tokens=21,
    )
    result = validate_d0_canary_preflight(_sealed(value))
    assert result["token_accounting"] == {
        "status": "TOKEN_ONLY_COST_UNAVAILABLE",
        "input_tokens": 11,
        "output_tokens": 7,
        "reasoning_tokens": 3,
        "total_tokens": 21,
        "network_request_count": 0,
        "cost": None,
        "currency": None,
    }


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("total_tokens", 1, "total does not equal"),
        ("cost", 0.0, "must not invent cost"),
        ("currency", "USD", "must not invent cost"),
        ("status", "PRICED", "status is not token-only"),
        ("network_request_count", 1, "network_request_count must be zero"),
    ],
)
def test_token_only_accounting_rejects_unreviewed_pricing_or_drift(
    field: str, value: object, match: str
) -> None:
    payload = _value()
    payload["token_accounting"][field] = value
    with pytest.raises(InputValidationError, match=match):
        validate_d0_canary_preflight(_sealed(payload))


@pytest.mark.parametrize(
    "claim",
    [
        "e_token_only_provider_integration_accepted_for_zero_provider_canary_preparation",
        "e_live_runtime_authority_active",
        "global_d0_development_preflight_pass",
        "run_authorized",
    ],
)
def test_preparation_rejects_claim_drift(claim: str) -> None:
    payload = _value()
    payload["claims"][claim] = not payload["claims"][claim]
    with pytest.raises(InputValidationError, match="unauthorized claim"):
        validate_d0_canary_preflight(_sealed(payload))


@pytest.mark.parametrize(
    "field",
    [
        "final_e_narrow_child",
        "final_e_narrow_parent",
        "final_e_narrow_tree",
        "final_e_review_package_sha256",
        "final_e_complete_bundle_sha256",
        "e05_authority_adapter_blob_oid",
        "token_accounting_adapter_blob_oid",
    ],
)
def test_preparation_rejects_final_e_authority_drift(field: str) -> None:
    payload = _value()
    payload["surfaces"]["e05"][field] = "f" * 64
    with pytest.raises(InputValidationError, match="e05 differs from preparation pin"):
        validate_d0_canary_preflight(_sealed(payload))


@pytest.mark.parametrize(
    "field",
    [
        "draft4_token_accounting_commit",
        "draft4_token_accounting_tree",
        "token_accounting_authority_self_sha256",
        "token_accounting_authority_physical_sha256",
        "usage_snapshot_schema_physical_sha256",
        "live_ledger_schema_physical_sha256",
    ],
)
def test_preparation_rejects_draft4_token_authority_drift(field: str) -> None:
    payload = _value()
    payload["surfaces"]["e05"][field] = "f" * len(
        str(payload["surfaces"]["e05"][field])
    )
    with pytest.raises(InputValidationError, match="e05 differs from preparation pin"):
        validate_d0_canary_preflight(_sealed(payload))


def test_preparation_rejects_foreign_candidate_and_surface_pin() -> None:
    payload = _value()
    payload["candidate_id"] = "candidate_foreign"
    with pytest.raises(InputValidationError, match="candidate binding mismatch"):
        validate_d0_canary_preflight(_sealed(payload))

    payload = _value()
    payload["surfaces"]["si"]["candidate_set_sha256"] = "f" * 64
    with pytest.raises(InputValidationError, match="si differs from preparation pin"):
        validate_d0_canary_preflight(_sealed(payload))


def test_preparation_rejects_tampered_self_hash() -> None:
    payload = _value()
    payload["token_accounting"]["input_tokens"] = 1
    payload["token_accounting"]["total_tokens"] = 1
    with pytest.raises(IntegrityValidationError, match="self_sha256"):
        validate_d0_canary_preflight(payload)
