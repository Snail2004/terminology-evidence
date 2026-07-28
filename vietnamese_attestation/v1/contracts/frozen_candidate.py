from __future__ import annotations

from typing import Any, Mapping

from vietnamese_attestation.v1.contracts.base import (
    CanonicalPolicy,
    ContractValidationError,
    canonicalize,
    require_enum,
    require_exact_keys,
    require_list,
    require_mapping,
    require_sha256,
    require_string,
    require_unique,
    seal_payload,
    verify_payload_hash,
)


FROZEN_CANDIDATE_SCHEMA_ID = "FrozenTerminologyCandidateV1"
FROZEN_CANDIDATE_SCHEMA_VERSION = "1.0.0"
FROZEN_CANDIDATE_POLICY_ID = "frozen_terminology_candidate_v1"
HASH_PATH = ("integrity", "frozen_candidate_sha256")
POLICY = CanonicalPolicy(
    set_like_paths=frozenset(
        {
            ("sense_contract", "definition_provenance"),
            ("known_surfaces", "validated_variants"),
            ("known_surfaces", "rejected_variants"),
            ("domain_profile", "vi_anchors"),
            ("domain_profile", "en_anchors"),
        }
    ),
    semantic_sequence_paths=frozenset(),
)


def seal_frozen_candidate(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(payload)
    candidate["schema_id"] = FROZEN_CANDIDATE_SCHEMA_ID
    candidate["schema_version"] = FROZEN_CANDIDATE_SCHEMA_VERSION
    candidate["policy_id"] = FROZEN_CANDIDATE_POLICY_ID
    candidate.setdefault("integrity", {})
    sealed = seal_payload(candidate, policy=POLICY, hash_path=HASH_PATH)
    return validate_frozen_candidate(sealed)


def validate_frozen_candidate(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = require_mapping(payload, path="$")
    require_exact_keys(
        root,
        required={
            "schema_id",
            "schema_version",
            "policy_id",
            "source_contract_ref",
            "candidate_id",
            "candidate_version",
            "term_id",
            "source_term",
            "candidate_vi",
            "sense_id",
            "scope_id",
            "sense_contract",
            "known_surfaces",
            "domain_profile",
            "run_policy",
            "integrity",
        },
        path="$",
    )
    source_ref = _source_contract_ref(root["source_contract_ref"])
    sense = _sense_contract(root["sense_contract"])
    surfaces = _known_surfaces(root["known_surfaces"])
    domain = _domain_profile(root["domain_profile"])
    run_policy = _run_policy(root["run_policy"])
    integrity = require_mapping(root["integrity"], path="$.integrity")
    require_exact_keys(
        integrity,
        required={"frozen_candidate_sha256"},
        path="$.integrity",
    )
    normalized = {
        "schema_id": require_enum(
            root["schema_id"],
            {FROZEN_CANDIDATE_SCHEMA_ID},
            path="$.schema_id",
        ),
        "schema_version": require_enum(
            root["schema_version"],
            {FROZEN_CANDIDATE_SCHEMA_VERSION},
            path="$.schema_version",
        ),
        "policy_id": require_enum(
            root["policy_id"],
            {FROZEN_CANDIDATE_POLICY_ID},
            path="$.policy_id",
        ),
        "source_contract_ref": source_ref,
        "candidate_id": require_string(
            root["candidate_id"], path="$.candidate_id", maximum=256
        ),
        "candidate_version": require_string(
            root["candidate_version"], path="$.candidate_version", maximum=4096
        ),
        "term_id": require_string(
            root["term_id"], path="$.term_id", maximum=256
        ),
        "source_term": require_string(
            root["source_term"], path="$.source_term", maximum=4096
        ),
        "candidate_vi": require_string(
            root["candidate_vi"], path="$.candidate_vi", maximum=4096
        ),
        "sense_id": require_string(
            root["sense_id"], path="$.sense_id", maximum=256
        ),
        "scope_id": require_string(
            root["scope_id"], path="$.scope_id", maximum=256
        ),
        "sense_contract": sense,
        "known_surfaces": surfaces,
        "domain_profile": domain,
        "run_policy": run_policy,
        "integrity": {
            "frozen_candidate_sha256": require_sha256(
                integrity["frozen_candidate_sha256"],
                path="$.integrity.frozen_candidate_sha256",
            )
        },
    }
    if surfaces["canonical"] != normalized["candidate_vi"]:
        raise ContractValidationError(
            "candidate_surface_mismatch",
            "$.known_surfaces.canonical",
            "canonical surface must equal candidate_vi",
        )
    if not verify_payload_hash(normalized, policy=POLICY, hash_path=HASH_PATH):
        raise ContractValidationError(
            "self_hash",
            "$.integrity.frozen_candidate_sha256",
            "frozen candidate self-hash mismatch",
        )
    return canonicalize(normalized, policy=POLICY)


def _source_contract_ref(value: Any) -> dict[str, Any]:
    row = require_mapping(value, path="$.source_contract_ref")
    require_exact_keys(
        row,
        required={
            "schema_id",
            "schema_version",
            "artifact_ref",
            "artifact_sha256",
        },
        path="$.source_contract_ref",
    )
    return {
        "schema_id": require_string(
            row["schema_id"], path="$.source_contract_ref.schema_id"
        ),
        "schema_version": require_string(
            row["schema_version"],
            path="$.source_contract_ref.schema_version",
        ),
        "artifact_ref": require_string(
            row["artifact_ref"], path="$.source_contract_ref.artifact_ref"
        ),
        "artifact_sha256": require_sha256(
            row["artifact_sha256"],
            path="$.source_contract_ref.artifact_sha256",
        ),
    }


def _sense_contract(value: Any) -> dict[str, Any]:
    row = require_mapping(value, path="$.sense_contract")
    require_exact_keys(
        row,
        required={
            "definition_en",
            "definition_review_status",
            "definition_provenance",
            "sense_inventory_version",
        },
        path="$.sense_contract",
    )
    provenance = _string_set(
        row["definition_provenance"],
        path="$.sense_contract.definition_provenance",
    )
    return {
        "definition_en": require_string(
            row["definition_en"],
            path="$.sense_contract.definition_en",
            maximum=4096,
        ),
        "definition_review_status": require_enum(
            row["definition_review_status"],
            {"VERIFIED", "UNVERIFIED"},
            path="$.sense_contract.definition_review_status",
        ),
        "definition_provenance": provenance,
        "sense_inventory_version": require_string(
            row["sense_inventory_version"],
            path="$.sense_contract.sense_inventory_version",
        ),
    }


def _known_surfaces(value: Any) -> dict[str, Any]:
    row = require_mapping(value, path="$.known_surfaces")
    require_exact_keys(
        row,
        required={"canonical", "validated_variants", "rejected_variants"},
        path="$.known_surfaces",
    )
    canonical = require_string(
        row["canonical"], path="$.known_surfaces.canonical", maximum=4096
    )
    validated = _string_set(
        row["validated_variants"],
        path="$.known_surfaces.validated_variants",
    )
    rejected = _string_set(
        row["rejected_variants"],
        path="$.known_surfaces.rejected_variants",
    )
    if canonical in validated or canonical in rejected:
        raise ContractValidationError(
            "surface_overlap",
            "$.known_surfaces",
            "canonical surface must not be repeated as a variant",
        )
    overlap = set(validated) & set(rejected)
    if overlap:
        raise ContractValidationError(
            "surface_overlap",
            "$.known_surfaces",
            "validated and rejected variants overlap",
        )
    return {
        "canonical": canonical,
        "validated_variants": validated,
        "rejected_variants": rejected,
    }


def _domain_profile(value: Any) -> dict[str, Any]:
    row = require_mapping(value, path="$.domain_profile")
    require_exact_keys(
        row,
        required={"domain_name", "vi_anchors", "en_anchors"},
        path="$.domain_profile",
    )
    return {
        "domain_name": require_string(
            row["domain_name"], path="$.domain_profile.domain_name"
        ),
        "vi_anchors": _string_set(
            row["vi_anchors"], path="$.domain_profile.vi_anchors"
        ),
        "en_anchors": _string_set(
            row["en_anchors"], path="$.domain_profile.en_anchors"
        ),
    }


def _run_policy(value: Any) -> dict[str, Any]:
    row = require_mapping(value, path="$.run_policy")
    required = {
        "attestation_policy_version",
        "query_policy_version",
        "source_policy_version",
        "dedup_policy_version",
        "judge_policy_version",
    }
    require_exact_keys(row, required=required, path="$.run_policy")
    return {
        key: require_string(row[key], path=f"$.run_policy.{key}")
        for key in sorted(required)
    }


def _string_set(value: Any, *, path: str) -> list[str]:
    rows = [
        require_string(item, path=f"{path}[{index}]", maximum=4096)
        for index, item in enumerate(require_list(value, path=path))
    ]
    require_unique(rows, path=path)
    return sorted(rows)


__all__ = [
    "FROZEN_CANDIDATE_POLICY_ID",
    "FROZEN_CANDIDATE_SCHEMA_ID",
    "FROZEN_CANDIDATE_SCHEMA_VERSION",
    "seal_frozen_candidate",
    "validate_frozen_candidate",
]
