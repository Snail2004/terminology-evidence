from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from authority_common import (
    APPROVED_FINAL_ZIP_SHA256,
    AUTHORITY_COMMIT,
    AUTHORITY_TAG,
    AUTHORITY_TAG_OBJECT_OID,
    CONTRACT_ROOT,
    CONTRACT_VERSION,
    FINAL_RELEASE_DIR,
    GATE_POLICY_SELF_SHA256,
    MANIFEST_SELF_SHA256,
    RECEIPT_NAME,
    REVIEWED_CONTENT_COMMIT,
    REVIEW_EVIDENCE_COMMIT,
    AuthorityError,
    calculate_self_sha256,
    canonical_sha256,
    git,
    read_checksum,
    read_strict_json,
    require_git_oid,
    require_sha256,
    resolve_tag_identity,
    safe_relative_path,
    seal_self_hash,
    sha256_file,
    strict_json_loads,
    verify_self_hash,
    verify_tagged_feature_registry,
    verify_tagged_gate_policy,
    verify_tagged_manifest,
    verify_zip_against_tag,
    write_json,
)


RECEIPT_FIELDS = {
    "schema_id",
    "schema_version",
    "receipt_revision",
    "authority_status",
    "publication_status",
    "contract_version",
    "authority_tag",
    "authority_tag_object_oid",
    "authority_commit",
    "canonical_main_observed_commit",
    "contract_root",
    "contract_tree_git_oid",
    "manifest_path",
    "manifest_sha256",
    "manifest_file_sha256",
    "final_release_path",
    "final_release_checksum_path",
    "final_release_zip_sha256",
    "final_release_audit_path",
    "final_release_audit_self_sha256",
    "final_release_audit_physical_sha256",
    "gate_policy_path",
    "gate_policy_self_sha256",
    "gate_policy_file_sha256",
    "feature_registry_path",
    "feature_registry_version",
    "feature_registry_canonical_sha256",
    "feature_registry_file_sha256",
    "reviewed_content_commit",
    "review_evidence_commit",
    "supersedes_receipts",
    "issued_at",
    "integrity",
}

SUPERSEDED_FIELDS = {
    "path",
    "status",
    "declared_self_sha256",
    "canonical_self_sha256",
    "physical_sha256",
}

STALE_ACTIVE_FILES = (
    "release/terminology_contracts_v1_1.zip",
    "release/terminology_contracts_v1_1.zip.sha256",
    "release/terminology_contracts_v1_1_audit.json",
    "release/junit.xml",
    "release/commands.txt",
)


def _require_exact_fields(payload: Mapping[str, Any], expected: set[str], *, label: str) -> None:
    actual = set(payload)
    if actual != expected:
        raise AuthorityError(
            f"{label}: unexpected field drift: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _resolve_distribution_path(
    distribution_root: Path,
    contract_root: str,
    relative: Any,
    *,
    field: str,
) -> Path:
    contract_root = safe_relative_path(contract_root, field="contract_root")
    relative = safe_relative_path(relative, field=field)
    base = (distribution_root / contract_root).resolve()
    target = (base / relative).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise AuthorityError(f"{field}: path escapes contract root") from exc
    return target


