from __future__ import annotations

import copy

import pytest

from conftest import load_v11, validate_payload
from terminology_contracts.integrity import seal_self_hash


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("candidate_id", "candidate-other"),
        ("candidate_version", "2"),
        ("sense_id", "sense-other"),
        ("scope_id", "scope-other"),
        ("dataset_manifest_sha256", "f" * 64),
        ("effective_sense_contract_sha256", "e" * 64),
    ],
)
def test_context_candidate_join_mismatch_rejects(field: str, replacement: str) -> None:
    envelope = load_v11("global_validator_input.json")
    envelope["context_evidence"]["candidate_key"][field] = replacement
    envelope["context_evidence"] = seal_self_hash(envelope["context_evidence"])
    envelope["assembly_metadata"]["source_package_hashes"][
        "context_evidence_sha256"
    ] = envelope["context_evidence"]["integrity"]["self_sha256"]
    errors = validate_payload(seal_self_hash(envelope))
    assert any("context_evidence.candidate_key mismatch" in error for error in errors)


def test_input_contract_hash_mismatch_rejects() -> None:
    envelope = load_v11("global_validator_input.json")
    envelope["attestation_evidence"]["input_contract_sha256"] = "f" * 64
    envelope["attestation_evidence"] = seal_self_hash(
        envelope["attestation_evidence"]
    )
    envelope["assembly_metadata"]["source_package_hashes"][
        "attestation_evidence_sha256"
    ] = envelope["attestation_evidence"]["integrity"]["self_sha256"]
    errors = validate_payload(seal_self_hash(envelope))
    assert any("attestation_evidence.input_contract_sha256 mismatch" in error for error in errors)


def test_nested_package_tamper_rejects_before_join() -> None:
    envelope = load_v11("global_validator_input.json")
    envelope["context_evidence"]["features"]["C_mean"] = 0.1
    errors = validate_payload(seal_self_hash(envelope))
    assert any("context_evidence.integrity.self_sha256 mismatch" in error for error in errors)
