from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from terminology_contracts.registries import (  # noqa: E402
    GATE_IDS,
    GATE_SOURCE_MODULES,
    PACKAGE_VERSION,
    feature_registry_payload,
    gate_registry_payload,
    schema_registry_payload,
)


LEGACY = ROOT / "schemas" / "legacy" / "v1.0.0"
V11 = ROOT / "schemas" / "v1.1.0"
CURRENT = ROOT / "schemas" / "current"
REGISTRIES = ROOT / "registries"


def main() -> int:
    if not LEGACY.is_dir():
        raise SystemExit(f"missing immutable V1.0 schema directory: {LEGACY}")
    for destination in (V11, CURRENT, REGISTRIES):
        destination.mkdir(parents=True, exist_ok=True)
    _clean_json(V11)
    _clean_json(CURRENT)

    schemas = {
        path.name: _load(path) for path in sorted(LEGACY.glob("*.schema.json"))
    }
    for schema in schemas.values():
        _bump_schema(schema)
    schemas["constraint_evidence_package.schema.json"] = _constraint_schema()
    _upgrade_common(schemas["common_defs.schema.json"])
    _upgrade_frozen_candidate(schemas["frozen_candidate_contract.schema.json"])
    _upgrade_context(schemas["context_evidence_package.schema.json"])
    _upgrade_attestation(schemas["attestation_evidence_package.schema.json"])
    _upgrade_gates(schemas["gate_result_set.schema.json"])
    _upgrade_global_input(schemas["global_validator_input.schema.json"])
    _upgrade_calibration(schemas["calibration_artifact.schema.json"])
    _upgrade_decision(schemas["global_decision_package.schema.json"])
    _upgrade_certificate(schemas["terminology_certificate.schema.json"])
    _upgrade_tac(schemas["tac_occurrence_input.schema.json"])

    for name, schema in sorted(schemas.items()):
        _write_json(V11 / name, schema)
        _write_json(CURRENT / name, schema)
    _write_json(
        REGISTRIES / "feature_contract_v1.1.0.json",
        feature_registry_payload(),
    )
    _write_json(
        REGISTRIES / "gate_registry_v1.1.0.json",
        gate_registry_payload(),
    )
    _write_json(
        REGISTRIES / "schema_registry_v1.1.0.json",
        schema_registry_payload(),
    )

    # Flat V1.0 schema aliases are removed only after immutable copies exist.
    for path in (ROOT / "schemas").glob("*.schema.json"):
        path.unlink()
    print(f"generated {len(schemas)} V1.1 schemas and 3 registries")
    return 0


def _bump_schema(value: Any) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("$id"), str):
            value["$id"] = value["$id"].replace(
                "/terminology-contracts/v1/",
                "/terminology-contracts/v1.1/",
            )
        for key, child in value.items():
            if key == "schema_version" and isinstance(child, dict):
                if child.get("const") == "1.0.0":
                    child["const"] = PACKAGE_VERSION
            _bump_schema(child)
    elif isinstance(value, list):
        for child in value:
            _bump_schema(child)


def _upgrade_common(schema: dict[str, Any]) -> None:
    provenance = schema["$defs"]["provenance"]
    provenance["required"] = _append_unique(
        provenance["required"], "run_spec_id", "execution_config_sha256"
    )
    provenance["properties"]["run_spec_id"] = {
        "$ref": "#/$defs/identifier"
    }
    provenance["properties"]["execution_config_sha256"] = {
        "$ref": "#/$defs/sha256"
    }
    schema["$defs"]["nullableSha256"] = {
        "anyOf": [
            {"$ref": "#/$defs/sha256"},
            {"type": "null"},
        ]
    }
    evidence_types = schema["$defs"]["evidenceRef"]["properties"]["evidence_type"][
        "enum"
    ]
    schema["$defs"]["evidenceRef"]["properties"]["evidence_type"]["enum"] = (
        _append_unique(evidence_types, "CONSTRAINT_EVIDENCE", "COLLISION_INDEX")
    )


def _upgrade_frozen_candidate(schema: dict[str, Any]) -> None:
    schema["required"] = _append_unique(
        schema["required"], "input_contract_sha256", "binding_status"
    )
    schema["properties"]["input_contract_sha256"] = {
        "$ref": "common_defs.schema.json#/$defs/sha256"
    }
    schema["properties"]["binding_status"] = {
        "enum": ["COMPLETE", "LEGACY_INCOMPLETE"]
    }


