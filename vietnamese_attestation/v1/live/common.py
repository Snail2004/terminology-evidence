"""Shared deterministic and fail-closed helpers for the E live tooling."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..strict_json import load_strict_json, strict_json_loads


LIVE_TOOL_SCHEMA_VERSION = "1.0.0"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class LiveSchemaError(ValueError):
    """Raised when a live sidecar or request violates its contract."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            .encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise LiveSchemaError("value is not canonically JSON serializable") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal(value: Mapping[str, Any], *, field: str = "self_sha256") -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    integrity = payload.setdefault("integrity", {})
    if not isinstance(integrity, dict):
        raise LiveSchemaError("integrity must be an object")
    integrity.pop(field, None)
    integrity[field] = canonical_sha256(payload)
    return payload


def verify_seal(
    value: Mapping[str, Any], *, field: str = "self_sha256"
) -> bool:
    integrity = value.get("integrity")
    return isinstance(integrity, Mapping) and integrity.get(field) == canonical_sha256(
        {**dict(value), "integrity": {key: item for key, item in integrity.items() if key != field}}
    )


def load_object(path: str | Path) -> dict[str, Any]:
    value = load_strict_json(Path(path))
    if not isinstance(value, dict):
        raise LiveSchemaError(f"JSON object required: {path}")
    return value


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LiveSchemaError(f"JSONL is not UTF-8: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise LiveSchemaError(f"blank JSONL row at line {line_number}")
        try:
            value = strict_json_loads(line)
        except ValueError as exc:
            raise LiveSchemaError(f"invalid JSONL at line {line_number}") from exc
        if not isinstance(value, dict):
            raise LiveSchemaError(f"JSONL row {line_number} must be an object")
        rows.append(value)
    return rows


def require_keys(
    value: Mapping[str, Any], required: set[str], *, path: str = "$"
) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise LiveSchemaError(f"{path} missing keys: {', '.join(missing)}")


def require_string(value: Any, *, path: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise LiveSchemaError(f"{path} must be a nonempty string")
    return value


def require_identifier(value: Any, *, path: str) -> str:
    result = require_string(value, path=path)
    if not IDENTIFIER_RE.fullmatch(result):
        raise LiveSchemaError(f"{path} must be a path-safe identifier")
    return result


def require_sha256(value: Any, *, path: str) -> str:
    result = require_string(value, path=path)
    if not SHA256_RE.fullmatch(result):
        raise LiveSchemaError(f"{path} must be a lowercase SHA-256")
    return result


def require_bool(value: Any, *, path: str) -> bool:
    if not isinstance(value, bool):
        raise LiveSchemaError(f"{path} must be boolean")
    return value


def require_nonnegative_int(value: Any, *, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LiveSchemaError(f"{path} must be a nonnegative integer")
    return value


def require_positive_int(value: Any, *, path: str) -> int:
    result = require_nonnegative_int(value, path=path)
    if result == 0:
        raise LiveSchemaError(f"{path} must be positive")
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_relative_path(value: Any, *, path: str = "$.path") -> str:
    if not isinstance(value, str) or not value:
        raise LiveSchemaError(f"{path} must be a relative POSIX path")
    if "\\" in value or ":" in value or value.startswith("/"):
        raise LiveSchemaError(f"{path} is not canonical POSIX form")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise LiveSchemaError(f"{path} contains an unsafe segment")
    return value


def binding_for_file(path: str | Path) -> dict[str, str]:
    resolved = Path(path).resolve(strict=True)
    raw = resolved.read_bytes()
    return {
        "physical_sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": str(len(raw)),
    }


__all__ = [
    "LIVE_TOOL_SCHEMA_VERSION",
    "LiveSchemaError",
    "IDENTIFIER_RE",
    "SHA256_RE",
    "binding_for_file",
    "canonical_bytes",
    "canonical_sha256",
    "file_sha256",
    "load_jsonl",
    "load_object",
    "require_bool",
    "require_identifier",
    "require_keys",
    "require_nonnegative_int",
    "require_positive_int",
    "require_sha256",
    "require_string",
    "safe_relative_path",
    "seal",
    "utc_now",
    "verify_seal",
]
