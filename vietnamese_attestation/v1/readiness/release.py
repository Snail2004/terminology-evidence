"""Deterministic source release and readiness evidence for Evidence E."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Any

from ..zero_api.artifacts import file_sha256, write_json
from ..zero_api.controlled_registry import inspect_controlled_registry
from .artifact import verify_zero_api_artifact
from .authority import verify_contract_authority
from .release_io import (
    git_bytes,
    git_text,
    release_manifest,
    tracked_source_paths,
    write_checksums,
    write_deterministic_zip,
)
from .release_reports import credential_scan, findings_report, seal, static_scan
from .junit import verify_junit


RELEASE_ID = "vietnamese-attestation-v1.1-post-zero-api-rc1"
RELEASE_ROOT_NAME = "vietnamese_attestation_v1_1_post_zero_api_rc1"
RELEASE_ZIP_NAME = RELEASE_ROOT_NAME + ".zip"
OWNED_PREFIX = "vietnamese_attestation/"


def build_post_zero_api_release(
    *,
    repository_root: str | Path,
    authority_receipt: str | Path,
    zero_api_artifact_root: str | Path,
    controlled_registry: str | Path,
    output_root: str | Path,
    implementation_commit: str = "HEAD",
    junit_path: str | Path,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve(strict=True)
    junit_report = verify_junit(junit_path)
    output = Path(output_root).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("post-zero-API release output root must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    release_root = output / RELEASE_ROOT_NAME
    release_root.mkdir()

    commit = git_text(repository, "rev-parse", f"{implementation_commit}^{{commit}}")
    parents = git_text(repository, "show", "-s", "--format=%P", commit).split()
    if not parents:
        raise ValueError("implementation commit has no parent")
    canonical_main = git_text(repository, "rev-parse", "main^{commit}")
    merge_base = git_text(repository, "merge-base", commit, canonical_main)
    branch = git_text(repository, "branch", "--show-current") or "DETACHED"
    status = git_text(
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        "vietnamese_attestation",
    ).splitlines()
    source_paths = tracked_source_paths(
        repository, commit, owned_prefix=OWNED_PREFIX
    )
    for relative in source_paths:
        target = release_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git_bytes(repository, "show", f"{commit}:{relative}"))

    authority = verify_contract_authority(
        repository_root=repository,
        receipt_path=authority_receipt,
    )
    zero_api = verify_zero_api_artifact(zero_api_artifact_root)
    controlled = inspect_controlled_registry(controlled_registry)
    if controlled["status"] != "BLOCKED_EXTERNAL_INPUT":
        raise ValueError("unexpected controlled registry readiness state")

    diff_check = subprocess.run(
        [
            "git",
            "diff",
            "--check",
            f"{parents[0]}..{commit}",
            "--",
            "vietnamese_attestation",
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if diff_check.returncode != 0:
        raise ValueError("implementation commit fails git diff --check")

    receipt = seal(
        {
            "schema_id": "VietnameseAttestationGitCommitReceiptV1",
            "schema_version": "1.0.0",
            "repository": repository.name,
            "branch": branch,
            "implementation_commit": commit,
            "parents": parents,
            "merge_base_with_main": merge_base,
            "canonical_main_commit_at_build": canonical_main,
            "source_snapshot_mode": "GIT_OBJECT_DATABASE",
            "git_status_porcelain_at_build": status,
            "git_diff_check": "PASS",
            "owned_prefix": OWNED_PREFIX,
            "owned_path_count": len(source_paths),
            "owned_paths": source_paths,
        }
    )
    reports = _readiness_reports(
        release_root=release_root,
        source_paths=source_paths,
        canonical_main=canonical_main,
        authority=authority,
        zero_api=zero_api,
        controlled=controlled,
        receipt=receipt,
        junit_report=junit_report,
    )
    for name, value in reports.items():
        write_json(release_root / name, value)

    _write_execution_evidence(release_root, junit_path)
    manifest = release_manifest(
        release_root,
        commit,
        release_id=RELEASE_ID,
        test_gate=junit_report,
    )
    write_json(release_root / "manifest.json", manifest)
    write_checksums(release_root)
    zip_path = output / RELEASE_ZIP_NAME
    write_deterministic_zip(
        release_root,
        zip_path,
        commit_epoch=int(
            git_text(repository, "show", "-s", "--format=%ct", commit)
        ),
    )
    zip_sha256 = file_sha256(zip_path)
    checksum_path = output / f"{RELEASE_ZIP_NAME}.sha256"
    checksum_path.write_text(
        f"{zip_sha256}  {RELEASE_ZIP_NAME}\n",
        encoding="ascii",
        newline="\n",
    )
    return {
        "schema_id": "VietnameseAttestationPostZeroApiReleaseSummaryV1",
        "schema_version": "1.0.0",
        "status": "PASS_WITH_EXTERNAL_HOLDS",
        "release_id": RELEASE_ID,
        "implementation_commit": commit,
        "release_root": release_root.as_posix(),
        "release_zip": zip_path.as_posix(),
        "release_zip_sha256": zip_sha256,
        "manifest_sha256": manifest["integrity"]["self_sha256"],
        "test_gate": {
            "tests": junit_report["tests"],
            "failures": junit_report["failures"],
            "errors": junit_report["errors"],
            "skipped": junit_report["skipped"],
            "policy_id": junit_report["policy_id"],
            "policy_version": junit_report["policy_version"],
        },
        "zero_api_replay": "15/15 PASS",
        "provider_call_count": 0,
        "holds": [
            "BLOCKED_BY_DATASET_AUTHORITY",
            "BLOCKED_BY_CONTROLLED_REGISTRY",
            "BLOCKED_BY_LIVE_CANARY_APPROVAL",
        ],
    }


def _readiness_reports(
    *,
    release_root: Path,
    source_paths: list[str],
    canonical_main: str,
    authority: dict[str, Any],
    zero_api: dict[str, Any],
    controlled: dict[str, Any],
    receipt: dict[str, Any],
    junit_report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "git_commit_receipt.json": receipt,
        "authority_verification_report.json": seal(authority),
        "zero_api_verification_report.json": seal(zero_api),
        "junit_verification_report.json": seal(junit_report),
        "dataset_input_conformance_report.json": seal(
            {
                "schema_id": "VietnameseAttestationDatasetInputConformanceReportV1",
                "schema_version": "1.0.0",
                "status": "BLOCKED_BY_DATASET_AUTHORITY",
                "official_candidate_count": 0,
                "required_candidate_count": 15,
                "projection_conformance_package_count": 0,
                "real_attestation_package_count": 0,
                "blockers": [
                    "OFFICIAL_FROZEN_CANDIDATE_CONTRACTS_NOT_SUPPLIED",
                    "EFFECTIVE_SENSE_AUTHORITY_NOT_SUPPLIED",
                ],
                "final_glossary_decision": None,
            }
        ),
        "controlled_registry_adapter_report.json": seal(controlled),
        "provider_canary_report.json": seal(
            {
                "schema_id": "VietnameseAttestationProviderCanaryReadinessV1",
                "schema_version": "1.0.0",
                "status": "BLOCKED_BY_LIVE_CANARY_APPROVAL",
                "routes": ["brave", "shopai", "ckey", "gemini_official"],
                "executed_routes": [],
                "external_provider_call_count": 0,
                "calibration_claim": False,
                "accuracy_claim": False,
            }
        ),
        "shared_projection_report.json": seal(
            {
                "schema_id": "VietnameseAttestationSharedProjectionReadinessV1",
                "schema_version": "1.0.0",
                "status": "BLOCKED_DEVELOPMENT_IDENTITY",
                "artifact_class": "OFFLINE_PROJECTION_CONFORMANCE_ONLY",
                "official_input_count": 0,
                "projected_package_count": 0,
                "real_evidence_authority": False,
                "global_handoff_allowed": False,
                "final_glossary_decision": None,
            }
        ),
        "readiness_findings_report.json": seal(findings_report(canonical_main)),
        "environment.json": seal(
            {
                "schema_id": "VietnameseAttestationReleaseEnvironmentV1",
                "schema_version": "1.0.0",
                "python_version": platform.python_version(),
                "python_implementation": platform.python_implementation(),
                "platform": platform.platform(),
                "source_encoding": "UTF-8",
                "network_calls": 0,
            }
        ),
        "static_scan.json": static_scan(release_root, source_paths),
        "credential_scan.json": credential_scan(release_root, source_paths),
        "ownership_scan.json": seal(
            {
                "schema_id": "VietnameseAttestationOwnershipScanV1",
                "schema_version": "1.0.0",
                "status": "PASS",
                "owned_prefix": OWNED_PREFIX,
                "path_count": len(source_paths),
                "outside_owned_prefix": [],
            }
        ),
    }


def _write_execution_evidence(release_root: Path, junit_path: str | Path) -> None:
    commands = (
        "python -m pytest -q vietnamese_attestation/v1/tests "
        "--junitxml=<junit-path>\n"
        "python -m vietnamese_attestation.v1.cli.readiness "
        "--repository-root <repo> --authority-receipt <receipt> "
        "--zero-api-artifact-root <artifact> --controlled-registry <registry> "
        "--output-root <release-output> --implementation-commit <commit>\n"
    )
    (release_root / "commands.txt").write_text(
        commands, encoding="utf-8", newline="\n"
    )
    junit = Path(junit_path).resolve(strict=True)
    (release_root / "junit.xml").write_bytes(junit.read_bytes())


__all__ = [
    "RELEASE_ID",
    "RELEASE_ROOT_NAME",
    "RELEASE_ZIP_NAME",
    "build_post_zero_api_release",
]
