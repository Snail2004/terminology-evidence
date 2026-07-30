"""Load exact Main-supplied authority receipts without granting authority locally."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from ...strict_json import reject_link
from ..common import (
    LIVE_TOOL_SCHEMA_VERSION,
    LiveSchemaError,
    canonical_sha256,
    file_sha256,
    load_object,
    require_exact_keys,
    require_sha256,
    require_string,
    seal,
    verify_seal,
)

PROFILE_SCHEMA_ID = "ETrustedAuthorityProfileV1"
EXTERNAL_RECEIPT_SCHEMA_ID = "EExternalAuthorityReceiptV1"
LOADED_BUNDLE_SCHEMA_ID = "ELoadedAuthorityBundleV1"
EXTERNAL_RECEIPT_ROLES = frozenset(
    {"REGISTRY_APPROVAL", "POLICY_APPROVAL", "CORPUS_ACQUISITION_AUTHORIZATION"}
)
PROTOCOL_SCHEMA_ROLES = frozenset(
    {"LIVE_AUTHORIZATION_RECEIPT", "RUN_STOP_RECEIPT", "LIVE_LEDGER_EVENT"}
)


def make_external_authority_receipt(
    *,
    receipt_id: str,
    role: str,
    issuer_id: str,
    authority_id: str,
    subject_self_sha256: str,
    subject_physical_sha256: str,
    status: str = "DRAFT_FIXTURE_ONLY",
) -> dict[str, Any]:
    return seal(
        {
            "schema_id": EXTERNAL_RECEIPT_SCHEMA_ID,
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "receipt_id": receipt_id,
            "role": role,
            "status": status,
            "issuer_id": issuer_id,
            "authority_id": authority_id,
            "subject_self_sha256": subject_self_sha256,
            "subject_physical_sha256": subject_physical_sha256,
            "integrity": {},
        }
    )


def make_trusted_authority_profile(
    *,
    trusted_issuers: list[str],
    trusted_authorities: list[str],
    receipt_bindings: list[Mapping[str, Any]],
    protocol_schema_bindings: list[Mapping[str, Any]] | None = None,
    status: str = "DRAFT_FIXTURE_ONLY",
) -> dict[str, Any]:
    return seal(
        {
            "schema_id": PROFILE_SCHEMA_ID,
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "profile_id": "e-trusted-authority-profile-v1",
            "status": status,
            "trusted_issuers": sorted(set(trusted_issuers)),
            "trusted_authorities": sorted(set(trusted_authorities)),
            "receipt_bindings": sorted(
                (dict(row) for row in receipt_bindings), key=lambda row: str(row["role"])
            ),
            "protocol_schema_bindings": sorted(
                (dict(row) for row in (protocol_schema_bindings or [])),
                key=lambda row: str(row["role"]),
            ),
            "integrity": {},
        }
    )


def validate_authority_profile(value: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "profile_id",
            "status",
            "trusted_issuers",
            "trusted_authorities",
            "receipt_bindings",
            "protocol_schema_bindings",
            "integrity",
        },
    )
    if value["schema_id"] != PROFILE_SCHEMA_ID or value["schema_version"] != LIVE_TOOL_SCHEMA_VERSION:
        raise LiveSchemaError("trusted authority profile identity mismatch")
    if value["status"] not in {"DRAFT_FIXTURE_ONLY", "MAIN_PINNED_RUNTIME_AUTHORITY"}:
        raise LiveSchemaError("trusted authority profile status is unsupported")
    for key in ("trusted_issuers", "trusted_authorities"):
        rows = value[key]
        if not isinstance(rows, list) or not rows or rows != sorted(set(rows)):
            raise LiveSchemaError(f"{key} must be a sorted unique nonempty list")
        for index, item in enumerate(rows):
            require_string(item, path=f"$.{key}[{index}]")
    receipt_bindings = _validate_bindings(
        value["receipt_bindings"], roles=EXTERNAL_RECEIPT_ROLES, path="$.receipt_bindings"
    )
    protocol_bindings = _validate_bindings(
        value["protocol_schema_bindings"],
        roles=PROTOCOL_SCHEMA_ROLES,
        path="$.protocol_schema_bindings",
        allow_empty=value["status"] == "DRAFT_FIXTURE_ONLY",
    )
    _validate_integrity(value["integrity"])
    if not verify_seal(value):
        raise LiveSchemaError("trusted authority profile self hash mismatch")
    result = dict(value)
    result["receipt_bindings"] = receipt_bindings
    result["protocol_schema_bindings"] = protocol_bindings
    return result


def load_authority_bundle(
    *,
    profile_path: str | Path,
    receipt_paths: Mapping[str, str | Path],
    protocol_schema_paths: Mapping[str, str | Path] | None = None,
    execution_mode: str = "LOCAL_FIXTURE_ONLY",
    expected_profile_physical_sha256: str | None = None,
) -> dict[str, Any]:
    """Load exact receipt/schema bytes and return only verified hash bindings."""
    profile_file = _regular_file(profile_path)
    if expected_profile_physical_sha256 is not None:
        require_sha256(expected_profile_physical_sha256, path="$.expected_profile_physical_sha256")
        if file_sha256(profile_file) != expected_profile_physical_sha256:
            raise LiveSchemaError("trusted authority profile physical hash mismatch")
    profile = validate_authority_profile(load_object(profile_file))
    if execution_mode not in {"LOCAL_FIXTURE_ONLY", "PRODUCTION_AUTHORITY"}:
        raise LiveSchemaError("authority execution mode is unsupported")
    if execution_mode == "PRODUCTION_AUTHORITY" and profile["status"] != "MAIN_PINNED_RUNTIME_AUTHORITY":
        raise LiveSchemaError("local/draft authority profile is forbidden in production mode")
    if execution_mode == "PRODUCTION_AUTHORITY" and expected_profile_physical_sha256 is None:
        raise LiveSchemaError("production authority profile requires an external physical hash pin")
    expected_receipts = {row["role"]: row for row in profile["receipt_bindings"]}
    if set(receipt_paths) != set(expected_receipts):
        raise LiveSchemaError("external authority receipt role set mismatch")
    loaded_receipts: dict[str, dict[str, Any]] = {}
    for role in sorted(expected_receipts):
        binding = expected_receipts[role]
        path = _regular_file(receipt_paths[role])
        if path.name != binding["artifact_ref"]:
            raise LiveSchemaError(f"external authority receipt filename mismatch: {role}")
        if file_sha256(path) != binding["artifact_physical_sha256"]:
            raise LiveSchemaError(f"external authority receipt physical hash mismatch: {role}")
        receipt = _validate_external_receipt(load_object(path), role=role)
        if receipt["integrity"]["self_sha256"] != binding["artifact_self_sha256"]:
            raise LiveSchemaError(f"external authority receipt self hash mismatch: {role}")
        if receipt["issuer_id"] not in profile["trusted_issuers"] or receipt["authority_id"] not in profile["trusted_authorities"]:
            raise LiveSchemaError(f"external authority issuer is not trusted: {role}")
        required_status = "MAIN_PINNED_APPROVED" if execution_mode == "PRODUCTION_AUTHORITY" else "DRAFT_FIXTURE_ONLY"
        if receipt["status"] != required_status:
            raise LiveSchemaError(f"external authority receipt status mismatch: {role}")
        loaded_receipts[role] = {
            "artifact_ref": path.name,
            "artifact_physical_sha256": file_sha256(path),
            "artifact_self_sha256": receipt["integrity"]["self_sha256"],
            "issuer_id": receipt["issuer_id"],
            "authority_id": receipt["authority_id"],
        }
    loaded_schemas = _load_protocol_schemas(
        profile, protocol_schema_paths or {}, execution_mode=execution_mode
    )
    bundle = seal(
        {
            "schema_id": LOADED_BUNDLE_SCHEMA_ID,
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "execution_mode": execution_mode,
            "profile_binding": {
                "artifact_ref": profile_file.name,
                "artifact_physical_sha256": file_sha256(profile_file),
                "artifact_self_sha256": profile["integrity"]["self_sha256"],
                "status": profile["status"],
            },
            "receipt_bindings": loaded_receipts,
            "protocol_schema_bindings": loaded_schemas,
            "integrity": {},
        }
    )
    return validate_loaded_authority_bundle(bundle)


def validate_loaded_authority_bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "execution_mode",
            "profile_binding",
            "receipt_bindings",
            "protocol_schema_bindings",
            "integrity",
        },
    )
    if value["schema_id"] != LOADED_BUNDLE_SCHEMA_ID or value["schema_version"] != LIVE_TOOL_SCHEMA_VERSION:
        raise LiveSchemaError("loaded authority bundle identity mismatch")
    if value["execution_mode"] not in {"LOCAL_FIXTURE_ONLY", "PRODUCTION_AUTHORITY"}:
        raise LiveSchemaError("loaded authority bundle mode is unsupported")
    profile = value["profile_binding"]
    require_exact_keys(profile, {"artifact_ref", "artifact_physical_sha256", "artifact_self_sha256", "status"}, path="$.profile_binding")
    for key in ("artifact_physical_sha256", "artifact_self_sha256"):
        require_sha256(profile[key], path=f"$.profile_binding.{key}")
    require_string(profile["artifact_ref"], path="$.profile_binding.artifact_ref")
    if profile["status"] not in {"DRAFT_FIXTURE_ONLY", "MAIN_PINNED_RUNTIME_AUTHORITY"}:
        raise LiveSchemaError("loaded authority profile status is unsupported")
    receipts = value["receipt_bindings"]
    if not isinstance(receipts, Mapping) or set(receipts) != set(EXTERNAL_RECEIPT_ROLES):
        raise LiveSchemaError("loaded authority receipt set is incomplete")
    for role, binding in receipts.items():
        require_exact_keys(binding, {"artifact_ref", "artifact_physical_sha256", "artifact_self_sha256", "issuer_id", "authority_id"}, path=f"$.receipt_bindings.{role}")
        require_string(binding["artifact_ref"], path=f"$.receipt_bindings.{role}.artifact_ref")
        for key in ("artifact_physical_sha256", "artifact_self_sha256"):
            require_sha256(binding[key], path=f"$.receipt_bindings.{role}.{key}")
        for key in ("issuer_id", "authority_id"):
            require_string(binding[key], path=f"$.receipt_bindings.{role}.{key}")
    schemas = value["protocol_schema_bindings"]
    if not isinstance(schemas, Mapping):
        raise LiveSchemaError("loaded protocol schema bindings must be an object")
    for role, binding in schemas.items():
        if role not in PROTOCOL_SCHEMA_ROLES:
            raise LiveSchemaError("loaded protocol schema role is unsupported")
        require_exact_keys(binding, {"artifact_ref", "artifact_physical_sha256", "artifact_self_sha256"}, path=f"$.protocol_schema_bindings.{role}")
        require_string(binding["artifact_ref"], path=f"$.protocol_schema_bindings.{role}.artifact_ref")
        for key in ("artifact_physical_sha256", "artifact_self_sha256"):
            require_sha256(binding[key], path=f"$.protocol_schema_bindings.{role}.{key}")
    _validate_integrity(value["integrity"])
    if not verify_seal(value):
        raise LiveSchemaError("loaded authority bundle self hash mismatch")
    return dict(value)


def validate_protocol_instance(
    value: Mapping[str, Any], *, role: str, schema_path: str | Path
) -> dict[str, Any]:
    if role not in PROTOCOL_SCHEMA_ROLES:
        raise LiveSchemaError("unknown Draft4 protocol schema role")
    schema = load_object(_regular_file(schema_path))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise LiveSchemaError(f"Draft4 protocol instance is invalid for {role}: {errors[0].message}")
    return dict(value)


def _validate_external_receipt(value: Mapping[str, Any], *, role: str) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "receipt_id",
            "role",
            "status",
            "issuer_id",
            "authority_id",
            "subject_self_sha256",
            "subject_physical_sha256",
            "integrity",
        },
    )
    if value["schema_id"] != EXTERNAL_RECEIPT_SCHEMA_ID or value["schema_version"] != LIVE_TOOL_SCHEMA_VERSION:
        raise LiveSchemaError("external authority receipt identity mismatch")
    if value["role"] != role or role not in EXTERNAL_RECEIPT_ROLES:
        raise LiveSchemaError("external authority receipt role mismatch")
    if value["status"] not in {"DRAFT_FIXTURE_ONLY", "MAIN_PINNED_APPROVED"}:
        raise LiveSchemaError("external authority receipt status is unsupported")
    for key in ("receipt_id", "issuer_id", "authority_id"):
        require_string(value[key], path=f"$.{key}")
    for key in ("subject_self_sha256", "subject_physical_sha256"):
        require_sha256(value[key], path=f"$.{key}")
    _validate_integrity(value["integrity"])
    if not verify_seal(value):
        raise LiveSchemaError("external authority receipt self hash mismatch")
    return dict(value)


def _validate_bindings(
    value: Any,
    *,
    roles: frozenset[str],
    path: str,
    allow_empty: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise LiveSchemaError(f"{path} must be a nonempty list")
    normalized = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise LiveSchemaError(f"{path}[{index}] must be an object")
        require_exact_keys(
            raw,
            {"role", "artifact_ref", "artifact_physical_sha256", "artifact_self_sha256"},
            path=f"{path}[{index}]",
        )
        if raw["role"] not in roles:
            raise LiveSchemaError(f"{path}[{index}].role is unsupported")
        require_string(raw["artifact_ref"], path=f"{path}[{index}].artifact_ref")
        require_sha256(raw["artifact_physical_sha256"], path=f"{path}[{index}].artifact_physical_sha256")
        require_sha256(raw["artifact_self_sha256"], path=f"{path}[{index}].artifact_self_sha256")
        normalized.append(dict(raw))
    if [row["role"] for row in normalized] != sorted({row["role"] for row in normalized}):
        raise LiveSchemaError(f"{path} must be sorted with unique roles")
    if normalized and {row["role"] for row in normalized} != set(roles):
        raise LiveSchemaError(f"{path} must cover the exact role set")
    return normalized


def _load_protocol_schemas(
    profile: Mapping[str, Any],
    paths: Mapping[str, str | Path],
    *,
    execution_mode: str,
) -> dict[str, dict[str, Any]]:
    expected = {row["role"]: row for row in profile["protocol_schema_bindings"]}
    if not expected and execution_mode == "LOCAL_FIXTURE_ONLY":
        if paths:
            raise LiveSchemaError("unbound Draft4 protocol schema paths were supplied")
        return {}
    if set(paths) != set(expected):
        raise LiveSchemaError("Draft4 protocol schema role set mismatch")
    loaded = {}
    for role in sorted(expected):
        path = _regular_file(paths[role])
        binding = expected[role]
        if file_sha256(path) != binding["artifact_physical_sha256"]:
            raise LiveSchemaError(f"Draft4 protocol schema physical hash mismatch: {role}")
        schema = load_object(path)
        if str(schema.get("$id", "")) != binding["artifact_ref"]:
            raise LiveSchemaError(f"Draft4 protocol schema identity mismatch: {role}")
        if canonical_sha256(schema) != binding["artifact_self_sha256"]:
            raise LiveSchemaError(f"Draft4 protocol schema canonical hash mismatch: {role}")
        loaded[role] = {
            "artifact_ref": binding["artifact_ref"],
            "artifact_physical_sha256": binding["artifact_physical_sha256"],
            "artifact_self_sha256": binding["artifact_self_sha256"],
        }
    return loaded


def _regular_file(path: str | Path) -> Path:
    supplied = Path(path).absolute()
    reject_link(supplied)
    resolved = supplied.resolve(strict=True)
    reject_link(resolved)
    if not resolved.is_file():
        raise LiveSchemaError(f"authority artifact is not a regular file: {path}")
    return resolved


def _validate_integrity(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise LiveSchemaError("integrity must be an object")
    require_exact_keys(value, {"self_sha256"}, path="$.integrity")
    require_sha256(value["self_sha256"], path="$.integrity.self_sha256")


__all__ = [
    "EXTERNAL_RECEIPT_ROLES",
    "LOADED_BUNDLE_SCHEMA_ID",
    "PROFILE_SCHEMA_ID",
    "load_authority_bundle",
    "make_external_authority_receipt",
    "make_trusted_authority_profile",
    "validate_authority_profile",
    "validate_protocol_instance",
]
