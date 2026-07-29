"""Fail-closed verification of the immutable Contracts V1.1 authority."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import (
    load_verified_json_artifact,
    sha256_file,
    verify_self_hash,
)
from terminology_contracts.manifest import verify_manifest
from .jsonio import load_strict_json_object


AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
AUTHORITY_TAG_OBJECT = "1a8c00d12f100145a276cd8304440ff0a7e8d2a1"
AUTHORITY_RECEIPT_SELF_SHA256 = (
    "c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4"
)
AUTHORITY_RECEIPT_PHYSICAL_SHA256 = (
    "3497460f16ca478dada7b25425775882f10d1cb2b5d3638c36cba4ec5fb2791b"
)
CONTRACT_MANIFEST_SHA256 = (
    "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
)
CONTRACT_MANIFEST_FILE_SHA256 = (
    "383884e28e9b9203b0ce346d8ad08572dea235a2d53c40c07bf1de22403f73fc"
)
GATE_POLICY_SHA256 = (
    "9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2"
)


def verify_contract_authority(
    *, repository_root: str | Path, receipt_path: str | Path
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    receipt_file = Path(receipt_path).resolve(strict=True)
    receipt = load_strict_json_object(receipt_file)
    verify_self_hash(receipt, path=str(receipt_file))

    expected = {
        "schema_id": "TerminologyContractsAuthorityReceiptV1",
        "contract_version": "1.1.0",
        "feature_contract_version": "1.1.0",
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "authority_tag_object_sha": AUTHORITY_TAG_OBJECT,
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "manifest_file_sha256": CONTRACT_MANIFEST_FILE_SHA256,
        "gate_policy_artifact_sha256": GATE_POLICY_SHA256,
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise ValueError(f"contracts authority {field} mismatch")
    if receipt["integrity"]["self_sha256"] != AUTHORITY_RECEIPT_SELF_SHA256:
        raise ValueError("contracts authority receipt canonical hash mismatch")
    if sha256_file(receipt_file) != AUTHORITY_RECEIPT_PHYSICAL_SHA256:
        raise ValueError("contracts authority receipt physical hash mismatch")

    contracts_root = repository / "terminology_contracts_v1"
    manifest_path = contracts_root / "manifest.json"
    gate_policy_path = contracts_root / "policies" / "gate_policy_v1.0.0.json"
    feature_registry_path = (
        contracts_root / "registries" / "feature_contract_v1.1.0.json"
    )
    schema_dir = contracts_root / "schemas" / "v1.1.0"
    for path in (manifest_path, gate_policy_path, feature_registry_path):
        if not path.is_file():
            raise ValueError(f"contracts authority file is missing: {path}")
    if not schema_dir.is_dir():
        raise ValueError("contracts authority V1.1 schema directory is missing")

    manifest = load_strict_json_object(manifest_path)
    if manifest.get("integrity", {}).get("manifest_sha256") != (
        CONTRACT_MANIFEST_SHA256
    ):
        raise ValueError("contracts manifest canonical hash mismatch")
    if sha256_file(manifest_path) != CONTRACT_MANIFEST_FILE_SHA256:
        raise ValueError("contracts manifest physical hash mismatch")
    manifest_errors = verify_manifest(contracts_root)
    if manifest_errors:
        raise ValueError(
            "contracts manifest verification failed: " + "; ".join(manifest_errors)
        )

    gate_policy = load_verified_json_artifact(
        gate_policy_path, expected_self_sha256=GATE_POLICY_SHA256
    )
    if gate_policy.physical_sha256 != receipt.get("gate_policy_file_sha256"):
        raise ValueError("contracts gate policy physical hash mismatch")
    if sha256_file(feature_registry_path) != receipt.get(
        "feature_contract_file_sha256"
    ):
        raise ValueError("contracts feature registry physical hash mismatch")

    tag_commit = _git(repository, "rev-parse", f"{AUTHORITY_TAG}^{{commit}}")
    tag_object = _git(repository, "rev-parse", AUTHORITY_TAG)
    if tag_commit != AUTHORITY_COMMIT:
        raise ValueError("contracts authority tag commit mismatch")
    if tag_object != AUTHORITY_TAG_OBJECT:
        raise ValueError("contracts authority tag object mismatch")
    drift = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            f"{AUTHORITY_TAG}..HEAD",
            "--",
            "terminology_contracts_v1",
        ],
        cwd=repository,
        check=False,
    ).returncode
    if drift != 0:
        raise ValueError("contracts tree differs from immutable authority tag")

    return {
        "schema_id": "VietnameseAttestationAuthorityVerificationReportV1",
        "schema_version": "1.0.0",
        "status": "PASS",
        "authority_tag": AUTHORITY_TAG,
        "authority_tag_object": AUTHORITY_TAG_OBJECT,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_version": "1.1.0",
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "manifest_file_sha256": CONTRACT_MANIFEST_FILE_SHA256,
        "gate_policy_artifact_sha256": GATE_POLICY_SHA256,
        "receipt_self_sha256": AUTHORITY_RECEIPT_SELF_SHA256,
        "receipt_physical_sha256": AUTHORITY_RECEIPT_PHYSICAL_SHA256,
        "contracts_tree_drift_count": 0,
        "provider_call_count": 0,
    }


def _git(repository: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"cannot verify Git authority: {' '.join(args)}") from exc


__all__ = [
    "AUTHORITY_COMMIT",
    "AUTHORITY_TAG",
    "AUTHORITY_TAG_OBJECT",
    "CONTRACT_MANIFEST_SHA256",
    "GATE_POLICY_SHA256",
    "verify_contract_authority",
]
