from __future__ import annotations

import copy
from pathlib import Path

import pytest

from global_validator.v1.authority import verify_authority
from global_validator.v1.config import validate_run_config
from global_validator.v1.errors import (
    AuthorityVerificationError,
    InputValidationError,
    IntegrityValidationError,
    JoinValidationError,
)
from global_validator.v1.input import (
    assemble_global_input,
    load_contract_artifact,
    verify_collision_index_binding,
)

from .helpers import load_base_input


def test_authority_accepts_canonical_published_receipt_only(
    repository_root: Path, authority_receipt: Path, tmp_path: Path
) -> None:
    verified = verify_authority(
        authority_receipt,
        repository_root / "terminology_contracts_v1",
        repository_root=repository_root,
    )
    assert verified.receipt_integrity_mode == "CANONICAL_SELF_HASH"
    assert verified.warnings == ()

    tampered = tmp_path / "authority_receipt.json"
    tampered.write_bytes(authority_receipt.read_bytes() + b" ")
    with pytest.raises(AuthorityVerificationError, match="physical SHA-256"):
        verify_authority(
            tampered,
            repository_root / "terminology_contracts_v1",
            repository_root=repository_root,
        )


@pytest.mark.parametrize(
    "payload,error",
    [
        ('{"schema_id":"A","schema_id":"B"}', "duplicate JSON key"),
        ('{"schema_id":"A","value":NaN}', "non-finite JSON number"),
        ('{"schema_id":"A"} trailing', "Extra data"),
    ],
)
def test_strict_json_rejects_ambiguous_inputs(
    payload: str, error: str, repository_root: Path, tmp_path: Path
) -> None:
    path = tmp_path / "input.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(InputValidationError, match=error):
        load_contract_artifact(
            path,
            schema_dir=(
                repository_root / "terminology_contracts_v1" / "schemas" / "v1.1.0"
            ),
        )


def test_assembler_rejects_exact_join_mismatch(
    valid_input_path: Path, repository_root: Path
) -> None:
    value = load_base_input(valid_input_path)
    attestation = copy.deepcopy(value["attestation_evidence"])
    attestation["candidate_key"]["candidate_id"] = "another-candidate"
    with pytest.raises(JoinValidationError, match="candidate_key mismatch"):
        assemble_global_input(
            effective_sense_contract=value["effective_sense_contract"],
            frozen_candidate_contract=value["frozen_candidate_contract"],
            constraint_evidence=value["constraint_evidence"],
            context_evidence=value["context_evidence"],
            attestation_evidence=attestation,
        )


def test_collision_index_is_required_and_physically_bound(
    valid_input_path: Path, collision_index_path: Path, tmp_path: Path
) -> None:
    value = load_base_input(valid_input_path)
    with pytest.raises(IntegrityValidationError, match="requires"):
        verify_collision_index_binding(value, None)

    tampered = tmp_path / "collision_index.json"
    tampered.write_bytes(collision_index_path.read_bytes() + b"\n")
    with pytest.raises(IntegrityValidationError, match="physical SHA-256"):
        verify_collision_index_binding(value, tampered)

    verify_collision_index_binding(value, collision_index_path)


def test_run_config_rejects_unsafe_id_and_time_order(config_factory) -> None:
    with pytest.raises(InputValidationError, match="safe identifier"):
        validate_run_config(config_factory(run_id="../escape"))
    with pytest.raises(InputValidationError, match="started_at"):
        validate_run_config(
            config_factory(
                started_at="2026-07-29T00:00:02+00:00",
                completed_at="2026-07-29T00:00:01+00:00",
            )
        )
