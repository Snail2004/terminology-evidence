from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .canonical import verify_self_sha256
from .calibration import CalibrationVerificationError, verify_calibration_artifact
from .integrity import IntegrityError, load_verified_json_artifact
from .registries import (
    CANDIDATE_JOIN_FIELDS,
    CORE_FEATURES,
    FEATURE_CONTRACT_VERSION,
    GATE_ACTION_PRECEDENCE,
    GATE_IDS,
    GATE_SOURCE_MODULES,
    LEGACY_VERSION,
    PACKAGE_VERSION,
    SCHEMA_FILES,
    known_feature_names,
    load_registry,
)


class ContractValidationError(ValueError):
    pass


def resolve_schema_dir(schema_dir: Path, schema_version: str) -> Path:
    """Resolve a package schema root without silently treating V1.0 as V1.1."""
    schema_dir = schema_dir.resolve()
    if schema_dir.name in {"v1.0.0", "v1.1.0", "current"}:
        return schema_dir
    if schema_version == PACKAGE_VERSION:
        current = schema_dir / "current"
        return current if current.is_dir() else schema_dir / "v1.1.0"
    if schema_version == LEGACY_VERSION:
        return schema_dir / "legacy" / "v1.0.0"
    raise ContractValidationError(
        f"unsupported schema version: {schema_version!r}"
    )


def _load_schemas(
    schema_dir: Path,
) -> tuple[dict[str, dict[str, Any]], Registry]:
    loaded: dict[str, dict[str, Any]] = {}
    registry = Registry()
    for path in schema_dir.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        loaded[path.name] = schema
        resource = Resource.from_contents(schema)
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
        registry = registry.with_resource(path.resolve().as_uri(), resource)
    return loaded, registry


def schema_validate_instance(
    instance: Mapping[str, Any], schema_dir: Path
) -> list[str]:
    if not isinstance(instance, Mapping):
        return ["$: payload must be an object"]
    schema_id = instance.get("schema_id")
    filename = SCHEMA_FILES.get(schema_id)
    if filename is None:
        return [f"unsupported schema_id: {schema_id!r}"]
    schema_version = instance.get("schema_version")
    try:
        resolved = resolve_schema_dir(schema_dir, schema_version)
    except ContractValidationError as exc:
        return [str(exc)]
    loaded, registry = _load_schemas(resolved)
    schema = loaded.get(filename)
    if schema is None:
        return [f"missing schema file: {resolved / filename}"]
    validator = Draft202012Validator(
        schema, registry=registry, format_checker=FormatChecker()
    )
    errors: list[str] = []
    for error in sorted(
        validator.iter_errors(instance),
        key=lambda item: (list(item.absolute_path), item.message),
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append(f"{location}: {error.message}")
    return errors


def validate_instance(
    instance: dict[str, Any],
    schema_dir: Path,
    *,
    calibration_path: Path | None = None,
    feature_registry_path: Path | None = None,
    expected_calibration_self_sha256: str | None = None,
    allow_legacy_migration: bool = False,
) -> list[str]:
    errors = schema_validate_instance(instance, schema_dir)
    if errors:
        return errors + _safe_semantic_errors(
            instance,
            schema_dir=schema_dir,
            calibration_path=calibration_path,
            feature_registry_path=feature_registry_path,
            expected_calibration_self_sha256=expected_calibration_self_sha256,
            allow_legacy_migration=allow_legacy_migration,
        )
    errors.extend(
        _safe_semantic_errors(
            instance,
            schema_dir=schema_dir,
            calibration_path=calibration_path,
            feature_registry_path=feature_registry_path,
            expected_calibration_self_sha256=expected_calibration_self_sha256,
            allow_legacy_migration=allow_legacy_migration,
        )
    )
    return errors


def validate_file(
    path: Path,
    schema_dir: Path,
    *,
    calibration_path: Path | None = None,
    feature_registry_path: Path | None = None,
    expected_calibration_self_sha256: str | None = None,
    allow_legacy_migration: bool = False,
) -> list[str]:
    try:
        instance = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"cannot read JSON: {exc}"]
    if not isinstance(instance, dict):
        return ["$: payload must be an object"]
    if calibration_path is None:
        calibration_path = _sibling_calibration_path(path, instance)
    if feature_registry_path is None:
        feature_registry_path = _default_feature_registry(schema_dir)
    return validate_instance(
        instance,
        schema_dir,
        calibration_path=calibration_path,
        feature_registry_path=feature_registry_path,
        expected_calibration_self_sha256=expected_calibration_self_sha256,
        allow_legacy_migration=allow_legacy_migration,
    )


