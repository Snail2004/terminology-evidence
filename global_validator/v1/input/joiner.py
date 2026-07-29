from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from terminology_contracts.registries import CANDIDATE_JOIN_FIELDS

from ..errors import JoinValidationError


def verify_exact_join(payloads: Mapping[str, Mapping[str, Any]]) -> None:
    if not payloads:
        raise JoinValidationError("at least one contract payload is required")
    first_name, first = next(iter(payloads.items()))
    candidate = first.get("candidate_key")
    input_hash = first.get("input_contract_sha256")
    if not isinstance(candidate, Mapping) or not isinstance(input_hash, str):
        raise JoinValidationError(f"{first_name}: candidate binding is missing")
    expected_key = {field: candidate.get(field) for field in CANDIDATE_JOIN_FIELDS}
    for name, payload in payloads.items():
        key = payload.get("candidate_key")
        if not isinstance(key, Mapping):
            raise JoinValidationError(f"{name}: candidate_key is missing")
        actual_key = {field: key.get(field) for field in CANDIDATE_JOIN_FIELDS}
        if actual_key != expected_key:
            raise JoinValidationError(f"{name}: candidate_key mismatch")
        if payload.get("input_contract_sha256") != input_hash:
            raise JoinValidationError(f"{name}: input_contract_sha256 mismatch")
