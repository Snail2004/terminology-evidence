from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .bindings import (
    calculate_replay_spec_sha256,
    normalize_term,
    verify_frozen_candidate_binding,
)
from .canonical import verify_self_sha256
from .calibration import CalibrationVerificationError, verify_calibration_artifact
from .integrity import (
    IntegrityError,
    load_verified_json_artifact,
    strict_json_loads,
)
from .registries import (
    CANDIDATE_JOIN_FIELDS,
    FEATURE_CONTRACT_VERSION,
    GATE_ACTION_PRECEDENCE,
    GATE_IDS,
    GATE_SOURCE_MODULES,
    LEGACY_VERSION,
    PACKAGE_VERSION,
    RegistryError,
    SCHEMA_FILES,
    load_registry,
)
from .scoring import (
    ScoringError,
    assemble_decision_features,
    evaluate_calibration_model,
    expected_decision,
    finite_number,
    select_model_features,
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
    global_input_path: Path | None = None,
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
            global_input_path=global_input_path,
            allow_legacy_migration=allow_legacy_migration,
        )
    errors.extend(
        _safe_semantic_errors(
            instance,
            schema_dir=schema_dir,
            calibration_path=calibration_path,
            feature_registry_path=feature_registry_path,
            expected_calibration_self_sha256=expected_calibration_self_sha256,
            global_input_path=global_input_path,
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
    global_input_path: Path | None = None,
    allow_legacy_migration: bool = False,
) -> list[str]:
    try:
        instance = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"cannot read JSON: {exc}"]
    if not isinstance(instance, dict):
        return ["$: payload must be an object"]
    if calibration_path is None:
        calibration_path = _sibling_calibration_path(path, instance)
    if feature_registry_path is None:
        feature_registry_path = _default_feature_registry(schema_dir)
    if global_input_path is None:
        global_input_path = _sibling_global_input_path(path, instance)
    return validate_instance(
        instance,
        schema_dir,
        calibration_path=calibration_path,
        feature_registry_path=feature_registry_path,
        expected_calibration_self_sha256=expected_calibration_self_sha256,
        global_input_path=global_input_path,
        allow_legacy_migration=allow_legacy_migration,
    )


