from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from terminology_contracts.dataset_mapping import DatasetMappingError, map_candidate_key


def _synthetic_records() -> tuple[dict, dict]:
    candidate = {
        "candidate_instance_id": "candidate-001",
        "schema_version": "3.0.0",
        "candidate_target_vi": "suy luan",
        "sense_id": "sense-001",
        "scope_id": "scope-001",
    }
    sense = {
        "sense_id": "sense-001",
        "scope_id": "scope-001",
        "source_term": "inference",
    }
    return candidate, sense


def test_mapping_requires_explicit_hash_bindings() -> None:
    candidate, sense = _synthetic_records()
    mapped = map_candidate_key(
        candidate=candidate,
        sense=sense,
        dataset_version="dataset-v3",
        dataset_manifest_sha256="a" * 64,
        effective_sense_contract_sha256="b" * 64,
    )
    assert mapped["candidate_id"] == "candidate-001"
    assert mapped["sense_id"] == "sense-001"
    assert mapped["scope_id"] == "scope-001"
    assert mapped["sense_inventory_version"] == "dataset-v3"


def test_mapping_rejects_record_identity_drift() -> None:
    candidate, sense = _synthetic_records()
    sense["sense_id"] = "other-sense"
    with pytest.raises(DatasetMappingError, match="sense_id"):
        map_candidate_key(
            candidate=candidate,
            sense=sense,
            dataset_version="dataset-v3",
            dataset_manifest_sha256="a" * 64,
            effective_sense_contract_sha256="b" * 64,
        )


@pytest.mark.parametrize(
    "dataset_name",
    ["d2l_context_support_set_validation_ready_v3", "pilot_dev_only_v1_1"],
)
def test_real_dataset_mapping_smoke(dataset_name: str) -> None:
    root_text = os.environ.get("TERMINOLOGY_DATASET_ROOT")
    if not root_text:
        pytest.skip("TERMINOLOGY_DATASET_ROOT not supplied")
    root = Path(root_text) / dataset_name
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    candidates = [
        json.loads(line)
        for line in (root / "candidate_instances.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    senses = {
        row["sense_id"]: row
        for row in (
            json.loads(line)
            for line in (root / "term_senses.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if line
        )
    }
    candidate = candidates[0]
    sense = senses[candidate["sense_id"]]
    mapped = map_candidate_key(
        candidate=candidate,
        sense=sense,
        dataset_version=manifest.get("dataset_version")
        or manifest.get("schema_version"),
        dataset_manifest_sha256=manifest["manifest_sha256"],
        effective_sense_contract_sha256="e" * 64,
    )
    assert mapped["candidate_id"] == candidate["candidate_instance_id"]
    assert mapped["sense_id"] == sense["sense_id"]
    assert mapped["scope_id"] == sense["scope_id"]


def test_runtime_mapper_contains_no_dataset_path_constant() -> None:
    import terminology_contracts.dataset_mapping as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "E:/" not in source
    assert "C:/" not in source