def _safe_semantic_errors(instance: Mapping[str, Any], **kwargs: Any) -> list[str]:
    try:
        return _semantic_validate(instance, **kwargs)
    except Exception as exc:  # Never hide a malformed payload behind a traceback.
        return [f"semantic validator error: {exc}"]


def _semantic_validate(
    instance: Mapping[str, Any],
    *,
    schema_dir: Path,
    calibration_path: Path | None,
    feature_registry_path: Path | None,
    expected_calibration_self_sha256: str | None,
    allow_legacy_migration: bool,
) -> list[str]:
    errors: list[str] = []
    schema_id = instance.get("schema_id")
    version = instance.get("schema_version")
    if version not in {LEGACY_VERSION, PACKAGE_VERSION}:
        return errors
    if not verify_self_sha256(dict(instance)):
        errors.append("integrity.self_sha256 mismatch")

    if schema_id == "FrozenCandidateContractV1":
        _validate_frozen_candidate(instance, errors)
    elif schema_id == "ContextEvidencePackageV1":
        _validate_context(instance, errors)
    elif schema_id == "AttestationEvidencePackageV1":
        _validate_attestation(instance, errors)
    elif schema_id == "GlobalValidatorInputV1":
        _validate_global_input(instance, errors)
    elif schema_id == "GateResultSetV1":
        _validate_gates(instance, errors)
    elif schema_id == "CalibrationArtifactV1":
        _validate_calibration_structural(
            instance, errors, allow_legacy_migration=allow_legacy_migration
        )
    elif schema_id == "GlobalDecisionPackageV1":
        _validate_decision(
            instance,
            errors,
            schema_dir=schema_dir,
            calibration_path=calibration_path,
            feature_registry_path=feature_registry_path,
            expected_calibration_self_sha256=expected_calibration_self_sha256,
            allow_legacy_migration=allow_legacy_migration,
        )
    elif schema_id == "TerminologyCertificateV1":
        _validate_certificate(instance, errors, allow_legacy_migration)
    elif schema_id == "TACOccurrenceInputV1":
        _validate_tac(instance, errors, allow_legacy_migration)

    return errors


def _validate_frozen_candidate(value: Mapping[str, Any], errors: list[str]) -> None:
    surfaces = value.get("surfaces", {})
    key = value.get("candidate_key", {})
    if surfaces.get("canonical_vi") != key.get("candidate_vi"):
        errors.append("surfaces.canonical_vi must equal candidate_key.candidate_vi")
    # input_contract_sha256 is a package-level join key.  It is deliberately
    # separate from self_sha256 so the binding does not become recursive.
    if value.get("schema_version") == PACKAGE_VERSION and not value.get(
        "input_contract_sha256"
    ):
        errors.append("V1.1 frozen candidate requires input_contract_sha256")


