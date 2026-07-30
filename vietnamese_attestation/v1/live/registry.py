"""Fail-closed controlled Vietnamese source registry for E Live."""

from __future__ import annotations

import fnmatch
import urllib.parse
from typing import Any, Mapping, Sequence

from .common import (
    LIVE_TOOL_SCHEMA_VERSION,
    LiveSchemaError,
    canonical_sha256,
    require_bool,
    require_keys,
    require_sha256,
    require_string,
    seal,
    verify_seal,
)

REGISTRY_SCHEMA_ID = "ControlledVietnameseSourceRegistryV1"
SOURCE_TIERS = frozenset({"A", "B", "C", "D"})
SOURCE_TYPES = frozenset({"OFFICIAL", "ACADEMIC", "PUBLISHER", "REFERENCE", "FIXTURE"})


def make_registry(
    records: Sequence[Mapping[str, Any]],
    *,
    authority_receipt_ref: str,
    authority_receipt_sha256: str,
    approval_id: str = "controlled-registry-approval-v1",
    approved_by: str = "MAIN_RESEARCH_GOVERNANCE",
) -> dict[str, Any]:
    """Create a registry bound to an external approval receipt.

    The receipt is an identity binding only. E never infers approval from the
    registry's own self hash.
    """
    normalized = [_normalize_record(row) for row in records]
    normalized.sort(key=lambda row: row["source_id"])
    return seal(
        {
            "schema_id": REGISTRY_SCHEMA_ID,
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "registry_id": "controlled-vietnamese-source-registry-v1",
            "records": normalized,
            "authority": {
                "approval_status": "APPROVED_EXTERNALLY",
                "approval_id": approval_id,
                "approved_by": approved_by,
                "authority_receipt_ref": authority_receipt_ref,
                "authority_receipt_sha256": authority_receipt_sha256,
            },
            "integrity": {},
        }
    )


def validate_registry(value: Mapping[str, Any]) -> dict[str, Any]:
    require_keys(
        value,
        {"schema_id", "schema_version", "registry_id", "records", "authority", "integrity"},
    )
    if value["schema_id"] != REGISTRY_SCHEMA_ID or value["schema_version"] != LIVE_TOOL_SCHEMA_VERSION:
        raise LiveSchemaError("registry schema identity mismatch")
    if not isinstance(value["registry_id"], str) or not value["registry_id"].strip():
        raise LiveSchemaError("registry_id must be nonempty")
    authority = value["authority"]
    if not isinstance(authority, Mapping):
        raise LiveSchemaError("registry authority binding is required")
    require_keys(
        authority,
        {"approval_status", "approval_id", "approved_by", "authority_receipt_ref", "authority_receipt_sha256"},
        path="$.authority",
    )
    if authority["approval_status"] != "APPROVED_EXTERNALLY":
        raise LiveSchemaError("registry has no external approval")
    for key in ("approval_id", "approved_by", "authority_receipt_ref"):
        require_string(authority[key], path=f"$.authority.{key}")
    require_sha256(authority["authority_receipt_sha256"], path="$.authority.authority_receipt_sha256")
    rows = value["records"]
    if not isinstance(rows, list) or not rows:
        raise LiveSchemaError("registry records must be nonempty")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise LiveSchemaError(f"registry record {index} must be an object")
        item = _normalize_record(row, path=f"$.records[{index}]")
        if item["source_id"] in seen:
            raise LiveSchemaError("duplicate registry source_id")
        seen.add(item["source_id"])
        normalized.append(item)
    if normalized != sorted(normalized, key=lambda row: row["source_id"]):
        raise LiveSchemaError("registry records must be deterministically ordered")
    if not verify_seal(value):
        raise LiveSchemaError("registry self hash mismatch")
    result = dict(value)
    result["records"] = normalized
    return result


def admit_source(
    registry: Mapping[str, Any],
    *,
    source_id: str,
    canonical_url: str | None = None,
    final_url: str,
    content_type: str,
    redirect_chain: Sequence[str] = (),
) -> dict[str, Any]:
    """Validate source, host, content type, and every redirect hop."""
    checked = validate_registry(registry)
    records = {row["source_id"]: row for row in checked["records"]}
    if source_id not in records:
        raise LiveSchemaError("unknown source_id")
    record = records[source_id]
    if not record["allowed"]:
        raise LiveSchemaError("source is not allowed")
    normalized_type = content_type.split(";", 1)[0].strip().casefold()
    if normalized_type not in record["allowed_content_types"]:
        raise LiveSchemaError("content type is not allowed by registry")
    urls = [*( [canonical_url] if canonical_url else [] ), *redirect_chain, final_url]
    for url in urls:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme not in {"http", "https", "fixture"} or not host:
            raise LiveSchemaError("source URL is not canonical/hosted")
        if not _host_matches(record["host_pattern"], host):
            raise LiveSchemaError("redirect or final host is outside source authority")
    return {
        "source_id": source_id,
        "host_pattern": record["host_pattern"],
        "source_tier": record["source_tier"],
        "source_type": record["source_type"],
        "domain_tags": list(record["domain_tags"]),
        "content_type": normalized_type,
        "final_url": final_url,
        "redirect_chain": list(redirect_chain),
        "registry_self_sha256": checked["integrity"]["self_sha256"],
        "authority_receipt_sha256": checked["authority"]["authority_receipt_sha256"],
    }


def source_record(registry: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    checked = validate_registry(registry)
    for row in checked["records"]:
        if row["source_id"] == source_id:
            return dict(row)
    raise LiveSchemaError("unknown source_id")


def _normalize_record(row: Mapping[str, Any], *, path: str = "$") -> dict[str, Any]:
    require_keys(
        row,
        {"source_id", "host_pattern", "source_tier", "source_type", "allowed_content_types", "allowed", "domain_tags"},
        path=path,
    )
    source_id = require_string(row["source_id"], path=f"{path}.source_id")
    host_pattern = require_string(row["host_pattern"], path=f"{path}.host_pattern").casefold()
    if "\\" in host_pattern or ":" in host_pattern or "/" in host_pattern or ".." in host_pattern:
        raise LiveSchemaError(f"{path}.host_pattern is not canonical")
    tier = require_string(row["source_tier"], path=f"{path}.source_tier")
    source_type = require_string(row["source_type"], path=f"{path}.source_type")
    if tier not in SOURCE_TIERS or source_type not in SOURCE_TYPES:
        raise LiveSchemaError(f"{path} source tier/type is unsupported")
    types = row["allowed_content_types"]
    if not isinstance(types, list) or not types or any(not isinstance(item, str) or not item.strip() for item in types):
        raise LiveSchemaError(f"{path}.allowed_content_types is invalid")
    tags = row["domain_tags"]
    if not isinstance(tags, list) or any(not isinstance(item, str) or not item.strip() for item in tags):
        raise LiveSchemaError(f"{path}.domain_tags is invalid")
    return {
        "source_id": source_id,
        "host_pattern": host_pattern,
        "source_tier": tier,
        "source_type": source_type,
        "allowed_content_types": sorted({item.split(";", 1)[0].strip().casefold() for item in types}),
        "allowed": require_bool(row["allowed"], path=f"{path}.allowed"),
        "domain_tags": sorted(set(tags)),
    }


def _host_matches(pattern: str, host: str) -> bool:
    pattern = pattern.casefold().strip()
    host = host.casefold().strip(".")
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return host.endswith(suffix) and host != suffix[1:]
    return fnmatch.fnmatchcase(host, pattern)


__all__ = ["REGISTRY_SCHEMA_ID", "admit_source", "make_registry", "source_record", "validate_registry"]
