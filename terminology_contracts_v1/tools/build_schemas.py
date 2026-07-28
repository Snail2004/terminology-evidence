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
    _upgrade_common(schemas["common_defs.schema.json"])
    _upgrade_frozen_candidate(schemas["frozen_candidate_contract.schema.json"])
    _upgrade_context(schemas["context_evidence_package.schema.json"])
    _upgrade_attestation(schemas["attestation_evidence_package.schema.json"])
    _upgrade_gates(schemas["gate_result_set.schema.json"])
    _upgrade_global_input(schemas["global_validator_input.schema.json"])
    _upgrade_calibration(schemas["calibration_artifact.schema.json"])
    _upgrade_decision(schemas["global_decision_package.schema.json"])
    _upgrade_certificate(schemas["terminology_certificate.schema.json"])

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


def _upgrade_frozen_candidate(schema: dict[str, Any]) -> None:
    schema["required"] = _append_unique(
        schema["required"], "input_contract_sha256"
    )
    schema["properties"]["input_contract_sha256"] = {
        "$ref": "common_defs.schema.json#/$defs/sha256"
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


def _upgrade_global_input(schema: dict[str, Any]) -> None:
    schema["required"] = _append_unique(schema["required"], "assembly_metadata")
    schema["properties"]["assembly_metadata"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "assembler_id",
            "assembler_version",
            "assembled_at",
            "source_package_hashes",
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
                ],
                "properties": {
                    "context_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/sha256"
                    },
                    "attestation_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/sha256"
                    },
                },
            },
        },
    }


def _upgrade_calibration(schema: dict[str, Any]) -> None:
    schema["required"] = _append_unique(
        schema["required"], "verification_status"
    )
    schema["properties"]["feature_contract_version"]["const"] = PACKAGE_VERSION
    schema["properties"]["verification_status"] = {
        "enum": ["SEALED", "UNVERIFIED_LEGACY"]
    }
    schema["properties"]["model"]["properties"]["model_type"]["enum"] = [
        "RULE_SET",
        "LOGISTIC_REGRESSION",
        "ISOTONIC",
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
                ],
                "properties": {
                    "global_validator_input_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/nullableSha256"
                    },
                    "context_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/sha256"
                    },
                    "attestation_evidence_sha256": {
                        "$ref": "common_defs.schema.json#/$defs/sha256"
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
    ):
        props[name] = {
            "$ref": "common_defs.schema.json#/$defs/nullableSha256"
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
