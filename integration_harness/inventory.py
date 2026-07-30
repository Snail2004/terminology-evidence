"""Explicit-manifest artifact discovery and physical integrity verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .errors import DiscoveryError, IntegrityError
from .hashing import self_sha256, sha256_file
from .jsonio import load_json
from .paths import ensure_no_symlink, ensure_plain_root, safe_relative_path


LEGACY_ADAPTER_INVENTORY_SCHEMA = "ArtifactInventory50_150V1"
ADAPTER_INVENTORY_SCHEMA = "ArtifactInventoryExactCohortV2"
LEGACY_INVENTORY_VERSION = "1.0.0"
INVENTORY_VERSION = "2.0.0"


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
class SourceAuthorityRecord:
    role: str
    path: Path
    relative_path: str
    physical_sha256: str
    declared_self_sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "relative_path": self.relative_path,
            "physical_sha256": self.physical_sha256,
            "declared_self_sha256": self.declared_self_sha256,
        }


@dataclass(frozen=True)
class HoldRecord:
    role: str
    candidate_key: dict[str, str]
    path: Path
    relative_path: str
    physical_sha256: str
    declared_self_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "candidate_key": self.candidate_key,
            "relative_path": self.relative_path,
            "physical_sha256": self.physical_sha256,
            "declared_self_sha256": self.declared_self_sha256,
        }


@dataclass(frozen=True)
class ArtifactInventory:
    manifest_path: Path
    manifest: dict[str, Any]
    records: tuple[ArtifactRecord, ...]
    manifest_sha256: str
    source_authority: tuple[SourceAuthorityRecord, ...] = ()
    holds: tuple[HoldRecord, ...] = ()


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DiscoveryError(f"manifest field {field} must be a non-empty string")
    return value


def load_inventory(manifest_path: Path) -> ArtifactInventory:
    manifest_path = ensure_plain_root(manifest_path.parent) / manifest_path.name
    if not manifest_path.is_file():
        raise DiscoveryError(f"manifest does not exist: {manifest_path}")
    manifest = load_json(manifest_path, require_object=True)
    schema_id = manifest.get("schema_id")
    if schema_id not in {"ArtifactInventoryV1", LEGACY_ADAPTER_INVENTORY_SCHEMA, ADAPTER_INVENTORY_SCHEMA}:
        raise DiscoveryError("unsupported artifact manifest schema")
    if schema_id == ADAPTER_INVENTORY_SCHEMA and manifest.get("schema_version") != INVENTORY_VERSION:
        raise DiscoveryError("unsupported exact-cohort artifact manifest version")
    if schema_id in {"ArtifactInventoryV1", LEGACY_ADAPTER_INVENTORY_SCHEMA} and manifest.get("schema_version") != LEGACY_INVENTORY_VERSION:
        raise DiscoveryError("unsupported artifact manifest version")
    integrity = manifest.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("self_sha256") != self_sha256(manifest):
        raise IntegrityError("artifact manifest self hash mismatch")
    raw_records = manifest.get("artifacts")
    if not isinstance(raw_records, list):
        raise DiscoveryError("artifact manifest artifacts must be an array")
    if not raw_records and schema_id not in {ADAPTER_INVENTORY_SCHEMA, LEGACY_ADAPTER_INVENTORY_SCHEMA}:
        raise DiscoveryError("artifact manifest must contain artifacts")
    records: list[ArtifactRecord] = []
    seen_paths: dict[str, ArtifactRecord] = {}
    for raw in raw_records:
        if not isinstance(raw, dict):
            raise DiscoveryError("artifact record must be an object")
        role = _string(raw.get("role"), "role")
        relative = safe_relative_path(_string(raw.get("relative_path"), "relative_path"))
        relative_text = relative.as_posix()
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
        record = ArtifactRecord(
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
        previous = seen_paths.get(relative_text)
        if previous is not None and not _shared_effective_allowed(
            previous, record, schema_id=schema_id
        ):
            raise DiscoveryError(f"duplicate artifact path: {relative_text}")
        seen_paths[relative_text] = previous or record
        records.append(record)
    source_authority = _load_source_authority(manifest_path, manifest, schema_id=schema_id)
    holds = _load_holds(manifest_path, manifest, schema_id=schema_id)
    if schema_id in {ADAPTER_INVENTORY_SCHEMA, LEGACY_ADAPTER_INVENTORY_SCHEMA}:
        candidate_count = manifest.get("candidate_count")
        sense_count = manifest.get("sense_count")
        if not isinstance(candidate_count, int) or candidate_count <= 0:
            raise DiscoveryError("adapter inventory candidate_count must be positive")
        if not isinstance(sense_count, int) or sense_count <= 0:
            raise DiscoveryError("adapter inventory sense_count must be positive")
        ready_count = manifest.get("ready_candidate_count")
        not_submitted = manifest.get("not_submitted_count")
        if (
            not isinstance(ready_count, int)
            or not isinstance(not_submitted, int)
            or ready_count < 0
            or not_submitted < 0
            or ready_count + not_submitted != candidate_count
        ):
            raise DiscoveryError("adapter ready/not-submitted counts mismatch")
    return ArtifactInventory(
        manifest_path=manifest_path,
        manifest=manifest,
        records=tuple(sorted(records, key=lambda item: (item.role, item.relative_path))),
        manifest_sha256=sha256_file(manifest_path),
        source_authority=source_authority,
        holds=holds,
    )


def inventory_report(inventory: ArtifactInventory) -> dict[str, Any]:
    return {
        "schema_id": "ArtifactInventoryReportV1",
        "manifest_sha256": inventory.manifest_sha256,
        "artifact_count": len(inventory.records),
        "artifacts": [record.as_dict() for record in inventory.records],
        "source_authority": [record.as_dict() for record in inventory.source_authority],
        "holds": [record.as_dict() for record in inventory.holds],
    }


def _shared_effective_allowed(
    previous: ArtifactRecord,
    current: ArtifactRecord,
    *,
    schema_id: Any,
) -> bool:
    if schema_id not in {ADAPTER_INVENTORY_SCHEMA, LEGACY_ADAPTER_INVENTORY_SCHEMA}:
        return False
    if previous.role != "effective_sense" or current.role != "effective_sense":
        return False
    if previous.candidate_key is None or current.candidate_key is None:
        return False
    if previous.candidate_key.get("candidate_id") == current.candidate_key.get("candidate_id"):
        return False
    for field in (
        "source_term",
        "sense_id",
        "scope_id",
        "sense_inventory_version",
        "dataset_manifest_sha256",
        "effective_sense_contract_sha256",
    ):
        if previous.candidate_key.get(field) != current.candidate_key.get(field):
            return False
    return (
        previous.schema_id == current.schema_id
        and previous.schema_version == current.schema_version
        and previous.producer == current.producer
        and previous.producer_commit == current.producer_commit
        and previous.physical_sha256 == current.physical_sha256
        and previous.declared_self_sha256 == current.declared_self_sha256
    )


def _load_source_authority(
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    schema_id: Any,
) -> tuple[SourceAuthorityRecord, ...]:
    raw_records = manifest.get("source_authority", [])
    if schema_id in {ADAPTER_INVENTORY_SCHEMA, LEGACY_ADAPTER_INVENTORY_SCHEMA} and not raw_records:
        raise DiscoveryError("adapter inventory requires source_authority")
    if not isinstance(raw_records, list):
        raise DiscoveryError("source_authority must be an array")
    result: list[SourceAuthorityRecord] = []
    seen_roles: set[str] = set()
    seen_paths: set[str] = set()
    for raw in raw_records:
        if not isinstance(raw, dict):
            raise DiscoveryError("source authority record must be an object")
        role = _string(raw.get("role"), "source_authority.role")
        relative = safe_relative_path(
            _string(raw.get("relative_path"), "source_authority.relative_path")
        )
        relative_text = relative.as_posix()
        if role in seen_roles or relative_text in seen_paths:
            raise DiscoveryError("duplicate source authority role/path")
        seen_roles.add(role)
        seen_paths.add(relative_text)
        path = ensure_no_symlink(manifest_path.parent, relative)
        if not path.is_file():
            raise DiscoveryError(f"source authority file is missing: {relative_text}")
        physical = sha256_file(path)
        if raw.get("physical_sha256") != physical:
            raise IntegrityError(f"source authority hash mismatch: {relative_text}")
        result.append(
            SourceAuthorityRecord(
                role=role,
                path=path,
                relative_path=relative_text,
                physical_sha256=physical,
                declared_self_sha256=raw.get("declared_self_sha256"),
            )
        )
    return tuple(sorted(result, key=lambda item: item.role))


def _load_holds(
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    schema_id: Any,
) -> tuple[HoldRecord, ...]:
    raw_records = manifest.get("holds", [])
    if raw_records:
        raise DiscoveryError("legacy hold records are forbidden; use availability sidecars")
    if not isinstance(raw_records, list):
        raise DiscoveryError("holds must be an array")
    result: list[HoldRecord] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_records:
        if not isinstance(raw, dict):
            raise DiscoveryError("HOLD record must be an object")
        role = _string(raw.get("role"), "holds.role")
        candidate_key = raw.get("candidate_key")
        if not isinstance(candidate_key, dict):
            raise DiscoveryError("HOLD candidate_key must be an object")
        candidate_id = _string(candidate_key.get("candidate_id"), "holds.candidate_id")
        key = (role, candidate_id)
        if key in seen:
            raise DiscoveryError("duplicate legacy hold record")
        seen.add(key)
        relative = safe_relative_path(
            _string(raw.get("relative_path"), "holds.relative_path")
        )
        path = ensure_no_symlink(manifest_path.parent, relative)
        if not path.is_file():
            raise DiscoveryError(f"HOLD file is missing: {relative.as_posix()}")
        physical = sha256_file(path)
        if raw.get("physical_sha256") != physical:
            raise IntegrityError(f"HOLD physical hash mismatch: {relative.as_posix()}")
        declared = _string(raw.get("declared_self_sha256"), "holds.declared_self_sha256")
        result.append(
            HoldRecord(
                role=role,
                candidate_key=candidate_key,
                path=path,
                relative_path=relative.as_posix(),
                physical_sha256=physical,
                declared_self_sha256=declared,
            )
        )
    return tuple(sorted(result, key=lambda item: (item.role, item.candidate_key["candidate_id"])))
