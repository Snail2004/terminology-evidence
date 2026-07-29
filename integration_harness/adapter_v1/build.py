"""Atomic materialization of a Dataset/C/E adapter inventory and audit seal."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Iterable

from integration_harness.adapter_v1.dataset import (
    OFFICIAL_MODE,
    SYNTHETIC_MODE,
    DatasetCandidate,
    DatasetRelease,
    load_dataset_release,
)
from integration_harness.adapter_v1.producer import ProducerItem, ProducerSet, load_producer_set
from integration_harness.errors import IntegrityError, PolicyError, StorageError
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.inventory import ADAPTER_INVENTORY_SCHEMA, load_inventory
from integration_harness.join import validate_and_join
from integration_harness.jsonio import dump_json, loads_strict
from integration_harness.paths import ensure_plain_root, relative_posix


ADAPTER_STATUS_READY_15 = "READY_FOR_15_CANDIDATE_ZERO_PROVIDER_RUN"
ADAPTER_STATUS_HOLD_15 = "READY_FOR_15_CANDIDATE_ZERO_PROVIDER_PREFLIGHT"
ADAPTER_STATUS_SYNTHETIC_150 = "SYNTHETIC_150_CANDIDATE_CONFORMANCE_PASS"
GLOBAL_READY = "READY_FOR_PUBLIC_GLOBAL_CLI"
GLOBAL_HOLD = "HOLD_EXPLICIT_PRODUCER_PACKAGE"


def build_adapter_bundle(
    *,
    dataset_zip: Path,
    dataset_pin: Path,
    dataset_git_receipt: Path | None,
    context_set_manifest: Path,
    attestation_set_manifest: Path,
    contracts_root: Path,
    repository_root: Path,
    output_root: Path,
    adapter_mode: str,
    allowed_hold_roles: frozenset[str] = frozenset(),
    inventory_schema_path: Path | None = None,
) -> dict[str, Any]:
    """Build a byte-preserving adapter bundle; never invokes Global or a provider."""

    output_root = output_root.absolute()
    parent = ensure_plain_root(output_root.parent)
    if output_root.exists():
        raise StorageError(f"refusing to overwrite adapter bundle: {output_root}")
    contracts_root = ensure_plain_root(contracts_root)
    repository_root = ensure_plain_root(repository_root)
    dataset = load_dataset_release(
        dataset_zip,
        dataset_pin,
        git_receipt_path=dataset_git_receipt,
        schema_root=contracts_root,
        mode=adapter_mode,
        repository_root=repository_root if adapter_mode == OFFICIAL_MODE else None,
    )
    context = load_producer_set(
        context_set_manifest,
        role="context_evidence",
        candidates=dataset.candidates,
        schema_root=contracts_root,
        adapter_mode=adapter_mode,
        allowed_hold_roles=allowed_hold_roles,
    )
    attestation = load_producer_set(
        attestation_set_manifest,
        role="attestation_evidence",
        candidates=dataset.candidates,
        schema_root=contracts_root,
        adapter_mode=adapter_mode,
        allowed_hold_roles=allowed_hold_roles,
    )
    temp = parent / f".{output_root.name}.tmp-{uuid.uuid4().hex}"
    temp.mkdir()
    try:
        manifest = _materialize(
            temp,
            dataset=dataset,
            context=context,
            attestation=attestation,
            inventory_schema_path=inventory_schema_path,
        )
        inventory_path = temp / "artifact_inventory.json"
        inventory = load_inventory(inventory_path)
        holds = len(inventory.holds)
        if holds:
            join_status = GLOBAL_HOLD
            joined_count = dataset.candidate_count
        else:
            joined, report = validate_and_join(inventory, schema_root=contracts_root)
            joined_count = report["joined_count"]
            if joined_count != dataset.candidate_count or len(joined) != dataset.candidate_count:
                raise IntegrityError("adapter runtime join count mismatch")
            join_status = GLOBAL_READY
        report = {
            "schema_id": "HarnessDataset50150AdapterReportV1",
            "schema_version": "1.0.0",
            "status": manifest["status"],
            "adapter_mode": adapter_mode,
            "candidate_count": dataset.candidate_count,
            "sense_count": dataset.sense_count,
            "joined_count": joined_count,
            "hold_count": holds,
            "shared_effective_sense_file_count": dataset.sense_count,
            "global_execution_status": join_status,
            "global_mode": "DEVELOPMENT_HEURISTIC",
            "network_calls": 0,
            "provider_calls": 0,
            "auto_approved_count": 0,
            "certificate_count": 0,
            "final_glossary_decision": None,
            "inventory_self_sha256": manifest["integrity"]["self_sha256"],
            "integrity": {},
        }
        report["integrity"]["self_sha256"] = self_sha256(report)
        dump_json(temp / "adapter_report.json", report)
        _write_checksums(temp)
        temp.replace(output_root)
    except Exception:
        if temp.parent == parent and temp.name.startswith(f".{output_root.name}.tmp-"):
            shutil.rmtree(temp, ignore_errors=True)
        raise
    return {
        "status": manifest["status"],
        "output_root": str(output_root),
        "inventory_path": str(output_root / "artifact_inventory.json"),
        "candidate_count": dataset.candidate_count,
        "sense_count": dataset.sense_count,
        "hold_count": holds,
        "global_execution_status": join_status,
        "network_calls": 0,
        "provider_calls": 0,
        "auto_approved_count": 0,
        "certificate_count": 0,
    }


def _materialize(
    root: Path,
    *,
    dataset: DatasetRelease,
    context: ProducerSet,
    attestation: ProducerSet,
    inventory_schema_path: Path | None,
) -> dict[str, Any]:
    source_records: list[dict[str, Any]] = []
    _write_bound_source(
        root,
        source_records,
        role="dataset_zip",
        relative="source_authority/dataset/release.zip",
        raw=dataset.zip_raw,
    )
    _write_bound_source(
        root,
        source_records,
        role="dataset_pin",
        relative="source_authority/dataset/input_pin.json",
        raw=dataset.pin_raw,
        declared_self=dataset.pin["integrity"]["self_sha256"],
    )
    _write_bound_source(
        root,
        source_records,
        role="dataset_manifest",
        relative="source_authority/dataset/manifest.json",
        raw=dataset.manifest_raw,
        declared_self=dataset.manifest["manifest_sha256"],
    )
    _write_bound_source(
        root,
        source_records,
        role="dataset_candidate_index",
        relative="source_authority/dataset/candidate_index.json",
        raw=dataset.index_raw,
        declared_self=dataset.index["integrity"]["self_sha256"],
    )
    if dataset.git_receipt_raw is not None and dataset.git_receipt is not None:
        _write_bound_source(
            root,
            source_records,
            role="dataset_git_receipt",
            relative="source_authority/dataset/git_source_receipt.json",
            raw=dataset.git_receipt_raw,
            declared_self=dataset.git_receipt["integrity"]["self_sha256"],
        )
    _copy_producer_authority(root, source_records, context)
    _copy_producer_authority(root, source_records, attestation)
    if inventory_schema_path is not None:
        schema_raw = inventory_schema_path.read_bytes()
        _write_bound_source(
            root,
            source_records,
            role="adapter_inventory_schema",
            relative="source_authority/harness/artifact_inventory_50_150_schema.json",
            raw=schema_raw,
        )

    context_by_id = {item.identity.candidate_id: item for item in context.items}
    attestation_by_id = {item.identity.candidate_id: item for item in attestation.items}
    artifacts: list[dict[str, Any]] = []
    holds: list[dict[str, Any]] = []
    effective_materialized: dict[str, tuple[str, bytes]] = {}
    dataset_commit = (
        dataset.git_receipt["producer"]["commit"]
        if dataset.git_receipt is not None
        else "synthetic-local-conformance"
    )
    for candidate in dataset.candidates:
        identity = candidate.identity.as_dict()
        effective_sha = candidate.effective["integrity"]["self_sha256"]
        effective_relative = f"packages/shared/effective_sense/{effective_sha}.json"
        existing = effective_materialized.get(effective_sha)
        if existing is None:
            _write_bytes(root / effective_relative, candidate.effective_raw)
            effective_materialized[effective_sha] = (
                effective_relative,
                candidate.effective_raw,
            )
        elif existing[1] != candidate.effective_raw:
            raise IntegrityError("shared Effective Sense bytes drift for one self hash")
        artifacts.append(
            _artifact_record(
                role="effective_sense",
                relative=effective_relative,
                value=candidate.effective,
                raw=candidate.effective_raw,
                producer="dataset",
                producer_commit=dataset_commit,
                candidate_key=identity,
            )
        )
        candidate_root = f"packages/candidates/{candidate.identity.candidate_id}"
        for role, name, value, raw in (
            ("frozen_candidate", "frozen_candidate.json", candidate.frozen, candidate.frozen_raw),
            ("constraints", "constraint_evidence.json", candidate.constraint, candidate.constraint_raw),
        ):
            relative = f"{candidate_root}/{name}"
            _write_bytes(root / relative, raw)
            artifacts.append(
                _artifact_record(
                    role=role,
                    relative=relative,
                    value=value,
                    raw=raw,
                    producer="dataset",
                    producer_commit=dataset_commit,
                    candidate_key=identity,
                )
            )
        for item in (context_by_id[candidate.identity.candidate_id], attestation_by_id[candidate.identity.candidate_id]):
            if item.kind == "PACKAGE":
                relative = f"{candidate_root}/{item.role}.json"
                _write_bytes(root / relative, item.raw)
                artifacts.append(
                    _artifact_record(
                        role=item.role,
                        relative=relative,
                        value=item.value,
                        raw=item.raw,
                        producer=item.value["provenance"]["component_id"],
                        producer_commit=(
                            context.manifest["producer"]["commit"]
                            if item.role == "context_evidence"
                            else attestation.manifest["producer"]["commit"]
                        ),
                        candidate_key=identity,
                    )
                )
            else:
                relative = f"holds/{item.role}/{candidate.identity.candidate_id}.json"
                _write_bytes(root / relative, item.raw)
                holds.append(
                    {
                        "role": item.role,
                        "candidate_key": identity,
                        "relative_path": relative,
                        "physical_sha256": sha256_bytes(item.raw),
                        "declared_self_sha256": item.self_sha256,
                    }
                )
    holds.sort(key=lambda item: (item["role"], item["candidate_key"]["candidate_id"]))
    artifacts.sort(
        key=lambda item: (
            item["candidate_key"]["candidate_id"],
            item["role"],
            item["relative_path"],
        )
    )
    global_status = GLOBAL_HOLD if holds else GLOBAL_READY
    if dataset.mode == OFFICIAL_MODE:
        status = ADAPTER_STATUS_HOLD_15 if holds else ADAPTER_STATUS_READY_15
    elif dataset.mode == SYNTHETIC_MODE:
        status = ADAPTER_STATUS_SYNTHETIC_150
    else:  # pragma: no cover - Dataset verifier already rejects it
        raise PolicyError("unsupported adapter mode")
    manifest = {
        "schema_id": ADAPTER_INVENTORY_SCHEMA,
        "schema_version": "1.0.0",
        "adapter_mode": dataset.mode,
        "status": status,
        "candidate_count": dataset.candidate_count,
        "sense_count": dataset.sense_count,
        "dataset_binding": {
            "pin_self_sha256": dataset.pin["integrity"]["self_sha256"],
            "zip_physical_sha256": sha256_bytes(dataset.zip_raw),
            "manifest_self_sha256": dataset.manifest["manifest_sha256"],
            "manifest_physical_sha256": sha256_bytes(dataset.manifest_raw),
            "producer_commit": dataset_commit,
            "excluded_later_commit": (
                dataset.git_receipt["version_exclusions"][
                    "later_dataset_commit_not_accepted_by_this_receipt"
                ]
                if dataset.git_receipt is not None
                else None
            ),
        },
        "producer_sets": [
            _producer_summary(context),
            _producer_summary(attestation),
        ],
        "source_authority": sorted(source_records, key=lambda item: item["role"]),
        "artifacts": artifacts,
        "holds": holds,
        "global_execution": {
            "status": global_status,
            "mode": "DEVELOPMENT_HEURISTIC",
            "network_policy": "FORBIDDEN",
            "approval_score": None,
            "auto_approved_count": 0,
            "certificate_count": 0,
        },
        "final_glossary_decision": None,
        "integrity": {},
    }
    manifest["integrity"]["self_sha256"] = self_sha256(manifest)
    dump_json(root / "artifact_inventory.json", manifest)
    return manifest


def _copy_producer_authority(
    root: Path,
    records: list[dict[str, Any]],
    producer: ProducerSet,
) -> None:
    prefix = "context" if producer.role == "context_evidence" else "attestation"
    _write_bound_source(
        root,
        records,
        role=f"{prefix}_package_set_manifest",
        relative=f"source_authority/{prefix}/package_set_manifest.json",
        raw=producer.manifest_raw,
        declared_self=producer.manifest["integrity"]["self_sha256"],
    )
    if producer.source_manifest_path is not None:
        raw = producer.source_manifest_path.read_bytes()
        value = loads_strict(raw, require_object=True)
        _write_bound_source(
            root,
            records,
            role=f"{prefix}_accepted_source_manifest",
            relative=f"source_authority/{prefix}/accepted_source_manifest.json",
            raw=raw,
            declared_self=value["integrity"]["self_sha256"],
        )
    if producer.acceptance_receipt_path is not None:
        raw = producer.acceptance_receipt_path.read_bytes()
        value = loads_strict(raw, require_object=True)
        _write_bound_source(
            root,
            records,
            role=f"{prefix}_acceptance_receipt",
            relative=f"source_authority/{prefix}/acceptance_receipt.json",
            raw=raw,
            declared_self=value["integrity"]["self_sha256"],
        )


def _write_bound_source(
    root: Path,
    records: list[dict[str, Any]],
    *,
    role: str,
    relative: str,
    raw: bytes,
    declared_self: str | None = None,
) -> None:
    _write_bytes(root / relative, raw)
    records.append(
        {
            "role": role,
            "relative_path": relative,
            "physical_sha256": sha256_bytes(raw),
            "declared_self_sha256": declared_self,
        }
    )


def _artifact_record(
    *,
    role: str,
    relative: str,
    value: dict[str, Any],
    raw: bytes,
    producer: str,
    producer_commit: str,
    candidate_key: dict[str, str],
) -> dict[str, Any]:
    return {
        "role": role,
        "relative_path": relative,
        "schema_id": value["schema_id"],
        "schema_version": value["schema_version"],
        "producer": producer,
        "producer_commit": producer_commit,
        "candidate_key": candidate_key,
        "physical_sha256": sha256_bytes(raw),
        "declared_self_sha256": value["integrity"]["self_sha256"],
    }


def _producer_summary(producer: ProducerSet) -> dict[str, Any]:
    return {
        "role": producer.role,
        "status": producer.status,
        "manifest_self_sha256": producer.manifest["integrity"]["self_sha256"],
        "manifest_physical_sha256": sha256_bytes(producer.manifest_raw),
        "package_count": sum(item.kind == "PACKAGE" for item in producer.items),
        "hold_count": sum(item.kind == "HOLD" for item in producer.items),
        "producer": producer.manifest["producer"],
    }


def _write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        if path.read_bytes() == raw:
            return
        raise IntegrityError(f"refusing conflicting materialization: {path}") from exc


def _write_checksums(root: Path) -> None:
    lines = [
        f"{sha256_file(path)}  {relative_posix(path, root)}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    ]
    (root / "CHECKSUMS.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


__all__ = ["build_adapter_bundle"]
