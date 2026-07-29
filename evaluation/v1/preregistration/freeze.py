"""Ledger-authoritative AR-2 freeze and one-time access state machine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..constants import MODE_REAL_AUTHORITY, STATUS_FROZEN
from ..jsonio import canonical_bytes, read_json, sha256_value
from .ledger import EventLedger, LedgerError, atomic_publish
from .receipt import verify_receipt_object


PROJECTION_SCHEMA_ID = "EvaluationPreregistrationStateProjectionV1"
PROJECTION_SCHEMA_VERSION = "1.0.0"
EVENT_FROZEN = "PREREGISTRATION_FROZEN"
EVENT_VALIDATION = "VALIDATION_ACCESS_OPENED"
EVENT_CALIBRATION = "CALIBRATION_ARTIFACT_FROZEN"
EVENT_HIDDEN_TEST = "HIDDEN_TEST_ACCESS_OPENED"
EVENT_AMENDMENT = "AMENDMENT_ACCEPTED"
EVENT_EXPLORATORY = "EXPLORATORY_POST_TEST_DECLARED"
EVENT_RECOVERY = "RECOVERY_RECORDED"
STATE_VALIDATION = "VALIDATION_ACCESSED"
STATE_CALIBRATION = "CALIBRATION_ARTIFACT_FROZEN"
STATE_HIDDEN_TEST = "HIDDEN_TEST_ACCESSED"
STATE_REFREEZE_REQUIRED = "REFREEZE_REQUIRED"


class FreezeError(ValueError):
    """Raised when ledger history and its projection cannot authorize access."""


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    integrity = dict(result.get("integrity", {}))
    integrity.pop("self_sha256", None)
    result["integrity"] = integrity
    return result


def _projection_hash(value: Mapping[str, Any]) -> str:
    return sha256_value(_without_self_hash(value))


def _require_payload_keys(payload: Any, keys: set[str], event_type: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping) or set(payload) != keys:
        raise FreezeError(f"{event_type} payload shape is invalid")
    return payload


def derive_projection(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay all events and return the only valid projection."""
    if not events or events[0].get("event_type") != EVENT_FROZEN:
        raise FreezeError("ledger has no preregistration freeze genesis")
    first = events[0]
    if first.get("sequence_number") != 0:
        raise FreezeError("freeze genesis is not sequence zero")
    refs = first.get("authority_refs")
    required_refs = {"preregistration_receipt_sha256", "split_manifest_sha256", "authority_profile_sha256"}
    if not isinstance(refs, Mapping) or set(refs) != required_refs:
        raise FreezeError("freeze authority refs are incomplete")
    payload = _require_payload_keys(
        first.get("payload"),
        {"receipt_mode", "receipt_sha256", "split_manifest_sha256", "authority_profile_sha256"},
        EVENT_FROZEN,
    )
    if payload["receipt_mode"] != MODE_REAL_AUTHORITY or payload["receipt_sha256"] != refs["preregistration_receipt_sha256"] or payload["split_manifest_sha256"] != refs["split_manifest_sha256"] or payload["authority_profile_sha256"] != refs["authority_profile_sha256"]:
        raise FreezeError("freeze payload does not match authority refs")

    status = STATUS_FROZEN
    validation_opened_at: str | None = None
    calibration_artifact_sha256: str | None = None
    hidden_test_opened_at: str | None = None
    amendment_count = 0
    exploratory_count = 0
    recovery_count = 0
    for event in events[1:]:
        if event.get("authority_refs") != refs:
            raise FreezeError("event authority refs drifted")
        event_type = event.get("event_type")
        payload = event.get("payload")
        if event_type == EVENT_VALIDATION:
            checked = _require_payload_keys(payload, {"purpose", "previous_ledger_head"}, EVENT_VALIDATION)
            if status != STATUS_FROZEN or validation_opened_at is not None or checked["previous_ledger_head"] != event["previous_event_sha256"]:
                raise FreezeError("validation access transition is invalid or repeated")
            status = STATE_VALIDATION
            validation_opened_at = event["issued_at"]
        elif event_type == EVENT_CALIBRATION:
            checked = _require_payload_keys(payload, {"calibration_artifact_sha256", "previous_ledger_head"}, EVENT_CALIBRATION)
            if status != STATE_VALIDATION or checked["previous_ledger_head"] != event["previous_event_sha256"]:
                raise FreezeError("calibration freeze transition is invalid")
            calibration_artifact_sha256 = checked["calibration_artifact_sha256"]
            status = STATE_CALIBRATION
        elif event_type == EVENT_HIDDEN_TEST:
            checked = _require_payload_keys(payload, {"purpose", "previous_ledger_head"}, EVENT_HIDDEN_TEST)
            if status != STATE_CALIBRATION or hidden_test_opened_at is not None or checked["previous_ledger_head"] != event["previous_event_sha256"]:
                raise FreezeError("hidden-test access transition is invalid or repeated")
            hidden_test_opened_at = event["issued_at"]
            status = STATE_HIDDEN_TEST
        elif event_type == EVENT_AMENDMENT:
            checked = _require_payload_keys(payload, {"amendment", "phase", "new_freeze_required", "previous_ledger_head"}, EVENT_AMENDMENT)
            expected_phase = "PRE_VALIDATION" if status == STATUS_FROZEN else "POST_VALIDATION_PRE_TEST"
            if status not in {STATUS_FROZEN, STATE_VALIDATION, STATE_CALIBRATION} or checked["phase"] != expected_phase or checked["new_freeze_required"] is not True or checked["previous_ledger_head"] != event["previous_event_sha256"]:
                raise FreezeError("primary amendment transition is invalid")
            amendment_count += 1
            status = STATE_REFREEZE_REQUIRED
        elif event_type == EVENT_EXPLORATORY:
            checked = _require_payload_keys(payload, {"amendment", "analysis_namespace", "previous_ledger_head"}, EVENT_EXPLORATORY)
            if status != STATE_HIDDEN_TEST or checked["previous_ledger_head"] != event["previous_event_sha256"]:
                raise FreezeError("post-test exploratory declaration is invalid")
            exploratory_count += 1
        elif event_type == EVENT_RECOVERY:
            checked = _require_payload_keys(payload, {"recovery_receipt_self_sha256", "recovery_receipt_physical_sha256", "ledger_head_before_recovery", "old_projection_sha256", "rebuilt_projection_sha256"}, EVENT_RECOVERY)
            if checked["ledger_head_before_recovery"] != event["previous_event_sha256"]:
                raise FreezeError("recovery event does not bind its previous ledger head")
            recovery_count += 1
        else:
            raise FreezeError(f"unknown preregistration event: {event_type}")

    projection: dict[str, Any] = {
        "schema_id": PROJECTION_SCHEMA_ID,
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "status": status,
        "event_count": len(events),
        "ledger_head_sha256": events[-1]["event_sha256"],
        "preregistration_receipt_sha256": refs["preregistration_receipt_sha256"],
        "split_manifest_sha256": refs["split_manifest_sha256"],
        "authority_profile_sha256": refs["authority_profile_sha256"],
        "validation_opened_at": validation_opened_at,
        "calibration_artifact_sha256": calibration_artifact_sha256,
        "hidden_test_opened_at": hidden_test_opened_at,
        "amendment_count": amendment_count,
        "exploratory_count": exploratory_count,
        "recovery_count": recovery_count,
        "integrity": {"self_sha256": ""},
    }
    projection["integrity"]["self_sha256"] = _projection_hash(projection)
    return projection


