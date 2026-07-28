from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .bindings import calculate_replay_spec_sha256
from .canonical import canonical_bytes
from .integrity import canonical_sha256, seal_self_hash, strict_json_loads
from .registries import LEGACY_VERSION, PACKAGE_VERSION


MIGRATION_TOOL_VERSION = "1.0.0"


class MigrationError(ValueError):
    pass


@dataclass(frozen=True)
class MigrationResult:
    payload: dict[str, Any]
    report: dict[str, Any]


_GATE_SOURCE_DEFAULTS: dict[str, list[str]] = {
    "input_contract_mismatch": ["CONTRACT"],
    "sense_definition_unverified": ["SENSE"],
    "unresolved_polysemy": ["SENSE"],
    "concept_mismatch": ["C", "E"],
    "wrong_sense": ["C"],
    "contradiction": ["C", "E"],
    "target_collision": ["GLOBAL"],
    "judge_disagreement": ["C", "E"],
    "insufficient_evidence": ["C", "E"],
    "missing_contrastive_context": ["C"],
    "incomplete_context_type_coverage": ["C"],
    "attestation_unjudgeable": ["E"],
}


def migrate_v1_0_to_v1_1(payload: Mapping[str, Any]) -> MigrationResult:
    source = copy.deepcopy(dict(payload))
    source_version = source.get("schema_version")
    if source_version == PACKAGE_VERSION:
        raise MigrationError("payload is already V1.1; migration is not idempotent")
    if source_version != LEGACY_VERSION:
        raise MigrationError(
            f"unsupported source schema_version: {source_version!r}"
        )
    if not isinstance(source.get("schema_id"), str):
        raise MigrationError("schema_id is required")

    source_sha = canonical_sha256(source)
    fields_added: list[str] = []
    fields_renamed: list[dict[str, str]] = []
    warnings: list[str] = []
    target = _migrate_payload(
        source,
        fields_added=fields_added,
        fields_renamed=fields_renamed,
        warnings=warnings,
        path="$",
    )
    target_sha = canonical_sha256(target)
    report = {
        "source_schema_id": source["schema_id"],
        "source_schema_version": LEGACY_VERSION,
        "target_schema_version": PACKAGE_VERSION,
        "migration_tool_version": MIGRATION_TOOL_VERSION,
        "fields_added": sorted(set(fields_added)),
        "fields_renamed": sorted(
            fields_renamed, key=lambda item: (item["from"], item["to"])
        ),
        "warnings": sorted(set(warnings)),
        "source_sha256": source_sha,
        "target_sha256": target_sha,
    }
    return MigrationResult(payload=target, report=report)


