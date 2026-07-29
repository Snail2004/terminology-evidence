from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from authority_fixtures import (  # noqa: F401
    authority_candidate,
    candidate_copy,
    candidate_payload,
    repository_root,
)
from authority_common import (
    AUTHORITY_COMMIT,
    AUTHORITY_TAG,
    AuthorityError,
    calculate_self_sha256,
    seal_self_hash,
    sha256_file,
    write_checksum,
    write_json,
)
from authority_verifier import verify_authority_receipt


def _verify(candidate: dict[str, Path]):
    return verify_authority_receipt(
        repo_root=candidate["repo"],
        distribution_root=candidate["distribution"],
        receipt_path=candidate["receipt"],
    )


def _write_receipt(path: Path, payload: dict, *, reseal: bool = True) -> None:
    if reseal:
        payload = seal_self_hash(payload)
    write_json(path, payload)
    write_checksum(path.with_name(path.name + ".sha256"), path)


def test_canonical_receipt_copy_verifies(candidate_copy) -> None:
    report = _verify(candidate_copy)
    assert report["result"] == "PASS"
    assert report["warnings"] == []
    assert report["authority_tag"] == AUTHORITY_TAG
    assert report["authority_commit"] == AUTHORITY_COMMIT


def test_historical_receipts_are_preserved_and_superseded(candidate_copy) -> None:
    report = _verify(candidate_copy)
    modes = {row["integrity_mode"] for row in report["historical_receipts"]}
    assert modes == {"CANONICAL_SELF_HASH", "HISTORICAL_INVALID_SELF_HASH"}
    assert all(
        row["status"] == "SUPERSEDED_BY_RECEIPT_R2"
        for row in report["historical_receipts"]
    )


def test_wrong_declared_self_hash_rejects(candidate_copy, candidate_payload) -> None:
    candidate_payload["issued_at"] = "2026-07-29T00:00:01Z"
    _write_receipt(candidate_copy["receipt"], candidate_payload, reseal=False)
    with pytest.raises(AuthorityError, match="self_sha256 mismatch"):
        _verify(candidate_copy)


def test_duplicate_key_rejects(candidate_copy) -> None:
    path = candidate_copy["receipt"]
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '{\n  "authority_commit"',
        '{\n  "schema_id": "TerminologyContractsAuthorityReceiptV1",\n  "authority_commit"',
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")
    write_checksum(path.with_name(path.name + ".sha256"), path)
    with pytest.raises(AuthorityError, match="duplicate JSON key: schema_id"):
        _verify(candidate_copy)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_number_rejects(candidate_copy, constant: str) -> None:
    path = candidate_copy["receipt"]
    text = path.read_text(encoding="utf-8")
    text = text.replace("{\n", f'{{\n  "nonfinite": {constant},\n', 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    write_checksum(path.with_name(path.name + ".sha256"), path)
    with pytest.raises(AuthorityError, match="non-finite JSON number"):
        _verify(candidate_copy)


def test_trailing_content_rejects(candidate_copy) -> None:
    path = candidate_copy["receipt"]
    path.write_text(
        path.read_text(encoding="utf-8") + "trailing\n",
        encoding="utf-8",
        newline="\n",
    )
    write_checksum(path.with_name(path.name + ".sha256"), path)
    with pytest.raises(AuthorityError, match="invalid strict JSON"):
        _verify(candidate_copy)


def test_authority_tag_drift_rejects(candidate_copy, candidate_payload) -> None:
    candidate_payload["authority_tag"] = "contracts-v1.1.0-moved"
    _write_receipt(candidate_copy["receipt"], candidate_payload)
    with pytest.raises(AuthorityError, match="authority_tag mismatch"):
        _verify(candidate_copy)


def test_authority_commit_drift_rejects(candidate_copy, candidate_payload) -> None:
    candidate_payload["authority_commit"] = "f" * 40
    _write_receipt(candidate_copy["receipt"], candidate_payload)
    with pytest.raises(AuthorityError, match="authority_commit mismatch"):
        _verify(candidate_copy)


def test_manifest_self_hash_drift_rejects(candidate_copy, candidate_payload) -> None:
    candidate_payload["manifest_sha256"] = "f" * 64
    _write_receipt(candidate_copy["receipt"], candidate_payload)
    with pytest.raises(AuthorityError, match="manifest_sha256 mismatch"):
        _verify(candidate_copy)


def test_manifest_physical_hash_drift_rejects(candidate_copy, candidate_payload) -> None:
    candidate_payload["manifest_file_sha256"] = "f" * 64
    _write_receipt(candidate_copy["receipt"], candidate_payload)
    with pytest.raises(AuthorityError, match="manifest physical binding mismatch"):
        _verify(candidate_copy)


def test_release_zip_byte_drift_rejects(candidate_copy, candidate_payload) -> None:
    zip_path = (
        candidate_copy["distribution"]
        / "terminology_contracts_v1"
        / candidate_payload["final_release_path"]
    )
    data = bytearray(zip_path.read_bytes())
    data[len(data) // 2] ^= 0x01
    zip_path.write_bytes(data)
    with pytest.raises(AuthorityError, match="ZIP SHA-256 mismatch|CRC verification failed"):
        _verify(candidate_copy)


def test_gate_policy_self_hash_drift_rejects(candidate_copy, candidate_payload) -> None:
    candidate_payload["gate_policy_self_sha256"] = "f" * 64
    _write_receipt(candidate_copy["receipt"], candidate_payload)
    with pytest.raises(AuthorityError, match="gate_policy_self_sha256 mismatch"):
        _verify(candidate_copy)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("feature_registry_version", "1.1.1", "feature_registry_version mismatch"),
        ("feature_registry_file_sha256", "f" * 64, "feature registry physical binding mismatch"),
        ("feature_registry_canonical_sha256", "f" * 64, "feature registry canonical binding mismatch"),
    ],
)
def test_feature_registry_drift_rejects(
    candidate_copy, candidate_payload, field: str, value: str, message: str
) -> None:
    candidate_payload[field] = value
    _write_receipt(candidate_copy["receipt"], candidate_payload)
    with pytest.raises(AuthorityError, match=message):
        _verify(candidate_copy)


