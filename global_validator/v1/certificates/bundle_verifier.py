from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from terminology_contracts.validation import verify_certificate_bundle

from ..errors import CertificateBindingError, IntegrityValidationError
from ..jsonio import assert_strict_json_file


def verify_persisted_certificate_bundle(
    run_dir: Path,
    *,
    schema_dir: Path,
    feature_registry_path: Path,
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
        for path in run_dir.rglob("*.json"):
            assert_strict_json_file(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise IntegrityValidationError(f"bundle JSON is not strict: {exc}") from exc

    checksum_errors = _verify_checksums(run_dir)
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
    return {
        "status": "PASS",
        "checked_files": len(required) + int(paths["collision_index"].is_file()),
        "checksum_status": "PASS",
        "certificate_status": "PASS",
    }


def _verify_checksums(run_dir: Path) -> list[str]:
    checksum_path = run_dir / "CHECKSUMS.sha256"
    if not checksum_path.is_file():
        return ["CHECKSUMS.sha256 is missing"]
    errors: list[str] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        checksum_path.read_text(encoding="ascii").splitlines(), start=1
    ):
        if "  " not in line:
            errors.append(f"invalid checksum line {line_number}")
            continue
        expected, relative = line.split("  ", 1)
        if relative in seen:
            errors.append(f"duplicate checksum path: {relative}")
            continue
        seen.add(relative)
        candidate = (run_dir / Path(relative)).resolve()
        try:
            candidate.relative_to(run_dir)
        except ValueError:
            errors.append(f"unsafe checksum path: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"checksummed file is missing: {relative}")
            continue
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"checksum mismatch: {relative}")
    actual_files = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path != checksum_path
    }
    for relative in sorted(actual_files.difference(seen)):
        errors.append(f"unlisted bundle file: {relative}")
    return errors


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
