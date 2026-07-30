from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Mapping


def load_contract_authority(repo_root: Path) -> tuple[Any, Any, Any]:
    package_root = repo_root / "terminology_contracts_v1" / "python"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from terminology_contracts.bindings import (  # type: ignore
        seal_frozen_candidate_contract,
    )
    from terminology_contracts.dataset_mapping import map_candidate_key  # type: ignore
    from terminology_contracts.integrity import seal_self_hash  # type: ignore

    return seal_self_hash, seal_frozen_candidate_contract, map_candidate_key


def provenance(
    *,
    component_id: str,
    component_version: str,
    policy_version: str,
    run_id: str,
    run_spec_id: str,
    created_at: str,
    source_artifact_hashes: Mapping[str, str],
    execution_config_sha256: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "started_at": created_at,
        "completed_at": created_at,
        "component_id": component_id,
        "component_version": component_version,
        "policy_version": policy_version,
        "prompt_hashes": {},
        "model_routes": [],
        "source_artifact_hashes": dict(sorted(source_artifact_hashes.items())),
        "raw_ledger_ref": None,
        "notes": notes,
        "run_spec_id": run_spec_id,
        "execution_config_sha256": execution_config_sha256,
    }


def domain_profile(
    sense: Mapping[str, Any], candidates: list[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "domain_id": sense["scope_id"],
        "anchors_en": [sense["source_term"]],
        "anchors_vi": sorted(
            {str(candidate["candidate_target_vi"]) for candidate in candidates}
        ),
    }


def effective_sense_contract(
    *,
    sense: Mapping[str, Any],
    candidates: list[Mapping[str, Any]],
    review_binding_sha256: str,
    dataset_manifest_sha256: str,
    created_at: str,
    execution_config_sha256: str,
    source_hashes: Mapping[str, str],
    seal_self_hash: Any,
) -> dict[str, Any]:
    contract = {
        "schema_id": "EffectiveSenseContractV1",
        "schema_version": "1.1.0",
        "sense_id": sense["sense_id"],
        "scope_id": sense["scope_id"],
        "source_term": sense["source_term"],
        "effective_definition_en": sense["definition"],
        "effective_part_of_speech": sense["part_of_speech"],
        "scope_note": None,
        "domain_profile": domain_profile(sense, candidates),
        "definition_source": "MODEL_ACCEPTED",
        "review_status": "ACCEPTED",
        "sense_inventory_version": sense["dataset_version"],
        "parent_dataset_manifest_sha256": dataset_manifest_sha256,
        "review_artifact_sha256": review_binding_sha256,
        "provenance": provenance(
            component_id="d2l-dataset-effective-sense-projector",
            component_version="1.0.0",
            policy_version="d2l-stage-a-p0b-official-5-sense-v1.0",
            run_id="d2l-stage-a-p0b-official-5-sense-release",
            run_spec_id="d2l-stage-a-p0b-official-5-sense-spec-v1",
            created_at=created_at,
            source_artifact_hashes=source_hashes,
            execution_config_sha256=execution_config_sha256,
            notes="Zero-network Dataset projection from human-reviewed Stage A evidence.",
        ),
    }
    return seal_self_hash(contract)


def frozen_candidate_contract(
    *,
    candidate: Mapping[str, Any],
    sense: Mapping[str, Any],
    sense_candidates: list[Mapping[str, Any]],
    effective: Mapping[str, Any],
    dataset_manifest_sha256: str,
    created_at: str,
    execution_config_sha256: str,
    source_hashes: Mapping[str, str],
    seal_frozen_candidate_contract: Any,
    map_candidate_key: Any,
) -> dict[str, Any]:
    candidate_key = map_candidate_key(
        candidate=candidate,
        sense=sense,
        dataset_version=sense["dataset_version"],
        dataset_manifest_sha256=dataset_manifest_sha256,
        effective_sense_contract_sha256=effective["integrity"]["self_sha256"],
    )
    alternatives = [
        other["candidate_target_vi"]
        for other in sense_candidates
        if other["candidate_instance_id"] != candidate["candidate_instance_id"]
    ]
    contract = {
        "schema_id": "FrozenCandidateContractV1",
        "schema_version": "1.1.0",
        "candidate_key": candidate_key,
        "effective_definition_en": effective["effective_definition_en"],
        "effective_part_of_speech": effective["effective_part_of_speech"],
        "scope_note": effective["scope_note"],
        "domain_profile": copy.deepcopy(effective["domain_profile"]),
        "surfaces": {
            "canonical_vi": candidate["candidate_target_vi"],
            "validated_variants_vi": [],
            "rejected_variants_vi": [],
        },
        "alternatives_vi": alternatives,
        "input_provenance": provenance(
            component_id="d2l-dataset-frozen-candidate-projector",
            component_version="1.0.0",
            policy_version="d2l-stage-a-p0b-official-5-sense-v1.0",
            run_id="d2l-stage-a-p0b-official-5-sense-release",
            run_spec_id="d2l-stage-a-p0b-official-5-sense-spec-v1",
            created_at=created_at,
            source_artifact_hashes=source_hashes,
            execution_config_sha256=execution_config_sha256,
            notes="Candidate identity is frozen; no candidate gold label or final glossary decision is assigned.",
        ),
        # The authority binding hash retains the integrity object while
        # excluding only integrity.self_sha256. Seed the object before the
        # binding is calculated so construction and verification see the same
        # canonical surface.
        "integrity": {},
    }
    return seal_frozen_candidate_contract(contract)


def constraint_evidence_package(
    *,
    frozen: Mapping[str, Any],
    effective: Mapping[str, Any],
    review_binding_path: str,
    review_binding_sha256: str,
    created_at: str,
    execution_config_sha256: str,
    source_hashes: Mapping[str, str],
    seal_self_hash: Any,
) -> dict[str, Any]:
    sense_id = effective["sense_id"]
    review_ref = {
        "evidence_id": f"review-binding-{sense_id}",
        "evidence_type": "REVIEW_ARTIFACT",
        "uri": f"artifact://d2l-stage-a-p0b/{review_binding_path}",
        "sha256": review_binding_sha256,
    }
    package = {
        "schema_id": "ConstraintEvidencePackageV1",
        "schema_version": "1.1.0",
        "candidate_key": copy.deepcopy(frozen["candidate_key"]),
        "input_contract_sha256": frozen["input_contract_sha256"],
        "binding_status": "COMPLETE",
        "sense_review": {
            "status": "VERIFIED",
            "effective_sense_contract_sha256": effective["integrity"]["self_sha256"],
            "review_artifact_ref": review_ref,
        },
        "polysemy_resolution": {
            "status": "RESOLVED_SINGLE",
            "related_sense_ids": [sense_id],
            "authority_ref": review_ref,
        },
        "target_collision": {
            "status": "UNJUDGEABLE",
            "collision_index_sha256": None,
            "collision_index_ref": None,
            "conflicting_candidate_keys": [],
            "evidence_refs": [],
        },
        "provenance": provenance(
            component_id="d2l-dataset-constraint-projector",
            component_version="1.0.0",
            policy_version="d2l-stage-a-p0b-official-5-sense-v1.0",
            run_id="d2l-stage-a-p0b-official-5-sense-release",
            run_spec_id="d2l-stage-a-p0b-official-5-sense-spec-v1",
            created_at=created_at,
            source_artifact_hashes=source_hashes,
            execution_config_sha256=execution_config_sha256,
            notes="Sense review and polysemy are bound; target collision remains explicitly unjudgeable for downstream review.",
        ),
    }
    return seal_self_hash(package)
