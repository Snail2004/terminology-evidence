from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from terminology_contracts.integrity import (
    safe_relative_path,
    sha256_file,
    verify_self_hash,
)

from ..errors import AuthorityVerificationError
from ..jsonio import load_json_object

AUTHORITY_SCHEMA_ID = "TerminologyContractsAuthorityReceiptV1"
AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_TAG_OBJECT_OID = "1a8c00d12f100145a276cd8304440ff0a7e8d2a1"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
AUTHORITY_CONTRACT_TREE_OID = "d6386c4c4d19ba2aad982a519b9b59ecfd2213c9"
CONTRACT_VERSION = "1.1.0"

R2_PUBLICATION_COMMIT = "282409c470049760904fa16de4c67d711b5fcd00"
R2_CONTRACT_TREE_OID = "938bca1f9c60596ef9403a43f0355476ad42afef"
R2_RECEIPT_RELATIVE_PATH = (
    "release/v1.1.0-final/contracts_v1_1_0_authority_receipt_r2.json"
)
R2_RECEIPT_SELF_SHA256 = (
    "a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618"
)
R2_RECEIPT_PHYSICAL_SHA256 = (
    "acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79"
)
R2_RELEASE_MANIFEST_SELF_SHA256 = (
    "d64b82abb2b74bf7477a1c9f740c8d6a3bc0155dae8d3476b484fee239ad7522"
)
R2_RELEASE_MANIFEST_PHYSICAL_SHA256 = (
    "bd9d4c10908bdb951eaebb8c139afe7a09b198bd6422ef7626dc728c6ea9ccb7"
)
R2_RELEASE_CHECKSUMS_PHYSICAL_SHA256 = (
    "295a93ea167c0cbb590e6d4cf5894f18e48782aa942dbe424855c19cb0c52196"
)
R2_FINAL_ZIP_SHA256 = (
    "2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471"
)
R2_FINAL_AUDIT_SELF_SHA256 = (
    "e8cec2de12224f816ca7eb6c8b38d75f2b07f6d99f44c019caae44f45c961202"
)
R2_FINAL_AUDIT_PHYSICAL_SHA256 = (
    "21a36752d0e244449c650221a0a89c73376526efd88a3b56f62d0e0c68eedfd3"
)
R2_REVIEWED_CONTENT_COMMIT = "36e041abcaa0a8a34ab892ae094b0b3d9c3af2f4"
R2_REVIEW_EVIDENCE_COMMIT = "147080746afee4f0059d9e51617097f7e383a8d1"

_RECEIPT_FIELDS = frozenset(
    {
        "authority_commit",
        "authority_status",
        "authority_tag",
        "authority_tag_object_oid",
        "canonical_main_observed_commit",
        "contract_root",
        "contract_tree_git_oid",
        "contract_version",
        "feature_registry_canonical_sha256",
        "feature_registry_file_sha256",
        "feature_registry_path",
        "feature_registry_version",
        "final_release_audit_path",
        "final_release_audit_physical_sha256",
        "final_release_audit_self_sha256",
        "final_release_checksum_path",
        "final_release_path",
        "final_release_zip_sha256",
        "gate_policy_file_sha256",
        "gate_policy_path",
        "gate_policy_self_sha256",
        "integrity",
        "issued_at",
        "manifest_file_sha256",
        "manifest_path",
        "manifest_sha256",
        "publication_status",
        "receipt_revision",
        "review_evidence_commit",
        "reviewed_content_commit",
        "schema_id",
        "schema_version",
        "supersedes_receipts",
    }
)
_SUPERSEDED_FIELDS = frozenset(
    {
        "canonical_self_sha256",
        "declared_self_sha256",
        "path",
        "physical_sha256",
        "status",
    }
)


@dataclass(frozen=True)
class VerifiedR2Publication:
    final_dir: Path
    release_manifest_path: Path
    checksums_path: Path
    final_zip_path: Path
    final_audit_path: Path


