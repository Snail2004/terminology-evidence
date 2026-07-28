from __future__ import annotations

import json

import pytest

from conftest import (
    GATE_POLICY,
    MIGRATED_V11,
    SCHEMAS,
    VALID_V11,
    load_json,
    load_v11,
)
from terminology_contracts.integrity import seal_self_hash
from terminology_contracts.validation import (
    schema_validate_instance,
    validate_gate_result_with_policy,
    validate_instance,
    verify_certificate_bundle,
)


def _verify(*, certificate_path, tac_path=None):
    return verify_certificate_bundle(
        certificate_path=certificate_path,
        frozen_candidate_path=VALID_V11 / "frozen_candidate_contract.json",
        effective_sense_contract_path=VALID_V11 / "effective_sense_contract.json",
        constraint_evidence_path=VALID_V11 / "constraint_evidence_package.json",
        global_input_path=VALID_V11 / "global_validator_input.json",
        context_evidence_path=VALID_V11 / "context_evidence_package.json",
        attestation_evidence_path=VALID_V11 / "attestation_evidence_package.json",
        gate_result_path=VALID_V11 / "gate_result_set.json",
        decision_path=VALID_V11 / "global_decision_package.json",
        calibration_path=VALID_V11 / "calibration_artifact.json",
        gate_policy_path=GATE_POLICY,
        collision_index_path=(
            VALID_V11.parents[1] / "support" / "v1.1.0" / "collision_index.json"
        ),
        schema_dir=SCHEMAS,
        feature_registry_path=(
            SCHEMAS.parent / "registries" / "feature_contract_v1.1.0.json"
        ),
        tac_path=tac_path,
    )


def _mutate_certificate(certificate: dict, mutation: str) -> None:
    context = load_v11("context_evidence_package.json")
    if mutation == "allowed_variant":
        certificate["allowed_variants"].append("hoan toan sai")
    elif mutation == "removed_forbidden":
        certificate["forbidden_candidates"] = []
    elif mutation == "scope":
        certificate["scope_note"] = "Valid in every domain and every context."
    elif mutation == "C_mean":
        certificate["evidence_summary"]["C_mean"] = 0.01
    elif mutation == "E_features":
        certificate["evidence_summary"]["E_features"]["E_authority"] = 0.01
    elif mutation == "threshold":
        certificate["threshold_version"] = "arbitrary-threshold-v999"
    elif mutation == "contrastive":
        certificate["validity_context_refs"] = context["support_set"][
            "contrastive_refs"
        ]
    elif mutation == "negative":
        certificate["validity_context_refs"] = context["support_set"][
            "negative_or_boundary_refs"
        ]
    elif mutation == "issued_before_decision":
        certificate["issued_at"] = "2026-07-28T10:59:59+00:00"
    else:  # pragma: no cover - test table is closed.
        raise AssertionError(mutation)


MUTATION_EXPECTATIONS = (
    ("allowed_variant", "allowed_variants differs"),
    ("removed_forbidden", "forbidden_candidates differs"),
    ("scope", "scope_note differs"),
    ("C_mean", "evidence_summary.C_mean differs"),
    ("E_features", "evidence_summary.E_features differs"),
    ("threshold", "threshold_version differs"),
    ("contrastive", "must equal positive support refs"),
    ("negative", "must equal positive support refs"),
    ("issued_before_decision", "issued_at precedes decision completion"),
)


@pytest.mark.parametrize(("mutation", "expected"), MUTATION_EXPECTATIONS)
def test_certificate_application_mutation_rejects(
    tmp_path, mutation: str, expected: str
) -> None:
    certificate = load_v11("terminology_certificate.json")
    _mutate_certificate(certificate, mutation)
    certificate = seal_self_hash(certificate)
    certificate_path = tmp_path / "certificate.json"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    errors = _verify(certificate_path=certificate_path)

    assert any(expected in error for error in errors)


@pytest.mark.parametrize(("mutation", "expected"), MUTATION_EXPECTATIONS)
def test_tac_cannot_embed_mutated_certificate(
    tmp_path, mutation: str, expected: str
) -> None:
    certificate = load_v11("terminology_certificate.json")
    _mutate_certificate(certificate, mutation)
    certificate = seal_self_hash(certificate)
    certificate_path = tmp_path / "certificate.json"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    tac = load_v11("tac_occurrence_input.json")
    tac["certificate"] = certificate
    tac_path = tmp_path / "tac.json"
    tac_path.write_text(json.dumps(seal_self_hash(tac)), encoding="utf-8")

    errors = _verify(certificate_path=certificate_path, tac_path=tac_path)

    assert any(expected in error for error in errors)


@pytest.mark.parametrize(
    "filename",
    ["context_evidence_package.json", "attestation_evidence_package.json"],
)
def test_native_gate_signals_are_json_schema_required(filename: str) -> None:
    evidence = load_v11(filename)
    evidence.pop("gate_signals")

    errors = schema_validate_instance(evidence, SCHEMAS)

    assert any("'gate_signals' is a required property" in error for error in errors)


@pytest.mark.parametrize(
    "filename",
    ["context_evidence_package.json", "attestation_evidence_package.json"],
)
def test_legacy_migration_remains_schema_compatible_without_gate_signals(
    filename: str,
) -> None:
    evidence = load_json(MIGRATED_V11 / filename)

    assert schema_validate_instance(evidence, SCHEMAS) == []


def test_standalone_gate_result_requires_loaded_policy() -> None:
    gates = load_v11("gate_result_set.json")

    errors = validate_instance(gates, SCHEMAS, gate_policy_path=None)

    assert any("requires a loaded GatePolicyArtifact" in error for error in errors)


def test_standalone_gate_result_rejects_policy_action_drift() -> None:
    gates = load_v11("gate_result_set.json")
    wrong_sense = next(
        row for row in gates["observations"] if row["gate_id"] == "wrong_sense"
    )
    wrong_sense.update(
        triggered=True,
        action="CAP_PROVISIONAL",
        reason_codes=["RC4_POLICY_REPRO"],
        evidence_refs=[
            {
                "evidence_id": "rc4-policy-repro",
                "evidence_type": "OTHER",
                "uri": "artifact://tests/rc4-policy-repro",
                "sha256": "a" * 64,
            }
        ],
    )
    gates = seal_self_hash(gates)

    errors = validate_gate_result_with_policy(
        gates,
        SCHEMAS,
        gate_policy_path=GATE_POLICY,
    )

    assert any("is not allowed by the sealed gate policy" in error for error in errors)