def verify_projection_object(value: Mapping[str, Any]) -> str:
    expected_keys = {
        "schema_id",
        "schema_version",
        "status",
        "event_count",
        "ledger_head_sha256",
        "preregistration_receipt_sha256",
        "split_manifest_sha256",
        "authority_profile_sha256",
        "validation_opened_at",
        "calibration_artifact_sha256",
        "hidden_test_opened_at",
        "amendment_count",
        "exploratory_count",
        "recovery_count",
        "integrity",
    }
    if set(value) != expected_keys or value.get("schema_id") != PROJECTION_SCHEMA_ID or value.get("schema_version") != PROJECTION_SCHEMA_VERSION:
        raise FreezeError("unsupported state projection shape")
    declared = value.get("integrity", {}).get("self_sha256") if isinstance(value.get("integrity"), Mapping) else None
    actual = _projection_hash(value)
    if declared != actual:
        raise FreezeError("state projection self hash mismatch")
    return actual


class DurablePreregistrationStore:
    """Mutate ledger and projection under one lock; the ledger remains authority."""

    def __init__(self, ledger_path: Path, projection_path: Path, *, lock_timeout_seconds: float = 2.0):
        self.ledger = EventLedger(ledger_path, lock_timeout_seconds=lock_timeout_seconds)
        self.projection_path = projection_path

    def freeze(self, receipt: Mapping[str, Any], *, actor: str, issued_at: str | None = None) -> dict[str, Any]:
        verify_receipt_object(receipt)
        if receipt.get("mode") != MODE_REAL_AUTHORITY or receipt.get("status") != STATUS_FROZEN:
            raise FreezeError("only a verified REAL_AUTHORITY receipt may freeze state")
        refs = {
            "preregistration_receipt_sha256": receipt["integrity"]["self_sha256"],
            "split_manifest_sha256": receipt["dataset_manifest_sha256"],
            "authority_profile_sha256": receipt["authority_evidence"]["profile_self_sha256"],
        }
        with self.ledger.writer():
            existing, _ = self.ledger.verify()
            if existing or self.projection_path.exists():
                raise FreezeError("preregistration state already exists")
            candidate = self.ledger.prepare_locked(
                event_type=EVENT_FROZEN,
                issued_at=issued_at or now_utc(),
                actor=actor,
                authority_refs=refs,
                payload={
                    "receipt_mode": MODE_REAL_AUTHORITY,
                    "receipt_sha256": refs["preregistration_receipt_sha256"],
                    "split_manifest_sha256": refs["split_manifest_sha256"],
                    "authority_profile_sha256": refs["authority_profile_sha256"],
                },
            )
            projection = derive_projection([candidate])
            self.ledger.append_prepared_locked(candidate)
            self._publish_projection(projection)
            return projection

    def load(self) -> dict[str, Any]:
        with self.ledger.writer():
            events, _ = self.ledger.verify()
            expected = derive_projection(events)
            actual = self._read_projection()
            if actual != expected:
                raise FreezeError("ledger/projection divergence")
            return actual

    def open_validation(self, *, actor: str, purpose: str, issued_at: str | None = None) -> dict[str, Any]:
        if not isinstance(purpose, str) or not purpose.strip():
            raise FreezeError("validation access purpose is required")
        return self._append_event(EVENT_VALIDATION, actor=actor, issued_at=issued_at, payload={"purpose": purpose})

    def freeze_calibration(self, *, actor: str, calibration_artifact_sha256: str, issued_at: str | None = None) -> dict[str, Any]:
        if len(calibration_artifact_sha256) != 64 or set(calibration_artifact_sha256) == {"0"} or any(character not in "0123456789abcdef" for character in calibration_artifact_sha256):
            raise FreezeError("calibration artifact hash is invalid")
        return self._append_event(EVENT_CALIBRATION, actor=actor, issued_at=issued_at, payload={"calibration_artifact_sha256": calibration_artifact_sha256})

    def open_hidden_test(self, *, actor: str, purpose: str, issued_at: str | None = None) -> dict[str, Any]:
        if not isinstance(purpose, str) or not purpose.strip():
            raise FreezeError("hidden-test access purpose is required")
        return self._append_event(EVENT_HIDDEN_TEST, actor=actor, issued_at=issued_at, payload={"purpose": purpose})

    def _append_event(self, event_type: str, *, actor: str, payload: Mapping[str, Any], issued_at: str | None = None) -> dict[str, Any]:
        with self.ledger.writer():
            events, head = self.ledger.verify()
            expected = derive_projection(events)
            actual = self._read_projection()
            if actual != expected:
                raise FreezeError("ledger/projection divergence")
            refs = {
                "preregistration_receipt_sha256": expected["preregistration_receipt_sha256"],
                "split_manifest_sha256": expected["split_manifest_sha256"],
                "authority_profile_sha256": expected["authority_profile_sha256"],
            }
            event_payload = dict(payload)
            event_payload["previous_ledger_head"] = head
            candidate = self.ledger.prepare_locked(
                event_type=event_type,
                issued_at=issued_at or now_utc(),
                actor=actor,
                authority_refs=refs,
                payload=event_payload,
            )
            projection = derive_projection(events + [candidate])
            self.ledger.append_prepared_locked(candidate)
            self._publish_projection(projection)
            return projection

    def _read_projection(self) -> dict[str, Any]:
        if self.projection_path.is_symlink() or not self.projection_path.is_file():
            raise FreezeError("state projection is missing or symlinked")
        try:
            value = read_json(self.projection_path)
        except (OSError, ValueError) as exc:
            raise FreezeError("state projection is unreadable") from exc
        verify_projection_object(value)
        return value

    def _publish_projection(self, value: Mapping[str, Any]) -> None:
        verify_projection_object(value)
        try:
            atomic_publish(self.projection_path, canonical_bytes(value) + b"\n")
        except LedgerError as exc:
            raise FreezeError(str(exc)) from exc


@dataclass(frozen=True)
class FreezeState:
    """Read-only compatibility projection; it has no mutating methods."""

    status: str
    receipt_sha256: str
    validation_opened_at: str | None
    hidden_test_opened_at: str | None

    @classmethod
    def from_projection(cls, value: Mapping[str, Any]) -> "FreezeState":
        verify_projection_object(value)
        return cls(
            status=value["status"],
            receipt_sha256=value["preregistration_receipt_sha256"],
            validation_opened_at=value["validation_opened_at"],
            hidden_test_opened_at=value["hidden_test_opened_at"],
        )


@dataclass(frozen=True)
class AccessLog:
    """Read-only access-event projection; writes must use the durable store."""

    entries: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_ledger(cls, ledger: EventLedger) -> "AccessLog":
        events, _ = ledger.verify()
        access = tuple(event for event in events if event["event_type"] in {EVENT_VALIDATION, EVENT_HIDDEN_TEST})
        return cls(entries=access)
