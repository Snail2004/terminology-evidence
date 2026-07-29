from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from context_substitution.v2.dataset.reviewed_support import (
    reviewed_support_to_context_substitution_input,
    validate_reviewed_support_bundle,
)
from context_substitution.v2.integration.common import (
    file_sha256,
    load_json,
    object_sha256,
    seal_object,
)


PILOT_SMOKE_SCHEMA_ID = "D2LContextSubstitutionPilotSmokeReceiptV1"
PILOT_SMOKE_SCHEMA_VERSION = "1.0.0"


def run_zero_api_pilot_smoke(
    *,
    pilot_directory: Path,
    pilot_zip: Path,
    parent_directory: Path,
    parent_zip: Path,
) -> dict[str, Any]:
    pilot_zip_hash = file_sha256(pilot_zip)
    parent_zip_hash = file_sha256(parent_zip)
    directory_validation = validate_reviewed_support_bundle(
        pilot_directory,
        parent_v3_source=parent_directory,
    )
    zip_validation = validate_reviewed_support_bundle(
        pilot_zip,
        expected_zip_sha256=pilot_zip_hash,
        parent_v3_source=parent_zip,
        expected_parent_zip_sha256=parent_zip_hash,
    )
    directory_adapted = reviewed_support_to_context_substitution_input(
        pilot_directory,
        parent_v3_source=parent_directory,
        source_split="development",
    )
    zip_adapted = reviewed_support_to_context_substitution_input(
        pilot_zip,
        expected_zip_sha256=pilot_zip_hash,
        parent_v3_source=parent_zip,
        expected_parent_zip_sha256=parent_zip_hash,
        source_split="development",
    )

    directory_input = directory_adapted["input"]
    zip_input = zip_adapted["input"]
    directory_semantic = _semantic_projection(directory_input)
    zip_semantic = _semantic_projection(zip_input)
    if directory_semantic != zip_semantic:
        raise ValueError("pilot directory and ZIP semantic projections differ")

    manifest = load_json(Path(pilot_directory) / "manifest.json")
    context_counts = dict(manifest["validation"]["context_role_counts"])
    counts = {
        "term_senses": int(directory_validation["counts"]["term_senses"]),
        "candidates": int(directory_validation["counts"]["candidate_instances"]),
        "primary_contexts": int(context_counts.get("PRIMARY", 0)),
        "backup_contexts": int(context_counts.get("BACKUP", 0)),
        "contrastive_contexts": int(context_counts.get("CONTRASTIVE", 0)),
        "missing_references": int(
            manifest["validation"]["missing_context_reference_count"]
        ),
    }
    expected = {
        "term_senses": 5,
        "candidates": 15,
        "primary_contexts": 25,
        "backup_contexts": 8,
        "contrastive_contexts": 5,
        "missing_references": 0,
    }
    if counts != expected:
        raise ValueError(f"pilot smoke counts differ: expected {expected}, got {counts}")
    if (
        directory_validation["provider_call_count"] != 0
        or zip_validation["provider_call_count"] != 0
    ):
        raise ValueError("zero-API pilot smoke unexpectedly recorded provider calls")

    receipt = {
        "schema_id": PILOT_SMOKE_SCHEMA_ID,
        "schema_version": PILOT_SMOKE_SCHEMA_VERSION,
        "agent": "CONTEXT_SUBSTITUTION_C",
        "adapter_version": directory_adapted["receipt"]["adapter_schema_version"],
        "dataset_manifest_sha256": directory_validation["source_manifest_sha256"],
        "parent_dataset_manifest_sha256": directory_validation[
            "parent_dataset_manifest_sha256"
        ],
        "pilot_zip_sha256": pilot_zip_hash,
        "parent_zip_sha256": parent_zip_hash,
        "directory_receipt_sha256": directory_adapted["receipt"]["receipt_sha256"],
        "zip_receipt_sha256": zip_adapted["receipt"]["receipt_sha256"],
        "semantic_projection_sha256": object_sha256(directory_semantic),
        "candidate_ids": directory_semantic["candidate_ids"],
        "counts": counts,
        "provider_call_count": 0,
        "final_glossary_decision": None,
        "status": "PASS",
        "integrity": {},
    }
    return seal_object(receipt, integrity_key="receipt_sha256")


def _semantic_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    terms = list(value["terms"])
    return {
        "input_schema_id": value["schema_id"],
        "input_schema_version": value["schema_version"],
        "dataset_manifest_sha256": value["selection_contract"][
            "dataset_manifest_sha256"
        ],
        "parent_dataset_manifest_sha256": value["selection_contract"][
            "parent_dataset_manifest_sha256"
        ],
        "terms": terms,
        "candidate_ids": sorted(
            target["candidate_target_id"]
            for term in terms
            for target in term["candidate_targets"]
        ),
    }