def migrate_file(
    source_path: Path,
    target_path: Path,
    report_path: Path,
) -> MigrationResult:
    try:
        payload = strict_json_loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise MigrationError(f"cannot load migration source {source_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MigrationError("migration source must contain a JSON object")
    result = migrate_v1_0_to_v1_1(payload)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(_pretty_json_bytes(result.payload))
    report_path.write_bytes(_pretty_json_bytes(result.report))
    return result


def _migrate_payload(
    payload: dict[str, Any],
    *,
    fields_added: list[str],
    fields_renamed: list[dict[str, str]],
    warnings: list[str],
    path: str,
) -> dict[str, Any]:
    sid = payload.get("schema_id")
    result = copy.deepcopy(payload)
    result["schema_version"] = PACKAGE_VERSION

    _migrate_provenance_objects(result, fields_added=fields_added, path=path)

    if sid == "FrozenCandidateContractV1":
        _add(
            result,
            "input_contract_sha256",
            payload.get("integrity", {}).get("self_sha256"),
            fields_added,
            path,
        )
        _add(
            result,
            "binding_status",
            "LEGACY_INCOMPLETE",
            fields_added,
            path,
        )
    elif sid == "ContextEvidencePackageV1":
        _add(result, "diagnostics", None, fields_added, path)
    elif sid == "AttestationEvidencePackageV1":
        _add(result, "diagnostics", None, fields_added, path)
    elif sid == "GateResultSetV1":
        _add(
            result,
            "binding_status",
            "LEGACY_INCOMPLETE",
            fields_added,
            path,
        )
        _add(
            result,
            "gate_policy_artifact_sha256",
            None,
            fields_added,
            path,
        )
        for index, observation in enumerate(result.get("observations", [])):
            if not isinstance(observation, dict):
                continue
            gate_id = str(observation.get("gate_id", "")).casefold()
            observation["gate_id"] = gate_id
            _add(
                observation,
                "source_modules",
                list(_GATE_SOURCE_DEFAULTS.get(gate_id, ["CONTRACT"])),
                fields_added,
                f"{path}.observations[{index}]",
            )
    elif sid == "GlobalValidatorInputV1":
        for field in ("context_evidence", "attestation_evidence"):
            nested = result.get(field)
            if isinstance(nested, dict):
                result[field] = _migrate_payload(
                    nested,
                    fields_added=fields_added,
                    fields_renamed=fields_renamed,
                    warnings=warnings,
                    path=f"{path}.{field}",
                )
        migrated_probes = []
        for index, probe in enumerate(result.get("optional_probes", [])):
            if isinstance(probe, dict):
                probe = _migrate_payload(
                    probe,
                    fields_added=fields_added,
                    fields_renamed=fields_renamed,
                    warnings=warnings,
                    path=f"{path}.optional_probes[{index}]",
                )
            migrated_probes.append(probe)
        result["optional_probes"] = migrated_probes
        context_sha = _nested_self_hash(result.get("context_evidence"))
        attestation_sha = _nested_self_hash(result.get("attestation_evidence"))
        _add(result, "effective_sense_contract", None, fields_added, path)
        _add(result, "frozen_candidate_contract", None, fields_added, path)
        _add(result, "constraint_evidence", None, fields_added, path)
        _add(
            result,
            "assembly_metadata",
            {
                "assembler_id": "terminology-contracts-migration",
                "assembler_version": PACKAGE_VERSION,
                "assembled_at": _nested_started_at(result.get("context_evidence")),
                "binding_status": "LEGACY_INCOMPLETE",
                "source_package_hashes": {
                    "context_evidence_sha256": context_sha,
                    "attestation_evidence_sha256": attestation_sha,
                    "effective_sense_contract_sha256": None,
                    "frozen_candidate_contract_sha256": None,
                    "constraint_evidence_sha256": None,
                },
            },
            fields_added,
            path,
        )
    elif sid == "CalibrationArtifactV1":
        result["feature_contract_version"] = PACKAGE_VERSION
        warnings.append(
            "feature_contract_version advanced to V1.1 for schema compatibility; model parameters remain unchanged."
        )
        _add(
            result,
            "verification_status",
            "UNVERIFIED_LEGACY",
            fields_added,
            path,
        )
        _add(result, "numerical_tolerance", None, fields_added, path)
        _add(
            result,
            "gate_policy_artifact_sha256",
            None,
            fields_added,
            path,
        )
        _add(result, "threshold_stability", None, fields_added, path)
        operating_point = result.get("operating_point")
        if isinstance(operating_point, dict):
            _add(
                operating_point,
                "operating_point_id",
                None,
                fields_added,
                f"{path}.operating_point",
            )
        warnings.append(
            "Legacy calibration migrated structurally but remains ineligible for frozen mode until independently verified."
        )
    elif sid == "GlobalDecisionPackageV1":
        gates = result.get("gate_results")
        if isinstance(gates, dict):
            result["gate_results"] = _migrate_payload(
                gates,
                fields_added=fields_added,
                fields_renamed=fields_renamed,
                warnings=warnings,
                path=f"{path}.gate_results",
            )
        policy = result.get("decision_policy")
        if isinstance(policy, dict):
            _add(
                policy,
                "feature_contract_version",
                PACKAGE_VERSION,
                fields_added,
                f"{path}.decision_policy",
            )
            _add(
                policy,
                "gate_policy_artifact_sha256",
                None,
                fields_added,
                f"{path}.decision_policy",
            )
        execution_config_sha256 = canonical_sha256(
            {
                "migration_tool_version": MIGRATION_TOOL_VERSION,
                "source_schema_id": sid,
                "source_self_sha256": payload.get("integrity", {}).get(
                    "self_sha256"
                ),
            }
        )
        source_hash = payload.get("integrity", {}).get("self_sha256")
        run_metadata = {
            "binding_status": "LEGACY_INCOMPLETE",
            "global_run_id": f"migrated-{str(source_hash)[:16]}",
            "global_run_spec_id": f"migrated-spec-{str(source_hash)[:16]}",
            "started_at": None,
            "completed_at": None,
            "engine_version": f"terminology-contracts-migration-{MIGRATION_TOOL_VERSION}",
            "execution_config_sha256": execution_config_sha256,
            "feature_contract_version": PACKAGE_VERSION,
            "gate_policy_version": result.get("gate_results", {}).get(
                "gate_policy_version"
            ),
            "gate_policy_artifact_sha256": None,
            "input_package_hashes": {
                "global_validator_input_sha256": None,
                "context_evidence_sha256": result.get(
                    "context_evidence_sha256"
                ),
                "attestation_evidence_sha256": result.get(
                    "attestation_evidence_sha256"
                ),
                "effective_sense_contract_sha256": None,
                "frozen_candidate_contract_sha256": None,
                "constraint_evidence_sha256": None,
                "gate_result_sha256": _nested_self_hash(
                    result.get("gate_results")
                ),
                "gate_policy_artifact_sha256": None,
            },
            "replay_spec_sha256": "0" * 64,
        }
        replay_value = copy.deepcopy(result)
        replay_value["run_metadata"] = run_metadata
        run_metadata["replay_spec_sha256"] = calculate_replay_spec_sha256(
            replay_value
        )
        _add(
            result,
            "run_metadata",
            run_metadata,
            fields_added,
            path,
        )
        warnings.append(
            "Legacy decision has no original GlobalValidatorInput artifact binding."
        )
    elif sid == "TerminologyCertificateV1":
        key = result.get("candidate_key", {})
        summary = result.get("evidence_summary", {})
        _add(result, "binding_status", "LEGACY_INCOMPLETE", fields_added, path)
        _add(result, "attestation_evidence_refs", [], fields_added, path)
        _add(result, "threshold_version", "MIGRATED_UNKNOWN", fields_added, path)
        _add(
            result,
            "sense_inventory_version",
            key.get("sense_inventory_version"),
            fields_added,
            path,
        )
        _add(
            result,
            "effective_sense_contract_sha256",
            key.get("effective_sense_contract_sha256"),
            fields_added,
            path,
        )
        _add(result, "input_contract_sha256", None, fields_added, path)
        _add(
            result,
            "context_evidence_sha256",
            summary.get("context_evidence_sha256"),
            fields_added,
            path,
        )
        _add(
            result,
            "attestation_evidence_sha256",
            summary.get("attestation_evidence_sha256"),
            fields_added,
            path,
        )
        _add(result, "gate_result_sha256", None, fields_added, path)
        _add(result, "calibration_artifact_sha256", None, fields_added, path)
        _add(result, "global_validator_input_sha256", None, fields_added, path)
        _add(result, "frozen_candidate_contract_sha256", None, fields_added, path)
        _add(result, "constraint_evidence_sha256", None, fields_added, path)
        _add(result, "gate_policy_artifact_sha256", None, fields_added, path)
        warnings.append(
            "Legacy certificate remains non-issuable until input, gate, and calibration bindings are supplied from verified artifacts."
        )
    elif sid == "TACOccurrenceInputV1":
        _add(result, "offset_unit", "UNICODE_CODEPOINT", fields_added, path)
        certificate = result.get("certificate")
        if isinstance(certificate, dict):
            result["certificate"] = _migrate_payload(
                certificate,
                fields_added=fields_added,
                fields_renamed=fields_renamed,
                warnings=warnings,
                path=f"{path}.certificate",
            )

    return seal_self_hash(result)


def _migrate_provenance_objects(
    value: Any, *, fields_added: list[str], path: str
) -> None:
    if isinstance(value, dict):
        for key, child in list(value.items()):
            child_path = f"{path}.{key}"
            if key in {"provenance", "input_provenance"} and isinstance(child, dict):
                run_id = str(child.get("run_id", "legacy-run"))
                config_source = {
                    "component_id": child.get("component_id"),
                    "component_version": child.get("component_version"),
                    "policy_version": child.get("policy_version"),
                    "prompt_hashes": child.get("prompt_hashes", {}),
                    "model_routes": child.get("model_routes", []),
                    "source_artifact_hashes": child.get(
                        "source_artifact_hashes", {}
                    ),
                }
                _add(
                    child,
                    "run_spec_id",
                    f"{run_id}-spec-migrated-v1-1",
                    fields_added,
                    child_path,
                )
                _add(
                    child,
                    "execution_config_sha256",
                    canonical_sha256(config_source),
                    fields_added,
                    child_path,
                )
            _migrate_provenance_objects(
                child, fields_added=fields_added, path=child_path
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _migrate_provenance_objects(
                child, fields_added=fields_added, path=f"{path}[{index}]"
            )


def _add(
    row: dict[str, Any],
    key: str,
    value: Any,
    fields_added: list[str],
    path: str,
) -> None:
    if key not in row:
        row[key] = value
        fields_added.append(f"{path}.{key}")


def _nested_self_hash(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    integrity = value.get("integrity")
    return integrity.get("self_sha256") if isinstance(integrity, dict) else None


def _nested_started_at(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    provenance = value.get("provenance")
    return provenance.get("started_at") if isinstance(provenance, dict) else None


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def deterministic_payload_bytes(value: Mapping[str, Any]) -> bytes:
    return canonical_bytes(value)
