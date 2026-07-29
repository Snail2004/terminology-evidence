from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from terminology_contracts.calibration import (
    CalibrationVerificationError,
    VerifiedCalibration,
    verify_calibration_artifact,
)
from terminology_contracts.scoring import (
    ScoringError,
    evaluate_calibration_model,
    select_model_features,
)

from ..errors import CalibrationError
from ..jsonio import assert_strict_json_file

EXAMPLE_CALIBRATION_SELF_SHA256 = (
    "e8b3b871dda5a17d2f449ed894b23a4b1d5614180fbc59035f92171560926a76"
)


@dataclass(frozen=True)
class FrozenScore:
    verified: VerifiedCalibration
    decision_features: dict[str, float]
    approval_score: float


def verify_and_score(
    *,
    calibration_path: Path,
    assembled_features: Mapping[str, float],
    schema_dir: Path,
    feature_registry_path: Path,
    expected_gate_policy_version: str,
    expected_gate_policy_artifact_sha256: str,
    expected_calibration_self_sha256: str | None = None,
    allow_example_calibration: bool = False,
) -> FrozenScore:
    try:
        assert_strict_json_file(calibration_path)
        assert_strict_json_file(feature_registry_path)
        verified = verify_calibration_artifact(
            calibration_path,
            schema_dir=schema_dir,
            feature_registry_path=feature_registry_path,
            expected_gate_policy_version=expected_gate_policy_version,
            expected_gate_policy_artifact_sha256=(
                expected_gate_policy_artifact_sha256
            ),
        )
        actual_calibration_hash = verified.artifact.self_sha256
        if allow_example_calibration and (
            actual_calibration_hash != EXAMPLE_CALIBRATION_SELF_SHA256
        ):
            raise CalibrationVerificationError(
                "test-only calibration mode accepts only the exact contract fixture"
            )
        if (
            actual_calibration_hash == EXAMPLE_CALIBRATION_SELF_SHA256
            and not allow_example_calibration
        ):
            raise CalibrationVerificationError(
                "contract example calibration is non-production; enable it only "
                "for explicit fixture tests"
            )
        if not allow_example_calibration and (
            actual_calibration_hash != expected_calibration_self_sha256
        ):
            raise CalibrationVerificationError(
                "calibration self hash differs from the reviewed authority pin"
            )
        decision_features = select_model_features(
            assembled_features, verified.feature_names
        )
        approval_score = evaluate_calibration_model(
            verified.artifact.payload, decision_features
        )
    except (
        CalibrationVerificationError,
        OSError,
        ScoringError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise CalibrationError(str(exc)) from exc
    return FrozenScore(
        verified=verified,
        decision_features=decision_features,
        approval_score=approval_score,
    )
