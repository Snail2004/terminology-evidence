from __future__ import annotations

from pathlib import Path

from terminology_contracts.integrity import seal_self_hash

from global_validator.v1.cli import main


def _authority_args(repository_root: Path, authority_receipt: Path) -> list[str]:
    return [
        "--repository-root",
        str(repository_root),
        "--authority-receipt",
        str(authority_receipt),
    ]


def test_cli_development_run_and_replay(
    repository_root: Path,
    authority_receipt: Path,
    valid_input_path: Path,
    collision_index_path: Path,
    tmp_path: Path,
    capsys,
) -> None:
    common = _authority_args(repository_root, authority_receipt)
    assert main(
        [
            "validate-input",
            *common,
            "--input",
            str(valid_input_path),
            "--collision-index",
            str(collision_index_path),
        ]
    ) == 0
    assert main(
        [
            "run",
            *common,
            "--input",
            str(valid_input_path),
            "--mode",
            "DEVELOPMENT_HEURISTIC",
            "--collision-index",
            str(collision_index_path),
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "cli-development",
        ]
    ) == 0
    assert main(
        ["replay", "--run-dir", str(tmp_path / "cli-development")]
    ) == 0
    assert '"matched": true' in capsys.readouterr().out


def test_cli_assembles_exact_global_input(
    repository_root: Path,
    authority_receipt: Path,
    collision_index_path: Path,
    tmp_path: Path,
) -> None:
    examples = (
        repository_root
        / "terminology_contracts_v1"
        / "examples"
        / "valid"
        / "v1.1.0"
    )
    output = tmp_path / "assembled.json"
    common = _authority_args(repository_root, authority_receipt)
    assert main(
        [
            "assemble-input",
            *common,
            "--effective-sense",
            str(examples / "effective_sense_contract.json"),
            "--frozen-candidate",
            str(examples / "frozen_candidate_contract.json"),
            "--constraints",
            str(examples / "constraint_evidence_package.json"),
            "--context-evidence",
            str(examples / "context_evidence_package.json"),
            "--attestation-evidence",
            str(examples / "attestation_evidence_package.json"),
            "--assembled-at",
            "2026-07-29T00:00:00+00:00",
            "--output",
            str(output),
        ]
    ) == 0
    assert main(
        [
            "validate-input",
            *common,
            "--input",
            str(output),
            "--collision-index",
            str(collision_index_path),
        ]
    ) == 0


def test_cli_frozen_bundle_and_decision_verification(
    repository_root: Path,
    authority_receipt: Path,
    valid_input_path: Path,
    collision_index_path: Path,
    calibration_path: Path,
    tmp_path: Path,
) -> None:
    common = _authority_args(repository_root, authority_receipt)
    run_id = "cli-frozen"
    assert main(
        [
            "run",
            *common,
            "--input",
            str(valid_input_path),
            "--mode",
            "FROZEN_CALIBRATED",
            "--calibration",
            str(calibration_path),
            "--collision-index",
            str(collision_index_path),
            "--output-dir",
            str(tmp_path),
            "--run-id",
            run_id,
            "--allow-example-calibration",
        ]
    ) == 0
    run_dir = tmp_path / run_id
    assert main(
        [
            "verify-decision",
            *common,
            "--decision",
            str(run_dir / "output" / "global_decision_package.json"),
            "--global-input",
            str(run_dir / "input" / "global_validator_input.json"),
            "--calibration",
            str(run_dir / "input" / "calibration_artifact.json"),
            "--collision-index",
            str(run_dir / "input" / "collision_index.json"),
        ]
    ) == 0
    assert main(
        [
            "verify-certificate-bundle",
            "--bundle-dir",
            str(run_dir),
            "--repository-root",
            str(repository_root),
        ]
    ) == 0


def test_cli_maps_schema_errors_to_exit_code_two(
    repository_root: Path,
    authority_receipt: Path,
    collision_index_path: Path,
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "invalid.json"
    import json

    invalid.write_text(
        json.dumps(seal_self_hash({"schema_id": "Nope"})), encoding="utf-8"
    )
    assert main(
        [
            "validate-input",
            *_authority_args(repository_root, authority_receipt),
            "--input",
            str(invalid),
            "--collision-index",
            str(collision_index_path),
        ]
    ) == 2
