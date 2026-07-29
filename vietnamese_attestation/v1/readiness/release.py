"""Deterministic source release and readiness evidence for Evidence E."""

from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from ..dataset import (
    OFFICIAL_PILOT_MANIFEST_SHA256,
    OFFICIAL_PILOT_MEMBER_COUNT,
    OFFICIAL_PILOT_PIN_MAIN_COMMIT,
    OFFICIAL_PILOT_PIN_REF,
    OFFICIAL_PILOT_PIN_SHA256,
    OFFICIAL_PILOT_SENSE_COUNT,
    OFFICIAL_PILOT_ZIP_SHA256,
    OFFICIAL_PILOT_ZIP_REF,
    OfficialFrozenCandidateSet,
    load_official_frozen_candidate_zip,
)
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
    dataset_release_zip: str | Path | None = None,
    dataset_input_pin: str | Path | None = None,
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
    if (dataset_release_zip is None) != (dataset_input_pin is None):
        raise ValueError("Dataset ZIP and Main pin must be supplied together")
    official_dataset = (
        load_official_frozen_candidate_zip(
            dataset_release_zip,
            dataset_input_pin,
            expected_release_zip_sha256=OFFICIAL_PILOT_ZIP_SHA256,
            expected_manifest_sha256=OFFICIAL_PILOT_MANIFEST_SHA256,
            expected_pin_sha256=OFFICIAL_PILOT_PIN_SHA256,
        )
        if dataset_release_zip is not None
        else None
    )
    if official_dataset is not None:
        _verify_main_dataset_bridge(
            repository=repository,
            canonical_main=canonical_main,
            official_dataset=official_dataset,
        )

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
        official_dataset=official_dataset,
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
    holds = [
        "BLOCKED_BY_CONTROLLED_REGISTRY",
        "BLOCKED_BY_LIVE_CANARY_APPROVAL",
    ]
    if official_dataset is None:
        holds.insert(0, "BLOCKED_BY_DATASET_BINDING_COMPATIBILITY")
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
        "holds": holds,
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
    official_dataset: OfficialFrozenCandidateSet | None,
) -> dict[str, dict[str, Any]]:
    dataset_report = _dataset_input_report(official_dataset)
    has_official_dataset = official_dataset is not None
    findings = findings_report(
        canonical_main,
        dataset_conformance=dataset_report,
    )
    _validate_dataset_finding_consistency(dataset_report, findings)
    reports = {
        "git_commit_receipt.json": receipt,
        "authority_verification_report.json": seal(authority),
        "zero_api_verification_report.json": seal(
            _publication_projection(
                zero_api,
                artifact_ref="inputs/zero_api_artifact",
            )
        ),
        "junit_verification_report.json": seal(
            _publication_projection(junit_report, path="junit.xml")
        ),
        "dataset_input_conformance_report.json": seal(dataset_report),
        "controlled_registry_adapter_report.json": seal(
            _publication_projection(
                controlled,
                registry_ref="inputs/controlled_vietnamese_source_registry.jsonl",
            )
        ),
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
                "status": (
                    "BLOCKED_PENDING_OFFICIAL_E_PACKAGES"
                    if has_official_dataset
                    else "BLOCKED_DEVELOPMENT_IDENTITY"
                ),
                "artifact_class": (
                    "OFFICIAL_INPUT_CONFORMANCE_ONLY"
                    if has_official_dataset
                    else "OFFLINE_PROJECTION_CONFORMANCE_ONLY"
                ),
                "official_input_count": (
                    OFFICIAL_PILOT_MEMBER_COUNT if has_official_dataset else 0
                ),
                "projected_package_count": 0,
                "real_evidence_authority": False,
                "global_handoff_allowed": False,
                "final_glossary_decision": None,
            }
        ),
        "readiness_findings_report.json": seal(findings),
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
    _reject_absolute_publication_paths(reports)
    return reports


def _publication_projection(
    report: dict[str, Any],
    **replacements: Any,
) -> dict[str, Any]:
    projected = dict(report)
    projected.update(replacements)
    return projected


def _validate_dataset_finding_consistency(
    dataset_report: dict[str, Any],
    findings: dict[str, Any],
) -> None:
    rows = [
        row
        for row in findings.get("findings", [])
        if isinstance(row, dict) and row.get("finding_id") == "E-RDY-002"
    ]
    if len(rows) != 1:
        raise ValueError("readiness findings must contain exactly one E-RDY-002")
    dataset_pass = (
        dataset_report.get("status") == "PASS_EXACT_OFFICIAL_DATASET_BINDING"
    )
    if dataset_pass and (
        dataset_report.get("official_candidate_count") != OFFICIAL_PILOT_MEMBER_COUNT
        or dataset_report.get("required_candidate_count")
        != OFFICIAL_PILOT_MEMBER_COUNT
        or dataset_report.get("official_sense_count") != OFFICIAL_PILOT_SENSE_COUNT
        or dataset_report.get("required_sense_count") != OFFICIAL_PILOT_SENSE_COUNT
        or dataset_report.get("blockers") != []
    ):
        raise ValueError("Dataset conformance PASS has incomplete official binding")
    dataset_finding_resolved = rows[0].get("status") == "RESOLVED"
    if dataset_pass != dataset_finding_resolved:
        raise ValueError(
            "Dataset conformance and readiness E-RDY-002 status conflict"
        )


