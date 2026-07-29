from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import (
    load_verified_json_artifact,
    sha256_file,
    verify_self_hash,
)
from terminology_contracts.manifest import verify_manifest

from ..errors import AuthorityVerificationError
from ..jsonio import assert_strict_json_file, load_json_object

AUTHORITY_SCHEMA_ID = "TerminologyContractsAuthorityReceiptV1"
AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
CONTRACT_VERSION = "1.1.0"
AUTHORITY_RECEIPT_SELF_SHA256 = (
    "c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4"
)
AUTHORITY_RECEIPT_PHYSICAL_SHA256 = (
    "3497460f16ca478dada7b25425775882f10d1cb2b5d3638c36cba4ec5fb2791b"
)


@dataclass(frozen=True)
class VerifiedAuthority:
    receipt: dict[str, Any]
    contracts_root: Path
    schema_dir: Path
    gate_policy_path: Path
    feature_registry_path: Path
    manifest_path: Path
    receipt_integrity_mode: str
    warnings: tuple[str, ...]


def verify_authority(
    receipt_path: Path,
    contracts_root: Path,
    *,
    repository_root: Path | None = None,
) -> VerifiedAuthority:
    receipt, receipt_integrity_mode, warnings = _load_receipt(receipt_path)
    _expect(receipt, "schema_id", AUTHORITY_SCHEMA_ID)
    _expect(receipt, "contract_version", CONTRACT_VERSION)
    _expect(receipt, "feature_contract_version", CONTRACT_VERSION)
    _expect(receipt, "authority_tag", AUTHORITY_TAG)
    _expect(receipt, "authority_commit", AUTHORITY_COMMIT)

    contracts_root = contracts_root.resolve()
    manifest_path = contracts_root / "manifest.json"
    gate_policy_path = contracts_root / "policies" / "gate_policy_v1.0.0.json"
    feature_registry_path = (
        contracts_root / "registries" / "feature_contract_v1.1.0.json"
    )
    schema_dir = contracts_root / "schemas" / "v1.1.0"
    required = (manifest_path, gate_policy_path, feature_registry_path)
    missing = [str(path) for path in required if not path.is_file()]
    if not schema_dir.is_dir():
        missing.append(str(schema_dir))
    if missing:
        raise AuthorityVerificationError(
            "contracts authority is incomplete: " + ", ".join(missing)
        )

    for path in required:
        try:
            assert_strict_json_file(path)
        except (OSError, UnicodeError, ValueError) as exc:
            raise AuthorityVerificationError(
                f"authority JSON is not strict: {path}: {exc}"
            ) from exc

    manifest = _strict_object(manifest_path)
    _expect(manifest, "package_version", CONTRACT_VERSION)
    _expect(
        manifest.get("integrity", {}),
        "manifest_sha256",
        receipt.get("manifest_sha256"),
    )
    if sha256_file(manifest_path) != receipt.get("manifest_file_sha256"):
        raise AuthorityVerificationError("manifest physical SHA-256 mismatch")

    gate_policy = load_verified_json_artifact(
        gate_policy_path,
        expected_self_sha256=receipt.get("gate_policy_artifact_sha256"),
    )
    if gate_policy.physical_sha256 != receipt.get("gate_policy_file_sha256"):
        raise AuthorityVerificationError("gate policy physical SHA-256 mismatch")
    if sha256_file(feature_registry_path) != receipt.get(
        "feature_contract_file_sha256"
    ):
        raise AuthorityVerificationError("feature registry physical SHA-256 mismatch")

    manifest_errors = verify_manifest(contracts_root)
    if manifest_errors:
        raise AuthorityVerificationError(
            "contracts manifest verification failed: " + "; ".join(manifest_errors)
        )
    if repository_root is not None:
        _verify_git_authority(repository_root.resolve())

    return VerifiedAuthority(
        receipt=receipt,
        contracts_root=contracts_root,
        schema_dir=schema_dir,
        gate_policy_path=gate_policy_path,
        feature_registry_path=feature_registry_path,
        manifest_path=manifest_path,
        receipt_integrity_mode=receipt_integrity_mode,
        warnings=warnings,
    )


def _load_receipt(path: Path) -> tuple[dict[str, Any], str, tuple[str, ...]]:
    try:
        value = load_json_object(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise AuthorityVerificationError(f"cannot load authority receipt: {exc}") from exc
    try:
        verify_self_hash(value, path=str(path))
    except ValueError as exc:
        raise AuthorityVerificationError(str(exc)) from exc
    declared = value.get("integrity", {}).get("self_sha256")
    if declared != AUTHORITY_RECEIPT_SELF_SHA256:
        raise AuthorityVerificationError(
            "authority receipt canonical self SHA-256 differs from published receipt"
        )
    if sha256_file(path) != AUTHORITY_RECEIPT_PHYSICAL_SHA256:
        raise AuthorityVerificationError(
            "authority receipt physical SHA-256 differs from published receipt"
        )
    return value, "CANONICAL_SELF_HASH", ()


def _strict_object(path: Path) -> dict[str, Any]:
    try:
        value = load_json_object(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise AuthorityVerificationError(f"cannot load {path}: {exc}") from exc
    return value


def _expect(value: Any, field: str, expected: Any) -> None:
    actual = value.get(field) if isinstance(value, dict) else None
    if actual != expected:
        raise AuthorityVerificationError(
            f"authority {field} mismatch: expected {expected!r}, got {actual!r}"
        )


def _verify_git_authority(repository_root: Path) -> None:
    try:
        tag_commit = subprocess.run(
            ["git", "rev-parse", f"{AUTHORITY_TAG}^{{commit}}"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        drift = subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                f"{AUTHORITY_TAG}..HEAD",
                "--",
                "terminology_contracts_v1",
            ],
            cwd=repository_root,
            check=False,
        ).returncode
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuthorityVerificationError(f"cannot verify Git authority: {exc}") from exc
    if tag_commit != AUTHORITY_COMMIT:
        raise AuthorityVerificationError("authority tag does not resolve to receipt commit")
    if drift != 0:
        raise AuthorityVerificationError("contracts tree differs from authority tag")
