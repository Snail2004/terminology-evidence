from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class StrictJSONError(ValueError):
    """Raised when persisted JSON is ambiguous or structurally invalid."""


def loads_strict(
    payload: str | bytes,
    *,
    source: str = "<json>",
    require_object: bool = False,
) -> Any:
    if isinstance(payload, bytes):
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StrictJSONError(f"{source}: JSON is not valid UTF-8") from exc
    elif isinstance(payload, str):
        text = payload
    else:
        raise StrictJSONError(f"{source}: JSON payload must be text or bytes")

    def reject_constant(value: str) -> None:
        raise StrictJSONError(f"{source}: non-finite JSON number {value} is forbidden")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise StrictJSONError(f"{source}: duplicate object key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except StrictJSONError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJSONError(
            f"{source}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    _reject_non_finite_values(value, source=source)
    if require_object and not isinstance(value, dict):
        raise StrictJSONError(f"{source}: top-level JSON value must be an object")
    return value


def _reject_non_finite_values(value: Any, *, source: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise StrictJSONError(f"{source}: non-finite JSON number is forbidden")
    if isinstance(value, dict):
        for child in value.values():
            _reject_non_finite_values(child, source=source)
    elif isinstance(value, list):
        for child in value:
            _reject_non_finite_values(child, source=source)


def load_json_file(path: Path, *, require_object: bool = True) -> Any:
    target = Path(path)
    try:
        payload = target.read_bytes()
    except OSError as exc:
        raise StrictJSONError(f"{target}: cannot read JSON artifact: {exc}") from exc
    return loads_strict(
        payload,
        source=target.as_posix(),
        require_object=require_object,
    )


def load_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    target = Path(path)
    try:
        text = target.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StrictJSONError(f"{target}: JSONL is not valid UTF-8") from exc
    except OSError as exc:
        raise StrictJSONError(f"{target}: cannot read JSONL artifact: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        rows.append(
            loads_strict(
                line,
                source=f"{target.as_posix()}:{line_number}",
                require_object=True,
            )
        )
    return rows


__all__ = [
    "StrictJSONError",
    "load_json_file",
    "load_jsonl_objects",
    "loads_strict",
]
