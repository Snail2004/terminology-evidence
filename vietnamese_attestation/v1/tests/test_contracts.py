from __future__ import annotations

import copy

import pytest

from vietnamese_attestation.v1.contracts.base import ContractValidationError
from vietnamese_attestation import v1
from vietnamese_attestation.v1.contracts.frozen_candidate import (
    FROZEN_CANDIDATE_SCHEMA_ID,
    validate_frozen_candidate,
)


def test_public_facade_exposes_versioned_input_and_output_contracts() -> None:
    assert v1.FROZEN_CANDIDATE_SCHEMA_ID == "FrozenTerminologyCandidateV1"
    assert v1.PACKAGE_SCHEMA_ID == "VietnameseAttestationPackageV1"
    assert callable(v1.seal_frozen_candidate)
    assert callable(v1.validate_attestation_package)


def test_frozen_candidate_is_hash_bound(
    frozen_candidate: dict[str, object],
) -> None:
    validated = validate_frozen_candidate(frozen_candidate)
    assert validated["schema_id"] == FROZEN_CANDIDATE_SCHEMA_ID
    assert len(validated["integrity"]["frozen_candidate_sha256"]) == 64

    tampered = copy.deepcopy(frozen_candidate)
    tampered["source_term"] = "prediction"
    with pytest.raises(ContractValidationError, match="self-hash mismatch"):
        validate_frozen_candidate(tampered)


def test_frozen_candidate_rejects_surface_drift(
    frozen_candidate: dict[str, object],
) -> None:
    tampered = copy.deepcopy(frozen_candidate)
    tampered["known_surfaces"]["canonical"] = "suy diễn"
    with pytest.raises(
        ContractValidationError, match="canonical surface must equal candidate_vi"
    ):
        validate_frozen_candidate(tampered)


def test_frozen_candidate_rejects_unknown_fields(
    frozen_candidate: dict[str, object],
) -> None:
    tampered = copy.deepcopy(frozen_candidate)
    tampered["context_substitution_score"] = 0.9
    with pytest.raises(ContractValidationError, match="unknown keys"):
        validate_frozen_candidate(tampered)
