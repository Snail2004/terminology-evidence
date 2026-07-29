"""Read-only verification for historical V1 preregistration receipt bytes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..constants import LEGACY_RECEIPT_SCHEMA_ID, MODE_LEGACY_READ_ONLY, SCHEMA_VERSION, STATUS_LEGACY_READ_ONLY
from ..jsonio import read_json, sha256_file, sha256_value


class LegacyReceiptError(ValueError):
    """Raised when historical receipt bytes cannot be verified exactly."""


_LEGACY_KEYS = {
    "schema_id",
    "schema_version",
    "status",
    "frozen_before_validation",
    "created_at",
    "base_commit",
    "dataset_manifest_sha256",
    "registries",
    "contracts_authority",
    "global_action_policy",
    "artifact_hashes",
    "integrity",
}


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    integrity = dict(result.get("integrity", {}))
    integrity.pop("self_sha256", None)
    result["integrity"] = integrity
    return result


def verify_legacy_receipt(path: Path, *, registry_root_path: Path) -> dict[str, Any]:
    value = read_json(path)
    if set(value) != _LEGACY_KEYS or value.get("schema_id") != LEGACY_RECEIPT_SCHEMA_ID or value.get("schema_version") != SCHEMA_VERSION:
        raise LegacyReceiptError("unsupported legacy receipt shape")
    integrity = value.get("integrity")
    declared = integrity.get("self_sha256") if isinstance(integrity, Mapping) else None
    if not isinstance(declared, str) or declared != sha256_value(_without_self_hash(value)):
        raise LegacyReceiptError("legacy receipt self hash mismatch")
    registries = value.get("registries")
    if not isinstance(registries, Mapping) or not registries:
        raise LegacyReceiptError("legacy registry binding is missing")
    for key, digest in registries.items():
        path_candidate = registry_root_path / f"{key}_v1.json"
        if not isinstance(digest, str) or not path_candidate.is_file() or sha256_file(path_candidate) != digest:
            raise LegacyReceiptError(f"legacy registry binding drift: {key}")
    return {
        "schema_id": "EvaluationLegacyReceiptProjectionV1",
        "schema_version": "1.0.0",
        "mode": MODE_LEGACY_READ_ONLY,
        "status": STATUS_LEGACY_READ_ONLY,
        "source_receipt_physical_sha256": sha256_file(path),
        "source_receipt_self_sha256": declared,
        "can_freeze": False,
        "can_open_validation": False,
        "can_open_hidden_test": False,
    }