def verify_certificate_bundle(
    *,
    certificate_path: Path,
    frozen_candidate_path: Path,
    effective_sense_contract_path: Path,
    constraint_evidence_path: Path,
    global_input_path: Path,
    context_evidence_path: Path,
    attestation_evidence_path: Path,
    gate_result_path: Path,
    decision_path: Path,
    calibration_path: Path | None,
    schema_dir: Path,
    feature_registry_path: Path,
    tac_path: Path | None = None,
) -> list[str]:
    """Verify a certificate against the exact artifact bundle it claims.

    Structural certificate validation intentionally cannot prove that external
    files exist. Consumers and TAC call this API before accepting authority.
    """
    errors: list[str] = []
    certificate = _load_bundle_artifact(
        "certificate", certificate_path, None, errors
    )
    if certificate is None:
        return errors
    errors.extend(
        f"certificate: {error}"
        for error in validate_instance(certificate, schema_dir)
    )

    expected = {
        "frozen_candidate": certificate.get("frozen_candidate_contract_sha256"),
        "effective_sense": certificate.get("effective_sense_contract_sha256"),
        "constraint_evidence": certificate.get("constraint_evidence_sha256"),
        "global_input": certificate.get("global_validator_input_sha256"),
        "context_evidence": certificate.get("context_evidence_sha256"),
        "attestation_evidence": certificate.get("attestation_evidence_sha256"),
        "gate_result": certificate.get("gate_result_sha256"),
        "decision": certificate.get("decision_package_sha256"),
        "calibration": certificate.get("calibration_artifact_sha256"),
    }
    paths = {
        "frozen_candidate": frozen_candidate_path,
        "effective_sense": effective_sense_contract_path,
        "constraint_evidence": constraint_evidence_path,
        "global_input": global_input_path,
        "context_evidence": context_evidence_path,
        "attestation_evidence": attestation_evidence_path,
        "gate_result": gate_result_path,
        "decision": decision_path,
    }
    artifacts: dict[str, Mapping[str, Any]] = {}
    for name, path in paths.items():
        payload = _load_bundle_artifact(name, path, expected[name], errors)
        if payload is not None:
            artifacts[name] = payload

    if expected["calibration"] is not None:
        if calibration_path is None:
            errors.append("calibration: certificate requires an artifact file")
        else:
            payload = _load_bundle_artifact(
                "calibration", calibration_path, expected["calibration"], errors
            )
            if payload is not None:
                artifacts["calibration"] = payload

    expected_schema_ids = {
        "frozen_candidate": "FrozenCandidateContractV1",
        "effective_sense": "EffectiveSenseContractV1",
        "constraint_evidence": "ConstraintEvidencePackageV1",
        "global_input": "GlobalValidatorInputV1",
        "context_evidence": "ContextEvidencePackageV1",
        "attestation_evidence": "AttestationEvidencePackageV1",
        "gate_result": "GateResultSetV1",
        "decision": "GlobalDecisionPackageV1",
        "calibration": "CalibrationArtifactV1",
    }
    for name, payload in artifacts.items():
        if payload.get("schema_id") != expected_schema_ids[name]:
            errors.append(
                f"{name}: expected {expected_schema_ids[name]}, got "
                f"{payload.get('schema_id')!r}"
            )

    for name in (
        "frozen_candidate",
        "effective_sense",
        "constraint_evidence",
        "global_input",
        "context_evidence",
        "attestation_evidence",
        "gate_result",
    ):
        payload = artifacts.get(name)
        if payload is not None:
            errors.extend(
                f"{name}: {error}"
                for error in validate_instance(payload, schema_dir)
            )

    decision = artifacts.get("decision")
    if decision is not None:
        errors.extend(
            f"decision: {error}"
            for error in validate_instance(
                decision,
                schema_dir,
                calibration_path=calibration_path,
                feature_registry_path=feature_registry_path,
                global_input_path=global_input_path,
            )
        )

    raw_key = certificate.get("candidate_key")
    key = raw_key if isinstance(raw_key, Mapping) else {}
    input_hash = certificate.get("input_contract_sha256")
    for name in (
        "frozen_candidate",
        "constraint_evidence",
        "global_input",
        "context_evidence",
        "attestation_evidence",
        "gate_result",
        "decision",
    ):
        payload = artifacts.get(name)
        if payload is None:
            continue
        if not _same_candidate_key(key, payload.get("candidate_key")):
            errors.append(f"{name}: candidate_key differs from certificate")
        if input_hash != payload.get("input_contract_sha256"):
            errors.append(f"{name}: input_contract_sha256 differs from certificate")

    effective = artifacts.get("effective_sense")
    if effective is not None:
        if _self_hash(effective) != key.get("effective_sense_contract_sha256"):
            errors.append("effective_sense: hash differs from candidate key")
        for field in ("source_term", "sense_id", "scope_id", "sense_inventory_version"):
            if effective.get(field) != key.get(field):
                errors.append(f"effective_sense: {field} differs from candidate key")

    global_input = artifacts.get("global_input")
    if global_input is not None:
        nested_bindings = {
            "frozen_candidate": "frozen_candidate_contract",
            "effective_sense": "effective_sense_contract",
            "constraint_evidence": "constraint_evidence",
            "context_evidence": "context_evidence",
            "attestation_evidence": "attestation_evidence",
        }
        for artifact_name, field in nested_bindings.items():
            payload = artifacts.get(artifact_name)
            if payload is not None and global_input.get(field) != payload:
                errors.append(
                    f"global_input.{field} differs from supplied {artifact_name}"
                )

    gates = artifacts.get("gate_result")
    if decision is not None and gates is not None:
        if decision.get("gate_results") != gates:
            errors.append("decision.gate_results differs from supplied gate result")
        if certificate.get("status") != decision.get("decision"):
            errors.append("certificate status differs from decision")
        if certificate.get("policy_version") != decision.get(
            "decision_policy", {}
        ).get("policy_version"):
            errors.append("certificate policy_version differs from decision")
        if certificate.get("calibration_artifact_sha256") != decision.get(
            "decision_policy", {}
        ).get("calibration_artifact_sha256"):
            errors.append("certificate calibration binding differs from decision")
        triggered = sorted(
            observation.get("gate_id")
            for observation in gates.get("observations", [])
            if observation.get("triggered")
        )
        if sorted(certificate.get("gate_summary", [])) != triggered:
            errors.append("certificate gate_summary differs from triggered gates")

    context = artifacts.get("context_evidence")
    if context is not None:
        context_refs = []
        support_set = context.get("support_set", {})
        for field in (
            "positive_support_refs",
            "contrastive_refs",
            "negative_or_boundary_refs",
        ):
            context_refs.extend(support_set.get(field, []))
        for reference in certificate.get("validity_context_refs", []):
            if reference not in context_refs:
                errors.append(
                    "certificate validity_context_refs contains unbound evidence"
                )

    attestation = artifacts.get("attestation_evidence")
    if attestation is not None:
        accepted_refs = attestation.get("accepted_evidence_refs", [])
        for reference in certificate.get("attestation_evidence_refs", []):
            if reference not in accepted_refs:
                errors.append(
                    "certificate attestation_evidence_refs contains unbound evidence"
                )

    if tac_path is not None:
        tac = _load_bundle_artifact("tac", tac_path, None, errors)
        if tac is not None:
            errors.extend(
                f"tac: {error}" for error in validate_instance(tac, schema_dir)
            )
            if tac.get("certificate") != certificate:
                errors.append("tac.certificate differs from supplied certificate")
    return errors


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
    global_input_path: Path | None,
    allow_legacy_migration: bool,
) -> list[str]:
    errors: list[str] = []
    schema_id = instance.get("schema_id")
    version = instance.get("schema_version")
    if version not in {LEGACY_VERSION, PACKAGE_VERSION}:
        return errors
    if not verify_self_sha256(dict(instance)):
        errors.append("integrity.self_sha256 mismatch")
    if version == PACKAGE_VERSION:
        errors.extend(_nonfinite_number_errors(instance))

    if schema_id == "FrozenCandidateContractV1":
        _validate_frozen_candidate(instance, errors, allow_legacy_migration)
    elif schema_id == "ConstraintEvidencePackageV1":
        _validate_constraint_evidence(instance, errors)
    elif schema_id == "ContextEvidencePackageV1":
        _validate_context(instance, errors)
    elif schema_id == "AttestationEvidencePackageV1":
        _validate_attestation(instance, errors)
    elif schema_id == "GlobalValidatorInputV1":
        _validate_global_input(instance, errors, allow_legacy_migration)
    elif schema_id == "GateResultSetV1":
        _validate_gates(instance, errors, allow_legacy_migration)
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
            global_input_path=global_input_path,
            allow_legacy_migration=allow_legacy_migration,
        )
    elif schema_id == "TerminologyCertificateV1":
        _validate_certificate(instance, errors, allow_legacy_migration)
    elif schema_id == "TACOccurrenceInputV1":
        _validate_tac(instance, errors, allow_legacy_migration)

    return errors


