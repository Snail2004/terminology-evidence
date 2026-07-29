"""Public-contract package checks without importing producer internals."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .errors import PolicyError, ValidationError
from .hashing import self_sha256
from .identity import CandidateIdentity
from .inventory import ArtifactRecord
from .jsonio import load_json


ROLE_SCHEMA = {
    "effective_sense": "EffectiveSenseContractV1",
    "frozen_candidate": "FrozenCandidateContractV1",
    "constraints": "ConstraintEvidencePackageV1",
    "context_evidence": "ContextEvidencePackageV1",
    "attestation_evidence": "AttestationEvidencePackageV1",
}


def _validate_jsonschema(value: dict[str, Any], schema_root: Path | None) -> None:
    if schema_root is None:
        return
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:  # pragma: no cover - environment gate reports this
        raise ValidationError("jsonschema is required for schema validation") from exc
    schema_path = (schema_root / "schemas" / "current" / _schema_filename(value["schema_id"])).resolve()
    if not schema_path.is_file():
        raise ValidationError(f"schema is unavailable: {schema_path}")
    schema = load_json(schema_path, require_object=True)
    store: dict[str, dict[str, Any]] = {}
    for candidate in schema_path.parent.glob("*.schema.json"):
        loaded = load_json(candidate, require_object=True)
        schema_id = loaded.get("$id")
        if isinstance(schema_id, str):
            store[schema_id] = loaded
    registry = Registry()
    for schema_id, loaded in store.items():
        registry = registry.with_resource(schema_id, Resource.from_contents(loaded))
    try:
        jsonschema.Draft202012Validator(schema, registry=registry).validate(value)
    except jsonschema.ValidationError as exc:
        raise ValidationError(f"schema validation failed: {exc.message}") from exc


def _schema_filename(schema_id: str) -> str:
    names = {
        "EffectiveSenseContractV1": "effective_sense_contract.schema.json",
        "FrozenCandidateContractV1": "frozen_candidate_contract.schema.json",
        "ConstraintEvidencePackageV1": "constraint_evidence_package.schema.json",
        "ContextEvidencePackageV1": "context_evidence_package.schema.json",
        "AttestationEvidencePackageV1": "attestation_evidence_package.schema.json",
    }
    try:
        return names[schema_id]
    except KeyError as exc:
        raise ValidationError(f"unknown contract schema: {schema_id}") from exc


def validate_package(record: ArtifactRecord, *, schema_root: Path | None = None) -> tuple[dict[str, Any], CandidateIdentity | None]:
    value = load_json(record.path, require_object=True)
    expected_schema = ROLE_SCHEMA.get(record.role)
    if expected_schema is None:
        raise ValidationError(f"unknown artifact role: {record.role}")
    if value.get("schema_id") != expected_schema:
        raise ValidationError(f"{record.relative_path}: schema role mismatch")
    if value.get("schema_version") != "1.1.0":
        raise ValidationError(f"{record.relative_path}: unsupported schema version")
    integrity = value.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("self_sha256") != self_sha256(value):
        raise ValidationError(f"{record.relative_path}: self hash mismatch")
    _validate_jsonschema(value, schema_root)
    if record.role == "effective_sense":
        if not isinstance(record.candidate_key, dict):
            raise ValidationError(f"{record.relative_path}: effective sense requires manifest candidate_key")
        expected = record.candidate_key
        for field in ("source_term", "sense_id", "scope_id", "sense_inventory_version", "dataset_manifest_sha256"):
            observed = value.get("parent_dataset_manifest_sha256") if field == "dataset_manifest_sha256" else value.get(field)
            if observed != expected.get(field):
                raise ValidationError(f"{record.relative_path}: effective sense identity mismatch for {field}")
        if value["integrity"]["self_sha256"] != expected.get("effective_sense_contract_sha256"):
            raise ValidationError(f"{record.relative_path}: effective sense self hash is not bound to candidate key")
        identity = None
    else:
        identity = CandidateIdentity.from_package(value)
    if record.candidate_key is not None and identity is not None:
        observed = {key: identity.as_dict().get(key) for key in record.candidate_key}
        if observed != record.candidate_key:
            raise PolicyError(f"{record.relative_path}: manifest/package identity mismatch")
    if record.declared_self_sha256 is not None and record.declared_self_sha256 != integrity["self_sha256"]:
        raise ValidationError(f"{record.relative_path}: manifest self hash mismatch")
    if record.role in {"frozen_candidate", "constraints"} and value.get("binding_status") != "COMPLETE":
        raise PolicyError(f"{record.relative_path}: package is not COMPLETE")
    if record.role in {"context_evidence", "attestation_evidence"}:
        if value.get("final_glossary_decision") is not None:
            raise PolicyError(f"{record.relative_path}: producer owns a final glossary decision")
        if "global_action" in value or "global_decision" in value:
            raise PolicyError(f"{record.relative_path}: producer emitted a global action")
    return value, identity
