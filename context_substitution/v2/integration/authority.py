from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
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
    "a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618"
)
AUTHORITY_RECEIPT_PHYSICAL_SHA256 = (
    "acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79"
)
AUTHORITY_RECEIPT_REVISION = 2
AUTHORITY_CONTRACT_TREE_GIT_OID = "d6386c4c4d19ba2aad982a519b9b59ecfd2213c9"
AUTHORITY_REVIEWED_CONTENT_COMMIT = "36e041abcaa0a8a34ab892ae094b0b3d9c3af2f4"
AUTHORITY_REVIEW_EVIDENCE_COMMIT = "147080746afee4f0059d9e51617097f7e383a8d1"
FEATURE_REGISTRY_PATH = "registries/feature_contract_v1.1.0.json"
FEATURE_REGISTRY_FILE_SHA256 = (
    "78a0cc6e969c88173a2203c76e41411e836a326616da452f38148c9f0c960244"
)
FEATURE_REGISTRY_CANONICAL_SHA256 = (
    "057f47d68097286f04f0870d2e78944e59c07b0cb4e9db7f9d8675c9f2c8b182"
)
GATE_POLICY_PATH = "policies/gate_policy_v1.0.0.json"
GATE_POLICY_FILE_SHA256 = (
    "3d9fe31a96eecb0ae5f84823f87c7bb4739bd8139942e7b04ac279cc8c39dc85"
)
GATE_POLICY_SELF_SHA256 = (
    "9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2"
)
FINAL_RELEASE_ZIP_SHA256 = (
    "2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471"
)
FINAL_RELEASE_AUDIT_PHYSICAL_SHA256 = (
    "21a36752d0e244449c650221a0a89c73376526efd88a3b56f62d0e0c68eedfd3"
)
FINAL_RELEASE_AUDIT_SELF_SHA256 = (
    "e8cec2de12224f816ca7eb6c8b38d75f2b07f6d99f44c019caae44f45c961202"
)
AUTHORITY_RELEASE_CHECKSUMS_PHYSICAL_SHA256 = (
    "295a93ea167c0cbb590e6d4cf5894f18e48782aa942dbe424855c19cb0c52196"
)
AUTHORITY_RELEASE_MANIFEST_PHYSICAL_SHA256 = (
    "bd9d4c10908bdb951eaebb8c139afe7a09b198bd6422ef7626dc728c6ea9ccb7"
)
AUTHORITY_RELEASE_MANIFEST_SELF_SHA256 = (
    "d64b82abb2b74bf7477a1c9f740c8d6a3bc0155dae8d3476b484fee239ad7522"
)
AUTHORITY_RECEIPT_CHECKSUM_PHYSICAL_SHA256 = (
    "510315f9cda35fd261eb0fea41c8683247fdc8a7be1d890bed70017918509bcc"
)
AUTHORITY_RELEASE_IMPLEMENTATION_COMMIT = (
    "3efc430312f080b4f8b1752e18173501283292f8"
)
_AUTHORITY_RELEASE_RELATIVE = Path("release") / "v1.1.0-final"
_AUTHORITY_RECEIPT_NAME = "contracts_v1_1_0_authority_receipt_r2.json"
DEFAULT_AUTHORITY_RECEIPT_PATH = Path(
    os.environ.get(
        "TERMINOLOGY_CONTRACTS_AUTHORITY_RECEIPT",
        str(
            Path(__file__).resolve().parents[3]
            / "terminology_contracts_v1"
            / _AUTHORITY_RELEASE_RELATIVE
            / _AUTHORITY_RECEIPT_NAME
        ),
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


def default_authority_receipt_path() -> Path:
    configured = os.environ.get("TERMINOLOGY_CONTRACTS_AUTHORITY_RECEIPT")
    if configured:
        return Path(configured).resolve()
    return (
        contract_package_root().resolve()
        / _AUTHORITY_RELEASE_RELATIVE
        / _AUTHORITY_RECEIPT_NAME
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
    path: Path | None = None,
) -> dict[str, Any]:
    receipt_path = (
        Path(path).resolve() if path is not None else default_authority_receipt_path()
    )
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
        "schema_version": "1.0.0",
        "contract_version": CONTRACT_VERSION,
        "authority_tag": AUTHORITY_TAG,
        "authority_tag_object_oid": AUTHORITY_TAG_OBJECT,
        "authority_commit": AUTHORITY_COMMIT,
        "authority_status": "SEALED",
        "contract_root": "terminology_contracts_v1",
        "contract_tree_git_oid": AUTHORITY_CONTRACT_TREE_GIT_OID,
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "manifest_file_sha256": CONTRACT_MANIFEST_FILE_SHA256,
        "manifest_path": "manifest.json",
        "feature_registry_path": FEATURE_REGISTRY_PATH,
        "feature_registry_file_sha256": FEATURE_REGISTRY_FILE_SHA256,
        "feature_registry_canonical_sha256": FEATURE_REGISTRY_CANONICAL_SHA256,
        "feature_registry_version": CONTRACT_VERSION,
        "gate_policy_path": GATE_POLICY_PATH,
        "gate_policy_file_sha256": GATE_POLICY_FILE_SHA256,
        "gate_policy_self_sha256": GATE_POLICY_SELF_SHA256,
        "final_release_path": "release/v1.1.0-final/terminology_contracts_v1_1_0_final.zip",
        "final_release_checksum_path": (
            "release/v1.1.0-final/terminology_contracts_v1_1_0_final.zip.sha256"
        ),
        "final_release_zip_sha256": FINAL_RELEASE_ZIP_SHA256,
        "final_release_audit_path": "release/v1.1.0-final/final_release_audit.json",
        "final_release_audit_physical_sha256": FINAL_RELEASE_AUDIT_PHYSICAL_SHA256,
        "final_release_audit_self_sha256": FINAL_RELEASE_AUDIT_SELF_SHA256,
        "reviewed_content_commit": AUTHORITY_REVIEWED_CONTENT_COMMIT,
        "review_evidence_commit": AUTHORITY_REVIEW_EVIDENCE_COMMIT,
        "receipt_revision": AUTHORITY_RECEIPT_REVISION,
        "publication_status": "PENDING_INDEPENDENT_REVIEW",
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise AuthorityConformanceError(f"authority receipt {key} mismatch")
    root = contract_package_root().resolve()
    expected_path = (
        root / _AUTHORITY_RELEASE_RELATIVE / _AUTHORITY_RECEIPT_NAME
    ).resolve()
    if receipt_path != expected_path:
        raise AuthorityConformanceError(
            "authority receipt path is not the canonical in-repository R2 path"
        )
    validate_authority()
    _validate_contract_artifact_bindings(root, receipt)
    _validate_release_bundle(receipt_path.parent)
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


def _validate_contract_artifact_bindings(
    root: Path, receipt: Mapping[str, Any]
) -> None:
    for relative, expected_sha, label in (
        (FEATURE_REGISTRY_PATH, FEATURE_REGISTRY_FILE_SHA256, "feature registry"),
        (GATE_POLICY_PATH, GATE_POLICY_FILE_SHA256, "gate policy"),
    ):
        path = root / Path(relative)
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise AuthorityConformanceError(f"cannot load {label}: {exc}") from exc
        receipt_key = f"{label.replace(' ', '_')}_file_sha256"
        if actual != expected_sha or receipt.get(receipt_key) != expected_sha:
            raise AuthorityConformanceError(f"{label} physical SHA mismatch")
        if label == "feature registry":
            value = _load_strict_object(path)
            if canonical_sha256(value) != FEATURE_REGISTRY_CANONICAL_SHA256:
                raise AuthorityConformanceError("feature registry canonical SHA mismatch")
        else:
            value = _load_strict_object(path)
            _verify_canonical_self_hash(
                value,
                expected=GATE_POLICY_SELF_SHA256,
                label="gate policy",
            )


def _validate_release_bundle(release_root: Path) -> None:
    checksums_path = release_root / "CHECKSUMS.sha256"
    try:
        checksum_bytes = checksums_path.read_bytes()
        checksum_text = checksum_bytes.decode("ascii")
    except (OSError, UnicodeError) as exc:
        raise AuthorityConformanceError(f"cannot load R2 release checksums: {exc}") from exc
    if (
        hashlib.sha256(checksum_bytes).hexdigest()
        != AUTHORITY_RELEASE_CHECKSUMS_PHYSICAL_SHA256
    ):
        raise AuthorityConformanceError("R2 release checksums physical SHA mismatch")

    entries: dict[str, str] = {}
    for line_number, line in enumerate(checksum_text.splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise AuthorityConformanceError(
                f"R2 release checksum line {line_number} is malformed"
            )
        digest, relative = match.groups()
        if "\\" in relative or ":" in relative:
            raise AuthorityConformanceError("R2 release checksum path is not canonical")
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or pure.as_posix() != relative
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise AuthorityConformanceError("R2 release checksum path is not canonical")
        if relative in entries:
            raise AuthorityConformanceError("R2 release checksum path is duplicated")
        entries[relative] = digest

    actual_files = {
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*")
        if path.is_file()
    }
    if any(path.is_symlink() for path in release_root.rglob("*")):
        raise AuthorityConformanceError("R2 release bundle contains a symlink")
    expected_files = set(entries) | {"CHECKSUMS.sha256"}
    if actual_files != expected_files:
        raise AuthorityConformanceError("R2 release file inventory mismatch")
    for relative, expected_sha in entries.items():
        path = release_root.joinpath(*PurePosixPath(relative).parts)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            raise AuthorityConformanceError(f"R2 release artifact SHA mismatch: {relative}")

    pinned = {
        "release_manifest.json": AUTHORITY_RELEASE_MANIFEST_PHYSICAL_SHA256,
        _AUTHORITY_RECEIPT_NAME: AUTHORITY_RECEIPT_PHYSICAL_SHA256,
        _AUTHORITY_RECEIPT_NAME + ".sha256": AUTHORITY_RECEIPT_CHECKSUM_PHYSICAL_SHA256,
        "final_release_audit.json": FINAL_RELEASE_AUDIT_PHYSICAL_SHA256,
        "terminology_contracts_v1_1_0_final.zip": FINAL_RELEASE_ZIP_SHA256,
    }
    for relative, expected_sha in pinned.items():
        if entries.get(relative) != expected_sha:
            raise AuthorityConformanceError(f"R2 release pin mismatch: {relative}")

    companion = (release_root / (_AUTHORITY_RECEIPT_NAME + ".sha256")).read_text(
        encoding="ascii"
    )
    expected_companion = f"{AUTHORITY_RECEIPT_PHYSICAL_SHA256}  {_AUTHORITY_RECEIPT_NAME}\n"
    if companion != expected_companion:
        raise AuthorityConformanceError("R2 authority receipt checksum content mismatch")

    release_manifest = _load_strict_object(release_root / "release_manifest.json")
    _verify_canonical_self_hash(
        release_manifest,
        expected=AUTHORITY_RELEASE_MANIFEST_SELF_SHA256,
        label="R2 release manifest",
    )
    records = release_manifest.get("files")
    if not isinstance(records, list):
        raise AuthorityConformanceError("R2 release manifest files are invalid")
    manifest_entries: dict[str, tuple[str, int]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise AuthorityConformanceError("R2 release manifest file record is invalid")
        relative = record.get("path")
        if not isinstance(relative, str) or relative in manifest_entries:
            raise AuthorityConformanceError("R2 release manifest path is invalid")
        manifest_entries[relative] = (str(record.get("sha256")), record.get("size_bytes"))
    expected_manifest_files = set(entries) - {"release_manifest.json"}
    if set(manifest_entries) != expected_manifest_files:
        raise AuthorityConformanceError("R2 release manifest inventory mismatch")
    for relative, (expected_sha, expected_size) in manifest_entries.items():
        path = release_root.joinpath(*PurePosixPath(relative).parts)
        if expected_sha != entries[relative] or expected_size != path.stat().st_size:
            raise AuthorityConformanceError(
                f"R2 release manifest binding mismatch: {relative}"
            )

    audit = _load_strict_object(release_root / "final_release_audit.json")
    _verify_canonical_self_hash(
        audit,
        expected=FINAL_RELEASE_AUDIT_SELF_SHA256,
        label="R2 final release audit",
    )
    if (
        audit.get("authority_tag") != AUTHORITY_TAG
        or audit.get("authority_commit") != AUTHORITY_COMMIT
        or audit.get("release_zip_sha256") != FINAL_RELEASE_ZIP_SHA256
        or audit.get("test_result") != "PASS"
        or audit.get("external_api_calls") != 0
    ):
        raise AuthorityConformanceError("R2 final release audit binding mismatch")

    git_receipt = _load_strict_object(release_root / "git_commit_receipt.json")
    tag_resolution = git_receipt.get("tag_resolution")
    if (
        git_receipt.get("implementation_commit")
        != AUTHORITY_RELEASE_IMPLEMENTATION_COMMIT
        or not isinstance(tag_resolution, Mapping)
        or tag_resolution.get("tag") != AUTHORITY_TAG
        or tag_resolution.get("commit_oid") != AUTHORITY_COMMIT
        or tag_resolution.get("tag_object_oid") != AUTHORITY_TAG_OBJECT
        or tag_resolution.get("contract_tree_oid") != AUTHORITY_CONTRACT_TREE_GIT_OID
    ):
        raise AuthorityConformanceError("R2 release Git authority binding mismatch")


def _load_strict_object(path: Path) -> dict[str, Any]:
    try:
        return loads_strict(path.read_bytes(), source=path.as_posix(), require_object=True)
    except (OSError, StrictJSONError) as exc:
        raise AuthorityConformanceError(f"cannot load R2 release artifact: {exc}") from exc


def _verify_canonical_self_hash(
    value: Mapping[str, Any], *, expected: str, label: str
) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or integrity.get("self_sha256") != expected:
        raise AuthorityConformanceError(f"{label} self-hash claim mismatch")
    identity = dict(value)
    identity_integrity = dict(integrity)
    identity_integrity.pop("self_sha256", None)
    identity["integrity"] = identity_integrity
    if canonical_sha256(identity) != expected:
        raise AuthorityConformanceError(f"{label} canonical self-hash mismatch")


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
