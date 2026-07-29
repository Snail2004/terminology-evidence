"""The complete candidate identity used by every cross-producer join."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import JoinError


IDENTITY_FIELDS = (
    "candidate_id",
    "candidate_version",
    "source_term",
    "candidate_vi",
    "sense_id",
    "scope_id",
    "sense_inventory_version",
    "dataset_manifest_sha256",
    "effective_sense_contract_sha256",
    "input_contract_sha256",
)


@dataclass(frozen=True, order=True)
class CandidateIdentity:
    candidate_id: str
    candidate_version: str
    source_term: str
    candidate_vi: str
    sense_id: str
    scope_id: str
    sense_inventory_version: str
    dataset_manifest_sha256: str
    effective_sense_contract_sha256: str
    input_contract_sha256: str

    @classmethod
    def from_package(cls, value: Mapping[str, Any]) -> "CandidateIdentity":
        key = value.get("candidate_key")
        if not isinstance(key, Mapping):
            raise JoinError("package is missing candidate_key")
        missing = [field for field in IDENTITY_FIELDS if field not in key and field != "input_contract_sha256"]
        if missing:
            raise JoinError(f"candidate_key missing fields: {', '.join(missing)}")
        input_hash = value.get("input_contract_sha256")
        if not isinstance(input_hash, str):
            raise JoinError("package is missing envelope input_contract_sha256")
        values: dict[str, Any] = {field: key.get(field) for field in IDENTITY_FIELDS if field != "input_contract_sha256"}
        values["input_contract_sha256"] = input_hash
        if any(not isinstance(values[field], str) or not values[field] for field in IDENTITY_FIELDS):
            raise JoinError("candidate identity fields must be non-empty strings")
        return cls(**values)

    def as_dict(self) -> dict[str, str]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_version": self.candidate_version,
            "source_term": self.source_term,
            "candidate_vi": self.candidate_vi,
            "sense_id": self.sense_id,
            "scope_id": self.scope_id,
            "sense_inventory_version": self.sense_inventory_version,
            "dataset_manifest_sha256": self.dataset_manifest_sha256,
            "effective_sense_contract_sha256": self.effective_sense_contract_sha256,
            "input_contract_sha256": self.input_contract_sha256,
        }

    @property
    def key(self) -> str:
        return "|".join(self.as_dict()[field] for field in IDENTITY_FIELDS)
