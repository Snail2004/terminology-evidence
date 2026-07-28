from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from .archive import (
    DatasetAdapterError,
    VerifiedDatasetArchive,
    load_supported_dataset_archive,
)
from .contracts import (
    ADAPTER_POLICY_ID,
    ADAPTER_SCHEMA_ID,
    ADAPTER_SCHEMA_VERSION,
    seal_adapter_candidate,
    seal_adapter_package,
)
from .specs import PILOT_SPEC, V3_MANIFEST_SHA256, V3_SPEC


AUTHORITY = {
    "official": False,
    "calibrated": False,
    "human_review_complete": False,
    "candidate_is_human_gold": False,
    "final_decision_authority": "GLOBAL_TERMINOLOGY_VALIDATOR_ONLY",
}
UNAVAILABLE_FIELDS = {
    "domain_anchors": "UNAVAILABLE_SCOPE_ID_ONLY",
    "human_gold": "UNAVAILABLE_HUMAN_REVIEW_REQUIRED",
    "known_vietnamese_surfaces": "UNAVAILABLE_NOT_PROVIDED",
}


def adapt_dataset_zip(
    source_zip: str | Path,
    *,
    parent_v3_zip: str | Path | None = None,
) -> dict[str, Any]:
    source = load_supported_dataset_archive(source_zip)
    parent: VerifiedDatasetArchive | None = None
    if source.spec.requires_parent_v3:
        if parent_v3_zip is None:
            raise DatasetAdapterError(
                "parent_v3_required",
                "$parent_v3_zip",
                "pilot V1.1 requires the exact V3 authority",
            )
        parent = load_supported_dataset_archive(parent_v3_zip)
        _validate_pilot_parent(source=source, parent=parent)
    elif parent_v3_zip is not None:
        raise DatasetAdapterError(
            "unexpected_parent",
            "$parent_v3_zip",
            "V3 is a root source and must not receive a parent",
        )
    parent_manifest_sha = (
        parent.spec.manifest_sha256 if parent is not None else None
    )
    senses = {_join_key(row): row for row in source.term_senses}
    candidates = [
        _map_candidate(
            candidate,
            sense=senses[_join_key(candidate)],
            dataset_manifest_sha256=source.spec.manifest_sha256,
            parent_dataset_manifest_sha256=parent_manifest_sha,
        )
        for candidate in source.candidate_instances
    ]
    candidates.sort(key=lambda row: row["candidate_id"])
    receipt = {
        "agent": "E",
        "adapter_schema_id": ADAPTER_SCHEMA_ID,
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "adapter_policy_id": ADAPTER_POLICY_ID,
        "source_schema_id": source.spec.schema_id,
        "source_schema_version": source.spec.schema_version,
        "source_zip_sha256": source.zip_sha256,
        "source_manifest_file_sha256": source.manifest_file_sha256,
        "source_manifest_sha256": source.spec.manifest_sha256,
        "parent_dataset_manifest_sha256": parent_manifest_sha,
        "effective_sense_contract_sha256": None,
        "review_artifact_sha256": None,
        "term_sense_count": len(source.term_senses),
        "candidate_count": len(candidates),
        "context_count": len(source.contexts),
        "mode": source.spec.mode,
        "provider_call_count": 0,
        "final_glossary_decision": None,
    }
    return seal_adapter_package(
        {
            "source": {
                "schema_id": source.spec.schema_id,
                "schema_version": source.spec.schema_version,
                "zip_sha256": source.zip_sha256,
                "manifest_file_sha256": source.manifest_file_sha256,
                "manifest_sha256": source.spec.manifest_sha256,
                "dataset_version": source.spec.dataset_version,
                "parent_dataset_manifest_sha256": parent_manifest_sha,
            },
            "mode": source.spec.mode,
            "authority": AUTHORITY,
            "unavailable_fields": UNAVAILABLE_FIELDS,
            "candidates": candidates,
            "receipt": receipt,
            "final_glossary_decision": None,
        }
    )


