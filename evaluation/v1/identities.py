"""Candidate and grouping identity helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class IdentityError(ValueError):
    """Raised when a row cannot provide an exact analysis identity."""


@dataclass(frozen=True, order=True)
class CandidateKey:
    source_term: str
    sense_id: str
    scope_id: str
    candidate_vi: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source_term": self.source_term,
            "sense_id": self.sense_id,
            "scope_id": self.scope_id,
            "candidate_vi": self.candidate_vi,
        }

    def as_string(self) -> str:
        return "|".join((self.source_term, self.sense_id, self.scope_id, self.candidate_vi))


def candidate_key_from(value: Mapping[str, Any] | CandidateKey) -> CandidateKey:
    if isinstance(value, CandidateKey):
        return value
    required = ("source_term", "sense_id", "scope_id", "candidate_vi")
    missing = [name for name in required if not isinstance(value.get(name), str) or not value[name]]
    if missing:
        raise IdentityError(f"candidate key missing fields: {', '.join(missing)}")
    return CandidateKey(*(value[name] for name in required))


def row_candidate_key(row: Mapping[str, Any]) -> CandidateKey:
    nested = row.get("candidate_key")
    if isinstance(nested, Mapping):
        return candidate_key_from(nested)
    if isinstance(nested, str) and nested:
        parts = nested.split("|", 3)
        if len(parts) == 4 and all(parts):
            return CandidateKey(*parts)
    if all(name in row for name in ("source_term", "sense_id", "scope_id", "candidate_vi")):
        return candidate_key_from(row)  # type: ignore[arg-type]
    raise IdentityError("row has no candidate_key")


def row_sense_id(row: Mapping[str, Any]) -> str:
    key = row_candidate_key(row)
    return key.sense_id


def source_block_ids(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = row.get("source_block_ids", row.get("source_blocks", ()))
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(sorted({str(value) for value in values if str(value)}))


def evidence_source_ids(row: Mapping[str, Any]) -> tuple[str, ...]:
    values = row.get("evidence_source_ids", row.get("evidence_sources", ()))
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(sorted({str(value) for value in values if str(value)}))
