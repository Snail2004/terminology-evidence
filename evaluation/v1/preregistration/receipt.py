"""AR-2 preregistration receipt modes and authority-bound construction."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..authority import verify_authority_evidence_object, verify_external_authorities
from ..artifacts.authority import AuthorityError, secure_existing_directory, secure_existing_file
from ..constants import (
    MODE_LEGACY_READ_ONLY,
    MODE_REAL_AUTHORITY,
    MODE_SYNTHETIC,
    RECEIPT_SCHEMA_ID,
    RECEIPT_SCHEMA_VERSION,
    STATUS_CONFORMANCE_ONLY,
    STATUS_FROZEN,
)
from ..jsonio import read_json, sha256_file, sha256_value, write_json
from ..registries.loader import registry_root
from ..time_policy import TimestampError, parse_rfc3339


class ReceiptError(ValueError):
    """Raised when a receipt could authorize an unbound preregistration state."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_COMMON_KEYS = {
    "schema_id",
    "schema_version",
    "mode",
    "status",
    "frozen_before_validation",
    "created_at",
    "base_commit",
    "dataset_manifest_sha256",
    "registries",
    "authority_evidence",
    "artifact_hashes",
    "integrity",
}
VERIFICATION_REPORT_SCHEMA_ID = "EvaluationRealReceiptVerificationReportV1"
VERIFICATION_REPORT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class VerifiedRealReceipt:
    """Verifier-produced capability required by the durable freeze boundary."""

    receipt: Mapping[str, Any]
    receipt_path: Path
    receipt_root_path: Path
    receipt_physical_sha256: str
    verification_report: Mapping[str, Any]


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    integrity = dict(result.get("integrity", {}))
    integrity.pop("self_sha256", None)
    result["integrity"] = integrity
    return result


def _require_commit(value: Any) -> str:
    if not isinstance(value, str) or not _COMMIT.fullmatch(value):
        raise ReceiptError("base_commit must be a full lowercase Git commit")
    return value


def _require_hash(value: Any, field: str, *, allow_none: bool = False) -> str | None:
    if allow_none and value is None:
        return None
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or set(value) == {"0"}:
        raise ReceiptError(f"{field} must be a nonzero lowercase SHA256")
    return value


def _verify_commit(repo_root_path: Path, commit: str) -> None:
    try:
        repository = secure_existing_directory(repo_root_path, field="receipt.git_repository")
    except AuthorityError as exc:
        raise ReceiptError(str(exc)) from exc
    try:
        resolved = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--verify", f"{commit}^{{commit}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip().lower()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReceiptError("base_commit is not present in the supplied repository") from exc
    if resolved != commit:
        raise ReceiptError("base_commit does not resolve exactly")


def _registry_hashes(root: Path) -> dict[str, str]:
    from ..authority import load_allowed_authority_profile

    try:
        registry_directory = secure_existing_directory(root, field="receipt.registry_root")
    except AuthorityError as exc:
        raise ReceiptError(str(exc)) from exc
    expected = load_allowed_authority_profile()["evaluation_registries"]
    result: dict[str, str] = {}
    for filename, digest in expected.items():
        try:
            path = secure_existing_file(
                registry_directory / filename,
                trusted_root=registry_directory,
                field=f"receipt.registry.{filename}",
            )
        except AuthorityError as exc:
            raise ReceiptError(str(exc)) from exc
        if sha256_file(path) != digest:
            raise ReceiptError(f"registry authority drift: {filename}")
        result[filename] = digest
    return dict(sorted(result.items()))


def _artifact_hashes(value: Mapping[str, str] | None, *, require_nonempty: bool) -> dict[str, str]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping) or (require_nonempty and not value):
        raise ReceiptError("artifact_hashes must be a nonempty object")
    result: dict[str, str] = {}
    for name, digest in value.items():
        if not isinstance(name, str) or not name or "/" in name or "\\" in name or ":" in name:
            raise ReceiptError("artifact hash key is not a canonical identifier")
        result[name] = str(_require_hash(digest, f"artifact_hashes.{name}"))
    return dict(sorted(result.items()))


