"""Complete producer package-set verification for Harness availability intake."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from integration_harness.adapter_v1.dataset import (
    DatasetCandidate,
    OFFICIAL_MODE,
    SYNTHETIC_MODE,
)
from integration_harness.errors import IntegrityError, PolicyError, ValidationError
from integration_harness.hashing import self_sha256, sha256_file
from integration_harness.identity import CandidateIdentity
from integration_harness.jsonio import dump_json, load_json
from integration_harness.packages import validate_contract_schema
from integration_harness.paths import ensure_no_symlink, ensure_plain_root, safe_relative_path


PACKAGE_SET_SCHEMA = "HarnessProducerPackageSetV1"
SCHEMA_VERSION = "1.0.0"

COMPLETE_ACCEPTED = "COMPLETE_ACCEPTED"
SYNTHETIC_COMPLETE = "SYNTHETIC_LOCAL_CONFORMANCE"

ROLE_SCHEMAS = {
    "context_evidence": "ContextEvidencePackageV1",
    "attestation_evidence": "AttestationEvidencePackageV1",
}

_MANIFEST_FIELDS = {
    "schema_id",
    "schema_version",
    "producer_role",
    "status",
    "producer",
    "entry_count",
    "package_count",
    "hold_count",
    "entries",
    "accepted_source_binding",
    "final_glossary_decision",
    "global_action",
    "integrity",
}
_ENTRY_FIELDS = {
    "candidate_id",
    "kind",
    "relative_path",
    "physical_sha256",
    "self_sha256",
}
_PRODUCER_FIELDS = {"component_id", "component_version", "run_id", "commit"}
_SOURCE_BINDING_FIELDS = {"source_manifest", "acceptance_receipt"}
_BOUND_FILE_FIELDS = {"relative_path", "physical_sha256", "self_sha256"}


@dataclass(frozen=True)
class ProducerItem:
    role: str
    identity: CandidateIdentity
    kind: str
    path: Path
    relative_path: str
    raw: bytes
    value: dict[str, Any]
    physical_sha256: str
    self_sha256: str


@dataclass(frozen=True)
class ProducerSet:
    role: str
    status: str
    manifest_path: Path
    manifest_raw: bytes
    manifest: dict[str, Any]
    items: tuple[ProducerItem, ...]
    source_manifest_path: Path | None
    acceptance_receipt_path: Path | None

def load_producer_set(
    manifest_path: Path,
    *,
    role: str,
    candidates: Sequence[DatasetCandidate],
    schema_root: Path,
    adapter_mode: str,
) -> ProducerSet:
    if role not in ROLE_SCHEMAS:
        raise ValidationError(f"unsupported producer role: {role}")
    root = ensure_plain_root(manifest_path.parent)
    manifest_path = ensure_no_symlink(root, safe_relative_path(manifest_path.name))
    manifest_raw = manifest_path.read_bytes()
    manifest = load_json(manifest_path, require_object=True)
    _require_exact_keys(manifest, _MANIFEST_FIELDS, "producer package-set manifest")
    if manifest.get("schema_id") != PACKAGE_SET_SCHEMA or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("unsupported Harness producer package-set manifest")
    _verify_self_hash(manifest, "producer package-set manifest")
    if manifest.get("producer_role") != role:
        raise ValidationError("producer package-set role mismatch")
    if manifest.get("final_glossary_decision") is not None:
        raise PolicyError("producer package-set contains a final glossary decision")
    if manifest.get("global_action") is not None:
        raise PolicyError("producer package-set contains a Global-owned action")
    status = _string(manifest.get("status"), "producer package-set status")
    _validate_status(status, adapter_mode=adapter_mode)
    producer = _producer(manifest.get("producer"))
    source_manifest_path, acceptance_receipt_path = _verify_source_binding(
        manifest,
        manifest_path=manifest_path,
        status=status,
    )
    expected = {candidate.identity.candidate_id: candidate.identity for candidate in candidates}
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != len(expected):
        raise ValidationError("producer package-set entry count mismatch")
    if entries != sorted(entries, key=lambda item: str(item.get("candidate_id", "")) if isinstance(item, Mapping) else ""):
        raise IntegrityError("producer package-set entries are not canonically sorted")
    if manifest.get("entry_count") != len(entries):
        raise ValidationError("producer package-set declared entry count mismatch")
    items: list[ProducerItem] = []
    observed: set[str] = set()
    folded_paths: set[str] = set()
    for offset, entry_value in enumerate(entries):
        entry = _mapping(entry_value, f"producer entry {offset}")
        _require_exact_keys(entry, _ENTRY_FIELDS, f"producer entry {offset}")
        candidate_id = _string(entry.get("candidate_id"), "producer candidate_id")
        if candidate_id in observed or candidate_id not in expected:
            raise ValidationError(f"duplicate or foreign producer candidate: {candidate_id}")
        observed.add(candidate_id)
        relative = safe_relative_path(
            _string(entry.get("relative_path"), "producer entry relative_path")
        )
        relative_text = relative.as_posix()
        if relative_text.casefold() in folded_paths:
            raise IntegrityError("producer package-set has case-confusable paths")
        folded_paths.add(relative_text.casefold())
        path = ensure_no_symlink(manifest_path.parent, relative)
        if not path.is_file():
            raise ValidationError(f"producer package is missing: {relative_text}")
        raw = path.read_bytes()
        physical = sha256_file(path)
        if entry.get("physical_sha256") != physical:
            raise IntegrityError(f"producer package physical hash mismatch: {relative_text}")
        value = load_json(path, require_object=True)
        kind = _string(entry.get("kind"), "producer entry kind")
        if kind == "PACKAGE":
            item = _validate_package(
                value,
                raw=raw,
                path=path,
                relative_path=relative_text,
                physical=physical,
                entry=entry,
                role=role,
                identity=expected[candidate_id],
                producer=producer,
                schema_root=schema_root,
            )
        else:
            raise ValidationError(f"unsupported producer entry kind: {kind}")
        items.append(item)
    if observed != set(expected):
        raise ValidationError("producer package-set is missing Dataset candidates")
    package_count = sum(item.kind == "PACKAGE" for item in items)
    if manifest.get("package_count") != package_count or manifest.get("hold_count") != 0:
        raise ValidationError("producer package-set package count mismatch")
    return ProducerSet(
        role=role,
        status=status,
        manifest_path=manifest_path,
        manifest_raw=manifest_raw,
        manifest=manifest,
        items=tuple(sorted(items, key=lambda item: item.identity.candidate_id)),
        source_manifest_path=source_manifest_path,
        acceptance_receipt_path=acceptance_receipt_path,
    )


def _validate_status(status: str, *, adapter_mode: str) -> None:
    if adapter_mode == OFFICIAL_MODE:
        allowed = {COMPLETE_ACCEPTED}
    elif adapter_mode == SYNTHETIC_MODE:
        allowed = {SYNTHETIC_COMPLETE}
    else:
        raise ValidationError(f"unsupported adapter mode: {adapter_mode}")
    if status not in allowed:
        raise PolicyError(f"producer package-set status is not admitted: {status}")


def _verify_source_binding(
    manifest: Mapping[str, Any],
    *,
    manifest_path: Path,
    status: str,
) -> tuple[Path | None, Path | None]:
    binding_value = manifest.get("accepted_source_binding")
    if status != COMPLETE_ACCEPTED:
        if binding_value is not None:
            raise PolicyError("non-official package set cannot claim an accepted source binding")
        return None, None
    binding = _mapping(binding_value, "accepted producer source binding")
    _require_exact_keys(
        binding,
        _SOURCE_BINDING_FIELDS,
        "accepted producer source binding",
    )
    source_path = _bound_file(
        manifest_path.parent,
        binding.get("source_manifest"),
        "producer source manifest",
    )
    receipt_path = _bound_file(
        manifest_path.parent,
        binding.get("acceptance_receipt"),
        "producer acceptance receipt",
    )
    return source_path, receipt_path


def _bound_file(root: Path, value: Any, label: str) -> Path:
    binding = _mapping(value, label)
    _require_exact_keys(binding, _BOUND_FILE_FIELDS, label)
    relative = safe_relative_path(_string(binding.get("relative_path"), f"{label} path"))
    path = ensure_no_symlink(root, relative)
    if not path.is_file() or binding.get("physical_sha256") != sha256_file(path):
        raise IntegrityError(f"{label} physical binding mismatch")
    payload = load_json(path, require_object=True)
    _verify_self_hash(payload, label)
    if binding.get("self_sha256") != payload["integrity"]["self_sha256"]:
        raise IntegrityError(f"{label} self-hash binding mismatch")
    return path


def _validate_package(
    value: Mapping[str, Any],
    *,
    raw: bytes,
    path: Path,
    relative_path: str,
    physical: str,
    entry: Mapping[str, Any],
    role: str,
    identity: CandidateIdentity,
    producer: Mapping[str, str],
    schema_root: Path,
) -> ProducerItem:
    expected_schema = ROLE_SCHEMAS[role]
    if value.get("schema_id") != expected_schema or value.get("schema_version") != "1.1.0":
        raise ValidationError(f"producer package schema mismatch: {relative_path}")
    _verify_self_hash(value, relative_path)
    validate_contract_schema(dict(value), schema_root)
    if CandidateIdentity.from_package(value) != identity:
        raise ValidationError(f"producer package identity mismatch: {relative_path}")
    if value.get("final_glossary_decision") is not None:
        raise PolicyError(f"producer package owns a final decision: {relative_path}")
    if any(field in value for field in ("global_action", "global_decision", "action_policy")):
        raise PolicyError(f"producer package owns a Global field: {relative_path}")
    provenance = _mapping(value.get("provenance"), f"{relative_path} provenance")
    for field in ("component_id", "component_version", "run_id"):
        if provenance.get(field) != producer[field]:
            raise ValidationError(f"producer provenance mismatch for {field}: {relative_path}")
    declared = value["integrity"]["self_sha256"]
    if entry.get("self_sha256") != declared:
        raise IntegrityError(f"producer manifest self-hash mismatch: {relative_path}")
    return ProducerItem(
        role=role,
        identity=identity,
        kind="PACKAGE",
        path=path,
        relative_path=relative_path,
        raw=raw,
        value=dict(value),
        physical_sha256=physical,
        self_sha256=declared,
    )


def _producer(value: Any) -> dict[str, str]:
    producer = _mapping(value, "producer")
    _require_exact_keys(producer, _PRODUCER_FIELDS, "producer")
    fields = ("component_id", "component_version", "run_id", "commit")
    result = {field: _string(producer.get(field), f"producer.{field}") for field in fields}
    return result


def _verify_self_hash(value: Mapping[str, Any], label: str) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping):
        raise IntegrityError(f"{label} integrity is invalid")
    _require_exact_keys(integrity, {"self_sha256"}, f"{label} integrity")
    if integrity.get("self_sha256") != self_sha256(value):
        raise IntegrityError(f"{label} self hash mismatch")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ValidationError(f"{label} fields mismatch: missing={missing}, extra={extra}")


__all__ = [
    "COMPLETE_ACCEPTED",
    "PACKAGE_SET_SCHEMA",
    "ProducerItem",
    "ProducerSet",
    "SYNTHETIC_COMPLETE",
    "load_producer_set",
]
