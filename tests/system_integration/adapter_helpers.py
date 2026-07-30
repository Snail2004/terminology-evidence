"""Deterministic zero-provider fixtures for exact-cohort adapter tests."""

from __future__ import annotations

import copy
import json
import stat
import zipfile
from pathlib import Path
from typing import Any, Sequence

from integration_harness.adapter_v1.dataset import DatasetCandidate
from integration_harness.adapter_v1.availability import (
    EXTERNAL_HOLD_RECEIPT_SCHEMA,
    RUN_AUTHORIZATION_SCHEMA,
    RUN_STOP_EVENT_SCHEMA,
)
from integration_harness.adapter_v1.producer import (
    ACCEPTANCE_RECEIPT_SCHEMA,
    APPROVAL_ARTIFACT_SCHEMA,
    COHORT_AUTHORITY_SCHEMA,
    COMPLETE_ACCEPTED,
    PACKAGE_SET_SCHEMA,
    SOURCE_MANIFEST_SCHEMA,
    SYNTHETIC_COMPLETE,
    candidate_set_sha256,
)
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.jsonio import canonical_bytes, dump_json, without_self_hash

from .helpers import ROLES, _replace


def make_synthetic_dataset_release(
    repo_root: Path,
    output_root: Path,
    *,
    candidate_count: int = 150,
) -> dict[str, Path]:
    if candidate_count <= 0:
        raise ValueError("candidate_count must be positive")
    candidates_per_sense = 1 if candidate_count == 1 else 3
    sense_count = (candidate_count + candidates_per_sense - 1) // candidates_per_sense
    output_root.mkdir(parents=True, exist_ok=True)
    contracts = repo_root / "terminology_contracts_v1" / "examples" / "valid" / "v1.1.0"
    source = {
        role: json.loads((contracts / filename).read_text(encoding="utf-8"))
        for role, filename in ROLES.items()
    }
    dataset_hash = "a" * 64
    members: dict[str, bytes] = {}
    effective_by_sense: dict[str, tuple[str, dict[str, Any]]] = {}
    entries: list[dict[str, Any]] = []
    for index in range(candidate_count):
        sense_number = index // candidates_per_sense
        sense_id = f"synthetic-sense-{sense_number:03d}"
        source_term = f"synthetic-term-{sense_number:03d}"
        candidate_id = f"synthetic-candidate-{index:03d}"
        identity = {
            "candidate_id": candidate_id,
            "candidate_version": f"synthetic-candidate-version-{index:03d}",
            "source_term": source_term,
            "candidate_vi": f"ung-vien-{index:03d}",
            "sense_id": sense_id,
            "scope_id": "machine_learning",
            "sense_inventory_version": f"synthetic-{sense_count}-sense-v2",
            "dataset_manifest_sha256": dataset_hash,
            "effective_sense_contract_sha256": "0" * 64,
            "input_contract_sha256": "0" * 64,
        }
        if sense_id not in effective_by_sense:
            effective = _replace(
                copy.deepcopy(source["effective_sense"]), identity, "b" * 64, "0" * 64
            )
            effective["source_term"] = source_term
            effective["sense_id"] = sense_id
            effective["scope_id"] = identity["scope_id"]
            effective["sense_inventory_version"] = identity["sense_inventory_version"]
            effective["parent_dataset_manifest_sha256"] = dataset_hash
            effective["integrity"]["self_sha256"] = self_sha256(effective)
            path = f"effective_sense_contracts_{sense_count}/{sense_id}.json"
            effective_by_sense[sense_id] = (path, effective)
            members[path] = _json_bytes(effective)
        effective_path, effective = effective_by_sense[sense_id]
        identity["effective_sense_contract_sha256"] = effective["integrity"]["self_sha256"]
        frozen = _replace(
            copy.deepcopy(source["frozen_candidate"]),
            identity,
            "b" * 64,
            identity["effective_sense_contract_sha256"],
        )
        frozen["surfaces"]["canonical_vi"] = identity["candidate_vi"]
        binding = without_self_hash(frozen)
        binding.pop("input_contract_sha256", None)
        identity["input_contract_sha256"] = sha256_bytes(canonical_bytes(binding))
        frozen["input_contract_sha256"] = identity["input_contract_sha256"]
        frozen["integrity"]["self_sha256"] = self_sha256(frozen)
        constraint = _replace(
            copy.deepcopy(source["constraints"]),
            identity,
            identity["input_contract_sha256"],
            identity["effective_sense_contract_sha256"],
        )
        constraint["polysemy_resolution"]["related_sense_ids"] = [sense_id]
        constraint["sense_review"]["effective_sense_contract_sha256"] = identity[
            "effective_sense_contract_sha256"
        ]
        constraint["target_collision"] = {
            "status": "UNJUDGEABLE",
            "collision_index_sha256": None,
            "collision_index_ref": None,
            "conflicting_candidate_keys": [],
            "evidence_refs": [],
        }
        constraint["integrity"]["self_sha256"] = self_sha256(constraint)
        frozen_path = f"frozen_candidate_contracts_{candidate_count}/{candidate_id}.json"
        constraint_path = f"constraint_evidence_packages_{candidate_count}/{candidate_id}.json"
        members[frozen_path] = _json_bytes(frozen)
        members[constraint_path] = _json_bytes(constraint)
        entries.append(
            {
                "binding_status": "COMPLETE",
                "candidate_id": candidate_id,
                "candidate_version": identity["candidate_version"],
                "candidate_vi": identity["candidate_vi"],
                "source_term": source_term,
                "sense_id": sense_id,
                "input_contract_sha256": identity["input_contract_sha256"],
                "effective_sense_path": effective_path,
                "effective_sense_sha256": effective["integrity"]["self_sha256"],
                "frozen_candidate_path": frozen_path,
                "frozen_candidate_sha256": frozen["integrity"]["self_sha256"],
                "constraint_evidence_path": constraint_path,
                "constraint_evidence_sha256": constraint["integrity"]["self_sha256"],
            }
        )
    index = {
        "schema_id": "HarnessSyntheticCandidateIndexV1",
        "schema_version": "1.0.0",
        "candidate_count": candidate_count,
        "entries": entries,
        "final_glossary_decision": None,
        "integrity": {},
    }
    index["integrity"]["self_sha256"] = self_sha256(index)
    members["candidate_index.json"] = _json_bytes(index)
    files = {
        name: {"sha256": sha256_bytes(raw), "size_bytes": len(raw)}
        for name, raw in sorted(members.items())
    }
    manifest = {
        "schema_id": "HarnessSyntheticDatasetManifestV1",
        "schema_version": "1.0.0",
        "status": "SYNTHETIC_LOCAL_CONFORMANCE",
        "candidate_index_path": "candidate_index.json",
        "counts": {
            "candidate": candidate_count,
            "selected_sense": sense_count,
            "effective_sense_contract": sense_count,
            "frozen_candidate_contract": candidate_count,
            "constraint_evidence_package": candidate_count,
        },
        "files": files,
        "provider_call_count": 0,
        "final_glossary_decision": None,
        "manifest_sha256": "",
    }
    manifest_without_hash = dict(manifest)
    manifest_without_hash.pop("manifest_sha256")
    manifest["manifest_sha256"] = sha256_bytes(canonical_bytes(manifest_without_hash))
    manifest_raw = _json_bytes(manifest)
    members["manifest.json"] = manifest_raw
    checksums = "".join(
        f"{sha256_bytes(raw)} *{name}\n" for name, raw in sorted(members.items())
    ).encode("utf-8")
    members["CHECKSUMS.sha256"] = checksums
    zip_path = output_root / f"synthetic_dataset_{sense_count}_{candidate_count}.zip"
    _write_deterministic_zip(zip_path, members)
    pin = {
        "schema_id": "HarnessSyntheticDatasetPinV1",
        "status": "SYNTHETIC_LOCAL_CONFORMANCE",
        "artifact": {
            "name": zip_path.name,
            "physical_sha256": sha256_file(zip_path),
            "size_bytes": zip_path.stat().st_size,
            "entry_count": len(members),
        },
        "manifest": {
            "self_sha256": manifest["manifest_sha256"],
            "physical_sha256": sha256_bytes(manifest_raw),
        },
        "counts": {
            "effective_sense_contracts": sense_count,
            "frozen_candidate_contracts": candidate_count,
            "constraint_evidence_packages": candidate_count,
        },
        "boundaries": {
            "provider_calls": 0,
            "network_calls": 0,
            "auto_approved": 0,
            "certificates": 0,
            "final_glossary_decision": None,
        },
        "integrity": {},
    }
    pin["integrity"]["self_sha256"] = self_sha256(pin)
    pin_path = output_root / "synthetic_dataset_pin.json"
    dump_json(pin_path, pin)
    return {"zip": zip_path, "pin": pin_path}


