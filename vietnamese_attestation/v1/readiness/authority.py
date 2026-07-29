"""Fail-closed verification of the immutable Contracts V1.1 R2 authority."""

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

from .jsonio import load_strict_json_object, reject_link


AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
AUTHORITY_TAG_OBJECT = "1a8c00d12f100145a276cd8304440ff0a7e8d2a1"
AUTHORITY_CONTRACTS_TREE_GIT_OID = "d6386c4c4d19ba2aad982a519b9b59ecfd2213c9"

R2_PUBLICATION_COMMIT = "282409c470049760904fa16de4c67d711b5fcd00"
R2_CONTRACTS_TREE_GIT_OID = "938bca1f9c60596ef9403a43f0355476ad42afef"
R2_RELEASE_TREE_GIT_OID = "69fefe7b5728a967a740ead747009aec0a12abb7"
R2_RECEIPT_RELATIVE_PATH = (
    "terminology_contracts_v1/release/v1.1.0-final/"
    "contracts_v1_1_0_authority_receipt_r2.json"
)
AUTHORITY_RECEIPT_SELF_SHA256 = (
    "a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618"
)
AUTHORITY_RECEIPT_PHYSICAL_SHA256 = (
    "acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79"
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

R2_FINAL_ROOT = "terminology_contracts_v1/release/v1.1.0-final"
R2_FINAL_AUDIT_SELF_SHA256 = (
    "e8cec2de12224f816ca7eb6c8b38d75f2b07f6d99f44c019caae44f45c961202"
)
R2_FINAL_AUDIT_PHYSICAL_SHA256 = (
    "21a36752d0e244449c650221a0a89c73376526efd88a3b56f62d0e0c68eedfd3"
)
R2_FINAL_MANIFEST_SELF_SHA256 = (
    "d64b82abb2b74bf7477a1c9f740c8d6a3bc0155dae8d3476b484fee239ad7522"
)
R2_FINAL_MANIFEST_PHYSICAL_SHA256 = (
    "bd9d4c10908bdb951eaebb8c139afe7a09b198bd6422ef7626dc728c6ea9ccb7"
)
R2_FINAL_ZIP_SHA256 = (
    "2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471"
)
R2_FINAL_ZIP_SIDECAR_PHYSICAL_SHA256 = (
    "aac6d21f8df4edaf1fda8870c55d713b6d0baccee946371b211f2e23cd324f80"
)
R2_FINAL_CHECKSUMS_PHYSICAL_SHA256 = (
    "295a93ea167c0cbb590e6d4cf5894f18e48782aa942dbe424855c19cb0c52196"
)


def verify_contract_authority(
    *, repository_root: str | Path, receipt_path: str | Path
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    canonical_receipt = (repository / R2_RECEIPT_RELATIVE_PATH).resolve(
        strict=True
    )
    supplied = Path(receipt_path)
    if not supplied.is_absolute():
        supplied = repository / supplied
    receipt_file = supplied.resolve(strict=True)
    if receipt_file != canonical_receipt:
        raise ValueError("canonical in-repo contracts authority R2 receipt required")
    reject_link(receipt_file)

    receipt = load_strict_json_object(receipt_file)
    verify_self_hash(receipt, path=str(receipt_file))
    expected = {
        "schema_id": "TerminologyContractsAuthorityReceiptV1",
        "schema_version": "1.0.0",
        "receipt_revision": 2,
        "contract_version": "1.1.0",
        "authority_status": "SEALED",
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "authority_tag_object_oid": AUTHORITY_TAG_OBJECT,
        "contract_tree_git_oid": AUTHORITY_CONTRACTS_TREE_GIT_OID,
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "manifest_file_sha256": CONTRACT_MANIFEST_FILE_SHA256,
        "gate_policy_self_sha256": GATE_POLICY_SHA256,
        "final_release_audit_self_sha256": R2_FINAL_AUDIT_SELF_SHA256,
        "final_release_audit_physical_sha256": (
            R2_FINAL_AUDIT_PHYSICAL_SHA256
        ),
        "final_release_zip_sha256": R2_FINAL_ZIP_SHA256,
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise ValueError(f"contracts authority R2 {field} mismatch")
    if receipt["integrity"]["self_sha256"] != AUTHORITY_RECEIPT_SELF_SHA256:
        raise ValueError("contracts authority R2 receipt canonical hash mismatch")
    if sha256_file(receipt_file) != AUTHORITY_RECEIPT_PHYSICAL_SHA256:
        raise ValueError("contracts authority R2 receipt physical hash mismatch")

    _verify_git_bindings(repository)
    _verify_contract_files(repository, receipt)
    _verify_final_release(repository, receipt)

    return {
        "schema_id": "VietnameseAttestationAuthorityVerificationReportV1",
        "schema_version": "1.0.0",
        "status": "PASS",
        "authority_tag": AUTHORITY_TAG,
        "authority_tag_object": AUTHORITY_TAG_OBJECT,
        "authority_commit": AUTHORITY_COMMIT,
        "authority_receipt_revision": 2,
        "r2_publication_commit": R2_PUBLICATION_COMMIT,
        "contract_version": "1.1.0",
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "manifest_file_sha256": CONTRACT_MANIFEST_FILE_SHA256,
        "gate_policy_artifact_sha256": GATE_POLICY_SHA256,
        "receipt_self_sha256": AUTHORITY_RECEIPT_SELF_SHA256,
        "receipt_physical_sha256": AUTHORITY_RECEIPT_PHYSICAL_SHA256,
        "authority_contracts_tree_git_oid": AUTHORITY_CONTRACTS_TREE_GIT_OID,
        "r2_contracts_tree_git_oid": R2_CONTRACTS_TREE_GIT_OID,
        "r2_release_tree_git_oid": R2_RELEASE_TREE_GIT_OID,
        "final_release_audit_self_sha256": R2_FINAL_AUDIT_SELF_SHA256,
        "final_release_audit_physical_sha256": (
            R2_FINAL_AUDIT_PHYSICAL_SHA256
        ),
        "final_release_zip_sha256": R2_FINAL_ZIP_SHA256,
        "release_delta_mode": "PINNED_R2_RELEASE_ONLY",
        "contracts_tree_drift_count": 0,
        "provider_call_count": 0,
    }


def _verify_git_bindings(repository: Path) -> None:
    tag_commit = _git(repository, "rev-parse", f"{AUTHORITY_TAG}^{{commit}}")
    tag_object = _git(repository, "rev-parse", AUTHORITY_TAG)
    if tag_commit != AUTHORITY_COMMIT:
        raise ValueError("contracts authority tag commit mismatch")
    if tag_object != AUTHORITY_TAG_OBJECT:
        raise ValueError("contracts authority tag object mismatch")
    if _git(
        repository, "rev-parse", f"{AUTHORITY_TAG}:terminology_contracts_v1"
    ) != AUTHORITY_CONTRACTS_TREE_GIT_OID:
        raise ValueError("contracts tagged source tree mismatch")

    publication_commit = _git(
        repository, "rev-parse", f"{R2_PUBLICATION_COMMIT}^{{commit}}"
    )
    if publication_commit != R2_PUBLICATION_COMMIT:
        raise ValueError("contracts R2 publication commit mismatch")
    if _git(
        repository,
        "rev-parse",
        f"{R2_PUBLICATION_COMMIT}:terminology_contracts_v1",
    ) != R2_CONTRACTS_TREE_GIT_OID:
        raise ValueError("contracts R2 publication tree mismatch")

    current_contracts_tree = _git(
        repository, "rev-parse", "HEAD:terminology_contracts_v1"
    )
    current_release_tree = _git(
        repository, "rev-parse", "HEAD:terminology_contracts_v1/release"
    )
    if current_contracts_tree != R2_CONTRACTS_TREE_GIT_OID:
        raise ValueError("contracts tree differs from reviewed R2 publication")
    if current_release_tree != R2_RELEASE_TREE_GIT_OID:
        raise ValueError("contracts release tree differs from reviewed R2 publication")

    status = _git(
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        "terminology_contracts_v1",
    )
    if status:
        raise ValueError("contracts worktree contains unreviewed physical drift")


def _verify_contract_files(repository: Path, receipt: dict[str, Any]) -> None:
    contracts_root = repository / "terminology_contracts_v1"
    manifest_path = contracts_root / "manifest.json"
    gate_policy_path = contracts_root / "policies" / "gate_policy_v1.0.0.json"
    feature_registry_path = (
        contracts_root / "registries" / "feature_contract_v1.1.0.json"
    )
    schema_dir = contracts_root / "schemas" / "v1.1.0"
    for path in (manifest_path, gate_policy_path, feature_registry_path):
        reject_link(path)
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
        "feature_registry_file_sha256"
    ):
        raise ValueError("contracts feature registry physical hash mismatch")


def _verify_final_release(repository: Path, receipt: dict[str, Any]) -> None:
    final_root = repository / R2_FINAL_ROOT
    audit_path = final_root / "final_release_audit.json"
    release_manifest_path = final_root / "release_manifest.json"
    zip_path = final_root / "terminology_contracts_v1_1_0_final.zip"
    zip_sidecar_path = final_root / "terminology_contracts_v1_1_0_final.zip.sha256"
    checksums_path = final_root / "CHECKSUMS.sha256"
    for path in (
        audit_path,
        release_manifest_path,
        zip_path,
        zip_sidecar_path,
        checksums_path,
    ):
        reject_link(path)
        if not path.is_file():
            raise ValueError(f"contracts R2 final artifact is missing: {path}")

    audit = load_strict_json_object(audit_path)
    verify_self_hash(audit, path=str(audit_path))
    audit_expected = {
        "schema_id": "TerminologyContractsAuthorityMaintenanceReleaseAuditV1",
        "authority_commit": AUTHORITY_COMMIT,
        "authority_tag": AUTHORITY_TAG,
        "authority_tag_object_oid": AUTHORITY_TAG_OBJECT,
        "contract_tree_git_oid": AUTHORITY_CONTRACTS_TREE_GIT_OID,
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "gate_policy_self_sha256": GATE_POLICY_SHA256,
        "release_zip_sha256": R2_FINAL_ZIP_SHA256,
        "release_zip_byte_identical_to_approved_rc4": True,
        "test_result": "PASS",
        "external_api_calls": 0,
    }
    for field, value in audit_expected.items():
        if audit.get(field) != value:
            raise ValueError(f"contracts R2 final audit {field} mismatch")
    if audit["integrity"]["self_sha256"] != R2_FINAL_AUDIT_SELF_SHA256:
        raise ValueError("contracts R2 final audit canonical hash mismatch")
    if sha256_file(audit_path) != R2_FINAL_AUDIT_PHYSICAL_SHA256:
        raise ValueError("contracts R2 final audit physical hash mismatch")

    release_manifest = load_strict_json_object(release_manifest_path)
    verify_self_hash(release_manifest, path=str(release_manifest_path))
    if release_manifest.get("schema_id") != (
        "TerminologyContractsAuthorityMaintenanceManifestV1"
    ):
        raise ValueError("contracts R2 final manifest schema mismatch")
    if release_manifest["integrity"]["self_sha256"] != (
        R2_FINAL_MANIFEST_SELF_SHA256
    ):
        raise ValueError("contracts R2 final manifest canonical hash mismatch")
    if sha256_file(release_manifest_path) != R2_FINAL_MANIFEST_PHYSICAL_SHA256:
        raise ValueError("contracts R2 final manifest physical hash mismatch")

    if sha256_file(zip_path) != R2_FINAL_ZIP_SHA256:
        raise ValueError("contracts R2 final ZIP physical hash mismatch")
    if receipt.get("final_release_zip_sha256") != R2_FINAL_ZIP_SHA256:
        raise ValueError("contracts R2 receipt final ZIP binding mismatch")
    if sha256_file(zip_sidecar_path) != R2_FINAL_ZIP_SIDECAR_PHYSICAL_SHA256:
        raise ValueError("contracts R2 final ZIP sidecar physical hash mismatch")
    expected_sidecar = (
        f"{R2_FINAL_ZIP_SHA256}  terminology_contracts_v1_1_0_final.zip\n"
    )
    if zip_sidecar_path.read_text(encoding="ascii") != expected_sidecar:
        raise ValueError("contracts R2 final ZIP sidecar content mismatch")
    if sha256_file(checksums_path) != R2_FINAL_CHECKSUMS_PHYSICAL_SHA256:
        raise ValueError("contracts R2 final checksums physical hash mismatch")


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
    "AUTHORITY_RECEIPT_PHYSICAL_SHA256",
    "AUTHORITY_RECEIPT_SELF_SHA256",
    "AUTHORITY_TAG",
    "AUTHORITY_TAG_OBJECT",
    "CONTRACT_MANIFEST_SHA256",
    "GATE_POLICY_SHA256",
    "R2_PUBLICATION_COMMIT",
    "R2_RECEIPT_RELATIVE_PATH",
    "verify_contract_authority",
]
