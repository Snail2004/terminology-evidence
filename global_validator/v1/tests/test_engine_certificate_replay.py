from __future__ import annotations

from pathlib import Path
import copy
import json

import pytest
from terminology_contracts.integrity import seal_self_hash

from global_validator.v1.audit import replay_run
from global_validator.v1.certificates import verify_persisted_certificate_bundle
from global_validator.v1.config import ExecutionMode, validate_run_config
from global_validator.v1.decision import verify_decision_artifact
from global_validator.v1.engine import run_global_validator
from global_validator.v1.errors import (
    CalibrationError,
    CertificateBindingError,
    StorageError,
)
from global_validator.v1.input import assemble_global_input

from .helpers import load_base_input


def test_development_run_is_provisional_certificate_free_and_replayable(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(output_root=tmp_path, run_id="development-run")
    result = run_global_validator(valid_input_path, config)

    assert result.decision["decision"] == "PROVISIONAL"
    assert result.decision["approval_score"] is None
    assert result.decision["decision_features"] == {}
    assert result.decision["certificate_ref"] is None
    assert result.certificate is None
    assert not (result.run_dir / "output" / "terminology_certificate.json").exists()
    assert replay_run(result.run_dir).matched is True
    assert (
        result.run_dir / "audit" / "authority_verification.json"
    ).read_text(encoding="utf-8").find("PINNED_PHYSICAL_FALLBACK") >= 0

    with pytest.raises(StorageError, match="already exists"):
        run_global_validator(valid_input_path, config)


def test_contract_example_calibration_requires_explicit_test_mode(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path,
        run_id="blocked-example-calibration",
    )
    with pytest.raises(CalibrationError, match="non-production"):
        run_global_validator(valid_input_path, config)


def test_frozen_production_requires_reviewed_calibration_pin(
    tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        calibration_path=tmp_path / "reviewed-calibration.json",
    )
    with pytest.raises(CalibrationError, match="expected_calibration_sha256"):
        validate_run_config(config)


def test_copied_example_calibration_remains_non_production(
    valid_input_path: Path,
    calibration_path: Path,
    tmp_path: Path,
    config_factory,
) -> None:
    copied = tmp_path / "copied-calibration.json"
    copied.write_bytes(calibration_path.read_bytes())
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path / "runs",
        run_id="copied-example-calibration",
        calibration_path=copied,
        expected_calibration_sha256=(
            "e8b3b871dda5a17d2f449ed894b23a4b1d5614180fbc59035f92171560926a76"
        ),
    )
    with pytest.raises(CalibrationError, match="non-production"):
        run_global_validator(valid_input_path, config)


def test_calibration_byte_tamper_fails_before_scoring(
    valid_input_path: Path,
    calibration_path: Path,
    tmp_path: Path,
    config_factory,
) -> None:
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    payload["model"]["parameters"]["coefficients"]["C_mean"] = 9.0
    tampered = tmp_path / "tampered-calibration.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path / "runs",
        run_id="tampered-calibration",
        calibration_path=tampered,
        allow_example_calibration=True,
    )
    with pytest.raises(CalibrationError, match="self_sha256 mismatch"):
        run_global_validator(valid_input_path, config)


def test_fixture_mode_rejects_resealed_nonfixture_calibration(
    valid_input_path: Path,
    calibration_path: Path,
    tmp_path: Path,
    config_factory,
) -> None:
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    payload["created_at"] = "2026-07-29T00:00:00+00:00"
    altered = tmp_path / "altered-calibration.json"
    altered.write_text(
        json.dumps(seal_self_hash(payload), ensure_ascii=False), encoding="utf-8"
    )
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path / "runs",
        run_id="altered-fixture",
        calibration_path=altered,
        allow_example_calibration=True,
    )
    with pytest.raises(CalibrationError, match="exact contract fixture"):
        run_global_validator(valid_input_path, config)