def _validate_context(value: Mapping[str, Any], errors: list[str]) -> None:
    features = value.get("features", {})
    counts = tuple(features.get(name) for name in ("pass_count", "minor_count", "fail_count"))
    valid_count = features.get("valid_context_count")
    if all(isinstance(item, int) and not isinstance(item, bool) for item in counts) and isinstance(valid_count, int):
        if sum(counts) != valid_count:
            errors.append(
                "pass_count + minor_count + fail_count must equal valid_context_count"
            )
    if all(isinstance(features.get(name), (int, float)) for name in ("C_min", "C_max", "C_range")):
        if abs((features["C_max"] - features["C_min"]) - features["C_range"]) > 1e-9:
            errors.append("C_range must equal C_max - C_min")
    flags = _flag_codes(value.get("flags"))
    if value.get("contrastive_status") == "ABSENT" and "missing_contrastive_context" not in flags:
        errors.append("ABSENT contrastive_status requires missing_contrastive_context flag")
    if (
        isinstance(features.get("required_context_type_coverage"), (int, float))
        and features["required_context_type_coverage"] < 1.0
        and "incomplete_context_type_coverage" not in flags
    ):
        errors.append(
            "incomplete required context coverage requires incomplete_context_type_coverage flag"
        )
    if value.get("selector_mode") == "FROZEN_HUMAN_REVIEWED_SELECTION" and not value.get(
        "review_artifact_sha256"
    ):
        errors.append("frozen selector mode requires review_artifact_sha256")


def _validate_attestation(value: Mapping[str, Any], errors: list[str]) -> None:
    if value.get("local_status") == "ATTESTED" and not value.get(
        "accepted_evidence_refs"
    ):
        errors.append("ATTESTED requires at least one accepted evidence reference")
    if value.get("local_status") == "ATTESTATION_UNJUDGEABLE" and value.get(
        "accepted_evidence_refs"
    ):
        errors.append(
            "ATTESTATION_UNJUDGEABLE cannot claim accepted evidence refs"
        )


def _validate_global_input(value: Mapping[str, Any], errors: list[str]) -> None:
    key = value.get("candidate_key")
    input_hash = value.get("input_contract_sha256")
    for name in ("context_evidence", "attestation_evidence"):
        package = value.get(name, {})
        if isinstance(package, dict) and not verify_self_sha256(package):
            errors.append(f"{name}.integrity.self_sha256 mismatch")
        if not _same_candidate_key(key, package.get("candidate_key")):
            errors.append(f"{name}.candidate_key mismatch")
        if input_hash != package.get("input_contract_sha256"):
            errors.append(f"{name}.input_contract_sha256 mismatch")
    assembly = value.get("assembly_metadata")
    if isinstance(assembly, Mapping):
        hashes = assembly.get("source_package_hashes", {})
        for name, package_name in (
            ("context_evidence_sha256", "context_evidence"),
            ("attestation_evidence_sha256", "attestation_evidence"),
        ):
            expected = _self_hash(value.get(package_name))
            if expected is not None and hashes.get(name) != expected:
                errors.append(f"assembly_metadata.{name} mismatch")
    for index, probe in enumerate(value.get("optional_probes", [])):
        if isinstance(probe, dict) and not verify_self_sha256(probe):
            errors.append(f"optional_probes[{index}].integrity.self_sha256 mismatch")
        if not _same_candidate_key(key, probe.get("candidate_key")):
            errors.append(f"optional_probes[{index}].candidate_key mismatch")
        if input_hash != probe.get("input_contract_sha256"):
            errors.append(f"optional_probes[{index}].input_contract_sha256 mismatch")


def _validate_gates(value: Mapping[str, Any], errors: list[str]) -> None:
    observations = value.get("observations", [])
    for index, observation in enumerate(observations):
        gate_id = observation.get("gate_id")
        if gate_id not in GATE_IDS:
            errors.append(f"observations[{index}].gate_id is not registered")
        if observation.get("triggered") is False and observation.get("action") != "NONE":
            errors.append(
                f"observations[{index}]: non-triggered gate must use action NONE"
            )
        if observation.get("triggered") is True and observation.get("action") == "NONE":
            errors.append(
                f"observations[{index}]: triggered gate cannot use action NONE"
            )
        modules = observation.get("source_modules", [])
        if any(module not in GATE_SOURCE_MODULES for module in modules):
            errors.append(f"observations[{index}].source_modules contains unknown module")


