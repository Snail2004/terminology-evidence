"""Non-circular plan/event/completion recovery for the state projection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..jsonio import canonical_bytes, read_json, sha256_bytes, sha256_file, sha256_value
from ..time_policy import TimestampError, parse_rfc3339
from .freeze import EVENT_RECOVERY, DurablePreregistrationStore, FreezeError, derive_projection, now_utc, verify_projection_object
from .ledger import atomic_create


PLAN_SCHEMA_ID = "EvaluationProjectionRecoveryPlanV1"
COMPLETION_SCHEMA_ID = "EvaluationProjectionRecoveryCompletionV1"
RECOVERY_SCHEMA_VERSION = "1.0.0"


class RecoveryError(ValueError):
    """Raised when projection recovery is unnecessary or cannot be proven."""


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    integrity = dict(result.get("integrity", {}))
    integrity.pop("self_sha256", None)
    result["integrity"] = integrity
    return result


def _require_hash(value: Any, field: str, *, allow_zero: bool = False) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        or (not allow_zero and set(value) == {"0"})
    ):
        raise RecoveryError(f"recovery {field} is invalid")
    return value


def _verify_self(value: Mapping[str, Any]) -> str:
    integrity = value.get("integrity")
    declared = integrity.get("self_sha256") if isinstance(integrity, Mapping) and set(integrity) == {"self_sha256"} else None
    actual = sha256_value(_without_self_hash(value))
    if declared != actual:
        raise RecoveryError("recovery receipt self hash mismatch")
    return actual


def verify_recovery_plan(value: Mapping[str, Any]) -> str:
    expected = {
        "schema_id",
        "schema_version",
        "ledger_head_before_recovery",
        "old_projection_sha256",
        "pre_event_projection_sha256",
        "reason",
        "operator",
        "issued_at",
        "recovery_tool",
        "recovery_tool_version",
        "integrity",
    }
    if not isinstance(value, Mapping) or set(value) != expected or value.get("schema_id") != PLAN_SCHEMA_ID or value.get("schema_version") != RECOVERY_SCHEMA_VERSION:
        raise RecoveryError("unsupported recovery plan shape")
    _require_hash(value.get("ledger_head_before_recovery"), "ledger_head_before_recovery")
    _require_hash(value.get("old_projection_sha256"), "old_projection_sha256", allow_zero=True)
    _require_hash(value.get("pre_event_projection_sha256"), "pre_event_projection_sha256")
    for field in ("reason", "operator", "recovery_tool", "recovery_tool_version"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise RecoveryError(f"recovery {field} is required")
    try:
        parse_rfc3339(value.get("issued_at"), "recovery_plan.issued_at")
    except TimestampError as exc:
        raise RecoveryError(str(exc)) from exc
    return _verify_self(value)


def verify_recovery_receipt(value: Mapping[str, Any]) -> str:
    """Verify completion evidence that binds the final published projection."""
    expected = {
        "schema_id",
        "schema_version",
        "status",
        "plan_self_sha256",
        "plan_physical_sha256",
        "recovery_event_sha256",
        "final_ledger_head_sha256",
        "final_projection_self_sha256",
        "final_projection_physical_sha256",
        "issued_at",
        "integrity",
    }
    if not isinstance(value, Mapping) or set(value) != expected or value.get("schema_id") != COMPLETION_SCHEMA_ID or value.get("schema_version") != RECOVERY_SCHEMA_VERSION or value.get("status") != "PUBLISHED":
        raise RecoveryError("unsupported recovery completion shape")
    for field in (
        "plan_self_sha256",
        "plan_physical_sha256",
        "recovery_event_sha256",
        "final_ledger_head_sha256",
        "final_projection_self_sha256",
        "final_projection_physical_sha256",
    ):
        _require_hash(value.get(field), field)
    if value["recovery_event_sha256"] != value["final_ledger_head_sha256"]:
        raise RecoveryError("recovery completion ledger/event binding mismatch")
    try:
        parse_rfc3339(value.get("issued_at"), "recovery_completion.issued_at")
    except TimestampError as exc:
        raise RecoveryError(str(exc)) from exc
    return _verify_self(value)


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
    """Plan recovery, append its event, publish, then seal completion evidence."""
    completion_path = receipt_path.with_name(receipt_path.stem + ".completion.json")
    if receipt_path.exists() or receipt_path.is_symlink() or completion_path.exists() or completion_path.is_symlink():
        raise RecoveryError("recovery evidence path already exists")
    event_time = issued_at or now_utc()
    try:
        parse_rfc3339(event_time, "recovery.issued_at")
    except TimestampError as exc:
        raise RecoveryError(str(exc)) from exc
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

        pre_event_bytes = canonical_bytes(correct) + b"\n"
        pre_event_hash = sha256_bytes(pre_event_bytes)
        plan: dict[str, Any] = {
            "schema_id": PLAN_SCHEMA_ID,
            "schema_version": RECOVERY_SCHEMA_VERSION,
            "ledger_head_before_recovery": head,
            "old_projection_sha256": old_hash,
            "pre_event_projection_sha256": pre_event_hash,
            "reason": reason,
            "operator": operator,
            "issued_at": event_time,
            "recovery_tool": recovery_tool,
            "recovery_tool_version": recovery_tool_version,
            "integrity": {"self_sha256": ""},
        }
        plan["integrity"]["self_sha256"] = sha256_value(_without_self_hash(plan))
        verify_recovery_plan(plan)
        plan_bytes = canonical_bytes(plan) + b"\n"
        atomic_create(receipt_path, plan_bytes)
        plan_physical = sha256_bytes(plan_bytes)

        refs = {
            "preregistration_receipt_sha256": correct["preregistration_receipt_sha256"],
            "preregistration_receipt_physical_sha256": correct["preregistration_receipt_physical_sha256"],
            "receipt_verification_report_sha256": correct["receipt_verification_report_sha256"],
            "split_manifest_sha256": correct["split_manifest_sha256"],
            "authority_profile_sha256": correct["authority_profile_sha256"],
        }
        candidate = store.ledger.prepare_locked(
            event_type=EVENT_RECOVERY,
            issued_at=event_time,
            actor=operator,
            authority_refs=refs,
            payload={
                "recovery_plan_self_sha256": plan["integrity"]["self_sha256"],
                "recovery_plan_physical_sha256": plan_physical,
                "ledger_head_before_recovery": head,
                "old_projection_sha256": old_hash,
                "pre_event_projection_sha256": pre_event_hash,
            },
        )
        updated_projection = derive_projection(events + [candidate])
        store.ledger.append_prepared_locked(candidate)
        store._publish_projection(updated_projection)

        final_physical = sha256_file(store.projection_path)
        completion: dict[str, Any] = {
            "schema_id": COMPLETION_SCHEMA_ID,
            "schema_version": RECOVERY_SCHEMA_VERSION,
            "status": "PUBLISHED",
            "plan_self_sha256": plan["integrity"]["self_sha256"],
            "plan_physical_sha256": plan_physical,
            "recovery_event_sha256": candidate["event_sha256"],
            "final_ledger_head_sha256": updated_projection["ledger_head_sha256"],
            "final_projection_self_sha256": updated_projection["integrity"]["self_sha256"],
            "final_projection_physical_sha256": final_physical,
            "issued_at": event_time,
            "integrity": {"self_sha256": ""},
        }
        completion["integrity"]["self_sha256"] = sha256_value(_without_self_hash(completion))
        verify_recovery_receipt(completion)
        atomic_create(completion_path, canonical_bytes(completion) + b"\n")
        return {
            "plan_receipt": plan,
            "completion_receipt": completion,
            "completion_path": completion_path,
            "projection": updated_projection,
        }