def _upgrade_context(schema: dict[str, Any]) -> None:
    schema["properties"]["diagnostics"] = {
        "anyOf": [
            {"type": "null"},
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "replacement_rate": {
                        "$ref": "common_defs.schema.json#/$defs/score01"
                    },
                    "contrastive_boundary_support": {
                        "$ref": "common_defs.schema.json#/$defs/score01"
                    },
                },
            },
        ]
    }


def _upgrade_attestation(schema: dict[str, Any]) -> None:
    schema["properties"]["diagnostics"] = {
        "anyOf": [
            {"type": "null"},
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "strong_positive_cluster_count": {
                        "type": "integer",
                        "minimum": 0,
                    },
                    "conflict_ratio": {
                        "$ref": "common_defs.schema.json#/$defs/score01"
                    },
                },
            },
        ]
    }


def _upgrade_gates(schema: dict[str, Any]) -> None:
    observation = schema["properties"]["observations"]["items"]
    observation["properties"]["gate_id"]["enum"] = list(GATE_IDS)
    observation["properties"]["source_modules"] = {
        "type": "array",
        "minItems": 1,
        "uniqueItems": True,
        "items": {"enum": list(GATE_SOURCE_MODULES)},
    }
    schema["properties"]["observations"]["uniqueItems"] = True
    schema["properties"]["observations"]["minItems"] = 1
    schema["properties"]["observations"]["maxItems"] = len(GATE_IDS)
    schema["required"] = _append_unique(schema["required"], "binding_status")
    schema["properties"]["binding_status"] = {
        "enum": ["COMPLETE", "LEGACY_INCOMPLETE"]
    }


def _upgrade_global_input(schema: dict[str, Any]) -> None:
    schema["required"] = _append_unique(
        schema["required"],
        "effective_sense_contract",
        "frozen_candidate_contract",
        "constraint_evidence",
        "assembly_metadata",
    )
    for field, reference in (
        ("effective_sense_contract", "effective_sense_contract.schema.json"),
        ("frozen_candidate_contract", "frozen_candidate_contract.schema.json"),
        ("constraint_evidence", "constraint_evidence_package.schema.json"),
    ):
        schema["properties"][field] = {
            "anyOf": [{"$ref": reference}, {"type": "null"}]
        }
    schema["properties"]["assembly_metadata"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "assembler_id",
            "assembler_version",
            "assembled_at",
            "source_package_hashes",
            "binding_status",
        ],
        "properties": {
            "assembler_id": {
                "$ref": "common_defs.schema.json#/$defs/identifier"
            },
            "assembler_version": {
                "$ref": "common_defs.schema.json#/$defs/nonEmptyString"
            },
            "assembled_at": {
                "anyOf": [
                    {"$ref": "common_defs.schema.json#/$defs/dateTime"},
                    {"type": "null"},
                ]
            },
            "source_package_hashes": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "context_evidence_sha256",
                    "attestation_evidence_sha256",
                    "effective_sense_contract_sha256",
                    "frozen_candidate_contract_sha256",
                    "constraint_evidence_sha256",
                ],
                "properties": {
                    "context_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/sha256"
                    },
                    "attestation_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/sha256"
                    },
                    "effective_sense_contract_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                    "frozen_candidate_contract_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                    "constraint_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                },
            },
            "binding_status": {
                "enum": ["COMPLETE", "LEGACY_INCOMPLETE"]
            },
        },
    }


