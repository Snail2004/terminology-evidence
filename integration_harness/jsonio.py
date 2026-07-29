"""Strict, deterministic JSON I/O used for persisted harness artifacts."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

from .errors import IntegrityError


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IntegrityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise IntegrityError(f"non-finite JSON constant: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise IntegrityError("non-finite JSON number")
    return parsed


def loads_strict(raw: bytes | str, *, require_object: bool = False) -> Any:
    """Parse UTF-8 JSON while rejecting duplicate keys and non-finite values."""

    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise IntegrityError("JSON is not valid UTF-8") from exc
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except IntegrityError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"invalid JSON: {exc}") from exc
    if require_object and not isinstance(value, dict):
        raise IntegrityError("JSON root must be an object")
    return value


def load_json(path: Path, *, require_object: bool = False) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise IntegrityError(f"cannot read JSON artifact {path}: {exc}") from exc
    return loads_strict(raw, require_object=require_object)


def canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise IntegrityError(f"cannot canonicalize JSON: {exc}") from exc
    return text.encode("utf-8")


def dump_json(path: Path, value: Any, *, exclusive: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "xb" if exclusive else "wb"
    try:
        with path.open(mode) as stream:
            stream.write(canonical_bytes(value))
            stream.write(b"\n")
    except FileExistsError as exc:
        raise IntegrityError(f"refusing to overwrite artifact: {path}") from exc


def without_self_hash(value: Any) -> Any:
    """Return a deep copy with the conventional integrity self hash removed."""

    result = copy.deepcopy(value)
    integrity = result.get("integrity") if isinstance(result, dict) else None
    if isinstance(integrity, dict):
        integrity.pop("self_sha256", None)
    return result
