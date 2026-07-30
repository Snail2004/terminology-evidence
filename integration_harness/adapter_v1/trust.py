"""Hash-pinned Main and producer authority for official Harness intake."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from integration_harness.errors import IntegrityError, PolicyError, ValidationError
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.jsonio import canonical_bytes, load_json
from integration_harness.paths import ensure_no_symlink, ensure_plain_root, safe_relative_path


PROFILE_SCHEMA = "HarnessTrustedMainAuthorityProfileV1"
PROFILE_VERSION = "1.0.0"
ZERO_PROVIDER_PROFILE = "ZERO_PROVIDER_TRUST_PROFILE_ACCEPTED"
LIVE_PROFILE = "LIVE_AUTHORITY_APPROVED"

LIVE_AUTHORIZATION_SCHEMA_ID = "LiveAuthorizationReceiptV1_1"
RUN_START_SCHEMA_ID = "LiveRunStartReceiptV1_1"
RUN_STOP_SCHEMA_ID = "LiveRunStopReceiptV1_1"
LIVE_LEDGER_EVENT_SCHEMA_ID = "LiveLedgerEventV1_1"
LIVE_PROTOCOL_VERSION = "1.1.0-draft.4"

PROTOCOL_SCHEMA_PINS = {
    "live_authorization": {
        "schema_id": LIVE_AUTHORIZATION_SCHEMA_ID,
        "urn_name": "LIVE_AUTHORIZATION_RECEIPT_V1_1",
        "schema_version": LIVE_PROTOCOL_VERSION,
        "physical_sha256": "eb634481e279e096e1deb1967afa47db38661360eee161090f1cef470a62d2a1",
    },
    "run_stop": {
        "schema_id": RUN_STOP_SCHEMA_ID,
        "urn_name": "RUN_STOP_RECEIPT_V1_1",
        "schema_version": LIVE_PROTOCOL_VERSION,
        "physical_sha256": "2ee470708e26382a52bb64b298b1afe026f7bd3d099622e1d04759f1c3b8f3f0",
    },
    "run_start": {
        "schema_id": RUN_START_SCHEMA_ID,
        "urn_name": "RUN_START_RECEIPT_V1_1",
        "schema_version": LIVE_PROTOCOL_VERSION,
        "physical_sha256": "8073a337cc306a88a20f0d693580ad8238ecdad9888e5690b62398619c91a18d",
    },
    "ledger_event": {
        "schema_id": LIVE_LEDGER_EVENT_SCHEMA_ID,
        "urn_name": "LIVE_LEDGER_EVENT_V1_1",
        "schema_version": LIVE_PROTOCOL_VERSION,
        "physical_sha256": "4203087c27a605bbb824569604755317e2134a85ac9ee02c357a57df90230d55",
    },
}

_PROFILE_FIELDS = {
    "schema_id", "schema_version", "status", "issuer_id", "authority_id",
    "run_id", "phase_id", "split_id", "parent_dataset", "protocol",
    "producer_authorities", "main_run_authority", "final_glossary_decision",
    "integrity",
}
_PARENT_DATASET_FIELDS = {
    "zip_physical_sha256", "manifest_self_sha256", "sense_identity_sha256",
    "candidate_identity_sha256", "context_identity_sha256",
    "parent_candidate_count", "authorized_candidate_set_sha256",
}
_PROTOCOL_FIELDS = {"status", "commit", "tree", "schemas"}
_SCHEMA_DESCRIPTOR_FIELDS = {
    "kind", "schema_id", "schema_version", "relative_path", "physical_sha256",
}
_PRODUCER_AUTHORITY_FIELDS = {
    "role", "component_id", "component_version", "run_id", "commit", "tree",
    "source_manifest_self_sha256", "source_manifest_physical_sha256",
    "release_receipt_self_sha256", "release_receipt_physical_sha256",
    "approval_artifact_self_sha256", "approval_artifact_physical_sha256",
    "acceptance_receipt_self_sha256", "acceptance_receipt_physical_sha256",
}
_MAIN_RUN_AUTHORITY_FIELDS = {
    "live_authorization_receipt", "run_start_receipt", "run_stop_receipt",
    "stop_event",
}
_SELF_DESCRIPTOR_FIELDS = {"relative_path", "physical_sha256", "self_sha256"}
_EVENT_DESCRIPTOR_FIELDS = {"relative_path", "physical_sha256", "event_sha256"}
_HEX_40 = "0123456789abcdef"


@dataclass(frozen=True)
class BoundAuthorityFile:
    path: Path
    relative_path: str
    raw: bytes
    value: dict[str, Any]
    physical_sha256: str
    identity_sha256: str


@dataclass(frozen=True)
class TrustedAuthorityProfile:
    path: Path
    raw: bytes
    value: dict[str, Any]
    protocol_schemas: Mapping[str, BoundAuthorityFile]
    live_authorization: BoundAuthorityFile
    run_start: BoundAuthorityFile
    run_stop: BoundAuthorityFile
    stop_event: BoundAuthorityFile
    authority_files: tuple[tuple[Path, str], ...]

    @property
    def live_promoted(self) -> bool:
        return self.value["status"] == LIVE_PROFILE

    def producer(self, role: str) -> Mapping[str, Any]:
        for value in self.value["producer_authorities"]:
            if value["role"] == role:
                return value
        raise ValidationError(f"trusted authority profile does not admit producer role: {role}")


def load_trusted_authority_profile(
    profile_path: Path,
    *,
    expected_physical_sha256: str,
    expected_self_sha256: str,
    expected_issuer_id: str,
    expected_authority_id: str,
) -> TrustedAuthorityProfile:
    """Load an explicitly pinned profile; self-sealing alone is never authority."""

    root = ensure_plain_root(profile_path.parent)
    profile_path = ensure_no_symlink(root, safe_relative_path(profile_path.name))
    if not profile_path.is_file():
        raise ValidationError("trusted authority profile is missing")
    raw = profile_path.read_bytes()
    if sha256_bytes(raw) != expected_physical_sha256:
        raise IntegrityError("trusted authority profile physical hash mismatch")
    value = load_json(profile_path, require_object=True)
    _require_exact_keys(value, _PROFILE_FIELDS, "trusted authority profile")
    if value.get("schema_id") != PROFILE_SCHEMA or value.get("schema_version") != PROFILE_VERSION:
        raise ValidationError("unsupported trusted authority profile")
    if value.get("status") not in {ZERO_PROVIDER_PROFILE, LIVE_PROFILE}:
        raise PolicyError("trusted authority profile status is not admitted")
    _verify_self_hash(value, "trusted authority profile")
    if value["integrity"]["self_sha256"] != expected_self_sha256:
        raise IntegrityError("trusted authority profile self hash mismatch")
    if value.get("issuer_id") != expected_issuer_id:
        raise ValidationError("trusted authority profile issuer mismatch")
    if value.get("authority_id") != expected_authority_id:
        raise ValidationError("trusted authority profile authority mismatch")
    for field in ("run_id", "phase_id", "split_id"):
        _string(value.get(field), f"trusted authority profile {field}")
    if value.get("final_glossary_decision") is not None:
        raise PolicyError("trusted authority profile contains a final decision")
    parent = _mapping(value.get("parent_dataset"), "trusted parent Dataset")
    _require_exact_keys(parent, _PARENT_DATASET_FIELDS, "trusted parent Dataset")
    for field in _PARENT_DATASET_FIELDS - {"parent_candidate_count"}:
        _sha256(parent.get(field), f"trusted parent Dataset {field}")
    if not isinstance(parent.get("parent_candidate_count"), int) or parent["parent_candidate_count"] <= 0:
        raise ValidationError("trusted parent Dataset candidate count is invalid")

    protocol = _mapping(value.get("protocol"), "trusted Main protocol")
    _require_exact_keys(protocol, _PROTOCOL_FIELDS, "trusted Main protocol")
    if protocol.get("status") not in {
        "DRAFT4_PUBLIC_SURFACE_UNPROMOTED", "REVIEWED_LIVE_AUTHORITY"
    }:
        raise ValidationError("trusted Main protocol status is invalid")
    if value["status"] == LIVE_PROFILE and protocol["status"] != "REVIEWED_LIVE_AUTHORITY":
        raise PolicyError("live profile requires a reviewed Main protocol authority")
    _git_oid(protocol.get("commit"), "trusted Main protocol commit")
    _git_oid(protocol.get("tree"), "trusted Main protocol tree")
    schema_files = _load_protocol_schemas(root, protocol.get("schemas"))

    producer_values = value.get("producer_authorities")
    if not isinstance(producer_values, list) or len(producer_values) != 2:
        raise ValidationError("trusted authority profile requires both producer roles")
    if producer_values != sorted(producer_values, key=lambda item: str(item.get("role", ""))):
        raise IntegrityError("trusted producer authorities are not canonically sorted")
    observed_roles: set[str] = set()
    for producer_value in producer_values:
        producer = _mapping(producer_value, "trusted producer authority")
        _require_exact_keys(producer, _PRODUCER_AUTHORITY_FIELDS, "trusted producer authority")
        role = _string(producer.get("role"), "trusted producer role")
        if role not in {"context_evidence", "attestation_evidence"} or role in observed_roles:
            raise ValidationError("trusted producer role set is invalid")
        observed_roles.add(role)
        for field in ("component_id", "component_version", "run_id"):
            _string(producer.get(field), f"trusted producer {field}")
        for field in ("commit", "tree"):
            _git_oid(producer.get(field), f"trusted producer {field}")
        for field in _PRODUCER_AUTHORITY_FIELDS:
            if field.endswith("_sha256"):
                _sha256(producer.get(field), f"trusted producer {field}")

    main_run = _mapping(value.get("main_run_authority"), "trusted Main run authority")
    _require_exact_keys(main_run, _MAIN_RUN_AUTHORITY_FIELDS, "trusted Main run authority")
    authorization = _load_self_bound_file(
        root, main_run.get("live_authorization_receipt"), "Main live authorization"
    )
    run_start = _load_self_bound_file(
        root, main_run.get("run_start_receipt"), "Main run-start receipt"
    )
    run_stop = _load_self_bound_file(
        root, main_run.get("run_stop_receipt"), "Main run-stop receipt"
    )
    stop_event = _load_event_bound_file(root, main_run.get("stop_event"), "Main STOP_EVENT")
    _validate_jsonschema(authorization.value, schema_files["live_authorization"].value, "Main live authorization")
    _validate_jsonschema(run_start.value, schema_files["run_start"].value, "Main run-start receipt")
    _validate_jsonschema(run_stop.value, schema_files["run_stop"].value, "Main run-stop receipt")
    _validate_jsonschema(stop_event.value, schema_files["ledger_event"].value, "Main STOP_EVENT")
    _verify_main_run_chain(
        value, protocol, authorization, run_start, run_stop, stop_event
    )

    authority_files = [(profile_path, profile_path.name)]
    authority_files.extend(
        (item.path, item.relative_path)
        for item in [
            *schema_files.values(), authorization, run_start, run_stop, stop_event
        ]
    )
    return TrustedAuthorityProfile(
        path=profile_path,
        raw=raw,
        value=dict(value),
        protocol_schemas=schema_files,
        live_authorization=authorization,
        run_start=run_start,
        run_stop=run_stop,
        stop_event=stop_event,
        authority_files=tuple(authority_files),
    )


def _load_protocol_schemas(root: Path, value: Any) -> dict[str, BoundAuthorityFile]:
    if not isinstance(value, list) or len(value) != len(PROTOCOL_SCHEMA_PINS):
        raise ValidationError("trusted Main protocol schema inventory is incomplete")
    if value != sorted(value, key=lambda item: str(item.get("kind", ""))):
        raise IntegrityError("trusted Main protocol schemas are not canonically sorted")
    result: dict[str, BoundAuthorityFile] = {}
    for descriptor_value in value:
        descriptor = _mapping(descriptor_value, "trusted Main protocol schema")
        _require_exact_keys(descriptor, _SCHEMA_DESCRIPTOR_FIELDS, "trusted Main protocol schema")
        kind = _string(descriptor.get("kind"), "trusted Main protocol schema kind")
        expected = PROTOCOL_SCHEMA_PINS.get(kind)
        if expected is None or kind in result:
            raise ValidationError("trusted Main protocol schema kind is invalid")
        for field in ("schema_id", "schema_version", "physical_sha256"):
            if descriptor.get(field) != expected[field]:
                raise IntegrityError(f"trusted Main protocol schema pin mismatch: {kind}.{field}")
        relative = safe_relative_path(
            _string(descriptor.get("relative_path"), "trusted Main protocol schema path")
        )
        path = ensure_no_symlink(root, relative)
        if not path.is_file() or sha256_file(path) != expected["physical_sha256"]:
            raise IntegrityError(f"trusted Main protocol schema bytes differ: {kind}")
        schema = load_json(path, require_object=True)
        Draft202012Validator.check_schema(schema)
        if schema.get("$id") != (
            f"urn:terminology-evidence:live-run:{expected['urn_name']}:"
            f"{expected['schema_version']}"
        ):
            raise ValidationError(f"trusted Main protocol schema identity mismatch: {kind}")
        raw = path.read_bytes()
        result[kind] = BoundAuthorityFile(
            path=path,
            relative_path=relative.as_posix(),
            raw=raw,
            value=schema,
            physical_sha256=sha256_bytes(raw),
            identity_sha256=sha256_bytes(raw),
        )
    return result


def _load_self_bound_file(root: Path, value: Any, label: str) -> BoundAuthorityFile:
    descriptor = _mapping(value, f"{label} descriptor")
    _require_exact_keys(descriptor, _SELF_DESCRIPTOR_FIELDS, f"{label} descriptor")
    relative = safe_relative_path(_string(descriptor.get("relative_path"), f"{label} path"))
    path = ensure_no_symlink(root, relative)
    if not path.is_file() or sha256_file(path) != descriptor.get("physical_sha256"):
        raise IntegrityError(f"{label} physical binding mismatch")
    payload = load_json(path, require_object=True)
    _verify_self_hash(payload, label)
    if payload["integrity"]["self_sha256"] != descriptor.get("self_sha256"):
        raise IntegrityError(f"{label} self binding mismatch")
    return BoundAuthorityFile(
        path=path,
        relative_path=relative.as_posix(),
        raw=path.read_bytes(),
        value=payload,
        physical_sha256=str(descriptor["physical_sha256"]),
        identity_sha256=str(descriptor["self_sha256"]),
    )


def _load_event_bound_file(root: Path, value: Any, label: str) -> BoundAuthorityFile:
    descriptor = _mapping(value, f"{label} descriptor")
    _require_exact_keys(descriptor, _EVENT_DESCRIPTOR_FIELDS, f"{label} descriptor")
    relative = safe_relative_path(_string(descriptor.get("relative_path"), f"{label} path"))
    path = ensure_no_symlink(root, relative)
    if not path.is_file() or sha256_file(path) != descriptor.get("physical_sha256"):
        raise IntegrityError(f"{label} physical binding mismatch")
    payload = load_json(path, require_object=True)
    observed = _event_sha256(payload)
    if payload.get("event_sha256") != observed or descriptor.get("event_sha256") != observed:
        raise IntegrityError(f"{label} event hash mismatch")
    return BoundAuthorityFile(
        path=path,
        relative_path=relative.as_posix(),
        raw=path.read_bytes(),
        value=payload,
        physical_sha256=str(descriptor["physical_sha256"]),
        identity_sha256=observed,
    )


def _verify_main_run_chain(
    profile: Mapping[str, Any],
    protocol: Mapping[str, Any],
    authorization: BoundAuthorityFile,
    run_start: BoundAuthorityFile,
    run_stop: BoundAuthorityFile,
    stop_event: BoundAuthorityFile,
) -> None:
    auth = authorization.value
    start = run_start.value
    stop = run_stop.value
    event = stop_event.value
    if auth.get("issuer_id") != profile.get("issuer_id"):
        raise ValidationError("Main authorization issuer differs from trusted profile")
    if auth.get("authority_id") != profile.get("authority_id"):
        raise ValidationError("Main authorization authority differs from trusted profile")
    if auth.get("phase_id") != profile.get("phase_id"):
        raise ValidationError("Main authorization phase differs from trusted profile")
    bindings = _mapping(auth.get("bindings"), "Main authorization bindings")
    if (
        bindings.get("phase_authorized_candidate_set_self_sha256")
        != profile["parent_dataset"]["authorized_candidate_set_sha256"]
    ):
        raise IntegrityError("Main authorization candidate-set authority mismatch")
    if auth.get("protocol_commit") != protocol.get("commit"):
        raise ValidationError("Main authorization protocol commit mismatch")
    if auth.get("protocol_tree_git_oid") != protocol.get("tree"):
        raise ValidationError("Main authorization protocol tree mismatch")
    expected_auth_status = (
        "RUN_AUTHORIZED" if profile.get("status") == LIVE_PROFILE else "SYNTHETIC_TEST_ONLY"
    )
    if auth.get("authorization_status") != expected_auth_status:
        raise PolicyError("Main authorization status exceeds trusted profile status")
    now = datetime.now(timezone.utc)
    valid_from = _timestamp(auth.get("valid_from"), "Main authorization valid_from")
    valid_until = _timestamp(auth.get("valid_until"), "Main authorization valid_until")
    issued_at = _timestamp(auth.get("issued_at"), "Main authorization issued_at")
    start_at = _timestamp(start.get("issued_at"), "Main run-start issued_at")
    stop_at = _timestamp(stop.get("issued_at"), "Main run-stop issued_at")
    if not (valid_from <= issued_at <= start_at <= stop_at < valid_until):
        raise PolicyError("Main authorization/run chronology is invalid")
    if now >= valid_until:
        raise PolicyError("Main authorization is expired")
    if start.get("phase_id") != profile.get("phase_id"):
        raise ValidationError("Main run-start phase mismatch")
    if start.get("authorization_receipt_self_sha256") != authorization.identity_sha256:
        raise IntegrityError("Main run-start does not bind authorization self hash")
    if start.get("authorization_receipt_physical_sha256") != authorization.physical_sha256:
        raise IntegrityError("Main run-start does not bind authorization bytes")
    if (
        start.get("phase_authorized_candidate_set_self_sha256")
        != profile["parent_dataset"]["authorized_candidate_set_sha256"]
    ):
        raise IntegrityError("Main run-start candidate-set authority mismatch")
    for field in ("run_spec_self_sha256", "run_spec_physical_sha256"):
        if start.get(field) != bindings.get(field):
            raise IntegrityError(f"Main run-start {field} binding mismatch")
    if start.get("budget_spec_sha256") != auth.get("budget_spec_sha256"):
        raise IntegrityError("Main run-start budget binding mismatch")
    if (
        start.get("secret_readiness_receipt_sha256")
        != auth.get("secret_readiness_receipt_sha256")
        or start.get("secret_readiness_receipt_self_sha256")
        != auth.get("secret_readiness_receipt_self_sha256")
    ):
        raise IntegrityError("Main run-start secret-readiness binding mismatch")
    if stop.get("phase_id") != profile.get("phase_id"):
        raise ValidationError("Main run-stop phase mismatch")
    if stop.get("authorization_receipt_self_sha256") != authorization.identity_sha256:
        raise IntegrityError("Main run-stop does not bind authorization")
    if stop.get("run_start_receipt_self_sha256") != run_start.identity_sha256:
        raise IntegrityError("Main run-stop does not bind run-start")
    if stop.get("terminal_status") != "EXTERNAL_HOLD":
        raise PolicyError("trusted external hold requires Main EXTERNAL_HOLD terminal status")
    if event.get("event_kind") != "STOP_EVENT" or event.get("producer") != "main_protocol":
        raise ValidationError("trusted Main event is not a protocol STOP_EVENT")
    if event.get("phase_id") != profile.get("phase_id"):
        raise ValidationError("Main STOP_EVENT phase mismatch")
    if event.get("run_id") != profile.get("run_id"):
        raise ValidationError("Main STOP_EVENT run mismatch")
    if stop.get("issued_at") != event.get("issued_at"):
        raise ValidationError("Main run-stop timestamp differs from STOP_EVENT")
    if stop.get("final_ledger_head_sha256") != stop_event.identity_sha256:
        raise IntegrityError("Main run-stop does not bind STOP_EVENT as final ledger head")
    if stop.get("stop_reason") != event.get("stop_reason"):
        raise ValidationError("Main run-stop reason differs from STOP_EVENT")


def _validate_jsonschema(value: Mapping[str, Any], schema: Mapping[str, Any], label: str) -> None:
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "$"
        raise ValidationError(f"{label} schema validation failed at {path}: {first.message}")


def _timestamp(value: Any, label: str) -> datetime:
    observed = _string(value, label)
    try:
        parsed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{label} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValidationError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _event_sha256(value: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(value))
    payload.pop("event_sha256", None)
    return sha256_bytes(canonical_bytes(payload))


def _verify_self_hash(value: Mapping[str, Any], label: str) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or integrity.get("self_sha256") != self_sha256(value):
        raise IntegrityError(f"{label} self hash mismatch")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def _sha256(value: Any, label: str) -> str:
    observed = _string(value, label)
    if len(observed) != 64 or any(char not in _HEX_40 for char in observed):
        raise ValidationError(f"{label} must be a lowercase SHA256")
    return observed


def _git_oid(value: Any, label: str) -> str:
    observed = _string(value, label)
    if len(observed) != 40 or any(char not in _HEX_40 for char in observed):
        raise ValidationError(f"{label} must be a full lowercase Git OID")
    return observed


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        raise ValidationError(
            f"{label} fields mismatch: missing={sorted(expected-observed)}, "
            f"extra={sorted(observed-expected)}"
        )


__all__ = [
    "LIVE_PROFILE",
    "PROFILE_SCHEMA",
    "PROTOCOL_SCHEMA_PINS",
    "TrustedAuthorityProfile",
    "ZERO_PROVIDER_PROFILE",
    "load_trusted_authority_profile",
]
