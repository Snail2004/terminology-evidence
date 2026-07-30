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
    require_exact_keys,
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
from .authority_adapter import (
    validate_authority_profile,
    validate_loaded_authority_bundle,
)

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
    acquisition_receipt_source: str | Path | None = None,
    authority_bundle: Mapping[str, Any] | None = None,
    authority_receipt_paths: Mapping[str, str | Path] | None = None,
    authority_profile_path: str | Path | None = None,
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
    original_receipt = _original_receipt_bytes(
        acquisition_receipt, acquisition_receipt_source=acquisition_receipt_source
    )
    original_receipt_ref = "authority/acquisition_receipt.original.json"
    original_receipt_path = target.joinpath(*original_receipt_ref.split("/"))
    original_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    original_receipt_path.write_bytes(original_receipt)
    physical_members.append(_member(original_receipt_path, target))
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
    authority_binding, authority_members = _persist_authority_bundle(
        target,
        authority_bundle=authority_bundle,
        authority_receipt_paths=authority_receipt_paths,
        authority_profile_path=authority_profile_path,
        original_receipt_ref=original_receipt_ref,
        original_receipt_sha256=hashlib.sha256(original_receipt).hexdigest(),
        normalized_receipt_self_sha256=receipt_copy["integrity"]["self_sha256"],
        source_kind="EXACT_EXTERNAL_FILE" if acquisition_receipt_source is not None else "CANONICAL_IN_MEMORY_FIXTURE",
    )
    physical_members.extend(authority_members)
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
            "authority_binding": authority_binding,
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
    files = _sorted_release_files(root)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            info.external_attr = 0
            info.extra = b""
            info.comment = b""
            archive.writestr(info, path.read_bytes())
    return destination


def _verify_directory(root: Path, expected_registry: str | None, expected_policy: str | None) -> dict[str, Any]:
    manifest_path = root / SNAPSHOT_MANIFEST_NAME
    checksums_path = root / CHECKSUMS_NAME
    manifest = load_object(manifest_path)
    require_exact_keys(manifest, {"schema_id", "schema_version", "snapshot_id", "mode", "documents", "member_manifest", "registry_binding", "retrieval_policy_binding", "authority_binding", "acquisition_receipt_sha256", "producer", "document_count", "total_document_bytes", "ordered_document_ids", "physical_inventory_sha256", "integrity"})
    if manifest["schema_id"] != SNAPSHOT_SCHEMA_ID or manifest["schema_version"] != LIVE_TOOL_SCHEMA_VERSION:
        raise LiveSchemaError("snapshot schema identity mismatch")
    _validate_snapshot_manifest_nesting(manifest)
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
        _validate_document_row(row)
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
    _validate_acquisition_receipt(receipt)
    if receipt.get("schema_id") != ACQUISITION_SCHEMA_ID or not verify_seal(receipt):
        raise LiveSchemaError("acquisition receipt is invalid")
    if canonical_sha256(receipt) != manifest["acquisition_receipt_sha256"]:
        raise LiveSchemaError("acquisition receipt binding mismatch")
    actual_members.append(_member(receipt_path, root))
    authority_members = _verify_authority_binding(root, manifest["authority_binding"], receipt)
    actual_members.extend(authority_members)
    actual_members.sort(key=lambda item: item["path"])
    if actual_members != manifest["member_manifest"]:
        raise LiveSchemaError("snapshot member manifest mismatch")
    if canonical_sha256(actual_members) != manifest["physical_inventory_sha256"]:
        raise LiveSchemaError("snapshot physical inventory mismatch")
    _verify_checksums(root, checksums_path)
    return manifest


