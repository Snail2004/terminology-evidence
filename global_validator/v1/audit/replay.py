from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import ExecutionMode, RunConfig
from ..errors import DecisionReplayError
from ..jsonio import load_json_object


@dataclass(frozen=True)
class ReplayResult:
    decision_sha256: str
    certificate_sha256: str | None
    matched: bool


def replay_run(run_dir: Path) -> ReplayResult:
    from ..engine import evaluate_global_input

    run_dir = run_dir.resolve()
    spec = _load_json(run_dir / "audit" / "run_spec.json")
    repository_root = Path(spec["repository_root"])
    config = RunConfig(
        repository_root=repository_root,
        authority_receipt_path=run_dir / "input" / "authority_receipt.json",
        gate_action_policy_path=run_dir / "input" / "gate_action_policy.json",
        mode=ExecutionMode(spec["mode"]),
        calibration_path=(
            run_dir / "input" / "calibration_artifact.json"
            if (run_dir / "input" / "calibration_artifact.json").is_file()
            else None
        ),
        collision_index_path=(
            run_dir / "input" / "collision_index.json"
            if (run_dir / "input" / "collision_index.json").is_file()
            else None
        ),
        allow_example_calibration=bool(spec.get("allow_example_calibration", False)),
        expected_calibration_sha256=spec.get("expected_calibration_sha256"),
        global_run_id=spec["global_run_id"],
        started_at=spec["started_at"],
        completed_at=spec["completed_at"],
        certificate_issued_at=spec["certificate_issued_at"],
    )
    replayed = evaluate_global_input(
        run_dir / "input" / "global_validator_input.json", config
    )
    expected_decision = _load_json(
        run_dir / "output" / "global_decision_package.json"
    )["integrity"]["self_sha256"]
    expected_certificate = None
    certificate_path = run_dir / "output" / "terminology_certificate.json"
    if certificate_path.is_file():
        expected_certificate = _load_json(certificate_path)["integrity"]["self_sha256"]
    actual_certificate = (
        None
        if replayed.certificate is None
        else replayed.certificate["integrity"]["self_sha256"]
    )
    actual_decision = replayed.decision["integrity"]["self_sha256"]
    matched = (
        actual_decision == expected_decision
        and actual_certificate == expected_certificate
    )
    if not matched:
        raise DecisionReplayError("replayed semantic output differs from sealed run")
    return ReplayResult(actual_decision, actual_certificate, True)


def _load_json(path: Path) -> dict:
    try:
        return load_json_object(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise DecisionReplayError(f"cannot load replay artifact {path}: {exc}") from exc