def _upgrade_calibration(schema: dict[str, Any]) -> None:
    schema["required"] = _append_unique(
        schema["required"], "verification_status", "numerical_tolerance"
    )
    schema["properties"]["feature_contract_version"]["const"] = PACKAGE_VERSION
    schema["properties"]["verification_status"] = {
        "enum": ["SEALED", "UNVERIFIED_LEGACY"]
    }
    schema["properties"]["numerical_tolerance"] = {
        "anyOf": [
            {"type": "number", "minimum": 0.0, "maximum": 1e-9},
            {"type": "null"},
        ]
    }
    operating_point = schema["properties"]["operating_point"]
    operating_point["required"] = _append_unique(
        operating_point["required"], "operating_point_id"
    )
    operating_point["properties"]["operating_point_id"] = {
        "anyOf": [
            {"$ref": "common_defs.schema.json#/$defs/identifier"},
            {"type": "null"},
        ]
    }
    strict_model = {
        "type": "object",
        "additionalProperties": False,
        "required": ["model_type", "parameters", "feature_names"],
        "properties": {
            "model_type": {"const": "LOGISTIC_REGRESSION"},
            "feature_names": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
            },
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["link_function", "intercept", "coefficients"],
                "properties": {
                    "link_function": {"const": "LOGIT"},
                    "intercept": {"type": "number"},
                    "coefficients": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                    },
                },
            },
        },
    }
    strict_results = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "development_sample_count",
            "validation_sample_count",
            "uncertainty_method",
            "selected_operating_point_id",
        ],
        "properties": {
            "development_sample_count": {"type": "integer", "minimum": 1},
            "validation_sample_count": {"type": "integer", "minimum": 1},
            "uncertainty_method": {
                "enum": [
                    "WILSON_SCORE",
                    "CLOPPER_PEARSON",
                    "BOOTSTRAP_PERCENTILE",
                ]
            },
            "selected_operating_point_id": {
                "$ref": "common_defs.schema.json#/$defs/identifier"
            },
        },
    }
    schema["allOf"] = [
        {
            "if": {
                "properties": {"verification_status": {"const": "SEALED"}},
                "required": ["verification_status"],
            },
            "then": {
                "properties": {
                    "numerical_tolerance": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1e-9,
                    },
                    "model": strict_model,
                    "calibration_results": strict_results,
                    "operating_point": {
                        "properties": {
                            "operating_point_id": {
                                "$ref": "common_defs.schema.json#/$defs/identifier"
                            }
                        }
                    },
                }
            },
        }
    ]


def _upgrade_decision(schema: dict[str, Any]) -> None:
    schema["required"] = _append_unique(schema["required"], "run_metadata")
    policy = schema["properties"]["decision_policy"]
    policy["required"] = _append_unique(
        policy["required"], "feature_contract_version"
    )
    policy["properties"]["feature_contract_version"] = {
        "const": PACKAGE_VERSION
    }
    schema["properties"]["run_metadata"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "binding_status",
            "global_run_id",
            "global_run_spec_id",
            "started_at",
            "completed_at",
            "engine_version",
            "execution_config_sha256",
            "feature_contract_version",
            "gate_policy_version",
            "input_package_hashes",
            "replay_spec_sha256",
        ],
        "properties": {
            "binding_status": {
                "enum": ["COMPLETE", "LEGACY_INCOMPLETE"]
            },
            "global_run_id": {
                "$ref": "common_defs.schema.json#/$defs/identifier"
            },
            "global_run_spec_id": {
                "$ref": "common_defs.schema.json#/$defs/identifier"
            },
            "started_at": {
                "anyOf": [
                    {"$ref": "common_defs.schema.json#/$defs/dateTime"},
                    {"type": "null"},
                ]
            },
            "completed_at": {
                "anyOf": [
                    {"$ref": "common_defs.schema.json#/$defs/dateTime"},
                    {"type": "null"},
                ]
            },
            "engine_version": {
                "$ref": "common_defs.schema.json#/$defs/nonEmptyString"
            },
            "execution_config_sha256": {
                "$ref": "common_defs.schema.json#/$defs/sha256"
            },
            "feature_contract_version": {"const": PACKAGE_VERSION},
            "gate_policy_version": {
                "$ref": "common_defs.schema.json#/$defs/nonEmptyString"
            },
            "input_package_hashes": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "global_validator_input_sha256",
                    "context_evidence_sha256",
                    "attestation_evidence_sha256",
                    "effective_sense_contract_sha256",
                    "frozen_candidate_contract_sha256",
                    "constraint_evidence_sha256",
                    "gate_result_sha256",
                ],
                "properties": {
                    "global_validator_input_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                    "context_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/sha256"
                    },
                    "attestation_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                    "effective_sense_contract_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                    "frozen_candidate_contract_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                    "constraint_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                    "gate_result_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                },
            },
            "replay_spec_sha256": {
                "$ref": "common_defs.schema.json#/$defs/sha256"
            },
        },
    }


