from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
import re

from .errors import CalibrationError, InputValidationError

ENGINE_VERSION = "global-validator-v1.1.0"
GLOBAL_RUN_SPEC_ID = "global-validator-run-spec-v1.1.0"


class ExecutionMode(str, Enum):
    DEVELOPMENT_HEURISTIC = "DEVELOPMENT_HEURISTIC"
    FROZEN_CALIBRATED = "FROZEN_CALIBRATED"


@dataclass(frozen=True)
class RunConfig:
    repository_root: Path
    authority_receipt_path: Path
    gate_action_policy_path: Path
    mode: ExecutionMode = ExecutionMode.DEVELOPMENT_HEURISTIC
    calibration_path: Path | None = None
    expected_calibration_sha256: str | None = None
    collision_index_path: Path | None = None
    output_root: Path | None = None
    allow_example_calibration: bool = False
    global_run_id: str = "global-validator-run"
    started_at: str = "1970-01-01T00:00:00+00:00"
    completed_at: str = "1970-01-01T00:00:00+00:00"
    certificate_issued_at: str = "1970-01-01T00:00:00+00:00"

    @property
    def contracts_root(self) -> Path:
        return self.repository_root / "terminology_contracts_v1"

    @property
    def schema_dir(self) -> Path:
        return self.contracts_root / "schemas" / "v1.1.0"

    @property
    def gate_policy_path(self) -> Path:
        return self.contracts_root / "policies" / "gate_policy_v1.0.0.json"

    @property
    def feature_registry_path(self) -> Path:
        return (
            self.contracts_root
            / "registries"
            / "feature_contract_v1.1.0.json"
        )


_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,220}$")


def validate_run_config(config: RunConfig) -> None:
    if not _SAFE_RUN_ID.fullmatch(config.global_run_id):
        raise InputValidationError("global_run_id is not a safe identifier")
    started = _parse_aware_datetime(config.started_at, "started_at")
    completed = _parse_aware_datetime(config.completed_at, "completed_at")
    issued = _parse_aware_datetime(
        config.certificate_issued_at, "certificate_issued_at"
    )
    if started > completed:
        raise InputValidationError("started_at must not follow completed_at")
    if issued < completed:
        raise InputValidationError(
            "certificate_issued_at must not precede completed_at"
        )
    if config.mode is ExecutionMode.DEVELOPMENT_HEURISTIC:
        if config.calibration_path is not None:
            raise CalibrationError(
                "development mode cannot load or use calibration"
            )
        if config.allow_example_calibration:
            raise CalibrationError(
                "allow_example_calibration is valid only in frozen test runs"
            )
        if config.expected_calibration_sha256 is not None:
            raise CalibrationError(
                "development mode cannot bind a calibration authority hash"
            )
        return
    if config.calibration_path is None:
        raise CalibrationError("frozen mode requires calibration_path")
    if _is_under(config.calibration_path, config.contracts_root / "examples"):
        if not config.allow_example_calibration:
            raise CalibrationError(
                "example calibration is non-production; explicitly enable it "
                "only for contract tests"
            )
    if config.allow_example_calibration:
        if config.expected_calibration_sha256 is not None:
            raise CalibrationError(
                "fixture mode cannot also claim a production calibration hash"
            )
    elif not _is_sha256(config.expected_calibration_sha256):
        raise CalibrationError(
            "frozen production mode requires expected_calibration_sha256"
        )


def _parse_aware_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise InputValidationError(f"{field} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None:
        raise InputValidationError(f"{field} must include a timezone")
    return parsed


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _is_sha256(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value != "0" * 64
        and value == value.casefold()
        and all(character in "0123456789abcdef" for character in value)
    )