def load_active_r2_receipt(path: Path) -> dict[str, Any]:
    receipt = _strict_object(path, label="authority receipt")
    _verify_self_hash(receipt, label="authority receipt")
    _require_exact_fields(receipt, _RECEIPT_FIELDS, label="authority receipt")

    _expect(receipt, "schema_id", AUTHORITY_SCHEMA_ID)
    _expect(receipt, "schema_version", "1.0.0")
    _expect(receipt, "receipt_revision", 2)
    _expect(receipt, "authority_status", "SEALED")
    _expect(receipt, "publication_status", "PENDING_INDEPENDENT_REVIEW")
    _expect(receipt, "contract_version", CONTRACT_VERSION)
    _expect(receipt, "contract_root", "terminology_contracts_v1")
    _expect(receipt, "authority_tag", AUTHORITY_TAG)
    _expect(receipt, "authority_tag_object_oid", AUTHORITY_TAG_OBJECT_OID)
    _expect(receipt, "authority_commit", AUTHORITY_COMMIT)
    _expect(receipt, "contract_tree_git_oid", AUTHORITY_CONTRACT_TREE_OID)
    _expect(receipt, "reviewed_content_commit", R2_REVIEWED_CONTENT_COMMIT)
    _expect(receipt, "review_evidence_commit", R2_REVIEW_EVIDENCE_COMMIT)
    _expect(receipt, "manifest_path", "manifest.json")
    _expect(receipt, "gate_policy_path", "policies/gate_policy_v1.0.0.json")
    _expect(
        receipt,
        "feature_registry_path",
        "registries/feature_contract_v1.1.0.json",
    )
    _expect(receipt, "feature_registry_version", CONTRACT_VERSION)
    _expect(
        receipt,
        "final_release_path",
        "release/v1.1.0-final/terminology_contracts_v1_1_0_final.zip",
    )
    _expect(
        receipt,
        "final_release_checksum_path",
        "release/v1.1.0-final/terminology_contracts_v1_1_0_final.zip.sha256",
    )
    _expect(
        receipt,
        "final_release_audit_path",
        "release/v1.1.0-final/final_release_audit.json",
    )
    _expect(receipt, "final_release_zip_sha256", R2_FINAL_ZIP_SHA256)
    _expect(receipt, "final_release_audit_self_sha256", R2_FINAL_AUDIT_SELF_SHA256)
    _expect(
        receipt,
        "final_release_audit_physical_sha256",
        R2_FINAL_AUDIT_PHYSICAL_SHA256,
    )

    integrity = receipt.get("integrity")
    _require_exact_fields(integrity, {"self_sha256"}, label="receipt integrity")
    _expect(integrity, "self_sha256", R2_RECEIPT_SELF_SHA256)
    if _sha256(path, label="authority receipt") != R2_RECEIPT_PHYSICAL_SHA256:
        raise AuthorityVerificationError(
            "authority receipt physical SHA-256 differs from active R2 receipt"
        )
    _verify_superseded_receipt_rows(receipt)
    return receipt


