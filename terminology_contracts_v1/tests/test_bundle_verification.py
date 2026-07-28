from __future__ import annotations

import json

from conftest import FEATURE_REGISTRY, SCHEMAS, VALID_V11, load_v11, validate_payload
from terminology_contracts.integrity import seal_self_hash
from terminology_contracts.validation import verify_certificate_bundle


def _verify(*, certificate_path=None, tac_path=None):
    return verify_certificate_bundle(
        certificate_path=certificate_path
        or VALID_V11 / "terminology_certificate.json",
        frozen_candidate_path=VALID_V11 / "frozen_candidate_contract.json",
        effective_sense_contract_path=VALID_V11 / "effective_sense_contract.json",
        constraint_evidence_path=VALID_V11 / "constraint_evidence_package.json",
        global_input_path=VALID_V11 / "global_validator_input.json",
        context_evidence_path=VALID_V11 / "context_evidence_package.json",
        attestation_evidence_path=VALID_V11 / "attestation_evidence_package.json",
        gate_result_path=VALID_V11 / "gate_result_set.json",
        decision_path=VALID_V11 / "global_decision_package.json",
        calibration_path=VALID_V11 / "calibration_artifact.json",
        schema_dir=SCHEMAS,
        feature_registry_path=FEATURE_REGISTRY,
        tac_path=tac_path,
    )


def test_valid_certificate_and_tac_bundle_pass() -> None:
    assert _verify(tac_path=VALID_V11 / "tac_occurrence_input.json") == []


def test_certificate_random_artifact_hash_rejects(tmp_path) -> None:
    certificate = load_v11("terminology_certificate.json")
    certificate["decision_package_sha256"] = "f" * 64
    path = tmp_path / "certificate.json"
    path.write_text(
        json.dumps(seal_self_hash(certificate), sort_keys=True), encoding="utf-8"
    )
    errors = _verify(certificate_path=path)
    assert any("decision" in error and "self hash mismatch" in error for error in errors)


def test_tac_span_outside_source_text_rejects() -> None:
    tac = load_v11("tac_occurrence_input.json")
    tac["source_term_span"]["end"] = len(tac["source_text"]) + 1
    errors = validate_payload(seal_self_hash(tac))
    assert any("exceeds source_text bounds" in error for error in errors)


def test_tac_span_must_select_certificate_source_term() -> None:
    tac = load_v11("tac_occurrence_input.json")
    tac["source_term_span"] = {"start": 0, "end": 6}
    errors = validate_payload(seal_self_hash(tac))
    assert any("does not match certificate source_term" in error for error in errors)


def test_tac_rejects_certificate_for_another_source_term() -> None:
    tac = load_v11("tac_occurrence_input.json")
    tac["certificate"]["candidate_key"]["source_term"] = "training"
    tac["certificate"] = seal_self_hash(tac["certificate"])
    errors = validate_payload(seal_self_hash(tac))
    assert any("does not match certificate source_term" in error for error in errors)
