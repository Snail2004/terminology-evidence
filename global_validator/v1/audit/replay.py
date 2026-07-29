from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import sha256_file, verify_self_hash

from ..authority import verify_authority
from ..certificates import verify_persisted_certificate_bundle
from ..config import ExecutionMode, RunConfig, validate_run_config
from ..decision import verify_decision_artifact
from ..errors import DecisionReplayError, GlobalValidatorError
from ..gates import load_gate_action_policy, verify_gate_result_artifact
from ..input import load_and_validate_global_input, verify_collision_index_binding
from ..jsonio import load_json_object
from .bundle_verifier import verify_persisted_run_bundle_integrity


@dataclass(frozen=True)
class ReplayResult:
    decision_sha256: str
    certificate_sha256: str | None
    matched: bool


def replay_run(run_dir: Path) -> ReplayResult:
    from ..engine import evaluate_global_input

    run_dir = run_dir.resolve()
    try:
        verify_persisted_run_bundle_integrity(run_dir)
        spec = _load_json(run_dir / "audit" / "run_spec.json")
        _validate_run_spec(spec)
        config = _config_from_spec(run_dir, spec)
        validate_run_config(config)

        authority = verify_authority(
            config.authority_receipt_path,
            config.contracts_root,
            repository_root=config.repository_root,
        )
        action_policy = load_gate_action_policy(
            config.gate_action_policy_path,
            gate_policy_path=authority.gate_policy_path,
            schema_dir=authority.schema_dir,
        )
        if action_policy.self_sha256 != spec["gate_action_policy_sha256"]:
            raise DecisionReplayError(
                "run spec gate_action_policy_sha256 differs from persisted policy"
            )
        _verify_authority_copies(run_dir, authority)

        global_input_path = run_dir / "input" / "global_validator_input.json"
        global_input = load_and_validate_global_input(
            global_input_path,
            schema_dir=authority.schema_dir,
            gate_policy_path=authority.gate_policy_path,
            feature_registry_path=authority.feature_registry_path,
        )
        verify_collision_index_binding(global_input, config.collision_index_path)
        _verify_input_projections(run_dir, global_input)

        stored_gate = verify_gate_result_artifact(
            run_dir / "output" / "gate_result_set.json",
            global_input=global_input,
            gate_policy_path=authority.gate_policy_path,
            schema_dir=authority.schema_dir,
        )
        decision_path = run_dir / "output" / "global_decision_package.json"
        stored_decision = verify_decision_artifact(
            decision_path,
            global_input_path=global_input_path,
            config=config,
            verify_run_config_binding=True,
        )
        if stored_decision.get("gate_results") != stored_gate:
            raise DecisionReplayError(
                "persisted gate result differs from decision gate_results"
            )
        _verify_audit_bindings(
            run_dir,
            spec=spec,
            authority_mode=authority.receipt_integrity_mode,
            authority_warnings=authority.warnings,
            decision=stored_decision,
        )

        stored_certificate = None
        certificate_path = run_dir / "output" / "terminology_certificate.json"
        if certificate_path.is_file():
            verify_persisted_certificate_bundle(
                run_dir,
                schema_dir=authority.schema_dir,
                feature_registry_path=authority.feature_registry_path,
            )
            stored_certificate = _load_verified_json(certificate_path)
            certificate_report = _load_json(
                run_dir / "audit" / "certificate_bundle.json"
            )
            if certificate_report != {"status": "PASS", "errors": []}:
                raise DecisionReplayError(
                    "persisted certificate bundle report is not PASS"
                )

        replayed = evaluate_global_input(global_input_path, config)
    except DecisionReplayError:
        raise
    except (GlobalValidatorError, OSError, UnicodeError, ValueError) as exc:
        raise DecisionReplayError(f"persisted run verification failed: {exc}") from exc

    if replayed.gate_results != stored_gate:
        raise DecisionReplayError("replayed gate results differ from sealed run")
    if replayed.decision != stored_decision:
        raise DecisionReplayError("replayed semantic decision differs from sealed run")
    if replayed.certificate != stored_certificate:
        raise DecisionReplayError("replayed certificate differs from sealed run")
    stored_features = _load_json(run_dir / "audit" / "feature_assembly.json")
    if stored_features != {"assembled_features": replayed.assembled_features}:
        raise DecisionReplayError("replayed features differ from sealed run")

    decision_sha = stored_decision["integrity"]["self_sha256"]
    certificate_sha = (
        None
        if stored_certificate is None
        else stored_certificate["integrity"]["self_sha256"]
    )
    return ReplayResult(decision_sha, certificate_sha, True)


def _config_from_spec(run_dir: Path, spec: dict[str, Any]) -> RunConfig:
    repository_root = Path(spec["repository_root"])
    return RunConfig(
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
        allow_example_calibration=spec["allow_example_calibration"],
        expected_calibration_sha256=spec["expected_calibration_sha256"],
        global_run_id=spec["global_run_id"],
        started_at=spec["started_at"],
        completed_at=spec["completed_at"],
        certificate_issued_at=spec["certificate_issued_at"],
    )


