from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class DuplicateJsonKeyError(ValueError):
    pass


def strict_json_loads_unique(text: str) -> Any:
    def parse_finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("non-finite JSON number is forbidden: exponent overflow")
        return parsed

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON number is forbidden: {value}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateJsonKeyError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result

    return json.loads(
        text,
        parse_constant=reject_constant,
        parse_float=parse_finite_float,
        object_pairs_hook=unique_object,
    )


def load_json_object(path: Path) -> dict[str, Any]:
    value = strict_json_loads_unique(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return value


def assert_strict_json_file(path: Path) -> None:
    load_json_object(path)
