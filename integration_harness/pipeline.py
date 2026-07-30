"""End-to-end M0-M5 orchestration."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .assembler import GlobalCliAdapter
from .assembly import assemble_candidates
from .authority import CONTRACTS_R2_CURRENT, SYNTHETIC_LOCAL_CONFORMANCE, resolve_authority
from .contracts_verifier import PublicContractR2Verifier
from .errors import ExecutionError, PolicyError
from .hashing import sha256_bytes
from .jsonio import canonical_bytes
from .inventory import ADAPTER_INVENTORY_SCHEMA, LEGACY_ADAPTER_INVENTORY_SCHEMA, load_inventory
from .join import validate_and_join
from .preflight import validate_preflight
from .report import build_report
from .sealer import seal_run


def execute_run(
    *,
    manifest_path: Path,
    authority_receipt: Path,
    contracts_root: Path,
    output_dir: Path,
    run_id: str,
    mode: str,
    action_policy: Path | None = None,
    action_policy_authority: Path | None = None,
    approval_root: Path | None = None,
    authority_mode: str | None = None,
    expected_authority: dict[str, Any] | None = None,
    contract_verifier: PublicContractR2Verifier | None = None,
    adapter: GlobalCliAdapter | None = None,
    repository_root: Path | None = None,
) -> Path:
    """Run discovery through sealing; no final directory is created on failure."""

    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    repository_root = (repository_root or contracts_root.resolve().parent).resolve()
    authority_mode = authority_mode or (
        SYNTHETIC_LOCAL_CONFORMANCE
        if mode == "FIXTURE_CONFORMANCE"
        else CONTRACTS_R2_CURRENT
    )
    inventory = load_inventory(manifest_path)
    if inventory.holds:
        raise PolicyError("legacy producer hold records block Global execution")
    if (
        inventory.manifest.get("schema_id")
        in {ADAPTER_INVENTORY_SCHEMA, LEGACY_ADAPTER_INVENTORY_SCHEMA}
        and inventory.manifest.get("global_execution", {}).get("status")
        != "READY_FOR_PUBLIC_GLOBAL_CLI"
    ):
        raise PolicyError("adapter inventory is not ready for public Global CLI")
    authority = resolve_authority(
        authority_receipt,
        contracts_root,
        action_policy_path=action_policy,
        action_policy_authority_path=action_policy_authority,
        approval_root=approval_root,
        repository_root=repository_root,
        authority_mode=authority_mode,
        expected=expected_authority,
        contract_verifier=contract_verifier,
    )
    candidates, join_report = validate_and_join(inventory, schema_root=contracts_root)
    preflight = validate_preflight(candidates, mode=mode, authority=authority)
    if adapter is None:
        adapter = GlobalCliAdapter(
            repository_root=repository_root,
            authority_receipt=authority.receipt_path,
            action_policy=authority.action_policy_path,
            contracts_root=authority.contracts_root,
        )
    with tempfile.TemporaryDirectory(prefix="system-integration-", dir=str(output_dir.parent.resolve())) as staging_name:
        staging = Path(staging_name)
        assembled_dir = staging / "global_inputs"
        assembled, assembly_report = assemble_candidates(candidates, adapter, assembled_dir)
        execution_dirs: dict[str, Path] = {}
        execution_results: list[dict[str, Any]] = []
        collision_index = candidates[0].support.get("collision_index").path if candidates and candidates[0].support.get("collision_index") else None
        for item in assembled:
            adapter.validate_input(item["path"], collision_index=collision_index)
            execution = adapter.run(item["path"], staging / "global_runs", f"{run_id}-{item['candidate_id']}", mode="DEVELOPMENT_HEURISTIC", collision_index=collision_index)
            run_dir_value = execution.get("run_dir")
            if run_dir_value:
                execution_dirs[item["candidate_id"]] = Path(run_dir_value).resolve()
            if execution.get("approval_score") is not None:
                raise ExecutionError("development execution returned a non-null approval score")
            if execution.get("decision") == "AUTO_APPROVED" or execution.get("certificate_sha256"):
                raise ExecutionError("development execution emitted forbidden approval/certificate")
            execution_results.append({
                "candidate_id": item["candidate_id"],
                "status": execution.get("status", "PASS"),
                "decision": execution.get("decision"),
                "approval_score": execution.get("approval_score"),
                "certificate_sha256": execution.get("certificate_sha256"),
            })
        run_spec = {
            "schema_id": "SystemIntegrationRunSpecV1",
            "schema_version": "1.0.0",
            "run_id": run_id,
            "mode": mode,
            "authority_mode": authority.authority_mode,
            "compatibility_mode": authority.compatibility_mode,
            "expected_candidate_count": len(candidates),
            "network_policy": "FORBIDDEN",
            "development_invariants": {
                "auto_approved_count": 0,
                "certificate_count": 0,
                "approval_score_must_be_null": True,
            },
            "authority": authority.as_dict(),
            "join_report_sha256": sha256_bytes(canonical_bytes(join_report)),
            "assembly_report_sha256": sha256_bytes(canonical_bytes(assembly_report)),
        }
        integration_report = build_report(
            candidates=len(candidates),
            joined=len(candidates),
            failures=[],
            execution_results=execution_results,
            replay_pass_count=0,
            authority_warnings=[],
            authority=authority.as_dict(),
        )
        return seal_run(
            output_dir,
            run_spec=run_spec,
            authority=authority,
            inventory=inventory,
            candidates=candidates,
            assembled=assembled,
            preflight_report=preflight,
            execution_results=execution_results,
            execution_dirs=execution_dirs,
            integration_report=integration_report,
        )
