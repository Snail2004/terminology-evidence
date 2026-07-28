from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audit.storage import persist_run_bundle
from .authority import VerifiedAuthority, verify_authority
from .calibration import FrozenScore, verify_and_score
from .certificates import build_certificate
from .config import ExecutionMode, RunConfig, validate_run_config
from .decision import build_decision_package, resolve_decision
from .features import assemble_registered_features
from .gates import build_gate_result_set, load_gate_action_policy
from .input import load_and_validate_global_input, verify_collision_index_binding


@dataclass(frozen=True)
class RunResult:
    authority: VerifiedAuthority
    global_input: dict[str, Any]
    gate_results: dict[str, Any]
    assembled_features: dict[str, float]
    decision: dict[str, Any]
    certificate: dict[str, Any] | None
    run_dir: Path | None


def evaluate_global_input(input_path: Path, config: RunConfig) -> RunResult:
    validate_run_config(config)
    authority = verify_authority(
        config.authority_receipt_path,
        config.contracts_root,
        repository_root=config.repository_root,
    )
    global_input = load_and_validate_global_input(
        input_path,
        schema_dir=authority.schema_dir,
        gate_policy_path=authority.gate_policy_path,
        feature_registry_path=authority.feature_registry_path,
    )
    verify_collision_index_binding(global_input, config.collision_index_path)
    action_policy = load_gate_action_policy(
        config.gate_action_policy_path,
        gate_policy_path=authority.gate_policy_path,
        schema_dir=authority.schema_dir,
    )
    gates = build_gate_result_set(
        global_input,
        action_policy=action_policy,
        gate_policy_path=authority.gate_policy_path,
        schema_dir=authority.schema_dir,
    )
    assembled_features, _ = assemble_registered_features(
        global_input, authority.feature_registry_path
    )

    frozen_score: FrozenScore | None = None
    if config.mode is ExecutionMode.FROZEN_CALIBRATED:
        frozen_score = verify_and_score(
            calibration_path=config.calibration_path,
            assembled_features=assembled_features,
            schema_dir=authority.schema_dir,
            feature_registry_path=authority.feature_registry_path,
            expected_gate_policy_version="1.0.0",
            expected_gate_policy_artifact_sha256=(
                action_policy.gate_policy_artifact_sha256
            ),
            expected_calibration_self_sha256=(
                config.expected_calibration_sha256
            ),
            allow_example_calibration=config.allow_example_calibration,
        )
    resolution = resolve_decision(
        gates["observations"],
        mode=config.mode,
        approval_score=(None if frozen_score is None else frozen_score.approval_score),
        threshold=(None if frozen_score is None else frozen_score.verified.threshold),
    )
    decision = build_decision_package(
        global_input=global_input,
        gate_results=gates,
        assembled_features=assembled_features,
        resolution=resolution,
        config=config,
        action_policy=action_policy,
        frozen_score=frozen_score,
        global_input_path=input_path,
    )
    certificate = build_certificate(
        global_input=global_input,
        gate_results=gates,
        decision=decision,
        config=config,
        frozen_score=frozen_score,
    )
    return RunResult(
        authority=authority,
        global_input=global_input,
        gate_results=gates,
        assembled_features=assembled_features,
        decision=decision,
        certificate=certificate,
        run_dir=None,
    )


def run_global_validator(input_path: Path, config: RunConfig) -> RunResult:
    evaluated = evaluate_global_input(input_path, config)
    action_policy = load_gate_action_policy(
        config.gate_action_policy_path,
        gate_policy_path=evaluated.authority.gate_policy_path,
        schema_dir=evaluated.authority.schema_dir,
    )
    run_dir = None
    if config.output_root is not None:
        run_dir = persist_run_bundle(
            config=config,
            authority_integrity_mode=(
                evaluated.authority.receipt_integrity_mode
            ),
            authority_warnings=evaluated.authority.warnings,
            global_input=evaluated.global_input,
            gate_results=evaluated.gate_results,
            assembled_features=evaluated.assembled_features,
            decision=evaluated.decision,
            certificate=evaluated.certificate,
            action_policy=action_policy,
        )
    elif evaluated.certificate is not None:
        from .errors import CertificateBindingError

        raise CertificateBindingError(
            "frozen certificate must be persisted and bundle-verified"
        )
    return RunResult(
        authority=evaluated.authority,
        global_input=evaluated.global_input,
        gate_results=evaluated.gate_results,
        assembled_features=evaluated.assembled_features,
        decision=evaluated.decision,
        certificate=evaluated.certificate,
        run_dir=run_dir,
    )
