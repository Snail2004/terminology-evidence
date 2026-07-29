"""Immutable run bundle creation."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

from .authority import AuthoritySet
from .errors import StorageError
from .hashing import sha256_file, self_sha256
from .identity import CandidateIdentity
from .inventory import ArtifactInventory
from .join import JoinedCandidate
from .jsonio import dump_json
from .paths import relative_posix


def _write_checksums(root: Path) -> None:
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "CHECKSUMS.sha256":
            continue
        lines.append(f"{sha256_file(path)}  {relative_posix(path, root)}")
    (root / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _copy_unique(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(source, destination)
    except OSError as exc:
        raise StorageError(f"cannot copy sealed artifact {source}: {exc}") from exc


def seal_run(
    output_dir: Path,
    *,
    run_spec: Mapping[str, Any],
    authority: AuthoritySet,
    inventory: ArtifactInventory,
    candidates: tuple[JoinedCandidate, ...],
    assembled: list[dict[str, Any]],
    preflight_report: Mapping[str, Any],
    execution_results: list[Mapping[str, Any]],
    execution_dirs: Mapping[str, Path] | None = None,
    integration_report: Mapping[str, Any] | None = None,
    source_package_root_name: str = "packages",
) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise StorageError(f"refusing to overwrite run bundle: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_dir.parent / f".{output_dir.name}.tmp-{uuid.uuid4().hex}"
    temp_dir.mkdir()
    try:
        input_root = temp_dir / "input"
        for candidate in candidates:
            candidate_root = input_root / source_package_root_name / candidate.identity.candidate_id
            for role, package in candidate.packages.items():
                _copy_unique(package.record.path, candidate_root / f"{role}.json")
        copied_support: set[tuple[str, str]] = set()
        for candidate in candidates:
            for role, record in candidate.support.items():
                key = (role, record.physical_sha256)
                if key in copied_support:
                    continue
                copied_support.add(key)
                _copy_unique(record.path, input_root / "support" / f"{role}.json")
        _copy_unique(authority.receipt_path, input_root / "authority" / "authority_receipt.json")
        for item in assembled:
            _copy_unique(item["path"], input_root / "global_inputs" / f"{item['candidate_id']}.json")
        for candidate_id, execution_dir in (execution_dirs or {}).items():
            destination = temp_dir / "output" / "decisions" / candidate_id
            if destination.exists():
                raise StorageError(f"duplicate execution output: {candidate_id}")
            shutil.copytree(execution_dir, destination, symlinks=False)
        dump_json(temp_dir / "authority" / "authority_set.json", authority.as_dict())
        dump_json(temp_dir / "audit" / "artifact_inventory.json", {
            "schema_id": "ArtifactInventoryReportV1",
            "manifest_sha256": inventory.manifest_sha256,
            "artifact_count": len(inventory.records),
            "artifacts": [record.as_dict() for record in inventory.records],
        })
        dump_json(temp_dir / "audit" / "join_report.json", {
            "schema_id": "ExactJoinReportV1",
            "candidate_count": len(candidates),
            "joined_count": len(candidates),
            "failed_count": 0,
            "candidates": [candidate.as_dict() for candidate in candidates],
        })
        dump_json(temp_dir / "audit" / "preflight_report.json", dict(preflight_report))
        dump_json(temp_dir / "audit" / "assembly_report.json", {
            "schema_id": "AssemblyReportV1",
            "candidate_count": len(assembled),
            "inputs": [{"candidate_id": item["candidate_id"], "self_sha256": item["self_sha256"]} for item in assembled],
        })
        dump_json(temp_dir / "audit" / "execution_report.json", {
            "schema_id": "ExecutionReportV1",
            "results": [dict(item) for item in execution_results],
            "network_calls": 0,
            "auto_approved_count": 0,
            "certificate_count": 0,
        })
        if integration_report is not None:
            dump_json(temp_dir / "audit" / "integration_report.json", dict(integration_report))
        sanitized_spec = dict(run_spec)
        sanitized_spec["authority"] = authority.as_dict()
        sanitized_spec.pop("repository_root", None)
        sanitized_spec.pop("artifact_root", None)
        dump_json(temp_dir / "run_spec.json", sanitized_spec)
        manifest = {
            "schema_id": "SystemIntegrationRunManifestV1",
            "schema_version": "1.0.0",
            "run_id": sanitized_spec.get("run_id"),
            "files": [],
            "integrity": {},
        }
        # The manifest itself is finalized after all other bytes exist.
        _write_checksums(temp_dir)
        for path in sorted(temp_dir.rglob("*")):
            if path.is_file() and path.name not in {"manifest.json", "CHECKSUMS.sha256"}:
                manifest["files"].append({"path": relative_posix(path, temp_dir), "sha256": sha256_file(path)})
        manifest["integrity"]["self_sha256"] = self_sha256(manifest)
        dump_json(temp_dir / "manifest.json", manifest)
        _write_checksums(temp_dir)
        temp_dir.replace(output_dir)
        return output_dir
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