def verify_r2_publication(
    receipt: Mapping[str, Any], contracts_root: Path
) -> VerifiedR2Publication:
    final_dir = contracts_root / "release" / "v1.1.0-final"
    canonical_receipt = contracts_root / R2_RECEIPT_RELATIVE_PATH
    receipt_checksum = final_dir / "contracts_v1_1_0_authority_receipt_r2.json.sha256"
    release_manifest_path = final_dir / "release_manifest.json"
    checksums_path = final_dir / "CHECKSUMS.sha256"
    required = (
        canonical_receipt,
        receipt_checksum,
        release_manifest_path,
        checksums_path,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise AuthorityVerificationError(
            "R2 authority publication is incomplete: " + ", ".join(missing)
        )

    if _sha256(canonical_receipt, label="canonical R2 receipt") != (
        R2_RECEIPT_PHYSICAL_SHA256
    ):
        raise AuthorityVerificationError("canonical in-repo R2 receipt hash mismatch")
    _verify_checksum_sidecar(
        receipt_checksum,
        expected_name=canonical_receipt.name,
        expected_sha256=R2_RECEIPT_PHYSICAL_SHA256,
    )

    release_manifest = _strict_object(
        release_manifest_path, label="R2 release manifest"
    )
    _verify_self_hash(release_manifest, label="R2 release manifest")
    _expect(
        release_manifest,
        "schema_id",
        "TerminologyContractsAuthorityMaintenanceManifestV1",
    )
    _expect(release_manifest, "contract_version", CONTRACT_VERSION)
    _expect(release_manifest, "authority_tag", AUTHORITY_TAG)
    _expect(
        release_manifest.get("integrity"),
        "self_sha256",
        R2_RELEASE_MANIFEST_SELF_SHA256,
    )
    if _sha256(release_manifest_path, label="R2 release manifest") != (
        R2_RELEASE_MANIFEST_PHYSICAL_SHA256
    ):
        raise AuthorityVerificationError("R2 release manifest physical hash mismatch")

    expected_checksum_lines = _verify_release_file_set(final_dir, release_manifest)
    expected_checksum_lines.append(
        f"{R2_RELEASE_MANIFEST_PHYSICAL_SHA256}  release_manifest.json"
    )
    if _sha256(checksums_path, label="R2 CHECKSUMS.sha256") != (
        R2_RELEASE_CHECKSUMS_PHYSICAL_SHA256
    ):
        raise AuthorityVerificationError("R2 CHECKSUMS.sha256 physical hash mismatch")
    try:
        actual_checksum_lines = checksums_path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise AuthorityVerificationError(
            f"cannot read R2 CHECKSUMS.sha256: {exc}"
        ) from exc
    if actual_checksum_lines != sorted(expected_checksum_lines):
        raise AuthorityVerificationError("R2 CHECKSUMS.sha256 content mismatch")

    final_zip_path = contracts_root / str(receipt["final_release_path"])
    final_zip_checksum = contracts_root / str(receipt["final_release_checksum_path"])
    if _sha256(final_zip_path, label="R2 final ZIP") != R2_FINAL_ZIP_SHA256:
        raise AuthorityVerificationError("R2 final release ZIP hash mismatch")
    _verify_checksum_sidecar(
        final_zip_checksum,
        expected_name=final_zip_path.name,
        expected_sha256=R2_FINAL_ZIP_SHA256,
    )

    final_audit_path = contracts_root / str(receipt["final_release_audit_path"])
    final_audit = _strict_object(final_audit_path, label="R2 final release audit")
    _verify_self_hash(final_audit, label="R2 final release audit")
    if _sha256(final_audit_path, label="R2 final release audit") != (
        R2_FINAL_AUDIT_PHYSICAL_SHA256
    ):
        raise AuthorityVerificationError("R2 final release audit physical hash mismatch")
    _verify_final_audit(final_audit, receipt)

    return VerifiedR2Publication(
        final_dir=final_dir,
        release_manifest_path=release_manifest_path,
        checksums_path=checksums_path,
        final_zip_path=final_zip_path,
        final_audit_path=final_audit_path,
    )


def _verify_release_file_set(
    final_dir: Path, release_manifest: Mapping[str, Any]
) -> list[str]:
    rows = release_manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise AuthorityVerificationError("R2 release manifest files must be nonempty")
    expected_paths: set[str] = set()
    checksum_lines: list[str] = []
    for index, row in enumerate(rows):
        label = f"R2 release manifest files[{index}]"
        _require_exact_fields(row, {"path", "sha256", "size_bytes"}, label=label)
        try:
            relative = safe_relative_path(row.get("path"), field=f"{label}.path")
        except ValueError as exc:
            raise AuthorityVerificationError(str(exc)) from exc
        if relative in expected_paths:
            raise AuthorityVerificationError("duplicate R2 release manifest path")
        expected_paths.add(relative)
        path = final_dir / Path(relative)
        if not path.is_file():
            raise AuthorityVerificationError(f"R2 release file is missing: {relative}")
        expected_hash = row.get("sha256")
        if _sha256(path, label=f"R2 release file {relative}") != expected_hash:
            raise AuthorityVerificationError(
                f"R2 release file hash mismatch: {relative}"
            )
        try:
            actual_size = path.stat().st_size
        except OSError as exc:
            raise AuthorityVerificationError(
                f"cannot stat R2 release file {relative}: {exc}"
            ) from exc
        if actual_size != row.get("size_bytes"):
            raise AuthorityVerificationError(
                f"R2 release file size mismatch: {relative}"
            )
        checksum_lines.append(f"{expected_hash}  {relative}")
    actual_paths = {
        path.relative_to(final_dir).as_posix()
        for path in final_dir.rglob("*")
        if path.is_file()
        and path.name not in {"release_manifest.json", "CHECKSUMS.sha256"}
    }
    if actual_paths != expected_paths:
        raise AuthorityVerificationError(
            "R2 release file-set mismatch: "
            f"missing={sorted(expected_paths - actual_paths)}, "
            f"extra={sorted(actual_paths - expected_paths)}"
        )
    return checksum_lines


def _verify_final_audit(
    audit: Mapping[str, Any], receipt: Mapping[str, Any]
) -> None:
    expected = {
        "schema_id": "TerminologyContractsAuthorityMaintenanceReleaseAuditV1",
        "release_channel": "v1.1.0-final-authority-r2",
        "source_ref": AUTHORITY_TAG,
        "authority_tag": AUTHORITY_TAG,
        "authority_tag_object_oid": AUTHORITY_TAG_OBJECT_OID,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_tree_git_oid": AUTHORITY_CONTRACT_TREE_OID,
        "contract_version": CONTRACT_VERSION,
        "manifest_sha256": receipt.get("manifest_sha256"),
        "manifest_file_sha256": receipt.get("manifest_file_sha256"),
        "gate_policy_self_sha256": receipt.get("gate_policy_self_sha256"),
        "gate_policy_file_sha256": receipt.get("gate_policy_file_sha256"),
        "feature_registry_canonical_sha256": receipt.get(
            "feature_registry_canonical_sha256"
        ),
        "feature_registry_file_sha256": receipt.get(
            "feature_registry_file_sha256"
        ),
        "feature_registry_version": CONTRACT_VERSION,
        "release_zip_sha256": R2_FINAL_ZIP_SHA256,
        "release_zip_byte_identical_to_approved_rc4": True,
        "test_result": "PASS",
        "test_count": 145,
        "test_failures": 0,
        "test_errors": 0,
        "test_skipped": 0,
        "external_api_calls": 0,
        "credential_scan_result": "PASS",
        "ownership_scan_result": "PASS",
        "static_scan_result": "PASS",
        "historical_receipts_preserved": 2,
    }
    for field, expected_value in expected.items():
        _expect(audit, field, expected_value)
    _expect(audit.get("integrity"), "self_sha256", R2_FINAL_AUDIT_SELF_SHA256)


def _verify_superseded_receipt_rows(receipt: Mapping[str, Any]) -> None:
    rows = receipt.get("supersedes_receipts")
    if not isinstance(rows, list) or len(rows) != 2:
        raise AuthorityVerificationError(
            "R2 receipt must bind exactly two superseded R1 receipts"
        )
    expected_paths = {
        "release/v1.1.0-final/history/contracts_v1_1_0_authority_receipt_r1_invalid.json",
        "release/v1.1.0-final/history/contracts_v1_1_0_authority_receipt_r1_resealed.json",
    }
    actual_paths: set[str] = set()
    for index, row in enumerate(rows):
        label = f"supersedes_receipts[{index}]"
        _require_exact_fields(row, _SUPERSEDED_FIELDS, label=label)
        _expect(row, "status", "SUPERSEDED_BY_RECEIPT_R2")
        try:
            path = safe_relative_path(row.get("path"), field=f"{label}.path")
        except ValueError as exc:
            raise AuthorityVerificationError(str(exc)) from exc
        actual_paths.add(path)
    if actual_paths != expected_paths:
        raise AuthorityVerificationError("R2 superseded receipt bindings mismatch")


def _verify_checksum_sidecar(
    path: Path, *, expected_name: str, expected_sha256: str
) -> None:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise AuthorityVerificationError(f"cannot read checksum file {path}: {exc}") from exc
    if lines != [f"{expected_sha256}  {expected_name}"]:
        raise AuthorityVerificationError(f"checksum sidecar mismatch: {path}")


def _strict_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        return load_json_object(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise AuthorityVerificationError(f"cannot load {label}: {exc}") from exc


def _verify_self_hash(value: Mapping[str, Any], *, label: str) -> None:
    try:
        verify_self_hash(value, path=label)
    except ValueError as exc:
        raise AuthorityVerificationError(str(exc)) from exc


def _sha256(path: Path, *, label: str) -> str:
    try:
        return sha256_file(path)
    except (OSError, ValueError) as exc:
        raise AuthorityVerificationError(f"cannot hash {label}: {exc}") from exc


def _require_exact_fields(
    value: Any, expected: set[str] | frozenset[str], *, label: str
) -> None:
    if not isinstance(value, Mapping):
        raise AuthorityVerificationError(f"{label} must be an object")
    actual = set(value)
    if actual != set(expected):
        raise AuthorityVerificationError(
            f"{label} fields mismatch: missing={sorted(set(expected) - actual)}, "
            f"extra={sorted(actual - set(expected))}"
        )


def _expect(value: Any, field: str, expected: Any) -> None:
    actual = value.get(field) if isinstance(value, Mapping) else None
    if actual != expected:
        raise AuthorityVerificationError(
            f"authority {field} mismatch: expected {expected!r}, got {actual!r}"
        )
