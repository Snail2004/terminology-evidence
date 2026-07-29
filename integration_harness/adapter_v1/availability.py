"""Harness-owned availability intake; producer evidence bytes remain producer-owned."""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from integration_harness.adapter_v1.dataset import DatasetCandidate
from integration_harness.adapter_v1.producer import ProducerItem, ProducerSet, load_producer_set
from integration_harness.errors import IntegrityError, PolicyError, ValidationError
from integration_harness.hashing import self_sha256, sha256_file
from integration_harness.identity import IDENTITY_FIELDS, CandidateIdentity
from integration_harness.jsonio import dump_json, load_json
from integration_harness.paths import ensure_no_symlink, ensure_plain_root, safe_relative_path


AVAILABILITY_SCHEMA = "HarnessEvidenceAvailabilityIntakeV1"
EXTERNAL_HOLD_RECEIPT_SCHEMA = "HarnessExternalAcquisitionHoldReceiptV1"
SCHEMA_VERSION = "1.0.0"

PRESENT = "PRESENT"
EXTERNAL_HOLD = "EXTERNAL_HOLD"
MISSING = "MISSING"
INVALID = "INVALID"
STATUSES = (PRESENT, EXTERNAL_HOLD, MISSING, INVALID)

ROLES = ("context_evidence", "attestation_evidence")

_MANIFEST_FIELDS = {
    "schema_id",
    "schema_version",
    "adapter_mode",
    "run_id",
    "phase_id",
    "split_id",
    "expected_candidate_count",
    "expected_roles",
    "producer_sets",
    "rows",
    "counts",
    "final_glossary_decision",
    "integrity",
}
_ROW_FIELDS = {
    "candidate_key",
    "role",
    "status",
    "observed_at",
    "reason_code",
    "validation_error_code",
    "external_hold_receipt",
}
_PRODUCER_SET_FIELDS = {
    "role",
    "relative_path",
    "physical_sha256",
    "self_sha256",
    "producer",
}
_RECEIPT_DESCRIPTOR_FIELDS = {"relative_path", "physical_sha256", "self_sha256"}
_HOLD_RECEIPT_FIELDS = {
    "schema_id",
    "schema_version",
    "candidate_key",
    "role",
    "status",
    "reason_code",
    "final_glossary_decision",
    "integrity",
}


@dataclass(frozen=True)
class AvailabilityItem:
    identity: CandidateIdentity
    role: str
    status: str
    observed_at: str
    reason_code: str | None
    validation_error_code: str | None
    package: ProducerItem | None
    receipt_path: Path | None
    receipt_raw: bytes | None
    receipt: dict[str, Any] | None


@dataclass(frozen=True)
class AvailabilityManifest:
    manifest_path: Path
    manifest_raw: bytes
    manifest: dict[str, Any]
    items: tuple[AvailabilityItem, ...]
    producer_sets: tuple[ProducerSet, ...]

    @property
    def ready_candidate_ids(self) -> frozenset[str]:
        by_candidate: dict[str, set[str]] = {}
        for item in self.items:
            if item.status == PRESENT:
                by_candidate.setdefault(item.identity.candidate_id, set()).add(item.role)
        return frozenset(
            candidate_id
            for candidate_id, roles in by_candidate.items()
            if roles == set(ROLES)
        )


