"""Append-only AR-2 event ledger with one local exclusive writer."""

from __future__ import annotations

import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from ..jsonio import StrictJSONError, canonical_bytes, read_jsonl, sha256_value


EVENT_SCHEMA_ID = "EvaluationPreregistrationEventV1"
EVENT_SCHEMA_VERSION = "1.0.0"
GENESIS_SHA256 = "0" * 64
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class LedgerError(ValueError):
    """Raised when ledger history or its single-writer boundary is invalid."""


def _thread_lock(path: Path) -> threading.RLock:
    key = str(path.resolve()).casefold()
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def exclusive_writer_lock(path: Path, *, timeout_seconds: float = 2.0) -> Iterator[None]:
    """Acquire an in-process and OS lock; stale locks are never auto-deleted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise LedgerError("writer lock path is symlinked")
    deadline = time.monotonic() + timeout_seconds
    with _thread_lock(path):
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(descriptor, f"{os.getpid()}:{uuid.uuid4().hex}".encode("ascii"))
                os.fsync(descriptor)
            except FileExistsError as exc:
                if time.monotonic() >= deadline:
                    raise LedgerError(f"writer lock is busy: {path}") from exc
                time.sleep(0.01)
        try:
            yield
        finally:
            os.close(descriptor)
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def _fsync_parent(path: Path) -> None:
    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_publish(path: Path, data: bytes) -> None:
    """Write, fsync and atomically replace one projection/receipt file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise LedgerError("atomic publication target is symlinked")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_parent(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_create(path: Path, data: bytes) -> None:
    """Atomically create an immutable receipt without replacing existing bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise LedgerError("immutable publication target already exists")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise LedgerError("immutable publication target already exists") from exc
        _fsync_parent(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _event_hash(value: Mapping[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("event_sha256", None)
    return sha256_value(unsigned)


def _validate_hash_mapping(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise LedgerError(f"{field} must be a nonempty object")
    result: dict[str, str] = {}
    for key, digest in value.items():
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(digest, str)
            or len(digest) != 64
            or set(digest) == {"0"}
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise LedgerError(f"{field}.{key} is invalid")
        result[key] = digest
    return dict(sorted(result.items()))


class EventLedger:
    """Hash-chained JSONL ledger. Mutation requires the ledger writer lock."""

    def __init__(self, path: Path, *, lock_timeout_seconds: float = 2.0):
        self.path = path
        self.lock_path = path.with_name(path.name + ".lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    @contextmanager
    def writer(self) -> Iterator[None]:
        with exclusive_writer_lock(self.lock_path, timeout_seconds=self.lock_timeout_seconds):
            yield

    def verify(self) -> tuple[list[dict[str, Any]], str]:
        if not self.path.exists():
            return [], GENESIS_SHA256
        if self.path.is_symlink() or not self.path.is_file():
            raise LedgerError("ledger is missing or symlinked")
        try:
            rows = read_jsonl(self.path)
        except (OSError, StrictJSONError) as exc:
            raise LedgerError("ledger bytes are invalid") from exc
        previous = GENESIS_SHA256
        verified: list[dict[str, Any]] = []
        expected_keys = {
            "schema_id",
            "schema_version",
            "sequence_number",
            "event_type",
            "issued_at",
            "actor",
            "previous_event_sha256",
            "authority_refs",
            "payload",
            "event_sha256",
        }
        for sequence, row in enumerate(rows):
            if set(row) != expected_keys or row.get("schema_id") != EVENT_SCHEMA_ID or row.get("schema_version") != EVENT_SCHEMA_VERSION:
                raise LedgerError("unsupported ledger event shape")
            if row.get("sequence_number") != sequence or row.get("previous_event_sha256") != previous:
                raise LedgerError("ledger sequence/hash predecessor mismatch")
            if not isinstance(row.get("event_type"), str) or not row["event_type"] or not isinstance(row.get("issued_at"), str) or not row["issued_at"] or not isinstance(row.get("actor"), str) or not row["actor"]:
                raise LedgerError("ledger event identity is invalid")
            _validate_hash_mapping(row.get("authority_refs"), "authority_refs")
            if not isinstance(row.get("payload"), Mapping):
                raise LedgerError("ledger payload must be an object")
            actual = _event_hash(row)
            if row.get("event_sha256") != actual:
                raise LedgerError("ledger event self hash mismatch")
            verified.append(dict(row))
            previous = actual
        return verified, previous

    def append_locked(
        self,
        *,
        event_type: str,
        issued_at: str,
        actor: str,
        authority_refs: Mapping[str, str],
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Append while the caller owns ``writer()`` across projection publish."""
        event = self.prepare_locked(
            event_type=event_type,
            issued_at=issued_at,
            actor=actor,
            authority_refs=authority_refs,
            payload=payload,
        )
        return self.append_prepared_locked(event)

    def prepare_locked(
        self,
        *,
        event_type: str,
        issued_at: str,
        actor: str,
        authority_refs: Mapping[str, str],
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Build the next event without mutating the ledger."""
        rows, previous = self.verify()
        event: dict[str, Any] = {
            "schema_id": EVENT_SCHEMA_ID,
            "schema_version": EVENT_SCHEMA_VERSION,
            "sequence_number": len(rows),
            "event_type": event_type,
            "issued_at": issued_at,
            "actor": actor,
            "previous_event_sha256": previous,
            "authority_refs": _validate_hash_mapping(authority_refs, "authority_refs"),
            "payload": dict(payload),
            "event_sha256": "",
        }
        event["event_sha256"] = _event_hash(event)
        return event

    def append_prepared_locked(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Append a prevalidated event only if the ledger head is unchanged."""
        rows, previous = self.verify()
        if event.get("sequence_number") != len(rows) or event.get("previous_event_sha256") != previous or event.get("event_sha256") != _event_hash(event):
            raise LedgerError("prepared event no longer matches the ledger head")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise LedgerError("ledger append target is symlinked")
        with self.path.open("ab") as handle:
            handle.write(canonical_bytes(dict(event)) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_parent(self.path)
        return dict(event)
