from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_PYTHON = REPOSITORY_ROOT / "terminology_contracts_v1" / "python"
for path in (REPOSITORY_ROOT, CONTRACTS_PYTHON):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from global_validator.v1.config import ExecutionMode, RunConfig


@pytest.fixture(scope="session")
def repository_root() -> Path:
    return REPOSITORY_ROOT


@pytest.fixture(scope="session")
def authority_receipt() -> Path:
    return Path(
        r"C:\work\terminology-evidence-authority\contracts-v1.1.0\authority_receipt.json"
    )


@pytest.fixture(scope="session")
def valid_input_path(repository_root: Path) -> Path:
    return (
        repository_root
        / "terminology_contracts_v1"
        / "examples"
        / "valid"
        / "v1.1.0"
        / "global_validator_input.json"
    )


@pytest.fixture(scope="session")
def collision_index_path(repository_root: Path) -> Path:
    return (
        repository_root
        / "terminology_contracts_v1"
        / "examples"
        / "support"
        / "v1.1.0"
        / "collision_index.json"
    )


@pytest.fixture(scope="session")
def calibration_path(repository_root: Path) -> Path:
    return (
        repository_root
        / "terminology_contracts_v1"
        / "examples"
        / "valid"
        / "v1.1.0"
        / "calibration_artifact.json"
    )


@pytest.fixture
def config_factory(
    repository_root: Path,
    authority_receipt: Path,
    collision_index_path: Path,
    calibration_path: Path,
) -> Callable[..., RunConfig]:
    def build(
        *,
        mode: ExecutionMode = ExecutionMode.DEVELOPMENT_HEURISTIC,
        output_root: Path | None = None,
        run_id: str = "gv-test-run",
        allow_example_calibration: bool = False,
        **overrides: object,
    ) -> RunConfig:
        values = {
            "repository_root": repository_root,
            "authority_receipt_path": authority_receipt,
            "gate_action_policy_path": (
                repository_root
                / "global_validator"
                / "v1"
                / "policies"
                / "gate_action_selection_v1.0.0.json"
            ),
            "mode": mode,
            "calibration_path": (
                calibration_path
                if mode is ExecutionMode.FROZEN_CALIBRATED
                else None
            ),
            "collision_index_path": collision_index_path,
            "output_root": output_root,
            "allow_example_calibration": allow_example_calibration,
            "global_run_id": run_id,
            "started_at": "2026-07-29T00:00:00+00:00",
            "completed_at": "2026-07-29T00:00:01+00:00",
            "certificate_issued_at": "2026-07-29T00:00:02+00:00",
        }
        values.update(overrides)
        return RunConfig(**values)

    return build
