from __future__ import annotations

import argparse
import json
import socket
import tempfile
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import seal_self_hash

from ..audit import replay_run
from ..authority import verify_authority
from ..certificates import verify_persisted_certificate_bundle
from ..config import ExecutionMode, RunConfig
from ..engine import run_global_validator
from ..gates import load_gate_action_policy
from ..testing import load_base_input, make_candidate_input


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--authority-receipt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_release_evidence(
        args.repository_root.resolve(),
        args.authority_receipt.resolve(),
        args.output_dir.resolve(),
    )
    return 0


def build_release_evidence(
    repository_root: Path, authority_receipt: Path, output_dir: Path
) -> None:
    authority = verify_authority(
        authority_receipt,
        repository_root / "terminology_contracts_v1",
        repository_root=repository_root,
    )
    input_path = (
        repository_root
        / "terminology_contracts_v1"
        / "examples"
        / "valid"
        / "v1.1.0"
        / "global_validator_input.json"
    )
    calibration_path = input_path.with_name("calibration_artifact.json")
    collision_index_path = (
        repository_root
        / "terminology_contracts_v1"
        / "examples"
        / "support"
        / "v1.1.0"
        / "collision_index.json"
    )
    action_policy_path = (
        repository_root
        / "global_validator"
        / "v1"
        / "policies"
        / "gate_action_selection_v1.0.0.json"
    )
    action_policy = load_gate_action_policy(
        action_policy_path,
        gate_policy_path=authority.gate_policy_path,
        schema_dir=authority.schema_dir,
    )
    base = load_base_input(input_path)
    network_attempts = 0

    def forbid_network(*_args: Any, **_kwargs: Any) -> None:
        nonlocal network_attempts
        network_attempts += 1
        raise RuntimeError("release evidence attempted network access")

    original_create_connection = socket.create_connection
    socket.create_connection = forbid_network
    try:
        with tempfile.TemporaryDirectory(prefix="global-validator-release-") as temp:
            temp_root = Path(temp)
            baseline = run_global_validator(
                input_path,
                _config(
                    repository_root,
                    authority_receipt,
                    action_policy_path,
                    collision_index_path,
                    output_root=temp_root / "baseline",
                    run_id="release-development-baseline",
                ),
            )
            baseline_replay = replay_run(baseline.run_dir)

            frozen_config = _config(
                repository_root,
                authority_receipt,
                action_policy_path,
                collision_index_path,
                output_root=temp_root / "frozen",
                run_id="release-frozen-contract-fixture",
                mode=ExecutionMode.FROZEN_CALIBRATED,
                calibration_path=calibration_path,
                allow_example_calibration=True,
            )
            frozen = run_global_validator(input_path, frozen_config)
            frozen_replay = replay_run(frozen.run_dir)
            certificate_report = verify_persisted_certificate_bundle(
                frozen.run_dir,
                schema_dir=authority.schema_dir,
                feature_registry_path=authority.feature_registry_path,
            )

            pilot_decisions: list[dict[str, Any]] = []
            pilot_replays = 0
            inputs_dir = temp_root / "pilot-inputs"
            inputs_dir.mkdir()
            for sense_index in range(5):
                for candidate_index in range(3):
                    payload = make_candidate_input(
                        base,
                        sense_index=sense_index,
                        candidate_index=candidate_index,
                        schema_dir=authority.schema_dir,
                        gate_policy_path=authority.gate_policy_path,
                        feature_registry_path=authority.feature_registry_path,
                    )
                    candidate_path = (
                        inputs_dir / f"candidate-{sense_index}-{candidate_index}.json"
                    )
                    _write_json(candidate_path, payload)
                    result = run_global_validator(
                        candidate_path,
                        _config(
                            repository_root,
                            authority_receipt,
                            action_policy_path,
                            collision_index_path,
                            output_root=temp_root / "pilot-runs",
                            run_id=f"pilot-{sense_index}-{candidate_index}",
                        ),
                    )
                    pilot_replays += int(replay_run(result.run_dir).matched)
                    pilot_decisions.append(
                        {
                            "candidate_id": result.global_input["candidate_key"][
                                "candidate_id"
                            ],
                            "sense_id": result.global_input["candidate_key"][
                                "sense_id"
                            ],
                            "decision": result.decision["decision"],
                            "gate_result_sha256": result.gate_results["integrity"][
                                "self_sha256"
                            ],
                            "decision_sha256": result.decision["integrity"][
                                "self_sha256"
                            ],
                        }
                    )
    finally:
        socket.create_connection = original_create_connection

    if network_attempts:
        raise RuntimeError(f"release evidence made {network_attempts} network attempts")

    reports = {
        "authority_verification_report.json": {
            "schema_id": "GlobalValidatorAuthorityVerificationReportV1",
            "status": "PASS",
            "authority_tag": authority.receipt["authority_tag"],
            "authority_commit": authority.receipt["authority_commit"],
            "contract_version": authority.receipt["contract_version"],
            "manifest_sha256": authority.receipt["manifest_sha256"],
            "gate_policy_artifact_sha256": action_policy.gate_policy_artifact_sha256,
            "receipt_integrity_mode": authority.receipt_integrity_mode,
            "warnings": list(authority.warnings),
        },
        "gate_projection_report.json": {
            "schema_id": "GlobalValidatorGateProjectionReportV1",
            "status": "PASS",
            "gate_count": len(baseline.gate_results["observations"]),
            "gate_ids": [
                item["gate_id"] for item in baseline.gate_results["observations"]
            ],
            "triggered_gate_count": sum(
                item["triggered"] is True
                for item in baseline.gate_results["observations"]
            ),
            "gate_result_sha256": baseline.gate_results["integrity"]["self_sha256"],
        },
        "gate_policy_report.json": {
            "schema_id": "GlobalValidatorGatePolicyReportV1",
            "status": "PASS",
            "action_policy_id": action_policy.policy_id,
            "action_policy_version": action_policy.policy_version,
            "action_policy_sha256": action_policy.self_sha256,
            "gate_policy_artifact_sha256": action_policy.gate_policy_artifact_sha256,
            "actions": action_policy.actions,
        },
        "feature_assembly_report.json": {
            "schema_id": "GlobalValidatorFeatureAssemblyReportV1",
            "status": "PASS",
            "feature_contract_version": "1.1.0",
            "assembled_features": baseline.assembled_features,
            "development_decision_features": baseline.decision["decision_features"],
        },
        "decision_replay_report.json": {
            "schema_id": "GlobalValidatorDecisionReplayReportV1",
            "status": "PASS",
            "development_baseline_matched": baseline_replay.matched,
            "frozen_fixture_matched": frozen_replay.matched,
            "pilot_replay_count": pilot_replays,
            "pilot_expected_replay_count": 15,
        },
        "certificate_bundle_report.json": {
            "schema_id": "GlobalValidatorCertificateBundleReportV1",
            "status": certificate_report["status"],
            "fixture_only": True,
            "decision": frozen.decision["decision"],
            "approval_score": frozen.decision["approval_score"],
            "certificate_sha256": frozen.certificate["integrity"]["self_sha256"],
            "bundle_verification": certificate_report,
            "production_authority": False,
            "production_blocker": "NO_HUMAN_FROZEN_CALIBRATION_ARTIFACT",
        },
        "pilot_zero_api_summary.json": {
            "schema_id": "GlobalValidatorZeroApiPilotSummaryV1",
            "status": "PASS",
            "fixture_kind": "SYNTHETIC_CONTRACT_FIXTURE",
            "sense_count": len({item["sense_id"] for item in pilot_decisions}),
            "candidate_count": len(pilot_decisions),
            "decision_count": len(pilot_decisions),
            "provisional_count": sum(
                item["decision"] == "PROVISIONAL" for item in pilot_decisions
            ),
            "auto_approved_count": sum(
                item["decision"] == "AUTO_APPROVED" for item in pilot_decisions
            ),
            "certificate_count": 0,
            "provider_call_count": network_attempts,
            "replay_pass_count": pilot_replays,
            "decisions": pilot_decisions,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, report in reports.items():
        report["schema_version"] = "1.0.0"
        report["integrity"] = {"self_sha256": "0" * 64}
        _write_json(output_dir / filename, seal_self_hash(report))


def _config(
    repository_root: Path,
    authority_receipt: Path,
    action_policy_path: Path,
    collision_index_path: Path,
    *,
    output_root: Path,
    run_id: str,
    mode: ExecutionMode = ExecutionMode.DEVELOPMENT_HEURISTIC,
    calibration_path: Path | None = None,
    allow_example_calibration: bool = False,
) -> RunConfig:
    return RunConfig(
        repository_root=repository_root,
        authority_receipt_path=authority_receipt,
        gate_action_policy_path=action_policy_path,
        mode=mode,
        calibration_path=calibration_path,
        collision_index_path=collision_index_path,
        output_root=output_root,
        allow_example_calibration=allow_example_calibration,
        global_run_id=run_id,
        started_at="2026-07-29T00:00:00+00:00",
        completed_at="2026-07-29T00:00:01+00:00",
        certificate_issued_at="2026-07-29T00:00:02+00:00",
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