def load_availability_manifest(
    manifest_path: Path,
    *,
    candidates: Sequence[DatasetCandidate],
    schema_root: Path,
    adapter_mode: str,
) -> AvailabilityManifest:
    root = ensure_plain_root(manifest_path.parent)
    manifest_path = ensure_no_symlink(root, safe_relative_path(manifest_path.name))
    raw = manifest_path.read_bytes()
    manifest = load_json(manifest_path, require_object=True)
    _require_exact_keys(manifest, _MANIFEST_FIELDS, "availability manifest")
    if manifest.get("schema_id") != AVAILABILITY_SCHEMA or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("unsupported HarnessEvidenceAvailabilityIntakeV1")
    if manifest.get("adapter_mode") != adapter_mode:
        raise ValidationError("availability adapter mode mismatch")
    if manifest.get("expected_roles") != list(ROLES):
        raise ValidationError("availability expected_roles mismatch")
    if manifest.get("final_glossary_decision") is not None:
        raise PolicyError("availability manifest contains a final glossary decision")
    _verify_self_hash(manifest, "availability manifest")
    expected = {candidate.identity.candidate_id: candidate for candidate in candidates}
    if manifest.get("expected_candidate_count") != len(expected):
        raise ValidationError("availability expected candidate count mismatch")
    for field in ("run_id", "phase_id", "split_id"):
        _string(manifest.get(field), f"availability {field}")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != len(expected) * len(ROLES):
        raise ValidationError("availability row cardinality mismatch")
    if rows != sorted(rows, key=_row_sort_key):
        raise IntegrityError("availability rows are not canonically sorted")
    raw_rows: dict[tuple[str, str], Mapping[str, Any]] = {}
    present_ids: dict[str, set[str]] = {role: set() for role in ROLES}
    counts = {status: 0 for status in STATUSES}
    receipt_data: dict[tuple[str, str], tuple[Path, bytes, dict[str, Any]]] = {}
    for offset, row_value in enumerate(rows):
        row = _mapping(row_value, f"availability row {offset}")
        _require_exact_keys(row, _ROW_FIELDS, f"availability row {offset}")
        identity = _identity(row.get("candidate_key"))
        candidate = expected.get(identity.candidate_id)
        if candidate is None or identity != candidate.identity:
            raise ValidationError("availability row has a foreign or drifted candidate identity")
        role = _string(row.get("role"), "availability role")
        if role not in ROLES:
            raise ValidationError(f"unsupported availability role: {role}")
        key = (identity.candidate_id, role)
        if key in raw_rows:
            raise ValidationError("duplicate availability candidate/role row")
        raw_rows[key] = row
        status = _string(row.get("status"), "availability status")
        if status not in STATUSES:
            raise ValidationError(f"unsupported availability status: {status}")
        counts[status] += 1
        _string(row.get("observed_at"), "availability observed_at")
        reason = row.get("reason_code")
        error = row.get("validation_error_code")
        receipt_value = row.get("external_hold_receipt")
        if status == PRESENT:
            if any(value is not None for value in (reason, error, receipt_value)):
                raise ValidationError("PRESENT availability row has blocking metadata")
            present_ids[role].add(identity.candidate_id)
        elif status == EXTERNAL_HOLD:
            _string(reason, "EXTERNAL_HOLD reason_code")
            if error is not None:
                raise ValidationError("EXTERNAL_HOLD cannot carry validation_error_code")
            receipt_data[key] = _load_hold_receipt(
                manifest_path.parent,
                receipt_value,
                expected_identity=identity,
                role=role,
            )
        elif status == MISSING:
            _string(reason, "MISSING reason_code")
            if error is not None or receipt_value is not None:
                raise ValidationError("MISSING availability row has invalid metadata")
        else:
            _string(error, "INVALID validation_error_code")
            if reason is not None:
                _string(reason, "INVALID reason_code")
            if receipt_value is not None:
                raise ValidationError("INVALID availability row cannot carry a hold receipt")
    if set(raw_rows) != {(candidate_id, role) for candidate_id in expected for role in ROLES}:
        raise ValidationError("availability manifest does not cover the exact cohort")
    declared_counts = _mapping(manifest.get("counts"), "availability counts")
    _require_exact_keys(declared_counts, set(STATUSES), "availability counts")
    if any(declared_counts.get(status) != count for status, count in counts.items()):
        raise ValidationError("availability status counts mismatch")
    producer_sets = _load_present_sets(
        manifest_path,
        manifest,
        candidates=expected,
        present_ids=present_ids,
        schema_root=schema_root,
        adapter_mode=adapter_mode,
    )
    package_index = {
        (item.identity.candidate_id, producer.role): item
        for producer in producer_sets
        for item in producer.items
    }
    items: list[AvailabilityItem] = []
    for key, row in sorted(raw_rows.items()):
        identity = expected[key[0]].identity
        receipt = receipt_data.get(key)
        items.append(
            AvailabilityItem(
                identity=identity,
                role=key[1],
                status=str(row["status"]),
                observed_at=str(row["observed_at"]),
                reason_code=row.get("reason_code"),
                validation_error_code=row.get("validation_error_code"),
                package=package_index.get(key),
                receipt_path=receipt[0] if receipt else None,
                receipt_raw=receipt[1] if receipt else None,
                receipt=receipt[2] if receipt else None,
            )
        )
    if any((item.status == PRESENT) != (item.package is not None) for item in items):
        raise ValidationError("availability PRESENT rows do not match producer package sets")
    return AvailabilityManifest(
        manifest_path=manifest_path,
        manifest_raw=raw,
        manifest=manifest,
        items=tuple(items),
        producer_sets=tuple(sorted(producer_sets, key=lambda item: item.role)),
    )


