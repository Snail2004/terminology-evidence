"""Portable replay verification for Dataset 15/150 adapter bundles."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from integration_harness.adapter_v1.dataset import OFFICIAL_MODE, load_dataset_release
from integration_harness.adapter_v1.producer import HOLD_SCHEMA, PACKAGE_SET_SCHEMA
from integration_harness.errors import IntegrityError, ReplayError
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.identity import CandidateIdentity
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
    hold_count = len(inventory.holds)
    if hold_count:
        _verify_dataset_artifacts(inventory, dataset)
        _verify_hold_join(inventory, dataset=dataset)
        semantic = "SEALED_ADAPTER_HOLD_REPLAY_PASS"
        joined_count = dataset.candidate_count
    else:
        joined, report = validate_and_join(inventory, schema_root=contracts_root)
        joined_count = report["joined_count"]
        if joined_count != dataset.candidate_count or len(joined) != dataset.candidate_count:
            raise ReplayError("sealed adapter exact join count mismatch")
        _verify_dataset_artifacts(inventory, dataset)
        semantic = "SEALED_ADAPTER_COMPLETE_REPLAY_PASS"
    report = load_json(bundle_root / "adapter_report.json", require_object=True)
    if report.get("integrity", {}).get("self_sha256") != self_sha256(report):
        raise ReplayError("adapter report self hash mismatch")
    if report.get("inventory_self_sha256") != manifest["integrity"]["self_sha256"]:
        raise ReplayError("adapter report inventory binding mismatch")
    if report.get("joined_count") != joined_count or report.get("hold_count") != hold_count:
        raise ReplayError("adapter report count binding mismatch")
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
        "hold_count": hold_count,
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
        "context_package_set_manifest",
        "attestation_package_set_manifest",
        "adapter_inventory_schema",
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
    _verify_dataset_artifacts(inventory, dataset)
    verify_producer_manifest_snapshot(
        source_paths["context_package_set_manifest"],
        inventory,
        role="context_evidence",
    )
    verify_producer_manifest_snapshot(
        source_paths["attestation_package_set_manifest"],
        inventory,
        role="attestation_evidence",
    )
    _verify_shared_effective_senses(inventory)
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
    hold_records = {
        record.candidate_key["candidate_id"]: record
        for record in inventory.holds
        if record.role == role
    }
    entries = value.get("entries")
    if not isinstance(entries, list):
        raise ReplayError(f"sealed producer manifest has no entries: {role}")
    if value.get("entry_count") != len(entries):
        raise ReplayError(f"sealed producer manifest entry count mismatch: {role}")
    package_count = sum(entry.get("kind") == "PACKAGE" for entry in entries if isinstance(entry, Mapping))
    hold_count = sum(entry.get("kind") == "HOLD" for entry in entries if isinstance(entry, Mapping))
    if value.get("package_count") != package_count or value.get("hold_count") != hold_count:
        raise ReplayError(f"sealed producer manifest package/HOLD counts mismatch: {role}")
    expected_status = "EXPLICIT_HOLD" if hold_count else None
    if expected_status is not None and value.get("status") != expected_status:
        raise ReplayError(f"sealed producer manifest HOLD status mismatch: {role}")
    if hold_count == 0 and value.get("status") not in {"COMPLETE_ACCEPTED", "SYNTHETIC_LOCAL_CONFORMANCE"}:
        raise ReplayError(f"sealed producer manifest complete status mismatch: {role}")
    observed: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ReplayError(f"sealed producer manifest entry is invalid: {role}")
        candidate_id = entry.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in observed:
            raise ReplayError(f"sealed producer manifest candidate is invalid: {role}")
        observed.add(candidate_id)
        if entry.get("kind") == "PACKAGE":
            record = package_records.get(candidate_id)
        elif entry.get("kind") == "HOLD":
            record = hold_records.get(candidate_id)
        else:
            raise ReplayError(f"sealed producer manifest entry kind is invalid: {role}")
        if record is None:
            raise ReplayError(f"sealed producer manifest entry is not materialized: {role}")
        if entry.get("physical_sha256") != record.physical_sha256:
            raise ReplayError(f"sealed producer package physical binding mismatch: {role}")
        if entry.get("self_sha256") != record.declared_self_sha256:
            raise ReplayError(f"sealed producer package self binding mismatch: {role}")
    if observed != set(package_records) | set(hold_records):
        raise ReplayError(f"sealed producer manifest candidate set mismatch: {role}")


def _verify_shared_effective_senses(inventory: ArtifactInventory) -> None:
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
    if any(count != 3 for count in candidates_by_self.values()):
        raise ReplayError("shared Effective Sense must bind exactly three candidates")
    if len(paths_by_self) != inventory.manifest.get("sense_count"):
        raise ReplayError("shared Effective Sense file count mismatch")


def _verify_dataset_artifacts(inventory: ArtifactInventory, dataset: Any) -> None:
    """Bind every sealed Dataset artifact to the independently verified ZIP."""

    expected = {candidate.identity.candidate_id: candidate for candidate in dataset.candidates}
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
    _verify_shared_effective_senses(inventory)

def _verify_hold_join(inventory: ArtifactInventory, *, dataset: Any) -> None:
    dataset_ids = {
        record.candidate_key["candidate_id"]
        for record in inventory.records
        if record.role == "frozen_candidate" and record.candidate_key is not None
    }
    expected = {candidate.identity.candidate_id: candidate.identity for candidate in dataset.candidates}
    if dataset_ids != set(expected):
        raise ReplayError("adapter HOLD replay has incomplete Dataset candidates")
    for hold in inventory.holds:
        value = load_json(hold.path, require_object=True)
        if value.get("schema_id") != HOLD_SCHEMA or value.get("producer_role") != hold.role:
            raise ReplayError("adapter HOLD schema mismatch")
        if value.get("integrity", {}).get("self_sha256") != self_sha256(value):
            raise ReplayError("adapter HOLD self hash mismatch")
        if value.get("final_glossary_decision") is not None:
            raise ReplayError("adapter HOLD contains a final decision")
        try:
            identity = CandidateIdentity.from_package(value)
        except Exception as exc:
            raise ReplayError("adapter HOLD identity is invalid") from exc
        candidate_id = identity.candidate_id
        if candidate_id not in expected or identity != expected[candidate_id]:
            raise ReplayError("adapter HOLD candidate is foreign")
        if hold.candidate_key != identity.as_dict():
            raise ReplayError("adapter HOLD inventory identity drift")
        if hold.declared_self_sha256 != value["integrity"]["self_sha256"]:
            raise ReplayError("adapter HOLD inventory self binding mismatch")
        if hold.physical_sha256 != sha256_file(hold.path):
            raise ReplayError("adapter HOLD inventory physical binding mismatch")
    for role in ("context_evidence", "attestation_evidence"):
        package_ids = {
            record.candidate_key["candidate_id"]
            for record in inventory.records
            if record.role == role and record.candidate_key is not None
        }
        hold_ids = {
            record.candidate_key["candidate_id"]
            for record in inventory.holds
            if record.role == role
        }
        if package_ids & hold_ids or package_ids | hold_ids != dataset_ids:
            raise ReplayError(f"adapter package/HOLD cardinality mismatch: {role}")


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
