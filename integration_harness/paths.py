"""Portable path and symlink checks for manifests and sealed runs."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path, PurePosixPath

from .errors import IntegrityError


def safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise IntegrityError("artifact path must be a non-empty string")
    if "\\" in value:
        raise IntegrityError(f"backslash is not allowed in artifact path: {value}")
    if re.match(r"^[A-Za-z]:", value) or value.startswith("//"):
        raise IntegrityError(f"drive or UNC path is not allowed: {value}")
    raw_parts = value.split("/")
    if any(part in ("", ".", "..") for part in raw_parts):
        raise IntegrityError(f"unsafe artifact path: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or value.startswith("/"):
        raise IntegrityError(f"absolute artifact path: {value}")
    if any(part in ("", ".", "..") for part in path.parts):
        raise IntegrityError(f"unsafe artifact path: {value}")
    return path


def ensure_no_symlink(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        if _is_reparse_point(current):
            raise IntegrityError(
                f"symlink, junction, or reparse point is not allowed in artifact path: {relative}"
            )
    return current


def ensure_plain_root(root: Path) -> Path:
    """Resolve a root only after rejecting reparse points in its existing ancestry."""

    absolute = root.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() and _is_reparse_point(current):
            raise IntegrityError(
                f"symlink, junction, or reparse point is not allowed in root: {root}"
            )
    return absolute


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)
    if is_junction is not None and is_junction(path):
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, FileNotFoundError, OSError):
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def relative_posix(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise IntegrityError(f"path escapes root: {path}") from exc
    return relative.as_posix()
