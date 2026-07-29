"""Deterministic batch authority, cohort, availability, and readiness sidecars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from integration_harness.adapter_v1.availability import (
    EXTERNAL_HOLD,
    INVALID,
    MISSING,
    PRESENT,
    ROLES,
    STATUSES,
    AvailabilityManifest,
)
from integration_harness.adapter_v1.dataset import DatasetRelease
from integration_harness.errors import IntegrityError, ReplayError, ValidationError
from integration_harness.hashing import self_sha256, sha256_bytes


COHORT_SCHEMA = "HarnessCohortInventoryV1"
BATCH_AUTHORITY_SCHEMA = "GlobalBatchAuthorityV1"
AVAILABILITY_SCHEMA = "EvidenceAvailabilityManifestV1"
READINESS_SCHEMA = "GlobalBatchReadinessReportV1"
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class SidecarSet:
    cohort: dict[str, Any]
    authority: dict[str, Any]
    availability: dict[str, Any]
    readiness: dict[str, Any]


def build_sidecars(
    dataset: DatasetRelease,
    availability_input: AvailabilityManifest,
    *,
    package_refs: Mapping[tuple[str, str], Mapping[str, Any]],
    receipt_refs: Mapping[tuple[str, str], Mapping[str, Any]],
    cohort_physical_sha256: str | None = None,
    authority_physical_sha256: str | None = None,
    availability_physical_sha256: str | None = None,
) -> SidecarSet:
    cohort = _build_cohort(dataset, availability_input)
    if cohort_physical_sha256 is not None and cohort_physical_sha256 != sha256_bytes(_json_bytes(cohort)):
        raise IntegrityError("cohort physical binding mismatch during sidecar rebuild")
    availability = _build_availability(
        availability_input,
        package_refs=package_refs,
        receipt_refs=receipt_refs,
    )
    authority = _build_authority(
        dataset,
        availability_input,
        cohort,
        cohort_physical_sha256=cohort_physical_sha256 or sha256_bytes(_json_bytes(cohort)),
    )
    readiness = _build_readiness(
        authority,
        availability,
        authority_physical_sha256=(
            authority_physical_sha256 or sha256_bytes(_json_bytes(authority))
        ),
        availability_physical_sha256=(
            availability_physical_sha256 or sha256_bytes(_json_bytes(availability))
        ),
    )
    return SidecarSet(cohort, authority, availability, readiness)


def verify_sidecars(
    sidecars: SidecarSet,
    *,
    dataset: DatasetRelease,
    physical_hashes: Mapping[str, str],
) -> dict[str, Any]:
    cohort = sidecars.cohort
    authority = sidecars.authority
    availability = sidecars.availability
    readiness = sidecars.readiness
    for value, schema, label in (
        (cohort, COHORT_SCHEMA, "cohort inventory"),
        (authority, BATCH_AUTHORITY_SCHEMA, "batch authority"),
        (availability, AVAILABILITY_SCHEMA, "availability manifest"),
        (readiness, READINESS_SCHEMA, "readiness report"),
    ):
        if value.get("schema_id") != schema or value.get("schema_version") != SCHEMA_VERSION:
            raise ReplayError(f"unsupported {label} schema")
        if value.get("integrity", {}).get("self_sha256") != self_sha256(value):
            raise ReplayError(f"{label} self hash mismatch")
    common = {
        "run_id": availability.get("run_id"),
        "phase_id": availability.get("phase_id"),
        "split_id": availability.get("split_id"),
    }
    if cohort.get("adapter_mode") != dataset.mode or authority.get("adapter_mode") != dataset.mode:
        raise ReplayError("sidecar adapter mode mismatch")
    if availability.get("adapter_mode") != dataset.mode:
        raise ReplayError("availability adapter mode mismatch")
    for value, label in (
        (cohort, "cohort inventory"),
        (authority, "batch authority"),
        (readiness, "readiness report"),
    ):
        if any(value.get(field) != expected for field, expected in common.items()):
            raise ReplayError(f"{label} run/phase/split binding mismatch")
    entries = cohort.get("candidates")
    if not isinstance(entries, list) or entries != sorted(entries, key=lambda item: item["candidate_key"]["candidate_id"]):
        raise ReplayError("cohort candidates are not canonically sorted")
    expected = {candidate.identity.candidate_id: candidate for candidate in dataset.candidates}
    if len(entries) != len(expected) or cohort.get("candidate_count") != len(expected):
        raise ReplayError("cohort candidate count mismatch")
    if cohort.get("sense_count") != dataset.sense_count:
        raise ReplayError("cohort sense count mismatch")
    if authority.get("expected_candidate_count") != dataset.candidate_count:
        raise ReplayError("batch authority candidate count mismatch")
    if authority.get("expected_sense_count") != dataset.sense_count:
        raise ReplayError("batch authority sense count mismatch")
    for entry in entries:
        candidate_id = entry.get("candidate_key", {}).get("candidate_id")
        candidate = expected.get(candidate_id)
        if candidate is None or entry.get("candidate_key") != candidate.identity.as_dict():
            raise ReplayError("cohort candidate identity mismatch")
        expected_artifacts = {
            "effective_sense": {
                "physical_sha256": sha256_bytes(candidate.effective_raw),
                "self_sha256": candidate.effective["integrity"]["self_sha256"],
            },
            "frozen_candidate": {
                "physical_sha256": sha256_bytes(candidate.frozen_raw),
                "self_sha256": candidate.frozen["integrity"]["self_sha256"],
            },
            "constraints": {
                "physical_sha256": sha256_bytes(candidate.constraint_raw),
                "self_sha256": candidate.constraint["integrity"]["self_sha256"],
            },
        }
        if entry.get("dataset_artifacts") != expected_artifacts:
            raise ReplayError("cohort Dataset artifact binding mismatch")
    dataset_binding = authority.get("dataset_binding", {})
    if dataset_binding.get("pin_self_sha256") != dataset.pin["integrity"]["self_sha256"]:
        raise ReplayError("batch authority Dataset pin mismatch")
    if dataset_binding.get("zip_physical_sha256") != sha256_bytes(dataset.zip_raw):
        raise ReplayError("batch authority Dataset ZIP mismatch")
    if dataset_binding.get("manifest_self_sha256") != dataset.manifest["manifest_sha256"]:
        raise ReplayError("batch authority Dataset manifest self binding mismatch")
    if dataset_binding.get("manifest_physical_sha256") != sha256_bytes(dataset.manifest_raw):
        raise ReplayError("batch authority Dataset manifest physical binding mismatch")
    if authority.get("cohort_inventory", {}).get("self_sha256") != cohort["integrity"]["self_sha256"]:
        raise ReplayError("batch authority cohort self binding mismatch")
    if authority.get("cohort_inventory", {}).get("physical_sha256") != physical_hashes.get("cohort"):
        raise ReplayError("batch authority cohort physical binding mismatch")
    if readiness.get("batch_authority", {}).get("self_sha256") != authority["integrity"]["self_sha256"]:
        raise ReplayError("readiness batch authority self binding mismatch")
    if readiness.get("batch_authority", {}).get("physical_sha256") != physical_hashes.get("authority"):
        raise ReplayError("readiness batch authority physical binding mismatch")
    if readiness.get("availability_manifest", {}).get("self_sha256") != availability["integrity"]["self_sha256"]:
        raise ReplayError("readiness availability self binding mismatch")
    if readiness.get("availability_manifest", {}).get("physical_sha256") != physical_hashes.get("availability"):
        raise ReplayError("readiness availability physical binding mismatch")
    availability_rows = availability.get("rows")
    if not isinstance(availability_rows, list):
        raise ReplayError("availability rows are missing")
    if availability_rows != sorted(
        availability_rows,
        key=lambda item: (item["candidate_key"]["candidate_id"], item["role"]),
    ):
        raise ReplayError("availability rows are not canonically sorted")
    observed_rows: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in availability_rows:
        candidate_key = row.get("candidate_key")
        if not isinstance(candidate_key, Mapping):
            raise ReplayError("availability candidate identity is missing")
        candidate_id = candidate_key.get("candidate_id")
        candidate = expected.get(candidate_id)
        if candidate is None or dict(candidate_key) != candidate.identity.as_dict():
            raise ReplayError("availability candidate identity mismatch")
        role = row.get("role")
        key = (str(candidate_id), str(role))
        if role not in ROLES or key in observed_rows:
            raise ReplayError("availability candidate/role cardinality mismatch")
        observed_rows[key] = row
        status = row.get("status")
        package = row.get("package")
        receipt = row.get("external_hold_receipt")
        if (status == PRESENT) != isinstance(package, Mapping):
            raise ReplayError("availability package/status mismatch")
        if (status == EXTERNAL_HOLD) != isinstance(receipt, Mapping):
            raise ReplayError("availability hold receipt/status mismatch")
    expected_rows = {
        (candidate_id, role)
        for candidate_id in expected
        for role in ROLES
    }
    if set(observed_rows) != expected_rows:
        raise ReplayError("availability does not cover the exact cohort")
    recomputed_counts = {status: 0 for status in STATUSES}
    for row in observed_rows.values():
        status = str(row.get("status"))
        if status not in recomputed_counts:
            raise ReplayError("unsupported availability status")
        recomputed_counts[status] += 1
    if availability.get("counts") != recomputed_counts:
        raise ReplayError("availability status counts mismatch")
    recomputed = _build_readiness(
        authority,
        availability,
        authority_physical_sha256=physical_hashes["authority"],
        availability_physical_sha256=physical_hashes["availability"],
    )
    if recomputed != readiness:
        raise ReplayError("readiness semantic projection drift")
    return {
        "candidate_count": cohort["candidate_count"],
        "sense_count": cohort["sense_count"],
        "ready_count": readiness["counts"]["ready_for_global"],
        "not_submitted_count": readiness["counts"]["not_submitted"],
        "status_counts": availability["counts"],
    }


def _build_cohort(dataset: DatasetRelease, availability: AvailabilityManifest) -> dict[str, Any]:
    candidates = []
    for candidate in sorted(dataset.candidates, key=lambda item: item.identity.candidate_id):
        candidates.append(
            {
                "candidate_key": candidate.identity.as_dict(),
                "dataset_artifacts": {
                    "effective_sense": {
                        "physical_sha256": sha256_bytes(candidate.effective_raw),
                        "self_sha256": candidate.effective["integrity"]["self_sha256"],
                    },
                    "frozen_candidate": {
                        "physical_sha256": sha256_bytes(candidate.frozen_raw),
                        "self_sha256": candidate.frozen["integrity"]["self_sha256"],
                    },
                    "constraints": {
                        "physical_sha256": sha256_bytes(candidate.constraint_raw),
                        "self_sha256": candidate.constraint["integrity"]["self_sha256"],
                    },
                },
            }
        )
    value = {
        "schema_id": COHORT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "adapter_mode": dataset.mode,
        "run_id": availability.manifest["run_id"],
        "phase_id": availability.manifest["phase_id"],
        "split_id": availability.manifest["split_id"],
        "candidate_count": dataset.candidate_count,
        "sense_count": dataset.sense_count,
        "candidates": candidates,
        "final_glossary_decision": None,
        "integrity": {},
    }
    value["integrity"]["self_sha256"] = self_sha256(value)
    return value


def _build_authority(
    dataset: DatasetRelease,
    availability: AvailabilityManifest,
    cohort: Mapping[str, Any],
    *,
    cohort_physical_sha256: str,
) -> dict[str, Any]:
    value = {
        "schema_id": BATCH_AUTHORITY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "adapter_mode": dataset.mode,
        "run_id": availability.manifest["run_id"],
        "phase_id": availability.manifest["phase_id"],
        "split_id": availability.manifest["split_id"],
        "expected_candidate_count": dataset.candidate_count,
        "expected_sense_count": dataset.sense_count,
        "expected_roles": list(ROLES),
        "expected_package_schemas": {
            "context_evidence": "ContextEvidencePackageV1@1.1.0",
            "attestation_evidence": "AttestationEvidencePackageV1@1.1.0",
        },
        "dataset_binding": {
            "pin_self_sha256": dataset.pin["integrity"]["self_sha256"],
            "zip_physical_sha256": sha256_bytes(dataset.zip_raw),
            "manifest_self_sha256": dataset.manifest["manifest_sha256"],
            "manifest_physical_sha256": sha256_bytes(dataset.manifest_raw),
        },
        "cohort_inventory": {
            "self_sha256": cohort["integrity"]["self_sha256"],
            "physical_sha256": cohort_physical_sha256,
        },
        "global_action_policy_binding": {
            "status": "BOUND_BY_SYSTEM_INTEGRATION_RUN_AUTHORITY",
            "required_before_global": True,
        },
        "network_policy": "FORBIDDEN",
        "final_glossary_decision": None,
        "integrity": {},
    }
    value["integrity"]["self_sha256"] = self_sha256(value)
    return value


def _build_availability(
    source: AvailabilityManifest,
    *,
    package_refs: Mapping[tuple[str, str], Mapping[str, Any]],
    receipt_refs: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts = {status: 0 for status in STATUSES}
    producer_sets = []
    for producer in source.producer_sets:
        producer_sets.append(
            {
                "role": producer.role,
                "manifest_self_sha256": producer.manifest["integrity"]["self_sha256"],
                "manifest_physical_sha256": sha256_bytes(producer.manifest_raw),
                "producer": producer.manifest["producer"],
            }
        )
    for item in source.items:
        key = (item.identity.candidate_id, item.role)
        counts[item.status] += 1
        package = package_refs.get(key)
        receipt = receipt_refs.get(key)
        if (item.status == PRESENT) != (package is not None):
            raise ValidationError("materialized package refs do not match PRESENT availability")
        if (item.status == EXTERNAL_HOLD) != (receipt is not None):
            raise ValidationError("materialized hold refs do not match EXTERNAL_HOLD availability")
        rows.append(
            {
                "candidate_key": item.identity.as_dict(),
                "role": item.role,
                "status": item.status,
                "observed_at": item.observed_at,
                "reason_code": item.reason_code,
                "validation_error_code": item.validation_error_code,
                "package": dict(package) if package is not None else None,
                "external_hold_receipt": dict(receipt) if receipt is not None else None,
            }
        )
    value = {
        "schema_id": AVAILABILITY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "adapter_mode": source.manifest["adapter_mode"],
        "run_id": source.manifest["run_id"],
        "phase_id": source.manifest["phase_id"],
        "split_id": source.manifest["split_id"],
        "expected_candidate_count": source.manifest["expected_candidate_count"],
        "expected_roles": list(ROLES),
        "producer_sets": sorted(producer_sets, key=lambda item: item["role"]),
        "rows": sorted(rows, key=lambda item: (item["candidate_key"]["candidate_id"], item["role"])),
        "counts": counts,
        "final_glossary_decision": None,
        "integrity": {},
    }
    value["integrity"]["self_sha256"] = self_sha256(value)
    return value


def _build_readiness(
    authority: Mapping[str, Any],
    availability: Mapping[str, Any],
    *,
    authority_physical_sha256: str,
    availability_physical_sha256: str,
) -> dict[str, Any]:
    by_candidate: dict[str, list[Mapping[str, Any]]] = {}
    for row_value in availability["rows"]:
        row = _mapping(row_value, "availability row")
        candidate_id = str(row["candidate_key"]["candidate_id"])
        by_candidate.setdefault(candidate_id, []).append(row)
    ready: list[str] = []
    not_submitted: list[dict[str, Any]] = []
    for candidate_id, rows in sorted(by_candidate.items()):
        statuses = {str(row["role"]): str(row["status"]) for row in rows}
        if statuses == {role: PRESENT for role in ROLES}:
            ready.append(candidate_id)
            continue
        reasons = []
        for row in sorted(rows, key=lambda item: str(item["role"])):
            if row["status"] != PRESENT:
                reasons.append(
                    {
                        "role": row["role"],
                        "status": row["status"],
                        "reason_code": row.get("reason_code"),
                        "validation_error_code": row.get("validation_error_code"),
                    }
                )
        not_submitted.append({"candidate_id": candidate_id, "reasons": reasons})
    expected = int(authority["expected_candidate_count"])
    if len(by_candidate) != expected or len(ready) + len(not_submitted) != expected:
        raise ValidationError("readiness projection candidate cardinality mismatch")
    status_counts = dict(availability["counts"])
    identity_rejected = {
        candidate_id
        for candidate_id, rows in by_candidate.items()
        if any(
            row.get("status") == INVALID
            and str(row.get("validation_error_code", "")).startswith("IDENTITY_")
            for row in rows
        )
    }
    value = {
        "schema_id": READINESS_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "run_id": authority["run_id"],
        "phase_id": authority["phase_id"],
        "split_id": authority["split_id"],
        "batch_authority": {
            "self_sha256": authority["integrity"]["self_sha256"],
            "physical_sha256": authority_physical_sha256,
        },
        "availability_manifest": {
            "self_sha256": availability["integrity"]["self_sha256"],
            "physical_sha256": availability_physical_sha256,
        },
        "counts": {
            "expected_candidates": expected,
            "ready_for_global": len(ready),
            "not_submitted": len(not_submitted),
            "identity_rejected": len(identity_rejected),
            "availability": status_counts,
        },
        "ready_for_global_candidate_ids": ready,
        "not_submitted": not_submitted,
        "global_mode": "DEVELOPMENT_HEURISTIC",
        "network_calls": 0,
        "provider_calls": 0,
        "auto_approved_count": 0,
        "certificate_count": 0,
        "final_glossary_decision": None,
        "integrity": {},
    }
    value["integrity"]["self_sha256"] = self_sha256(value)
    return value


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    from integration_harness.jsonio import canonical_bytes

    return canonical_bytes(dict(value)) + b"\n"


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReplayError(f"{label} must be an object")
    return value


__all__ = [
    "AVAILABILITY_SCHEMA",
    "BATCH_AUTHORITY_SCHEMA",
    "COHORT_SCHEMA",
    "READINESS_SCHEMA",
    "SidecarSet",
    "build_sidecars",
    "verify_sidecars",
]