def test_frozen_fixture_score_certificate_bundle_and_replay(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path,
        run_id="frozen-fixture-run",
        allow_example_calibration=True,
    )
    result = run_global_validator(valid_input_path, config)

    assert result.decision["decision"] == "AUTO_APPROVED"
    assert result.decision["approval_score"] == pytest.approx(
        0.880481737215655, abs=1e-15
    )
    assert result.certificate is not None
    certificate = result.certificate
    frozen = result.global_input["frozen_candidate_contract"]
    assert certificate["allowed_variants"] == frozen["surfaces"][
        "validated_variants_vi"
    ]
    assert certificate["forbidden_candidates"] == frozen["surfaces"][
        "rejected_variants_vi"
    ]
    assert certificate["validity_context_refs"] == result.global_input[
        "context_evidence"
    ]["support_set"]["positive_support_refs"]
    assert certificate["attestation_evidence_refs"] == result.global_input[
        "attestation_evidence"
    ]["accepted_evidence_refs"]

    report = verify_persisted_certificate_bundle(
        result.run_dir,
        schema_dir=config.schema_dir,
        feature_registry_path=config.feature_registry_path,
    )
    assert report["status"] == "PASS"
    assert replay_run(result.run_dir).matched is True
    verified_decision = verify_decision_artifact(
        result.run_dir / "output" / "global_decision_package.json",
        global_input_path=result.run_dir / "input" / "global_validator_input.json",
        config=config,
    )
    assert verified_decision["integrity"]["self_sha256"] == result.decision[
        "integrity"
    ]["self_sha256"]


def test_frozen_cap_provisional_still_emits_scope_limited_certificate(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    base = load_base_input(valid_input_path)
    context = copy.deepcopy(base["context_evidence"])
    context["contrastive_status"] = "ABSENT"
    context["support_set"]["contrastive_refs"] = []
    context["flags"] = [
        {
            "code": "missing_contrastive_context",
            "severity": "WARNING",
            "message": "Synthetic contract test.",
            "evidence_refs": [],
        }
    ]
    signal = next(
        item
        for item in context["gate_signals"]
        if item["gate_id"] == "missing_contrastive_context"
    )
    signal.update(
        {
            "asserted": True,
            "reason_codes": ["MISSING_CONTRASTIVE_CONTEXT"],
            "evidence_refs": [],
        }
    )
    context = seal_self_hash(context)
    payload = assemble_global_input(
        effective_sense_contract=base["effective_sense_contract"],
        frozen_candidate_contract=base["frozen_candidate_contract"],
        constraint_evidence=base["constraint_evidence"],
        context_evidence=context,
        attestation_evidence=base["attestation_evidence"],
        assembled_at="2026-07-29T00:00:00+00:00",
        schema_dir=config_factory().schema_dir,
        gate_policy_path=config_factory().gate_policy_path,
        feature_registry_path=config_factory().feature_registry_path,
    )
    input_path = tmp_path / "provisional-input.json"
    input_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path / "runs",
        run_id="frozen-provisional",
        allow_example_calibration=True,
    )
    result = run_global_validator(input_path, config)
    assert result.decision["decision"] == "PROVISIONAL"
    assert result.certificate is not None
    assert result.certificate["status"] == "PROVISIONAL"
    assert result.certificate["gate_summary"] == ["missing_contrastive_context"]


def test_bundle_tamper_is_rejected(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path,
        run_id="tamper-run",
        allow_example_calibration=True,
    )
    result = run_global_validator(valid_input_path, config)
    decision_path = result.run_dir / "output" / "global_decision_package.json"
    decision_path.write_bytes(decision_path.read_bytes() + b"\n")
    with pytest.raises(CertificateBindingError, match="checksum mismatch"):
        verify_persisted_certificate_bundle(
            result.run_dir,
            schema_dir=config.schema_dir,
            feature_registry_path=config.feature_registry_path,
        )
