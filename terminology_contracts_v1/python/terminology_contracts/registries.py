from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .integrity import strict_json_loads


PACKAGE_VERSION = "1.1.0"
LEGACY_VERSION = "1.0.0"
FEATURE_CONTRACT_VERSION = "1.1.0"
GATE_REGISTRY_VERSION = "1.1.0"
SCHEMA_REGISTRY_VERSION = "1.1.0"
GATE_POLICY_ID = "gate-policy-v1"
GATE_POLICY_VERSION = "1.0.0"

SCHEMA_FILES: dict[str, str] = {
    "EffectiveSenseContractV1": "effective_sense_contract.schema.json",
    "FrozenCandidateContractV1": "frozen_candidate_contract.schema.json",
    "ConstraintEvidencePackageV1": "constraint_evidence_package.schema.json",
    "ContextEvidencePackageV1": "context_evidence_package.schema.json",
    "AttestationEvidencePackageV1": "attestation_evidence_package.schema.json",
    "OptionalProbePackageV1": "optional_probe_package.schema.json",
    "GlobalValidatorInputV1": "global_validator_input.schema.json",
    "GateResultSetV1": "gate_result_set.schema.json",
    "GatePolicyArtifactV1": "gate_policy_artifact.schema.json",
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

FEATURE_MAPPINGS: tuple[tuple[str, str, str], ...] = (
    ("context_evidence", "features.C_mean", "C_mean"),
    ("context_evidence", "features.C_min", "C_min"),
    ("context_evidence", "features.C_max", "C_max"),
    ("context_evidence", "features.C_range", "C_range"),
    ("context_evidence", "features.evidence_coverage", "C_evidence_coverage"),
    (
        "context_evidence",
        "features.required_context_type_coverage",
        "C_required_context_type_coverage",
    ),
    ("context_evidence", "features.judge_agreement", "C_judge_agreement"),
    ("context_evidence", "features.valid_context_count", "C_valid_context_count"),
    ("context_evidence", "features.pass_count", "C_pass_count"),
    ("context_evidence", "features.minor_count", "C_minor_count"),
    ("context_evidence", "features.fail_count", "C_fail_count"),
    (
        "context_evidence",
        "diagnostics.replacement_rate",
        "C_replacement_rate",
    ),
    (
        "context_evidence",
        "diagnostics.contrastive_boundary_support",
        "C_contrastive_boundary_support",
    ),
    ("attestation_evidence", "features.E_authority", "E_authority"),
    ("attestation_evidence", "features.E_independence", "E_independence"),
    ("attestation_evidence", "features.E_domain", "E_domain"),
    ("attestation_evidence", "features.E_concept", "E_concept"),
    (
        "attestation_evidence",
        "features.E_conventionality",
        "E_conventionality",
    ),
    ("attestation_evidence", "features.E_coverage", "E_coverage"),
    (
        "attestation_evidence",
        "diagnostics.strong_positive_cluster_count",
        "E_strong_positive_cluster_count",
    ),
    (
        "attestation_evidence",
        "diagnostics.conflict_ratio",
        "E_conflict_ratio",
    ),
    ("optional_probe:R", "features.R_score", "R_score"),
    ("optional_probe:Q", "features.Q_score", "Q_score"),
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

CONTEXT_GATE_SIGNAL_IDS: tuple[str, ...] = (
    "concept_mismatch",
    "wrong_sense",
    "contradiction",
    "judge_disagreement",
    "insufficient_evidence",
    "missing_contrastive_context",
    "incomplete_context_type_coverage",
)

ATTESTATION_GATE_SIGNAL_IDS: tuple[str, ...] = (
    "concept_mismatch",
    "contradiction",
    "judge_disagreement",
    "insufficient_evidence",
    "attestation_unjudgeable",
)

# This is the active RC4 policy. The sealed artifact generated from it is the
# authority consumed by the Global Validator; the registry remains descriptive.
GATE_ALLOWED_ACTIONS: dict[str, tuple[str, ...]] = {
    "input_contract_mismatch": ("FATAL_REJECT",),
    "sense_definition_unverified": ("ESCALATE_HUMAN",),
    "unresolved_polysemy": ("FATAL_SPLIT", "ESCALATE_HUMAN"),
    "concept_mismatch": ("FATAL_REJECT",),
    "wrong_sense": ("FATAL_REJECT", "FATAL_SPLIT"),
    "contradiction": ("FATAL_REJECT", "ESCALATE_HUMAN"),
    "target_collision": ("ESCALATE_HUMAN",),
    "judge_disagreement": ("ESCALATE_HUMAN",),
    "insufficient_evidence": ("CAP_PROVISIONAL", "ESCALATE_HUMAN"),
    "missing_contrastive_context": ("CAP_PROVISIONAL", "ESCALATE_HUMAN"),
    "incomplete_context_type_coverage": ("CAP_PROVISIONAL", "ESCALATE_HUMAN"),
    "attestation_unjudgeable": ("CAP_PROVISIONAL", "ESCALATE_HUMAN"),
}


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
        "feature_mappings": [
            {
                "source_package": source_package,
                "source_path": source_path,
                "target_feature": target_feature,
            }
            for source_package, source_path, target_feature in FEATURE_MAPPINGS
        ],
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
        "signal_sources": {
            "C": list(CONTEXT_GATE_SIGNAL_IDS),
            "E": list(ATTESTATION_GATE_SIGNAL_IDS),
        },
    }


def gate_policy_payload() -> dict[str, Any]:
    return {
        "schema_id": "GatePolicyArtifactV1",
        "schema_version": PACKAGE_VERSION,
        "gate_policy_id": GATE_POLICY_ID,
        "gate_policy_version": GATE_POLICY_VERSION,
        "gate_registry_version": GATE_REGISTRY_VERSION,
        "rules": {
            gate_id: {"allowed_actions": list(GATE_ALLOWED_ACTIONS[gate_id])}
            for gate_id in GATE_IDS
        },
        "integrity": {"self_sha256": ""},
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
                "legacy_path": (
                    None
                    if schema_id
                    in {"ConstraintEvidencePackageV1", "GatePolicyArtifactV1"}
                    else f"schemas/legacy/v1.0.0/{filename}"
                ),
            }
            for schema_id, filename in sorted(SCHEMA_FILES.items())
        ],
    }


def load_registry(path: Path) -> dict[str, Any]:
    try:
        payload = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
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
    mappings = registry.get("feature_mappings")
    if not isinstance(mappings, list) or not mappings:
        raise RegistryError("feature registry requires feature_mappings")
    sources: set[tuple[str, str]] = set()
    targets: set[str] = set()
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, Mapping):
            raise RegistryError(f"feature_mappings[{index}] must be an object")
        source = mapping.get("source_package")
        path = mapping.get("source_path")
        target = mapping.get("target_feature")
        if not all(isinstance(item, str) and item for item in (source, path, target)):
            raise RegistryError(f"feature_mappings[{index}] is incomplete")
        source_key = (source, path)
        if source_key in sources:
            raise RegistryError(f"duplicate feature mapping source: {source}:{path}")
        if target in targets:
            raise RegistryError(f"duplicate feature mapping target: {target}")
        if target not in result:
            raise RegistryError(f"feature mapping target is not active: {target}")
        sources.add(source_key)
        targets.add(target)
    missing_targets = sorted(result.difference(targets))
    if missing_targets:
        raise RegistryError(
            "active features without a source mapping: "
            + ", ".join(missing_targets)
        )
    return frozenset(result)
