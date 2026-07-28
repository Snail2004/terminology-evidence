from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, RefResolver

from .canonical import verify_self_sha256

SCHEMA_FILES = {
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


class ContractValidationError(ValueError):
    pass


def _load_schemas(schema_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    store: dict[str, Any] = {}
    for path in schema_dir.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        loaded[path.name] = schema
        if "$id" in schema:
            store[schema["$id"]] = schema
        store[path.name] = schema
        store[path.resolve().as_uri()] = schema
    return loaded, store


def _schema_validate(instance: dict[str, Any], schema_dir: Path) -> list[str]:
    schema_id = instance.get("schema_id")
    filename = SCHEMA_FILES.get(schema_id)
    if not filename:
        return [f"unsupported schema_id: {schema_id!r}"]
    loaded, store = _load_schemas(schema_dir)
    schema = loaded[filename]
    resolver = RefResolver(base_uri=(schema_dir.resolve().as_uri() + "/"), referrer=schema, store=store)
    validator = Draft202012Validator(schema, resolver=resolver, format_checker=FormatChecker())
    errors = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        location = ".".join(str(p) for p in error.absolute_path) or "$"
        errors.append(f"{location}: {error.message}")
    return errors


def _same_candidate_key(a: Any, b: Any) -> bool:
    return isinstance(a, dict) and isinstance(b, dict) and a == b


def _semantic_validate(instance: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sid = instance.get("schema_id")

    if not verify_self_sha256(instance):
        errors.append("integrity.self_sha256 mismatch")

    if sid == "FrozenCandidateContractV1":
        if instance.get("surfaces", {}).get("canonical_vi") != instance.get("candidate_key", {}).get("candidate_vi"):
            errors.append("surfaces.canonical_vi must equal candidate_key.candidate_vi")

    elif sid == "ContextEvidencePackageV1":
        f = instance.get("features", {})
        if f.get("pass_count", 0) + f.get("minor_count", 0) + f.get("fail_count", 0) != f.get("valid_context_count"):
            errors.append("pass_count + minor_count + fail_count must equal valid_context_count")
        if all(isinstance(f.get(k), (int, float)) for k in ("C_min", "C_max", "C_range")):
            if abs((f["C_max"] - f["C_min"]) - f["C_range"]) > 1e-9:
                errors.append("C_range must equal C_max - C_min")
        if instance.get("selector_mode") == "FROZEN_HUMAN_REVIEWED_SELECTION" and not instance.get("review_artifact_sha256"):
            errors.append("frozen selector mode requires review_artifact_sha256")

    elif sid == "AttestationEvidencePackageV1":
        if instance.get("local_status") == "ATTESTED" and not instance.get("accepted_evidence_refs"):
            errors.append("ATTESTED requires at least one accepted evidence reference")

    elif sid == "GlobalValidatorInputV1":
        key = instance.get("candidate_key")
        input_hash = instance.get("input_contract_sha256")
        for name in ("context_evidence", "attestation_evidence"):
            pkg = instance.get(name, {})
            if not _same_candidate_key(key, pkg.get("candidate_key")):
                errors.append(f"{name}.candidate_key mismatch")
            if input_hash != pkg.get("input_contract_sha256"):
                errors.append(f"{name}.input_contract_sha256 mismatch")
            errors.extend(f"{name}: {e}" for e in _semantic_validate(pkg))
        for index, pkg in enumerate(instance.get("optional_probes", [])):
            if not _same_candidate_key(key, pkg.get("candidate_key")):
                errors.append(f"optional_probes[{index}].candidate_key mismatch")
            if input_hash != pkg.get("input_contract_sha256"):
                errors.append(f"optional_probes[{index}].input_contract_sha256 mismatch")
            errors.extend(f"optional_probes[{index}]: {e}" for e in _semantic_validate(pkg))

    elif sid == "GateResultSetV1":
        for index, obs in enumerate(instance.get("observations", [])):
            if obs.get("triggered") is False and obs.get("action") != "NONE":
                errors.append(f"observations[{index}]: non-triggered gate must use action NONE")
            if obs.get("triggered") is True and obs.get("action") == "NONE":
                errors.append(f"observations[{index}]: triggered gate cannot use action NONE")

    elif sid == "GlobalDecisionPackageV1":
        gates = instance.get("gate_results", {})
        if not _same_candidate_key(instance.get("candidate_key"), gates.get("candidate_key")):
            errors.append("gate_results.candidate_key mismatch")
        if instance.get("input_contract_sha256") != gates.get("input_contract_sha256"):
            errors.append("gate_results.input_contract_sha256 mismatch")
        errors.extend(f"gate_results: {e}" for e in _semantic_validate(gates))
        policy = instance.get("decision_policy", {})
        decision = instance.get("decision")
        score = instance.get("approval_score")
        threshold = policy.get("threshold")
        fatal_actions = {
            obs.get("action") for obs in gates.get("observations", []) if obs.get("triggered")
        }
        if policy.get("mode") == "DEVELOPMENT_HEURISTIC" and decision == "AUTO_APPROVED":
            errors.append("DEVELOPMENT_HEURISTIC cannot emit AUTO_APPROVED")
        if policy.get("mode") == "FROZEN_CALIBRATED":
            if not policy.get("calibration_artifact_sha256") or threshold is None:
                errors.append("FROZEN_CALIBRATED requires calibration artifact and threshold")
        if decision == "AUTO_APPROVED":
            if score is None or threshold is None or score < threshold:
                errors.append("AUTO_APPROVED requires approval_score >= threshold")
            if fatal_actions & {"FATAL_REJECT", "FATAL_SPLIT", "ESCALATE_HUMAN", "CAP_PROVISIONAL"}:
                errors.append("AUTO_APPROVED is incompatible with triggered blocking gates")
        if decision == "REJECTED" and "FATAL_REJECT" not in fatal_actions:
            errors.append("REJECTED requires a triggered FATAL_REJECT gate")
        if decision == "SPLIT_REQUIRED" and "FATAL_SPLIT" not in fatal_actions:
            errors.append("SPLIT_REQUIRED requires a triggered FATAL_SPLIT gate")

    elif sid == "TerminologyCertificateV1":
        if instance.get("status") not in {"AUTO_APPROVED", "PROVISIONAL"}:
            errors.append("certificate status must be AUTO_APPROVED or PROVISIONAL")

    return errors


def validate_instance(instance: dict[str, Any], schema_dir: Path) -> list[str]:
    return _schema_validate(instance, schema_dir) + _semantic_validate(instance)


def validate_file(path: Path, schema_dir: Path) -> list[str]:
    try:
        instance = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - CLI guard
        return [f"cannot read JSON: {exc}"]
    return validate_instance(instance, schema_dir)