def build_receipt(
    *,
    mode: str,
    base_commit: str,
    repo_root_path: Path,
    registry_root_path: Path | None = None,
    artifact_hashes: Mapping[str, str] | None = None,
    authority_artifact_paths: Mapping[str, Path] | None = None,
    authority_root_path: Path | None = None,
    created_at: str | None = None,
    synthetic_reason: str | None = None,
) -> dict[str, Any]:
    """Build a real or conformance-only receipt; legacy mode is verify-only."""
    if mode == MODE_LEGACY_READ_ONLY:
        raise ReceiptError("LEGACY_READ_ONLY cannot build or freeze a new receipt")
    if mode not in {MODE_REAL_AUTHORITY, MODE_SYNTHETIC}:
        raise ReceiptError(f"unsupported receipt mode: {mode}")
    commit = _require_commit(base_commit)
    _verify_commit(repo_root_path, commit)
    root = registry_root_path or registry_root()
    registries = _registry_hashes(root)
    timestamp = created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        parse_rfc3339(timestamp, "receipt.created_at")
    except TimestampError as exc:
        raise ReceiptError(str(exc)) from exc

    if mode == MODE_REAL_AUTHORITY:
        if authority_artifact_paths is None or authority_root_path is None:
            raise ReceiptError("REAL_AUTHORITY requires all authority artifacts and an explicit trusted root")
        authority_evidence = verify_external_authorities(
            authority_artifact_paths,
            registry_root=root,
            trusted_root=authority_root_path,
        )
        verify_authority_evidence_object(authority_evidence)
        dataset_hash: str | None = authority_evidence["dataset"]["manifest_declared_sha256"]
        status = STATUS_FROZEN
        frozen = True
        hashes = _artifact_hashes(artifact_hashes, require_nonempty=True)
        extra: dict[str, Any] = {}
    else:
        if authority_artifact_paths is not None or authority_root_path is not None:
            raise ReceiptError("synthetic mode cannot consume real authority artifacts")
        if not isinstance(synthetic_reason, str) or not synthetic_reason.strip():
            raise ReceiptError("synthetic mode requires an explicit conformance reason")
        authority_evidence = None
        dataset_hash = None
        status = STATUS_CONFORMANCE_ONLY
        frozen = False
        hashes = _artifact_hashes(artifact_hashes, require_nonempty=False)
        extra = {"synthetic_reason": synthetic_reason}

    receipt: dict[str, Any] = {
        "schema_id": RECEIPT_SCHEMA_ID,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "mode": mode,
        "status": status,
        "frozen_before_validation": frozen,
        "created_at": timestamp,
        "base_commit": commit,
        "dataset_manifest_sha256": dataset_hash,
        "registries": registries,
        "authority_evidence": authority_evidence,
        "artifact_hashes": hashes,
        **extra,
        "integrity": {"self_sha256": ""},
    }
    receipt["integrity"]["self_sha256"] = sha256_value(_without_self_hash(receipt))
    verify_receipt_object(receipt)
    return receipt


