from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .integrity import (
    IntegrityError,
    VerifiedArtifact,
    load_verified_json_artifact,
    require_nonzero_sha256,
)
from .registries import (
    FEATURE_CONTRACT_VERSION,
    RegistryError,
    known_feature_names,
    load_registry,
)


class CalibrationVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedCalibration:
    artifact: VerifiedArtifact
    threshold: float
    feature_names: tuple[str, ...]
    gate_policy_version: str
    feature_contract_version: str
    development_dataset_sha256: str
    validation_dataset_sha256: str
    numerical_tolerance: float


def verify_calibration_artifact(
    path: Path,
    *,
    schema_dir: Path,
    feature_registry_path: Path,
    expected_self_sha256: str | None = None,
    expected_development_dataset_sha256: str | None = None,
    expected_validation_dataset_sha256: str | None = None,
    expected_gate_policy_version: str | None = None,
    expected_feature_contract_version: str = FEATURE_CONTRACT_VERSION,
    expected_threshold: float | None = None,
) -> VerifiedCalibration:
    try:
        artifact = load_verified_json_artifact(
            path, expected_self_sha256=expected_self_sha256
        )
        payload = artifact.payload
        require_nonzero_sha256(
            payload.get("development_dataset_sha256"),
            field="development_dataset_sha256",
        )
        require_nonzero_sha256(
            payload.get("validation_dataset_sha256"),
            field="validation_dataset_sha256",
        )
    except IntegrityError as exc:
        raise CalibrationVerificationError(str(exc)) from exc

    # Imported lazily to keep the schema loader independent from calibration.
    from .validation import schema_validate_instance

    schema_errors = schema_validate_instance(payload, schema_dir)
    if schema_errors:
        raise CalibrationVerificationError(
            "calibration schema validation failed: " + "; ".join(schema_errors)
        )
    if payload.get("verification_status") != "SEALED":
        raise CalibrationVerificationError(
            "frozen mode requires verification_status=SEALED"
        )

    feature_version = payload.get("feature_contract_version")
    if feature_version != expected_feature_contract_version:
        raise CalibrationVerificationError(
            "feature_contract_version mismatch: "
            f"expected {expected_feature_contract_version!r}, got {feature_version!r}"
        )
    try:
        registry = load_registry(feature_registry_path)
        if registry.get("registry_version") != feature_version:
            raise CalibrationVerificationError(
                "feature registry version does not match calibration artifact"
            )
        known = known_feature_names(registry)
    except RegistryError as exc:
        raise CalibrationVerificationError(str(exc)) from exc

    model = payload.get("model")
    if not isinstance(model, Mapping):
        raise CalibrationVerificationError("model must be an object")
    raw_names = model.get("feature_names")
    if not isinstance(raw_names, list) or not raw_names:
        raise CalibrationVerificationError("model.feature_names must not be empty")
    if not all(isinstance(name, str) and name for name in raw_names):
        raise CalibrationVerificationError("model.feature_names contains invalid name")
    if len(raw_names) != len(set(raw_names)):
        raise CalibrationVerificationError("model.feature_names contains duplicates")
    unknown = sorted(set(raw_names).difference(known))
    if unknown:
        raise CalibrationVerificationError(
            "calibration references unregistered features: " + ", ".join(unknown)
        )
    _verify_model_parameters(model)

    numerical_tolerance = _finite_number(
        payload.get("numerical_tolerance"), field="numerical_tolerance"
    )
    if not 0.0 <= numerical_tolerance <= 1e-9:
        raise CalibrationVerificationError(
            "numerical_tolerance must be in [0, 1e-9]"
        )

    gate_policy = payload.get("gate_policy_version")
    if expected_gate_policy_version is not None and gate_policy != expected_gate_policy_version:
        raise CalibrationVerificationError(
            "gate_policy_version mismatch: "
            f"expected {expected_gate_policy_version!r}, got {gate_policy!r}"
        )
    _expect_hash(
        payload,
        "development_dataset_sha256",
        expected_development_dataset_sha256,
    )
    _expect_hash(
        payload,
        "validation_dataset_sha256",
        expected_validation_dataset_sha256,
    )

    operating_point = payload.get("operating_point")
    if not isinstance(operating_point, Mapping):
        raise CalibrationVerificationError("operating_point must be an object")
    threshold = _finite_number(
        operating_point.get("threshold"), field="operating_point.threshold"
    )
    if not 0.0 <= threshold <= 1.0:
        raise CalibrationVerificationError("operating_point.threshold must be in [0,1]")
    if expected_threshold is not None and not math.isclose(
        threshold, expected_threshold, rel_tol=0.0, abs_tol=1e-12
    ):
        raise CalibrationVerificationError(
            f"decision threshold {expected_threshold!r} differs from verified "
            f"artifact threshold {threshold!r}"
        )

    target = payload.get("metric_target")
    results = payload.get("calibration_results")
    if not isinstance(target, Mapping) or not isinstance(results, Mapping):
        raise CalibrationVerificationError(
            "metric_target and calibration_results must be objects"
        )
    for field in ("auto_approval_precision_target", "confidence_level"):
        _finite_number(target.get(field), field=f"metric_target.{field}")
    for field in (
        "observed_precision",
        "coverage",
        "precision_lower_bound",
    ):
        _finite_number(operating_point.get(field), field=f"operating_point.{field}")
    if operating_point.get("operating_point_id") != results.get(
        "selected_operating_point_id"
    ):
        raise CalibrationVerificationError(
            "selected operating point does not match operating_point_id"
        )
    for field in ("development_sample_count", "validation_sample_count"):
        value = results.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise CalibrationVerificationError(
                f"calibration_results.{field} must be a positive integer"
            )
    if results.get("uncertainty_method") not in {
        "WILSON_SCORE",
        "CLOPPER_PEARSON",
        "BOOTSTRAP_PERCENTILE",
    }:
        raise CalibrationVerificationError(
            "calibration_results.uncertainty_method is unsupported"
        )
    if operating_point["precision_lower_bound"] < target[
        "auto_approval_precision_target"
    ]:
        raise CalibrationVerificationError(
            "precision lower bound does not meet auto-approval target"
        )

    return VerifiedCalibration(
        artifact=artifact,
        threshold=threshold,
        feature_names=tuple(raw_names),
        gate_policy_version=str(gate_policy),
        feature_contract_version=str(feature_version),
        development_dataset_sha256=str(payload["development_dataset_sha256"]),
        validation_dataset_sha256=str(payload["validation_dataset_sha256"]),
        numerical_tolerance=numerical_tolerance,
    )


