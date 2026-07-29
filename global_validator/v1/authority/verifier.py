from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import (
    canonical_sha256,
    load_verified_json_artifact,
    sha256_file,
)
from terminology_contracts.manifest import verify_manifest

from ..errors import AuthorityVerificationError
from ..jsonio import assert_strict_json_file, load_json_object
from .publication import (
    AUTHORITY_COMMIT,
    AUTHORITY_CONTRACT_TREE_OID,
    AUTHORITY_SCHEMA_ID,
    AUTHORITY_TAG,
    AUTHORITY_TAG_OBJECT_OID,
    CONTRACT_VERSION,
    R2_CONTRACT_TREE_OID,
    R2_PUBLICATION_COMMIT,
    load_active_r2_receipt,
    verify_r2_publication,
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
    receipt = load_active_r2_receipt(receipt_path)
    receipt_integrity_mode = "CANONICAL_SELF_HASH"
    warnings: tuple[str, ...] = ()
    _expect(receipt, "schema_id", AUTHORITY_SCHEMA_ID)
    _expect(receipt, "contract_version", CONTRACT_VERSION)
    _expect(receipt, "feature_registry_version", CONTRACT_VERSION)
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
        expected_self_sha256=receipt.get("gate_policy_self_sha256"),
    )
    if gate_policy.physical_sha256 != receipt.get("gate_policy_file_sha256"):
        raise AuthorityVerificationError("gate policy physical SHA-256 mismatch")
    feature_registry = _strict_object(feature_registry_path)
    _expect(
        feature_registry,
        "registry_id",
        "TerminologyFeatureContractRegistryV1_1",
    )
    _expect(feature_registry, "registry_version", CONTRACT_VERSION)
    if canonical_sha256(feature_registry) != receipt.get(
        "feature_registry_canonical_sha256"
    ):
        raise AuthorityVerificationError("feature registry canonical SHA-256 mismatch")
    if sha256_file(feature_registry_path) != receipt.get(
        "feature_registry_file_sha256"
    ):
        raise AuthorityVerificationError("feature registry physical SHA-256 mismatch")

    verify_r2_publication(receipt, contracts_root)
    manifest_errors = verify_manifest(contracts_root)
    if manifest_errors:
        raise AuthorityVerificationError(
            "contracts manifest verification failed: " + "; ".join(manifest_errors)
        )
    if repository_root is not None:
        _verify_git_authority(repository_root.resolve(), receipt)

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


def _verify_git_authority(
    repository_root: Path, receipt: dict[str, Any]
) -> None:
    try:
        tag_type = _git_output(repository_root, "cat-file", "-t", f"refs/tags/{AUTHORITY_TAG}")
        tag_object = _git_output(repository_root, "rev-parse", f"refs/tags/{AUTHORITY_TAG}")
        tag_commit = _git_output(repository_root, "rev-parse", f"{AUTHORITY_TAG}^{{commit}}")
        tag_tree = _git_output(
            repository_root,
            "rev-parse",
            f"{AUTHORITY_TAG}:terminology_contracts_v1",
        )
        publication_type = _git_output(
            repository_root, "cat-file", "-t", R2_PUBLICATION_COMMIT
        )
        publication_ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", R2_PUBLICATION_COMMIT, "HEAD"],
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        publication_tree = _git_output(
            repository_root,
            "rev-parse",
            f"{R2_PUBLICATION_COMMIT}:terminology_contracts_v1",
        )
        head_tree = _git_output(
            repository_root, "rev-parse", "HEAD:terminology_contracts_v1"
        )
        worktree_status = _git_output(
            repository_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            "terminology_contracts_v1",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuthorityVerificationError(f"cannot verify Git authority: {exc}") from exc
    if tag_type != "tag" or tag_object != AUTHORITY_TAG_OBJECT_OID:
        raise AuthorityVerificationError("authority annotated tag object mismatch")
    if tag_commit != AUTHORITY_COMMIT:
        raise AuthorityVerificationError("authority tag does not resolve to receipt commit")
    if tag_tree != AUTHORITY_CONTRACT_TREE_OID or tag_tree != receipt.get(
        "contract_tree_git_oid"
    ):
        raise AuthorityVerificationError("authority tag contract tree binding mismatch")
    if publication_type != "commit" or publication_ancestor != 0:
        raise AuthorityVerificationError(
            "reviewed R2 publication commit is not an ancestor of runtime HEAD"
        )
    if publication_tree != R2_CONTRACT_TREE_OID:
        raise AuthorityVerificationError("reviewed R2 publication tree moved")
    if head_tree != R2_CONTRACT_TREE_OID:
        raise AuthorityVerificationError(
            "contracts tree differs from exact reviewed R2 publication"
        )
    if worktree_status:
        raise AuthorityVerificationError(
            "contracts working tree contains unreviewed mutation"
        )


def _git_output(repository_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
