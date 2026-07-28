from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .canonical import canonical_bytes
from .integrity import safe_relative_path
from .registries import PACKAGE_VERSION


MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "TerminologyContractsPackageManifestV1"
DEFAULT_EXCLUSIONS = (
    "release",
    "CHECKSUMS.sha256",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)


def build_manifest(
    root: Path,
    *,
    package_version: str = PACKAGE_VERSION,
    excluded_prefixes: Iterable[str] = DEFAULT_EXCLUSIONS,
) -> dict[str, Any]:
    """Build a deterministic content manifest for the package tree."""
    root = root.resolve()
    excluded = {prefix.rstrip("/") for prefix in excluded_prefixes}
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME or relative.endswith(".pyc"):
            continue
        if "__pycache__/" in f"{relative}/":
            continue
        if any(relative == prefix or relative.startswith(prefix + "/") for prefix in excluded):
            continue
        data = path.read_bytes()
        records.append(
            {
                "path": relative,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest: dict[str, Any] = {
        "schema_id": MANIFEST_SCHEMA,
        "package_id": "TerminologyInterModuleContractsV1",
        "package_version": package_version,
        "authority": "schemas/v1.1.0/",
        "excluded_paths": sorted(excluded),
        "files": records,
        "integrity": {"manifest_sha256": ""},
    }
    manifest["integrity"]["manifest_sha256"] = calculate_manifest_sha256(manifest)
    return manifest


def calculate_manifest_sha256(manifest: dict[str, Any]) -> str:
    clone = copy.deepcopy(manifest)
    integrity = clone.setdefault("integrity", {})
    if isinstance(integrity, dict):
        integrity.pop("manifest_sha256", None)
    return hashlib.sha256(canonical_bytes(clone)).hexdigest()


def write_manifest(root: Path, manifest: dict[str, Any] | None = None) -> Path:
    root = root.resolve()
    manifest = manifest or build_manifest(root)
    path = root / MANIFEST_NAME
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def verify_manifest(root: Path) -> list[str]:
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"cannot read manifest: {exc}"]
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    if manifest.get("schema_id") != MANIFEST_SCHEMA:
        errors.append("unsupported manifest schema_id")
    if manifest.get("package_version") != PACKAGE_VERSION:
        errors.append("manifest package_version mismatch")
    if manifest.get("integrity", {}).get("manifest_sha256") != calculate_manifest_sha256(manifest):
        errors.append("manifest_sha256 mismatch")

    records = manifest.get("files")
    if not isinstance(records, list):
        return errors + ["manifest.files must be an array"]
    seen: set[str] = set()
    expected_files: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            errors.append("manifest file record must be an object")
            continue
        try:
            relative = safe_relative_path(record.get("path"), field="manifest.path")
        except Exception as exc:
            errors.append(str(exc))
            continue
        if relative in seen:
            errors.append(f"duplicate manifest path: {relative}")
            continue
        seen.add(relative)
        expected_files.add(relative)
        path = root / relative
        if not path.is_file():
            errors.append(f"missing: {relative}")
            continue
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if record.get("size_bytes") != len(data):
            errors.append(f"size mismatch: {relative}")
        if record.get("sha256") != actual:
            errors.append(f"hash mismatch: {relative}")

    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.name != MANIFEST_NAME
        and not path.name.endswith(".pyc")
        and "__pycache__/" not in f"{path.relative_to(root).as_posix()}/"
        and not _is_excluded(
            path.relative_to(root).as_posix(), manifest.get("excluded_paths", [])
        )
    }
    for extra in sorted(actual_files - expected_files):
        errors.append(f"unlisted file: {extra}")
    for missing in sorted(expected_files - actual_files):
        if not any(message.endswith(missing) for message in errors):
            errors.append(f"listed file disappeared: {missing}")
    return errors


def _is_excluded(relative: str, prefixes: Any) -> bool:
    if not isinstance(prefixes, list):
        return False
    return any(
        isinstance(prefix, str)
        and (relative == prefix or relative.startswith(prefix.rstrip("/") + "/"))
        for prefix in prefixes
    )
