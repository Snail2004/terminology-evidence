"""Publish commit-bound D0 refreeze evidence outside the source build."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from ..jsonio import loads_strict, sha256_bytes, sha256_value, write_json
from ..release_tools.git_source import resolve_commit, source_entries, source_tree_sha256
from .builder import (
    ALL_CONTENT_FILES,
    BASE_FREEZE_RECEIPT_SHA256,
    CONTENT_MANIFEST_FILE,
    REFREEZE_CONTENT_FILE,
)


class D0PublicationError(ValueError):
    """Raised when D0 publication cannot be bound to one Git object."""


_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise D0PublicationError("Git object lookup failed") from exc


def _blob(repo: Path, commit: str, relative: str) -> bytes:
    try:
        return subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{relative}"], check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise D0PublicationError(f"missing Git-object publication path: {relative}") from exc


def _without_self_hash(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["integrity"] = {}
    return result


def _seal(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["integrity"] = {"self_sha256": ""}
    result["integrity"]["self_sha256"] = sha256_value(_without_self_hash(result))
    return result


def build_d0_publication(repo: Path, content_commit: str, output_directory: Path) -> dict[str, Any]:
    """Create immutable authority files from the exact content Git object."""
    if not _COMMIT.fullmatch(content_commit):
        raise D0PublicationError("content commit must be a full lowercase Git OID")
    commit, tree = resolve_commit(repo, content_commit)
    if output_directory.exists():
        raise D0PublicationError("D0 publication output already exists")
    entries = source_entries(repo, commit)
    by_path = dict(entries)
    content_prefix = "evaluation/v1/authority/d0_preparation_v1/"
    content_paths = [content_prefix + filename for filename in ALL_CONTENT_FILES]
    for path in content_paths:
        if path not in by_path:
            raise D0PublicationError(f"content commit does not contain {path}")
    content_manifest = loads_strict(by_path[content_prefix + CONTENT_MANIFEST_FILE].decode("utf-8"))
    declared_manifest = content_manifest.get("integrity", {}).get("self_sha256")
    if declared_manifest != sha256_value(_without_self_hash(content_manifest)):
        raise D0PublicationError("content manifest Git object self hash is invalid")
    content_inventory = [
        {"path": path, "bytes": len(by_path[path]), "sha256": sha256_bytes(by_path[path])}
        for path in content_paths
    ]
    # The manifest excludes itself; compare the exact source bytes without
    # relying on the live checkout.
    expected = [
        {"path": name, "bytes": len(by_path[content_prefix + name]), "sha256": sha256_bytes(by_path[content_prefix + name])}
        for name in ALL_CONTENT_FILES[:-1]
    ]
    if content_manifest.get("files") != expected:
        raise D0PublicationError("content manifest inventory does not match Git object")
    refreeze_content = loads_strict(by_path[content_prefix + REFREEZE_CONTENT_FILE].decode("utf-8"))
    receipt = _seal(
        {
            "schema_id": "EvaluationPreD0RefreezePublicationReceiptV1",
            "schema_version": "1.0.0",
            "status": "PRE_D0_ADDENDUM_REFROZEN",
            "content_commit": commit,
            "content_tree_git_oid": tree,
            "content_tree_sha256": source_tree_sha256([(path, data) for path, data in entries if path.startswith(content_prefix)]),
            "content_manifest_self_sha256": declared_manifest,
            "content_manifest_physical_sha256": sha256_bytes(by_path[content_prefix + CONTENT_MANIFEST_FILE]),
            "refreeze_content_sha256": refreeze_content["integrity"]["self_sha256"],
            "base_freeze_receipt_sha256": BASE_FREEZE_RECEIPT_SHA256,
            "expected_test_manifest_path": "evaluation/v1/authority/expected_test_manifest_v1.json",
            "expected_test_manifest_physical_sha256": sha256_bytes(by_path["evaluation/v1/authority/expected_test_manifest_v1.json"]),
            "expected_test_count": 47,
            "testcase_identity_sha256": "c02de79cb32481a9dfd1be9937eeafdb93d474f20c2356f026f15b076d2dbc5d",
            "gold_access": False,
            "validation_access": False,
            "held_out_test_access": False,
            "producer_outputs_opened": False,
            "provider_calls": 0,
            "network_calls": 0,
        }
    )
    manifest = _seal(
        {
            "schema_id": "EvaluationPreD0RefreezePublicationManifestV1",
            "schema_version": "1.0.0",
            "status": "PASS",
            "content_commit": commit,
            "content_tree_git_oid": tree,
            "receipt_sha256": receipt["integrity"]["self_sha256"],
            "files": [
                {"path": "pre_d0_refreeze_receipt_v1.json", "bytes": 0, "sha256": ""},
            ],
            "gold_access": False,
            "provider_calls": 0,
            "network_calls": 0,
        }
    )
    output_directory.mkdir(parents=True)
    write_json(output_directory / "pre_d0_refreeze_receipt_v1.json", receipt)
    manifest["files"][0] = {
        "path": "pre_d0_refreeze_receipt_v1.json",
        "bytes": (output_directory / "pre_d0_refreeze_receipt_v1.json").stat().st_size,
        "sha256": sha256_bytes((output_directory / "pre_d0_refreeze_receipt_v1.json").read_bytes()),
    }
    manifest["integrity"]["self_sha256"] = sha256_value(_without_self_hash(manifest))
    write_json(output_directory / "manifest.json", manifest)
    checksum_lines = []
    for path in sorted(output_directory.iterdir()):
        if path.is_file():
            checksum_lines.append(f"{sha256_bytes(path.read_bytes())}  {path.name}")
    (output_directory / "CHECKSUMS.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="ascii", newline="\n")
    return {
        "status": "PASS",
        "content_commit": commit,
        "content_tree_git_oid": tree,
        "receipt_self_sha256": receipt["integrity"]["self_sha256"],
        "manifest_self_sha256": manifest["integrity"]["self_sha256"],
        "checksums_physical_sha256": sha256_bytes((output_directory / "CHECKSUMS.sha256").read_bytes()),
        "gold_access": False,
        "provider_calls": 0,
        "network_calls": 0,
    }


def verify_d0_publication(repo: Path, publication_directory: Path) -> dict[str, Any]:
    """Verify the three publication bytes and their Git-object binding."""
    expected_files = {"pre_d0_refreeze_receipt_v1.json", "manifest.json", "CHECKSUMS.sha256"}
    allowed_content = set(ALL_CONTENT_FILES)
    actual_files = {path.name for path in publication_directory.iterdir() if path.is_file()} if publication_directory.is_dir() else set()
    if not expected_files.issubset(actual_files) or actual_files - expected_files - allowed_content:
        raise D0PublicationError("D0 publication file set is not exact")
    receipt_path = publication_directory / "pre_d0_refreeze_receipt_v1.json"
    manifest_path = publication_directory / "manifest.json"
    receipt = loads_strict(receipt_path.read_text(encoding="utf-8"))
    manifest = loads_strict(manifest_path.read_text(encoding="utf-8"))
    receipt_self = receipt.get("integrity", {}).get("self_sha256")
    if receipt_self != sha256_value(_without_self_hash(receipt)):
        raise D0PublicationError("D0 publication receipt self hash mismatch")
    manifest_self = manifest.get("integrity", {}).get("self_sha256")
    if manifest_self != sha256_value(_without_self_hash(manifest)):
        raise D0PublicationError("D0 publication manifest self hash mismatch")
    if manifest.get("schema_id") != "EvaluationPreD0RefreezePublicationManifestV1" or manifest.get("status") != "PASS":
        raise D0PublicationError("D0 publication manifest identity/status is invalid")
    if manifest.get("receipt_sha256") != receipt_self or manifest.get("content_commit") != receipt.get("content_commit"):
        raise D0PublicationError("D0 publication receipt/manifest binding drifted")
    if receipt.get("status") != "PRE_D0_ADDENDUM_REFROZEN" or receipt.get("base_freeze_receipt_sha256") != BASE_FREEZE_RECEIPT_SHA256:
        raise D0PublicationError("D0 publication status/base binding is invalid")
    if any(receipt.get(key) is not False for key in ("gold_access", "validation_access", "held_out_test_access", "producer_outputs_opened")):
        raise D0PublicationError("D0 publication reports restricted access")
    if receipt.get("provider_calls") != 0 or receipt.get("network_calls") != 0:
        raise D0PublicationError("D0 publication reports provider/network calls")
    content_commit = receipt.get("content_commit")
    commit, tree = resolve_commit(repo, content_commit)
    if tree != receipt.get("content_tree_git_oid"):
        raise D0PublicationError("D0 publication Git tree binding drifted")
    entries = source_entries(repo, commit)
    prefix = "evaluation/v1/authority/d0_preparation_v1/"
    content_entries = [(path, data) for path, data in entries if path.startswith(prefix)]
    if source_tree_sha256(content_entries) != receipt.get("content_tree_sha256"):
        raise D0PublicationError("D0 publication content tree hash drifted")
    manifest_blob = dict(entries).get(prefix + CONTENT_MANIFEST_FILE)
    if manifest_blob is None or sha256_bytes(manifest_blob) != receipt.get("content_manifest_physical_sha256"):
        raise D0PublicationError("D0 publication content manifest physical hash drifted")
    if receipt.get("expected_test_manifest_physical_sha256") != sha256_bytes(dict(entries)[receipt["expected_test_manifest_path"]]):
        raise D0PublicationError("D0 publication expected-test authority drifted")
    checksum_lines = [
        f"{sha256_bytes(path.read_bytes())}  {path.name}"
        for path in sorted((receipt_path, manifest_path), key=lambda item: item.name)
    ]
    if (publication_directory / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines() != checksum_lines:
        raise D0PublicationError("D0 publication CHECKSUMS drifted")
    return {
        "status": "PASS",
        "content_commit": commit,
        "content_tree_git_oid": tree,
        "receipt_self_sha256": receipt_self,
        "manifest_self_sha256": manifest_self,
        "checksums_physical_sha256": sha256_bytes((publication_directory / "CHECKSUMS.sha256").read_bytes()),
        "gold_access": False,
        "provider_calls": 0,
        "network_calls": 0,
    }
