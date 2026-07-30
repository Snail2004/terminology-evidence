"""Complete producer package-set verification for Harness availability intake."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from integration_harness.adapter_v1.dataset import (
    DatasetCandidate,
    OFFICIAL_MODE,
    SYNTHETIC_MODE,
)
from integration_harness.errors import IntegrityError, PolicyError, ValidationError
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.identity import CandidateIdentity
from integration_harness.jsonio import canonical_bytes, load_json
from integration_harness.packages import validate_contract_schema
from integration_harness.paths import ensure_no_symlink, ensure_plain_root, safe_relative_path
from integration_harness.adapter_v1.trust import TrustedAuthorityProfile


LEGACY_PACKAGE_SET_SCHEMA = "HarnessProducerPackageSetV1"
PACKAGE_SET_SCHEMA = "HarnessProducerPackageSetV2"
LEGACY_SCHEMA_VERSION = "1.0.0"
SCHEMA_VERSION = "2.0.0"

ACCEPTANCE_RECEIPT_SCHEMA = "HarnessProducerSetAcceptanceReceiptV1"
APPROVAL_ARTIFACT_SCHEMA = "HarnessProducerSetApprovalArtifactV1"
COHORT_AUTHORITY_SCHEMA = "HarnessCandidateCohortAuthorityV1"
SOURCE_MANIFEST_SCHEMA = "HarnessProducerSourceManifestV1"
AUTHORITY_SCHEMA_VERSION = "1.0.0"
NEW_INPUT_MODE = "NEW_INPUT"
HISTORICAL_REPLAY_MODE = "HISTORICAL_REPLAY_ONLY"

COMPLETE_ACCEPTED = "COMPLETE_ACCEPTED"
SYNTHETIC_COMPLETE = "SYNTHETIC_LOCAL_CONFORMANCE"

ROLE_SCHEMAS = {
    "context_evidence": "ContextEvidencePackageV1",
    "attestation_evidence": "AttestationEvidencePackageV1",
}

_LEGACY_MANIFEST_FIELDS = {
    "schema_id", "schema_version", "producer_role", "status", "producer",
    "entry_count", "package_count", "hold_count", "entries",
    "accepted_source_binding", "final_glossary_decision", "global_action",
    "integrity",
}
_MANIFEST_FIELDS = {
    "schema_id", "schema_version", "producer_role", "status", "producer",
    "entry_count", "package_count", "hold_count", "entries", "source_manifest",
    "final_glossary_decision", "global_action", "integrity",
}
_ENTRY_FIELDS = {
    "candidate_id", "kind", "relative_path", "physical_sha256", "self_sha256",
}
_LEGACY_PRODUCER_FIELDS = {"component_id", "component_version", "run_id", "commit"}
_PRODUCER_FIELDS = _LEGACY_PRODUCER_FIELDS | {"tree"}
_BOUND_FILE_FIELDS = {"relative_path", "physical_sha256", "self_sha256"}
_COHORT_FIELDS = {
    "schema_id", "schema_version", "run_id", "phase_id", "split_id",
    "candidate_count", "candidate_set_sha256", "candidates",
    "final_glossary_decision", "integrity",
}
_APPROVAL_FIELDS = {
    "schema_id", "schema_version", "status", "issuer_id", "authority_id",
    "run_id", "phase_id", "split_id", "producer_role", "producer",
    "package_set_manifest", "candidate_cohort", "candidate_count",
    "candidate_set_sha256", "final_glossary_decision", "integrity",
}
_RECEIPT_FIELDS = _APPROVAL_FIELDS | {"approval_artifact"}
_SOURCE_MANIFEST_FIELDS = {
    "schema_id", "schema_version", "status", "producer_role", "producer",
    "candidate_count", "candidate_set_sha256", "producer_release_receipt",
    "final_glossary_decision", "integrity",
}
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class ProducerItem:
    role: str
    identity: CandidateIdentity
    kind: str
    path: Path
    relative_path: str
    raw: bytes
    value: dict[str, Any]
    physical_sha256: str
    self_sha256: str


@dataclass(frozen=True)
class ProducerSet:
    role: str
    status: str
    manifest_path: Path
    manifest_raw: bytes
    manifest: dict[str, Any]
    items: tuple[ProducerItem, ...]
    source_manifest_path: Path | None
    source_authority_files: tuple[tuple[Path, str], ...]
    acceptance_receipt_path: Path | None
    acceptance_receipt_raw: bytes | None
    acceptance_receipt: dict[str, Any] | None
    acceptance_authority_files: tuple[tuple[Path, str], ...]


def candidate_set_sha256(candidates: Sequence[DatasetCandidate]) -> str:
    """Hash the exact, canonically ordered candidate identities."""

    identities = [
        item.identity.as_dict()
        for item in sorted(candidates, key=lambda item: item.identity.candidate_id)
    ]
    return sha256_bytes(canonical_bytes(identities))


def load_producer_set(
    manifest_path: Path,
    *,
    role: str,
    candidates: Sequence[DatasetCandidate],
    schema_root: Path,
    adapter_mode: str,
    acceptance_receipt_path: Path | None = None,
    run_id: str | None = None,
    phase_id: str | None = None,
    split_id: str | None = None,
    trust_profile: TrustedAuthorityProfile | None = None,
    intake_mode: str = NEW_INPUT_MODE,
) -> ProducerSet:
    if role not in ROLE_SCHEMAS:
        raise ValidationError(f"unsupported producer role: {role}")
    root = ensure_plain_root(manifest_path.parent)
    manifest_path = ensure_no_symlink(root, safe_relative_path(manifest_path.name))
    manifest_raw = manifest_path.read_bytes()
    manifest = load_json(manifest_path, require_object=True)
    schema_id = manifest.get("schema_id")
    if schema_id == PACKAGE_SET_SCHEMA:
        if intake_mode == HISTORICAL_REPLAY_MODE:
            raise PolicyError("historical replay mode admits only legacy producer package sets")
        _require_exact_keys(manifest, _MANIFEST_FIELDS, "producer package-set manifest")
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValidationError("unsupported Harness producer package-set V2 manifest")
        producer = _producer(manifest.get("producer"), legacy=False)
    elif schema_id == LEGACY_PACKAGE_SET_SCHEMA:
        if intake_mode != HISTORICAL_REPLAY_MODE:
            raise PolicyError("legacy producer package set is historical-replay only")
        _require_exact_keys(
            manifest, _LEGACY_MANIFEST_FIELDS, "legacy producer package-set manifest"
        )
        if manifest.get("schema_version") != LEGACY_SCHEMA_VERSION:
            raise ValidationError("unsupported Harness producer package-set V1 manifest")
        producer = _producer(manifest.get("producer"), legacy=True)
    else:
        raise ValidationError("unsupported Harness producer package-set manifest")
    _verify_self_hash(manifest, "producer package-set manifest")
    if manifest.get("producer_role") != role:
        raise ValidationError("producer package-set role mismatch")
    if manifest.get("final_glossary_decision") is not None:
        raise PolicyError("producer package-set contains a final glossary decision")
    if manifest.get("global_action") is not None:
        raise PolicyError("producer package-set contains a Global-owned action")
    status = _string(manifest.get("status"), "producer package-set status")
    _validate_status(status, adapter_mode=adapter_mode)
    if status == COMPLETE_ACCEPTED and schema_id != PACKAGE_SET_SCHEMA:
        raise PolicyError(
            "official PRESENT admission requires HarnessProducerPackageSetV2"
        )

    expected = {candidate.identity.candidate_id: candidate.identity for candidate in candidates}
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != len(expected):
        raise ValidationError("producer package-set entry count mismatch")
    if entries != sorted(
        entries,
        key=lambda item: str(item.get("candidate_id", "")) if isinstance(item, Mapping) else "",
    ):
        raise IntegrityError("producer package-set entries are not canonically sorted")
    if manifest.get("entry_count") != len(entries):
        raise ValidationError("producer package-set declared entry count mismatch")

    items: list[ProducerItem] = []
    observed: set[str] = set()
    folded_paths: set[str] = set()
    for offset, entry_value in enumerate(entries):
        entry = _mapping(entry_value, f"producer entry {offset}")
        _require_exact_keys(entry, _ENTRY_FIELDS, f"producer entry {offset}")
        candidate_id = _string(entry.get("candidate_id"), "producer candidate_id")
        if candidate_id in observed or candidate_id not in expected:
            raise ValidationError(f"duplicate or foreign producer candidate: {candidate_id}")
        observed.add(candidate_id)
        relative = safe_relative_path(
            _string(entry.get("relative_path"), "producer entry relative_path")
        )
        relative_text = relative.as_posix()
        if relative_text.casefold() in folded_paths:
            raise IntegrityError("producer package-set has case-confusable paths")
        folded_paths.add(relative_text.casefold())
        path = ensure_no_symlink(manifest_path.parent, relative)
        if not path.is_file():
            raise ValidationError(f"producer package is missing: {relative_text}")
        raw = path.read_bytes()
        physical = sha256_file(path)
        if entry.get("physical_sha256") != physical:
            raise IntegrityError(f"producer package physical hash mismatch: {relative_text}")
        value = load_json(path, require_object=True)
        kind = _string(entry.get("kind"), "producer entry kind")
        if kind != "PACKAGE":
            raise ValidationError(f"unsupported producer entry kind: {kind}")
        items.append(
            _validate_package(
                value,
                raw=raw,
                path=path,
                relative_path=relative_text,
                physical=physical,
                entry=entry,
                role=role,
                identity=expected[candidate_id],
                producer=producer,
                schema_root=schema_root,
            )
        )
    if observed != set(expected):
        raise ValidationError("producer package-set is missing Dataset candidates")
    if manifest.get("package_count") != len(items) or manifest.get("hold_count") != 0:
        raise ValidationError("producer package-set package count mismatch")

    source_manifest_path: Path | None = None
    source_authority_files: tuple[tuple[Path, str], ...] = ()
    receipt_raw: bytes | None = None
    receipt: dict[str, Any] | None = None
    authority_files: tuple[tuple[Path, str], ...] = ()
    if schema_id == PACKAGE_SET_SCHEMA:
        source_manifest_path, source_authority_files = _verify_source_manifest(
            manifest_path,
            manifest.get("source_manifest"),
            role=role,
            producer=producer,
            candidates=candidates,
            required=status == COMPLETE_ACCEPTED,
            trust_profile=trust_profile,
        )
        if status == COMPLETE_ACCEPTED:
            if trust_profile is None:
                raise PolicyError("official PRESENT admission requires a trusted authority profile")
            if acceptance_receipt_path is None:
                raise PolicyError("official PRESENT admission requires an acceptance receipt")
            if None in (run_id, phase_id, split_id):
                raise ValidationError("official acceptance requires run/phase/split binding")
            receipt_raw, receipt, authority_files = _verify_acceptance_receipt(
                acceptance_receipt_path,
                manifest_path=manifest_path,
                manifest=manifest,
                producer=producer,
                role=role,
                candidates=candidates,
                run_id=str(run_id),
                phase_id=str(phase_id),
                split_id=str(split_id),
                trust_profile=trust_profile,
            )
        elif acceptance_receipt_path is not None:
            raise PolicyError("synthetic producer set cannot claim an acceptance receipt")
    else:
        legacy_binding = manifest.get("accepted_source_binding")
        if legacy_binding is not None:
            raise PolicyError("legacy accepted_source_binding is not admitted for new input")
        if acceptance_receipt_path is not None:
            raise PolicyError("legacy producer set cannot claim an acceptance receipt")

    return ProducerSet(
        role=role,
        status=status,
        manifest_path=manifest_path,
        manifest_raw=manifest_raw,
        manifest=manifest,
        items=tuple(sorted(items, key=lambda item: item.identity.candidate_id)),
        source_manifest_path=source_manifest_path,
        source_authority_files=source_authority_files,
        acceptance_receipt_path=acceptance_receipt_path,
        acceptance_receipt_raw=receipt_raw,
        acceptance_receipt=receipt,
        acceptance_authority_files=authority_files,
    )


def _validate_status(status: str, *, adapter_mode: str) -> None:
    allowed = (
        {COMPLETE_ACCEPTED}
        if adapter_mode == OFFICIAL_MODE
        else {SYNTHETIC_COMPLETE}
        if adapter_mode == SYNTHETIC_MODE
        else set()
    )
    if not allowed:
        raise ValidationError(f"unsupported adapter mode: {adapter_mode}")
    if status not in allowed:
        raise PolicyError(f"producer package-set status is not admitted: {status}")


def _verify_source_manifest(
    manifest_path: Path,
    descriptor_value: Any,
    *,
    role: str,
    producer: Mapping[str, str],
    candidates: Sequence[DatasetCandidate],
    required: bool,
    trust_profile: TrustedAuthorityProfile | None,
) -> tuple[Path | None, tuple[tuple[Path, str], ...]]:
    if descriptor_value is None:
        if required:
            raise PolicyError("official producer set requires a typed source manifest")
        return None, ()
    path, value = _bound_json(manifest_path.parent, descriptor_value, "producer source manifest")
    _require_exact_keys(value, _SOURCE_MANIFEST_FIELDS, "producer source manifest")
    if (
        value.get("schema_id") != SOURCE_MANIFEST_SCHEMA
        or value.get("schema_version") != AUTHORITY_SCHEMA_VERSION
        or value.get("status") != "COMPLETE"
        or value.get("producer_role") != role
        or value.get("producer") != dict(producer)
    ):
        raise ValidationError("producer source manifest authority mismatch")
    _verify_candidate_counts(value, candidates, "producer source manifest")
    _require_null_decision(value, "producer source manifest")
    if required:
        if trust_profile is None:
            raise PolicyError("official producer source manifest requires trusted authority")
        expected = trust_profile.producer(role)
        if value["integrity"]["self_sha256"] != expected["source_manifest_self_sha256"]:
            raise IntegrityError("producer source manifest trusted self hash mismatch")
        if sha256_file(path) != expected["source_manifest_physical_sha256"]:
            raise IntegrityError("producer source manifest trusted physical hash mismatch")
        release_path, release = _bound_json(
            manifest_path.parent,
            value.get("producer_release_receipt"),
            "producer release receipt",
        )
        if release["integrity"]["self_sha256"] != expected["release_receipt_self_sha256"]:
            raise IntegrityError("producer release receipt trusted self hash mismatch")
        if sha256_file(release_path) != expected["release_receipt_physical_sha256"]:
            raise IntegrityError("producer release receipt trusted physical hash mismatch")
        source_relative = _descriptor_relative(descriptor_value)
        return path, (
            (path, source_relative),
            (
                release_path,
                _descriptor_relative(value["producer_release_receipt"]),
            ),
        )
    if value.get("producer_release_receipt") is not None:
        raise PolicyError("synthetic source manifest cannot claim a producer release receipt")
    return path, ((path, _descriptor_relative(descriptor_value)),)


def _verify_acceptance_receipt(
    receipt_path: Path,
    *,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    producer: Mapping[str, str],
    role: str,
    candidates: Sequence[DatasetCandidate],
    run_id: str,
    phase_id: str,
    split_id: str,
    trust_profile: TrustedAuthorityProfile,
) -> tuple[bytes, dict[str, Any], tuple[tuple[Path, str], ...]]:
    root = ensure_plain_root(receipt_path.parent)
    receipt_path = ensure_no_symlink(root, safe_relative_path(receipt_path.name))
    raw = receipt_path.read_bytes()
    receipt = load_json(receipt_path, require_object=True)
    _require_exact_keys(receipt, _RECEIPT_FIELDS, "producer acceptance receipt")
    if (
        receipt.get("schema_id") != ACCEPTANCE_RECEIPT_SCHEMA
        or receipt.get("schema_version") != AUTHORITY_SCHEMA_VERSION
        or receipt.get("status") != "ACCEPTED"
    ):
        raise ValidationError("unsupported or non-accepted producer acceptance receipt")
    _verify_self_hash(receipt, "producer acceptance receipt")
    trusted = trust_profile.producer(role)
    _verify_trusted_profile_run(
        trust_profile, run_id=run_id, phase_id=phase_id, split_id=split_id
    )
    if receipt.get("issuer_id") != trust_profile.value["issuer_id"]:
        raise ValidationError("producer acceptance receipt issuer is not trusted")
    if receipt.get("authority_id") != trust_profile.value["authority_id"]:
        raise ValidationError("producer acceptance receipt authority is not trusted")
    if receipt["integrity"]["self_sha256"] != trusted["acceptance_receipt_self_sha256"]:
        raise IntegrityError("producer acceptance receipt trusted self hash mismatch")
    if sha256_bytes(raw) != trusted["acceptance_receipt_physical_sha256"]:
        raise IntegrityError("producer acceptance receipt trusted physical hash mismatch")
    _verify_common_authority_fields(
        receipt,
        producer=producer,
        role=role,
        run_id=run_id,
        phase_id=phase_id,
        split_id=split_id,
        label="producer acceptance receipt",
    )
    _verify_manifest_binding(
        receipt.get("package_set_manifest"), manifest_path, manifest,
        "producer acceptance receipt",
    )
    _verify_candidate_counts(receipt, candidates, "producer acceptance receipt")
    if receipt["candidate_set_sha256"] != trust_profile.value["parent_dataset"]["authorized_candidate_set_sha256"]:
        raise IntegrityError("producer acceptance cohort differs from trusted candidate set")
    _require_null_decision(receipt, "producer acceptance receipt")

    cohort_path, cohort = _bound_json(
        root, receipt.get("candidate_cohort"), "acceptance candidate cohort"
    )
    _require_exact_keys(cohort, _COHORT_FIELDS, "acceptance candidate cohort")
    if (
        cohort.get("schema_id") != COHORT_AUTHORITY_SCHEMA
        or cohort.get("schema_version") != AUTHORITY_SCHEMA_VERSION
    ):
        raise ValidationError("unsupported acceptance candidate cohort")
    _verify_run_fields(cohort, run_id, phase_id, split_id, "acceptance candidate cohort")
    _verify_candidate_counts(cohort, candidates, "acceptance candidate cohort")
    expected_identities = [
        item.identity.as_dict()
        for item in sorted(candidates, key=lambda item: item.identity.candidate_id)
    ]
    if cohort.get("candidates") != expected_identities:
        raise ValidationError("acceptance candidate cohort identity mismatch")
    _require_null_decision(cohort, "acceptance candidate cohort")

    approval_path, approval = _bound_json(
        root, receipt.get("approval_artifact"), "producer approval artifact"
    )
    _require_exact_keys(approval, _APPROVAL_FIELDS, "producer approval artifact")
    if (
        approval.get("schema_id") != APPROVAL_ARTIFACT_SCHEMA
        or approval.get("schema_version") != AUTHORITY_SCHEMA_VERSION
        or approval.get("status") != "APPROVED"
    ):
        raise ValidationError("unsupported or non-approved producer approval artifact")
    _verify_common_authority_fields(
        approval,
        producer=producer,
        role=role,
        run_id=run_id,
        phase_id=phase_id,
        split_id=split_id,
        label="producer approval artifact",
    )
    _verify_manifest_binding(
        approval.get("package_set_manifest"), manifest_path, manifest,
        "producer approval artifact",
    )
    if approval.get("candidate_cohort") != receipt.get("candidate_cohort"):
        raise IntegrityError("approval/receipt candidate cohort binding mismatch")
    _verify_candidate_counts(approval, candidates, "producer approval artifact")
    _require_null_decision(approval, "producer approval artifact")
    if approval.get("issuer_id") != receipt.get("issuer_id"):
        raise ValidationError("approval/receipt issuer mismatch")
    if approval.get("authority_id") != receipt.get("authority_id"):
        raise ValidationError("approval/receipt authority mismatch")
    if approval["integrity"]["self_sha256"] != trusted["approval_artifact_self_sha256"]:
        raise IntegrityError("producer approval trusted self hash mismatch")
    if sha256_file(approval_path) != trusted["approval_artifact_physical_sha256"]:
        raise IntegrityError("producer approval trusted physical hash mismatch")
    expected_producer = {
        field: trusted[field]
        for field in ("component_id", "component_version", "run_id", "commit", "tree")
    }
    if dict(producer) != expected_producer:
        raise ValidationError("producer Git/release identity is not trusted")
    return raw, receipt, (
        (receipt_path, receipt_path.name),
        (cohort_path, _descriptor_relative(receipt["candidate_cohort"])),
        (approval_path, _descriptor_relative(receipt["approval_artifact"])),
    )


def verify_producer_acceptance_receipt(
    receipt_path: Path,
    *,
    manifest_path: Path,
    role: str,
    candidates: Sequence[DatasetCandidate],
    run_id: str,
    phase_id: str,
    split_id: str,
    trust_profile: TrustedAuthorityProfile,
) -> dict[str, Any]:
    """Revalidate detached acceptance authority for a sealed manifest snapshot."""

    manifest = load_json(manifest_path, require_object=True)
    if (
        manifest.get("schema_id") != PACKAGE_SET_SCHEMA
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != COMPLETE_ACCEPTED
        or manifest.get("producer_role") != role
    ):
        raise ValidationError("sealed official producer manifest is not V2 COMPLETE_ACCEPTED")
    _verify_self_hash(manifest, "sealed producer package-set manifest")
    producer = _producer(manifest.get("producer"), legacy=False)
    _, receipt, _ = _verify_acceptance_receipt(
        receipt_path,
        manifest_path=manifest_path,
        manifest=manifest,
        producer=producer,
        role=role,
        candidates=candidates,
        run_id=run_id,
        phase_id=phase_id,
        split_id=split_id,
        trust_profile=trust_profile,
    )
    return receipt


def _verify_common_authority_fields(
    value: Mapping[str, Any],
    *,
    producer: Mapping[str, str],
    role: str,
    run_id: str,
    phase_id: str,
    split_id: str,
    label: str,
) -> None:
    _string(value.get("issuer_id"), f"{label} issuer_id")
    _string(value.get("authority_id"), f"{label} authority_id")
    _verify_run_fields(value, run_id, phase_id, split_id, label)
    if value.get("producer_role") != role or value.get("producer") != dict(producer):
        raise ValidationError(f"{label} producer authority mismatch")
    for field in ("commit", "tree"):
        observed = producer.get(field)
        if not isinstance(observed, str) or _HEX_40.fullmatch(observed) is None:
            raise ValidationError(f"{label} requires a full producer {field} Git OID")


def _verify_trusted_profile_run(
    profile: TrustedAuthorityProfile,
    *,
    run_id: str,
    phase_id: str,
    split_id: str,
) -> None:
    expected = profile.value
    if any(
        expected.get(field) != value
        for field, value in (
            ("run_id", run_id), ("phase_id", phase_id), ("split_id", split_id)
        )
    ):
        raise ValidationError("trusted authority profile run/phase/split mismatch")


def _verify_run_fields(
    value: Mapping[str, Any], run_id: str, phase_id: str, split_id: str, label: str
) -> None:
    expected = {"run_id": run_id, "phase_id": phase_id, "split_id": split_id}
    if any(value.get(field) != item for field, item in expected.items()):
        raise ValidationError(f"{label} run/phase/split binding mismatch")


def _verify_manifest_binding(
    descriptor_value: Any,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    label: str,
) -> None:
    descriptor = _mapping(descriptor_value, f"{label} package_set_manifest")
    _require_exact_keys(
        descriptor, {"physical_sha256", "self_sha256"},
        f"{label} package_set_manifest",
    )
    if descriptor.get("physical_sha256") != sha256_file(manifest_path):
        raise IntegrityError(f"{label} package-set physical binding mismatch")
    if descriptor.get("self_sha256") != manifest["integrity"]["self_sha256"]:
        raise IntegrityError(f"{label} package-set self binding mismatch")


def _verify_candidate_counts(
    value: Mapping[str, Any], candidates: Sequence[DatasetCandidate], label: str
) -> None:
    if value.get("candidate_count") != len(candidates):
        raise ValidationError(f"{label} candidate count mismatch")
    if value.get("candidate_set_sha256") != candidate_set_sha256(candidates):
        raise IntegrityError(f"{label} candidate-set hash mismatch")


def _require_null_decision(value: Mapping[str, Any], label: str) -> None:
    if value.get("final_glossary_decision") is not None:
        raise PolicyError(f"{label} contains a final glossary decision")


def _bound_json(root: Path, value: Any, label: str) -> tuple[Path, dict[str, Any]]:
    binding = _mapping(value, label)
    _require_exact_keys(binding, _BOUND_FILE_FIELDS, label)
    relative = safe_relative_path(_string(binding.get("relative_path"), f"{label} path"))
    path = ensure_no_symlink(root, relative)
    if not path.is_file() or binding.get("physical_sha256") != sha256_file(path):
        raise IntegrityError(f"{label} physical binding mismatch")
    payload = load_json(path, require_object=True)
    _verify_self_hash(payload, label)
    if binding.get("self_sha256") != payload["integrity"]["self_sha256"]:
        raise IntegrityError(f"{label} self-hash binding mismatch")
    return path, payload


def _descriptor_relative(value: Any) -> str:
    descriptor = _mapping(value, "bound file descriptor")
    return safe_relative_path(
        _string(descriptor.get("relative_path"), "bound file relative_path")
    ).as_posix()


def _validate_package(
    value: Mapping[str, Any],
    *,
    raw: bytes,
    path: Path,
    relative_path: str,
    physical: str,
    entry: Mapping[str, Any],
    role: str,
    identity: CandidateIdentity,
    producer: Mapping[str, str],
    schema_root: Path,
) -> ProducerItem:
    expected_schema = ROLE_SCHEMAS[role]
    if value.get("schema_id") != expected_schema or value.get("schema_version") != "1.1.0":
        raise ValidationError(f"producer package schema mismatch: {relative_path}")
    _verify_self_hash(value, relative_path)
    validate_contract_schema(dict(value), schema_root)
    if CandidateIdentity.from_package(value) != identity:
        raise ValidationError(f"producer package identity mismatch: {relative_path}")
    if value.get("final_glossary_decision") is not None:
        raise PolicyError(f"producer package owns a final decision: {relative_path}")
    if any(field in value for field in ("global_action", "global_decision", "action_policy")):
        raise PolicyError(f"producer package owns a Global field: {relative_path}")
    provenance = _mapping(value.get("provenance"), f"{relative_path} provenance")
    for field in ("component_id", "component_version", "run_id"):
        if provenance.get(field) != producer[field]:
            raise ValidationError(f"producer provenance mismatch for {field}: {relative_path}")
    declared = value["integrity"]["self_sha256"]
    if entry.get("self_sha256") != declared:
        raise IntegrityError(f"producer manifest self-hash mismatch: {relative_path}")
    return ProducerItem(
        role=role,
        identity=identity,
        kind="PACKAGE",
        path=path,
        relative_path=relative_path,
        raw=raw,
        value=dict(value),
        physical_sha256=physical,
        self_sha256=declared,
    )


def _producer(value: Any, *, legacy: bool) -> dict[str, str]:
    producer = _mapping(value, "producer")
    expected = _LEGACY_PRODUCER_FIELDS if legacy else _PRODUCER_FIELDS
    _require_exact_keys(producer, expected, "producer")
    return {
        field: _string(producer.get(field), f"producer.{field}")
        for field in sorted(expected)
    }


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


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ValidationError(f"{label} fields mismatch: missing={missing}, extra={extra}")


__all__ = [
    "ACCEPTANCE_RECEIPT_SCHEMA",
    "APPROVAL_ARTIFACT_SCHEMA",
    "COHORT_AUTHORITY_SCHEMA",
    "COMPLETE_ACCEPTED",
    "HISTORICAL_REPLAY_MODE",
    "LEGACY_PACKAGE_SET_SCHEMA",
    "PACKAGE_SET_SCHEMA",
    "NEW_INPUT_MODE",
    "ProducerItem",
    "ProducerSet",
    "SOURCE_MANIFEST_SCHEMA",
    "SYNTHETIC_COMPLETE",
    "candidate_set_sha256",
    "load_producer_set",
    "verify_producer_acceptance_receipt",
]
