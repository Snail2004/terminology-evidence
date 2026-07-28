from __future__ import annotations

import pytest

from conftest import load_v11, validate_payload
from terminology_contracts.integrity import seal_self_hash


def test_auto_approved_certificate_is_complete() -> None:
    assert validate_payload(load_v11("terminology_certificate.json")) == []


def test_complete_provisional_certificate_requires_calibration_hash() -> None:
    certificate = load_v11("terminology_certificate.json")
    certificate["status"] = "PROVISIONAL"
    certificate["calibration_artifact_sha256"] = None
    errors = validate_payload(seal_self_hash(certificate))
    assert any("complete certificate requires calibration artifact" in error for error in errors)


@pytest.mark.parametrize("status", ["HUMAN_REVIEW", "REJECTED", "SPLIT_REQUIRED"])
def test_nonissuable_status_rejects(status: str) -> None:
    certificate = load_v11("terminology_certificate.json")
    certificate["status"] = status
    assert validate_payload(seal_self_hash(certificate))


def test_missing_decision_binding_rejects() -> None:
    certificate = load_v11("terminology_certificate.json")
    certificate["decision_package_sha256"] = "0" * 64
    errors = validate_payload(seal_self_hash(certificate))
    assert any("decision_package_sha256" in error for error in errors)


def test_evidence_summary_hash_drift_rejects() -> None:
    certificate = load_v11("terminology_certificate.json")
    certificate["evidence_summary"]["context_evidence_sha256"] = "f" * 64
    errors = validate_payload(seal_self_hash(certificate))
    assert any("evidence_summary.context_evidence_sha256 mismatch" in error for error in errors)


def test_effective_sense_binding_drift_rejects() -> None:
    certificate = load_v11("terminology_certificate.json")
    certificate["effective_sense_contract_sha256"] = "f" * 64
    errors = validate_payload(seal_self_hash(certificate))
    assert any("effective sense contract hash mismatch" in error for error in errors)


def test_tac_rejects_legacy_incomplete_certificate() -> None:
    tac = load_v11("tac_occurrence_input.json")
    tac["certificate"]["binding_status"] = "LEGACY_INCOMPLETE"
    tac["certificate"] = seal_self_hash(tac["certificate"])
    errors = validate_payload(seal_self_hash(tac))
    assert any("TAC requires a complete V1.1 certificate" in error for error in errors)
