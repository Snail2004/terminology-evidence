from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _strict_float(value: str) -> float:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid JSON number: {value}") from exc
    converted = float(parsed)
    if not parsed.is_finite() or not math.isfinite(converted):
        raise ValueError(f"non-finite or overflowing JSON number: {value}")
    return converted


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def strict_json_loads(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
        parse_float=_strict_float,
    )


def strict_json_file(path: Path) -> Any:
    return strict_json_loads(path.read_bytes().decode("utf-8", errors="strict"))


def strict_json_object(path: Path) -> dict[str, Any]:
    value = strict_json_file(path)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON payload must be an object")
    return value


def strict_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_bytes().decode("utf-8", errors="strict")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = strict_json_loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
        rows.append(value)
    return rows


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
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


def seal_integrity(record: Mapping[str, Any]) -> dict[str, Any]:
    sealed = json.loads(json.dumps(record, ensure_ascii=False, allow_nan=False))
    integrity = sealed.setdefault("integrity", {})
    if not isinstance(integrity, dict):
        raise ValueError("integrity must be an object")
    integrity.pop("self_sha256", None)
    integrity["self_sha256"] = sha256_bytes(canonical_json_bytes(sealed))
    return sealed


def verify_integrity(record: Mapping[str, Any]) -> bool:
    integrity = record.get("integrity")
    if not isinstance(integrity, Mapping):
        return False
    claimed = integrity.get("self_sha256")
    payload = json.loads(json.dumps(record, ensure_ascii=False, allow_nan=False))
    payload_integrity = payload.get("integrity")
    if not isinstance(payload_integrity, dict):
        return False
    payload_integrity.pop("self_sha256", None)
    return claimed == sha256_bytes(canonical_json_bytes(payload))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: CSV header is required")
        return [
            {key.lstrip("\ufeff"): value for key, value in row.items()}
            for row in reader
        ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
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


def canonical_paths(root: Path) -> list[Path]:
    paths = [path for path in root.rglob("*") if path.is_file()]
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def build_file_inventory(
    root: Path,
    excluded: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    excluded = excluded or set()
    inventory: dict[str, dict[str, Any]] = {}
    for path in canonical_paths(root):
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
        for path in canonical_paths(source_root):
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


def replace_directory(staging: Path, destination: Path) -> None:
    if destination.exists() and destination.is_symlink():
        raise ValueError(f"refusing to replace symlink output: {destination}")
    if destination.exists():
        shutil.rmtree(destination)
    staging.replace(destination)
