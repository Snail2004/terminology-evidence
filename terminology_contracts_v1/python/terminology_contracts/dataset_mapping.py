from __future__ import annotations

from typing import Any, Mapping

from .integrity import require_nonzero_sha256


class DatasetMappingError(ValueError):
    pass


def map_candidate_key(
    *,
    candidate: Mapping[str, Any],
    sense: Mapping[str, Any],
    dataset_version: str,
    dataset_manifest_sha256: str,
    effective_sense_contract_sha256: str,
) -> dict[str, str]:
    """Map normalized records to the contract join key.

    The caller supplies records and immutable bindings.  This function never
    opens dataset files and therefore does not couple runtime contracts to a
    V3 or pilot storage layout.
    """
    candidate_id = _first(candidate, "candidate_id", "candidate_instance_id")
    # A schema revision describes the record format, not this candidate's
    # content. Prefer an explicit revision and otherwise use the immutable
    # candidate instance binding supplied by the dataset.
    candidate_version = _first(
        candidate, "candidate_version", "candidate_instance_sha256"
    )
    candidate_vi = _first(candidate, "candidate_vi", "candidate_target_vi")
    source_term = _first(sense, "source_term")
    sense_id = _first(candidate, "sense_id")
    scope_id = _first(candidate, "scope_id")
    if sense_id != _first(sense, "sense_id"):
        raise DatasetMappingError("candidate and sense records disagree on sense_id")
    if scope_id != _first(sense, "scope_id"):
        raise DatasetMappingError("candidate and sense records disagree on scope_id")
    if not isinstance(dataset_version, str) or not dataset_version:
        raise DatasetMappingError("dataset_version is required")
    try:
        require_nonzero_sha256(
            dataset_manifest_sha256, field="dataset_manifest_sha256"
        )
        require_nonzero_sha256(
            effective_sense_contract_sha256,
            field="effective_sense_contract_sha256",
        )
    except ValueError as exc:
        raise DatasetMappingError(str(exc)) from exc
    return {
        "candidate_id": candidate_id,
        "candidate_version": candidate_version,
        "source_term": source_term,
        "candidate_vi": candidate_vi,
        "sense_id": sense_id,
        "scope_id": scope_id,
        "sense_inventory_version": dataset_version,
        "dataset_manifest_sha256": dataset_manifest_sha256,
        "effective_sense_contract_sha256": effective_sense_contract_sha256,
    }


def _first(value: Mapping[str, Any], *fields: str) -> str:
    for field in fields:
        candidate = value.get(field)
        if isinstance(candidate, str) and candidate:
            return candidate
    raise DatasetMappingError("missing required field: " + " or ".join(fields))