def _validate_frozen_candidate(
    value: Mapping[str, Any],
    errors: list[str],
    allow_legacy_migration: bool,
) -> None:
    surfaces = value.get("surfaces", {})
    key = value.get("candidate_key", {})
    if surfaces.get("canonical_vi") != key.get("candidate_vi"):
        errors.append("surfaces.canonical_vi must equal candidate_key.candidate_vi")
    if value.get("schema_version") != PACKAGE_VERSION:
        return
    binding_status = value.get("binding_status")
    if binding_status == "COMPLETE":
        if not verify_frozen_candidate_binding(value):
            errors.append(
                "input_contract_sha256 does not bind FrozenCandidateContract content"
            )
    elif binding_status == "LEGACY_INCOMPLETE":
        if not allow_legacy_migration:
            errors.append("legacy-incomplete Frozen Candidate is not native V1.1")
    else:
        errors.append("Frozen Candidate binding_status is invalid")


def _validate_constraint_evidence(
    value: Mapping[str, Any], errors: list[str]
) -> None:
    key = value.get("candidate_key", {})
    sense = value.get("sense_review", {})
    sense_status = sense.get("status")
    sense_hash = sense.get("effective_sense_contract_sha256")
    review_ref = sense.get("review_artifact_ref")
    if sense_status == "VERIFIED":
        if sense_hash != key.get("effective_sense_contract_sha256"):
            errors.append("verified sense review hash differs from candidate key")
        if not isinstance(review_ref, Mapping):
            errors.append("verified sense review requires review_artifact_ref")
    elif sense_status == "UNVERIFIED":
        if sense_hash is not None or review_ref is not None:
            errors.append("unverified sense review cannot claim verified bindings")

    polysemy = value.get("polysemy_resolution", {})
    polysemy_status = polysemy.get("status")
    related = polysemy.get("related_sense_ids", [])
    authority_ref = polysemy.get("authority_ref")
    if polysemy_status == "RESOLVED_SINGLE":
        if related != [key.get("sense_id")]:
            errors.append("RESOLVED_SINGLE must contain only candidate sense_id")
        if not isinstance(authority_ref, Mapping):
            errors.append("resolved polysemy requires authority_ref")
    elif polysemy_status == "RESOLVED_SPLIT":
        if len(related) < 2 or key.get("sense_id") not in related:
            errors.append("RESOLVED_SPLIT requires candidate plus related senses")
        if not isinstance(authority_ref, Mapping):
            errors.append("resolved split requires authority_ref")
    elif polysemy_status == "UNRESOLVED" and authority_ref is not None:
        errors.append("UNRESOLVED polysemy cannot claim authority_ref")

    collision = value.get("target_collision", {})
    collision_status = collision.get("status")
    index_hash = collision.get("collision_index_sha256")
    conflicts = collision.get("conflicting_candidate_keys", [])
    refs = collision.get("evidence_refs", [])
    if collision_status == "CLEAR":
        if not _is_nonzero_sha256(index_hash):
            errors.append("CLEAR target collision status requires index hash")
        if conflicts:
            errors.append("CLEAR target collision status cannot list conflicts")
    elif collision_status == "COLLISION":
        if not _is_nonzero_sha256(index_hash):
            errors.append("COLLISION status requires index hash")
        if not conflicts or not refs:
            errors.append("COLLISION status requires conflicts and evidence")
        if any(_same_candidate_key(key, conflict) for conflict in conflicts):
            errors.append("target collision cannot reference the candidate itself")
    elif collision_status == "UNJUDGEABLE":
        if conflicts:
            errors.append("UNJUDGEABLE collision status cannot list conflicts")


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