def verify_receipt_object(receipt: Mapping[str, Any]) -> str:
    mode = receipt.get("mode")
    expected_keys = set(_COMMON_KEYS)
    if mode == MODE_SYNTHETIC:
        expected_keys.add("synthetic_reason")
    if set(receipt) != expected_keys:
        raise ReceiptError(f"receipt fields mismatch: {sorted(set(receipt))}")
    if receipt.get("schema_id") != RECEIPT_SCHEMA_ID or receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ReceiptError("unsupported preregistration receipt schema")
    _require_commit(receipt.get("base_commit"))
    try:
        parse_rfc3339(receipt.get("created_at"), "receipt.created_at")
    except TimestampError as exc:
        raise ReceiptError(str(exc)) from exc
    registries = receipt.get("registries")
    if not isinstance(registries, Mapping) or not registries:
        raise ReceiptError("receipt registry binding is missing")
    for name, digest in registries.items():
        if not isinstance(name, str) or not name.endswith("_v1.json"):
            raise ReceiptError("receipt registry name is invalid")
        _require_hash(digest, f"registries.{name}")
    if mode == MODE_REAL_AUTHORITY:
        if receipt.get("status") != STATUS_FROZEN or receipt.get("frozen_before_validation") is not True:
            raise ReceiptError("REAL_AUTHORITY receipt is not frozen")
        _require_hash(receipt.get("dataset_manifest_sha256"), "dataset_manifest_sha256")
        evidence = receipt.get("authority_evidence")
        if not isinstance(evidence, Mapping):
            raise ReceiptError("REAL_AUTHORITY receipt has no verified authority evidence")
        verify_authority_evidence_object(evidence)
        if receipt["dataset_manifest_sha256"] != evidence["dataset"]["manifest_declared_sha256"]:
            raise ReceiptError("receipt Dataset binding differs from verified authority evidence")
        _artifact_hashes(receipt.get("artifact_hashes"), require_nonempty=True)
    elif mode == MODE_SYNTHETIC:
        if receipt.get("status") != STATUS_CONFORMANCE_ONLY or receipt.get("frozen_before_validation") is not False:
            raise ReceiptError("synthetic receipt has an authority-bearing status")
        if receipt.get("authority_evidence") is not None or receipt.get("dataset_manifest_sha256") is not None:
            raise ReceiptError("synthetic receipt contains real authority bindings")
        if not isinstance(receipt.get("synthetic_reason"), str) or not receipt["synthetic_reason"].strip():
            raise ReceiptError("synthetic receipt reason is missing")
        _artifact_hashes(receipt.get("artifact_hashes"), require_nonempty=False)
    else:
        raise ReceiptError("legacy/unknown receipt mode cannot use the V2 verifier")
    integrity = receipt.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {"self_sha256"}:
        raise ReceiptError("receipt integrity shape is invalid")
    declared = _require_hash(integrity.get("self_sha256"), "integrity.self_sha256")
    actual = sha256_value(_without_self_hash(receipt))
    if declared != actual:
        raise ReceiptError("receipt self hash mismatch")
    return actual


def write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    verify_receipt_object(receipt)
    write_json(path, dict(receipt))


def verify_receipt(
    path: Path,
    *,
    registry_root_path: Path | None = None,
    repo_root_path: Path | None = None,
    authority_artifact_paths: Mapping[str, Path] | None = None,
    authority_root_path: Path | None = None,
) -> dict[str, Any]:
    receipt = read_json(path)
    verify_receipt_object(receipt)
    root = registry_root_path or registry_root()
    if receipt["registries"] != _registry_hashes(root):
        raise ReceiptError("receipt registry authority drift")
    if receipt["mode"] == MODE_REAL_AUTHORITY and (
        repo_root_path is None
        or authority_artifact_paths is None
        or authority_root_path is None
    ):
        raise ReceiptError("REAL_AUTHORITY verification requires Git root, authority root and all authority paths")
    if repo_root_path is not None:
        _verify_commit(repo_root_path, receipt["base_commit"])
    if receipt["mode"] == MODE_REAL_AUTHORITY:
        current = verify_external_authorities(
            authority_artifact_paths,
            registry_root=root,
            trusted_root=authority_root_path,
        )
        if current != receipt["authority_evidence"]:
            raise ReceiptError("external authority bytes differ from frozen receipt")
    return receipt


def _verification_report_hash(value: Mapping[str, Any]) -> str:
    return sha256_value(_without_self_hash(value))


