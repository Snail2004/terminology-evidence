"""AR-2 preregistration receipt modes and authority-bound construction."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..authority import verify_authority_evidence_object, verify_external_authorities
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
        resolved = subprocess.run(
            ["git", "-C", str(repo_root_path), "rev-parse", "--verify", f"{commit}^{{commit}}"],
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

    expected = load_allowed_authority_profile()["evaluation_registries"]
    result: dict[str, str] = {}
    for filename, digest in expected.items():
        path = root / filename
        if path.is_symlink() or not path.is_file() or sha256_file(path) != digest:
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
    if not isinstance(timestamp, str) or not timestamp:
        raise ReceiptError("created_at is required")

    if mode == MODE_REAL_AUTHORITY:
        if authority_artifact_paths is None:
            raise ReceiptError("REAL_AUTHORITY requires external authority artifacts")
        authority_evidence = verify_external_authorities(authority_artifact_paths, registry_root=root)
        verify_authority_evidence_object(authority_evidence)
        dataset_hash: str | None = authority_evidence["dataset"]["manifest_declared_sha256"]
        status = STATUS_FROZEN
        frozen = True
        hashes = _artifact_hashes(artifact_hashes, require_nonempty=True)
        extra: dict[str, Any] = {}
    else:
        if authority_artifact_paths is not None:
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
) -> dict[str, Any]:
    receipt = read_json(path)
    verify_receipt_object(receipt)
    root = registry_root_path or registry_root()
    if receipt["registries"] != _registry_hashes(root):
        raise ReceiptError("receipt registry authority drift")
    if repo_root_path is not None:
        _verify_commit(repo_root_path, receipt["base_commit"])
    if receipt["mode"] == MODE_REAL_AUTHORITY and authority_artifact_paths is not None:
        current = verify_external_authorities(authority_artifact_paths, registry_root=root)
        if current != receipt["authority_evidence"]:
            raise ReceiptError("external authority bytes differ from frozen receipt")
    return receipt
