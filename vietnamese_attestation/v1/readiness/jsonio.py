"""Strict persisted-data decoding and safe artifact path handling."""

from __future__ import annotations

import json
import math
import os
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any


def strict_json_loads(text: str) -> Any:
    """Decode one complete JSON value with recursive duplicate-key rejection."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON value: {value}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"JSON number overflows finite range: {value}")
        return parsed

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    decoder = json.JSONDecoder(
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
        parse_float=finite_float,
    )
    start = len(text) - len(text.lstrip())
    try:
        value, end = decoder.raw_decode(text, start)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid strict JSON") from exc
    if text[end:].strip():
        raise ValueError("trailing data after JSON value")
    return value


def load_strict_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read strict JSON: {path}") from exc
    return strict_json_loads(text)


def load_strict_json_object(path: Path) -> dict[str, Any]:
    value = load_strict_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"strict JSON object required: {path}")
    return value


def load_strict_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_bytes().decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read strict JSONL: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"blank JSONL row at line {line_number}: {path}")
        try:
            value = strict_json_loads(line)
        except ValueError as exc:
            raise ValueError(f"invalid JSONL row at line {line_number}: {path}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row is not an object at line {line_number}: {path}")
        rows.append(value)
    return rows


def resolve_artifact_root(root: str | Path) -> Path:
    supplied = Path(root).absolute()
    reject_link(supplied)
    resolved = supplied.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError(f"artifact root is not a directory: {root}")
    reject_symlink_tree(resolved)
    return resolved


def reject_symlink_tree(root: Path) -> None:
    reject_link(root)
    for current, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]:
            reject_link(Path(current) / name)


def reject_link(path: Path) -> None:
    try:
        is_junction = bool(getattr(path, "is_junction", lambda: False)())
    except OSError as exc:
        raise ValueError(f"cannot inspect artifact path: {path}") from exc
    if path.is_symlink() or is_junction:
        raise ValueError(f"symlink or junction is forbidden: {path}")


def canonical_relative_ref(value: Any) -> tuple[str, str]:
    if not isinstance(value, str) or not value:
        raise ValueError("artifact_ref must be a nonempty string")
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value or unicodedata.normalize("NFKC", value) != value:
        raise ValueError("artifact_ref is not Unicode-canonical")
    if any(ord(char) < 0x20 for char in value):
        raise ValueError("artifact_ref contains a control character")
    if "\\" in value or ":" in value:
        raise ValueError("artifact_ref contains a forbidden path character")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value:
        raise ValueError("artifact_ref is not canonical relative POSIX path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("artifact_ref contains an unsafe path segment")
    case_key = unicodedata.normalize("NFKC", value).casefold()
    return value, case_key


def resolve_artifact_file(root: Path, relative: str) -> Path:
    path = root.joinpath(*PurePosixPath(relative).parts)
    reject_link(path)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("artifact_ref resolves outside artifact root") from exc
    reject_link(resolved)
    if not resolved.is_file():
        raise ValueError(f"artifact_ref is not a regular file: {relative}")
    return resolved


def regular_files(root: Path) -> set[str]:
    reject_symlink_tree(root)
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and not path.name.endswith(".tmp")
        and path.name != "zero_api_artifact_manifest.json"
    }


__all__ = [
    "canonical_relative_ref",
    "load_strict_json",
    "load_strict_json_object",
    "load_strict_jsonl",
    "regular_files",
    "reject_link",
    "reject_symlink_tree",
    "resolve_artifact_file",
    "resolve_artifact_root",
    "strict_json_loads",
]
