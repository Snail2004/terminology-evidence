"""Verified readers for stage-bound Evidence E audit replay."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from ..strict_json import (
    canonical_relative_ref,
    reject_link,
    reject_symlink_tree,
    strict_json_loads,
    strict_jsonl_loads,
)

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
_ALL_STREAMS = frozenset(
    stream for streams in _MODE_STREAMS.values() for stream in streams
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


class AuditReplayReader:
    def __init__(
        self,
        manifest_path: Path,
        *,
        expected_manifest_sha256: str | None = None,
    ) -> None:
        supplied = Path(manifest_path).absolute()
        reject_link(supplied)
        self.manifest_path = supplied.resolve(strict=True)
        reject_link(self.manifest_path)
        self.run_root = self.manifest_path.parent
        reject_link(self.run_root)
        raw = self.manifest_path.read_bytes()
        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        if expected_manifest_sha256 is not None:
            if (
                not isinstance(expected_manifest_sha256, str)
                or _SHA256.fullmatch(expected_manifest_sha256) is None
            ):
                raise ValueError("expected audit manifest SHA-256 is invalid")
            if self.manifest_sha256 != expected_manifest_sha256:
                raise ValueError("audit manifest authority SHA-256 mismatch")
        try:
            value = strict_json_loads(raw.decode("utf-8", errors="strict"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError("invalid strict audit manifest JSON") from exc
        if not isinstance(value, Mapping):
            raise ValueError("audit manifest must be an object")
        self.manifest = dict(value)
        self._validate_manifest()

    def replay(self, mode: str) -> dict[str, Any]:
        if mode not in _MODE_STREAMS:
            raise ValueError("unsupported audit replay mode")
        streams = {
            name: self.load_stream(name) for name in _MODE_STREAMS[mode]
        }
        return {
            "mode": mode,
            "manifest_sha256": self.manifest_sha256,
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
        path = self._resolved_ref(record["artifact_ref"], require_file=False)
        raw = path.read_bytes() if path.is_file() else b""
        if hashlib.sha256(raw).hexdigest() != record["artifact_sha256"]:
            raise ValueError(f"audit stream hash mismatch: {name}")
        try:
            rows = strict_jsonl_loads(
                raw.decode("utf-8", errors="strict"), source=record["artifact_ref"]
            )
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f"invalid strict audit stream: {name}") from exc
        if len(rows) != record["row_count"]:
            raise ValueError(f"audit stream row count mismatch: {name}")
        return rows

    def load_blob(self, artifact_ref: str, expected_sha256: str) -> bytes:
        path = self._resolved_ref(artifact_ref, require_file=True)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("audit blob hash mismatch")
        return raw

    def verify_all_content(self) -> None:
        reject_symlink_tree(self.run_root)
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
        if set(self.manifest["streams"]) != _ALL_STREAMS:
            raise ValueError("audit manifest stream set mismatch")
        for name, record in self.manifest["streams"].items():
            if not isinstance(record, Mapping) or set(record) != {
                "artifact_ref",
                "artifact_sha256",
                "row_count",
            }:
                raise ValueError(f"audit stream record is invalid: {name}")
            canonical_relative_ref(record["artifact_ref"])
            if (
                not isinstance(record["artifact_sha256"], str)
                or _SHA256.fullmatch(record["artifact_sha256"]) is None
            ):
                raise ValueError(f"audit stream SHA-256 is invalid: {name}")
            if type(record["row_count"]) is not int or record["row_count"] < 0:
                raise ValueError(f"audit stream row count is invalid: {name}")

    def _resolved_ref(self, artifact_ref: str, *, require_file: bool) -> Path:
        value, _ = canonical_relative_ref(artifact_ref)
        supplied = self.run_root.joinpath(*value.split("/"))
        reject_link(supplied)
        path = supplied.resolve(strict=False)
        try:
            path.relative_to(self.run_root)
        except ValueError as exc:
            raise ValueError("audit artifact escapes the run root") from exc
        if require_file and not path.is_file():
            raise ValueError("audit artifact is not a regular file")
        if path.exists() and not path.is_file():
            raise ValueError("audit artifact is not a regular file")
        return path


__all__ = ["AuditReplayReader"]
