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
from ..jsonio import loads_strict, read_json, sha256_bytes, sha256_file, sha256_value, write_json
from ..preregistration.receipt import build_receipt, write_receipt
from ..registries.loader import REGISTRY_FILES, registry_counts, load_registries, validate_registries
from ..reports.builder import build_evaluation_report
from .git_source import (
    SOURCE_ROOTS,
    GitSourceError,
    materialize_commit,
    read_source_zip,
    require_clean_exact_head,
    resolve_commit,
    source_entries,
    source_tree_sha256,
    write_source_zip,
)
from .junit import MANIFEST_FILE, normalized_junit_bytes, run_evaluation_pytest, verify_junit
from .publication import external_atomic_stage


RELEASE_SCHEMA_ID = "EvaluationReleaseManifestV1"
RELEASE_SCHEMA_VERSION = "1.0.0"
RELEASE_CHECKSUM_FILE = "RELEASE_CHECKSUMS.sha256"


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


def _released_registry_counts(entries: list[tuple[str, bytes]]) -> dict[str, int]:
    by_path = dict(entries)
    registries: dict[str, Any] = {}
    try:
        for name in REGISTRY_FILES:
            relative = f"evaluation/v1/registries/{name}"
            data = by_path.get(relative)
            if data is None:
                raise ReleaseBuildError(f"source ZIP is missing registry: {relative}")
            registries[name.removesuffix("_v1.json")] = loads_strict(data.decode("utf-8"))
        validate_registries(registries)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ReleaseBuildError("source ZIP registry authority is invalid") from exc
    return registry_counts(registries)