def test_absolute_release_path_rejects(candidate_copy, candidate_payload) -> None:
    candidate_payload["final_release_path"] = "C:/authority/final.zip"
    _write_receipt(candidate_copy["receipt"], candidate_payload)
    with pytest.raises(AuthorityError, match="final_release_path"):
        _verify(candidate_copy)


def test_unexpected_receipt_field_rejects(candidate_copy, candidate_payload) -> None:
    candidate_payload["silent_extension"] = True
    _write_receipt(candidate_copy["receipt"], candidate_payload)
    with pytest.raises(AuthorityError, match="unexpected field drift"):
        _verify(candidate_copy)


def test_stale_rc1_active_path_rejects(candidate_copy) -> None:
    contract = candidate_copy["distribution"] / "terminology_contracts_v1"
    stale = contract / "release" / "terminology_contracts_v1_1.zip"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"stale RC1")
    with pytest.raises(AuthorityError, match="stale RC1 active release paths remain"):
        _verify(candidate_copy)


def test_release_audit_tamper_rejects(candidate_copy, candidate_payload) -> None:
    audit = (
        candidate_copy["distribution"]
        / "terminology_contracts_v1"
        / candidate_payload["final_release_audit_path"]
    )
    payload = json.loads(audit.read_text(encoding="utf-8"))
    payload["test_count"] = 0
    write_json(audit, seal_self_hash(payload))
    with pytest.raises(AuthorityError, match="audit (self-hash|physical hash) mismatch"):
        _verify(candidate_copy)


def test_receipt_physical_checksum_rejects_reserialization(candidate_copy) -> None:
    path = candidate_copy["receipt"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(AuthorityError, match="physical SHA-256 mismatch"):
        _verify(candidate_copy)


def test_receipt_canonical_hash_is_recomputable(candidate_copy) -> None:
    payload = json.loads(candidate_copy["receipt"].read_text(encoding="utf-8"))
    assert payload["integrity"]["self_sha256"] == calculate_self_sha256(payload)
    assert sha256_file(candidate_copy["receipt"]) != payload["integrity"]["self_sha256"]