def _verify_model_parameters(model: Mapping[str, Any]) -> None:
    model_type = model.get("model_type")
    parameters = model.get("parameters")
    feature_names = tuple(model.get("feature_names", ()))
    if not isinstance(parameters, Mapping):
        raise CalibrationVerificationError("model.parameters must be an object")
    if model_type == "LOGISTIC_REGRESSION":
        if parameters.get("link_function") != "LOGIT":
            raise CalibrationVerificationError(
                "LOGISTIC_REGRESSION requires link_function=LOGIT"
            )
        _finite_number(parameters.get("intercept"), field="model.parameters.intercept")
        coefficients = parameters.get("coefficients")
        if not isinstance(coefficients, Mapping):
            raise CalibrationVerificationError(
                "logistic regression requires a coefficients object"
            )
        if set(coefficients) != set(feature_names):
            raise CalibrationVerificationError(
                "logistic regression coefficients must exactly cover feature_names"
            )
        for name, value in coefficients.items():
            _finite_number(value, field=f"model.parameters.coefficients.{name}")
    else:
        raise CalibrationVerificationError(
            "V1.1 frozen calibration supports only LOGISTIC_REGRESSION; "
            f"got {model_type!r}"
        )


def _finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationVerificationError(f"{field}: finite number required")
    result = float(value)
    if not math.isfinite(result):
        raise CalibrationVerificationError(f"{field}: finite number required")
    return result


def _expect_hash(
    payload: Mapping[str, Any], field: str, expected: str | None
) -> None:
    if expected is not None and payload.get(field) != expected:
        raise CalibrationVerificationError(
            f"{field} mismatch: expected {expected!r}, got {payload.get(field)!r}"
        )
