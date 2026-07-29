"""Synthetic fixture and fake public-runner helpers for zero-network tests."""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from integration_harness.contracts_verifier import (
    NON_PRODUCTION_CONFORMANCE,
    PublicContractR2Verifier,
)
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.jsonio import canonical_bytes, dump_json, load_json, without_self_hash
from integration_harness.paths import relative_posix


ROLES = {
    "effective_sense": "effective_sense_contract.json",
    "frozen_candidate": "frozen_candidate_contract.json",
    "constraints": "constraint_evidence_package.json",
    "context_evidence": "context_evidence_package.json",
    "attestation_evidence": "attestation_evidence_package.json",
}


def _replace(value: Any, identity: dict[str, str], input_hash: str, effective_hash: str) -> Any:
    if isinstance(value, list):
        return [_replace(item, identity, input_hash, effective_hash) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key == "candidate_key":
            result[key] = {field: identity[field] for field in identity if field != "input_contract_sha256"}
        elif key == "input_contract_sha256":
            result[key] = input_hash
        elif key == "effective_sense_contract_sha256":
            result[key] = effective_hash
        elif key in {"dataset_manifest_sha256", "parent_dataset_manifest_sha256"}:
            result[key] = identity["dataset_manifest_sha256"]
        else:
            result[key] = _replace(item, identity, input_hash, effective_hash)
    return result


def _make_authority(repo_root: Path, output_root: Path) -> Path:
    contracts = repo_root / "terminology_contracts_v1"
    action_policy = repo_root / "global_validator" / "v1" / "policies" / "gate_action_selection_v1.0.0.json"
    manifest = load_json(contracts / "manifest.json", require_object=True)
    action = load_json(action_policy, require_object=True)
    receipt = {
        "schema_id": "TerminologyContractsAuthorityReceiptV1",
        "schema_version": "1.1.0",
        "authority_tag": "contracts-v1.1.0",
        "authority_commit": "fixture-authority-commit",
        "contract_version": "1.1.0",
        "manifest_sha256": manifest["integrity"]["manifest_sha256"],
        "manifest_file_sha256": sha256_file(contracts / "manifest.json"),
        "action_policy_sha256": action["integrity"]["self_sha256"],
        "integrity": {},
    }
    receipt["integrity"]["self_sha256"] = self_sha256(receipt)
    path = output_root / "authority_receipt.json"
    dump_json(path, receipt)
    return path


def make_fixture_repo(repo_root: Path, output_root: Path, count: int = 15) -> dict[str, Path]:
    """Create a manifest-driven 15-candidate package set from public examples."""

    output_root.mkdir(parents=True, exist_ok=True)
    base = repo_root / "terminology_contracts_v1" / "examples" / "valid" / "v1.1.0"
    source = {role: load_json(base / filename, require_object=True) for role, filename in ROLES.items()}
    dataset_hash = "a" * 64
    input_hash = "b" * 64
    records: list[dict[str, Any]] = []
    pending: list[tuple[dict[str, str], dict[str, dict[str, Any]]]] = []
    for index in range(count):
        candidate_id = f"synthetic-candidate-{index:03d}"
        identity = {
            "candidate_id": candidate_id,
            "candidate_version": "synthetic-v1",
            "source_term": f"term-{index:03d}",
            "candidate_vi": f"ung-viet-{index:03d}",
            "sense_id": f"sense-{index:03d}",
            "scope_id": "machine_learning",
            "sense_inventory_version": "sense-v1",
            "dataset_manifest_sha256": dataset_hash,
            "effective_sense_contract_sha256": "0" * 64,
            "input_contract_sha256": input_hash,
        }
        effective = copy.deepcopy(source["effective_sense"])
        effective = _replace(effective, identity, input_hash, "0" * 64)
        effective["source_term"] = identity["source_term"]
        effective["sense_id"] = identity["sense_id"]
        effective["scope_id"] = identity["scope_id"]
        effective["sense_inventory_version"] = identity["sense_inventory_version"]
        effective["parent_dataset_manifest_sha256"] = dataset_hash
        effective["integrity"]["self_sha256"] = self_sha256(effective)
        identity["effective_sense_contract_sha256"] = effective["integrity"]["self_sha256"]
        frozen = _replace(copy.deepcopy(source["frozen_candidate"]), identity, input_hash, identity["effective_sense_contract_sha256"])
        frozen["surfaces"]["canonical_vi"] = identity["candidate_vi"]
        binding_surface = without_self_hash(frozen)
        binding_surface.pop("input_contract_sha256", None)
        identity["input_contract_sha256"] = sha256_bytes(canonical_bytes(binding_surface))
        frozen["input_contract_sha256"] = identity["input_contract_sha256"]
        frozen["integrity"]["self_sha256"] = self_sha256(frozen)
        values: dict[str, dict[str, Any]] = {"effective_sense": effective, "frozen_candidate": frozen}
        for role in ("constraints", "context_evidence", "attestation_evidence"):
            value = _replace(copy.deepcopy(source[role]), identity, identity["input_contract_sha256"], identity["effective_sense_contract_sha256"])
            if role == "constraints":
                value["polysemy_resolution"]["related_sense_ids"] = [identity["sense_id"]]
                value["sense_review"]["effective_sense_contract_sha256"] = identity["effective_sense_contract_sha256"]
            value["integrity"]["self_sha256"] = self_sha256(value)
            values[role] = value
        pending.append((identity, values))
    collision_index = {
        "index_id": "synthetic-collision-index-v1",
        "candidate_keys": [
            {field: identity[field] for field in identity if field != "input_contract_sha256"}
            for identity, _values in pending
        ],
    }
    collision_path = output_root / "support" / "collision_index.json"
    dump_json(collision_path, collision_index)
    collision_sha = sha256_file(collision_path)
    records.append({
        "role": "collision_index",
        "relative_path": collision_path.relative_to(output_root).as_posix(),
        "schema_id": "CollisionIndexV1",
        "schema_version": "1.0.0",
        "producer": "dataset",
        "producer_commit": "synthetic-fixture-v1",
        "candidate_key": None,
        "physical_sha256": collision_sha,
        "declared_self_sha256": None,
    })
    for identity, values in pending:
        constraint = values["constraints"]
        constraint["target_collision"]["collision_index_sha256"] = collision_sha
        constraint["target_collision"]["collision_index_ref"]["sha256"] = collision_sha
        constraint["target_collision"]["collision_index_ref"]["evidence_id"] = collision_index["index_id"]
        constraint["integrity"]["self_sha256"] = self_sha256(constraint)
        candidate_id = identity["candidate_id"]
        candidate_root = output_root / "packages" / candidate_id
        for role, value in values.items():
            path = candidate_root / ROLES[role]
            dump_json(path, value)
            records.append({
                "role": role,
                "relative_path": path.relative_to(output_root).as_posix(),
                "schema_id": value["schema_id"],
                "schema_version": value["schema_version"],
                "producer": {"effective_sense": "dataset", "frozen_candidate": "dataset", "constraints": "dataset", "context_evidence": "context-substitution", "attestation_evidence": "vietnamese-attestation"}[role],
                "producer_commit": "synthetic-fixture-v1",
                "candidate_key": identity,
                "physical_sha256": sha256_file(path),
                "declared_self_sha256": value["integrity"]["self_sha256"],
            })
    manifest = {
        "schema_id": "ArtifactInventoryV1",
        "schema_version": "1.0.0",
        "release_id": "synthetic-system-integration-v1",
        "artifacts": records,
        "integrity": {},
    }
    manifest["integrity"]["self_sha256"] = self_sha256(manifest)
    manifest_path = output_root / "artifact_manifest.json"
    dump_json(manifest_path, manifest)
    authority = _make_authority(repo_root, output_root)
    return {
        "manifest": manifest_path,
        "authority": authority,
        "contracts": repo_root / "terminology_contracts_v1",
        "action_policy": repo_root / "global_validator" / "v1" / "policies" / "gate_action_selection_v1.0.0.json",
        "action_policy_authority": repo_root / "global_validator" / "v1" / "policies" / "gate_action_policy_authority_v1.0.0.json",
        "approval_root": repo_root / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2",
        "r2_receipt": repo_root / "terminology_contracts_v1" / "release" / "v1.1.0-final" / "contracts_v1_1_0_authority_receipt_r2.json",
    }


def fake_contract_verifier(repo_root: Path) -> PublicContractR2Verifier:
    return PublicContractR2Verifier(
        repo_root,
        repo_root / "terminology_contracts_v1",
        command_prefix=(
            sys.executable,
            "-B",
            str(
                repo_root
                / "tests"
                / "system_integration"
                / "fixtures"
                / "public_contract_verifier.py"
            ),
        ),
        execution_boundary=NON_PRODUCTION_CONFORMANCE,
    )


def reseal_test_run(run_dir: Path) -> None:
    manifest_path = run_dir / "manifest.json"
    checksums_path = run_dir / "CHECKSUMS.sha256"
    if checksums_path.exists():
        checksums_path.unlink()
    manifest = load_json(manifest_path, require_object=True)
    if manifest_path.exists():
        manifest_path.unlink()
    manifest["files"] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "CHECKSUMS.sha256"}:
            manifest["files"].append(
                {"path": relative_posix(path, run_dir), "sha256": sha256_file(path)}
            )
    manifest["integrity"]["self_sha256"] = self_sha256(manifest)
    dump_json(manifest_path, manifest)
    lines = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "CHECKSUMS.sha256":
            lines.append(f"{sha256_file(path)}  {relative_posix(path, run_dir)}")
    checksums_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