def _validate_global_input(
    value: Mapping[str, Any],
    errors: list[str],
    allow_legacy_migration: bool,
) -> None:
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
        if name == "context_evidence":
            _validate_context(package, errors)
        else:
            _validate_attestation(package, errors)

    if value.get("schema_version") != PACKAGE_VERSION:
        for index, probe in enumerate(value.get("optional_probes", [])):
            if isinstance(probe, dict) and not verify_self_sha256(probe):
                errors.append(
                    f"optional_probes[{index}].integrity.self_sha256 mismatch"
                )
            if not _same_candidate_key(key, probe.get("candidate_key")):
                errors.append(f"optional_probes[{index}].candidate_key mismatch")
            if input_hash != probe.get("input_contract_sha256"):
                errors.append(
                    f"optional_probes[{index}].input_contract_sha256 mismatch"
                )
        return

    assembly = value.get("assembly_metadata")
    binding_status = assembly.get("binding_status") if isinstance(assembly, Mapping) else None
    effective = value.get("effective_sense_contract")
    frozen = value.get("frozen_candidate_contract")
    constraint = value.get("constraint_evidence")
    if binding_status == "LEGACY_INCOMPLETE":
        if not allow_legacy_migration:
            errors.append("legacy-incomplete Global Input is not native V1.1")
        if any(item is not None for item in (effective, frozen, constraint)):
            errors.append("legacy-incomplete Global Input cannot claim new bindings")
    elif binding_status == "COMPLETE":
        if not isinstance(frozen, Mapping) or not isinstance(constraint, Mapping):
            errors.append("complete Global Input requires Frozen Candidate and constraints")
        else:
            if not verify_self_sha256(dict(frozen)):
                errors.append("frozen_candidate_contract.integrity.self_sha256 mismatch")
            if not _same_candidate_key(key, frozen.get("candidate_key")):
                errors.append("frozen_candidate_contract.candidate_key mismatch")
            if input_hash != frozen.get("input_contract_sha256"):
                errors.append("frozen_candidate_contract.input_contract_sha256 mismatch")
            _validate_frozen_candidate(frozen, errors, allow_legacy_migration)
            if not verify_self_sha256(dict(constraint)):
                errors.append("constraint_evidence.integrity.self_sha256 mismatch")
            if not _same_candidate_key(key, constraint.get("candidate_key")):
                errors.append("constraint_evidence.candidate_key mismatch")
            if input_hash != constraint.get("input_contract_sha256"):
                errors.append("constraint_evidence.input_contract_sha256 mismatch")
            _validate_constraint_evidence(constraint, errors)

            sense_status = constraint.get("sense_review", {}).get("status")
            if sense_status == "VERIFIED":
                if not isinstance(effective, Mapping):
                    errors.append("verified sense review requires Effective Sense Contract")
                else:
                    if not verify_self_sha256(dict(effective)):
                        errors.append("effective_sense_contract.integrity.self_sha256 mismatch")
                    effective_hash = _self_hash(effective)
                    if effective_hash != key.get("effective_sense_contract_sha256"):
                        errors.append("Effective Sense Contract hash differs from candidate key")
                    for field in ("source_term", "sense_id", "scope_id", "sense_inventory_version"):
                        if effective.get(field) != key.get(field):
                            errors.append(f"effective_sense_contract.{field} mismatch")
                    if effective.get("parent_dataset_manifest_sha256") != key.get(
                        "dataset_manifest_sha256"
                    ):
                        errors.append("effective_sense_contract dataset manifest mismatch")
                    review_ref = constraint.get("sense_review", {}).get(
                        "review_artifact_ref", {}
                    )
                    if isinstance(review_ref, Mapping) and review_ref.get(
                        "sha256"
                    ) != effective.get("review_artifact_sha256"):
                        errors.append("sense review artifact binding mismatch")
                    for field in (
                        "effective_definition_en",
                        "effective_part_of_speech",
                        "scope_note",
                        "domain_profile",
                    ):
                        if frozen.get(field) != effective.get(field):
                            errors.append(f"Frozen Candidate {field} differs from Effective Sense")
            elif effective is not None:
                errors.append("unverified sense review must not embed Effective Sense Contract")
    else:
        errors.append("Global Input assembly binding_status is invalid")
    if isinstance(assembly, Mapping):
        hashes = assembly.get("source_package_hashes", {})
        for name, package_name in (
            ("context_evidence_sha256", "context_evidence"),
            ("attestation_evidence_sha256", "attestation_evidence"),
        ):
            expected = _self_hash(value.get(package_name))
            if expected is not None and hashes.get(name) != expected:
                errors.append(f"assembly_metadata.{name} mismatch")
        for name, package_name in (
            ("effective_sense_contract_sha256", "effective_sense_contract"),
            ("frozen_candidate_contract_sha256", "frozen_candidate_contract"),
            ("constraint_evidence_sha256", "constraint_evidence"),
        ):
            expected = _self_hash(value.get(package_name))
            if hashes.get(name) != expected:
                errors.append(f"assembly_metadata.{name} mismatch")
    for index, probe in enumerate(value.get("optional_probes", [])):
        if isinstance(probe, dict) and not verify_self_sha256(probe):
            errors.append(f"optional_probes[{index}].integrity.self_sha256 mismatch")
        if not _same_candidate_key(key, probe.get("candidate_key")):
            errors.append(f"optional_probes[{index}].candidate_key mismatch")
        if input_hash != probe.get("input_contract_sha256"):
            errors.append(f"optional_probes[{index}].input_contract_sha256 mismatch")


