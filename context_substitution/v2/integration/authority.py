from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

from context_substitution.v2.jsonio import StrictJSONError, loads_strict


AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_TAG_OBJECT = "1a8c00d12f100145a276cd8304440ff0a7e8d2a1"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
CONTRACT_MANIFEST_SHA256 = (
    "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
)
CONTRACT_MANIFEST_FILE_SHA256 = (
    "383884e28e9b9203b0ce346d8ad08572dea235a2d53c40c07bf1de22403f73fc"
)
AUTHORITY_RECEIPT_SELF_SHA256 = (
    "c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4"
)
AUTHORITY_RECEIPT_PHYSICAL_SHA256 = (
    "3497460f16ca478dada7b25425775882f10d1cb2b5d3638c36cba4ec5fb2791b"
)
DEFAULT_AUTHORITY_RECEIPT_PATH = Path(
    os.environ.get(
        "TERMINOLOGY_CONTRACTS_AUTHORITY_RECEIPT",
        r"C:\work\terminology-evidence-authority\contracts-v1.1.0\authority_receipt.json",
    )
)
CONTRACT_VERSION = "1.1.0"


class AuthorityConformanceError(ValueError):
    pass


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def contract_package_root() -> Path:
    configured = os.environ.get("TERMINOLOGY_CONTRACTS_ROOT")
    return (
        Path(configured).resolve()
        if configured
        else repository_root() / "terminology_contracts_v1"
    )


def validate_authority() -> dict[str, Any]:
    root = contract_package_root()
    manifest_path = root / "manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = loads_strict(
            manifest_bytes,
            source=manifest_path.as_posix(),
            require_object=True,
        )
    except (OSError, StrictJSONError) as exc:
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


def validate_authority_receipt(
    path: Path = DEFAULT_AUTHORITY_RECEIPT_PATH,
) -> dict[str, Any]:
    receipt_path = Path(path).resolve()
    try:
        receipt_bytes = receipt_path.read_bytes()
        receipt = loads_strict(
            receipt_bytes,
            source=receipt_path.as_posix(),
            require_object=True,
        )
    except (OSError, StrictJSONError) as exc:
        raise AuthorityConformanceError(
            f"cannot load Terminology Contracts authority receipt: {exc}"
        ) from exc
    physical_sha = hashlib.sha256(receipt_bytes).hexdigest()
    if physical_sha != AUTHORITY_RECEIPT_PHYSICAL_SHA256:
        raise AuthorityConformanceError("authority receipt physical SHA mismatch")
    if not isinstance(receipt, Mapping):
        raise AuthorityConformanceError("authority receipt must be an object")
    integrity = receipt.get("integrity")
    if not isinstance(integrity, Mapping):
        raise AuthorityConformanceError("authority receipt integrity is missing")
    claimed = integrity.get("self_sha256")
    identity = dict(receipt)
    identity_integrity = dict(integrity)
    identity_integrity.pop("self_sha256", None)
    identity["integrity"] = identity_integrity
    actual = canonical_sha256(identity)
    if claimed != AUTHORITY_RECEIPT_SELF_SHA256 or actual != claimed:
        raise AuthorityConformanceError("authority receipt canonical self-hash mismatch")
    expected = {
        "schema_id": "TerminologyContractsAuthorityReceiptV1",
        "contract_version": CONTRACT_VERSION,
        "authority_tag": AUTHORITY_TAG,
        "authority_tag_object_sha": AUTHORITY_TAG_OBJECT,
        "authority_commit": AUTHORITY_COMMIT,
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "manifest_file_sha256": CONTRACT_MANIFEST_FILE_SHA256,
        "publication_status": "PUBLISHED_LOCAL_NO_REMOTE",
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise AuthorityConformanceError(f"authority receipt {key} mismatch")
    return {
        **dict(receipt),
        "physical_sha256": physical_sha,
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
