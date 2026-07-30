"""Strict loaders for evaluation inputs and JSONL records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..jsonio import read_json, read_jsonl


class ArtifactError(ValueError):
    """Raised for an invalid persisted evaluation artifact."""


def load_json_artifact(
    path: Path,
    *,
    schema_id: str | None = None,
    schema_version: str | None = None,
) -> dict[str, Any]:
    value = read_json(path)
    if schema_id is not None and value.get("schema_id") != schema_id:
        raise ArtifactError(f"{path}: expected schema_id {schema_id}")
    if schema_version is not None and value.get("schema_version") != schema_version:
        raise ArtifactError(f"{path}: expected schema_version {schema_version}")
    return value


def load_jsonl_artifact(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path)


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return load_jsonl_artifact(path)
    value = read_json(path, require_object=False)
    if isinstance(value, list) and all(isinstance(row, dict) for row in value):
        return value
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        rows = value["rows"]
        if all(isinstance(row, dict) for row in rows):
            return rows
    raise ArtifactError(f"{path}: expected JSON array, rows object or JSONL")
