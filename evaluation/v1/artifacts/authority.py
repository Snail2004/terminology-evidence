"""Canonical path containment and content-addressed manifest verification."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from ..jsonio import read_json, sha256_file


class AuthorityError(ValueError):
    """Raised when a path or content-addressed authority binding is unsafe."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPARSE_POINT = 0x400


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & _REPARSE_POINT)
    except OSError:
        return False


def _lexical_absolute(path: Path, field: str) -> Path:
    raw = os.fspath(path)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise AuthorityError(f"{field} is empty or invalid")
    normalized = raw.replace("\\", "/")
    if normalized.startswith("//"):
        raise AuthorityError(f"{field} cannot use a UNC/network path")
    if any(part in {".", ".."} for part in normalized.split("/")):
        raise AuthorityError(f"{field} contains a dot/traversal segment")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate


def _require_unlinked_existing(path: Path, *, directory: bool, field: str) -> Path:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if not current.exists() or _is_link_or_reparse(current):
            raise AuthorityError(f"{field} is missing or traverses a link/reparse point")
    if directory and not current.is_dir():
        raise AuthorityError(f"{field} is not a directory")
    if not directory and not current.is_file():
        raise AuthorityError(f"{field} is not a regular file")
    return current


def secure_existing_directory(path: Path, *, trusted_root: Path | None = None, field: str = "directory") -> Path:
    """Resolve an existing directory only after lexical and component checks."""
    lexical = _lexical_absolute(path, field)
    checked = _require_unlinked_existing(lexical, directory=True, field=field)
    resolved = checked.resolve(strict=True)
    if trusted_root is not None:
        trusted_lexical = _lexical_absolute(trusted_root, f"{field}.trusted_root")
        trusted = _require_unlinked_existing(trusted_lexical, directory=True, field=f"{field}.trusted_root").resolve(strict=True)
        try:
            resolved.relative_to(trusted)
        except ValueError as exc:
            raise AuthorityError(f"{field} escapes its trusted root") from exc
    return resolved


def secure_existing_file(path: Path, *, trusted_root: Path | None = None, field: str = "file") -> Path:
    """Resolve an existing file only after lexical, containment and link checks."""
    lexical = _lexical_absolute(path, field)
    checked = _require_unlinked_existing(lexical, directory=False, field=field)
    resolved = checked.resolve(strict=True)
    if trusted_root is not None:
        trusted = secure_existing_directory(trusted_root, field=f"{field}.trusted_root")
        try:
            resolved.relative_to(trusted)
        except ValueError as exc:
            raise AuthorityError(f"{field} escapes its trusted root") from exc
    return resolved


def canonical_manifest_path(value: str) -> str:
    """Validate and return an unchanged canonical POSIX-relative path."""
    if not isinstance(value, str) or not value or value != unicodedata.normalize("NFC", value):
        raise AuthorityError("manifest path is empty or not NFC-normalized")
    if "\\" in value or ":" in value or value.startswith("/") or value.endswith("/") or "//" in value:
        raise AuthorityError(f"unsafe manifest path: {value}")
    path = PurePosixPath(value)
    parts = value.split("/")
    if path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise AuthorityError(f"unsafe manifest path: {value}")
    canonical = "/".join(path.parts)
    if canonical != value:
        raise AuthorityError(f"noncanonical manifest path: {value}")
    return canonical


def resolve_contained_file(root: Path, relative: str) -> Path:
    """Resolve one manifest file while rejecting every link/reparse component."""
    canonical = canonical_manifest_path(relative)
    if not root.is_dir() or _is_link_or_reparse(root):
        raise AuthorityError("manifest root is missing, symlinked or a reparse point")
    root_resolved = root.resolve(strict=True)
    current = root
    for part in canonical.split("/"):
        current = current / part
        if not current.exists() or _is_link_or_reparse(current):
            raise AuthorityError(f"manifest path is missing or traverses a link/reparse point: {relative}")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root_resolved)
    except (OSError, ValueError) as exc:
        raise AuthorityError(f"manifest path escapes root: {relative}") from exc
    if not resolved.is_file() or _is_link_or_reparse(resolved):
        raise AuthorityError(f"manifest target is not a regular file: {relative}")
    return resolved


def verify_sha256(path: Path, expected: str) -> str:
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise AuthorityError("expected SHA256 is invalid")
    if path.is_symlink() or not path.is_file() or _is_link_or_reparse(path):
        raise AuthorityError(f"artifact is missing or linked: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise AuthorityError(f"SHA256 mismatch for {path}")
    return actual


def verify_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise AuthorityError("manifest files must be a nonempty list")
    exact: set[str] = set()
    folded: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise AuthorityError("manifest entry shape is invalid")
        relative = canonical_manifest_path(entry["path"])
        casefolded = unicodedata.normalize("NFC", relative).casefold()
        if relative in exact or casefolded in folded:
            raise AuthorityError(f"duplicate or case-confusable manifest path: {relative}")
        exact.add(relative)
        folded.add(casefolded)
        verify_sha256(resolve_contained_file(root, relative), entry["sha256"])
    return manifest