def make_producer_set(
    repo_root: Path,
    output_root: Path,
    *,
    candidates: Sequence[DatasetCandidate],
    role: str,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    producer = {
        "component_id": (
            "context-substitution" if role == "context_evidence" else "vietnamese-attestation"
        ),
        "component_version": "synthetic-conformance-v1",
        "run_id": f"synthetic-{role}-run-v1",
        "commit": "synthetic-local-conformance",
        "tree": "synthetic-local-conformance",
    }
    entries: list[dict[str, Any]] = []
    template_name = ROLES[role]
    template = json.loads(
        (
            repo_root
            / "terminology_contracts_v1"
            / "examples"
            / "valid"
            / "v1.1.0"
            / template_name
        ).read_text(encoding="utf-8")
    )
    for candidate in candidates:
        identity = candidate.identity.as_dict()
        value = _replace(
            copy.deepcopy(template),
            identity,
            identity["input_contract_sha256"],
            identity["effective_sense_contract_sha256"],
        )
        value["provenance"]["component_id"] = producer["component_id"]
        value["provenance"]["component_version"] = producer["component_version"]
        value["provenance"]["run_id"] = producer["run_id"]
        value["provenance"]["source_artifact_hashes"]["dataset"] = identity[
            "dataset_manifest_sha256"
        ]
        value["final_glossary_decision"] = None
        value["integrity"]["self_sha256"] = self_sha256(value)
        relative = f"packages/{candidate.identity.candidate_id}.json"
        path = output_root / relative
        dump_json(path, value)
        entries.append(
            {
                "candidate_id": candidate.identity.candidate_id,
                "kind": "PACKAGE",
                "relative_path": relative,
                "physical_sha256": sha256_file(path),
                "self_sha256": value["integrity"]["self_sha256"],
            }
        )
    manifest = {
        "schema_id": PACKAGE_SET_SCHEMA,
        "schema_version": "2.0.0",
        "producer_role": role,
        "status": SYNTHETIC_COMPLETE,
        "producer": producer,
        "entry_count": len(entries),
        "package_count": len(entries),
        "hold_count": 0,
        "entries": entries,
        "source_manifest": None,
        "final_glossary_decision": None,
        "global_action": None,
        "integrity": {},
    }
    manifest["integrity"]["self_sha256"] = self_sha256(manifest)
    manifest_path = output_root / "manifest.json"
    dump_json(manifest_path, manifest)
    return manifest_path


def make_accepted_producer_set(
    repo_root: Path,
    output_root: Path,
    *,
    candidates: Sequence[DatasetCandidate],
    role: str,
    run_id: str,
    phase_id: str,
    split_id: str,
) -> dict[str, Path]:
    """Build a typed official producer set and detached acceptance authority."""

    manifest_path = make_producer_set(
        repo_root, output_root, candidates=candidates, role=role
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    marker = "1" if role == "context_evidence" else "2"
    producer = {
        "component_id": (
            "context-substitution" if role == "context_evidence" else "vietnamese-attestation"
        ),
        "component_version": "1.1.0",
        "run_id": f"official-{role}-producer-run",
        "commit": marker * 40,
        "tree": ("3" if role == "context_evidence" else "4") * 40,
    }
    for entry in manifest["entries"]:
        package_path = output_root / entry["relative_path"]
        value = json.loads(package_path.read_text(encoding="utf-8"))
        for field in ("component_id", "component_version", "run_id"):
            value["provenance"][field] = producer[field]
        value["integrity"]["self_sha256"] = self_sha256(value)
        package_path.unlink()
        dump_json(package_path, value)
        entry["physical_sha256"] = sha256_file(package_path)
        entry["self_sha256"] = value["integrity"]["self_sha256"]

    exact_hash = candidate_set_sha256(candidates)
    source = {
        "schema_id": SOURCE_MANIFEST_SCHEMA,
        "schema_version": "1.0.0",
        "status": "COMPLETE",
        "producer_role": role,
        "producer": producer,
        "candidate_count": len(candidates),
        "candidate_set_sha256": exact_hash,
        "final_glossary_decision": None,
        "integrity": {},
    }
    source["integrity"]["self_sha256"] = self_sha256(source)
    source_path = output_root / "source" / "source_manifest.json"
    dump_json(source_path, source)
    manifest["status"] = COMPLETE_ACCEPTED
    manifest["producer"] = producer
    manifest["source_manifest"] = {
        "relative_path": "source/source_manifest.json",
        "physical_sha256": sha256_file(source_path),
        "self_sha256": source["integrity"]["self_sha256"],
    }
    manifest["integrity"]["self_sha256"] = self_sha256(manifest)
    manifest_path.unlink()
    dump_json(manifest_path, manifest)

    authority_root = output_root / "acceptance"
    identities = [
        item.identity.as_dict()
        for item in sorted(candidates, key=lambda item: item.identity.candidate_id)
    ]
    cohort = {
        "schema_id": COHORT_AUTHORITY_SCHEMA,
        "schema_version": "1.0.0",
        "run_id": run_id,
        "phase_id": phase_id,
        "split_id": split_id,
        "candidate_count": len(candidates),
        "candidate_set_sha256": exact_hash,
        "candidates": identities,
        "final_glossary_decision": None,
        "integrity": {},
    }
    cohort["integrity"]["self_sha256"] = self_sha256(cohort)
    cohort_path = authority_root / "candidate_cohort.json"
    dump_json(cohort_path, cohort)
    cohort_binding = {
        "relative_path": "candidate_cohort.json",
        "physical_sha256": sha256_file(cohort_path),
        "self_sha256": cohort["integrity"]["self_sha256"],
    }
    manifest_binding = {
        "physical_sha256": sha256_file(manifest_path),
        "self_sha256": manifest["integrity"]["self_sha256"],
    }
    common = {
        "issuer_id": "system-integration-maintainer",
        "authority_id": "main-reviewed-producer-set-authority-v1",
        "run_id": run_id,
        "phase_id": phase_id,
        "split_id": split_id,
        "producer_role": role,
        "producer": producer,
        "package_set_manifest": manifest_binding,
        "candidate_cohort": cohort_binding,
        "candidate_count": len(candidates),
        "candidate_set_sha256": exact_hash,
        "final_glossary_decision": None,
    }
    approval = {
        "schema_id": APPROVAL_ARTIFACT_SCHEMA,
        "schema_version": "1.0.0",
        "status": "APPROVED",
        **common,
        "integrity": {},
    }
    approval["integrity"]["self_sha256"] = self_sha256(approval)
    approval_path = authority_root / "approval_artifact.json"
    dump_json(approval_path, approval)
    receipt = {
        "schema_id": ACCEPTANCE_RECEIPT_SCHEMA,
        "schema_version": "1.0.0",
        "status": "ACCEPTED",
        **common,
        "approval_artifact": {
            "relative_path": "approval_artifact.json",
            "physical_sha256": sha256_file(approval_path),
            "self_sha256": approval["integrity"]["self_sha256"],
        },
        "integrity": {},
    }
    receipt["integrity"]["self_sha256"] = self_sha256(receipt)
    receipt_path = authority_root / "acceptance_receipt.json"
    dump_json(receipt_path, receipt)
    return {"manifest": manifest_path, "receipt": receipt_path}


def make_external_hold_authority(
    availability_path: Path,
    *,
    candidate_key: dict[str, str],
    role: str,
    run_id: str,
    phase_id: str,
    split_id: str,
    reason_code: str,
    observed_at: str,
) -> dict[str, Any]:
    authority_root = availability_path.parent / "external_stop"
    producer = {
        "component_id": "context-substitution" if role == "context_evidence" else "vietnamese-attestation",
        "component_version": "1.1.0",
        "run_id": f"external-{role}-run",
        "commit": "5" * 40,
        "tree": "6" * 40,
    }
    common = {
        "issuer_id": "system-integration-maintainer",
        "authority_id": "main-run-stop-authority-v1",
        "run_id": run_id,
        "phase_id": phase_id,
        "split_id": split_id,
        "candidate_key": candidate_key,
        "role": role,
        "producer": producer,
        "final_glossary_decision": None,
    }
    authorization = {
        "schema_id": RUN_AUTHORIZATION_SCHEMA,
        "schema_version": "1.0.0",
        "status": "AUTHORIZED",
        **common,
        "integrity": {},
    }
    authorization["integrity"]["self_sha256"] = self_sha256(authorization)
    authorization_path = authority_root / "authorization.json"
    dump_json(authorization_path, authorization)
    authorization_binding = {
        "relative_path": "authorization.json",
        "physical_sha256": sha256_file(authorization_path),
        "self_sha256": authorization["integrity"]["self_sha256"],
    }
    stop = {
        "schema_id": RUN_STOP_EVENT_SCHEMA,
        "schema_version": "1.0.0",
        "event_type": "STOP_EVENT",
        "status": "STOPPED",
        "run_id": run_id,
        "phase_id": phase_id,
        "split_id": split_id,
        "candidate_key": candidate_key,
        "role": role,
        "producer": producer,
        "reason_code": reason_code,
        "observed_at": observed_at,
        "authorization_receipt": authorization_binding,
        "final_glossary_decision": None,
        "integrity": {},
    }
    stop["integrity"]["self_sha256"] = self_sha256(stop)
    stop_path = authority_root / "stop_event.json"
    dump_json(stop_path, stop)
    receipt = {
        "schema_id": EXTERNAL_HOLD_RECEIPT_SCHEMA,
        "schema_version": "2.0.0",
        **common,
        "status": "EXTERNAL_HOLD",
        "authorization_receipt": authorization_binding,
        "stop_event": {
            "relative_path": "stop_event.json",
            "physical_sha256": sha256_file(stop_path),
            "self_sha256": stop["integrity"]["self_sha256"],
        },
        "reason_code": reason_code,
        "observed_at": observed_at,
        "integrity": {},
    }
    receipt["integrity"]["self_sha256"] = self_sha256(receipt)
    receipt_path = authority_root / "hold_receipt.json"
    dump_json(receipt_path, receipt)
    return {
        "relative_path": receipt_path.relative_to(availability_path.parent).as_posix(),
        "physical_sha256": sha256_file(receipt_path),
        "self_sha256": receipt["integrity"]["self_sha256"],
    }


def _json_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def _write_deterministic_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, raw)


__all__ = [
    "make_accepted_producer_set",
    "make_external_hold_authority",
    "make_producer_set",
    "make_synthetic_dataset_release",
]