def _validate_gates(
    value: Mapping[str, Any],
    errors: list[str],
    allow_legacy_migration: bool,
) -> None:
    observations = value.get("observations", [])
    native_v11 = value.get("schema_version") == PACKAGE_VERSION
    binding_status = value.get("binding_status") if native_v11 else None
    strict_native = native_v11 and binding_status == "COMPLETE"
    if native_v11:
        gate_ids = [
            item.get("gate_id")
            for item in observations
            if isinstance(item, Mapping)
        ]
        if strict_native and len(gate_ids) != len(set(gate_ids)):
            errors.append("observations must contain unique gate_id values")
        if binding_status == "COMPLETE":
            missing = sorted(set(GATE_IDS).difference(gate_ids))
            extra = sorted(set(gate_ids).difference(GATE_IDS))
            if missing or extra:
                errors.append(
                    "complete GateResultSet must cover registry exactly: "
                    f"missing={missing}, extra={extra}"
                )
        elif binding_status == "LEGACY_INCOMPLETE":
            if not allow_legacy_migration:
                errors.append("legacy-incomplete GateResultSet is not native V1.1")
        else:
            errors.append("GateResultSet binding_status is invalid")
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
        if strict_native and observation.get("triggered") is True:
            if not observation.get("reason_codes"):
                errors.append(
                    f"observations[{index}]: triggered gate requires reason_codes"
                )
            if not observation.get("evidence_refs"):
                errors.append(
                    f"observations[{index}]: triggered gate requires evidence_refs"
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
    global_input_path: Path | None,
    allow_legacy_migration: bool,
) -> None:
    gates = value.get("gate_results", {})
    if isinstance(gates, dict) and not verify_self_sha256(gates):
        errors.append("gate_results.integrity.self_sha256 mismatch")
    if not _same_candidate_key(value.get("candidate_key"), gates.get("candidate_key")):
        errors.append("gate_results.candidate_key mismatch")
    if value.get("input_contract_sha256") != gates.get("input_contract_sha256"):
        errors.append("gate_results.input_contract_sha256 mismatch")
    _validate_gates(gates, errors, allow_legacy_migration)
    policy = value.get("decision_policy", {})
    mode = policy.get("mode")
    decision = value.get("decision")
    score = value.get("approval_score")
    run_metadata = value.get("run_metadata", {})
    native_v11 = value.get("schema_version") == PACKAGE_VERSION
    migrated_legacy = (
        native_v11
        and allow_legacy_migration
        and run_metadata.get("binding_status") == "LEGACY_INCOMPLETE"
    )
    global_input: Mapping[str, Any] | None = None
    feature_registry: Mapping[str, Any] | None = None
    verified_calibration = None

    if native_v11 and not migrated_legacy:
        expected_global_hash = run_metadata.get("input_package_hashes", {}).get(
            "global_validator_input_sha256"
        )
        if global_input_path is None:
            errors.append("complete decision requires a loaded GlobalValidatorInput")
        else:
            try:
                loaded = load_verified_json_artifact(
                    global_input_path,
                    expected_self_sha256=expected_global_hash,
                )
                global_input = loaded.payload
            except IntegrityError as exc:
                errors.append(f"GlobalValidatorInput verification failed: {exc}")
            else:
                nested_errors = validate_instance(
                    dict(global_input),
                    schema_dir,
                    feature_registry_path=feature_registry_path,
                    allow_legacy_migration=allow_legacy_migration,
                )
                errors.extend(
                    f"GlobalValidatorInput: {error}" for error in nested_errors
                )
                if not _same_candidate_key(
                    value.get("candidate_key"), global_input.get("candidate_key")
                ):
                    errors.append("GlobalValidatorInput candidate_key mismatch")
                if value.get("input_contract_sha256") != global_input.get(
                    "input_contract_sha256"
                ):
                    errors.append("GlobalValidatorInput input_contract_sha256 mismatch")

        if feature_registry_path is None:
            errors.append("complete decision requires a feature registry")
        else:
            try:
                feature_registry = load_registry(feature_registry_path)
            except RegistryError as exc:
                errors.append(f"feature registry verification failed: {exc}")

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
                verified_calibration = verify_calibration_artifact(
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
                if verified_calibration.artifact.self_sha256 != policy.get(
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
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not math.isfinite(float(score))
            or not isinstance(threshold, (int, float))
            or isinstance(threshold, bool)
            or not math.isfinite(float(threshold))
            or score < threshold
        ):
            errors.append("AUTO_APPROVED requires approval_score >= threshold")
        if blocking != "NONE":
            errors.append("AUTO_APPROVED is incompatible with blocking gates")
    if native_v11:
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
        if hashes.get("gate_result_sha256") != _self_hash(gates):
            errors.append("run_metadata gate result hash mismatch")
        if run_metadata.get("replay_spec_sha256") != calculate_replay_spec_sha256(
            value
        ):
            errors.append("run_metadata replay_spec_sha256 mismatch")
        if run_metadata.get("binding_status") == "COMPLETE":
            for field in (
                "global_validator_input_sha256",
                "context_evidence_sha256",
                "attestation_evidence_sha256",
                "effective_sense_contract_sha256",
                "frozen_candidate_contract_sha256",
                "constraint_evidence_sha256",
                "gate_result_sha256",
            ):
                if not _is_nonzero_sha256(hashes.get(field)):
                    errors.append(f"COMPLETE run metadata requires {field}")
            if (
                run_metadata.get("started_at") is None
                or run_metadata.get("completed_at") is None
            ):
                errors.append("COMPLETE run metadata requires start and completion timestamps")
        elif not allow_legacy_migration and run_metadata.get("binding_status") != "COMPLETE":
            errors.append("native V1.1 decision requires COMPLETE run metadata")

        if global_input is not None:
            expected_hashes = {
                "global_validator_input_sha256": _self_hash(global_input),
                "context_evidence_sha256": _self_hash(
                    global_input.get("context_evidence")
                ),
                "attestation_evidence_sha256": _self_hash(
                    global_input.get("attestation_evidence")
                ),
                "effective_sense_contract_sha256": _self_hash(
                    global_input.get("effective_sense_contract")
                ),
                "frozen_candidate_contract_sha256": _self_hash(
                    global_input.get("frozen_candidate_contract")
                ),
                "constraint_evidence_sha256": _self_hash(
                    global_input.get("constraint_evidence")
                ),
                "gate_result_sha256": _self_hash(gates),
            }
            for field, expected in expected_hashes.items():
                if hashes.get(field) != expected:
                    errors.append(f"run_metadata {field} differs from loaded input")
            _validate_constraint_gate_projection(global_input, gates, errors)

        if (
            mode == "FROZEN_CALIBRATED"
            and verified_calibration is not None
            and global_input is not None
            and feature_registry is not None
        ):
            try:
                assembled = assemble_decision_features(global_input, feature_registry)
                expected_features = select_model_features(
                    assembled, verified_calibration.feature_names
                )
                actual_features = value.get("decision_features")
                if not isinstance(actual_features, Mapping):
                    raise ScoringError("decision_features must be an object")
                if set(actual_features) != set(expected_features):
                    missing = sorted(set(expected_features).difference(actual_features))
                    unknown = sorted(set(actual_features).difference(expected_features))
                    raise ScoringError(
                        "decision feature set mismatch: "
                        f"missing={missing}, unknown={unknown}"
                    )
                for name, expected_feature in expected_features.items():
                    actual_feature = finite_number(
                        actual_features[name], field=f"decision_features.{name}"
                    )
                    if not math.isclose(
                        actual_feature, expected_feature, rel_tol=0.0, abs_tol=1e-12
                    ):
                        raise ScoringError(
                            f"decision_features.{name} differs from mapped evidence"
                        )
                computed_score = evaluate_calibration_model(
                    verified_calibration.artifact.payload, actual_features
                )
                actual_score = finite_number(score, field="approval_score")
                if not math.isclose(
                    actual_score,
                    computed_score,
                    rel_tol=0.0,
                    abs_tol=verified_calibration.numerical_tolerance,
                ):
                    errors.append(
                        "approval_score differs from replayed calibration model: "
                        f"expected {computed_score:.17g}, got {actual_score:.17g}"
                    )
                expected_status = expected_decision(
                    computed_score, verified_calibration.threshold, blocking
                )
                if decision != expected_status:
                    errors.append(
                        "decision differs from calibrated score and gate precedence: "
                        f"expected {expected_status}, got {decision}"
                    )
            except ScoringError as exc:
                errors.append(f"frozen decision replay failed: {exc}")


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
            "global_validator_input_sha256",
            "frozen_candidate_contract_sha256",
            "constraint_evidence_sha256",
        )
        for field in required:
            if not _is_nonzero_sha256(value.get(field)):
                errors.append(f"complete certificate requires {field}")
        calibration_hash = value.get("calibration_artifact_sha256")
        if calibration_hash is not None and not _is_nonzero_sha256(calibration_hash):
            errors.append("calibration_artifact_sha256 must be null or nonzero")
        if status == "AUTO_APPROVED" and not _is_nonzero_sha256(calibration_hash):
            errors.append("AUTO_APPROVED certificate requires calibration artifact")
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
    source_text = value.get("source_text")
    if isinstance(span, Mapping):
        start = span.get("start")
        end = span.get("end")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
        ):
            errors.append("source_term_span must satisfy 0 <= start < end")
        elif not isinstance(source_text, str) or end > len(source_text):
            errors.append("source_term_span exceeds source_text bounds")
    certificate = value.get("certificate")
    if isinstance(certificate, Mapping) and certificate.get("schema_version") == PACKAGE_VERSION:
        _validate_certificate(certificate, errors, allow_legacy_migration)
        if certificate.get("binding_status") != "COMPLETE" and not allow_legacy_migration:
            errors.append("TAC requires a complete V1.1 certificate binding")
        if (
            isinstance(span, Mapping)
            and isinstance(source_text, str)
            and isinstance(span.get("start"), int)
            and not isinstance(span.get("start"), bool)
            and isinstance(span.get("end"), int)
            and not isinstance(span.get("end"), bool)
            and 0 <= span["start"] < span["end"] <= len(source_text)
        ):
            selected = source_text[span["start"] : span["end"]]
            expected = certificate.get("candidate_key", {}).get("source_term")
            if not isinstance(expected, str) or normalize_term(selected) != normalize_term(
                expected
            ):
                errors.append(
                    "source_term_span text does not match certificate source_term"
                )