def _validate_receipt_shape(payload: Mapping[str, Any]) -> None:
    _require_exact_fields(payload, RECEIPT_FIELDS, label="authority receipt")
    expected_scalars = {
        "schema_id": "TerminologyContractsAuthorityReceiptV1",
        "schema_version": "1.0.0",
        "receipt_revision": 2,
        "authority_status": "SEALED",
        "publication_status": "PENDING_INDEPENDENT_REVIEW",
        "contract_version": CONTRACT_VERSION,
        "authority_tag": AUTHORITY_TAG,
        "authority_tag_object_oid": AUTHORITY_TAG_OBJECT_OID,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_root": CONTRACT_ROOT,
        "manifest_path": "manifest.json",
        "manifest_sha256": MANIFEST_SELF_SHA256,
        "final_release_path": f"{FINAL_RELEASE_DIR}/terminology_contracts_v1_1_0_final.zip",
        "final_release_checksum_path": f"{FINAL_RELEASE_DIR}/terminology_contracts_v1_1_0_final.zip.sha256",
        "final_release_zip_sha256": APPROVED_FINAL_ZIP_SHA256,
        "final_release_audit_path": f"{FINAL_RELEASE_DIR}/final_release_audit.json",
        "gate_policy_path": "policies/gate_policy_v1.0.0.json",
        "gate_policy_self_sha256": GATE_POLICY_SELF_SHA256,
        "feature_registry_path": "registries/feature_contract_v1.1.0.json",
        "feature_registry_version": CONTRACT_VERSION,
        "reviewed_content_commit": REVIEWED_CONTENT_COMMIT,
        "review_evidence_commit": REVIEW_EVIDENCE_COMMIT,
    }
    for field, expected in expected_scalars.items():
        if payload.get(field) != expected:
            raise AuthorityError(
                f"authority receipt {field} mismatch: expected {expected!r}, "
                f"got {payload.get(field)!r}"
            )
    require_git_oid(payload.get("canonical_main_observed_commit"), field="canonical_main_observed_commit")
    require_git_oid(payload.get("contract_tree_git_oid"), field="contract_tree_git_oid")
    for field in (
        "manifest_file_sha256",
        "final_release_audit_self_sha256",
        "final_release_audit_physical_sha256",
        "gate_policy_file_sha256",
        "feature_registry_canonical_sha256",
        "feature_registry_file_sha256",
    ):
        require_sha256(payload.get(field), field=field)
    issued_at = payload.get("issued_at")
    if not isinstance(issued_at, str) or not issued_at.endswith("Z"):
        raise AuthorityError("issued_at must be an explicit UTC timestamp")
    verify_self_hash(payload, label="authority receipt")


def _verify_superseded_receipts(
    payload: Mapping[str, Any],
    *,
    distribution_root: Path,
) -> list[dict[str, str]]:
    rows = payload.get("supersedes_receipts")
    if not isinstance(rows, list) or len(rows) != 2:
        raise AuthorityError("supersedes_receipts must contain the two historical receipts")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise AuthorityError(f"supersedes_receipts[{index}] must be an object")
        _require_exact_fields(row, SUPERSEDED_FIELDS, label=f"supersedes_receipts[{index}]")
        path_text = safe_relative_path(row.get("path"), field=f"supersedes_receipts[{index}].path")
        if path_text in seen:
            raise AuthorityError("duplicate superseded receipt path")
        seen.add(path_text)
        if row.get("status") != "SUPERSEDED_BY_RECEIPT_R2":
            raise AuthorityError("historical receipt must be marked SUPERSEDED_BY_RECEIPT_R2")
        declared = require_sha256(
            row.get("declared_self_sha256"),
            field=f"supersedes_receipts[{index}].declared_self_sha256",
        )
        canonical = require_sha256(
            row.get("canonical_self_sha256"),
            field=f"supersedes_receipts[{index}].canonical_self_sha256",
        )
        physical = require_sha256(
            row.get("physical_sha256"),
            field=f"supersedes_receipts[{index}].physical_sha256",
        )
        path = _resolve_distribution_path(
            distribution_root,
            CONTRACT_ROOT,
            path_text,
            field=f"supersedes_receipts[{index}].path",
        )
        historical = read_strict_json(path)
        historical_declared = historical.get("integrity", {}).get("self_sha256")
        historical_canonical = calculate_self_sha256(historical)
        if historical_declared != declared:
            raise AuthorityError(f"historical receipt declared hash mismatch: {path_text}")
        if historical_canonical != canonical:
            raise AuthorityError(f"historical receipt canonical hash mismatch: {path_text}")
        if sha256_file(path) != physical:
            raise AuthorityError(f"historical receipt physical hash mismatch: {path_text}")
        results.append(
            {
                "path": path_text,
                "status": "SUPERSEDED_BY_RECEIPT_R2",
                "integrity_mode": (
                    "CANONICAL_SELF_HASH" if declared == canonical else "HISTORICAL_INVALID_SELF_HASH"
                ),
            }
        )
    return results


