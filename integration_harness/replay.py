"""Checksum-first portable replay verification."""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from .assembler import GlobalCliAdapter
from .errors import ReplayError
from .hashing import sha256_file, self_sha256
from .identity import CandidateIdentity
from .inventory import ArtifactInventory, ArtifactRecord
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


def replay_run(run_dir: Path, *, adapter: GlobalCliAdapter | None = None) -> dict[str, Any]:
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
    join_report = load_json(run_dir / "audit" / "join_report.json", require_object=True)
    execution = load_json(run_dir / "audit" / "execution_report.json", require_object=True)
    if execution.get("network_calls") != 0:
        raise ReplayError("sealed run records network calls")
    if execution.get("auto_approved_count") != 0 or execution.get("certificate_count") != 0:
        raise ReplayError("development run violates approval/certificate invariant")
    package_count = len(list((run_dir / "input" / "packages").rglob("*.json")))
    if package_count != join_report.get("candidate_count", 0) * 5:
        raise ReplayError("sealed package count does not match join report")
    if adapter is not None:
        sealed_receipt = run_dir / "input" / "authority" / "authority_receipt.json"
        replay_adapter = replace(adapter, authority_receipt=sealed_receipt)
        try:
            from .authority import resolve_authority

            resolve_authority(
                sealed_receipt,
                replay_adapter.contracts_root,
                action_policy_path=replay_adapter.action_policy,
                expected=run_spec.get("authority", {}),
            )
        except Exception as exc:
            raise ReplayError(f"sealed authority verification failed: {exc}") from exc
        try:
            validate_and_join(_sealed_inventory(run_dir), schema_root=replay_adapter.contracts_root)
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
    return {
        "status": "PASS",
        "matched": True,
        "run_id": run_spec.get("run_id"),
        "candidate_count": join_report.get("candidate_count", 0),
        "checksum_file_count": checksum["file_count"],
        "semantic_replay": semantic,
    }
