from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping


AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_TAG_OBJECT = "1a8c00d12f100145a276cd8304440ff0a7e8d2a1"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
CONTRACT_MANIFEST_SHA256 = (
    "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
)
CONTRACT_MANIFEST_FILE_SHA256 = (
    "383884e28e9b9203b0ce346d8ad08572dea235a2d53c40c07bf1de22403f73fc"
)
CONTRACT_VERSION = "1.1.0"


class AuthorityConformanceError(ValueError):
    pass


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def contract_package_root() -> Path:
    return repository_root() / "terminology_contracts_v1"


def validate_authority() -> dict[str, Any]:
    root = contract_package_root()
    manifest_path = root / "manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorityConformanceError(
            f"cannot load Terminology Contracts authority manifest: {exc}"
        ) from exc
    physical_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if physical_sha != CONTRACT_MANIFEST_FILE_SHA256:
        raise AuthorityConformanceError(
            "Terminology Contracts authority manifest physical SHA mismatch"
        )
    if manifest.get("package_version") != CONTRACT_VERSION:
        raise AuthorityConformanceError("Terminology Contracts authority version mismatch")
    if manifest.get("integrity", {}).get("manifest_sha256") != CONTRACT_MANIFEST_SHA256:
        raise AuthorityConformanceError("Terminology Contracts manifest binding mismatch")
    errors = _module("manifest").verify_manifest(root)
    if errors:
        raise AuthorityConformanceError(
            "Terminology Contracts authority verification failed: " + "; ".join(errors)
        )
    return {
        "authority_tag": AUTHORITY_TAG,
        "authority_tag_object": AUTHORITY_TAG_OBJECT,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_version": CONTRACT_VERSION,
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "manifest_file_sha256": CONTRACT_MANIFEST_FILE_SHA256,
    }


def validate_official_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    errors = _module("validation").validate_instance(
        payload,
        contract_package_root() / "schemas" / "v1.1.0",
    )
    if errors:
        raise AuthorityConformanceError("; ".join(errors))
    return payload


def seal_official_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    return _module("integrity").seal_self_hash(value)


def seal_frozen_candidate_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    return _module("bindings").seal_frozen_candidate_contract(value)


def verify_frozen_candidate_binding(value: Mapping[str, Any]) -> bool:
    return bool(_module("bindings").verify_frozen_candidate_binding(value))


def canonical_sha256(value: Any) -> str:
    return str(_module("integrity").canonical_sha256(value))


def _module(name: str) -> ModuleType:
    try:
        return importlib.import_module(f"terminology_contracts.{name}")
    except ModuleNotFoundError as exc:
        if exc.name not in {"terminology_contracts", f"terminology_contracts.{name}"}:
            raise
        package_path = contract_package_root() / "python"
        value = str(package_path)
        if value not in sys.path:
            sys.path.insert(0, value)
        return importlib.import_module(f"terminology_contracts.{name}")
