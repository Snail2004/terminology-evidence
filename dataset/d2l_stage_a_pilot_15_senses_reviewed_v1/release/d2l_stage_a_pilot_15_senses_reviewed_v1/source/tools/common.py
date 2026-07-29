from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seal_record(record: Mapping[str, Any], field: str = "record_sha256") -> dict[str, Any]:
    sealed = dict(record)
    sealed.pop(field, None)
    sealed[field] = sha256_bytes(canonical_json_bytes(sealed))
    return sealed


def verify_record(record: Mapping[str, Any], field: str = "record_sha256") -> bool:
    claimed = record.get(field)
    if not isinstance(claimed, str):
        return False
    payload = dict(record)
    payload.pop(field, None)
    return claimed == sha256_bytes(canonical_json_bytes(payload))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
            rows.append(value)
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    # Some Excel exports contain a literal U+FEFF in the first header even
    # after the byte-order mark has been decoded. Normalize only that header
    # artifact; cell contents remain byte/character faithful.
    return [
        {key.lstrip("\ufeff"): value for key, value in row.items()}
        for row in rows
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(canonical_json_bytes(record).decode("utf-8") + "\n")


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def reset_directory(path: Path) -> None:
    if path.exists():
        if path.is_symlink():
            raise ValueError(f"refusing to replace symlink output: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True)


def build_file_inventory(
    root: Path,
    excluded: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    excluded = excluded or set()
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        inventory[relative] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    return inventory


def write_checksums(root: Path, path: Path) -> None:
    excluded = {path.relative_to(root).as_posix()}
    lines = [
        f"{metadata['sha256']} *{relative}"
        for relative, metadata in build_file_inventory(root, excluded).items()
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def build_deterministic_zip(source_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
