from __future__ import annotations

from pathlib import Path
from typing import Any

from terminology_contracts.integrity import verify_self_hash
from terminology_contracts.validation import validate_instance

from ..errors import InputValidationError, IntegrityValidationError
from ..jsonio import load_json_object


def load_contract_artifact(
    path: Path,
    *,
    schema_dir: Path,
    gate_policy_path: Path | None = None,
    feature_registry_path: Path | None = None,
) -> dict[str, Any]:
    try:
        value = load_json_object(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise InputValidationError(f"cannot load JSON artifact {path}: {exc}") from exc
    try:
        verify_self_hash(value, path=str(path))
    except ValueError as exc:
        raise IntegrityValidationError(str(exc)) from exc
    errors = validate_instance(
        value,
        schema_dir,
        gate_policy_path=gate_policy_path,
        feature_registry_path=feature_registry_path,
    )
    if errors:
        raise InputValidationError(f"{path}: " + "; ".join(errors))
    return value


def load_and_validate_global_input(
    path: Path,
    *,
    schema_dir: Path,
    gate_policy_path: Path,
    feature_registry_path: Path,
) -> dict[str, Any]:
    value = load_contract_artifact(
        path,
        schema_dir=schema_dir,
        gate_policy_path=gate_policy_path,
        feature_registry_path=feature_registry_path,
    )
    if value.get("schema_id") != "GlobalValidatorInputV1":
        raise InputValidationError("expected GlobalValidatorInputV1")
    if value.get("schema_version") != "1.1.0":
        raise InputValidationError("runtime accepts only schema_version=1.1.0")
    if value.get("assembly_metadata", {}).get("binding_status") != "COMPLETE":
        raise InputValidationError("runtime accepts only COMPLETE global inputs")
    return value