def _validate_snapshot_manifest_nesting(manifest: Mapping[str, Any]) -> None:
    for key in ("registry_binding", "retrieval_policy_binding", "producer", "integrity"):
        if not isinstance(manifest[key], Mapping):
            raise LiveSchemaError(f"snapshot {key} must be an object")
    require_exact_keys(
        manifest["registry_binding"],
        {"registry_self_sha256", "registry_physical_sha256"},
        path="$.registry_binding",
    )
    require_exact_keys(
        manifest["retrieval_policy_binding"],
        {"retrieval_policy_self_sha256", "retrieval_policy_physical_sha256"},
        path="$.retrieval_policy_binding",
    )
    require_exact_keys(
        manifest["producer"],
        {"producer_id", "producer_commit", "producer_tree"},
        path="$.producer",
    )
    require_exact_keys(manifest["integrity"], {"self_sha256"}, path="$.integrity")
    for path, value in (
        ("$.registry_binding.registry_self_sha256", manifest["registry_binding"]["registry_self_sha256"]),
        ("$.registry_binding.registry_physical_sha256", manifest["registry_binding"]["registry_physical_sha256"]),
        ("$.retrieval_policy_binding.retrieval_policy_self_sha256", manifest["retrieval_policy_binding"]["retrieval_policy_self_sha256"]),
        ("$.retrieval_policy_binding.retrieval_policy_physical_sha256", manifest["retrieval_policy_binding"]["retrieval_policy_physical_sha256"]),
        ("$.acquisition_receipt_sha256", manifest["acquisition_receipt_sha256"]),
        ("$.physical_inventory_sha256", manifest["physical_inventory_sha256"]),
        ("$.integrity.self_sha256", manifest["integrity"]["self_sha256"]),
    ):
        require_sha256(value, path=path)
    for key in ("producer_id", "producer_commit", "producer_tree"):
        require_string(manifest["producer"][key], path=f"$.producer.{key}")
    members = manifest["member_manifest"]
    if not isinstance(members, list):
        raise LiveSchemaError("snapshot member_manifest must be a list")
    member_paths = []
    for index, row in enumerate(members):
        if not isinstance(row, Mapping):
            raise LiveSchemaError("snapshot member row must be an object")
        require_exact_keys(row, {"path", "sha256", "size"}, path=f"$.member_manifest[{index}]")
        member_paths.append(safe_relative_path(row["path"], path=f"$.member_manifest[{index}].path"))
        require_sha256(row["sha256"], path=f"$.member_manifest[{index}].sha256")
        if isinstance(row["size"], bool) or not isinstance(row["size"], int) or row["size"] < 0:
            raise LiveSchemaError("snapshot member size must be nonnegative")
    if member_paths != sorted(member_paths) or len(member_paths) != len(set(path.casefold() for path in member_paths)):
        raise LiveSchemaError("snapshot member_manifest order/path set is not canonical")


def _validate_document_row(row: Mapping[str, Any]) -> None:
    require_exact_keys(
        row,
        {
            "document_id",
            "source_id",
            "canonical_url",
            "final_url",
            "content_type",
            "content_size_bytes",
            "content_physical_sha256",
            "retrieved_at_utc",
            "text_extraction_sha256",
            "extractor_id",
            "extractor_version",
            "document_ref",
            "extraction_ref",
            "redirect_chain",
            "registry_admission",
        },
        path="$.documents[]",
    )
    for key in ("document_id", "source_id", "canonical_url", "final_url", "content_type", "retrieved_at_utc", "extractor_id", "extractor_version"):
        require_string(row[key], path=f"$.documents[].{key}")
    for key in ("content_physical_sha256", "text_extraction_sha256"):
        require_sha256(row[key], path=f"$.documents[].{key}")
    safe_relative_path(row["document_ref"], path="$.documents[].document_ref")
    safe_relative_path(row["extraction_ref"], path="$.documents[].extraction_ref")
    if isinstance(row["content_size_bytes"], bool) or not isinstance(row["content_size_bytes"], int) or row["content_size_bytes"] < 0:
        raise LiveSchemaError("snapshot document size must be nonnegative")
    if not isinstance(row["redirect_chain"], list) or any(not isinstance(item, str) for item in row["redirect_chain"]):
        raise LiveSchemaError("snapshot redirect_chain must be a string list")
    admission = row["registry_admission"]
    if not isinstance(admission, Mapping):
        raise LiveSchemaError("snapshot registry_admission must be an object")
    require_exact_keys(
        admission,
        {
            "source_id",
            "host_pattern",
            "source_tier",
            "source_type",
            "domain_tags",
            "content_type",
            "final_url",
            "redirect_chain",
            "registry_self_sha256",
            "authority_receipt_sha256",
        },
        path="$.documents[].registry_admission",
    )


