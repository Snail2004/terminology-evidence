from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from terminology_contracts.validation import verify_certificate_bundle

from ..audit.bundle_verifier import verify_persisted_run_bundle_integrity
from ..errors import CertificateBindingError, IntegrityValidationError


def verify_persisted_certificate_bundle(
    run_dir: Path,
    *,
    schema_dir: Path,
    feature_registry_path: Path,
    authority_root: Path | None = None,
    exact_replay: bool = True,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    paths = {
        "certificate": run_dir / "output" / "terminology_certificate.json",
        "frozen_candidate": run_dir / "input" / "frozen_candidate_contract.json",
        "effective_sense": run_dir / "input" / "effective_sense_contract.json",
        "constraint_evidence": run_dir / "input" / "constraint_evidence.json",
        "global_input": run_dir / "input" / "global_validator_input.json",
        "context_evidence": run_dir / "input" / "context_evidence.json",
        "attestation_evidence": run_dir / "input" / "attestation_evidence.json",
        "gate_result": run_dir / "output" / "gate_result_set.json",
        "decision": run_dir / "output" / "global_decision_package.json",
        "calibration": run_dir / "input" / "calibration_artifact.json",
        "gate_policy": run_dir / "input" / "gate_policy.json",
        "feature_registry": run_dir / "input" / "feature_registry.json",
        "collision_index": run_dir / "input" / "collision_index.json",
    }
    required = tuple(path for name, path in paths.items() if name != "collision_index")
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise CertificateBindingError(
            "certificate bundle is incomplete: " + ", ".join(missing)
        )
    try:
        integrity_report = verify_persisted_run_bundle_integrity(run_dir)
    except IntegrityValidationError as exc:
        raise CertificateBindingError(str(exc)) from exc
    checksum_errors: list[str] = []
    if _sha256(paths["feature_registry"]) != _sha256(feature_registry_path):
        checksum_errors.append("feature registry differs from verified authority")
    errors = verify_certificate_bundle(
        certificate_path=paths["certificate"],
        frozen_candidate_path=paths["frozen_candidate"],
        effective_sense_contract_path=paths["effective_sense"],
        constraint_evidence_path=paths["constraint_evidence"],
        global_input_path=paths["global_input"],
        context_evidence_path=paths["context_evidence"],
        attestation_evidence_path=paths["attestation_evidence"],
        gate_result_path=paths["gate_result"],
        decision_path=paths["decision"],
        calibration_path=paths["calibration"],
        gate_policy_path=paths["gate_policy"],
        collision_index_path=(
            paths["collision_index"] if paths["collision_index"].is_file() else None
        ),
        schema_dir=schema_dir,
        feature_registry_path=paths["feature_registry"],
    )
    all_errors = checksum_errors + errors
    if all_errors:
        raise CertificateBindingError(
            "certificate bundle verification failed: " + "; ".join(all_errors)
        )
    report = {
        "status": "PASS",
        "checked_files": integrity_report["checked_files"],
        "checksum_status": "PASS",
        "strict_json_status": integrity_report["strict_json_status"],
        "certificate_status": "PASS",
    }
    if exact_replay:
        from ..audit import replay_run

        replayed = replay_run(run_dir, authority_root=authority_root)
        report.update(
            {
                "decision_replay_status": "PASS",
                "decision_sha256": replayed.decision_sha256,
                "certificate_sha256": replayed.certificate_sha256,
            }
        )
    return report


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