def _reject_absolute_publication_paths(
    reports: dict[str, dict[str, Any]],
) -> None:
    findings: list[str] = []

    def visit(value: Any, location: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{location}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{location}[{index}]")
        elif isinstance(value, str) and (
            PurePosixPath(value).is_absolute()
            or PureWindowsPath(value).is_absolute()
            or value.startswith("\\\\")
        ):
            findings.append(location)

    for name, report in reports.items():
        visit(report, name)
    if findings:
        raise ValueError(
            "release publication contains absolute paths: " + ", ".join(findings)
        )


def _dataset_input_report(
    official_dataset: OfficialFrozenCandidateSet | None,
) -> dict[str, Any]:
    if official_dataset is None:
        return {
            "schema_id": "VietnameseAttestationDatasetInputConformanceReportV1",
            "schema_version": "1.0.0",
            "status": "BLOCKED_BY_DATASET_BINDING_COMPATIBILITY",
            "official_candidate_count": 0,
            "required_candidate_count": OFFICIAL_PILOT_MEMBER_COUNT,
            "projection_conformance_package_count": 0,
            "real_attestation_package_count": 0,
            "blockers": ["EXACT_MAIN_PINNED_DATASET_PACKAGE_NOT_SUPPLIED"],
            "final_glossary_decision": None,
        }
    return {
        "schema_id": "VietnameseAttestationDatasetInputConformanceReportV1",
        "schema_version": "1.0.0",
        "status": "PASS_EXACT_OFFICIAL_DATASET_BINDING",
        "canonical_main_pin_commit": OFFICIAL_PILOT_PIN_MAIN_COMMIT,
        "dataset_release_zip_sha256": (
            official_dataset.release_zip_physical_sha256
        ),
        "dataset_manifest_sha256": official_dataset.manifest[
            "manifest_sha256"
        ],
        "dataset_manifest_physical_sha256": (
            official_dataset.manifest_physical_sha256
        ),
        "dataset_input_pin_sha256": official_dataset.receipt["integrity"][
            "self_sha256"
        ],
        "archive_member_count": official_dataset.archive_member_count,
        "official_candidate_count": len(official_dataset.candidates),
        "required_candidate_count": OFFICIAL_PILOT_MEMBER_COUNT,
        "official_sense_count": len(
            {
                row["candidate_key"]["sense_id"]
                for row in official_dataset.candidates
            }
        ),
        "required_sense_count": OFFICIAL_PILOT_SENSE_COUNT,
        "producer_component_id": (
            official_dataset.candidates[0]["input_provenance"]["component_id"]
        ),
        "projection_conformance_package_count": 0,
        "real_attestation_package_count": 0,
        "production_generation_status": "HOLD_UNTIL_15_ACCEPTED_C_PACKAGES",
        "blockers": [],
        "provider_call_count": 0,
        "final_glossary_decision": None,
    }


def _verify_main_dataset_bridge(
    *,
    repository: Path,
    canonical_main: str,
    official_dataset: OfficialFrozenCandidateSet,
) -> None:
    ancestor = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            OFFICIAL_PILOT_PIN_MAIN_COMMIT,
            canonical_main,
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestor.returncode != 0:
        raise ValueError("canonical main does not contain the accepted Dataset pin")
    pin_bytes = git_bytes(
        repository,
        "show",
        f"{OFFICIAL_PILOT_PIN_MAIN_COMMIT}:{OFFICIAL_PILOT_PIN_REF}",
    )
    zip_bytes = git_bytes(
        repository,
        "show",
        f"{OFFICIAL_PILOT_PIN_MAIN_COMMIT}:{OFFICIAL_PILOT_ZIP_REF}",
    )
    if hashlib.sha256(pin_bytes).hexdigest() != (
        official_dataset.receipt_physical_sha256
    ):
        raise ValueError("supplied Dataset pin bytes differ from canonical Main")
    if hashlib.sha256(zip_bytes).hexdigest() != OFFICIAL_PILOT_ZIP_SHA256:
        raise ValueError("canonical Main Dataset ZIP bytes differ from the accepted pin")


def _write_execution_evidence(release_root: Path, junit_path: str | Path) -> None:
    commands = (
        "python -m pytest -q vietnamese_attestation/v1/tests "
        "--junitxml=<junit-path>\n"
        "python -m vietnamese_attestation.v1.cli.readiness "
        "--repository-root <repo> --authority-receipt <receipt> "
        "--zero-api-artifact-root <artifact> --controlled-registry <registry> "
        "--dataset-release-zip <exact-zip> --dataset-input-pin <main-pin> "
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