def _validate_calibration_structural(
    value: Mapping[str, Any],
    errors: list[str],
    *,
    allow_legacy_migration: bool,
) -> None:
    if value.get("schema_version") == PACKAGE_VERSION:
        for field in ("development_dataset_sha256", "validation_dataset_sha256"):
            if not _is_nonzero_sha256(value.get(field)):
                errors.append(f"{field} must bind a nonzero SHA-256 artifact")
        status = value.get("verification_status")
        if status == "UNVERIFIED_LEGACY" and not allow_legacy_migration:
            errors.append(
                "UNVERIFIED_LEGACY calibration is not eligible for release/frozen mode"
            )
        if status == "SEALED" and value.get("feature_contract_version") != FEATURE_CONTRACT_VERSION:
            errors.append("sealed calibration feature contract version mismatch")


def _validate_decision(
    value: Mapping[str, Any],
    errors: list[str],
    *,
    schema_dir: Path,
    calibration_path: Path | None,
    feature_registry_path: Path | None,
    expected_calibration_self_sha256: str | None,
    allow_legacy_migration: bool,
) -> None:
    gates = value.get("gate_results", {})
    if isinstance(gates, dict) and not verify_self_sha256(gates):
        errors.append("gate_results.integrity.self_sha256 mismatch")
    if not _same_candidate_key(value.get("candidate_key"), gates.get("candidate_key")):
        errors.append("gate_results.candidate_key mismatch")
    if value.get("input_contract_sha256") != gates.get("input_contract_sha256"):
        errors.append("gate_results.input_contract_sha256 mismatch")
    _validate_gates(gates, errors)
    policy = value.get("decision_policy", {})
    mode = policy.get("mode")
    decision = value.get("decision")
    score = value.get("approval_score")
    run_metadata = value.get("run_metadata", {})
    if mode == "DEVELOPMENT_HEURISTIC":
        if decision == "AUTO_APPROVED":
            errors.append("DEVELOPMENT_HEURISTIC cannot emit AUTO_APPROVED")
        if score is not None:
            errors.append("DEVELOPMENT_HEURISTIC approval_score must be null")
        if value.get("certificate_ref") is not None:
            errors.append("DEVELOPMENT_HEURISTIC cannot emit certificate_ref")
    elif mode == "FROZEN_CALIBRATED":
        if not policy.get("calibration_artifact_sha256"):
            errors.append("FROZEN_CALIBRATED requires calibration artifact hash")
        migrated_legacy = (
            value.get("schema_version") == PACKAGE_VERSION
            and allow_legacy_migration
            and run_metadata.get("binding_status") == "LEGACY_INCOMPLETE"
        )
        if migrated_legacy:
            pass
        elif calibration_path is None:
            errors.append("FROZEN_CALIBRATED requires a loaded calibration artifact")
        elif value.get("schema_version") == LEGACY_VERSION:
            _validate_legacy_calibration_binding(
                calibration_path,
                schema_dir=schema_dir,
                expected_self_sha256=expected_calibration_self_sha256
                or policy.get("calibration_artifact_sha256"),
                errors=errors,
            )
        elif feature_registry_path is None:
            errors.append("FROZEN_CALIBRATED requires a feature registry")
        else:
            try:
                verified = verify_calibration_artifact(
                    calibration_path,
                    schema_dir=resolve_schema_dir(schema_dir, PACKAGE_VERSION),
                    feature_registry_path=feature_registry_path,
                    expected_self_sha256=expected_calibration_self_sha256
                    or policy.get("calibration_artifact_sha256"),
                    expected_gate_policy_version=run_metadata.get(
                        "gate_policy_version"
                    ),
                    expected_threshold=policy.get("threshold"),
                )
                if verified.artifact.self_sha256 != policy.get(
                    "calibration_artifact_sha256"
                ):
                    errors.append("decision calibration hash differs from artifact")
            except CalibrationVerificationError as exc:
                errors.append(f"calibration verification failed: {exc}")

    triggered_actions = [
        observation.get("action")
        for observation in gates.get("observations", [])
        if observation.get("triggered")
    ]
    blocking = next(
        (action for action in GATE_ACTION_PRECEDENCE if action in triggered_actions),
        "NONE",
    )
    if blocking == "FATAL_SPLIT" and decision != "SPLIT_REQUIRED":
        errors.append("FATAL_SPLIT must resolve to SPLIT_REQUIRED")
    elif blocking == "FATAL_REJECT" and decision != "REJECTED":
        errors.append("FATAL_REJECT must resolve to REJECTED")
    elif blocking == "ESCALATE_HUMAN" and decision != "HUMAN_REVIEW":
        errors.append("ESCALATE_HUMAN must resolve to HUMAN_REVIEW")
    elif blocking == "CAP_PROVISIONAL" and decision not in {
        "PROVISIONAL",
        "HUMAN_REVIEW",
    }:
        errors.append("CAP_PROVISIONAL cannot resolve to an approval/rejection")
    if decision == "AUTO_APPROVED":
        threshold = policy.get("threshold")
        if not isinstance(score, (int, float)) or not isinstance(threshold, (int, float)) or score < threshold:
            errors.append("AUTO_APPROVED requires approval_score >= threshold")
        if blocking != "NONE":
            errors.append("AUTO_APPROVED is incompatible with blocking gates")
    if value.get("schema_version") == PACKAGE_VERSION:
        if run_metadata.get("feature_contract_version") != FEATURE_CONTRACT_VERSION:
            errors.append("run_metadata feature contract version mismatch")
        if policy.get("feature_contract_version") != FEATURE_CONTRACT_VERSION:
            errors.append("decision policy feature contract version mismatch")
        if run_metadata.get("gate_policy_version") != gates.get("gate_policy_version"):
            errors.append("run_metadata gate policy version mismatch")
        hashes = run_metadata.get("input_package_hashes", {})
        if hashes.get("context_evidence_sha256") != value.get("context_evidence_sha256"):
            errors.append("run_metadata context evidence hash mismatch")
        if hashes.get("attestation_evidence_sha256") != value.get("attestation_evidence_sha256"):
            errors.append("run_metadata attestation evidence hash mismatch")
        replay_spec = {
            "candidate_key": value.get("candidate_key"),
            "input_contract_sha256": value.get("input_contract_sha256"),
            "gate_policy_version": gates.get("gate_policy_version"),
            "decision_policy": policy,
        }
        from .integrity import canonical_sha256

        if run_metadata.get("replay_spec_sha256") != canonical_sha256(replay_spec):
            errors.append("run_metadata replay_spec_sha256 mismatch")
        if run_metadata.get("binding_status") == "COMPLETE":
            if hashes.get("global_validator_input_sha256") is None:
                errors.append(
                    "COMPLETE run metadata requires GlobalValidatorInput hash"
                )
            if run_metadata.get("started_at") is None or run_metadata.get("completed_at") is None:
                errors.append("COMPLETE run metadata requires start and completion timestamps")
        elif not allow_legacy_migration and run_metadata.get("binding_status") != "COMPLETE":
            errors.append("native V1.1 decision requires COMPLETE run metadata")