def verify_real_receipt_capability(value: VerifiedRealReceipt) -> str:
    if not isinstance(value, VerifiedRealReceipt):
        raise ReceiptError("freeze requires a VerifiedRealReceipt capability")
    receipt = value.receipt
    verify_receipt_object(receipt)
    if receipt.get("mode") != MODE_REAL_AUTHORITY:
        raise ReceiptError("verified capability is not REAL_AUTHORITY")
    _require_hash(value.receipt_physical_sha256, "receipt_physical_sha256")
    try:
        current_path = secure_existing_file(
            value.receipt_path,
            trusted_root=value.receipt_root_path,
            field="verified_preregistration_receipt",
        )
    except AuthorityError as exc:
        raise ReceiptError(str(exc)) from exc
    if sha256_file(current_path) != value.receipt_physical_sha256:
        raise ReceiptError("verified preregistration receipt physical bytes drifted")
    report = value.verification_report
    expected_keys = {
        "schema_id",
        "schema_version",
        "receipt_self_sha256",
        "receipt_physical_sha256",
        "base_commit",
        "registry_binding_sha256",
        "authority_evidence_sha256",
        "integrity",
    }
    if not isinstance(report, Mapping) or set(report) != expected_keys:
        raise ReceiptError("verified receipt report shape is invalid")
    if report.get("schema_id") != VERIFICATION_REPORT_SCHEMA_ID or report.get("schema_version") != VERIFICATION_REPORT_SCHEMA_VERSION:
        raise ReceiptError("unsupported verified receipt report")
    expected = {
        "receipt_self_sha256": receipt["integrity"]["self_sha256"],
        "receipt_physical_sha256": value.receipt_physical_sha256,
        "base_commit": receipt["base_commit"],
        "registry_binding_sha256": sha256_value(receipt["registries"]),
        "authority_evidence_sha256": receipt["authority_evidence"]["integrity"]["self_sha256"],
    }
    for field, expected_value in expected.items():
        if report.get(field) != expected_value:
            raise ReceiptError(f"verified receipt report {field} mismatch")
    declared = report.get("integrity", {}).get("self_sha256") if isinstance(report.get("integrity"), Mapping) else None
    actual = _verification_report_hash(report)
    if declared != actual:
        raise ReceiptError("verified receipt report self hash mismatch")
    return actual


def verify_real_receipt(
    receipt_path: Path,
    *,
    receipt_root_path: Path,
    repo_root_path: Path,
    registry_root_path: Path,
    authority_artifact_paths: Mapping[str, Path],
    authority_root_path: Path,
) -> VerifiedRealReceipt:
    """Verify persisted REAL receipt bytes and return the only freeze capability."""
    try:
        checked_root = secure_existing_directory(
            receipt_root_path,
            field="preregistration_receipt_root",
        )
        checked_path = secure_existing_file(
            receipt_path,
            trusted_root=checked_root,
            field="preregistration_receipt",
        )
    except AuthorityError as exc:
        raise ReceiptError(str(exc)) from exc
    physical_before = sha256_file(checked_path)
    receipt = verify_receipt(
        checked_path,
        registry_root_path=registry_root_path,
        repo_root_path=repo_root_path,
        authority_artifact_paths=authority_artifact_paths,
        authority_root_path=authority_root_path,
    )
    try:
        checked_after = secure_existing_file(
            receipt_path,
            trusted_root=checked_root,
            field="preregistration_receipt",
        )
    except AuthorityError as exc:
        raise ReceiptError(str(exc)) from exc
    physical_after = sha256_file(checked_after)
    if physical_after != physical_before:
        raise ReceiptError("preregistration receipt bytes drifted during verification")
    if receipt.get("mode") != MODE_REAL_AUTHORITY:
        raise ReceiptError("only REAL_AUTHORITY receipts produce freeze capabilities")
    report: dict[str, Any] = {
        "schema_id": VERIFICATION_REPORT_SCHEMA_ID,
        "schema_version": VERIFICATION_REPORT_SCHEMA_VERSION,
        "receipt_self_sha256": receipt["integrity"]["self_sha256"],
        "receipt_physical_sha256": physical_before,
        "base_commit": receipt["base_commit"],
        "registry_binding_sha256": sha256_value(receipt["registries"]),
        "authority_evidence_sha256": receipt["authority_evidence"]["integrity"]["self_sha256"],
        "integrity": {"self_sha256": ""},
    }
    report["integrity"]["self_sha256"] = _verification_report_hash(report)
    capability = VerifiedRealReceipt(
        receipt=dict(receipt),
        receipt_path=checked_after,
        receipt_root_path=checked_root,
        receipt_physical_sha256=physical_before,
        verification_report=report,
    )
    verify_real_receipt_capability(capability)
    return capability
