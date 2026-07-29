from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .audit import replay_run
from .authority import verify_authority
from .certificates import verify_persisted_certificate_bundle
from .config import ExecutionMode, RunConfig
from .decision import verify_decision_artifact
from .engine import run_global_validator
from .errors import (
    AuthorityVerificationError,
    CalibrationError,
    CertificateBindingError,
    DecisionReplayError,
    FeatureAssemblyError,
    GatePolicyError,
    GateProjectionError,
    GlobalValidatorError,
    InputValidationError,
    IntegrityValidationError,
    JoinValidationError,
    StorageError,
)
from .input import (
    assemble_global_input,
    load_and_validate_global_input,
    load_contract_artifact,
    verify_collision_index_binding,
)


EXIT_CODES = {
    AuthorityVerificationError: 2,
    InputValidationError: 2,
    IntegrityValidationError: 3,
    JoinValidationError: 4,
    GatePolicyError: 5,
    GateProjectionError: 5,
    FeatureAssemblyError: 5,
    CalibrationError: 6,
    CertificateBindingError: 7,
    DecisionReplayError: 8,
    StorageError: 9,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="global-validator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    authority = subparsers.add_parser("authority-verify")
    authority.add_argument("--receipt", type=Path, required=True)
    authority.add_argument("--contracts-root", type=Path, required=True)
    authority.add_argument("--repository-root", type=Path)
    authority.set_defaults(handler=_authority_verify)

    assemble = subparsers.add_parser("assemble-input")
    _add_authority_arguments(assemble)
    assemble.add_argument("--effective-sense", type=Path, required=True)
    assemble.add_argument("--frozen-candidate", type=Path, required=True)
    assemble.add_argument("--constraints", type=Path, required=True)
    assemble.add_argument("--context-evidence", type=Path, required=True)
    assemble.add_argument("--attestation-evidence", type=Path, required=True)
    assemble.add_argument("--optional-probe", type=Path, action="append", default=[])
    assemble.add_argument("--assembled-at")
    assemble.add_argument("--output", type=Path, required=True)
    assemble.set_defaults(handler=_assemble_input)

    validate = subparsers.add_parser("validate-input")
    _add_authority_arguments(validate)
    validate.add_argument("--input", type=Path, required=True)
    validate.add_argument("--collision-index", type=Path)
    validate.set_defaults(handler=_validate_input)

    run = subparsers.add_parser("run")
    _add_authority_arguments(run)
    run.add_argument("--input", type=Path, required=True)
    run.add_argument(
        "--mode",
        choices=[mode.value for mode in ExecutionMode],
        required=True,
    )
    run.add_argument("--calibration", type=Path)
    run.add_argument("--expected-calibration-sha256")
    run.add_argument("--collision-index", type=Path)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--started-at", default="1970-01-01T00:00:00+00:00")
    run.add_argument("--completed-at", default="1970-01-01T00:00:00+00:00")
    run.add_argument(
        "--certificate-issued-at", default="1970-01-01T00:00:00+00:00"
    )
    run.add_argument("--allow-example-calibration", action="store_true")
    run.set_defaults(handler=_run)

    replay = subparsers.add_parser("replay")
    replay.add_argument("--run-dir", type=Path, required=True)
    replay.add_argument("--authority-root", type=Path)
    replay.set_defaults(handler=_replay)

    decision = subparsers.add_parser("verify-decision")
    _add_authority_arguments(decision)
    decision.add_argument("--decision", type=Path, required=True)
    decision.add_argument("--global-input", type=Path, required=True)
    decision.add_argument("--calibration", type=Path)
    decision.add_argument("--collision-index", type=Path)
    decision.add_argument(
        "--mode",
        choices=[mode.value for mode in ExecutionMode],
        required=True,
    )
    decision.add_argument("--expected-calibration-sha256")
    decision.add_argument("--allow-example-calibration", action="store_true")
    decision.add_argument("--run-id", required=True)
    decision.add_argument("--started-at", required=True)
    decision.add_argument("--completed-at", required=True)
    decision.add_argument("--certificate-issued-at", required=True)
    decision.set_defaults(handler=_verify_decision)

    bundle = subparsers.add_parser("verify-certificate-bundle")
    bundle.add_argument("--bundle-dir", type=Path, required=True)
    bundle.add_argument("--repository-root", type=Path, default=Path.cwd())
    bundle.add_argument("--authority-receipt", type=Path)
    bundle.set_defaults(handler=_verify_bundle)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except tuple(EXIT_CODES) as exc:
        _emit_error(exc)
        return _exit_code(exc)
    except GlobalValidatorError as exc:
        _emit_error(exc)
        return 9
    except Exception as exc:
        _emit_error(exc)
        return 9
    _emit(result)
    return 0


def _add_authority_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--authority-receipt", type=Path, required=True)
    parser.add_argument("--action-policy", type=Path)


def _base_config(args: argparse.Namespace, **overrides: Any) -> RunConfig:
    root = args.repository_root.resolve()
    action_policy = args.action_policy or (
        root / "global_validator" / "v1" / "policies" / "gate_action_selection_v1.0.0.json"
    )
    return RunConfig(
        repository_root=root,
        authority_receipt_path=args.authority_receipt.resolve(),
        gate_action_policy_path=action_policy.resolve(),
        **overrides,
    )


def _authority_verify(args: argparse.Namespace) -> dict[str, Any]:
    verified = verify_authority(
        args.receipt,
        args.contracts_root,
        repository_root=args.repository_root,
    )
    return {
        "status": "PASS",
        "authority_tag": verified.receipt["authority_tag"],
        "authority_commit": verified.receipt["authority_commit"],
        "contract_version": verified.receipt["contract_version"],
        "receipt_integrity_mode": verified.receipt_integrity_mode,
        "warnings": list(verified.warnings),
    }


def _assemble_input(args: argparse.Namespace) -> dict[str, Any]:
    config = _base_config(args)
    authority = verify_authority(
        config.authority_receipt_path,
        config.contracts_root,
        repository_root=config.repository_root,
    )
    load_kwargs = {
        "schema_dir": authority.schema_dir,
        "gate_policy_path": authority.gate_policy_path,
        "feature_registry_path": authority.feature_registry_path,
    }
    result = assemble_global_input(
        effective_sense_contract=load_contract_artifact(
            args.effective_sense, **load_kwargs
        ),
        frozen_candidate_contract=load_contract_artifact(
            args.frozen_candidate, **load_kwargs
        ),
        constraint_evidence=load_contract_artifact(args.constraints, **load_kwargs),
        context_evidence=load_contract_artifact(args.context_evidence, **load_kwargs),
        attestation_evidence=load_contract_artifact(
            args.attestation_evidence, **load_kwargs
        ),
        optional_probes=[
            load_contract_artifact(path, **load_kwargs) for path in args.optional_probe
        ],
        assembled_at=args.assembled_at,
        schema_dir=authority.schema_dir,
        gate_policy_path=authority.gate_policy_path,
        feature_registry_path=authority.feature_registry_path,
    )
    _write_new_json(args.output, result)
    return {
        "status": "PASS",
        "output": str(args.output.resolve()),
        "self_sha256": result["integrity"]["self_sha256"],
    }


def _validate_input(args: argparse.Namespace) -> dict[str, Any]:
    config = _base_config(args)
    authority = verify_authority(
        config.authority_receipt_path,
        config.contracts_root,
        repository_root=config.repository_root,
    )
    value = load_and_validate_global_input(
        args.input,
        schema_dir=authority.schema_dir,
        gate_policy_path=authority.gate_policy_path,
        feature_registry_path=authority.feature_registry_path,
    )
    verify_collision_index_binding(value, args.collision_index)
    return {
        "status": "PASS",
        "candidate_id": value["candidate_key"]["candidate_id"],
        "self_sha256": value["integrity"]["self_sha256"],
    }


def _run(args: argparse.Namespace) -> dict[str, Any]:
    config = _base_config(
        args,
        mode=ExecutionMode(args.mode),
        calibration_path=args.calibration,
        expected_calibration_sha256=args.expected_calibration_sha256,
        collision_index_path=args.collision_index,
        output_root=args.output_dir,
        allow_example_calibration=args.allow_example_calibration,
        global_run_id=args.run_id,
        started_at=args.started_at,
        completed_at=args.completed_at,
        certificate_issued_at=args.certificate_issued_at,
    )
    result = run_global_validator(args.input, config)
    return {
        "status": "PASS",
        "decision": result.decision["decision"],
        "approval_score": result.decision["approval_score"],
        "gate_result_sha256": result.gate_results["integrity"]["self_sha256"],
        "decision_sha256": result.decision["integrity"]["self_sha256"],
        "certificate_sha256": (
            None
            if result.certificate is None
            else result.certificate["integrity"]["self_sha256"]
        ),
        "run_dir": str(result.run_dir),
        "authority_warnings": list(result.authority.warnings),
    }


def _replay(args: argparse.Namespace) -> dict[str, Any]:
    result = replay_run(args.run_dir, authority_root=args.authority_root)
    return {
        "status": "PASS",
        "matched": result.matched,
        "decision_sha256": result.decision_sha256,
        "certificate_sha256": result.certificate_sha256,
    }


def _verify_decision(args: argparse.Namespace) -> dict[str, Any]:
    config = _base_config(
        args,
        mode=ExecutionMode(args.mode),
        calibration_path=args.calibration,
        collision_index_path=args.collision_index,
        expected_calibration_sha256=args.expected_calibration_sha256,
        allow_example_calibration=args.allow_example_calibration,
        global_run_id=args.run_id,
        started_at=args.started_at,
        completed_at=args.completed_at,
        certificate_issued_at=args.certificate_issued_at,
    )
    decision = verify_decision_artifact(
        args.decision,
        global_input_path=args.global_input,
        config=config,
    )
    return {
        "status": "PASS",
        "decision": decision["decision"],
        "self_sha256": decision["integrity"]["self_sha256"],
    }


def _verify_bundle(args: argparse.Namespace) -> dict[str, Any]:
    repository_root = args.repository_root.resolve()
    receipt = args.authority_receipt or (
        args.bundle_dir / "input" / "authority_receipt.json"
    )
    authority = verify_authority(
        receipt,
        repository_root / "terminology_contracts_v1",
        repository_root=repository_root,
    )
    return verify_persisted_certificate_bundle(
        args.bundle_dir,
        schema_dir=authority.schema_dir,
        feature_registry_path=authority.feature_registry_path,
        authority_root=repository_root,
    )


def _write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(
                value,
                stream,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            stream.write("\n")
    except FileExistsError as exc:
        raise StorageError(f"refusing to overwrite existing output: {path}") from exc


def _exit_code(exc: Exception) -> int:
    return next(
        code for error_type, code in EXIT_CODES.items() if isinstance(exc, error_type)
    )


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))


def _emit_error(exc: Exception) -> None:
    print(
        json.dumps(
            {
                "status": "ERROR",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