def _validate_certificate(
    value: Mapping[str, Any], errors: list[str], allow_legacy_migration: bool
) -> None:
    status = value.get("status")
    if status not in {"AUTO_APPROVED", "PROVISIONAL"}:
        errors.append("certificate status must be AUTO_APPROVED or PROVISIONAL")
    if value.get("schema_version") != PACKAGE_VERSION:
        return
    binding = value.get("binding_status")
    if binding == "COMPLETE":
        required = (
            "input_contract_sha256",
            "context_evidence_sha256",
            "attestation_evidence_sha256",
            "gate_result_sha256",
            "decision_package_sha256",
        )
        for field in required:
            if not _is_nonzero_sha256(value.get(field)):
                errors.append(f"complete certificate requires {field}")
        calibration_hash = value.get("calibration_artifact_sha256")
        if calibration_hash is not None and not _is_nonzero_sha256(calibration_hash):
            errors.append("calibration_artifact_sha256 must be null or nonzero")
        if not value.get("attestation_evidence_refs"):
            errors.append("complete certificate requires attestation_evidence_refs")
        if value.get("status") not in {"AUTO_APPROVED", "PROVISIONAL"}:
            errors.append("complete certificate status is not issuable")
        key = value.get("candidate_key", {})
        if value.get("sense_inventory_version") != key.get("sense_inventory_version"):
            errors.append("certificate sense_inventory_version mismatch")
        if value.get("effective_sense_contract_sha256") != key.get(
            "effective_sense_contract_sha256"
        ):
            errors.append("certificate effective sense contract hash mismatch")
        summary = value.get("evidence_summary", {})
        for field in ("context_evidence_sha256", "attestation_evidence_sha256"):
            if summary.get(field) != value.get(field):
                errors.append(f"certificate evidence_summary.{field} mismatch")
    elif binding == "LEGACY_INCOMPLETE" and not allow_legacy_migration:
        errors.append("legacy-incomplete certificate cannot be issued")


