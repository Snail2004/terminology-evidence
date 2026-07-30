"""Git-object-bound publication for the frozen 50/150 analysis plan."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.authority import AuthorityError, resolve_contained_file, secure_existing_directory
from ..jsonio import canonical_bytes, loads_strict, read_json, sha256_bytes, sha256_file, sha256_value, write_json
from ..release_tools.git_source import GitSourceError, materialize_commit, resolve_commit, source_entries
from ..release_tools.publication import PublicationError, external_atomic_stage
from .access import GENESIS_SHA256
from .builder import (
    ACCESS_TEMPLATES_FILE,
    CONTENT_DIRECTORY,
    EXPECTED_TEST_MANIFEST,
    PLAN_DOCUMENT,
    PLAN_FILE,
    REQUIREMENT_DOCUMENT,
    TABLES_FILE,
)
from .specification import PLAN_ID, STAGE_ORDER
from .verifier import AnalysisPlanError, verify_analysis_plan_content


FREEZE_RECEIPT_FILE = "analysis_plan_freeze_receipt_v1.json"
PUBLICATION_MANIFEST_FILE = "manifest.json"
PUBLICATION_CHECKSUMS_FILE = "CHECKSUMS.sha256"
FREEZE_STATUS = "ANALYSIS_PLAN_FROZEN_FOR_D0"

CONTENT_PATHS = (
    PLAN_DOCUMENT.as_posix(),
    REQUIREMENT_DOCUMENT.as_posix(),
    (CONTENT_DIRECTORY / PLAN_FILE).as_posix(),
    (CONTENT_DIRECTORY / ACCESS_TEMPLATES_FILE).as_posix(),
    (CONTENT_DIRECTORY / TABLES_FILE).as_posix(),
    EXPECTED_TEST_MANIFEST.as_posix(),
)
RECEIPT_PATH = (CONTENT_DIRECTORY / FREEZE_RECEIPT_FILE).as_posix()
MANIFEST_PATH = (CONTENT_DIRECTORY / PUBLICATION_MANIFEST_FILE).as_posix()


class AnalysisPlanPublicationError(ValueError):
    """Raised when the analysis-plan freeze cannot be proven from Git bytes."""


def _seal(value: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(value)
    sealed["integrity"] = {"self_sha256": ""}
    unsigned = dict(sealed)
    unsigned["integrity"] = {}
    sealed["integrity"]["self_sha256"] = sha256_value(unsigned)
    return sealed


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return canonical_bytes(value) + b"\n"


def _file_row(path: str, data: bytes) -> dict[str, Any]:
    return {"path": path, "bytes": len(data), "sha256": sha256_bytes(data)}


def _commit_parent(repo: Path, commit: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--parents", "-n", "1", commit],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AnalysisPlanPublicationError("cannot inspect analysis-plan content commit parent") from exc
    parts = completed.stdout.strip().lower().split()
    if len(parts) != 2 or parts[0] != commit:
        raise AnalysisPlanPublicationError("analysis-plan content commit must have exactly one parent")
    return parts[1]


def _committed_content(repo: Path, commit: str) -> tuple[str, str, dict[str, bytes]]:
    try:
        resolved, tree = resolve_commit(repo, commit)
        available = dict(source_entries(repo, resolved))
    except GitSourceError as exc:
        raise AnalysisPlanPublicationError(str(exc)) from exc
    missing = sorted(set(CONTENT_PATHS) - set(available))
    if missing:
        raise AnalysisPlanPublicationError(f"analysis-plan content commit is missing authority files: {missing}")
    return resolved, tree, {path: available[path] for path in CONTENT_PATHS}


def _verified_content(repo: Path, commit: str) -> tuple[str, str, str, dict[str, bytes], dict[str, Any]]:
    resolved, tree, content = _committed_content(repo, commit)
    parent = _commit_parent(repo, resolved)
    with tempfile.TemporaryDirectory(prefix="evaluation-analysis-plan-freeze-") as temporary:
        materialized = Path(temporary) / "source"
        try:
            materialize_commit(repo, resolved, materialized)
            report = verify_analysis_plan_content(materialized)
        except (GitSourceError, AnalysisPlanError) as exc:
            raise AnalysisPlanPublicationError(str(exc)) from exc
        plan = read_json(materialized / CONTENT_DIRECTORY / PLAN_FILE)
        expected_test = read_json(materialized / EXPECTED_TEST_MANIFEST)
    if plan.get("source_parent_commit") != parent:
        raise AnalysisPlanPublicationError("analysis plan does not bind the exact parent of its content commit")
    return resolved, tree, parent, content, {
        "report": report,
        "plan": plan,
        "expected_test": expected_test,
    }


def _expected_publication(repo: Path, commit: str) -> tuple[dict[str, Any], dict[str, Any], bytes, dict[str, bytes]]:
    resolved, tree, parent, content, verified = _verified_content(repo, commit)
    plan = verified["plan"]
    report = verified["report"]
    expected_test = verified["expected_test"]
    content_rows = [_file_row(path, content[path]) for path in sorted(content)]
    receipt = _seal(
        {
            "schema_id": "EvaluationAnalysisPlanFreezeReceiptV1",
            "schema_version": "1.0.0",
            "status": FREEZE_STATUS,
            "plan_id": PLAN_ID,
            "frozen_at": plan["frozen_at"],
            "content_commit": resolved,
            "content_tree_git_oid": tree,
            "content_parent_commit": parent,
            "scope": plan["scope"],
            "plan_self_sha256": report["plan_self_sha256"],
            "planned_tables_self_sha256": report["tables_self_sha256"],
            "gold_access_templates_self_sha256": report["gold_access_templates_self_sha256"],
            "expected_test_authority": {
                "path": EXPECTED_TEST_MANIFEST.as_posix(),
                "physical_sha256": sha256_bytes(content[EXPECTED_TEST_MANIFEST.as_posix()]),
                "canonical_self_sha256": expected_test["integrity"]["self_sha256"],
                "testcase_identity_sha256": expected_test["testcase_identity_sha256"],
                "test_count": expected_test["test_count"],
            },
            "content_files": content_rows,
            "access_order": list(STAGE_ORDER),
            "access_state": {
                "producer_outputs_opened": False,
                "gold_opened": False,
                "validation_opened": False,
                "held_out_test_opened": False,
                "actual_gold_access_receipt_count": 0,
                "gold_access_ledger_head": GENESIS_SHA256,
            },
            "network_calls": 0,
            "provider_calls": 0,
        }
    )
    receipt_bytes = _json_bytes(receipt)
    files = content_rows + [_file_row(RECEIPT_PATH, receipt_bytes)]
    files.sort(key=lambda row: row["path"])
    manifest = _seal(
        {
            "schema_id": "EvaluationAnalysisPlanPublicationManifestV1",
            "schema_version": "1.0.0",
            "status": FREEZE_STATUS,
            "plan_id": PLAN_ID,
            "content_commit": resolved,
            "content_tree_git_oid": tree,
            "content_parent_commit": parent,
            "freeze_receipt_self_sha256": receipt["integrity"]["self_sha256"],
            "file_count": len(files),
            "files": files,
            "network_calls": 0,
            "provider_calls": 0,
        }
    )
    manifest_bytes = _json_bytes(manifest)
    checksummed = dict(content)
    checksummed[RECEIPT_PATH] = receipt_bytes
    checksummed[MANIFEST_PATH] = manifest_bytes
    checksum_bytes = (
        "\n".join(f"{sha256_bytes(checksummed[path])}  {path}" for path in sorted(checksummed)) + "\n"
    ).encode("ascii")
    return receipt, manifest, checksum_bytes, content


def _bundle_file(root: Path, name: str) -> Path:
    try:
        return resolve_contained_file(root, name)
    except AuthorityError as exc:
        raise AnalysisPlanPublicationError(str(exc)) from exc


def _verify_live_content(repo: Path, content: Mapping[str, bytes]) -> None:
    for relative, expected in content.items():
        try:
            path = resolve_contained_file(repo, relative)
        except AuthorityError as exc:
            raise AnalysisPlanPublicationError(str(exc)) from exc
        if path.read_bytes() != expected:
            raise AnalysisPlanPublicationError(f"working analysis-plan authority differs from content commit: {relative}")


def verify_analysis_plan_publication(repo: Path, *, bundle_root: Path | None = None) -> dict[str, Any]:
    try:
        repository = secure_existing_directory(repo, field="analysis_plan_publication_repo")
        bundle = secure_existing_directory(
            bundle_root or repository / CONTENT_DIRECTORY,
            field="analysis_plan_publication_bundle",
        )
    except AuthorityError as exc:
        raise AnalysisPlanPublicationError(str(exc)) from exc
    receipt_path = _bundle_file(bundle, FREEZE_RECEIPT_FILE)
    manifest_path = _bundle_file(bundle, PUBLICATION_MANIFEST_FILE)
    checksums_path = _bundle_file(bundle, PUBLICATION_CHECKSUMS_FILE)
    try:
        receipt = loads_strict(receipt_path.read_text(encoding="utf-8"))
        manifest = loads_strict(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnalysisPlanPublicationError("analysis-plan publication JSON is invalid") from exc
    commit = receipt.get("content_commit") if isinstance(receipt, Mapping) else None
    if not isinstance(commit, str):
        raise AnalysisPlanPublicationError("freeze receipt content commit is missing")
    expected_receipt, expected_manifest, expected_checksums, content = _expected_publication(repository, commit)
    if receipt != expected_receipt:
        raise AnalysisPlanPublicationError("freeze receipt differs from exact Git-object authority")
    if manifest != expected_manifest:
        raise AnalysisPlanPublicationError("publication manifest differs from exact Git-object authority")
    if checksums_path.read_bytes() != expected_checksums:
        raise AnalysisPlanPublicationError("analysis-plan publication CHECKSUMS drifted")
    _verify_live_content(repository, content)
    return {
        "status": FREEZE_STATUS,
        "content_commit": receipt["content_commit"],
        "content_tree_git_oid": receipt["content_tree_git_oid"],
        "plan_self_sha256": receipt["plan_self_sha256"],
        "freeze_receipt_self_sha256": receipt["integrity"]["self_sha256"],
        "freeze_receipt_physical_sha256": sha256_file(receipt_path),
        "manifest_self_sha256": manifest["integrity"]["self_sha256"],
        "manifest_physical_sha256": sha256_file(manifest_path),
        "checksums_physical_sha256": sha256_file(checksums_path),
        "actual_gold_access_receipt_count": 0,
        "network_calls": 0,
        "provider_calls": 0,
    }


def build_analysis_plan_publication(*, repo: Path, content_commit: str, output: Path) -> dict[str, Any]:
    try:
        repository = secure_existing_directory(repo, field="analysis_plan_publication_repo")
        receipt, manifest, checksums, _content = _expected_publication(repository, content_commit)
        with external_atomic_stage(output, repository) as stage:
            write_json(stage / FREEZE_RECEIPT_FILE, receipt)
            write_json(stage / PUBLICATION_MANIFEST_FILE, manifest)
            (stage / PUBLICATION_CHECKSUMS_FILE).write_bytes(checksums)
            verify_analysis_plan_publication(repository, bundle_root=stage)
        return verify_analysis_plan_publication(repository, bundle_root=output)
    except (AuthorityError, PublicationError, OSError, ValueError) as exc:
        if isinstance(exc, AnalysisPlanPublicationError):
            raise
        raise AnalysisPlanPublicationError(str(exc)) from exc