def _validate_constraint_gate_projection(
    global_input: Mapping[str, Any],
    gates: Mapping[str, Any],
    errors: list[str],
) -> None:
    constraint = global_input.get("constraint_evidence")
    if not isinstance(constraint, Mapping):
        errors.append("constraint gate projection requires ConstraintEvidencePackage")
        return
    expected = {
        "sense_definition_unverified": constraint.get("sense_review", {}).get(
            "status"
        )
        != "VERIFIED",
        "unresolved_polysemy": constraint.get("polysemy_resolution", {}).get(
            "status"
        )
        == "UNRESOLVED",
        "target_collision": constraint.get("target_collision", {}).get("status")
        != "CLEAR",
    }
    observations = {
        observation.get("gate_id"): observation
        for observation in gates.get("observations", [])
        if isinstance(observation, Mapping)
    }
    for gate_id, expected_triggered in expected.items():
        observation = observations.get(gate_id)
        if not isinstance(observation, Mapping):
            errors.append(f"constraint projection missing gate: {gate_id}")
        elif observation.get("triggered") is not expected_triggered:
            errors.append(
                f"gate {gate_id} disagrees with declared constraint evidence"
            )


def _nonfinite_number_errors(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            errors.extend(_nonfinite_number_errors(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_nonfinite_number_errors(child, f"{path}[{index}]"))
    elif isinstance(value, float) and not math.isfinite(value):
        errors.append(f"{path}: non-finite number is forbidden")
    return errors


def _load_bundle_artifact(
    name: str,
    path: Path,
    expected_self_sha256: Any,
    errors: list[str],
) -> Mapping[str, Any] | None:
    if expected_self_sha256 is not None and not _is_nonzero_sha256(
        expected_self_sha256
    ):
        errors.append(f"{name}: expected hash is not a nonzero SHA-256")
        return None
    try:
        artifact = load_verified_json_artifact(
            path,
            expected_self_sha256=expected_self_sha256,
        )
    except IntegrityError as exc:
        errors.append(f"{name}: {exc}")
        return None
    return artifact.payload


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


def _sibling_global_input_path(
    path: Path, instance: Mapping[str, Any]
) -> Path | None:
    if instance.get("schema_id") != "GlobalDecisionPackageV1":
        return None
    candidate = path.parent / "global_validator_input.json"
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
        payload = strict_json_loads(path.read_text(encoding="utf-8"))
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
