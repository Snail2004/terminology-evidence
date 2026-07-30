from __future__ import annotations

import copy
import sys
from typing import Any, Mapping


CONTRACT_TAG = "contracts-v1.1.0"
CONTRACT_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
CONTRACT_MANIFEST_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
CONTRACT_RECEIPT_SELF_SHA256 = "c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4"
CONTRACT_RECEIPT_PHYSICAL_SHA256 = "3497460f16ca478dada7b25425775882f10d1cb2b5d3638c36cba4ec5fb2791b"


def load_contract_authority(repo_root):
    package_root = repo_root / "terminology_contracts_v1" / "python"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from terminology_contracts.bindings import seal_frozen_candidate_contract
    from terminology_contracts.dataset_mapping import map_candidate_key
    from terminology_contracts.integrity import seal_self_hash

    return seal_self_hash, seal_frozen_candidate_contract, map_candidate_key


def _provenance(
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


def _domain_profile(sense: Mapping[str, Any], candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "domain_id": sense["scope_id"],
        "anchors_en": [sense["source_term"]],
        "anchors_vi": sorted({str(candidate["candidate_target_vi"]) for candidate in candidates}),
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
    route = str(sense.get("stage_a_route", ""))
    contract = {
        "schema_id": "EffectiveSenseContractV1",
        "schema_version": "1.1.0",
        "sense_id": sense["sense_id"],
        "scope_id": sense["scope_id"],
        "source_term": sense["source_term"],
        "effective_definition_en": sense["definition"],
        "effective_part_of_speech": sense["part_of_speech"],
        "scope_note": None,
        "domain_profile": _domain_profile(sense, candidates),
        "definition_source": sense.get("definition_source", "MODEL_ACCEPTED"),
        "review_status": "ADJUDICATED" if "ADJUDICATED" in route else "ACCEPTED",
        "sense_inventory_version": sense["dataset_version"],
        "parent_dataset_manifest_sha256": dataset_manifest_sha256,
        "review_artifact_sha256": review_binding_sha256,
        "provenance": _provenance(
            component_id="d2l-dataset-effective-sense-projector",
            component_version="1.0.0",
            policy_version="d2l-dataset-50-senses-150-candidates-stage-b-v1.0",
            run_id="d2l-dataset-50-sense-contract-release",
            run_spec_id="d2l-dataset-50-sense-contract-spec-v1",
            created_at=created_at,
            source_artifact_hashes=source_hashes,
            execution_config_sha256=execution_config_sha256,
            notes="Zero-network projection from Stage A evidence; no Stage B gold or final decision is assigned.",
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
        candidate={
            "candidate_id": candidate["candidate_instance_id"],
            "candidate_version": candidate["candidate_version"],
            "candidate_vi": candidate["candidate_target_vi"],
            "sense_id": candidate["sense_id"],
            "scope_id": candidate["scope_id"],
        },
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
        "input_provenance": _provenance(
            component_id="d2l-dataset-frozen-candidate-projector",
            component_version="1.0.0",
            policy_version="d2l-dataset-50-senses-150-candidates-stage-b-v1.0",
            run_id="d2l-dataset-50-sense-contract-release",
            run_spec_id="d2l-dataset-50-sense-contract-spec-v1",
            created_at=created_at,
            source_artifact_hashes=source_hashes,
            execution_config_sha256=execution_config_sha256,
            notes="Candidate identity is frozen before Stage B; no candidate gold label or final glossary decision is assigned.",
        ),
        "integrity": {},
    }
    return seal_frozen_candidate_contract(contract)


def constraint_evidence_package(
    *,
    frozen: Mapping[str, Any],
    effective: Mapping[str, Any],
    review_binding_path: str,
    review_binding_sha256: str,
    sense: Mapping[str, Any],
    created_at: str,
    execution_config_sha256: str,
    source_hashes: Mapping[str, str],
    seal_self_hash: Any,
) -> dict[str, Any]:
    review_ref = {
        "evidence_id": f"review-binding-{effective['sense_id']}",
        "evidence_type": "REVIEW_ARTIFACT",
        "uri": f"artifact://d2l-dataset-50/{review_binding_path}",
        "sha256": review_binding_sha256,
    }
    collision_status = (
        "UNJUDGEABLE"
        if sense.get("stratum") == "collision_or_multi_target"
        else "UNJUDGEABLE"
    )
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
            "related_sense_ids": [effective["sense_id"]],
            "authority_ref": review_ref,
        },
        "target_collision": {
            "status": collision_status,
            "collision_index_sha256": None,
            "collision_index_ref": None,
            "conflicting_candidate_keys": [],
            "evidence_refs": [],
        },
        "provenance": _provenance(
            component_id="d2l-dataset-constraint-projector",
            component_version="1.0.0",
            policy_version="d2l-dataset-50-senses-150-candidates-stage-b-v1.0",
            run_id="d2l-dataset-50-sense-contract-release",
            run_spec_id="d2l-dataset-50-sense-contract-spec-v1",
            created_at=created_at,
            source_artifact_hashes=source_hashes,
            execution_config_sha256=execution_config_sha256,
            notes="Stage A constraints are bound; candidate gold, C/E evidence, and final glossary decision remain unassigned.",
        ),
    }
    return seal_self_hash(package)
