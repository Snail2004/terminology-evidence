"""Checksum-first portable replay verification."""

from __future__ import annotations

import copy
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from .assembler import GlobalCliAdapter
from .adapter_v1.replay import verify_adapter_inventory_source_binding
from .authority import (
    CONTRACTS_R1_HISTORICAL_REPLAY,
    CONTRACTS_R2_CURRENT,
    SYNTHETIC_LOCAL_CONFORMANCE,
    resolve_authority,
    verify_historical_r1_binding,
)
from .contracts_verifier import PublicContractR2Verifier
from .errors import ReplayError
from .hashing import sha256_file, self_sha256
from .identity import CandidateIdentity
from .inventory import (
    ADAPTER_INVENTORY_SCHEMA,
    LEGACY_ADAPTER_INVENTORY_SCHEMA,
    ArtifactInventory,
    ArtifactRecord,
    SourceAuthorityRecord,
)
from .join import validate_and_join
from .jsonio import load_json
from .paths import ensure_no_symlink, safe_relative_path


def verify_checksums(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    checksum_path = run_dir / "CHECKSUMS.sha256"
    if not checksum_path.is_file():
        raise ReplayError("sealed run has no CHECKSUMS.sha256")
    entries: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise ReplayError("malformed checksum line")
        digest, relative = parts
        try:
            safe = safe_relative_path(relative)
            path = ensure_no_symlink(run_dir, safe)
        except Exception as exc:
            raise ReplayError(f"unsafe checksum path: {relative}") from exc
        if not path.is_file() or sha256_file(path) != digest:
            raise ReplayError(f"checksum mismatch: {relative}")
        if relative in entries:
            raise ReplayError(f"duplicate checksum path: {relative}")
        entries[relative] = digest
    return {"status": "PASS", "file_count": len(entries), "entries": entries}


def _sealed_inventory(run_dir: Path) -> ArtifactInventory:
    join_report = load_json(run_dir / "audit" / "join_report.json", require_object=True)
    records: list[ArtifactRecord] = []
    for candidate in join_report.get("candidates", []):
        identity = candidate.get("candidate_key")
        if not isinstance(identity, dict):
            raise ReplayError("join report has no candidate identity")
        candidate_id = identity.get("candidate_id")
        for role in ("effective_sense", "frozen_candidate", "constraints", "context_evidence", "attestation_evidence"):
            if role == "effective_sense":
                effective_sha = identity.get("effective_sense_contract_sha256")
                shared = (
                    run_dir
                    / "input"
                    / "shared"
                    / "effective_sense"
                    / f"{effective_sha}.json"
                )
                legacy = (
                    run_dir / "input" / "packages" / str(candidate_id) / f"{role}.json"
                )
                path = shared if shared.is_file() else legacy
            else:
                path = run_dir / "input" / "packages" / str(candidate_id) / f"{role}.json"
            if not path.is_file():
                raise ReplayError(f"sealed package is missing: {path}")
            value = load_json(path, require_object=True)
            records.append(ArtifactRecord(
                role=role,
                path=path,
                relative_path=path.relative_to(run_dir).as_posix(),
                schema_id=str(value.get("schema_id")),
                schema_version=str(value.get("schema_version")),
                producer="sealed",
                producer_commit="sealed",
                candidate_key=identity,
                physical_sha256=sha256_file(path),
                declared_self_sha256=value.get("integrity", {}).get("self_sha256"),
            ))
    collision = run_dir / "input" / "support" / "collision_index.json"
    if collision.is_file():
        records.append(ArtifactRecord(
            role="collision_index",
            path=collision,
            relative_path=collision.relative_to(run_dir).as_posix(),
            schema_id="CollisionIndexV1",
            schema_version="1.0.0",
            producer="sealed",
            producer_commit="sealed",
            candidate_key=None,
            physical_sha256=sha256_file(collision),
            declared_self_sha256=None,
        ))
    return ArtifactInventory(
        manifest_path=run_dir / "manifest.json",
        manifest={"schema_id": "SealedInventoryV1"},
        records=tuple(records),
        manifest_sha256=sha256_file(run_dir / "manifest.json"),
    )


def replay_run(
    run_dir: Path,
    *,
    adapter: GlobalCliAdapter | None = None,
    contract_verifier: PublicContractR2Verifier | None = None,
    repository_root: Path | None = None,
    contracts_root: Path | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    checksum = verify_checksums(run_dir)
    manifest = load_json(run_dir / "manifest.json", require_object=True)
    if manifest.get("integrity", {}).get("self_sha256") != self_sha256(manifest):
        raise ReplayError("run manifest self hash mismatch")
    if manifest.get("schema_id") != "SystemIntegrationRunManifestV1":
        raise ReplayError("unsupported run manifest")
    declared_files = {
        item.get("path"): item.get("sha256")
        for item in manifest.get("files", [])
        if isinstance(item, dict)
    }
    actual_files = dict(checksum.get("entries", {}))
    actual_files.pop("manifest.json", None)
    actual_files.pop("CHECKSUMS.sha256", None)
    if declared_files != actual_files:
        raise ReplayError("run manifest file inventory differs from CHECKSUMS")
    run_spec = load_json(run_dir / "run_spec.json", require_object=True)
    authority_expected = run_spec.get("authority")
    if not isinstance(authority_expected, dict):
        raise ReplayError("sealed run spec has no authority binding")
    authority_mode = authority_expected.get("authority_mode")
    compatibility_mode = authority_expected.get("compatibility_mode")
    if run_spec.get("authority_mode") != authority_mode or run_spec.get("compatibility_mode") != compatibility_mode:
        raise ReplayError("run-spec authority mode binding mismatch")
    join_report = load_json(run_dir / "audit" / "join_report.json", require_object=True)
    execution = load_json(run_dir / "audit" / "execution_report.json", require_object=True)
    if execution.get("network_calls") != 0:
        raise ReplayError("sealed run records network calls")
    if execution.get("auto_approved_count") != 0 or execution.get("certificate_count") != 0:
        raise ReplayError("development run violates approval/certificate invariant")
    candidate_count = join_report.get("candidate_count", 0)
    candidate_package_count = len(list((run_dir / "input" / "packages").rglob("*.json")))
    shared_effective_count = len(
        list((run_dir / "input" / "shared" / "effective_sense").glob("*.json"))
    )
    expected_package_count = (
        candidate_count * 4 + shared_effective_count
        if shared_effective_count
        else candidate_count * 5
    )
    if candidate_package_count + shared_effective_count != expected_package_count:
        raise ReplayError("sealed package count does not match join report")
    sealed_authority = run_dir / "input" / "authority"
    sealed_receipt = sealed_authority / "authority_receipt.json"
    if authority_mode == CONTRACTS_R1_HISTORICAL_REPLAY:
        try:
            verify_historical_r1_binding(sealed_receipt, authority_expected)
        except Exception as exc:
            raise ReplayError(f"historical R1 authority verification failed: {exc}") from exc
        semantic = "HISTORICAL_R1_SEALED_REPLAY_PASS"
    elif authority_mode in {CONTRACTS_R2_CURRENT, SYNTHETIC_LOCAL_CONFORMANCE}:
        sealed_policy = sealed_authority / "global_action_policy.json"
        sealed_policy_authority = sealed_authority / "global_action_policy_authority.json"
        repository_root = (
            repository_root
            or (adapter.repository_root if adapter is not None else None)
        )
        contracts_root = (
            contracts_root
            or (adapter.contracts_root if adapter is not None else None)
        )
        if contracts_root is None or repository_root is None:
            if authority_mode == CONTRACTS_R2_CURRENT:
                raise ReplayError("R2 replay requires repository and Contracts roots")
            if sha256_file(sealed_receipt) != authority_expected.get("receipt_physical_sha256"):
                raise ReplayError("synthetic sealed receipt physical hash mismatch")
            if sha256_file(sealed_policy) != authority_expected.get("action_policy_file_sha256"):
                raise ReplayError("synthetic sealed action-policy hash mismatch")
            if sha256_file(sealed_policy_authority) != authority_expected.get("action_policy_authority_physical_sha256"):
                raise ReplayError("synthetic sealed action-policy authority hash mismatch")
        else:
            approval_root = (
                sealed_authority / "approval"
                if authority_mode == CONTRACTS_R2_CURRENT
                else None
            )
            verifier = contract_verifier
            if authority_mode == CONTRACTS_R2_CURRENT and verifier is None:
                verifier = PublicContractR2Verifier(repository_root, contracts_root)
            try:
                resolve_authority(
                    sealed_receipt,
                    contracts_root,
                    action_policy_path=sealed_policy,
                    action_policy_authority_path=sealed_policy_authority,
                    approval_root=approval_root,
                    repository_root=repository_root,
                    authority_mode=authority_mode,
                    expected=authority_expected,
                    contract_verifier=verifier,
                )
            except Exception as exc:
                raise ReplayError(f"sealed authority verification failed: {exc}") from exc
        if authority_mode == CONTRACTS_R2_CURRENT:
            report_path = sealed_authority / "contracts_r2_verifier_report.json"
            try:
                report = load_json(report_path, require_object=True)
            except Exception as exc:
                raise ReplayError("sealed public Contract verifier report is invalid") from exc
            if report.get("integrity", {}).get("self_sha256") != authority_expected.get("contract_verifier_report_self_sha256"):
                raise ReplayError("sealed public Contract verifier report self hash mismatch")
            if sha256_file(report_path) != authority_expected.get("contract_verifier_report_physical_sha256"):
                raise ReplayError("sealed public Contract verifier report physical hash mismatch")
        if adapter is not None:
            replay_adapter = _bind_replay_authority(
                adapter,
                authority_receipt=sealed_receipt,
                action_policy=sealed_policy,
            )
            try:
                sealed_inventory = _sealed_inventory(run_dir)
                validate_and_join(
                    sealed_inventory, schema_root=replay_adapter.contracts_root
                )
                _verify_adapter_sources_if_present(
                    run_dir,
                    run_spec=run_spec,
                    sealed_packages=sealed_inventory,
                    contracts_root=replay_adapter.contracts_root,
                    repository_root=repository_root,
                )
            except Exception as exc:
                raise ReplayError(f"sealed package rejoin failed: {exc}") from exc
            expected = {item.get("candidate_id"): item for item in execution.get("results", [])}
            collision_index = run_dir / "input" / "support" / "collision_index.json"
            if not collision_index.is_file():
                collision_index = None
            with tempfile.TemporaryDirectory(prefix="system-integration-replay-") as temp:
                for input_path in sorted((run_dir / "input" / "global_inputs").glob("*.json")):
                    replay_adapter.validate_input(input_path, collision_index=collision_index)
                    result = replay_adapter.run(input_path, Path(temp), f"replay-{input_path.stem}", mode="DEVELOPMENT_HEURISTIC", collision_index=collision_index)
                    candidate_id = input_path.stem
                    original = expected.get(candidate_id)
                    if original is None:
                        raise ReplayError(f"execution report missing candidate: {candidate_id}")
                    if any(result.get(key) != original.get(key) for key in ("decision", "approval_score", "certificate_sha256")):
                        raise ReplayError(f"semantic decision drift for candidate: {candidate_id}")
            semantic = "PUBLIC_CLI_REPLAY_PASS"
        else:
            semantic = "SEALED_INPUT_REVALIDATION_ONLY"
    else:
        raise ReplayError(f"unsupported sealed authority mode: {authority_mode}")
    return {
        "status": "PASS",
        "matched": True,
        "run_id": run_spec.get("run_id"),
        "candidate_count": join_report.get("candidate_count", 0),
        "checksum_file_count": checksum["file_count"],
        "semantic_replay": semantic,
        "authority_mode": authority_mode,
        "compatibility_mode": compatibility_mode,
    }


def _verify_adapter_sources_if_present(
    run_dir: Path,
    *,
    run_spec: dict[str, Any],
    sealed_packages: ArtifactInventory,
    contracts_root: Path,
    repository_root: Path | None,
) -> None:
    binding = run_spec.get("adapter_inventory_binding")
    if (
        not isinstance(binding, dict)
        or binding.get("schema_id")
        not in {ADAPTER_INVENTORY_SCHEMA, LEGACY_ADAPTER_INVENTORY_SCHEMA}
    ):
        return
    manifest_path = run_dir / "input" / "inventory" / "artifact_manifest.json"
    manifest = load_json(manifest_path, require_object=True)
    if manifest.get("integrity", {}).get("self_sha256") != binding.get(
        "manifest_self_sha256"
    ):
        raise ReplayError("sealed adapter inventory self-hash binding mismatch")
    if sha256_file(manifest_path) != binding.get("manifest_physical_sha256"):
        raise ReplayError("sealed adapter inventory physical binding mismatch")
    audit = load_json(run_dir / "audit" / "artifact_inventory.json", require_object=True)
    raw_sources = audit.get("source_authority")
    if not isinstance(raw_sources, list) or len(raw_sources) != binding.get(
        "source_authority_count"
    ):
        raise ReplayError("sealed adapter source authority count mismatch")
    records: list[SourceAuthorityRecord] = []
    source_paths: dict[str, Path] = {}
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise ReplayError("sealed adapter source authority record is invalid")
        relative = safe_relative_path(str(raw.get("sealed_relative_path")))
        path = ensure_no_symlink(run_dir, relative)
        if not path.is_file() or sha256_file(path) != raw.get("physical_sha256"):
            raise ReplayError("sealed adapter source authority hash mismatch")
        role = str(raw.get("role"))
        if role in source_paths:
            raise ReplayError("duplicate sealed adapter source authority role")
        source_paths[role] = path
        records.append(
            SourceAuthorityRecord(
                role=role,
                path=path,
                relative_path=relative.as_posix(),
                physical_sha256=str(raw.get("physical_sha256")),
                declared_self_sha256=raw.get("declared_self_sha256"),
            )
        )
    adapter_inventory = ArtifactInventory(
        manifest_path=manifest_path,
        manifest=manifest,
        records=sealed_packages.records,
        manifest_sha256=sha256_file(manifest_path),
        source_authority=tuple(records),
        holds=(),
    )
    verify_adapter_inventory_source_binding(
        adapter_inventory,
        source_paths=source_paths,
        contracts_root=contracts_root,
        repository_root=repository_root,
    )


def _bind_replay_authority(
    adapter: Any,
    *,
    authority_receipt: Path,
    action_policy: Path,
) -> Any:
    try:
        return replace(
            adapter,
            authority_receipt=authority_receipt,
            action_policy=action_policy,
        )
    except TypeError:
        # Public test/conformance adapters may be ordinary objects rather than dataclasses.
        clone = copy.copy(adapter)
        if not hasattr(clone, "authority_receipt") or not hasattr(clone, "action_policy"):
            raise ReplayError("adapter cannot be rebound to sealed authority")
        clone.authority_receipt = authority_receipt
        clone.action_policy = action_policy
        return clone
