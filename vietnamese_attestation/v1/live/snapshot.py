"""Deterministic local controlled-corpus snapshot builder and verifier."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..retrieval.extraction import EXTRACTOR_VERSION, extract_document
from ..retrieval.fetch import FetchedDocument
from ..strict_json import (
    canonical_relative_ref,
    reject_link,
    reject_symlink_tree,
    resolve_artifact_file,
    resolve_artifact_root,
    regular_files,
)
from .common import (
    LIVE_TOOL_SCHEMA_VERSION,
    LiveSchemaError,
    canonical_bytes,
    canonical_sha256,
    file_sha256,
    load_object,
    require_keys,
    require_sha256,
    require_string,
    safe_relative_path,
    seal,
    utc_now,
    verify_seal,
)
from .policies import validate_policy_bundle
from .registry import admit_source, validate_registry

SNAPSHOT_SCHEMA_ID = "EControlledCorpusSnapshotV1"
ACQUISITION_SCHEMA_ID = "EControlledAcquisitionReceiptV1"
SNAPSHOT_MANIFEST_NAME = "snapshot_manifest.json"
CHECKSUMS_NAME = "CHECKSUMS"


def build_snapshot(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    registry: Mapping[str, Any],
    retrieval_policy: Mapping[str, Any],
    acquisition_receipt: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    producer_commit: str = "0000000000000000000000000000000000000000",
    producer_tree: str = "fixture-tree",
    registry_physical_sha256: str | None = None,
    retrieval_policy_physical_sha256: str | None = None,
) -> dict[str, Any]:
    """Freeze supplied local bytes; this function never performs network IO."""
    source_root = resolve_artifact_root(input_dir)
    target = Path(output_dir).absolute()
    reject_link(target)
    if target.exists():
        if not target.is_dir() or any(target.iterdir()):
            raise LiveSchemaError("snapshot output directory must be new and empty")
    else:
        target.mkdir(parents=True)
    validate_registry(registry)
    if retrieval_policy.get("network_mode") not in {"LOCAL_FIXTURE_ONLY", "LIVE_AUTHORIZED"}:
        raise LiveSchemaError("retrieval policy network mode is invalid")
    rows = _receipt_rows(acquisition_receipt)
    if not rows:
        raise LiveSchemaError("acquisition receipt has no local documents")
    seen: set[str] = set()
    listed_input_refs = {canonical_relative_ref(str(row["file_ref"]))[0] for row in rows}
    actual_input_refs = regular_files(source_root)
    if actual_input_refs != listed_input_refs:
        raise LiveSchemaError("acquisition receipt must enumerate exactly all local source files")
    document_records: list[dict[str, Any]] = []
    physical_members: list[dict[str, Any]] = []
    receipt_copy = {
        "schema_id": ACQUISITION_SCHEMA_ID,
        "schema_version": LIVE_TOOL_SCHEMA_VERSION,
        "mode": "LOCAL_FIXTURE_ONLY",
        "rows": rows,
        "integrity": {},
    }
    receipt_copy = seal(receipt_copy)
    _write_json(target / "acquisition_receipt.json", receipt_copy)
    physical_members.append(_member(target / "acquisition_receipt.json", target))
    for index, raw in enumerate(sorted(rows, key=lambda item: str(item["file_ref"]))):
        file_ref = safe_relative_path(raw["file_ref"], path=f"$.rows[{index}].file_ref")
        _, case_key = canonical_relative_ref(file_ref)
        if case_key in seen:
            raise LiveSchemaError("duplicate or case-confusable receipt file_ref")
        seen.add(case_key)
        source_id = require_string(raw["source_id"], path=f"$.rows[{index}].source_id")
        canonical_url = require_string(raw["canonical_url"], path=f"$.rows[{index}].canonical_url")
        final_url = require_string(raw.get("final_url", canonical_url), path=f"$.rows[{index}].final_url")
        content_type = require_string(raw["content_type"], path=f"$.rows[{index}].content_type")
        redirect_chain = raw.get("redirect_chain", [])
        if not isinstance(redirect_chain, list) or any(not isinstance(item, str) for item in redirect_chain):
            raise LiveSchemaError("redirect_chain must be a string list")
        admission = admit_source(
            registry,
            source_id=source_id,
            canonical_url=canonical_url,
            final_url=final_url,
            content_type=content_type,
            redirect_chain=redirect_chain,
        )
        supplied = resolve_artifact_file(source_root, file_ref)
        body = supplied.read_bytes()
        if not body:
            raise LiveSchemaError(f"empty controlled source bytes: {file_ref}")
        document_ref = f"documents/{file_ref}"
        extraction_ref = f"extractions/{file_ref}.txt"
        destination = target.joinpath(*document_ref.split("/"))
        extraction_destination = target.joinpath(*extraction_ref.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        extraction_destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        fetched = FetchedDocument(
            canonical_url=final_url,
            content_type=content_type,
            body=body,
            content_sha256=hashlib.sha256(body).hexdigest(),
            from_cache=False,
            retrieved_at=str(raw.get("retrieved_at_utc", "1970-01-01T00:00:00Z")),
            http_status=int(raw.get("http_status", 200)),
            response_headers=(),
            fetch_policy_version="EControlledCorpusSnapshotV1",
            robots_status="NOT_APPLICABLE_LOCAL_FIXTURE",
            redirect_chain=tuple(redirect_chain),
        )
        extracted = extract_document(fetched)
        extraction_bytes = extracted.text.encode("utf-8")
        extraction_destination.write_bytes(extraction_bytes)
        physical_members.extend(
            [_member(destination, target), _member(extraction_destination, target)]
        )
        document_records.append(
            {
                "document_id": "doc_" + hashlib.sha256((source_id + "\0" + final_url + "\0" + hashlib.sha256(body).hexdigest()).encode("utf-8")).hexdigest()[:32],
                "source_id": source_id,
                "canonical_url": canonical_url,
                "final_url": final_url,
                "content_type": content_type.split(";", 1)[0].strip().casefold(),
                "content_size_bytes": len(body),
                "content_physical_sha256": hashlib.sha256(body).hexdigest(),
                "retrieved_at_utc": fetched.retrieved_at,
                "text_extraction_sha256": hashlib.sha256(extraction_bytes).hexdigest(),
                "extractor_id": "vietnamese_attestation_extractor",
                "extractor_version": EXTRACTOR_VERSION,
                "document_ref": document_ref,
                "extraction_ref": extraction_ref,
                "redirect_chain": list(redirect_chain),
                "registry_admission": admission,
            }
        )
    document_records.sort(key=lambda row: row["document_id"])
    physical_members.sort(key=lambda row: row["path"])
    physical_digest = canonical_sha256(physical_members)
    manifest = seal(
        {
            "schema_id": SNAPSHOT_SCHEMA_ID,
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "snapshot_id": "e-corpus-snapshot-" + physical_digest[:24],
            "mode": "LOCAL_FIXTURE_ONLY",
            "documents": document_records,
            "member_manifest": physical_members,
            "registry_binding": {
                "registry_self_sha256": registry["integrity"]["self_sha256"],
                "registry_physical_sha256": registry_physical_sha256 or registry["integrity"]["self_sha256"],
            },
            "retrieval_policy_binding": {
                "retrieval_policy_self_sha256": retrieval_policy["integrity"]["self_sha256"],
                "retrieval_policy_physical_sha256": retrieval_policy_physical_sha256 or retrieval_policy["integrity"]["self_sha256"],
            },
            "acquisition_receipt_sha256": canonical_sha256(receipt_copy),
            "producer": {"producer_id": "e-controlled-corpus-snapshot-builder", "producer_commit": producer_commit, "producer_tree": producer_tree},
            "document_count": len(document_records),
            "total_document_bytes": sum(row["content_size_bytes"] for row in document_records),
            "ordered_document_ids": [row["document_id"] for row in document_records],
            "physical_inventory_sha256": physical_digest,
            "integrity": {},
        }
    )
    _write_json(target / SNAPSHOT_MANIFEST_NAME, manifest)
    checksums = _write_checksums(target)
    result = dict(manifest)
    result["checksums_sha256"] = hashlib.sha256(checksums).hexdigest()
    return result


def verify_snapshot(
    snapshot: str | Path,
    *,
    expected_registry_self_sha256: str | None = None,
    expected_retrieval_policy_self_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify a directory or deterministic ZIP without network access."""
    supplied = Path(snapshot).absolute()
    reject_link(supplied)
    if supplied.is_file() and supplied.suffix.casefold() == ".zip":
        with tempfile.TemporaryDirectory(prefix="e_snapshot_verify_") as temporary:
            root = Path(temporary)
            _extract_safe_zip(supplied, root)
            return _verify_directory(root, expected_registry_self_sha256, expected_retrieval_policy_self_sha256)
    root = resolve_artifact_root(supplied)
    return _verify_directory(root, expected_registry_self_sha256, expected_retrieval_policy_self_sha256)