class FakePublicGlobalAdapter:
    """A deterministic stand-in for the public CLI used only by tests."""

    def __init__(self, repo_root: Path, work_root: Path) -> None:
        self.repository_root = repo_root
        self.authority_receipt = work_root / "authority_receipt.json"
        self.action_policy = repo_root / "global_validator" / "v1" / "policies" / "gate_action_selection_v1.0.0.json"
        self.contracts_root = repo_root / "terminology_contracts_v1"
        self.work_root = work_root

    def assemble(self, candidate: Any, output: Path) -> dict[str, Any]:
        template = load_json(self.repository_root / "terminology_contracts_v1" / "examples" / "valid" / "v1.1.0" / "global_validator_input.json", require_object=True)
        identity = candidate.identity.as_dict()
        result = _replace(template, identity, identity["input_contract_sha256"], identity["effective_sense_contract_sha256"])
        result["candidate_key"] = {field: identity[field] for field in identity if field != "input_contract_sha256"}
        for role, key in (("effective_sense", "effective_sense_contract"), ("frozen_candidate", "frozen_candidate_contract"), ("constraints", "constraint_evidence"), ("context_evidence", "context_evidence"), ("attestation_evidence", "attestation_evidence")):
            result[key] = candidate.packages[role].value
        result["input_contract_sha256"] = identity["input_contract_sha256"]
        result["integrity"]["self_sha256"] = self_sha256(result)
        dump_json(output, result)
        return {"status": "PASS", "output": str(output), "self_sha256": result["integrity"]["self_sha256"]}

    def validate_input(self, input_path: Path, *, collision_index: Path | None = None) -> dict[str, Any]:
        value = load_json(input_path, require_object=True)
        return {"status": "PASS", "candidate_id": value["candidate_key"]["candidate_id"], "self_sha256": value["integrity"]["self_sha256"]}

    def run(self, input_path: Path, output_dir: Path, run_id: str, *, mode: str, collision_index: Path | None = None) -> dict[str, Any]:
        value = load_json(input_path, require_object=True)
        run_dir = output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        dump_json(run_dir / "decision.json", {"schema_id": "FakeGlobalDecisionV1", "decision": "PROVISIONAL", "candidate_id": value["candidate_key"]["candidate_id"]})
        return {"status": "PASS", "decision": "PROVISIONAL", "approval_score": None, "certificate_sha256": None, "run_dir": str(run_dir)}
