from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


PACKAGE_VERSION = "1.1.0"
LEGACY_VERSION = "1.0.0"
FEATURE_CONTRACT_VERSION = "1.1.0"
GATE_REGISTRY_VERSION = "1.1.0"
SCHEMA_REGISTRY_VERSION = "1.1.0"

SCHEMA_FILES: dict[str, str] = {
    "EffectiveSenseContractV1": "effective_sense_contract.schema.json",
    "FrozenCandidateContractV1": "frozen_candidate_contract.schema.json",
    "ContextEvidencePackageV1": "context_evidence_package.schema.json",
    "AttestationEvidencePackageV1": "attestation_evidence_package.schema.json",
    "OptionalProbePackageV1": "optional_probe_package.schema.json",
    "GlobalValidatorInputV1": "global_validator_input.schema.json",
    "GateResultSetV1": "gate_result_set.schema.json",
    "CalibrationArtifactV1": "calibration_artifact.schema.json",
    "GlobalDecisionPackageV1": "global_decision_package.schema.json",
    "TerminologyCertificateV1": "terminology_certificate.schema.json",
    "TACOccurrenceInputV1": "tac_occurrence_input.schema.json",
}

CANDIDATE_JOIN_FIELDS: tuple[str, ...] = (
    "candidate_id",
    "candidate_version",
    "source_term",
    "candidate_vi",
    "sense_id",
    "scope_id",
    "sense_inventory_version",
    "dataset_manifest_sha256",
    "effective_sense_contract_sha256",
)

CORE_FEATURES: tuple[str, ...] = (
    "C_mean",
    "C_min",
    "C_max",
    "C_range",
    "C_evidence_coverage",
    "C_required_context_type_coverage",
    "C_judge_agreement",
    "C_valid_context_count",
    "C_pass_count",
    "C_minor_count",
    "C_fail_count",
    "E_authority",
    "E_independence",
    "E_domain",
    "E_concept",
    "E_conventionality",
    "E_coverage",
)

PRODUCER_CONTEXT_FEATURES: tuple[str, ...] = (
    "C_mean",
    "C_min",
    "C_max",
    "C_range",
    "evidence_coverage",
    "required_context_type_coverage",
    "judge_agreement",
    "valid_context_count",
    "pass_count",
    "minor_count",
    "fail_count",
)

PRODUCER_ATTESTATION_FEATURES: tuple[str, ...] = (
    "E_authority",
    "E_independence",
    "E_domain",
    "E_concept",
    "E_conventionality",
    "E_coverage",
)

OPTIONAL_PROBE_FEATURES: tuple[str, ...] = ("R_score", "Q_score")

DIAGNOSTIC_FEATURES: tuple[str, ...] = (
    "C_replacement_rate",
    "C_contrastive_boundary_support",
    "E_strong_positive_cluster_count",
    "E_conflict_ratio",
)

DEPRECATED_FEATURES: tuple[str, ...] = (
    "E_score",
    "feature_registry_version",
    "support_context_refs",
)

GATE_IDS: tuple[str, ...] = (
    "input_contract_mismatch",
    "sense_definition_unverified",
    "unresolved_polysemy",
    "concept_mismatch",
    "wrong_sense",
    "contradiction",
    "target_collision",
    "judge_disagreement",
    "insufficient_evidence",
    "missing_contrastive_context",
    "incomplete_context_type_coverage",
    "attestation_unjudgeable",
)

GATE_ACTIONS: tuple[str, ...] = (
    "NONE",
    "FATAL_REJECT",
    "FATAL_SPLIT",
    "ESCALATE_HUMAN",
    "CAP_PROVISIONAL",
)

GATE_ACTION_PRECEDENCE: tuple[str, ...] = (
    "FATAL_SPLIT",
    "FATAL_REJECT",
    "ESCALATE_HUMAN",
    "CAP_PROVISIONAL",
    "NONE",
)

GATE_SOURCE_MODULES: tuple[str, ...] = (
    "CONTRACT",
    "SENSE",
    "C",
    "E",
    "GLOBAL",
    "HUMAN_REVIEW",
)


class RegistryError(ValueError):
    pass


def feature_registry_payload() -> dict[str, Any]:
    return {
        "registry_id": "TerminologyFeatureContractRegistryV1_1",
        "registry_version": FEATURE_CONTRACT_VERSION,
        "core_features": list(CORE_FEATURES),
        "producer_context_features": list(PRODUCER_CONTEXT_FEATURES),
        "producer_attestation_features": list(PRODUCER_ATTESTATION_FEATURES),
        "optional_probe_features": list(OPTIONAL_PROBE_FEATURES),
        "diagnostic_features": list(DIAGNOSTIC_FEATURES),
        "deprecated_features": list(DEPRECATED_FEATURES),
    }


def gate_registry_payload() -> dict[str, Any]:
    return {
        "registry_id": "TerminologyGateRegistryV1_1",
        "registry_version": GATE_REGISTRY_VERSION,
        "gate_ids": list(GATE_IDS),
        "actions": list(GATE_ACTIONS),
        "precedence": list(GATE_ACTION_PRECEDENCE),
        "source_modules": list(GATE_SOURCE_MODULES),
    }


def schema_registry_payload() -> dict[str, Any]:
    return {
        "registry_id": "TerminologySchemaRegistryV1_1",
        "registry_version": SCHEMA_REGISTRY_VERSION,
        "package_version": PACKAGE_VERSION,
        "legacy_versions": [LEGACY_VERSION],
        "schemas": [
            {
                "schema_id": schema_id,
                "schema_version": PACKAGE_VERSION,
                "path": f"schemas/v1.1.0/{filename}",
                "legacy_path": f"schemas/legacy/v1.0.0/{filename}",
            }
            for schema_id, filename in sorted(SCHEMA_FILES.items())
        ],
    }


def load_registry(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot load registry {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RegistryError(f"registry {path} must be a JSON object")
    return payload


def known_feature_names(registry: Mapping[str, Any]) -> frozenset[str]:
    groups = (
        "core_features",
        "optional_probe_features",
        "diagnostic_features",
    )
    result: set[str] = set()
    for group in groups:
        values = registry.get(group)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            raise RegistryError(f"invalid feature registry group: {group}")
        if len(values) != len(set(values)):
            raise RegistryError(f"duplicate feature in registry group: {group}")
        result.update(values)
    deprecated = registry.get("deprecated_features", [])
    if not isinstance(deprecated, list) or not all(
        isinstance(value, str) and value for value in deprecated
    ):
        raise RegistryError("invalid deprecated feature registry group")
    overlap = result.intersection(deprecated)
    if overlap:
        raise RegistryError(
            "active and deprecated feature names overlap: "
            + ", ".join(sorted(overlap))
        )
    return frozenset(result)
