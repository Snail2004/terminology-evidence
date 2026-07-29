from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from terminology_contracts.validation import verify_certificate_bundle

from ..config import RunConfig
from ..errors import CertificateBindingError, StorageError
from ..gates import GateActionPolicy


def persist_run_bundle(
    *,
    config: RunConfig,
    authority_integrity_mode: str,
    authority_warnings: tuple[str, ...],
    global_input: Mapping[str, Any],
    gate_results: Mapping[str, Any],
    assembled_features: Mapping[str, float],
    decision: Mapping[str, Any],
    certificate: Mapping[str, Any] | None,
    action_policy: GateActionPolicy,
) -> Path:
    if config.output_root is None:
        raise StorageError("output_root is required to persist a run")
    output_root = config.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / config.global_run_id
    if target.exists():
        raise StorageError(f"run directory already exists: {target}")

    staging = Path(
        tempfile.mkdtemp(prefix=f".{config.global_run_id}.", dir=output_root)
    )
    try:
        paths = _write_bundle(
            staging=staging,
            config=config,
            authority_integrity_mode=authority_integrity_mode,
            authority_warnings=authority_warnings,
            global_input=global_input,
            gate_results=gate_results,
            assembled_features=assembled_features,
            decision=decision,
            certificate=certificate,
            action_policy=action_policy,
        )
        if certificate is not None:
            errors = verify_certificate_bundle(
                certificate_path=paths["certificate"],
                frozen_candidate_path=paths["frozen_candidate"],
                effective_sense_contract_path=paths["effective_sense"],
                constraint_evidence_path=paths["constraint_evidence"],
                global_input_path=paths["global_input"],
                context_evidence_path=paths["context_evidence"],
                attestation_evidence_path=paths["attestation_evidence"],
                gate_result_path=paths["gate_results"],
                decision_path=paths["decision"],
                calibration_path=paths.get("calibration"),
                gate_policy_path=paths["gate_policy"],
                collision_index_path=paths.get("collision_index"),
                schema_dir=config.schema_dir,
                feature_registry_path=paths["feature_registry"],
            )
            _write_json(staging / "audit" / "certificate_bundle.json", {
                "status": "PASS" if not errors else "FAIL",
                "errors": errors,
            })
            if errors:
                raise CertificateBindingError(
                    "certificate bundle verification failed: " + "; ".join(errors)
                )
        _write_checksums(staging)
        os.replace(staging, target)
        return target
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _write_bundle(
    *,
    staging: Path,
    config: RunConfig,
    authority_integrity_mode: str,
    authority_warnings: tuple[str, ...],
    global_input: Mapping[str, Any],
    gate_results: Mapping[str, Any],
    assembled_features: Mapping[str, float],
    decision: Mapping[str, Any],
    certificate: Mapping[str, Any] | None,
    action_policy: GateActionPolicy,
) -> dict[str, Path]:
    input_dir = staging / "input"
    output_dir = staging / "output"
    audit_dir = staging / "audit"
    for directory in (input_dir, output_dir, audit_dir):
        directory.mkdir(parents=True)

    paths = {
        "global_input": input_dir / "global_validator_input.json",
        "effective_sense": input_dir / "effective_sense_contract.json",
        "frozen_candidate": input_dir / "frozen_candidate_contract.json",
        "constraint_evidence": input_dir / "constraint_evidence.json",
        "context_evidence": input_dir / "context_evidence.json",
        "attestation_evidence": input_dir / "attestation_evidence.json",
        "gate_policy": input_dir / "gate_policy.json",
        "feature_registry": input_dir / "feature_registry.json",
        "gate_action_policy": input_dir / "gate_action_policy.json",
        "gate_action_policy_authority": (
            input_dir / "gate_action_policy_authority.json"
        ),
        "gate_results": output_dir / "gate_result_set.json",
        "decision": output_dir / "global_decision_package.json",
    }
    _write_json(paths["global_input"], global_input)
    _write_json(paths["effective_sense"], global_input["effective_sense_contract"])
    _write_json(paths["frozen_candidate"], global_input["frozen_candidate_contract"])
    _write_json(paths["constraint_evidence"], global_input["constraint_evidence"])
    _write_json(paths["context_evidence"], global_input["context_evidence"])
    _write_json(paths["attestation_evidence"], global_input["attestation_evidence"])
    shutil.copyfile(config.gate_policy_path, paths["gate_policy"])
    shutil.copyfile(config.feature_registry_path, paths["feature_registry"])
    _write_json(paths["gate_action_policy"], action_policy.payload)
    _write_json(
        paths["gate_action_policy_authority"], action_policy.authority_payload
    )
    _write_json(paths["gate_results"], gate_results)
    _write_json(paths["decision"], decision)

    if config.calibration_path is not None:
        paths["calibration"] = input_dir / "calibration_artifact.json"
        shutil.copyfile(config.calibration_path, paths["calibration"])
    if config.collision_index_path is not None:
        paths["collision_index"] = input_dir / "collision_index.json"
        shutil.copyfile(config.collision_index_path, paths["collision_index"])
    if certificate is not None:
        paths["certificate"] = output_dir / "terminology_certificate.json"
        _write_json(paths["certificate"], certificate)

    shutil.copyfile(
        config.authority_receipt_path,
        input_dir / "authority_receipt.json",
    )
    _write_json(audit_dir / "feature_assembly.json", {
        "assembled_features": dict(assembled_features)
    })
    _write_json(audit_dir / "authority_verification.json", {
        "status": "PASS",
        "receipt_integrity_mode": authority_integrity_mode,
        "warnings": list(authority_warnings),
    })
    _write_json(audit_dir / "run_spec.json", _run_spec(config, action_policy))
    _write_json(audit_dir / "run.json", {
        "status": "COMPLETE",
        "global_run_id": config.global_run_id,
        "mode": config.mode.value,
        "decision": decision["decision"],
        "decision_package_sha256": decision["integrity"]["self_sha256"],
        "certificate_sha256": (
            None if certificate is None else certificate["integrity"]["self_sha256"]
        ),
    })
    return paths


def _run_spec(config: RunConfig, action_policy: GateActionPolicy) -> dict[str, Any]:
    contracts_authority = action_policy.authority_payload["contracts_authority"]
    return {
        "schema_id": "GlobalValidatorReplaySpecV1",
        "schema_version": "1.1.0",
        "repository_root_hint": str(config.repository_root.resolve()),
        "contracts_authority_tag": contracts_authority["tag"],
        "contracts_authority_commit": contracts_authority["commit"],
        "contracts_manifest_sha256": contracts_authority["manifest_sha256"],
        "gate_action_policy_authority_sha256": action_policy.authority_sha256,
        "mode": config.mode.value,
        "global_run_id": config.global_run_id,
        "started_at": config.started_at,
        "completed_at": config.completed_at,
        "certificate_issued_at": config.certificate_issued_at,
        "gate_action_policy_sha256": action_policy.self_sha256,
        "allow_example_calibration": config.allow_example_calibration,
        "expected_calibration_sha256": config.expected_calibration_sha256,
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_checksums(root: Path) -> None:
    entries: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "CHECKSUMS.sha256":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(root).as_posix()
        entries.append(f"{digest}  {relative}")
    (root / "CHECKSUMS.sha256").write_text(
        "\n".join(entries) + "\n",
        encoding="ascii",
        newline="\n",
    )
