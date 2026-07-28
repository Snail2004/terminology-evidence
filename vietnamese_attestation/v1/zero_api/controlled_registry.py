"""Fail-closed inspection for the future controlled Vietnamese registry."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


CONTROLLED_REGISTRY_SCHEMA_ID = "ControlledVietnameseRegistryInspectionV1"
CONTROLLED_REGISTRY_SCHEMA_VERSION = "1.0.0"
EMPTY_REGISTRY_SHA256 = hashlib.sha256(b"").hexdigest()
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_ALLOWED_SOURCE_TIERS = {
    "UNIVERSITY_TEXTBOOK",
    "UNIVERSITY_LECTURE",
    "PUBLISHED_TRANSLATED_BOOK",
    "PEER_REVIEWED_PAPER",
    "THESIS_DISSERTATION",
    "OFFICIAL_VENDOR_DOCUMENTATION",
    "GOVERNMENT_OR_STANDARDS_DOCUMENT",
    "OPEN_WEB",
}
_REQUIRED_IDENTITY_FIELDS = (
    "source_id",
    "organization_id",
    "document_id",
    "content_hash",
    "dedup_group_id",
    "source_tier",
)


def inspect_controlled_registry(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Inspect the immutable registry without promoting it to retrieval input.

    Dataset Methodology Hardening V1 intentionally publishes an empty registry.
    Non-empty rows are checked against the minimum dataset-owned identity fields,
    but remain blocked until a retrieval-content schema is frozen.
    """

    resolved = Path(path).resolve(strict=True)
    raw = resolved.read_bytes()
    physical_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and physical_sha256 != expected_sha256:
        raise ValueError("controlled registry physical SHA-256 mismatch")
    rows = _jsonl_rows(raw)
    _validate_rows(rows)
    blockers: list[str] = []
    if not rows:
        blockers.append("CONTROLLED_VIETNAMESE_REGISTRY_EMPTY")
    else:
        blockers.append("CONTROLLED_REGISTRY_RETRIEVAL_SCHEMA_NOT_FROZEN")
    return {
        "schema_id": CONTROLLED_REGISTRY_SCHEMA_ID,
        "schema_version": CONTROLLED_REGISTRY_SCHEMA_VERSION,
        "registry_ref": resolved.as_posix(),
        "physical_sha256": physical_sha256,
        "row_count": len(rows),
        "status": "BLOCKED_EXTERNAL_INPUT",
        "blockers": blockers,
        "retrieval_provider_created": False,
        "provider_call_count": 0,
    }


def _jsonl_rows(raw: bytes) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("controlled registry is not UTF-8") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ValueError(
                f"controlled registry contains an empty line at {line_number}"
            )
        try:
            value = json.loads(
                line,
                parse_constant=lambda item: (_ for _ in ()).throw(
                    ValueError(f"non-finite JSON value: {item}")
                ),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(
                f"invalid controlled registry JSON at line {line_number}"
            ) from exc
        if not isinstance(value, Mapping):
            raise ValueError(
                f"controlled registry row {line_number} is not an object"
            )
        rows.append(dict(value))
    return rows


def _validate_rows(rows: list[dict[str, Any]]) -> None:
    source_ids: set[str] = set()
    for index, row in enumerate(rows):
        path = f"$[{index}]"
        for field in _REQUIRED_IDENTITY_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{path}.{field} is required")
        source_id = str(row["source_id"])
        if source_id in source_ids:
            raise ValueError(f"duplicate controlled source_id: {source_id}")
        source_ids.add(source_id)
        if row["source_tier"] not in _ALLOWED_SOURCE_TIERS:
            raise ValueError(f"{path}.source_tier is unsupported")
        if not _SHA256_RE.fullmatch(str(row["content_hash"])):
            raise ValueError(f"{path}.content_hash is not SHA-256")


__all__ = [
    "CONTROLLED_REGISTRY_SCHEMA_ID",
    "CONTROLLED_REGISTRY_SCHEMA_VERSION",
    "EMPTY_REGISTRY_SHA256",
    "inspect_controlled_registry",
]
