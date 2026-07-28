from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_object(value: Any) -> str:
    return sha256_text(canonical_json(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    payload = canonical_json([str(part) for part in parts])
    return f"{prefix}_{sha256_text(payload)[:24]}"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def write_text(path: Path, value: str) -> None:
    payload = value if value.endswith("\n") else value + "\n"
    _atomic_write(path, payload.encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(canonical_json(row) + "\n" for row in rows).encode("utf-8"),
    )


def write_csv(
    path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def seal(value: dict[str, Any], hash_field: str) -> dict[str, Any]:
    sealed = dict(value)
    sealed.pop(hash_field, None)
    sealed[hash_field] = sha256_object(sealed)
    return sealed


def validate_self_hash(
    value: dict[str, Any], hash_field: str, label: str, errors: list[str]
) -> None:
    identity = dict(value)
    expected = identity.pop(hash_field, None)
    if expected != sha256_object(identity):
        errors.append(f"{label} self hash mismatch")


def file_bindings(root: Path, excluded: set[str] | None = None) -> dict[str, Any]:
    excluded = excluded or set()
    return {
        path.relative_to(root).as_posix(): {
            "ref": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    }


def validate_file_bindings(
    root: Path, bindings: dict[str, Any], label: str, errors: list[str]
) -> None:
    for relative, binding in bindings.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"{label} missing file: {relative}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"{label} file hash mismatch: {relative}")


def write_checksums(root: Path, path: Path) -> None:
    rows = []
    for member in sorted(root.rglob("*")):
        if member.is_file() and member != path:
            rows.append(f"{sha256_file(member)}  {member.relative_to(root).as_posix()}")
    write_text(path, "\n".join(rows))


def deterministic_zip(source_root: Path, archive_path: Path, root_name: str) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=archive_path.parent,
        prefix=f".{archive_path.name}.",
        suffix=".tmp",
    ) as temporary_handle:
        temporary = Path(temporary_handle.name)
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in sorted(source_root.rglob("*")):
                if not path.is_file():
                    continue
                relative = Path(root_name) / path.relative_to(source_root)
                info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compresslevel=9)
        os.replace(temporary, archive_path)
    finally:
        temporary.unlink(missing_ok=True)
