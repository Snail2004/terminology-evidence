"""Exact Git-object collection and safe detached materialization."""

from __future__ import annotations

import hashlib
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Iterable

from ..artifacts.authority import canonical_manifest_path


SOURCE_ROOTS = ("evaluation", "tests/evaluation", "docs/evaluation")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class GitSourceError(ValueError):
    """Raised when release bytes cannot be proven to come from one Git object."""


def _git(repo: Path, *arguments: str, text: bool = True) -> str | bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GitSourceError(f"git command failed: {' '.join(arguments)}") from exc
    return completed.stdout


def resolve_commit(repo: Path, commit: str) -> tuple[str, str]:
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
        raise GitSourceError("source commit must be a full lowercase Git OID")
    resolved = str(_git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}"),).strip().lower()
    if resolved != commit:
        raise GitSourceError("source commit does not resolve exactly")
    tree = str(_git(repo, "rev-parse", f"{commit}^{{tree}}"),).strip().lower()
    return resolved, tree


def require_clean_exact_head(repo: Path, commit: str) -> None:
    resolved, _ = resolve_commit(repo, commit)
    head = str(_git(repo, "rev-parse", "HEAD"),).strip().lower()
    status = str(_git(repo, "status", "--porcelain=v1", "--untracked-files=all"))
    if head != resolved:
        raise GitSourceError("normal release requires HEAD == source commit")
    if status:
        raise GitSourceError("normal release requires a completely clean worktree")


def source_entries(repo: Path, commit: str, roots: Iterable[str] = SOURCE_ROOTS) -> list[tuple[str, bytes]]:
    resolve_commit(repo, commit)
    roots = tuple(roots)
    listing = bytes(_git(repo, "ls-tree", "-r", "-z", commit, "--", *roots, text=False))
    entries: list[tuple[str, bytes]] = []
    folded: set[str] = set()
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        try:
            header, raw_path = raw.split(b"\t", 1)
            mode, object_type, _object_id = header.decode("ascii").split(" ", 2)
            relative = canonical_manifest_path(raw_path.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise GitSourceError("Git tree contains an invalid path entry") from exc
        if object_type != "blob" or mode == "120000":
            raise GitSourceError(f"Git source contains a nonregular file: {relative}")
        if not any(relative == root or relative.startswith(root + "/") for root in roots):
            raise GitSourceError(f"Git source escapes Evaluation ownership: {relative}")
        key = relative.casefold()
        if key in folded:
            raise GitSourceError(f"Git source contains a case-confusable path: {relative}")
        folded.add(key)
        entries.append((relative, bytes(_git(repo, "show", f"{commit}:{relative}", text=False))))
    if not entries:
        raise GitSourceError("Evaluation source tree is empty")
    return sorted(entries)


def source_tree_sha256(entries: Iterable[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative, data in entries:
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def write_source_zip(entries: Iterable[tuple[str, bytes]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, data in sorted(entries):
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def read_source_zip(path: Path, roots: Iterable[str] = SOURCE_ROOTS) -> list[tuple[str, bytes]]:
    """Read a released source ZIP while enforcing exact Evaluation ownership."""
    roots = tuple(roots)
    entries: list[tuple[str, bytes]] = []
    folded: set[str] = set()
    try:
        with zipfile.ZipFile(path, "r") as archive:
            for info in archive.infolist():
                if info.is_dir() or info.flag_bits & 0x1:
                    raise GitSourceError("source ZIP contains a directory/encrypted member")
                relative = canonical_manifest_path(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if mode not in {0, 0o100000}:
                    raise GitSourceError(f"source ZIP contains a nonregular member: {relative}")
                if not any(relative == root or relative.startswith(root + "/") for root in roots):
                    raise GitSourceError(f"source ZIP escapes Evaluation ownership: {relative}")
                key = relative.casefold()
                if key in folded:
                    raise GitSourceError(f"source ZIP contains a duplicate/case-confusable member: {relative}")
                folded.add(key)
                entries.append((relative, archive.read(info)))
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        raise GitSourceError("source ZIP is malformed or unsafe") from exc
    if not entries:
        raise GitSourceError("source ZIP is empty")
    return sorted(entries)


def materialize_commit(repo: Path, commit: str, destination: Path) -> None:
    """Materialize the full Git object without trusting live checkout bytes."""
    resolve_commit(repo, commit)
    if destination.exists():
        raise GitSourceError("materialization destination already exists")
    destination.mkdir(parents=True)
    archive_path = destination.parent / f".{destination.name}.git-object.zip"
    try:
        _git(repo, "archive", "--format=zip", f"--output={archive_path}", commit)
        with zipfile.ZipFile(archive_path, "r") as archive:
            seen: set[str] = set()
            for info in archive.infolist():
                name = info.filename.rstrip("/")
                if not name:
                    continue
                canonical = canonical_manifest_path(name)
                folded = canonical.casefold()
                mode = (info.external_attr >> 16) & 0o170000
                if folded in seen or mode == 0o120000:
                    raise GitSourceError(f"unsafe archive member: {name}")
                seen.add(folded)
                target = destination.joinpath(*canonical.split("/"))
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, "r") as source, target.open("xb") as handle:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            handle.write(chunk)
    finally:
        if archive_path.exists():
            archive_path.unlink()
