"""Append-only, content-addressed audit storage for Evidence E runs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Protocol


AUDIT_SCHEMA_ID = "VietnameseAttestationAuditManifestV1"
AUDIT_SCHEMA_VERSION = "1.1.0"
REPLAY_MODES = (
    "REPLAY_FROM_SEARCH",
    "REPLAY_FROM_FETCH",
    "REPLAY_FROM_EXTRACTION",
    "REPLAY_FROM_SNIPPETS",
    "REPLAY_FROM_JUDGE",
)
_STREAM_PATHS = {
    "search_attempts": "search/requests.jsonl",
    "search_results": "search/normalized_results.jsonl",
    "url_attempts": "fetch/attempts.jsonl",
    "extraction_attempts": "extraction/records.jsonl",
    "span_observations": "snippets/snippets.jsonl",
    "dedup_clusters": "dedup/clusters.jsonl",
    "judge_attempts": "judge/attempts.jsonl",
}


class RunAuditStore(Protocol):
    execution_id: str

    def append(self, stream: str, row: Mapping[str, Any]) -> None: ...

    def put_json(self, namespace: str, value: Any) -> dict[str, Any]: ...

    def put_bytes(
        self, namespace: str, value: bytes, *, suffix: str = ""
    ) -> dict[str, Any]: ...

    def finalize(
        self,
        *,
        run_spec_id: str,
        started_at: str,
        completed_at: str,
    ) -> dict[str, Any]: ...


class FileRunAuditStore:
    def __init__(self, root: Path, execution_id: str) -> None:
        self.execution_id = execution_id
        self.run_root = Path(root).resolve() / "runs" / execution_id
        if self.run_root.exists():
            raise ValueError("attestation execution audit directory already exists")
        self.run_root.mkdir(parents=True, exist_ok=False)
        self._stream_counts = {name: 0 for name in _STREAM_PATHS}
        self._blob_refs: list[dict[str, Any]] = []

    def append(self, stream: str, row: Mapping[str, Any]) -> None:
        try:
            relative = _STREAM_PATHS[stream]
        except KeyError as exc:
            raise ValueError(f"unknown audit stream: {stream}") from exc
        path = self.run_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = _canonical_json(row) + b"\n"
        with path.open("ab") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        self._stream_counts[stream] += 1

    def put_json(self, namespace: str, value: Any) -> dict[str, Any]:
        return self.put_bytes(namespace, _canonical_json(value), suffix=".json")

    def put_bytes(
        self, namespace: str, value: bytes, *, suffix: str = ""
    ) -> dict[str, Any]:
        safe_namespace = _namespace(namespace)
        digest = hashlib.sha256(value).hexdigest()
        relative = f"{safe_namespace}/{digest}{suffix}"
        path = self.run_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != value:
                raise RuntimeError("content-addressed audit blob collision")
        else:
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(value)
            os.replace(tmp, path)
        ref = {
            "artifact_ref": relative.replace("\\", "/"),
            "artifact_sha256": digest,
            "byte_count": len(value),
        }
        self._blob_refs.append(ref)
        return ref

    def finalize(
        self,
        *,
        run_spec_id: str,
        started_at: str,
        completed_at: str,
    ) -> dict[str, Any]:
        streams: dict[str, dict[str, Any]] = {}
        for stream, relative in sorted(_STREAM_PATHS.items()):
            path = self.run_root / relative
            raw = path.read_bytes() if path.is_file() else b""
            streams[stream] = {
                "artifact_ref": relative,
                "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                "row_count": self._stream_counts[stream],
            }
        manifest = {
            "schema_id": AUDIT_SCHEMA_ID,
            "schema_version": AUDIT_SCHEMA_VERSION,
            "run_spec_id": run_spec_id,
            "attestation_execution_id": self.execution_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "replay_modes": list(REPLAY_MODES),
            "streams": streams,
            "blob_count": len(
                {
                    (ref["artifact_ref"], ref["artifact_sha256"])
                    for ref in self._blob_refs
                }
            ),
        }
        raw = _canonical_json(manifest) + b"\n"
        path = self.run_root / "run_manifest.json"
        tmp = self.run_root / "run_manifest.json.tmp"
        tmp.write_bytes(raw)
        os.replace(tmp, path)
        return {
            "schema_id": AUDIT_SCHEMA_ID,
            "schema_version": AUDIT_SCHEMA_VERSION,
            "run_spec_id": run_spec_id,
            "attestation_execution_id": self.execution_id,
            "store_mode": "FILE",
            "manifest_ref": f"runs/{self.execution_id}/run_manifest.json",
            "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "replay_modes": list(REPLAY_MODES),
        }


class MemoryRunAuditStore:
    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        self.streams: dict[str, list[dict[str, Any]]] = {
            name: [] for name in _STREAM_PATHS
        }
        self.blobs: dict[str, bytes] = {}

    def append(self, stream: str, row: Mapping[str, Any]) -> None:
        if stream not in self.streams:
            raise ValueError(f"unknown audit stream: {stream}")
        self.streams[stream].append(json.loads(_canonical_json(row)))

    def put_json(self, namespace: str, value: Any) -> dict[str, Any]:
        return self.put_bytes(namespace, _canonical_json(value), suffix=".json")

    def put_bytes(
        self, namespace: str, value: bytes, *, suffix: str = ""
    ) -> dict[str, Any]:
        safe_namespace = _namespace(namespace)
        digest = hashlib.sha256(value).hexdigest()
        ref = f"memory/{safe_namespace}/{digest}{suffix}"
        self.blobs[ref] = bytes(value)
        return {
            "artifact_ref": ref,
            "artifact_sha256": digest,
            "byte_count": len(value),
        }

    def finalize(
        self,
        *,
        run_spec_id: str,
        started_at: str,
        completed_at: str,
    ) -> dict[str, Any]:
        manifest = {
            "schema_id": AUDIT_SCHEMA_ID,
            "schema_version": AUDIT_SCHEMA_VERSION,
            "run_spec_id": run_spec_id,
            "attestation_execution_id": self.execution_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "replay_modes": list(REPLAY_MODES),
            "stream_counts": {
                name: len(rows) for name, rows in sorted(self.streams.items())
            },
            "blob_count": len(self.blobs),
        }
        raw = _canonical_json(manifest) + b"\n"
        return {
            "schema_id": AUDIT_SCHEMA_ID,
            "schema_version": AUDIT_SCHEMA_VERSION,
            "run_spec_id": run_spec_id,
            "attestation_execution_id": self.execution_id,
            "store_mode": "MEMORY",
            "manifest_ref": f"memory://{self.execution_id}/run_manifest.json",
            "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "replay_modes": list(REPLAY_MODES),
        }


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _namespace(value: str) -> str:
    normalized = value.replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if not normalized or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid audit namespace")
    return "/".join(parts)


__all__ = [
    "AUDIT_SCHEMA_ID",
    "AUDIT_SCHEMA_VERSION",
    "FileRunAuditStore",
    "MemoryRunAuditStore",
    "REPLAY_MODES",
    "RunAuditStore",
]
