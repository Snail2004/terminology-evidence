from __future__ import annotations

import copy
import json
import shutil
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


def test_authority_accepts_canonical_r2_published_receipt_only(
    repository_root: Path, authority_receipt: Path, tmp_path: Path
) -> None:
    verified = verify_authority(
        authority_receipt,
        repository_root / "terminology_contracts_v1",
        repository_root=repository_root,
    )
    assert verified.receipt_integrity_mode == "CANONICAL_SELF_HASH"
    assert verified.warnings == ()
    assert verified.receipt["receipt_revision"] == 2

    tampered = tmp_path / "authority_receipt.json"
    tampered.write_bytes(authority_receipt.read_bytes() + b" ")
    with pytest.raises(AuthorityVerificationError, match="physical SHA-256"):
        verify_authority(
            tampered,
            repository_root / "terminology_contracts_v1",
            repository_root=repository_root,
        )


def test_superseded_r1_receipt_is_not_active(
    repository_root: Path,
) -> None:
    legacy = (
        repository_root
        / "terminology_contracts_v1"
        / "release"
        / "v1.1.0-final"
        / "history"
        / "contracts_v1_1_0_authority_receipt_r1_resealed.json"
    )
    with pytest.raises(AuthorityVerificationError):
        verify_authority(
            legacy,
            repository_root / "terminology_contracts_v1",
            repository_root=repository_root,
        )


def test_authority_rejects_non_release_contract_drift(
    repository_root: Path, tmp_path: Path
) -> None:
    contracts_root = _copy_contracts(repository_root, tmp_path)
    schema = contracts_root / "schemas" / "v1.1.0" / "common_defs.schema.json"
    schema.write_bytes(schema.read_bytes() + b" ")
    with pytest.raises(AuthorityVerificationError, match="manifest verification"):
        verify_authority(_r2_receipt(contracts_root), contracts_root)


def test_authority_rejects_unreviewed_release_only_drift(
    repository_root: Path, tmp_path: Path
) -> None:
    contracts_root = _copy_contracts(repository_root, tmp_path)
    (contracts_root / "release" / "v1.1.0-final" / "unreviewed.txt").write_text(
        "unreviewed\n", encoding="utf-8"
    )
    with pytest.raises(AuthorityVerificationError, match="file-set mismatch"):
        verify_authority(_r2_receipt(contracts_root), contracts_root)


@pytest.mark.parametrize(
    "relative_path",
    [
        "release/v1.1.0-final/CHECKSUMS.sha256",
        "release/v1.1.0-final/release_manifest.json",
        "release/v1.1.0-final/terminology_contracts_v1_1_0_final.zip",
        "release/v1.1.0-final/final_release_audit.json",
    ],
)
def test_authority_rejects_r2_publication_tamper(
    relative_path: str, repository_root: Path, tmp_path: Path
) -> None:
    contracts_root = _copy_contracts(repository_root, tmp_path)
    artifact = contracts_root / Path(relative_path)
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(AuthorityVerificationError):
        verify_authority(_r2_receipt(contracts_root), contracts_root)


@pytest.mark.parametrize(
    "field,value",
    [("receipt_revision", 1), ("contract_tree_git_oid", "0" * 40)],
)
def test_authority_rejects_wrong_r2_revision_or_tree_binding(
    field: str, value: object, repository_root: Path, tmp_path: Path
) -> None:
    contracts_root = _copy_contracts(repository_root, tmp_path)
    receipt_path = _r2_receipt(contracts_root)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload[field] = value
    receipt_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(AuthorityVerificationError):
        verify_authority(receipt_path, contracts_root)


def _copy_contracts(repository_root: Path, tmp_path: Path) -> Path:
    contracts_root = tmp_path / "terminology_contracts_v1"
    shutil.copytree(repository_root / "terminology_contracts_v1", contracts_root)
    return contracts_root


def _r2_receipt(contracts_root: Path) -> Path:
    return (
        contracts_root
        / "release"
        / "v1.1.0-final"
        / "contracts_v1_1_0_authority_receipt_r2.json"
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
