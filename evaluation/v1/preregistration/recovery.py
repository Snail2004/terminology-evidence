"""Explicit projection recovery from a valid AR-2 event ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..jsonio import canonical_bytes, read_json, sha256_bytes, sha256_file, sha256_value
from .freeze import EVENT_RECOVERY, DurablePreregistrationStore, FreezeError, derive_projection, now_utc, verify_projection_object
from .ledger import atomic_create


RECOVERY_SCHEMA_ID = "EvaluationProjectionRecoveryReceiptV1"
RECOVERY_SCHEMA_VERSION = "1.0.0"


class RecoveryError(ValueError):
    """Raised when projection recovery is unnecessary or cannot be proven."""


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    integrity = dict(result.get("integrity", {}))
    integrity.pop("self_sha256", None)
    result["integrity"] = integrity
    return result


def verify_recovery_receipt(value: Mapping[str, Any]) -> str:
    expected = {
        "schema_id",
        "schema_version",
        "ledger_head_before_recovery",
        "old_projection_sha256",
        "rebuilt_projection_sha256",
        "reason",
        "operator",
        "issued_at",
        "recovery_tool",
        "recovery_tool_version",
        "integrity",
    }
    if not isinstance(value, Mapping) or set(value) != expected or value.get("schema_id") != RECOVERY_SCHEMA_ID or value.get("schema_version") != RECOVERY_SCHEMA_VERSION:
        raise RecoveryError("unsupported recovery receipt shape")
    for field in ("ledger_head_before_recovery", "old_projection_sha256", "rebuilt_projection_sha256"):
        digest = value.get(field)
        if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise RecoveryError(f"recovery {field} is invalid")
    for field in ("reason", "operator", "issued_at", "recovery_tool", "recovery_tool_version"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise RecoveryError(f"recovery {field} is required")
    integrity = value.get("integrity")
    declared = integrity.get("self_sha256") if isinstance(integrity, Mapping) and set(integrity) == {"self_sha256"} else None
    actual = sha256_value(_without_self_hash(value))
    if declared != actual:
        raise RecoveryError("recovery receipt self hash mismatch")
    return actual


def recover_projection(
    store: DurablePreregistrationStore,
    receipt_path: Path,
    *,
    reason: str,
    operator: str,
    recovery_tool: str,
    recovery_tool_version: str,
    issued_at: str | None = None,
) -> dict[str, Any]:
    """Rebuild only the projection, append RECOVERY_RECORDED, and preserve history."""
    if receipt_path.exists() or receipt_path.is_symlink():
        raise RecoveryError("recovery receipt path already exists")
    with store.ledger.writer():
        events, head = store.ledger.verify()
        correct = derive_projection(events)
        old_hash = "0" * 64
        current_matches = False
        if store.projection_path.exists():
            if store.projection_path.is_symlink() or not store.projection_path.is_file():
                raise RecoveryError("projection path is linked or not a file")
            old_hash = sha256_file(store.projection_path)
            try:
                current = read_json(store.projection_path)
                verify_projection_object(current)
                current_matches = current == correct
            except (OSError, ValueError, FreezeError):
                current_matches = False
        if current_matches:
            raise RecoveryError("projection already matches the authoritative ledger")
        rebuilt_bytes = canonical_bytes(correct) + b"\n"
        rebuilt_hash = sha256_bytes(rebuilt_bytes)
        receipt: dict[str, Any] = {
            "schema_id": RECOVERY_SCHEMA_ID,
            "schema_version": RECOVERY_SCHEMA_VERSION,
            "ledger_head_before_recovery": head,
            "old_projection_sha256": old_hash,
            "rebuilt_projection_sha256": rebuilt_hash,
            "reason": reason,
            "operator": operator,
            "issued_at": issued_at or now_utc(),
            "recovery_tool": recovery_tool,
            "recovery_tool_version": recovery_tool_version,
            "integrity": {"self_sha256": ""},
        }
        receipt["integrity"]["self_sha256"] = sha256_value(_without_self_hash(receipt))
        verify_recovery_receipt(receipt)
        receipt_bytes = canonical_bytes(receipt) + b"\n"
        atomic_create(receipt_path, receipt_bytes)
        receipt_physical = sha256_bytes(receipt_bytes)
        refs = {
            "preregistration_receipt_sha256": correct["preregistration_receipt_sha256"],
            "split_manifest_sha256": correct["split_manifest_sha256"],
            "authority_profile_sha256": correct["authority_profile_sha256"],
        }
        candidate = store.ledger.prepare_locked(
            event_type=EVENT_RECOVERY,
            issued_at=receipt["issued_at"],
            actor=operator,
            authority_refs=refs,
            payload={
                "recovery_receipt_self_sha256": receipt["integrity"]["self_sha256"],
                "recovery_receipt_physical_sha256": receipt_physical,
                "ledger_head_before_recovery": head,
                "old_projection_sha256": old_hash,
                "rebuilt_projection_sha256": rebuilt_hash,
            },
        )
        updated_projection = derive_projection(events + [candidate])
        store.ledger.append_prepared_locked(candidate)
        store._publish_projection(updated_projection)
        return {"receipt": receipt, "projection": updated_projection}
