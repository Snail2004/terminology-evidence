from __future__ import annotations

from typing import Any, Mapping, Sequence

from context_substitution.v2.contracts.input import validate_context_substitution_input
from context_substitution.v2.contracts.run import validate_context_substitution_run
from context_substitution.v2.integration.authority import canonical_sha256
from context_substitution.v2.integration.common import seal_object


FIXTURE_SET_SCHEMA_ID = "ContextSubstitutionTestCandidateFixtureSetV1"
FIXTURE_SET_SCHEMA_VERSION = "2.0.0"
FIXTURE_HOLD_STATUS = "HOLD_LOCAL_CONFORMANCE_ONLY"
CANDIDATE_FIXTURE_SCHEMA_ID = "ContextSubstitutionTestCandidateFixtureV1"


def build_development_frozen_candidate_fixtures(
    *,
    input_payload: Mapping[str, Any],
    run_payload: Mapping[str, Any],
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    """Build test-only rows that cannot validate as FrozenCandidateContractV1."""

    source = validate_context_substitution_input(input_payload)
    run = validate_context_substitution_run(run_payload)
    if run["input_sha256"] != source["integrity"]["input_sha256"]:
        raise ValueError("development fixture input and Context Substitution run differ")
    policy = run["execution_policy"]
    if policy["selector_mode"] != "MODEL_CLASSIFICATION_DEVELOPMENT":
        raise ValueError("development fixtures require development selector mode")

    candidates = sorted(run["candidates"], key=lambda row: row["candidate_id"])
    alternatives_by_term = _alternatives_by_term(candidates)
    frozen = [
        _freeze_candidate(
            candidate,
            alternatives=alternatives_by_term[candidate["term_id"]],
            dataset_manifest_sha256=policy["dataset_manifest_sha256"],
            source_input_sha256=run["input_sha256"],
            source_run_sha256=run["integrity"]["run_sha256"],
            started_at=started_at,
            completed_at=completed_at,
        )
        for candidate in candidates
    ]
    result = {
        "schema_id": FIXTURE_SET_SCHEMA_ID,
        "schema_version": FIXTURE_SET_SCHEMA_VERSION,
        "status": FIXTURE_HOLD_STATUS,
        "source_input_sha256": run["input_sha256"],
        "source_run_sha256": run["integrity"]["run_sha256"],
        "candidate_count": len(frozen),
        "candidates": frozen,
        "final_glossary_decision": None,
        "integrity": {},
    }
    return seal_object(result, integrity_key="fixture_set_sha256")


def _freeze_candidate(
    candidate: Mapping[str, Any],
    *,
    alternatives: Sequence[str],
    dataset_manifest_sha256: str,
    source_input_sha256: str,
    source_run_sha256: str,
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    target = str(candidate["candidate_translation"])
    candidate_version = candidate["candidate_generation"]["candidate_version"]
    if candidate_version is None:
        raise ValueError("development fixture requires a bound candidate version")
    sense_contract = candidate["sense_contract"]
    sense_hash = canonical_sha256(sense_contract)
    config = {
        "fixture_policy": "C_LOCAL_CONFORMANCE_FIXTURE_V1",
        "source_input_sha256": source_input_sha256,
        "source_run_sha256": source_run_sha256,
    }
    payload = {
        "schema_id": CANDIDATE_FIXTURE_SCHEMA_ID,
        "schema_version": "1.0.0",
        "status": FIXTURE_HOLD_STATUS,
        "candidate_key": {
            "candidate_id": candidate["candidate_id"],
            "candidate_version": candidate_version,
            "source_term": candidate["source_term"],
            "candidate_vi": target,
            "sense_id": candidate["sense_id"],
            "scope_id": candidate["scope_id"],
            "sense_inventory_version": sense_contract["sense_inventory_version"],
            "dataset_manifest_sha256": dataset_manifest_sha256,
            "effective_sense_contract_sha256": sense_hash,
        },
        "effective_definition_en": sense_contract["definition_en"],
        "effective_part_of_speech": candidate["part_of_speech"],
        "scope_note": "Local development conformance fixture; not reviewed authority.",
        "domain_profile": {
            "domain_id": candidate["scope_id"],
            "anchors_en": [candidate["source_term"]],
            "anchors_vi": [target],
        },
        "surfaces": {
            "canonical_vi": target,
            "validated_variants_vi": [],
            "rejected_variants_vi": [],
        },
        "alternatives_vi": sorted(value for value in alternatives if value != target),
        "input_provenance": {
            "run_id": "c-local-fixture:" + source_run_sha256[:24],
            "started_at": started_at,
            "completed_at": completed_at,
            "component_id": "context-substitution-fixture-freezer",
            "component_version": "1.1.0",
            "policy_version": "C_LOCAL_CONFORMANCE_FIXTURE_V1",
            "prompt_hashes": {},
            "model_routes": [],
            "source_artifact_hashes": {
                "dataset": dataset_manifest_sha256,
                "context_substitution_input": source_input_sha256,
                "context_substitution_run": source_run_sha256,
                "effective_sense_contract": sense_hash,
            },
            "raw_ledger_ref": None,
            "notes": "HOLD_LOCAL_CONFORMANCE_ONLY; not a reviewed Frozen Candidate authority.",
            "run_spec_id": "c-local-fixture-spec:" + source_input_sha256[:24],
            "execution_config_sha256": canonical_sha256(config),
        },
        "integrity": {},
        "source_input_sha256": source_input_sha256,
        "source_run_sha256": source_run_sha256,
        "binding_status": "TEST_ONLY_NOT_AUTHORITY",
    }
    return seal_object(payload, integrity_key="fixture_sha256")


def _alternatives_by_term(
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for candidate in candidates:
        result.setdefault(candidate["term_id"], []).append(
            str(candidate["candidate_translation"])
        )
    return {key: sorted(set(values)) for key, values in result.items()}
