from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_bytes, calculate_self_sha256


class IntegrityError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise IntegrityError(f"cannot read artifact file {path}: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def seal_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(value, ensure_ascii=False))
    integrity = result.setdefault("integrity", {})
    if not isinstance(integrity, dict):
        raise IntegrityError("integrity must be an object")
    integrity["self_sha256"] = calculate_self_sha256(result)
    return result


def verify_self_hash(value: Mapping[str, Any], *, path: str = "$") -> None:
    if not isinstance(value, dict):
        raise IntegrityError(f"{path}: payload must be an object")
    integrity = value.get("integrity")
    if not isinstance(integrity, dict):
        raise IntegrityError(f"{path}.integrity: object is required")
    actual = calculate_self_sha256(value)
    expected = integrity.get("self_sha256")
    if expected != actual:
        raise IntegrityError(
            f"{path}.integrity.self_sha256 mismatch: expected {expected!r}, "
            f"computed {actual}"
        )


@dataclass(frozen=True)
class VerifiedArtifact:
    path: Path
    payload: dict[str, Any]
    self_sha256: str
    physical_sha256: str


def load_verified_json_artifact(
    path: Path,
    *,
    expected_self_sha256: str | None = None,
) -> VerifiedArtifact:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"cannot load JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IntegrityError(f"artifact {path} must contain a JSON object")
    verify_self_hash(payload, path=str(path))
    self_sha = payload["integrity"]["self_sha256"]
    if expected_self_sha256 is not None and self_sha != expected_self_sha256:
        raise IntegrityError(
            f"artifact {path} self hash mismatch: expected {expected_self_sha256}, "
            f"got {self_sha}"
        )
    return VerifiedArtifact(
        path=path,
        payload=payload,
        self_sha256=self_sha,
        physical_sha256=sha256_file(path),
    )


def require_nonzero_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise IntegrityError(f"{field}: expected lowercase SHA-256")
    if value != value.casefold() or any(c not in "0123456789abcdef" for c in value):
        raise IntegrityError(f"{field}: expected lowercase SHA-256")
    if value == "0" * 64:
        raise IntegrityError(f"{field}: all-zero hash is not an artifact binding")
    return value


def safe_relative_path(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise IntegrityError(f"{field}: relative path is required")
    if "\\" in value or value.startswith("/") or value.startswith("\\"):
        raise IntegrityError(f"{field}: path must use portable forward slashes")
    if len(value) >= 2 and value[1] == ":":
        raise IntegrityError(f"{field}: drive-qualified path is forbidden")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise IntegrityError(f"{field}: unsafe relative path")
    return value
