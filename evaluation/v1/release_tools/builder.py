"""AR-2 exact-object release builder with external atomic publication."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.authority import AuthorityError, canonical_manifest_path, resolve_contained_file, verify_sha256
from ..constants import MODE_SYNTHETIC, STATUS_CONFORMANCE_ONLY
from ..fixtures.synthetic import write_synthetic_release
from ..jsonio import read_json, sha256_file, sha256_value, write_json
from ..preregistration.receipt import build_receipt, write_receipt
from ..registries.loader import registry_counts, load_registries
from ..reports.builder import build_evaluation_report
from .git_source import SOURCE_ROOTS, materialize_commit, require_clean_exact_head, resolve_commit, source_entries, source_tree_sha256, write_source_zip
from .junit import MANIFEST_FILE, normalized_junit_bytes, run_evaluation_pytest, verify_junit
from .publication import external_atomic_stage


RELEASE_SCHEMA_ID = "EvaluationReleaseManifestV1"
RELEASE_SCHEMA_VERSION = "1.0.0"


class ReleaseBuildError(ValueError):
    """Raised when a release cannot be proven exact, green and external."""


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    integrity = dict(result.get("integrity", {}))
    integrity.pop("self_sha256", None)
    result["integrity"] = integrity
    return result


def _write_worker_payload(stage: Path, source_commit: str, git_repo_root: Path, materialized_root: Path) -> dict[str, Any]:
    """Run inside the materialized target commit; never publish or inspect live source."""
    if not stage.is_dir():
        raise ReleaseBuildError("worker stage does not exist")
    registries = materialized_root / "evaluation" / "v1" / "registries"
    synthetic_root = stage / "synthetic"
    synthetic_manifest = write_synthetic_release(synthetic_root)
    report = build_evaluation_report(
        read_json(synthetic_root / "rows.json")["rows"],
        synthetic_root / "report",
        split="development",
        bootstrap_seed=20260729,
        bootstrap_replicates=200,
    )
    receipt = build_receipt(
        mode=MODE_SYNTHETIC,
        base_commit=source_commit,
        repo_root_path=git_repo_root,
        registry_root_path=registries,
        artifact_hashes={"synthetic_rows": synthetic_manifest["rows_sha256"]},
        synthetic_reason="source-only conformance fixture; no validation/hidden-test authority",
        created_at="2026-07-29T00:00:00Z",
    )
    write_receipt(stage / "preregistration_conformance_receipt.json", receipt)
    write_json(stage / "synthetic_metric_report.json", report)
    write_json(
        stage / "environment.json",
        {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "source_commit": source_commit,
            "network_calls": 0,
            "provider_calls": 0,
        },
    )
    write_json(
        stage / "commands.json",
        {
            "test": "python -B -m pytest -q tests/evaluation --tb=short -p no:cacheprovider",
            "release": f"python -B -m evaluation.v1.tools.build_release --source-commit {source_commit} --output <external-path>",
            "network_calls": 0,
        },
    )
    return {"receipt_status": receipt["status"], "synthetic_rows_sha256": synthetic_manifest["rows_sha256"]}


def _run_materialized_worker(materialized_root: Path, stage: Path, commit: str, repo: Path) -> None:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(materialized_root)
    command = [
        sys.executable,
        "-B",
        "-m",
        "evaluation.v1.tools.build_release",
        "--worker-stage",
        str(stage),
        "--source-commit",
        commit,
        "--git-repo-root",
        str(repo),
    ]
    completed = subprocess.run(command, cwd=materialized_root, env=env, capture_output=True, text=True)
    if completed.returncode != 0:
        raise ReleaseBuildError(f"materialized release worker failed: {completed.stdout}\n{completed.stderr}")


def _scan_source(entries: list[tuple[str, bytes]]) -> tuple[list[str], list[str]]:
    forbidden_domains = ("dataset", "context_substitution", "vietnamese_attestation", "global_validator", "terminology_contracts_v1", "integration_harness")
    forbidden_imports: list[str] = []
    credential_literals: list[str] = []
    credential = re.compile(r"(?i)(api[_-]?key|secret[_-]?key)\s*=\s*['\"][^'\"]{8,}['\"]")
    for relative, data in entries:
        if not relative.endswith(".py"):
            continue
        text = data.decode("utf-8", errors="strict")
        if any(f"from {domain}" in text or f"import {domain}" in text for domain in forbidden_domains):
            forbidden_imports.append(relative)
        if credential.search(text):
            credential_literals.append(relative)
    return sorted(forbidden_imports), sorted(credential_literals)


def _file_inventory(root: Path) -> list[dict[str, Any]]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and relative not in {"release_manifest.json", "CHECKSUMS.sha256"}:
            canonical = canonical_manifest_path(relative)
            files[canonical] = path
    return [
        {"path": relative, "bytes": files[relative].stat().st_size, "sha256": sha256_file(files[relative])}
        for relative in sorted(files)
    ]


def _write_checksums(root: Path) -> None:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and relative != "CHECKSUMS.sha256":
            files[canonical_manifest_path(relative)] = path
    lines = [f"{sha256_file(files[relative])}  {relative}" for relative in sorted(files)]
    (root / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def build_release(
    *,
    repo: Path,
    output: Path,
    source_commit: str,
    detached_object: bool = False,
    external_junit: Path | None = None,
) -> dict[str, Any]:
    commit, tree = resolve_commit(repo, source_commit)
    if not detached_object:
        require_clean_exact_head(repo, commit)
    entries = source_entries(repo, commit)
    forbidden_imports, credential_literals = _scan_source(entries)
    if forbidden_imports or credential_literals:
        raise ReleaseBuildError(f"source scan failed: imports={forbidden_imports} credentials={credential_literals}")

    with tempfile.TemporaryDirectory(prefix="evaluation-ar2-release-") as temporary:
        temp_root = Path(temporary)
        materialized = temp_root / "source"
        materialize_commit(repo, commit, materialized)
        raw_junit = temp_root / "pytest-junit.xml"
        junit_report = run_evaluation_pytest(
            materialized,
            raw_junit,
            git_repo_root=repo,
            source_commit=commit,
        )
        external_report = None
        if external_junit is not None:
            external_report = verify_junit(
                external_junit,
                expected_manifest_path=materialized / "evaluation" / "v1" / "authority" / MANIFEST_FILE,
            )
            if external_report["testcase_identities"] != junit_report["testcase_identities"]:
                raise ReleaseBuildError("external JUnit identity differs from the release-run suite")

        with external_atomic_stage(output, repo) as stage:
            _run_materialized_worker(materialized, stage, commit, repo)
            expected_manifest = materialized / "evaluation" / "v1" / "authority" / MANIFEST_FILE
            shutil.copyfile(expected_manifest, stage / MANIFEST_FILE)
            (stage / "junit.xml").write_bytes(normalized_junit_bytes(junit_report))
            write_source_zip(entries, stage / "evaluation_preregistration_source.zip")
            source_hash = source_tree_sha256(entries)
            write_json(
                stage / "git_source_receipt.json",
                {
                    "schema_id": "EvaluationGitSourceReceiptV1",
                    "schema_version": "1.0.0",
                    "source_commit": commit,
                    "source_tree_git_oid": tree,
                    "source_tree_sha256": source_hash,
                    "source_file_count": len(entries),
                    "release_mode": "DETACHED_OBJECT" if detached_object else "CLEAN_EXACT_HEAD",
                },
            )
            write_json(stage / "ownership_scan.json", {"status": "PASS", "allowed_roots": list(SOURCE_ROOTS), "source_files": len(entries)})
            write_json(stage / "static_scan.json", {"status": "PASS", "forbidden_imports": forbidden_imports})
            write_json(stage / "credential_scan.json", {"status": "PASS", "credential_literals": credential_literals})
            inventory = _file_inventory(stage)
            manifest: dict[str, Any] = {
                "schema_id": RELEASE_SCHEMA_ID,
                "schema_version": RELEASE_SCHEMA_VERSION,
                "status": STATUS_CONFORMANCE_ONLY,
                "source_commit": commit,
                "source_tree_git_oid": tree,
                "source_tree_sha256": source_hash,
                "source_file_count": len(entries),
                "release_mode": "DETACHED_OBJECT" if detached_object else "CLEAN_EXACT_HEAD",
                "junit": {key: value for key, value in junit_report.items() if key != "testcase_identities"},
                "external_junit": None if external_report is None else {key: value for key, value in external_report.items() if key != "testcase_identities"},
                "expected_test_manifest_sha256": sha256_file(expected_manifest),
                "registry_counts": registry_counts(load_registries(materialized / "evaluation" / "v1" / "registries")),
                "network_calls": 0,
                "provider_calls": 0,
                "files": inventory,
                "integrity": {"self_sha256": ""},
            }
            manifest["integrity"]["self_sha256"] = sha256_value(_without_self_hash(manifest))
            write_json(stage / "release_manifest.json", manifest)
            _write_checksums(stage)
            verify_release(stage)

    verified = verify_release(output)
    return {
        "status": "PASS",
        "source_commit": commit,
        "source_tree_git_oid": tree,
        "release_manifest_physical_sha256": sha256_file(output / "release_manifest.json"),
        "release_manifest_self_sha256": verified["integrity"]["self_sha256"],
        "checksums_physical_sha256": sha256_file(output / "CHECKSUMS.sha256"),
        "source_zip_physical_sha256": sha256_file(output / "evaluation_preregistration_source.zip"),
    }


def verify_release(root: Path) -> dict[str, Any]:
    try:
        manifest_path = resolve_contained_file(root, "release_manifest.json")
    except AuthorityError as exc:
        raise ReleaseBuildError("release root/manifest is unsafe") from exc
    manifest = read_json(manifest_path)
    expected_keys = {
        "schema_id",
        "schema_version",
        "status",
        "source_commit",
        "source_tree_git_oid",
        "source_tree_sha256",
        "source_file_count",
        "release_mode",
        "junit",
        "external_junit",
        "expected_test_manifest_sha256",
        "registry_counts",
        "network_calls",
        "provider_calls",
        "files",
        "integrity",
    }
    if set(manifest) != expected_keys or manifest.get("schema_id") != RELEASE_SCHEMA_ID or manifest.get("schema_version") != RELEASE_SCHEMA_VERSION or manifest.get("status") != STATUS_CONFORMANCE_ONLY:
        raise ReleaseBuildError("release manifest shape/status is invalid")
    declared = manifest.get("integrity", {}).get("self_sha256") if isinstance(manifest.get("integrity"), Mapping) else None
    if declared != sha256_value(_without_self_hash(manifest)):
        raise ReleaseBuildError("release manifest self hash mismatch")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        raise ReleaseBuildError("release file inventory must be nonempty")
    paths: set[str] = set()
    folded_paths: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"path", "bytes", "sha256"}:
            raise ReleaseBuildError("release file inventory shape is invalid")
        try:
            relative = canonical_manifest_path(row["path"])
        except AuthorityError as exc:
            raise ReleaseBuildError("release inventory path is unsafe") from exc
        folded = relative.casefold()
        if relative in paths or folded in folded_paths:
            raise ReleaseBuildError("duplicate or case-confusable release inventory path")
        if isinstance(row["bytes"], bool) or not isinstance(row["bytes"], int) or row["bytes"] < 0:
            raise ReleaseBuildError("release inventory byte count is invalid")
        paths.add(relative)
        folded_paths.add(folded)
        try:
            path = resolve_contained_file(root, relative)
            verify_sha256(path, row["sha256"])
        except AuthorityError as exc:
            raise ReleaseBuildError(f"release file is unsafe or drifted: {relative}") from exc
        if path.stat().st_size != row["bytes"]:
            raise ReleaseBuildError(f"release file drift: {relative}")

    actual_paths: set[str] = set()
    actual_folded: set[str] = set()
    for path in root.rglob("*"):
        relative = canonical_manifest_path(path.relative_to(root).as_posix())
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ReleaseBuildError(f"release tree contains a link/reparse point: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ReleaseBuildError(f"release tree contains a nonregular node: {relative}")
        folded = relative.casefold()
        if relative in actual_paths or folded in actual_folded:
            raise ReleaseBuildError(f"release tree contains a case-confusable path: {relative}")
        actual_paths.add(relative)
        actual_folded.add(folded)
    expected_paths = paths | {"release_manifest.json", "CHECKSUMS.sha256"}
    if actual_paths != expected_paths:
        raise ReleaseBuildError(
            f"release physical file set differs from inventory: missing={sorted(expected_paths - actual_paths)} extra={sorted(actual_paths - expected_paths)}"
        )

    try:
        junit_path = resolve_contained_file(root, "junit.xml")
        expected_manifest_path = resolve_contained_file(root, MANIFEST_FILE)
        checksum_path = resolve_contained_file(root, "CHECKSUMS.sha256")
    except AuthorityError as exc:
        raise ReleaseBuildError("release authority/JUnit/checksum path is unsafe") from exc
    verify_junit(junit_path, expected_manifest_path=expected_manifest_path)
    expected_lines = []
    for relative in sorted(actual_paths - {"CHECKSUMS.sha256"}):
        path = resolve_contained_file(root, relative)
        expected_lines.append(f"{sha256_file(path)}  {relative}")
    if checksum_path.read_text(encoding="ascii").splitlines() != expected_lines:
        raise ReleaseBuildError("release CHECKSUMS drift")
    return manifest
