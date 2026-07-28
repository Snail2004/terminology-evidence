from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vietnamese_attestation.v1.zero_api.controlled_registry import (
    EMPTY_REGISTRY_SHA256,
    inspect_controlled_registry,
)


def test_empty_dataset_registry_is_bound_and_blocked_honestly(
    tmp_path: Path,
) -> None:
    path = tmp_path / "controlled.jsonl"
    path.write_bytes(b"")

    report = inspect_controlled_registry(
        path, expected_sha256=EMPTY_REGISTRY_SHA256
    )

    assert report["physical_sha256"] == EMPTY_REGISTRY_SHA256
    assert report["row_count"] == 0
    assert report["status"] == "BLOCKED_EXTERNAL_INPUT"
    assert report["blockers"] == ["CONTROLLED_VIETNAMESE_REGISTRY_EMPTY"]
    assert report["retrieval_provider_created"] is False
    assert report["provider_call_count"] == 0


def test_nonempty_minimum_registry_stays_blocked_until_schema_freeze(
    tmp_path: Path,
) -> None:
    path = tmp_path / "controlled.jsonl"
    row = {
        "source_id": "source-1",
        "organization_id": "org-1",
        "document_id": "doc-1",
        "content_hash": "a" * 64,
        "dedup_group_id": "dedup-1",
        "source_tier": "UNIVERSITY_TEXTBOOK",
    }
    raw = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(raw, encoding="utf-8")

    report = inspect_controlled_registry(
        path,
        expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )

    assert report["row_count"] == 1
    assert report["blockers"] == [
        "CONTROLLED_REGISTRY_RETRIEVAL_SCHEMA_NOT_FROZEN"
    ]
    assert report["retrieval_provider_created"] is False


def test_registry_rejects_hash_drift_and_malformed_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "controlled.jsonl"
    path.write_text(
        json.dumps(
            {
                "source_id": "source-1",
                "organization_id": "org-1",
                "document_id": "doc-1",
                "content_hash": "not-a-hash",
                "dedup_group_id": "dedup-1",
                "source_tier": "OPEN_WEB",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="physical SHA-256 mismatch"):
        inspect_controlled_registry(path, expected_sha256="0" * 64)
    with pytest.raises(ValueError, match="content_hash is not SHA-256"):
        inspect_controlled_registry(path)
