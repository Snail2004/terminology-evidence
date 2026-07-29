"""Explicit-manifest artifact discovery and physical integrity verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .errors import DiscoveryError, IntegrityError
from .hashing import self_sha256, sha256_file
from .jsonio import load_json
from .paths import ensure_no_symlink, safe_relative_path


@dataclass(frozen=True)
class ArtifactRecord:
    role: str
    path: Path
    relative_path: str
    schema_id: str
    schema_version: str
    producer: str
    producer_commit: str
    candidate_key: dict[str, str] | None
    physical_sha256: str
    declared_self_sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "relative_path": self.relative_path,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "producer": self.producer,
            "producer_commit": self.producer_commit,
            "candidate_key": self.candidate_key,
            "physical_sha256": self.physical_sha256,
            "declared_self_sha256": self.declared_self_sha256,
        }


@dataclass(frozen=True)
class ArtifactInventory:
    manifest_path: Path
    manifest: dict[str, Any]
    records: tuple[ArtifactRecord, ...]
    manifest_sha256: str


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DiscoveryError(f"manifest field {field} must be a non-empty string")
    return value


def load_inventory(manifest_path: Path) -> ArtifactInventory:
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_file():
        raise DiscoveryError(f"manifest does not exist: {manifest_path}")
    manifest = load_json(manifest_path, require_object=True)
    if manifest.get("schema_id") != "ArtifactInventoryV1":
        raise DiscoveryError("unsupported artifact manifest schema")
    if manifest.get("schema_version") != "1.0.0":
        raise DiscoveryError("unsupported artifact manifest version")
    integrity = manifest.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("self_sha256") != self_sha256(manifest):
        raise IntegrityError("artifact manifest self hash mismatch")
    raw_records = manifest.get("artifacts")
    if not isinstance(raw_records, list) or not raw_records:
        raise DiscoveryError("artifact manifest must contain artifacts")
    records: list[ArtifactRecord] = []
    seen_paths: set[str] = set()
    for raw in raw_records:
        if not isinstance(raw, dict):
            raise DiscoveryError("artifact record must be an object")
        role = _string(raw.get("role"), "role")
        relative = safe_relative_path(_string(raw.get("relative_path"), "relative_path"))
        relative_text = relative.as_posix()
        if relative_text in seen_paths:
            raise DiscoveryError(f"duplicate artifact path: {relative_text}")
        seen_paths.add(relative_text)
        path = ensure_no_symlink(manifest_path.parent, relative)
        if not path.is_file():
            raise DiscoveryError(f"artifact file is missing: {relative_text}")
        physical = sha256_file(path)
        declared_physical = _string(raw.get("physical_sha256"), "physical_sha256")
        if physical != declared_physical:
            raise IntegrityError(f"physical hash mismatch: {relative_text}")
        candidate_key = raw.get("candidate_key")
        if candidate_key is not None and not isinstance(candidate_key, dict):
            raise DiscoveryError("candidate_key in manifest must be an object")
        records.append(
            ArtifactRecord(
                role=role,
                path=path,
                relative_path=relative_text,
                schema_id=_string(raw.get("schema_id"), "schema_id"),
                schema_version=_string(raw.get("schema_version"), "schema_version"),
                producer=_string(raw.get("producer"), "producer"),
                producer_commit=_string(raw.get("producer_commit"), "producer_commit"),
                candidate_key=candidate_key,
                physical_sha256=physical,
                declared_self_sha256=raw.get("declared_self_sha256"),
            )
        )
    return ArtifactInventory(
        manifest_path=manifest_path,
        manifest=manifest,
        records=tuple(sorted(records, key=lambda item: (item.role, item.relative_path))),
        manifest_sha256=sha256_file(manifest_path),
    )


def inventory_report(inventory: ArtifactInventory) -> dict[str, Any]:
    return {
        "schema_id": "ArtifactInventoryReportV1",
        "manifest_sha256": inventory.manifest_sha256,
        "artifact_count": len(inventory.records),
        "artifacts": [record.as_dict() for record in inventory.records],
    }
