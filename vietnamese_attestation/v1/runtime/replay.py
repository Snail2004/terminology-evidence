"""Verified readers for stage-bound Evidence E audit replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .audit import AUDIT_SCHEMA_ID, AUDIT_SCHEMA_VERSION, REPLAY_MODES


_MODE_STREAMS = {
    "REPLAY_FROM_SEARCH": ("search_attempts", "search_results"),
    "REPLAY_FROM_FETCH": (
        "search_attempts",
        "search_results",
        "url_attempts",
    ),
    "REPLAY_FROM_EXTRACTION": (
        "search_attempts",
        "search_results",
        "url_attempts",
        "extraction_attempts",
    ),
    "REPLAY_FROM_SNIPPETS": (
        "search_attempts",
        "search_results",
        "url_attempts",
        "extraction_attempts",
        "span_observations",
        "dedup_clusters",
    ),
    "REPLAY_FROM_JUDGE": (
        "search_attempts",
        "search_results",
        "url_attempts",
        "extraction_attempts",
        "span_observations",
        "dedup_clusters",
        "judge_attempts",
    ),
}


class AuditReplayReader:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = Path(manifest_path).resolve()
        self.run_root = self.manifest_path.parent
        self.manifest = json.loads(
            self.manifest_path.read_text(encoding="utf-8")
        )
        self._validate_manifest()

    def replay(self, mode: str) -> dict[str, Any]:
        if mode not in _MODE_STREAMS:
            raise ValueError("unsupported audit replay mode")
        streams = {
            name: self.load_stream(name) for name in _MODE_STREAMS[mode]
        }
        return {
            "mode": mode,
            "run_spec_id": self.manifest["run_spec_id"],
            "attestation_execution_id": self.manifest[
                "attestation_execution_id"
            ],
            "streams": streams,
        }

    def load_stream(self, name: str) -> list[dict[str, Any]]:
        try:
            record = self.manifest["streams"][name]
        except KeyError as exc:
            raise ValueError(f"unknown replay stream: {name}") from exc
        path = self._resolved_ref(record["artifact_ref"])
        raw = path.read_bytes() if path.is_file() else b""
        if hashlib.sha256(raw).hexdigest() != record["artifact_sha256"]:
            raise ValueError(f"audit stream hash mismatch: {name}")
        rows = [json.loads(line) for line in raw.splitlines() if line]
        if len(rows) != record["row_count"]:
            raise ValueError(f"audit stream row count mismatch: {name}")
        return rows

    def load_blob(self, artifact_ref: str, expected_sha256: str) -> bytes:
        path = self._resolved_ref(artifact_ref)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("audit blob hash mismatch")
        return raw

    def verify_all_content(self) -> None:
        for name in self.manifest["streams"]:
            self.load_stream(name)
        for directory in (
            "search/responses",
            "fetch/bodies",
            "extraction/texts",
            "judge/responses",
        ):
            root = self.run_root / directory
            if not root.is_dir():
                continue
            for path in root.iterdir():
                if not path.is_file() or path.name.endswith(".tmp"):
                    continue
                expected = path.name.split(".", 1)[0]
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError(f"content-addressed blob mismatch: {path}")

    def _validate_manifest(self) -> None:
        if self.manifest.get("schema_id") != AUDIT_SCHEMA_ID:
            raise ValueError("audit manifest schema ID mismatch")
        if self.manifest.get("schema_version") != AUDIT_SCHEMA_VERSION:
            raise ValueError("audit manifest schema version mismatch")
        if set(self.manifest.get("replay_modes", ())) != set(REPLAY_MODES):
            raise ValueError("audit replay mode set mismatch")
        if not isinstance(self.manifest.get("streams"), dict):
            raise ValueError("audit manifest streams are missing")

    def _resolved_ref(self, artifact_ref: str) -> Path:
        value = str(artifact_ref).replace("\\", "/")
        if value.startswith("/") or ":" in value or ".." in value.split("/"):
            raise ValueError("audit artifact reference is not relative")
        path = (self.run_root / value).resolve()
        try:
            path.relative_to(self.run_root)
        except ValueError as exc:
            raise ValueError("audit artifact escapes the run root") from exc
        return path


__all__ = ["AuditReplayReader"]