def _verify_release_audit(payload: Mapping[str, Any], receipt: Mapping[str, Any]) -> None:
    verify_self_hash(payload, label="final release audit")
    expected = {
        "schema_id": "TerminologyContractsAuthorityMaintenanceReleaseAuditV1",
        "contract_version": CONTRACT_VERSION,
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "manifest_sha256": MANIFEST_SELF_SHA256,
        "release_zip_sha256": APPROVED_FINAL_ZIP_SHA256,
        "gate_policy_self_sha256": GATE_POLICY_SELF_SHA256,
        "feature_registry_version": CONTRACT_VERSION,
        "test_result": "PASS",
        "test_failures": 0,
        "test_errors": 0,
        "test_skipped": 0,
        "external_api_calls": 0,
        "source_ref": AUTHORITY_TAG,
    }
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise AuthorityError(f"final release audit {field} mismatch")
    if not isinstance(payload.get("test_count"), int) or payload["test_count"] <= 0:
        raise AuthorityError("final release audit requires nonzero passing tests")
    if payload.get("feature_registry_file_sha256") != receipt.get("feature_registry_file_sha256"):
        raise AuthorityError("final release audit feature registry binding mismatch")
    if payload.get("manifest_file_sha256") != receipt.get("manifest_file_sha256"):
        raise AuthorityError("final release audit manifest physical binding mismatch")


def _verify_distribution_manifest(final_dir: Path) -> dict[str, Any]:
    manifest_path = final_dir / "release_manifest.json"
    checksums_path = final_dir / "CHECKSUMS.sha256"
    payload = read_strict_json(manifest_path)
    verify_self_hash(payload, label="release manifest")
    if payload.get("schema_id") != "TerminologyContractsAuthorityMaintenanceManifestV1":
        raise AuthorityError("release manifest schema_id mismatch")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise AuthorityError("release manifest files must be non-empty")
    expected_paths: set[str] = set()
    expected_lines: list[str] = []
    for index, row in enumerate(files):
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256", "size_bytes"}:
            raise AuthorityError(f"release manifest files[{index}] shape mismatch")
        relative = safe_relative_path(row.get("path"), field=f"release manifest files[{index}].path")
        if relative in expected_paths:
            raise AuthorityError(f"duplicate release artifact: {relative}")
        expected_paths.add(relative)
        path = (final_dir / relative).resolve()
        try:
            path.relative_to(final_dir.resolve())
        except ValueError as exc:
            raise AuthorityError(f"release artifact escapes final directory: {relative}") from exc
        if not path.is_file():
            raise AuthorityError(f"release artifact missing: {relative}")
        if row.get("size_bytes") != path.stat().st_size:
            raise AuthorityError(f"release artifact size mismatch: {relative}")
        digest = sha256_file(path)
        if row.get("sha256") != digest:
            raise AuthorityError(f"release artifact hash mismatch: {relative}")
        expected_lines.append(f"{digest}  {relative}")
    actual_paths = {
        path.relative_to(final_dir).as_posix()
        for path in final_dir.rglob("*")
        if path.is_file() and path.name not in {"release_manifest.json", "CHECKSUMS.sha256"}
    }
    if actual_paths != expected_paths:
        raise AuthorityError(
            f"release manifest file-set mismatch: missing={sorted(expected_paths - actual_paths)}, "
            f"extra={sorted(actual_paths - expected_paths)}"
        )
    expected_lines.append(f"{sha256_file(manifest_path)}  release_manifest.json")
    actual_lines = checksums_path.read_text(encoding="ascii").splitlines()
    if actual_lines != sorted(expected_lines):
        raise AuthorityError("release CHECKSUMS.sha256 mismatch")
    return payload


