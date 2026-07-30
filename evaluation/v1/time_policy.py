"""Strict timezone-aware RFC3339 policy shared by receipts and ledgers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


_RFC3339 = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}:\d{2})(?P<fraction>\.\d{1,6})?(?P<zone>Z|[+-]\d{2}:\d{2})$"
)


class TimestampError(ValueError):
    """Raised when persisted event time is ambiguous or moves backwards."""


def parse_rfc3339(value: Any, field: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not _RFC3339.fullmatch(value):
        raise TimestampError(f"{field} must be an exact timezone-aware RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TimestampError(f"{field} is not a valid calendar timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TimestampError(f"{field} has no timezone")
    return parsed.astimezone(timezone.utc)