def write_missing_availability_manifest(
    output_root: Path,
    *,
    candidates: Sequence[DatasetCandidate],
    adapter_mode: str,
    run_id: str,
    phase_id: str,
    split_id: str,
    observed_at: str,
    reason_code: str,
) -> Path:
    return _write_availability_manifest(
        output_root,
        candidates=candidates,
        adapter_mode=adapter_mode,
        run_id=run_id,
        phase_id=phase_id,
        split_id=split_id,
        observed_at=observed_at,
        reason_code=reason_code,
        producer_sets=(),
    )


def write_present_availability_manifest(
    output_root: Path,
    *,
    candidates: Sequence[DatasetCandidate],
    adapter_mode: str,
    context_set_manifest: Path,
    attestation_set_manifest: Path,
    schema_root: Path,
    run_id: str,
    phase_id: str,
    split_id: str,
    observed_at: str,
) -> Path:
    producers = (
        load_producer_set(
            context_set_manifest,
            role="context_evidence",
            candidates=candidates,
            schema_root=schema_root,
            adapter_mode=adapter_mode,
        ),
        load_producer_set(
            attestation_set_manifest,
            role="attestation_evidence",
            candidates=candidates,
            schema_root=schema_root,
            adapter_mode=adapter_mode,
        ),
    )
    return _write_availability_manifest(
        output_root,
        candidates=candidates,
        adapter_mode=adapter_mode,
        run_id=run_id,
        phase_id=phase_id,
        split_id=split_id,
        observed_at=observed_at,
        reason_code=None,
        producer_sets=producers,
    )


