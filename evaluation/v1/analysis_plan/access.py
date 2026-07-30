"""Hash-chained, stage-ordered verification for future gold-access receipts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..jsonio import sha256_value
from ..time_policy import TimestampError, parse_rfc3339
from .specification import STAGE_ORDER


GOLD_ACCESS_SCHEMA_ID = "EvaluationGoldAccessEventV1"
GOLD_ACCESS_SCHEMA_VERSION = "1.0.0"
GENESIS_SHA256 = "0" * 64


class GoldAccessError(ValueError):
    """Raised when a gold-access event is unbound, out of order or tampered."""


def _require_sha256(value: Any, field: str, *, allow_zero: bool = False) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        or (not allow_zero and set(value) == {"0"})
    ):
        raise GoldAccessError(f"{field} must be a lowercase SHA256")
    return value


def _event_hash(value: Mapping[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("event_sha256", None)
    return sha256_value(unsigned)


def verify_gold_access_ledger(
    events: Sequence[Mapping[str, Any]],
    *,
    analysis_plan_freeze_receipt_sha256: str,
) -> str:
    """Verify exact D0 -> D1 -> V1 -> T1 ordering without opening gold bytes."""
    _require_sha256(
        analysis_plan_freeze_receipt_sha256,
        "analysis_plan_freeze_receipt_sha256",
    )
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        raise GoldAccessError("gold access ledger must be a sequence")
    previous = GENESIS_SHA256
    previous_time = None
    expected_keys = {
        "schema_id",
        "schema_version",
        "sequence_number",
        "stage",
        "issued_at",
        "actor",
        "purpose",
        "previous_event_sha256",
        "analysis_plan_freeze_receipt_sha256",
        "dataset_split_manifest_sha256",
        "producer_bundle_manifest_sha256",
        "gold_bundle_manifest_sha256",
        "authorized_scope_sha256",
        "authorization",
        "event_sha256",
    }
    for sequence_number, event in enumerate(events):
        if not isinstance(event, Mapping) or set(event) != expected_keys:
            raise GoldAccessError("gold access event shape is invalid")
        if (
            event.get("schema_id") != GOLD_ACCESS_SCHEMA_ID
            or event.get("schema_version") != GOLD_ACCESS_SCHEMA_VERSION
            or event.get("sequence_number") != sequence_number
        ):
            raise GoldAccessError("gold access event identity is invalid")
        if sequence_number >= len(STAGE_ORDER) or event.get("stage") != STAGE_ORDER[sequence_number]:
            raise GoldAccessError("gold access stage order is invalid")
        if event.get("previous_event_sha256") != previous:
            raise GoldAccessError("gold access predecessor hash is invalid")
        if event.get("analysis_plan_freeze_receipt_sha256") != analysis_plan_freeze_receipt_sha256:
            raise GoldAccessError("gold access event uses a different analysis-plan freeze")
        for field in (
            "dataset_split_manifest_sha256",
            "producer_bundle_manifest_sha256",
            "gold_bundle_manifest_sha256",
            "authorized_scope_sha256",
        ):
            _require_sha256(event.get(field), field)
        if not isinstance(event.get("actor"), str) or not event["actor"].strip():
            raise GoldAccessError("gold access actor is required")
        if not isinstance(event.get("purpose"), str) or not event["purpose"].strip():
            raise GoldAccessError("gold access purpose is required")
        authorization = event.get("authorization")
        if not isinstance(authorization, Mapping) or set(authorization) != {
            "approved",
            "approved_by",
            "approved_at",
            "approval_receipt_sha256",
        }:
            raise GoldAccessError("gold access authorization shape is invalid")
        if authorization.get("approved") is not True:
            raise GoldAccessError("gold access is not approved")
        if not isinstance(authorization.get("approved_by"), str) or not authorization["approved_by"].strip():
            raise GoldAccessError("gold access approver is required")
        _require_sha256(authorization.get("approval_receipt_sha256"), "approval_receipt_sha256")
        try:
            issued_at = parse_rfc3339(event.get("issued_at"), "gold_access.issued_at")
            approved_at = parse_rfc3339(authorization.get("approved_at"), "gold_access.approved_at")
        except TimestampError as exc:
            raise GoldAccessError(str(exc)) from exc
        if approved_at > issued_at:
            raise GoldAccessError("gold access was issued before approval")
        if previous_time is not None and issued_at < previous_time:
            raise GoldAccessError("gold access event time moved backwards")
        actual = _event_hash(event)
        if event.get("event_sha256") != actual:
            raise GoldAccessError("gold access event self hash mismatch")
        previous = actual
        previous_time = issued_at
    return previous


def seal_gold_access_event(value: Mapping[str, Any]) -> dict[str, Any]:
    """Test/operator helper: seal a complete event, never open or read gold."""
    event = dict(value)
    event["event_sha256"] = ""
    event["event_sha256"] = _event_hash(event)
    return event