def _validate_acquisition_receipt(receipt: Mapping[str, Any]) -> None:
    require_exact_keys(
        receipt,
        {"schema_id", "schema_version", "mode", "rows", "integrity"},
        path="$.acquisition_receipt",
    )
    if receipt["schema_id"] != ACQUISITION_SCHEMA_ID or receipt["schema_version"] != LIVE_TOOL_SCHEMA_VERSION or receipt["mode"] != "LOCAL_FIXTURE_ONLY":
        raise LiveSchemaError("acquisition receipt identity/mode mismatch")
    if not isinstance(receipt["integrity"], Mapping):
        raise LiveSchemaError("acquisition receipt integrity must be an object")
    require_exact_keys(receipt["integrity"], {"self_sha256"}, path="$.acquisition_receipt.integrity")
    require_sha256(receipt["integrity"]["self_sha256"], path="$.acquisition_receipt.integrity.self_sha256")
    _receipt_rows(receipt)


def _original_receipt_bytes(
    receipt: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    acquisition_receipt_source: str | Path | None,
) -> bytes:
    if acquisition_receipt_source is None:
        return canonical_bytes(receipt)
    supplied = Path(acquisition_receipt_source).absolute()
    reject_link(supplied)
    resolved = supplied.resolve(strict=True)
    reject_link(resolved)
    if not resolved.is_file():
        raise LiveSchemaError("acquisition receipt source is not a regular file")
    loaded = load_object(resolved)
    if _receipt_rows(loaded) != _receipt_rows(receipt):
        raise LiveSchemaError("acquisition receipt source bytes differ from supplied receipt")
    return resolved.read_bytes()