def _validate_run_spec(spec: dict[str, Any]) -> None:
    required = {
        "schema_id",
        "schema_version",
        "repository_root",
        "mode",
        "global_run_id",
        "started_at",
        "completed_at",
        "certificate_issued_at",
        "gate_action_policy_sha256",
        "allow_example_calibration",
        "expected_calibration_sha256",
    }
    if set(spec) != required:
        raise DecisionReplayError("run spec fields differ from GlobalValidatorReplaySpecV1")
    if spec.get("schema_id") != "GlobalValidatorReplaySpecV1":
        raise DecisionReplayError("expected GlobalValidatorReplaySpecV1")
    if spec.get("schema_version") != "1.0.0":
        raise DecisionReplayError("unsupported replay spec schema_version")
    repository_root = spec.get("repository_root")
    if not isinstance(repository_root, str) or not Path(repository_root).is_absolute():
        raise DecisionReplayError("run spec repository_root must be absolute")
    if type(spec.get("allow_example_calibration")) is not bool:
        raise DecisionReplayError("run spec allow_example_calibration must be boolean")
    for field in (
        "global_run_id",
        "started_at",
        "completed_at",
        "certificate_issued_at",
    ):
        if not isinstance(spec.get(field), str) or not spec[field]:
            raise DecisionReplayError(f"run spec {field} must be a nonempty string")
    _require_sha256(spec.get("gate_action_policy_sha256"), "gate_action_policy_sha256")
    expected_calibration = spec.get("expected_calibration_sha256")
    if expected_calibration is not None:
        _require_sha256(expected_calibration, "expected_calibration_sha256")
    try:
        ExecutionMode(spec.get("mode"))
    except ValueError as exc:
        raise DecisionReplayError("run spec mode is unsupported") from exc


def _verify_authority_copies(run_dir: Path, authority: Any) -> None:
    copies = {
        run_dir / "input" / "gate_policy.json": authority.gate_policy_path,
        run_dir / "input" / "feature_registry.json": authority.feature_registry_path,
    }
    for persisted, authoritative in copies.items():
        if sha256_file(persisted) != sha256_file(authoritative):
            raise DecisionReplayError(
                f"persisted {persisted.name} differs from verified authority"
            )


def _verify_input_projections(
    run_dir: Path, global_input: dict[str, Any]
) -> None:
    projections = {
        "effective_sense_contract.json": "effective_sense_contract",
        "frozen_candidate_contract.json": "frozen_candidate_contract",
        "constraint_evidence.json": "constraint_evidence",
        "context_evidence.json": "context_evidence",
        "attestation_evidence.json": "attestation_evidence",
    }
    for filename, field in projections.items():
        persisted = _load_json(run_dir / "input" / filename)
        if persisted != global_input.get(field):
            raise DecisionReplayError(
                f"persisted input projection {filename} differs from global input"
            )


def _verify_audit_bindings(
    run_dir: Path,
    *,
    spec: dict[str, Any],
    authority_mode: str,
    authority_warnings: tuple[str, ...],
    decision: dict[str, Any],
) -> None:
    authority_report = _load_json(
        run_dir / "audit" / "authority_verification.json"
    )
    expected_authority = {
        "status": "PASS",
        "receipt_integrity_mode": authority_mode,
        "warnings": list(authority_warnings),
    }
    if authority_report != expected_authority:
        raise DecisionReplayError("persisted authority verification report mismatch")

    certificate_path = run_dir / "output" / "terminology_certificate.json"
    certificate_sha = None
    if certificate_path.is_file():
        certificate_sha = _load_verified_json(certificate_path)["integrity"][
            "self_sha256"
        ]
    expected_run = {
        "status": "COMPLETE",
        "global_run_id": spec["global_run_id"],
        "mode": spec["mode"],
        "decision": decision["decision"],
        "decision_package_sha256": decision["integrity"]["self_sha256"],
        "certificate_sha256": certificate_sha,
    }
    if _load_json(run_dir / "audit" / "run.json") != expected_run:
        raise DecisionReplayError("persisted run summary bindings mismatch")


def _load_verified_json(path: Path) -> dict[str, Any]:
    value = _load_json(path)
    try:
        verify_self_hash(value, path=str(path))
    except ValueError as exc:
        raise DecisionReplayError(str(exc)) from exc
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise DecisionReplayError(f"cannot load replay artifact {path}: {exc}") from exc


def _require_sha256(value: Any, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.casefold()
        or any(character not in "0123456789abcdef" for character in value)
        or value == "0" * 64
    ):
        raise DecisionReplayError(f"run spec {field} must be a nonzero SHA-256")
