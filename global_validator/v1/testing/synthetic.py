from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from terminology_contracts.bindings import seal_frozen_candidate_contract
from terminology_contracts.integrity import seal_self_hash

from ..input import assemble_global_input
from ..jsonio import load_json_object


def load_base_input(path: Path) -> dict[str, Any]:
    return load_json_object(path)


def make_candidate_input(
    base: dict[str, Any],
    *,
    sense_index: int,
    candidate_index: int,
    schema_dir: Path,
    gate_policy_path: Path,
    feature_registry_path: Path,
) -> dict[str, Any]:
    source_term = f"term-{sense_index}"
    sense_id = f"sense-{sense_index}"
    candidate_id = f"candidate-{sense_index}-{candidate_index}"
    candidate_vi = f"thuat-ngu-{sense_index}-{candidate_index}"

    effective = copy.deepcopy(base["effective_sense_contract"])
    effective.update(
        {
            "source_term": source_term,
            "sense_id": sense_id,
            "scope_note": f"Synthetic zero-API fixture sense {sense_index}.",
        }
    )
    effective = seal_self_hash(effective)

    frozen = copy.deepcopy(base["frozen_candidate_contract"])
    key = copy.deepcopy(frozen["candidate_key"])
    key.update(
        {
            "candidate_id": candidate_id,
            "candidate_vi": candidate_vi,
            "source_term": source_term,
            "sense_id": sense_id,
            "effective_sense_contract_sha256": effective["integrity"][
                "self_sha256"
            ],
        }
    )
    frozen["candidate_key"] = key
    frozen["scope_note"] = effective["scope_note"]
    frozen["surfaces"]["canonical_vi"] = candidate_vi
    frozen = seal_frozen_candidate_contract(frozen)

    packages: dict[str, dict[str, Any]] = {}
    for field in (
        "constraint_evidence",
        "context_evidence",
        "attestation_evidence",
    ):
        package = copy.deepcopy(base[field])
        package["candidate_key"] = copy.deepcopy(frozen["candidate_key"])
        package["input_contract_sha256"] = frozen["input_contract_sha256"]
        if field == "constraint_evidence":
            package["sense_review"]["effective_sense_contract_sha256"] = (
                effective["integrity"]["self_sha256"]
            )
            package["polysemy_resolution"]["related_sense_ids"] = [sense_id]
        packages[field] = seal_self_hash(package)

    return assemble_global_input(
        effective_sense_contract=effective,
        frozen_candidate_contract=frozen,
        constraint_evidence=packages["constraint_evidence"],
        context_evidence=packages["context_evidence"],
        attestation_evidence=packages["attestation_evidence"],
        assembled_at="2026-07-29T00:00:00+00:00",
        schema_dir=schema_dir,
        gate_policy_path=gate_policy_path,
        feature_registry_path=feature_registry_path,
    )