def _validate_tac(
    value: Mapping[str, Any], errors: list[str], allow_legacy_migration: bool
) -> None:
    span = value.get("source_term_span", {})
    if isinstance(span, Mapping) and span.get("end", 0) <= span.get("start", 0):
        errors.append("source_term_span.end must be greater than start")
    certificate = value.get("certificate")
    if isinstance(certificate, Mapping) and certificate.get("schema_version") == PACKAGE_VERSION:
        _validate_certificate(certificate, errors, allow_legacy_migration)
        if certificate.get("binding_status") != "COMPLETE" and not allow_legacy_migration:
            errors.append("TAC requires a complete V1.1 certificate binding")


def _flag_codes(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        str(item.get("code"))
        for item in value
        if isinstance(item, Mapping) and isinstance(item.get("code"), str)
    }


def _same_candidate_key(a: Any, b: Any) -> bool:
    return (
        isinstance(a, Mapping)
        and isinstance(b, Mapping)
        and all(a.get(field) == b.get(field) for field in CANDIDATE_JOIN_FIELDS)
    )


def _self_hash(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping):
        return None
    return integrity.get("self_sha256")


def _is_nonzero_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value != "0" * 64
        and value == value.casefold()
        and all(character in "0123456789abcdef" for character in value)
    )


def _sibling_calibration_path(path: Path, instance: Mapping[str, Any]) -> Path | None:
    if instance.get("schema_id") != "GlobalDecisionPackageV1":
        return None
    candidate = path.parent / "calibration_artifact.json"
    return candidate if candidate.is_file() else None


def _validate_legacy_calibration_binding(
    path: Path,
    *,
    schema_dir: Path,
    expected_self_sha256: str | None,
    errors: list[str],
) -> None:
    """Validate a V1.0 calibration without interpreting it as V1.1."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("calibration artifact must be an object")
        legacy_errors = schema_validate_instance(payload, schema_dir)
        if legacy_errors:
            raise ValueError("; ".join(legacy_errors))
        if not verify_self_sha256(payload):
            raise ValueError("calibration artifact self hash mismatch")
        actual = payload.get("integrity", {}).get("self_sha256")
        if expected_self_sha256 and actual != expected_self_sha256:
            raise ValueError("calibration artifact hash differs from policy")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"legacy calibration verification failed: {exc}")


def _default_feature_registry(schema_dir: Path) -> Path | None:
    root = schema_dir
    if root.name in {"current", "v1.1.0", "v1.0.0"}:
        root = root.parent
    candidate = root.parent / "registries" / "feature_contract_v1.1.0.json"
    if candidate.is_file():
        return candidate
    candidate = root / "registries" / "feature_contract_v1.1.0.json"
    return candidate if candidate.is_file() else None
