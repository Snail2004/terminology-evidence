"""Deterministic zero-provider fixtures for the 15/150 adapter tests."""

from __future__ import annotations

import copy
import json
import stat
import zipfile
from pathlib import Path
from typing import Any, Sequence

from integration_harness.adapter_v1.dataset import DatasetCandidate
from integration_harness.adapter_v1.producer import (
    PACKAGE_SET_SCHEMA,
    SYNTHETIC_COMPLETE,
)
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.jsonio import canonical_bytes, dump_json, without_self_hash

from .helpers import ROLES, _replace


def make_synthetic_dataset_release(
    repo_root: Path,
    output_root: Path,
) -> dict[str, Path]:
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
    for index in range(150):
        sense_number = index // 3
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
            "sense_inventory_version": "synthetic-50-sense-v1",
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
            path = f"effective_sense_contracts_50/{sense_id}.json"
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
        frozen_path = f"frozen_candidate_contracts_150/{candidate_id}.json"
        constraint_path = f"constraint_evidence_packages_150/{candidate_id}.json"
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
        "candidate_count": 150,
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
            "candidate": 150,
            "selected_sense": 50,
            "effective_sense_contract": 50,
            "frozen_candidate_contract": 150,
            "constraint_evidence_package": 150,
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
    zip_path = output_root / "synthetic_dataset_50_150.zip"
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
            "effective_sense_contracts": 50,
            "frozen_candidate_contracts": 150,
            "constraint_evidence_packages": 150,
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
        "schema_version": "1.0.0",
        "producer_role": role,
        "status": SYNTHETIC_COMPLETE,
        "producer": producer,
        "entry_count": len(entries),
        "package_count": len(entries),
        "hold_count": 0,
        "entries": entries,
        "accepted_source_binding": None,
        "final_glossary_decision": None,
        "global_action": None,
        "integrity": {},
    }
    manifest["integrity"]["self_sha256"] = self_sha256(manifest)
    manifest_path = output_root / "manifest.json"
    dump_json(manifest_path, manifest)
    return manifest_path


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


__all__ = ["make_producer_set", "make_synthetic_dataset_release"]