def _upgrade_certificate(schema: dict[str, Any]) -> None:
    new_fields = (
        "binding_status",
        "attestation_evidence_refs",
        "threshold_version",
        "sense_inventory_version",
        "effective_sense_contract_sha256",
        "input_contract_sha256",
        "context_evidence_sha256",
        "attestation_evidence_sha256",
        "gate_result_sha256",
        "calibration_artifact_sha256",
        "global_validator_input_sha256",
        "frozen_candidate_contract_sha256",
        "constraint_evidence_sha256",
    )
    schema["required"] = _append_unique(schema["required"], *new_fields)
    props = schema["properties"]
    props["binding_status"] = {"enum": ["COMPLETE", "LEGACY_INCOMPLETE"]}
    props["attestation_evidence_refs"] = {
        "type": "array",
        "items": {"$ref": "common_defs.schema.json#/$defs/evidenceRef"},
    }
    props["threshold_version"] = {
        "$ref": "common_defs.schema.json#/$defs/nonEmptyString"
    }
    props["sense_inventory_version"] = {
        "$ref": "common_defs.schema.json#/$defs/nonEmptyString"
    }
    props["effective_sense_contract_sha256"] = {
        "$ref": "common_defs.schema.json#/$defs/sha256"
    }
    for name in (
        "input_contract_sha256",
        "context_evidence_sha256",
        "attestation_evidence_sha256",
        "gate_result_sha256",
        "calibration_artifact_sha256",
        "global_validator_input_sha256",
        "frozen_candidate_contract_sha256",
        "constraint_evidence_sha256",
    ):
        props[name] = {
            "$ref": "common_defs.schema.json#/$defs/nullableSha256"
        }


def _upgrade_tac(schema: dict[str, Any]) -> None:
    schema["required"] = _append_unique(schema["required"], "offset_unit")
    schema["properties"]["offset_unit"] = {"const": "UNICODE_CODEPOINT"}


def _constraint_schema() -> dict[str, Any]:
    identifier = {"$ref": "common_defs.schema.json#/$defs/identifier"}
    nullable_hash = {"$ref": "common_defs.schema.json#/$defs/nullableSha256"}
    evidence_ref = {"$ref": "common_defs.schema.json#/$defs/evidenceRef"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://thesis.local/terminology-contracts/v1.1/constraint_evidence_package.schema.json",
        "title": "Global Constraint Evidence Package V1",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_id",
            "schema_version",
            "candidate_key",
            "input_contract_sha256",
            "binding_status",
            "sense_review",
            "polysemy_resolution",
            "target_collision",
            "provenance",
            "integrity",
        ],
        "properties": {
            "schema_id": {"const": "ConstraintEvidencePackageV1"},
            "schema_version": {"const": PACKAGE_VERSION},
            "candidate_key": {
                "$ref": "common_defs.schema.json#/$defs/candidateKey"
            },
            "input_contract_sha256": {
                "$ref": "common_defs.schema.json#/$defs/sha256"
            },
            "binding_status": {"const": "COMPLETE"},
            "sense_review": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "status",
                    "effective_sense_contract_sha256",
                    "review_artifact_ref",
                ],
                "properties": {
                    "status": {"enum": ["VERIFIED", "UNVERIFIED"]},
                    "effective_sense_contract_sha256": nullable_hash,
                    "review_artifact_ref": {
                        "anyOf": [evidence_ref, {"type": "null"}]
                    },
                },
            },
            "polysemy_resolution": {
                "type": "object",
                "additionalProperties": False,
                "required": ["status", "related_sense_ids", "authority_ref"],
                "properties": {
                    "status": {
                        "enum": [
                            "RESOLVED_SINGLE",
                            "RESOLVED_SPLIT",
                            "UNRESOLVED",
                        ]
                    },
                    "related_sense_ids": {
                        "type": "array",
                        "items": identifier,
                        "uniqueItems": True,
                    },
                    "authority_ref": {
                        "anyOf": [evidence_ref, {"type": "null"}]
                    },
                },
            },
            "target_collision": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "status",
                    "collision_index_sha256",
                    "conflicting_candidate_keys",
                    "evidence_refs",
                ],
                "properties": {
                    "status": {"enum": ["CLEAR", "COLLISION", "UNJUDGEABLE"]},
                    "collision_index_sha256": nullable_hash,
                    "conflicting_candidate_keys": {
                        "type": "array",
                        "items": {
                            "$ref": "common_defs.schema.json#/$defs/candidateKey"
                        },
                        "uniqueItems": True,
                    },
                    "evidence_refs": {
                        "type": "array",
                        "items": evidence_ref,
                        "uniqueItems": True,
                    },
                },
            },
            "provenance": {"$ref": "common_defs.schema.json#/$defs/provenance"},
            "integrity": {"$ref": "common_defs.schema.json#/$defs/integrity"},
        },
    }


def _append_unique(values: list[str], *items: str) -> list[str]:
    result = list(values)
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _clean_json(path: Path) -> None:
    for child in path.glob("*.json"):
        child.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
