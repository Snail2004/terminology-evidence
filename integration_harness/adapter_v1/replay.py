"""Portable replay verification for Dataset 15/150 adapter bundles."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from integration_harness.adapter_v1.availability import EXTERNAL_HOLD, PRESENT
from integration_harness.adapter_v1.dataset import OFFICIAL_MODE, load_dataset_release
from integration_harness.adapter_v1.producer import PACKAGE_SET_SCHEMA
from integration_harness.adapter_v1.sidecars import SidecarSet, verify_sidecars
from integration_harness.errors import IntegrityError, ReplayError
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.inventory import ADAPTER_INVENTORY_SCHEMA, ArtifactInventory, load_inventory
from integration_harness.join import validate_and_join
from integration_harness.jsonio import load_json
from integration_harness.paths import ensure_no_symlink, safe_relative_path


def replay_adapter_bundle(
    bundle_root: Path,
    *,
    contracts_root: Path,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    bundle_root = bundle_root.absolute()
    checksums = _verify_checksums(bundle_root)
    inventory = load_inventory(bundle_root / "artifact_inventory.json")
    manifest = inventory.manifest
    if manifest.get("schema_id") != ADAPTER_INVENTORY_SCHEMA:
        raise ReplayError("adapter bundle has the wrong inventory schema")
    sources = {record.role: record for record in inventory.source_authority}
    source_paths = {role: record.path for role, record in sources.items()}
    dataset = verify_adapter_inventory_source_binding(
        inventory,
        source_paths=source_paths,
        contracts_root=contracts_root,
        repository_root=repository_root,
    )
    sidecar_stats = _verify_sidecar_sources(
        inventory,
        source_paths=source_paths,
        dataset=dataset,
    )
    ready_count = sidecar_stats["ready_count"]
    not_submitted_count = sidecar_stats["not_submitted_count"]
    ready_ids = frozenset(sidecar_stats["ready_candidate_ids"])
    _verify_dataset_artifacts(inventory, dataset, expected_ids=ready_ids)
    _verify_availability_artifact_projection(
        inventory,
        availability=sidecar_stats["availability"],
        source_paths=source_paths,
    )
    if ready_count:
        joined, report = validate_and_join(inventory, schema_root=contracts_root)
        joined_count = report["joined_count"]
        if joined_count != ready_count or len(joined) != ready_count:
            raise ReplayError("sealed adapter exact join count mismatch")
    else:
        joined_count = 0
        if inventory.records:
            raise ReplayError("adapter with zero ready candidates materialized evidence artifacts")
    if not_submitted_count:
        semantic = "SEALED_ADAPTER_AVAILABILITY_HOLD_REPLAY_PASS"
    else:
        semantic = "SEALED_ADAPTER_COMPLETE_REPLAY_PASS"
    report = load_json(bundle_root / "adapter_report.json", require_object=True)
    if report.get("integrity", {}).get("self_sha256") != self_sha256(report):
        raise ReplayError("adapter report self hash mismatch")
    if report.get("inventory_self_sha256") != manifest["integrity"]["self_sha256"]:
        raise ReplayError("adapter report inventory binding mismatch")
    if report.get("joined_count") != joined_count:
        raise ReplayError("adapter report count binding mismatch")
    if report.get("ready_candidate_count") != ready_count:
        raise ReplayError("adapter report ready count binding mismatch")
    if report.get("not_submitted_count") != not_submitted_count:
        raise ReplayError("adapter report not-submitted count binding mismatch")
    if any(
        report.get(field) != 0
        for field in (
            "network_calls",
            "provider_calls",
            "auto_approved_count",
            "certificate_count",
        )
    ):
        raise ReplayError("adapter report violates zero-provider development invariants")
    if report.get("final_glossary_decision") is not None:
        raise ReplayError("adapter report contains a final glossary decision")
    return {
        "status": "PASS",
        "semantic_replay": semantic,
        "candidate_count": dataset.candidate_count,
        "sense_count": dataset.sense_count,
        "joined_count": joined_count,
        "ready_candidate_count": ready_count,
        "not_submitted_count": not_submitted_count,
        "availability_counts": sidecar_stats["status_counts"],
        "checksum_file_count": len(checksums),
        "network_calls": 0,
        "provider_calls": 0,
        "auto_approved_count": 0,
        "certificate_count": 0,
    }


def verify_adapter_inventory_source_binding(
    inventory: ArtifactInventory,
    *,
    source_paths: Mapping[str, Path],
    contracts_root: Path,
    repository_root: Path | None = None,
):
    """Revalidate public source bindings for either a bundle or a sealed run."""

    manifest = inventory.manifest
    _validate_inventory_schema(inventory)
    required = {
        "dataset_zip",
        "dataset_pin",
        "dataset_manifest",
        "dataset_candidate_index",
        "adapter_inventory_schema",
        "availability_intake_manifest",
        "harness_cohort_inventory",
        "global_batch_authority",
        "evidence_availability_manifest",
        "global_batch_readiness_report",
        "harness_cohort_inventory_schema",
        "global_batch_authority_schema",
        "evidence_availability_manifest_schema",
        "global_batch_readiness_report_schema",
    }
    if manifest.get("adapter_mode") == OFFICIAL_MODE:
        required.add("dataset_git_receipt")
    if not required.issubset(source_paths):
        raise ReplayError("adapter bundle is missing required source authority")
    dataset = load_dataset_release(
        source_paths["dataset_zip"],
        source_paths["dataset_pin"],
        git_receipt_path=(
            source_paths["dataset_git_receipt"]
            if "dataset_git_receipt" in source_paths
            else None
        ),
        schema_root=contracts_root,
        mode=manifest["adapter_mode"],
        repository_root=repository_root,
    )
    if dataset.manifest_raw != source_paths["dataset_manifest"].read_bytes():
        raise ReplayError("sealed Dataset manifest copy differs from ZIP")
    if dataset.index_raw != source_paths["dataset_candidate_index"].read_bytes():
        raise ReplayError("sealed Dataset candidate index copy differs from ZIP")
    if dataset.candidate_count != manifest.get("candidate_count"):
        raise ReplayError("replayed Dataset candidate count mismatch")
    if dataset.sense_count != manifest.get("sense_count"):
        raise ReplayError("replayed Dataset sense count mismatch")
    return dataset


def _validate_inventory_schema(inventory: ArtifactInventory) -> None:
    schema_record = next(
        (
            record
            for record in inventory.source_authority
            if record.role == "adapter_inventory_schema"
        ),
        None,
    )
    if schema_record is None:
        raise ReplayError("adapter inventory schema binding is missing")
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover
        raise ReplayError("jsonschema is required for adapter replay") from exc
    schema = load_json(schema_record.path, require_object=True)
    try:
        jsonschema.Draft202012Validator(schema).validate(inventory.manifest)
    except jsonschema.ValidationError as exc:
        raise ReplayError(f"adapter inventory schema validation failed: {exc.message}") from exc


def _verify_sidecar_sources(
    inventory: ArtifactInventory,
    *,
    source_paths: Mapping[str, Path],
    dataset: Any,
) -> dict[str, Any]:
    source_records = {record.role: record for record in inventory.source_authority}
    expected_sidecar_roles = {
        "harness_cohort_inventory",
        "global_batch_authority",
        "evidence_availability_manifest",
        "global_batch_readiness_report",
    }
    bindings = inventory.manifest.get("sidecar_bindings")
    if not isinstance(bindings, Mapping) or set(bindings) != expected_sidecar_roles:
        raise ReplayError("adapter sidecar binding surface mismatch")
    for role in sorted(expected_sidecar_roles):
        binding = bindings.get(role)
        source_record = source_records.get(role)
        if not isinstance(binding, Mapping) or source_record is None:
            raise ReplayError(f"adapter sidecar source is missing: {role}")
        if binding.get("relative_path") != source_record.relative_path:
            raise ReplayError(f"adapter sidecar path binding mismatch: {role}")
        if binding.get("physical_sha256") != source_record.physical_sha256:
            raise ReplayError(f"adapter sidecar physical binding mismatch: {role}")
        if binding.get("self_sha256") != source_record.declared_self_sha256:
            raise ReplayError(f"adapter sidecar self binding mismatch: {role}")
    sidecars = SidecarSet(
        cohort=load_json(source_paths["harness_cohort_inventory"], require_object=True),
        authority=load_json(source_paths["global_batch_authority"], require_object=True),
        availability=load_json(
            source_paths["evidence_availability_manifest"], require_object=True
        ),
        readiness=load_json(
            source_paths["global_batch_readiness_report"], require_object=True
        ),
    )
    for value, schema_role in (
        (sidecars.cohort, "harness_cohort_inventory_schema"),
        (sidecars.authority, "global_batch_authority_schema"),
        (sidecars.availability, "evidence_availability_manifest_schema"),
        (sidecars.readiness, "global_batch_readiness_report_schema"),
    ):
        _validate_jsonschema(value, source_paths[schema_role], schema_role)
    physical = {
        "cohort": sha256_file(source_paths["harness_cohort_inventory"]),
        "authority": sha256_file(source_paths["global_batch_authority"]),
        "availability": sha256_file(source_paths["evidence_availability_manifest"]),
        "readiness": sha256_file(source_paths["global_batch_readiness_report"]),
    }
    stats = verify_sidecars(sidecars, dataset=dataset, physical_hashes=physical)
    intake = load_json(source_paths["availability_intake_manifest"], require_object=True)
    if intake.get("integrity", {}).get("self_sha256") != self_sha256(intake):
        raise ReplayError("availability intake self hash mismatch")
    intake_rows = {
        (row["candidate_key"]["candidate_id"], row["role"]): {
            key: row.get(key)
            for key in (
                "candidate_key",
                "role",
                "status",
                "observed_at",
                "reason_code",
                "validation_error_code",
            )
        }
        for row in intake.get("rows", [])
        if isinstance(row, Mapping) and isinstance(row.get("candidate_key"), Mapping)
    }
    output_rows = {
        (row["candidate_key"]["candidate_id"], row["role"]): {
            key: row.get(key)
            for key in (
                "candidate_key",
                "role",
                "status",
                "observed_at",
                "reason_code",
                "validation_error_code",
            )
        }
        for row in sidecars.availability.get("rows", [])
        if isinstance(row, Mapping) and isinstance(row.get("candidate_key"), Mapping)
    }
    if intake_rows != output_rows:
        raise ReplayError("availability intake/output semantic projection drift")
    ready_ids = sidecars.readiness.get("ready_for_global_candidate_ids")
    if not isinstance(ready_ids, list):
        raise ReplayError("readiness report has no ready candidate list")
    return {
        **stats,
        "ready_candidate_ids": ready_ids,
        "availability": sidecars.availability,
    }


def _validate_jsonschema(
    value: Mapping[str, Any],
    schema_path: Path,
    label: str,
) -> None:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover
        raise ReplayError("jsonschema is required for sidecar replay") from exc
    schema = load_json(schema_path, require_object=True)
    try:
        jsonschema.Draft202012Validator(schema).validate(value)
    except jsonschema.ValidationError as exc:
        raise ReplayError(f"{label} validation failed: {exc.message}") from exc


def _verify_availability_artifact_projection(
    inventory: ArtifactInventory,
    *,
    availability: Mapping[str, Any],
    source_paths: Mapping[str, Path],
) -> None:
    records = {
        (record.candidate_key["candidate_id"], record.role): record
        for record in inventory.records
        if record.role in {"context_evidence", "attestation_evidence"}
        and record.candidate_key is not None
    }
    source_records = {record.role: record for record in inventory.source_authority}
    for row in availability.get("rows", []):
        if not isinstance(row, Mapping) or not isinstance(row.get("candidate_key"), Mapping):
            raise ReplayError("availability output row is invalid")
        key = (row["candidate_key"]["candidate_id"], row.get("role"))
        package = row.get("package")
        receipt = row.get("external_hold_receipt")
        if row.get("status") == PRESENT:
            if not isinstance(package, Mapping):
                raise ReplayError("PRESENT availability row has no package binding")
            record = records.get(key)
            if record is None:
                source_role = f"availability_present_{key[1]}_{key[0]}"
                source_record = source_records.get(source_role)
                if source_record is None:
                    raise ReplayError("PRESENT availability package is not materialized")
                observed_physical = source_record.physical_sha256
                observed_self = source_record.declared_self_sha256
                observed_relative = source_record.relative_path
                package_value = load_json(source_record.path, require_object=True)
            else:
                observed_physical = record.physical_sha256
                observed_self = record.declared_self_sha256
                observed_relative = record.relative_path
                package_value = load_json(record.path, require_object=True)
            if package.get("relative_path") != observed_relative:
                raise ReplayError("PRESENT availability package path binding mismatch")
            if package.get("physical_sha256") != observed_physical:
                raise ReplayError("PRESENT availability package physical binding mismatch")
            if package.get("self_sha256") != observed_self:
                raise ReplayError("PRESENT availability package self binding mismatch")
            provenance = package_value.get("provenance")
            expected_producer = {
                field: provenance.get(field) if isinstance(provenance, Mapping) else None
                for field in ("component_id", "component_version", "run_id")
            }
            if package.get("producer") != expected_producer:
                raise ReplayError("PRESENT availability producer binding mismatch")
        elif package is not None:
            raise ReplayError("non-PRESENT availability row contains a package")
        if row.get("status") == EXTERNAL_HOLD:
            if not isinstance(receipt, Mapping):
                raise ReplayError("EXTERNAL_HOLD row has no receipt binding")
            source_role = f"external_hold_receipt_{key[1]}_{key[0]}"
            source_record = source_records.get(source_role)
            if source_record is None:
                raise ReplayError("EXTERNAL_HOLD receipt is not sealed")
            if receipt.get("relative_path") != source_record.relative_path:
                raise ReplayError("EXTERNAL_HOLD receipt path binding mismatch")
            if receipt.get("physical_sha256") != source_record.physical_sha256:
                raise ReplayError("EXTERNAL_HOLD receipt physical binding mismatch")
            if receipt.get("self_sha256") != source_record.declared_self_sha256:
                raise ReplayError("EXTERNAL_HOLD receipt self binding mismatch")
        elif receipt is not None:
            raise ReplayError("non-EXTERNAL_HOLD row contains a hold receipt")
    declared_sets = availability.get("producer_sets")
    if not isinstance(declared_sets, list):
        raise ReplayError("availability producer set bindings are missing")
    set_by_role: dict[str, Mapping[str, Any]] = {}
    for value in declared_sets:
        if not isinstance(value, Mapping):
            raise ReplayError("availability producer set binding is invalid")
        role = value.get("role")
        if not isinstance(role, str) or role in set_by_role:
            raise ReplayError("availability producer set role is invalid")
        set_by_role[role] = value
    present_roles: set[str] = set()
    for role, source_path in (
        ("context_evidence", source_paths.get("context_package_set_manifest")),
        ("attestation_evidence", source_paths.get("attestation_package_set_manifest")),
    ):
        has_present = any(
            row.get("role") == role and row.get("status") == PRESENT
            for row in availability.get("rows", [])
            if isinstance(row, Mapping)
        )
        if has_present:
            present_roles.add(role)
            if source_path is None:
                raise ReplayError(f"PRESENT availability lacks producer set manifest: {role}")
            declared = set_by_role.get(role)
            source_value = load_json(source_path, require_object=True)
            if not isinstance(declared, Mapping):
                raise ReplayError(f"availability producer set binding is missing: {role}")
            if declared.get("manifest_self_sha256") != source_value.get("integrity", {}).get("self_sha256"):
                raise ReplayError(f"availability producer set self binding mismatch: {role}")
            if declared.get("manifest_physical_sha256") != sha256_file(source_path):
                raise ReplayError(f"availability producer set physical binding mismatch: {role}")
            if declared.get("producer") != source_value.get("producer"):
                raise ReplayError(f"availability producer set provenance mismatch: {role}")
            verify_producer_manifest_snapshot(source_path, inventory, role=role)
        elif source_path is not None:
            raise ReplayError(f"unused producer set manifest is sealed: {role}")
    if set(set_by_role) != present_roles:
        raise ReplayError("availability producer set bindings do not match PRESENT roles")


def verify_producer_manifest_snapshot(
    manifest_path: Path,
    inventory: ArtifactInventory,
    *,
    role: str,
) -> None:
    value = load_json(manifest_path, require_object=True)
    if value.get("schema_id") != PACKAGE_SET_SCHEMA:
        raise ReplayError(f"sealed producer manifest schema mismatch: {role}")
    if value.get("schema_version") != "1.0.0":
        raise ReplayError(f"sealed producer manifest version mismatch: {role}")
    if value.get("producer_role") != role:
        raise ReplayError(f"sealed producer manifest role mismatch: {role}")
    if value.get("final_glossary_decision") is not None or value.get("global_action") is not None:
        raise ReplayError(f"sealed producer manifest owns a forbidden decision: {role}")
    if value.get("integrity", {}).get("self_sha256") != self_sha256(value):
        raise ReplayError(f"sealed producer manifest self hash mismatch: {role}")
    package_records = {
        record.candidate_key["candidate_id"]: record
        for record in inventory.records
        if record.role == role and record.candidate_key is not None
    }
    source_prefix = f"availability_present_{role}_"
    source_package_records = {
        record.role[len(source_prefix):]: record
        for record in inventory.source_authority
        if record.role.startswith(source_prefix)
    }
    entries = value.get("entries")
    if not isinstance(entries, list):
        raise ReplayError(f"sealed producer manifest has no entries: {role}")
    if value.get("entry_count") != len(entries):
        raise ReplayError(f"sealed producer manifest entry count mismatch: {role}")
    package_count = sum(
        entry.get("kind") == "PACKAGE"
        for entry in entries
        if isinstance(entry, Mapping)
    )
    if package_count != len(entries) or value.get("package_count") != package_count:
        raise ReplayError(f"sealed producer manifest package count mismatch: {role}")
    if value.get("hold_count") != 0:
        raise ReplayError(f"sealed producer manifest contains fake HOLD packages: {role}")
    if value.get("status") not in {"COMPLETE_ACCEPTED", "SYNTHETIC_LOCAL_CONFORMANCE"}:
        raise ReplayError(f"sealed producer manifest complete status mismatch: {role}")
    observed: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ReplayError(f"sealed producer manifest entry is invalid: {role}")
        candidate_id = entry.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in observed:
            raise ReplayError(f"sealed producer manifest candidate is invalid: {role}")
        observed.add(candidate_id)
        if entry.get("kind") != "PACKAGE":
            raise ReplayError(f"sealed producer manifest entry kind is invalid: {role}")
        record = package_records.get(candidate_id) or source_package_records.get(candidate_id)
        if record is None:
            raise ReplayError(f"sealed producer manifest entry is not materialized: {role}")
        if entry.get("physical_sha256") != record.physical_sha256:
            raise ReplayError(f"sealed producer package physical binding mismatch: {role}")
        if entry.get("self_sha256") != record.declared_self_sha256:
            raise ReplayError(f"sealed producer package self binding mismatch: {role}")
    if observed != set(package_records) | set(source_package_records):
        raise ReplayError(f"sealed producer manifest candidate set mismatch: {role}")


def _verify_shared_effective_senses(
    inventory: ArtifactInventory,
    *,
    expected_candidates_by_self: Mapping[str, int],
) -> None:
    records = [record for record in inventory.records if record.role == "effective_sense"]
    paths_by_self: dict[str, set[str]] = {}
    candidates_by_self: Counter[str] = Counter()
    for record in records:
        declared = record.declared_self_sha256
        if not isinstance(declared, str):
            raise ReplayError("Effective Sense record has no declared self hash")
        paths_by_self.setdefault(declared, set()).add(record.relative_path)
        candidates_by_self[declared] += 1
    if any(len(paths) != 1 for paths in paths_by_self.values()):
        raise ReplayError("one Effective Sense identity maps to multiple physical paths")
    if dict(candidates_by_self) != dict(expected_candidates_by_self):
        raise ReplayError("shared Effective Sense candidate binding count mismatch")
    if len(paths_by_self) != len(expected_candidates_by_self):
        raise ReplayError("shared Effective Sense file count mismatch")


def _verify_dataset_artifacts(
    inventory: ArtifactInventory,
    dataset: Any,
    *,
    expected_ids: frozenset[str],
) -> None:
    """Bind every sealed Dataset artifact to the independently verified ZIP."""

    all_candidates = {
        candidate.identity.candidate_id: candidate for candidate in dataset.candidates
    }
    if not expected_ids.issubset(all_candidates):
        raise ReplayError("readiness report contains a foreign candidate")
    expected = {candidate_id: all_candidates[candidate_id] for candidate_id in expected_ids}
    observed: dict[str, dict[str, Any]] = {role: {} for role in ("effective_sense", "frozen_candidate", "constraints")}
    for record in inventory.records:
        if record.role not in observed:
            continue
        if not isinstance(record.candidate_key, Mapping):
            raise ReplayError(f"Dataset artifact has no candidate identity: {record.relative_path}")
        candidate_id = record.candidate_key.get("candidate_id")
        candidate = expected.get(candidate_id)
        if candidate is None:
            raise ReplayError(f"Dataset artifact is foreign: {record.relative_path}")
        if dict(record.candidate_key) != candidate.identity.as_dict():
            raise ReplayError(f"Dataset artifact identity drift: {record.relative_path}")
        if candidate_id in observed[record.role]:
            raise ReplayError(f"duplicate Dataset artifact: {record.role}/{candidate_id}")
        if record.role == "effective_sense":
            raw = candidate.effective_raw
            declared = candidate.effective["integrity"]["self_sha256"]
        elif record.role == "frozen_candidate":
            raw = candidate.frozen_raw
            declared = candidate.frozen["integrity"]["self_sha256"]
        else:
            raw = candidate.constraint_raw
            declared = candidate.constraint["integrity"]["self_sha256"]
        if record.physical_sha256 != sha256_file(record.path) or record.physical_sha256 != sha256_bytes(raw):
            raise ReplayError(f"Dataset artifact bytes drift: {record.relative_path}")
        if record.declared_self_sha256 != declared:
            raise ReplayError(f"Dataset artifact self identity drift: {record.relative_path}")
        observed[record.role][candidate_id] = record
    for role, records in observed.items():
        if set(records) != set(expected):
            raise ReplayError(f"Dataset artifact cardinality mismatch: {role}")
    expected_candidates_by_self = Counter(
        candidate.effective["integrity"]["self_sha256"]
        for candidate in expected.values()
    )
    _verify_shared_effective_senses(
        inventory,
        expected_candidates_by_self=expected_candidates_by_self,
    )


def _verify_checksums(root: Path) -> dict[str, str]:
    path = root / "CHECKSUMS.sha256"
    if not path.is_file():
        raise ReplayError("adapter bundle has no CHECKSUMS.sha256")
    entries: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    relative_paths: list[str] = []
    for line in lines:
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise ReplayError("malformed adapter checksum line")
        digest, relative_text = parts
        relative = safe_relative_path(relative_text)
        target = ensure_no_symlink(root, relative)
        if not target.is_file() or sha256_file(target) != digest:
            raise ReplayError(f"adapter checksum mismatch: {relative_text}")
        if relative_text in entries:
            raise ReplayError("duplicate adapter checksum path")
        entries[relative_text] = digest
        relative_paths.append(relative_text)
    if relative_paths != sorted(relative_paths):
        raise ReplayError("adapter checksums are not sorted")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    }
    if set(entries) != actual:
        raise ReplayError("adapter checksum inventory mismatch")
    return entries


__all__ = [
    "replay_adapter_bundle",
    "verify_adapter_inventory_source_binding",
    "verify_producer_manifest_snapshot",
]