def _write_availability_manifest(
    output_root: Path,
    *,
    candidates: Sequence[DatasetCandidate],
    adapter_mode: str,
    run_id: str,
    phase_id: str,
    split_id: str,
    observed_at: str,
    reason_code: str | None,
    producer_sets: Sequence[ProducerSet],
) -> Path:
    for value, label in (
        (run_id, "run_id"),
        (phase_id, "phase_id"),
        (split_id, "split_id"),
        (observed_at, "observed_at"),
    ):
        _string(value, label)
    output_root = output_root.absolute()
    if output_root.exists():
        raise PolicyError(f"refusing to overwrite availability manifest: {output_root}")
    parent = ensure_plain_root(output_root.parent)
    temp = parent / f".{output_root.name}.tmp-{uuid.uuid4().hex}"
    temp.mkdir()
    try:
        bindings: list[dict[str, Any]] = []
        status_by_role = {producer.role: PRESENT for producer in producer_sets}
        for producer in producer_sets:
            destination_root = temp / "producer_sets" / producer.role
            _copy_file(producer.manifest_path, destination_root / "manifest.json")
            for item in producer.items:
                _copy_file(item.path, destination_root / safe_relative_path(item.relative_path))
            for bound in (producer.source_manifest_path, producer.acceptance_receipt_path):
                if bound is None:
                    continue
                try:
                    relative = bound.relative_to(producer.manifest_path.parent)
                except ValueError as exc:
                    raise ValidationError("producer source binding escapes its manifest root") from exc
                _copy_file(bound, destination_root / relative)
            bindings.append(
                {
                    "role": producer.role,
                    "relative_path": f"producer_sets/{producer.role}/manifest.json",
                    "physical_sha256": sha256_file(destination_root / "manifest.json"),
                    "self_sha256": producer.manifest["integrity"]["self_sha256"],
                    "producer": producer.manifest["producer"],
                }
            )
        rows: list[dict[str, Any]] = []
        counts = {status: 0 for status in STATUSES}
        for candidate in sorted(candidates, key=lambda item: item.identity.candidate_id):
            for role in ROLES:
                status = status_by_role.get(role, MISSING)
                counts[status] += 1
                rows.append(
                    {
                        "candidate_key": candidate.identity.as_dict(),
                        "role": role,
                        "status": status,
                        "observed_at": observed_at,
                        "reason_code": None if status == PRESENT else reason_code,
                        "validation_error_code": None,
                        "external_hold_receipt": None,
                    }
                )
        manifest = {
            "schema_id": AVAILABILITY_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "adapter_mode": adapter_mode,
            "run_id": run_id,
            "phase_id": phase_id,
            "split_id": split_id,
            "expected_candidate_count": len(candidates),
            "expected_roles": list(ROLES),
            "producer_sets": sorted(bindings, key=lambda item: item["role"]),
            "rows": sorted(rows, key=_row_sort_key),
            "counts": counts,
            "final_glossary_decision": None,
            "integrity": {},
        }
        manifest["integrity"]["self_sha256"] = self_sha256(manifest)
        dump_json(temp / "manifest.json", manifest)
        temp.replace(output_root)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return output_root / "manifest.json"


def _load_present_sets(
    manifest_path: Path,
    manifest: Mapping[str, Any],
    *,
    candidates: Mapping[str, DatasetCandidate],
    present_ids: Mapping[str, set[str]],
    schema_root: Path,
    adapter_mode: str,
) -> tuple[ProducerSet, ...]:
    bindings = manifest.get("producer_sets")
    if not isinstance(bindings, list):
        raise ValidationError("availability producer_sets must be an array")
    if bindings != sorted(bindings, key=lambda item: str(item.get("role", "")) if isinstance(item, Mapping) else ""):
        raise IntegrityError("availability producer_sets are not canonically sorted")
    by_role: dict[str, Mapping[str, Any]] = {}
    for value in bindings:
        binding = _mapping(value, "availability producer set binding")
        _require_exact_keys(
            binding,
            _PRODUCER_SET_FIELDS,
            "availability producer set binding",
        )
        role = _string(binding.get("role"), "availability producer set role")
        if role not in ROLES or role in by_role:
            raise ValidationError("duplicate or unsupported availability producer set")
        by_role[role] = binding
    expected_roles = {role for role, ids in present_ids.items() if ids}
    if set(by_role) != expected_roles:
        raise ValidationError("availability producer set bindings do not match PRESENT roles")
    result: list[ProducerSet] = []
    for role in sorted(expected_roles):
        binding = by_role[role]
        relative = safe_relative_path(_string(binding.get("relative_path"), "producer set path"))
        path = ensure_no_symlink(manifest_path.parent, relative)
        if not path.is_file() or sha256_file(path) != binding.get("physical_sha256"):
            raise IntegrityError("availability producer set physical hash mismatch")
        value = load_json(path, require_object=True)
        if value.get("integrity", {}).get("self_sha256") != binding.get("self_sha256"):
            raise IntegrityError("availability producer set self hash mismatch")
        producer = load_producer_set(
            path,
            role=role,
            candidates=[candidates[candidate_id] for candidate_id in sorted(present_ids[role])],
            schema_root=schema_root,
            adapter_mode=adapter_mode,
        )
        if binding.get("producer") != producer.manifest.get("producer"):
            raise ValidationError("availability producer set provenance mismatch")
        result.append(producer)
    return tuple(result)


