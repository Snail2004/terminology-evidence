from __future__ import annotations

import json

import pytest

from conftest import CALIBRATION, FEATURE_REGISTRY, SCHEMAS, load_v11, validate_payload
from terminology_contracts.calibration import (
    CalibrationVerificationError,
    verify_calibration_artifact,
)
from terminology_contracts.integrity import seal_self_hash


def _write(path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _verify(path, **kwargs):
    return verify_calibration_artifact(
        path,
        schema_dir=SCHEMAS,
        feature_registry_path=FEATURE_REGISTRY,
        **kwargs,
    )


def test_real_fixture_file_is_loaded_and_verified() -> None:
    verified = _verify(CALIBRATION)
    assert verified.threshold == 0.84
    assert verified.artifact.path == CALIBRATION


def test_hash_string_without_loaded_artifact_cannot_open_frozen_mode() -> None:
    decision = load_v11("global_decision_package.json")
    errors = validate_payload(decision, calibration_path=None)
    assert any("requires a loaded calibration artifact" in error for error in errors)


def test_all_zero_dataset_hash_rejects(tmp_path) -> None:
    payload = load_v11("calibration_artifact.json")
    payload["development_dataset_sha256"] = "0" * 64
    path = tmp_path / "calibration.json"
    _write(path, seal_self_hash(payload))
    with pytest.raises(CalibrationVerificationError, match="all-zero"):
        _verify(path)


def test_tampered_canonical_hash_rejects(tmp_path) -> None:
    payload = load_v11("calibration_artifact.json")
    payload["operating_point"]["threshold"] = 0.5
    path = tmp_path / "calibration.json"
    _write(path, payload)
    with pytest.raises(CalibrationVerificationError, match="self_sha256 mismatch"):
        _verify(path)


def test_unknown_feature_rejects(tmp_path) -> None:
    payload = load_v11("calibration_artifact.json")
    payload["model"]["feature_names"].append("UNKNOWN_FEATURE")
    payload["model"]["parameters"]["coefficients"]["UNKNOWN_FEATURE"] = 0.0
    path = tmp_path / "calibration.json"
    _write(path, seal_self_hash(payload))
    with pytest.raises(CalibrationVerificationError, match="unregistered features"):
        _verify(path)


def test_threshold_dataset_and_gate_bindings_reject_drift() -> None:
    with pytest.raises(CalibrationVerificationError, match="decision threshold"):
        _verify(CALIBRATION, expected_threshold=0.5)
    with pytest.raises(CalibrationVerificationError, match="development_dataset_sha256 mismatch"):
        _verify(CALIBRATION, expected_development_dataset_sha256="f" * 64)
    with pytest.raises(CalibrationVerificationError, match="gate_policy_version mismatch"):
        _verify(CALIBRATION, expected_gate_policy_version="other-policy")