def _persist_authority_bundle(
    target: Path,
    *,
    authority_bundle: Mapping[str, Any] | None,
    authority_receipt_paths: Mapping[str, str | Path] | None,
    authority_profile_path: str | Path | None,
    original_receipt_ref: str,
    original_receipt_sha256: str,
    normalized_receipt_self_sha256: str,
    source_kind: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if authority_bundle is None:
        if authority_receipt_paths or authority_profile_path is not None:
            raise LiveSchemaError("authority files require a verified authority bundle")
        return (
            {
                "mode": "LOCAL_FIXTURE_ONLY",
                "acquisition_receipt_source_kind": source_kind,
                "acquisition_receipt_original_ref": original_receipt_ref,
                "acquisition_receipt_physical_sha256": original_receipt_sha256,
                "acquisition_receipt_self_sha256": normalized_receipt_self_sha256,
                "authority_profile_ref": None,
                "authority_profile_physical_sha256": None,
                "authority_bundle_ref": None,
                "authority_bundle_physical_sha256": None,
                "authority_bundle_self_sha256": None,
                "external_receipts": [],
            },
            [],
        )
    authority_bundle = validate_loaded_authority_bundle(authority_bundle)
    require_exact_keys(
        authority_bundle,
        {
            "schema_id",
            "schema_version",
            "execution_mode",
            "profile_binding",
            "receipt_bindings",
            "protocol_schema_bindings",
            "integrity",
        },
        path="$.authority_bundle",
    )
    paths = dict(authority_receipt_paths or {})
    bound_receipts = authority_bundle["receipt_bindings"]
    if not isinstance(bound_receipts, Mapping) or set(paths) != set(bound_receipts):
        raise LiveSchemaError("authority receipt path set differs from verified bundle")
    if authority_profile_path is None:
        raise LiveSchemaError("authority profile bytes are required with an external bundle")
    profile_source = Path(authority_profile_path).absolute()
    reject_link(profile_source)
    profile_source = profile_source.resolve(strict=True)
    reject_link(profile_source)
    profile_binding = authority_bundle["profile_binding"]
    if file_sha256(profile_source) != profile_binding["artifact_physical_sha256"]:
        raise LiveSchemaError("authority profile physical hash mismatch")
    members: list[dict[str, Any]] = []
    profile_ref = "authority/trusted_authority_profile.json"
    profile_target = target.joinpath(*profile_ref.split("/"))
    profile_target.parent.mkdir(parents=True, exist_ok=True)
    profile_target.write_bytes(profile_source.read_bytes())
    members.append(_member(profile_target, target))
    bundle_ref = "authority/loaded_authority_bundle.json"
    bundle_target = target.joinpath(*bundle_ref.split("/"))
    bundle_target.write_bytes(canonical_bytes(authority_bundle))
    members.append(_member(bundle_target, target))
    external = []
    for role in sorted(bound_receipts):
        source = Path(paths[role]).absolute()
        reject_link(source)
        source = source.resolve(strict=True)
        reject_link(source)
        binding = bound_receipts[role]
        if file_sha256(source) != binding["artifact_physical_sha256"]:
            raise LiveSchemaError(f"authority receipt physical hash drift: {role}")
        load_object(source)
        ref = f"authority/receipts/{role.casefold()}.json"
        destination = target.joinpath(*ref.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        members.append(_member(destination, target))
        external.append(
            {
                "role": role,
                "artifact_ref": ref,
                "artifact_physical_sha256": binding["artifact_physical_sha256"],
                "artifact_self_sha256": binding["artifact_self_sha256"],
            }
        )
    return (
        {
            "mode": str(authority_bundle["execution_mode"]),
            "acquisition_receipt_source_kind": source_kind,
            "acquisition_receipt_original_ref": original_receipt_ref,
            "acquisition_receipt_physical_sha256": original_receipt_sha256,
            "acquisition_receipt_self_sha256": normalized_receipt_self_sha256,
            "authority_profile_ref": profile_ref,
            "authority_profile_physical_sha256": profile_binding["artifact_physical_sha256"],
            "authority_bundle_ref": bundle_ref,
            "authority_bundle_physical_sha256": file_sha256(bundle_target),
            "authority_bundle_self_sha256": authority_bundle["integrity"]["self_sha256"],
            "external_receipts": external,
        },
        members,
    )


def _verify_authority_binding(
    root: Path, binding: Mapping[str, Any], normalized_receipt: Mapping[str, Any]
) -> list[dict[str, Any]]:
    expected = {
        "mode",
        "acquisition_receipt_source_kind",
        "acquisition_receipt_original_ref",
        "acquisition_receipt_physical_sha256",
        "acquisition_receipt_self_sha256",
        "authority_profile_ref",
        "authority_profile_physical_sha256",
        "authority_bundle_ref",
        "authority_bundle_physical_sha256",
        "authority_bundle_self_sha256",
        "external_receipts",
    }
    require_exact_keys(binding, expected, path="$.authority_binding")
    if binding["mode"] not in {"LOCAL_FIXTURE_ONLY", "PRODUCTION_AUTHORITY"}:
        raise LiveSchemaError("snapshot authority mode is unsupported")
    original_path = resolve_artifact_file(root, binding["acquisition_receipt_original_ref"])
    if file_sha256(original_path) != binding["acquisition_receipt_physical_sha256"]:
        raise LiveSchemaError("original acquisition receipt physical hash mismatch")
    original = load_object(original_path)
    if _receipt_rows(original) != normalized_receipt["rows"]:
        raise LiveSchemaError("original acquisition receipt rows differ from normalized receipt")
    if normalized_receipt["integrity"]["self_sha256"] != binding["acquisition_receipt_self_sha256"]:
        raise LiveSchemaError("normalized acquisition receipt self hash mismatch")
    members = [_member(original_path, root)]
    nullable = (
        "authority_profile_ref",
        "authority_profile_physical_sha256",
        "authority_bundle_ref",
        "authority_bundle_physical_sha256",
        "authority_bundle_self_sha256",
    )
    if binding["mode"] == "LOCAL_FIXTURE_ONLY" and all(
        binding[key] is None for key in nullable
    ) and not binding["external_receipts"]:
        return members
    for key in nullable:
        if binding[key] is None:
            raise LiveSchemaError("production snapshot authority binding is incomplete")
    profile_path = resolve_artifact_file(root, binding["authority_profile_ref"])
    bundle_path = resolve_artifact_file(root, binding["authority_bundle_ref"])
    if file_sha256(profile_path) != binding["authority_profile_physical_sha256"]:
        raise LiveSchemaError("snapshot authority profile hash mismatch")
    if file_sha256(bundle_path) != binding["authority_bundle_physical_sha256"]:
        raise LiveSchemaError("snapshot authority bundle physical hash mismatch")
    bundle = load_object(bundle_path)
    bundle = validate_loaded_authority_bundle(bundle)
    if bundle["execution_mode"] != binding["mode"]:
        raise LiveSchemaError("snapshot authority bundle mode mismatch")
    profile = validate_authority_profile(load_object(profile_path))
    if profile["status"] != (
        "DRAFT_FIXTURE_ONLY"
        if binding["mode"] == "LOCAL_FIXTURE_ONLY"
        else "MAIN_PINNED_RUNTIME_AUTHORITY"
    ):
        raise LiveSchemaError("snapshot authority profile status mismatch")
    if (
        profile["integrity"]["self_sha256"]
        != bundle["profile_binding"]["artifact_self_sha256"]
    ):
        raise LiveSchemaError("snapshot authority profile self hash mismatch")
    if not verify_seal(bundle) or bundle["integrity"]["self_sha256"] != binding["authority_bundle_self_sha256"]:
        raise LiveSchemaError("snapshot authority bundle self hash mismatch")
    members.extend([_member(profile_path, root), _member(bundle_path, root)])
    rows = binding["external_receipts"]
    if not isinstance(rows, list):
        raise LiveSchemaError("snapshot external receipt bindings must be a list")
    if {str(row.get("role")) for row in rows} != set(bundle["receipt_bindings"]):
        raise LiveSchemaError("snapshot external receipt role set mismatch")
    for index, row in enumerate(rows):
        require_exact_keys(
            row,
            {"role", "artifact_ref", "artifact_physical_sha256", "artifact_self_sha256"},
            path=f"$.authority_binding.external_receipts[{index}]",
        )
        receipt_path = resolve_artifact_file(root, row["artifact_ref"])
        if file_sha256(receipt_path) != row["artifact_physical_sha256"]:
            raise LiveSchemaError("snapshot external receipt physical hash mismatch")
        receipt = load_object(receipt_path)
        if not verify_seal(receipt) or receipt["integrity"]["self_sha256"] != row["artifact_self_sha256"]:
            raise LiveSchemaError("snapshot external receipt self hash mismatch")
        if row["artifact_self_sha256"] != bundle["receipt_bindings"][row["role"]]["artifact_self_sha256"]:
            raise LiveSchemaError("snapshot external receipt binding drift")
        members.append(_member(receipt_path, root))
    return members


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
        allowed = {
            "file_ref",
            "source_id",
            "canonical_url",
            "final_url",
            "content_type",
            "redirect_chain",
            "retrieved_at_utc",
            "http_status",
        }
        require_keys(row, {"file_ref", "source_id", "canonical_url", "content_type"}, path=f"$.rows[{index}]")
        extra = sorted(set(row) - allowed)
        if extra:
            raise LiveSchemaError(f"$.rows[{index}] unsupported keys: {', '.join(extra)}")
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
    for path in _sorted_release_files(root, exclude_names={CHECKSUMS_NAME}):
        rows.append(f"{file_sha256(path)}  {path.relative_to(root).as_posix()}")
    raw = ("\n".join(rows) + "\n").encode("utf-8")
    (root / CHECKSUMS_NAME).write_bytes(raw)
    return raw


def _sorted_release_files(root: Path, *, exclude_names: set[str] | None = None) -> list[Path]:
    excluded = exclude_names or set()
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.name not in excluded),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _verify_checksums(root: Path, path: Path) -> None:
    if not path.is_file():
        raise LiveSchemaError("snapshot CHECKSUMS is missing")
    seen: set[str] = set()
    exact_refs: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or "  " not in line:
            raise LiveSchemaError("snapshot CHECKSUMS row is malformed")
        digest, ref = line.split("  ", 1)
        require_sha256(digest, path="CHECKSUMS.sha256")
        ref, case_key = canonical_relative_ref(ref)
        if case_key in seen:
            raise LiveSchemaError("duplicate CHECKSUMS path")
        seen.add(case_key)
        exact_refs.append(ref)
        actual = resolve_artifact_file(root, ref)
        if file_sha256(actual) != digest:
            raise LiveSchemaError(f"CHECKSUMS hash mismatch: {ref}")
    if exact_refs != sorted(exact_refs):
        raise LiveSchemaError("CHECKSUMS paths are not in canonical POSIX order")
    actual_refs = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != CHECKSUMS_NAME
    }
    if actual_refs != set(exact_refs):
        raise LiveSchemaError("CHECKSUMS does not enumerate the exact snapshot files")


def _extract_safe_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        names: set[str] = set()
        exact_names: list[str] = []
        for info in archive.infolist():
            ref, case_key = canonical_relative_ref(info.filename)
            if case_key in names:
                raise LiveSchemaError("ZIP contains duplicate/case-confusable member")
            names.add(case_key)
            exact_names.append(ref)
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise LiveSchemaError("ZIP symlink/directory member is forbidden")
            path = destination.joinpath(*ref.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(info))
        if exact_names != sorted(exact_names):
            raise LiveSchemaError("ZIP members are not in canonical POSIX order")


__all__ = ["ACQUISITION_SCHEMA_ID", "SNAPSHOT_SCHEMA_ID", "build_snapshot", "inspect_snapshot", "verify_snapshot", "zip_snapshot"]