def _validate_pilot_parent(
    *,
    source: VerifiedDatasetArchive,
    parent: VerifiedDatasetArchive,
) -> None:
    if source.spec != PILOT_SPEC or parent.spec != V3_SPEC:
        raise DatasetAdapterError(
            "parent_schema",
            "$parent_v3_zip",
            "pilot parent must be exact supported V3",
        )
    source_v3 = source.manifest.get("source_v3")
    if not isinstance(source_v3, Mapping):
        raise DatasetAdapterError(
            "pilot_parent_binding", "$.manifest.source_v3", "missing object"
        )
    expected = {
        "schema_id": V3_SPEC.schema_id,
        "dataset_version": V3_SPEC.dataset_version,
        "manifest_sha256": V3_MANIFEST_SHA256,
        "manifest_file_sha256": V3_SPEC.manifest_file_sha256,
    }
    for field, value in expected.items():
        if source_v3.get(field) != value:
            raise DatasetAdapterError(
                "pilot_parent_binding",
                f"$.manifest.source_v3.{field}",
                f"expected {value!r}",
            )
    for name in (
        "term_senses.jsonl",
        "candidate_instances.jsonl",
        "contexts.jsonl",
    ):
        parent_rows = set(parent.raw_jsonl_rows[name])
        child_rows = source.raw_jsonl_rows[name]
        if any(row not in parent_rows for row in child_rows):
            raise DatasetAdapterError(
                "pilot_parent_row_drift",
                f"$.{name}",
                "pilot row is not byte-identical to V3",
            )
    slots_by_id = {
        str(row["candidate_slot_id"]): row for row in parent.candidate_slots
    }
    for index, candidate in enumerate(source.candidate_instances):
        path = f"$.candidates[{index}]"
        slot_id = str(candidate["candidate_slot_id"])
        slot = slots_by_id.get(slot_id)
        if slot is None:
            raise DatasetAdapterError(
                "broken_candidate_slot_ref", path, slot_id
            )
        for field in (
            "candidate_instance_id",
            "candidate_target_vi",
            "formation_method",
            "term_id",
            "sense_id",
            "scope_id",
            "shared_context_set_id",
        ):
            if candidate.get(field) != slot.get(field):
                raise DatasetAdapterError(
                    "candidate_slot_mismatch", f"{path}.{field}", field
                )


def _map_candidate(
    candidate: Mapping[str, Any],
    *,
    sense: Mapping[str, Any],
    dataset_manifest_sha256: str,
    parent_dataset_manifest_sha256: str | None,
) -> dict[str, Any]:
    if sense.get("definition_review_status") != "PENDING_HUMAN_REVIEW":
        raise DatasetAdapterError(
            "unexpected_review_authority",
            "$.term_sense.definition_review_status",
            "development adapter requires pending human review",
        )
    if sense.get("official_cst_status") != "HUMAN_REVIEW_REQUIRED":
        raise DatasetAdapterError(
            "unexpected_review_authority",
            "$.term_sense.official_cst_status",
            "development adapter cannot consume official authority",
        )
    candidate_id = str(candidate["candidate_instance_id"])
    candidate_version = str(candidate["candidate_instance_sha256"])
    return seal_adapter_candidate(
        {
            "candidate_id": candidate_id,
            "candidate_version": candidate_version,
            "term_id": str(candidate["term_id"]),
            "source_term": str(sense["source_term"]),
            "candidate_vi": str(candidate["candidate_target_vi"]),
            "sense_id": str(candidate["sense_id"]),
            "scope_id": str(candidate["scope_id"]),
            "shared_context_set_id": str(
                candidate["shared_context_set_id"]
            ),
            "source_candidate_slot_id": str(
                candidate["candidate_slot_id"]
            ),
            "identity_binding": {
                "candidate_id": candidate_id,
                "candidate_version": candidate_version,
                "sense_id": str(candidate["sense_id"]),
                "scope_id": str(candidate["scope_id"]),
                "sense_inventory_version": str(sense["dataset_version"]),
                "dataset_manifest_sha256": dataset_manifest_sha256,
                "parent_dataset_manifest_sha256": (
                    parent_dataset_manifest_sha256
                ),
                "effective_sense_contract_sha256": None,
            },
            "sense_contract": {
                "definition_en": str(sense["definition"]),
                "part_of_speech": str(sense["part_of_speech"]),
                "review_status": "PENDING_HUMAN_REVIEW",
                "term_sense_sha256": str(sense["term_sense_sha256"]),
                "sense_inventory_version": str(sense["dataset_version"]),
                "effective_sense_contract_sha256": None,
            },
            "formation": {
                "method": str(candidate["formation_method"]),
                "provenance": copy.deepcopy(
                    candidate["formation_provenance"]
                ),
                "applicability": copy.deepcopy(candidate["applicability"]),
            },
            "context_provenance": {
                "primary_context_ids": list(sense["primary_context_ids"]),
                "backup_context_ids": list(sense["backup_context_ids"]),
                "contrastive_context_ids": list(
                    sense["contrastive_context_ids"]
                ),
                "usage_policy": "PROVENANCE_ONLY_NOT_ATTESTATION_EVIDENCE",
            },
            "known_vietnamese_surfaces": {
                "status": "UNAVAILABLE_NOT_PROVIDED",
                "canonical": None,
                "validated_variants": None,
                "rejected_variants": None,
                "source_term_surfaces_usage": (
                    "ENGLISH_SOURCE_ONLY_NOT_MAPPED"
                ),
            },
            "domain_anchors": {
                "status": "UNAVAILABLE_SCOPE_ID_ONLY",
                "domain_profile_id": None,
                "vi_anchors": None,
                "en_anchors": None,
            },
            "authority": AUTHORITY,
            "final_glossary_decision": None,
        }
    )


def _join_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return tuple(
        str(row[field])
        for field in (
            "term_id",
            "sense_id",
            "scope_id",
            "shared_context_set_id",
        )
    )


__all__ = ["adapt_dataset_zip"]
