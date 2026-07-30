"""Preregistered exclusion handling."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..constants import ALLOWED_EXCLUSION_REASONS
from ..identities import row_candidate_key


class EligibilityError(ValueError):
    """Raised when an exclusion violates the preregistered policy."""


def apply_exclusions(
    rows: Iterable[Mapping[str, Any]],
    exclusions: Iterable[Mapping[str, Any]] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    row_list = [dict(row) for row in rows]
    by_key = {row_candidate_key(row): row for row in row_list}
    excluded: list[dict[str, Any]] = []
    seen = set()
    for item in exclusions:
        key = row_candidate_key(item)
        reason = item.get("reason")
        required = ("artifact_ref", "timestamp", "reviewer_approval")
        if reason not in ALLOWED_EXCLUSION_REASONS:
            raise EligibilityError(f"forbidden exclusion reason: {reason}")
        if any(not item.get(field) for field in required):
            raise EligibilityError(f"incomplete exclusion for {key.as_string()}")
        if key not in by_key:
            raise EligibilityError(f"exclusion references unknown candidate: {key.as_string()}")
        if key in seen:
            raise EligibilityError(f"duplicate exclusion: {key.as_string()}")
        seen.add(key)
        record = dict(item)
        record["candidate_key"] = key.as_dict()
        excluded.append(record)
    eligible = [row for row in row_list if row_candidate_key(row) not in seen]
    return eligible, excluded
