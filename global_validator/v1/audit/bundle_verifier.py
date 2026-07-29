from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import safe_relative_path

from ..errors import IntegrityValidationError
from ..jsonio import assert_strict_json_file

_CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
_REQUIRED_FILES = {
    "audit/authority_verification.json",
    "audit/feature_assembly.json",
    "audit/run.json",
    "audit/run_spec.json",
    "input/attestation_evidence.json",
    "input/authority_receipt.json",
    "input/constraint_evidence.json",
    "input/context_evidence.json",
    "input/effective_sense_contract.json",
    "input/feature_registry.json",
    "input/frozen_candidate_contract.json",
    "input/gate_action_policy.json",
    "input/gate_policy.json",
    "input/global_validator_input.json",
    "output/gate_result_set.json",
    "output/global_decision_package.json",
}
_OPTIONAL_FILES = {
    "audit/certificate_bundle.json",
    "input/calibration_artifact.json",
    "input/collision_index.json",
    "output/terminology_certificate.json",
}


def verify_persisted_run_bundle_integrity(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise IntegrityValidationError(f"run bundle directory is missing: {run_dir}")
    _reject_symlinks(run_dir)

    checksum_path = run_dir / "CHECKSUMS.sha256"
    if not checksum_path.is_file():
        raise IntegrityValidationError("CHECKSUMS.sha256 is missing")
    try:
        checksum_bytes = checksum_path.read_bytes()
        checksum_text = checksum_bytes.decode("ascii")
    except (OSError, UnicodeError) as exc:
        raise IntegrityValidationError(f"cannot read CHECKSUMS.sha256: {exc}") from exc
    if not checksum_text.endswith("\n") or "\r" in checksum_text:
        raise IntegrityValidationError(
            "CHECKSUMS.sha256 must use canonical LF text with a final newline"
        )

    expected: dict[str, str] = {}
    ordered_paths: list[str] = []
    casefolded: set[str] = set()
    for line_number, line in enumerate(checksum_text.splitlines(), start=1):
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise IntegrityValidationError(
                f"invalid CHECKSUMS.sha256 line {line_number}"
            )
        digest, relative = match.groups()
        try:
            safe_relative_path(relative, field=f"checksum line {line_number}")
        except ValueError as exc:
            raise IntegrityValidationError(str(exc)) from exc
        if relative == "CHECKSUMS.sha256":
            raise IntegrityValidationError("CHECKSUMS.sha256 cannot list itself")
        folded = relative.casefold()
        if folded in casefolded:
            raise IntegrityValidationError(
                f"duplicate or case-confusable checksum path: {relative}"
            )
        casefolded.add(folded)
        expected[relative] = digest
        ordered_paths.append(relative)
    if ordered_paths != sorted(ordered_paths):
        raise IntegrityValidationError("CHECKSUMS.sha256 paths are not canonical-sorted")

    actual_paths = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path != checksum_path
    }
    expected_paths = set(expected)
    missing = sorted(expected_paths.difference(actual_paths))
    unlisted = sorted(actual_paths.difference(expected_paths))
    if missing:
        raise IntegrityValidationError(
            "checksummed file is missing: " + ", ".join(missing)
        )
    if unlisted:
        raise IntegrityValidationError(
            "unlisted bundle file: " + ", ".join(unlisted)
        )

    unsupported = sorted(actual_paths.difference(_REQUIRED_FILES | _OPTIONAL_FILES))
    absent = sorted(_REQUIRED_FILES.difference(actual_paths))
    if unsupported:
        raise IntegrityValidationError(
            "unsupported run bundle file: " + ", ".join(unsupported)
        )
    if absent:
        raise IntegrityValidationError(
            "required run bundle file is missing: " + ", ".join(absent)
        )
    has_certificate = "output/terminology_certificate.json" in actual_paths
    has_certificate_report = "audit/certificate_bundle.json" in actual_paths
    if has_certificate != has_certificate_report:
        raise IntegrityValidationError(
            "certificate and certificate bundle report must be present together"
        )
    if has_certificate and "input/calibration_artifact.json" not in actual_paths:
        raise IntegrityValidationError("certificate bundle is missing calibration")

    for relative in ordered_paths:
        path = run_dir.joinpath(*relative.split("/"))
        try:
            path.resolve().relative_to(run_dir)
            actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError) as exc:
            raise IntegrityValidationError(
                f"cannot verify checksummed file {relative}: {exc}"
            ) from exc
        if actual_digest != expected[relative]:
            raise IntegrityValidationError(f"checksum mismatch: {relative}")

    for relative in sorted(path for path in actual_paths if path.endswith(".json")):
        try:
            assert_strict_json_file(run_dir.joinpath(*relative.split("/")))
        except (OSError, UnicodeError, ValueError) as exc:
            raise IntegrityValidationError(
                f"bundle JSON is not strict: {relative}: {exc}"
            ) from exc

    return {
        "status": "PASS",
        "checked_files": len(actual_paths),
        "checksum_entry_count": len(expected),
        "checksums_sha256": hashlib.sha256(checksum_bytes).hexdigest(),
        "strict_json_status": "PASS",
    }


def _reject_symlinks(run_dir: Path) -> None:
    for path in run_dir.rglob("*"):
        if path.is_symlink():
            raise IntegrityValidationError(
                f"run bundle cannot contain symlinks: {path.relative_to(run_dir)}"
            )