def verify_authority_receipt(
    *,
    repo_root: Path,
    distribution_root: Path,
    receipt_path: Path,
    require_distribution_manifest: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    distribution_root = distribution_root.resolve()
    receipt_path = receipt_path.resolve()
    receipt = read_strict_json(receipt_path)
    _validate_receipt_shape(receipt)

    checksum_path = receipt_path.with_name(receipt_path.name + ".sha256")
    expected_physical = read_checksum(checksum_path, expected_name=receipt_path.name)
    physical = sha256_file(receipt_path)
    if physical != expected_physical:
        raise AuthorityError("authority receipt physical SHA-256 mismatch")

    identity = resolve_tag_identity(repo_root)
    if receipt["contract_tree_git_oid"] != identity.contract_tree_oid:
        raise AuthorityError("contract tree Git OID mismatch")
    observed_main = receipt["canonical_main_observed_commit"]
    if git(repo_root, "cat-file", "-t", observed_main) != "commit":
        raise AuthorityError("canonical_main_observed_commit is not a commit")
    try:
        git(repo_root, "merge-base", "--is-ancestor", AUTHORITY_COMMIT, observed_main)
    except AuthorityError as exc:
        raise AuthorityError("authority commit is not an ancestor of observed main") from exc

    manifest = verify_tagged_manifest(repo_root)
    if receipt["manifest_sha256"] != manifest.self_sha256:
        raise AuthorityError("receipt manifest self-hash binding mismatch")
    if receipt["manifest_file_sha256"] != manifest.physical_sha256:
        raise AuthorityError("receipt manifest physical binding mismatch")

    final_zip = _resolve_distribution_path(
        distribution_root,
        receipt["contract_root"],
        receipt["final_release_path"],
        field="final_release_path",
    )
    zip_checksum = _resolve_distribution_path(
        distribution_root,
        receipt["contract_root"],
        receipt["final_release_checksum_path"],
        field="final_release_checksum_path",
    )
    checksum_digest = read_checksum(zip_checksum, expected_name=final_zip.name)
    zip_digest = verify_zip_against_tag(repo_root, final_zip, manifest=manifest)
    if zip_digest != checksum_digest or zip_digest != receipt["final_release_zip_sha256"]:
        raise AuthorityError("final release ZIP SHA-256 mismatch")

    gate_policy = verify_tagged_gate_policy(repo_root)
    if receipt["gate_policy_self_sha256"] != gate_policy["self_sha256"]:
        raise AuthorityError("receipt GatePolicy self-hash binding mismatch")
    if receipt["gate_policy_file_sha256"] != gate_policy["physical_sha256"]:
        raise AuthorityError("receipt GatePolicy physical binding mismatch")

    feature_registry = verify_tagged_feature_registry(repo_root)
    if receipt["feature_registry_version"] != feature_registry["version"]:
        raise AuthorityError("receipt feature registry version mismatch")
    if receipt["feature_registry_canonical_sha256"] != feature_registry["canonical_sha256"]:
        raise AuthorityError("receipt feature registry canonical binding mismatch")
    if receipt["feature_registry_file_sha256"] != feature_registry["physical_sha256"]:
        raise AuthorityError("receipt feature registry physical binding mismatch")

    audit_path = _resolve_distribution_path(
        distribution_root,
        receipt["contract_root"],
        receipt["final_release_audit_path"],
        field="final_release_audit_path",
    )
    audit = read_strict_json(audit_path)
    audit_self = verify_self_hash(audit, label="final release audit")
    if audit_self != receipt["final_release_audit_self_sha256"]:
        raise AuthorityError("receipt final release audit self-hash mismatch")
    if sha256_file(audit_path) != receipt["final_release_audit_physical_sha256"]:
        raise AuthorityError("receipt final release audit physical hash mismatch")
    _verify_release_audit(audit, receipt)

    historical = _verify_superseded_receipts(
        receipt,
        distribution_root=distribution_root,
    )

    contract_root = (distribution_root / CONTRACT_ROOT).resolve()
    stale = [path for path in STALE_ACTIVE_FILES if (contract_root / path).exists()]
    if stale:
        raise AuthorityError(f"stale RC1 active release paths remain: {stale}")

    final_dir = final_zip.parent
    if require_distribution_manifest:
        _verify_distribution_manifest(final_dir)

    return seal_self_hash(
        {
            "schema_id": "TerminologyContractsAuthorityVerificationReportV1",
            "result": "PASS",
            "authority_tag": AUTHORITY_TAG,
            "authority_commit": AUTHORITY_COMMIT,
            "receipt_self_sha256": receipt["integrity"]["self_sha256"],
            "receipt_physical_sha256": physical,
            "manifest_sha256": manifest.self_sha256,
            "release_zip_sha256": zip_digest,
            "gate_policy_self_sha256": gate_policy["self_sha256"],
            "feature_registry_canonical_sha256": feature_registry["canonical_sha256"],
            "historical_receipts": historical,
            "integrity_mode": "CANONICAL_SELF_HASH_AND_PHYSICAL_DISTRIBUTION_PIN",
            "warnings": [],
            "integrity": {"self_sha256": ""},
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Contracts V1.1.0 authority receipt R2")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--distribution-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    receipt = args.receipt or (
        args.distribution_root
        / CONTRACT_ROOT
        / FINAL_RELEASE_DIR
        / RECEIPT_NAME
    )
    try:
        report = verify_authority_receipt(
            repo_root=args.repo_root,
            distribution_root=args.distribution_root,
            receipt_path=receipt,
        )
    except AuthorityError as exc:
        raise SystemExit(f"AUTHORITY VERIFICATION FAILED: {exc}") from exc
    if args.report:
        write_json(args.report, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
