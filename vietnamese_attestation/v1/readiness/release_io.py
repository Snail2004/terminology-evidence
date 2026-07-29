"""Git snapshot, checksum, manifest, and ZIP helpers for E releases."""

from __future__ import annotations

import datetime as dt
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from ..zero_api.artifacts import file_sha256
from .release_reports import seal


def git_text(repository: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"git command failed: {' '.join(args)}") from exc


def git_bytes(repository: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repository,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"git command failed: {' '.join(args)}") from exc


def tracked_source_paths(
    repository: Path, commit: str, *, owned_prefix: str
) -> list[str]:
    output = git_text(
        repository,
        "ls-tree",
        "-r",
        "--name-only",
        commit,
        "--",
        "vietnamese_attestation/v1",
    )
    paths = [line for line in output.splitlines() if line]
    if not paths:
        raise ValueError("implementation commit has no Evidence E source files")
    for path in paths:
        if not path.startswith(owned_prefix):
            raise ValueError(f"source path is outside E ownership: {path}")
        if is_cache_path(path):
            raise ValueError(f"tracked cache path is forbidden: {path}")
    return paths


def release_manifest(
    root: Path, commit: str, *, release_id: str
) -> dict[str, Any]:
    records = [
        {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in sorted(
            root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
        )
        if path.is_file()
        and path.name not in {"manifest.json", "CHECKSUMS.sha256"}
        and not is_cache_path(path.relative_to(root).as_posix())
    ]
    return seal(
        {
            "schema_id": "VietnameseAttestationPostZeroApiReleaseManifestV1",
            "schema_version": "1.0.0",
            "release_id": release_id,
            "implementation_commit": commit,
            "file_count": len(records),
            "files": records,
            "excluded_patterns": ["__pycache__", "*.pyc", ".pytest_cache"],
            "provider_call_count": 0,
        }
    )


def write_checksums(root: Path) -> None:
    lines = [
        f"{file_sha256(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(
            root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
        )
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    ]
    (root / "CHECKSUMS.sha256").write_text(
        "\n".join(lines) + "\n", encoding="ascii", newline="\n"
    )


def write_deterministic_zip(
    root: Path, output: Path, *, commit_epoch: int
) -> None:
    timestamp = _zip_timestamp(commit_epoch)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(
            root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
        ):
            if not path.is_file():
                continue
            relative = f"{root.name}/{path.relative_to(root).as_posix()}"
            info = zipfile.ZipInfo(relative, timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def is_cache_path(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return (
        "__pycache__" in parts
        or ".pytest_cache" in parts
        or path.endswith((".pyc", ".pyo"))
    )


def _zip_timestamp(epoch: int) -> tuple[int, int, int, int, int, int]:
    value = dt.datetime.fromtimestamp(max(epoch, 315532800), tz=dt.timezone.utc)
    second = value.second - (value.second % 2)
    return value.year, value.month, value.day, value.hour, value.minute, second


__all__ = [
    "git_bytes",
    "git_text",
    "is_cache_path",
    "release_manifest",
    "tracked_source_paths",
    "write_checksums",
    "write_deterministic_zip",
]