def _load_hold_receipt(
    root: Path,
    value: Any,
    *,
    expected_identity: CandidateIdentity,
    role: str,
) -> tuple[Path, bytes, dict[str, Any]]:
    descriptor = _mapping(value, "EXTERNAL_HOLD receipt descriptor")
    _require_exact_keys(
        descriptor,
        _RECEIPT_DESCRIPTOR_FIELDS,
        "EXTERNAL_HOLD receipt descriptor",
    )
    relative = safe_relative_path(_string(descriptor.get("relative_path"), "hold receipt path"))
    path = ensure_no_symlink(root, relative)
    if not path.is_file() or sha256_file(path) != descriptor.get("physical_sha256"):
        raise IntegrityError("EXTERNAL_HOLD receipt physical hash mismatch")
    raw = path.read_bytes()
    receipt = load_json(path, require_object=True)
    _require_exact_keys(receipt, _HOLD_RECEIPT_FIELDS, "EXTERNAL_HOLD receipt")
    if receipt.get("schema_id") != EXTERNAL_HOLD_RECEIPT_SCHEMA or receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("unsupported EXTERNAL_HOLD receipt")
    _verify_self_hash(receipt, "EXTERNAL_HOLD receipt")
    if descriptor.get("self_sha256") != receipt["integrity"]["self_sha256"]:
        raise IntegrityError("EXTERNAL_HOLD receipt self binding mismatch")
    if receipt.get("role") != role or receipt.get("status") != EXTERNAL_HOLD:
        raise ValidationError("EXTERNAL_HOLD receipt role/status mismatch")
    if _identity(receipt.get("candidate_key")) != expected_identity:
        raise ValidationError("EXTERNAL_HOLD receipt identity mismatch")
    if receipt.get("final_glossary_decision") is not None:
        raise PolicyError("EXTERNAL_HOLD receipt contains a final decision")
    _string(receipt.get("reason_code"), "EXTERNAL_HOLD receipt reason")
    return path, raw, receipt


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() == source.read_bytes():
            return
        raise IntegrityError(f"conflicting availability source path: {destination}")
    shutil.copyfile(source, destination)


def _identity(value: Any) -> CandidateIdentity:
    mapping = _mapping(value, "availability candidate_key")
    _require_exact_keys(mapping, set(IDENTITY_FIELDS), "availability candidate_key")
    envelope = {
        "candidate_key": {
            key: item for key, item in mapping.items() if key != "input_contract_sha256"
        },
        "input_contract_sha256": mapping.get("input_contract_sha256"),
    }
    return CandidateIdentity.from_package(envelope)


def _row_sort_key(value: Any) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        return ("", "")
    candidate = value.get("candidate_key")
    candidate_id = candidate.get("candidate_id") if isinstance(candidate, Mapping) else ""
    return (str(candidate_id), str(value.get("role", "")))


def _verify_self_hash(value: Mapping[str, Any], label: str) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping):
        raise IntegrityError(f"{label} integrity is invalid")
    _require_exact_keys(integrity, {"self_sha256"}, f"{label} integrity")
    if integrity.get("self_sha256") != self_sha256(value):
        raise IntegrityError(f"{label} self hash mismatch")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ValidationError(f"{label} fields mismatch: missing={missing}, extra={extra}")


__all__ = [
    "AVAILABILITY_SCHEMA",
    "EXTERNAL_HOLD",
    "INVALID",
    "MISSING",
    "PRESENT",
    "AvailabilityItem",
    "AvailabilityManifest",
    "load_availability_manifest",
    "write_missing_availability_manifest",
    "write_present_availability_manifest",
]