def inspect_snapshot(snapshot: str | Path) -> dict[str, Any]:
    verified = verify_snapshot(snapshot)
    return {
        "schema_id": verified["schema_id"],
        "schema_version": verified["schema_version"],
        "snapshot_id": verified["snapshot_id"],
        "mode": verified["mode"],
        "document_count": verified["document_count"],
        "total_document_bytes": verified["total_document_bytes"],
        "physical_inventory_sha256": verified["physical_inventory_sha256"],
        "manifest_self_sha256": verified["integrity"]["self_sha256"],
        "documents": [
            {key: row[key] for key in ("document_id", "source_id", "final_url", "content_type", "content_size_bytes")}
            for row in verified["documents"]
        ],
    }


def zip_snapshot(snapshot_root: str | Path, zip_path: str | Path) -> Path:
    root = resolve_artifact_root(snapshot_root)
    verify_snapshot(root)
    destination = Path(zip_path).absolute()
    reject_link(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise LiveSchemaError("snapshot ZIP already exists")
    files = sorted(path for path in root.rglob("*") if path.is_file())
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return destination


def _verify_directory(root: Path, expected_registry: str | None, expected_policy: str | None) -> dict[str, Any]:
    manifest_path = root / SNAPSHOT_MANIFEST_NAME
    checksums_path = root / CHECKSUMS_NAME
    manifest = load_object(manifest_path)
    require_keys(manifest, {"schema_id", "schema_version", "snapshot_id", "mode", "documents", "member_manifest", "registry_binding", "retrieval_policy_binding", "acquisition_receipt_sha256", "producer", "document_count", "total_document_bytes", "ordered_document_ids", "physical_inventory_sha256", "integrity"})
    if manifest["schema_id"] != SNAPSHOT_SCHEMA_ID or manifest["schema_version"] != LIVE_TOOL_SCHEMA_VERSION:
        raise LiveSchemaError("snapshot schema identity mismatch")
    if manifest["mode"] != "LOCAL_FIXTURE_ONLY":
        raise LiveSchemaError("only local fixture snapshots are accepted in this milestone")
    if not verify_seal(manifest):
        raise LiveSchemaError("snapshot manifest self hash mismatch")
    if expected_registry and manifest["registry_binding"]["registry_self_sha256"] != expected_registry:
        raise LiveSchemaError("snapshot registry binding mismatch")
    if expected_policy and manifest["retrieval_policy_binding"]["retrieval_policy_self_sha256"] != expected_policy:
        raise LiveSchemaError("snapshot retrieval policy binding mismatch")
    documents = manifest["documents"]
    if not isinstance(documents, list) or len(documents) != manifest["document_count"]:
        raise LiveSchemaError("snapshot document count mismatch")
    if manifest["ordered_document_ids"] != sorted(manifest["ordered_document_ids"]):
        raise LiveSchemaError("snapshot document order is not canonical")
    actual_members: list[dict[str, Any]] = []
    for row in documents:
        if not isinstance(row, Mapping):
            raise LiveSchemaError("snapshot document row is invalid")
        require_keys(row, {"document_id", "source_id", "canonical_url", "final_url", "content_type", "content_size_bytes", "content_physical_sha256", "retrieved_at_utc", "text_extraction_sha256", "extractor_id", "extractor_version", "document_ref", "extraction_ref", "redirect_chain", "registry_admission"})
        doc_path = resolve_artifact_file(root, row["document_ref"])
        extraction_path = resolve_artifact_file(root, row["extraction_ref"])
        body = doc_path.read_bytes()
        extracted = extraction_path.read_bytes()
        if len(body) != row["content_size_bytes"] or file_sha256(doc_path) != row["content_physical_sha256"]:
            raise LiveSchemaError("snapshot source byte hash/size mismatch")
        if file_sha256(extraction_path) != row["text_extraction_sha256"]:
            raise LiveSchemaError("snapshot extraction hash mismatch")
        actual_members.extend([_member(doc_path, root), _member(extraction_path, root)])
    receipt_path = root / "acquisition_receipt.json"
    receipt = load_object(receipt_path)
    if receipt.get("schema_id") != ACQUISITION_SCHEMA_ID or not verify_seal(receipt):
        raise LiveSchemaError("acquisition receipt is invalid")
    if canonical_sha256(receipt) != manifest["acquisition_receipt_sha256"]:
        raise LiveSchemaError("acquisition receipt binding mismatch")
    actual_members.append(_member(receipt_path, root))
    actual_members.sort(key=lambda item: item["path"])
    if actual_members != manifest["member_manifest"]:
        raise LiveSchemaError("snapshot member manifest mismatch")
    if canonical_sha256(actual_members) != manifest["physical_inventory_sha256"]:
        raise LiveSchemaError("snapshot physical inventory mismatch")
    _verify_checksums(root, checksums_path)
    return manifest


def _receipt_rows(receipt: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(receipt, Mapping):
        if receipt.get("schema_id") == ACQUISITION_SCHEMA_ID:
            rows = receipt.get("rows")
        else:
            rows = receipt.get("documents") or receipt.get("rows")
    else:
        rows = receipt
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise LiveSchemaError("acquisition receipt rows are required")
    result = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise LiveSchemaError(f"acquisition receipt row {index} is invalid")
        require_keys(row, {"file_ref", "source_id", "canonical_url", "content_type"}, path=f"$.rows[{index}]")
        result.append(dict(row))
    return result


def _member(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    return {"path": relative, "sha256": file_sha256(path), "size": path.stat().st_size}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def _write_checksums(root: Path) -> bytes:
    rows = []
    for path in sorted(path for path in root.rglob("*") if path.is_file() and path.name != CHECKSUMS_NAME):
        rows.append(f"{file_sha256(path)}  {path.relative_to(root).as_posix()}")
    raw = ("\n".join(rows) + "\n").encode("utf-8")
    (root / CHECKSUMS_NAME).write_bytes(raw)
    return raw


def _verify_checksums(root: Path, path: Path) -> None:
    if not path.is_file():
        raise LiveSchemaError("snapshot CHECKSUMS is missing")
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or "  " not in line:
            raise LiveSchemaError("snapshot CHECKSUMS row is malformed")
        digest, ref = line.split("  ", 1)
        require_sha256(digest, path="CHECKSUMS.sha256")
        ref, case_key = canonical_relative_ref(ref)
        if case_key in seen:
            raise LiveSchemaError("duplicate CHECKSUMS path")
        seen.add(case_key)
        actual = resolve_artifact_file(root, ref)
        if file_sha256(actual) != digest:
            raise LiveSchemaError(f"CHECKSUMS hash mismatch: {ref}")
    actual_refs = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != CHECKSUMS_NAME
    }
    if actual_refs != seen:
        raise LiveSchemaError("CHECKSUMS does not enumerate the exact snapshot files")


def _extract_safe_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        names: set[str] = set()
        for info in archive.infolist():
            ref, case_key = canonical_relative_ref(info.filename)
            if case_key in names:
                raise LiveSchemaError("ZIP contains duplicate/case-confusable member")
            names.add(case_key)
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise LiveSchemaError("ZIP symlink/directory member is forbidden")
            path = destination.joinpath(*ref.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(info))


__all__ = ["ACQUISITION_SCHEMA_ID", "SNAPSHOT_SCHEMA_ID", "build_snapshot", "inspect_snapshot", "verify_snapshot", "zip_snapshot"]