def _file_inventory(root: Path) -> list[dict[str, Any]]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and relative not in {"release_manifest.json", RELEASE_CHECKSUM_FILE}:
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
        if path.is_file() and relative != RELEASE_CHECKSUM_FILE:
            files[canonical_manifest_path(relative)] = path
    lines = [f"{sha256_file(files[relative])}  {relative}" for relative in sorted(files)]
    (root / RELEASE_CHECKSUM_FILE).write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


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
            normalized_junit = normalized_junit_bytes(junit_report)
            (stage / "junit.xml").write_bytes(normalized_junit)
            release_junit_report = {key: value for key, value in junit_report.items() if key != "testcase_identities"}
            release_junit_report["physical_sha256"] = sha256_bytes(normalized_junit)
            external_release_report = None
            if external_report is not None:
                normalized_external = normalized_junit_bytes(external_report)
                (stage / "external_junit.xml").write_bytes(normalized_external)
                external_release_report = {key: value for key, value in external_report.items() if key != "testcase_identities"}
                external_release_report["physical_sha256"] = sha256_bytes(normalized_external)
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
                "junit": release_junit_report,
                "external_junit": external_release_report,
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
        "checksums_physical_sha256": sha256_file(output / RELEASE_CHECKSUM_FILE),
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
    if manifest.get("release_mode") not in {"CLEAN_EXACT_HEAD", "DETACHED_OBJECT"}:
        raise ReleaseBuildError("release mode is not allowed")
    if manifest.get("network_calls") != 0 or isinstance(manifest.get("network_calls"), bool) or manifest.get("provider_calls") != 0 or isinstance(manifest.get("provider_calls"), bool):
        raise ReleaseBuildError("release reports network/provider activity")
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
    expected_paths = paths | {"release_manifest.json", RELEASE_CHECKSUM_FILE}
    if actual_paths != expected_paths:
        raise ReleaseBuildError(
            f"release physical file set differs from inventory: missing={sorted(expected_paths - actual_paths)} extra={sorted(actual_paths - expected_paths)}"
        )

    try:
        junit_path = resolve_contained_file(root, "junit.xml")
        expected_manifest_path = resolve_contained_file(root, MANIFEST_FILE)
        checksum_path = resolve_contained_file(root, RELEASE_CHECKSUM_FILE)
        git_receipt_path = resolve_contained_file(root, "git_source_receipt.json")
        source_zip_path = resolve_contained_file(root, "evaluation_preregistration_source.zip")
        ownership_path = resolve_contained_file(root, "ownership_scan.json")
        static_scan_path = resolve_contained_file(root, "static_scan.json")
        credential_scan_path = resolve_contained_file(root, "credential_scan.json")
        commands_path = resolve_contained_file(root, "commands.json")
        environment_path = resolve_contained_file(root, "environment.json")
    except AuthorityError as exc:
        raise ReleaseBuildError("release authority/JUnit/checksum path is unsafe") from exc
    junit_report = verify_junit(junit_path, expected_manifest_path=expected_manifest_path)
    expected_junit = {key: value for key, value in junit_report.items() if key != "testcase_identities"}
    if manifest.get("junit") != expected_junit:
        raise ReleaseBuildError("release manifest JUnit claims differ from parsed junit.xml")
    if manifest.get("expected_test_manifest_sha256") != sha256_file(expected_manifest_path):
        raise ReleaseBuildError("release expected-test manifest hash mismatch")

    git_receipt = read_json(git_receipt_path)
    git_receipt_keys = {
        "schema_id",
        "schema_version",
        "source_commit",
        "source_tree_git_oid",
        "source_tree_sha256",
        "source_file_count",
        "release_mode",
    }
    if set(git_receipt) != git_receipt_keys or git_receipt.get("schema_id") != "EvaluationGitSourceReceiptV1" or git_receipt.get("schema_version") != "1.0.0":
        raise ReleaseBuildError("Git source receipt shape/schema is invalid")
    source_claims = (
        "source_commit",
        "source_tree_git_oid",
        "source_tree_sha256",
        "source_file_count",
        "release_mode",
    )
    if any(manifest.get(field) != git_receipt.get(field) for field in source_claims):
        raise ReleaseBuildError("release manifest source claims differ from Git source receipt")
    if not isinstance(manifest.get("source_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]):
        raise ReleaseBuildError("release source commit is invalid")
    if not isinstance(manifest.get("source_tree_git_oid"), str) or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_tree_git_oid"]):
        raise ReleaseBuildError("release Git tree OID is invalid")
    if not isinstance(manifest.get("source_tree_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", manifest["source_tree_sha256"]):
        raise ReleaseBuildError("release source tree SHA256 is invalid")
    if isinstance(manifest.get("source_file_count"), bool) or not isinstance(manifest.get("source_file_count"), int) or manifest["source_file_count"] <= 0:
        raise ReleaseBuildError("release source file count is invalid")
    try:
        released_entries = read_source_zip(source_zip_path)
    except GitSourceError as exc:
        raise ReleaseBuildError(str(exc)) from exc
    if len(released_entries) != manifest["source_file_count"] or source_tree_sha256(released_entries) != manifest["source_tree_sha256"]:
        raise ReleaseBuildError("source ZIP count/tree SHA differs from release claims")
    released_by_path = dict(released_entries)
    committed_test_authority = released_by_path.get(f"evaluation/v1/authority/{MANIFEST_FILE}")
    if committed_test_authority != expected_manifest_path.read_bytes():
        raise ReleaseBuildError("expected-test manifest differs from committed source ZIP authority")
    ownership = read_json(ownership_path)
    if ownership != {"status": "PASS", "allowed_roots": list(SOURCE_ROOTS), "source_files": len(released_entries)}:
        raise ReleaseBuildError("source ownership evidence differs from inspected ZIP")
    forbidden_imports, credential_literals = _scan_source(released_entries)
    if read_json(static_scan_path) != {"status": "PASS", "forbidden_imports": forbidden_imports}:
        raise ReleaseBuildError("static scan evidence differs from inspected ZIP")
    if read_json(credential_scan_path) != {"status": "PASS", "credential_literals": credential_literals}:
        raise ReleaseBuildError("credential scan evidence differs from inspected ZIP")
    if manifest.get("registry_counts") != _released_registry_counts(released_entries):
        raise ReleaseBuildError("release registry counts differ from inspected ZIP")

    commands = read_json(commands_path)
    if set(commands) != {"test", "release", "network_calls"} or not all(isinstance(commands.get(key), str) and commands[key] for key in ("test", "release")) or commands.get("network_calls") != 0 or isinstance(commands.get("network_calls"), bool):
        raise ReleaseBuildError("release command evidence is invalid")
    environment = read_json(environment_path)
    if set(environment) != {"python", "platform", "source_commit", "network_calls", "provider_calls"}:
        raise ReleaseBuildError("release environment evidence shape is invalid")
    if not all(isinstance(environment.get(key), str) and environment[key] for key in ("python", "platform")) or environment.get("source_commit") != manifest["source_commit"]:
        raise ReleaseBuildError("release environment source identity is invalid")
    if environment.get("network_calls") != 0 or isinstance(environment.get("network_calls"), bool) or environment.get("provider_calls") != 0 or isinstance(environment.get("provider_calls"), bool):
        raise ReleaseBuildError("release environment reports network/provider activity")

    external_junit = manifest.get("external_junit")
    if external_junit is not None:
        try:
            external_path = resolve_contained_file(root, "external_junit.xml")
        except AuthorityError as exc:
            raise ReleaseBuildError("external JUnit evidence is missing or unsafe") from exc
        verified_external = verify_junit(external_path, expected_manifest_path=expected_manifest_path)
        expected_external = {key: value for key, value in verified_external.items() if key != "testcase_identities"}
        if external_junit != expected_external:
            raise ReleaseBuildError("external JUnit claims differ from its physical exact-test evidence")
    elif "external_junit.xml" in actual_paths:
        raise ReleaseBuildError("external JUnit file exists without a manifest claim")
    expected_lines = []
    for relative in sorted(actual_paths - {RELEASE_CHECKSUM_FILE}):
        path = resolve_contained_file(root, relative)
        expected_lines.append(f"{sha256_file(path)}  {relative}")
    if checksum_path.read_text(encoding="ascii").splitlines() != expected_lines:
        raise ReleaseBuildError("release CHECKSUMS drift")
    return manifest
