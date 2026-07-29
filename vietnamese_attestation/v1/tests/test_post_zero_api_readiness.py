from __future__ import annotations

import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from vietnamese_attestation.v1.readiness import (
    build_post_zero_api_release,
    verify_contract_authority,
    verify_junit,
    verify_zero_api_artifact,
)
from vietnamese_attestation.v1.cli.readiness import main as readiness_cli_main
from vietnamese_attestation.v1.zero_api.artifacts import (
    file_sha256,
    self_sha256,
    verify_self_sha256,
)


AUTHORITY_RECEIPT = Path(
    r"C:\work\terminology-evidence-authority\contracts-v1.1.0\authority_receipt.json"
)
ZERO_API_ARTIFACT = Path(
    r"C:\work\terminology-evidence-artifacts\vietnamese-attestation-v1.1-zero-api-20260729-v3"
)


def test_authority_and_zero_api_artifact_verify_without_provider_calls() -> None:
    repository = _repository_root()
    authority = verify_contract_authority(
        repository_root=repository,
        receipt_path=AUTHORITY_RECEIPT,
    )
    artifact = verify_zero_api_artifact(ZERO_API_ARTIFACT)

    assert authority["status"] == "PASS"
    assert authority["provider_call_count"] == 0
    assert artifact["status"] == "PASS"
    assert artifact["candidate_count"] == 15
    assert artifact["replay_pass_count"] == 15
    assert artifact["manifest_file_count"] == 273
    assert artifact["shared_projection_status"] == (
        "BLOCKED_DEVELOPMENT_IDENTITY"
    )
    assert artifact["controlled_registry_status"] == "BLOCKED_EXTERNAL_INPUT"
    assert artifact["external_provider_call_count"] == 0
    assert artifact["final_glossary_decision"] is None


def test_strict_persisted_decoder_rejects_ambiguous_json(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(ZERO_API_ARTIFACT, artifact)
    summary_path = artifact / "pilot_zero_api_summary.json"
    original = summary_path.read_bytes()
    invalid_payloads = [
        b'{"candidate_count":15,"candidate_count":15}',
        b'{"integrity":{"self_sha256":"a","self_sha256":"b"}}',
        b'{"candidate_count":1e999}',
        b'{"candidate_count":NaN}',
        b'{"candidate_count":15} trailing',
        b'{"candidate_count":15}\x80',
    ]
    try:
        for payload in invalid_payloads:
            summary_path.write_bytes(payload)
            with pytest.raises(ValueError):
                verify_zero_api_artifact(artifact)
    finally:
        summary_path.write_bytes(original)


def test_manifest_refs_reject_unsafe_and_case_confusable_paths(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(ZERO_API_ARTIFACT, artifact)
    manifest_path = artifact / "zero_api_artifact_manifest.json"
    original = manifest_path.read_bytes()
    unsafe_refs = [
        "packages/example.json:outside",
        "packages\\example.json",
        "/absolute/example.json",
        "../outside.json",
        "packages//example.json",
        "packages/./example.json",
    ]
    try:
        baseline = json.loads(original)
        for reference in unsafe_refs:
            mutated = json.loads(original)
            mutated["files"][0]["artifact_ref"] = reference
            mutated["integrity"]["self_sha256"] = self_sha256(mutated)
            manifest_path.write_text(
                json.dumps(mutated, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with pytest.raises(ValueError):
                verify_zero_api_artifact(artifact)

        duplicate = json.loads(original)
        duplicate["files"].append(dict(baseline["files"][0]))
        duplicate["files"][-1]["artifact_ref"] = (
            duplicate["files"][0]["artifact_ref"].upper()
        )
        duplicate["file_count"] = len(duplicate["files"])
        duplicate["integrity"]["self_sha256"] = self_sha256(duplicate)
        manifest_path.write_text(
            json.dumps(duplicate, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="case-confusable"):
            verify_zero_api_artifact(artifact)
    finally:
        manifest_path.write_bytes(original)


def test_provider_ledger_duplicate_key_is_rejected(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(ZERO_API_ARTIFACT, artifact)
    ledger = artifact / "provider_attempts.jsonl"
    original = ledger.read_bytes()
    try:
        ledger.write_bytes(b'{"run_id":"a","run_id":"b"}\n')
        with pytest.raises(ValueError, match="JSONL"):
            verify_zero_api_artifact(artifact)
    finally:
        ledger.write_bytes(original)


def test_artifact_symlink_is_rejected_when_supported(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(ZERO_API_ARTIFACT, artifact)
    victim = next((artifact / "packages").glob("*.json"))
    outside = tmp_path / "outside.json"
    outside.write_bytes(victim.read_bytes())
    victim.unlink()
    try:
        os.symlink(outside, victim)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(ValueError, match="symlink or junction"):
        verify_zero_api_artifact(artifact)


def test_junit_gate_rejects_missing_empty_red_wrong_and_unrelated_reports(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.xml"
    with pytest.raises(ValueError):
        verify_junit(missing)

    cases = (
        ("malformed.xml", "<testsuites>"),
        ("empty.xml", _junit_xml(0)),
        ("red.xml", _junit_xml(74, failures=1)),
        ("wrong-count.xml", _junit_xml(73)),
        ("unrelated.xml", _junit_xml(74, classname="other.tests.Case")),
    )
    for filename, content in cases:
        path = tmp_path / filename
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            verify_junit(path)

    wrong_count = tmp_path / "wrong-count-release.xml"
    wrong_count.write_text(_junit_xml(73), encoding="utf-8")
    output = tmp_path / "wrong-count-release"
    with pytest.raises(ValueError, match="count mismatch"):
        build_post_zero_api_release(
            repository_root=_repository_root(),
            authority_receipt=AUTHORITY_RECEIPT,
            zero_api_artifact_root=ZERO_API_ARTIFACT,
            controlled_registry=(
                _repository_root()
                / "dataset"
                / "dataset_methodology_hardening_v1"
                / "release"
                / "controlled_vietnamese_source_registry.jsonl"
            ),
            output_root=output,
            implementation_commit=_git(_repository_root(), "rev-parse", "HEAD"),
            junit_path=wrong_count,
        )
    assert not output.exists()

    with pytest.raises(SystemExit):
        readiness_cli_main(
            [
                "--repository-root",
                str(_repository_root()),
                "--authority-receipt",
                str(AUTHORITY_RECEIPT),
                "--zero-api-artifact-root",
                str(ZERO_API_ARTIFACT),
                "--controlled-registry",
                str(
                    _repository_root()
                    / "dataset"
                    / "dataset_methodology_hardening_v1"
                    / "release"
                    / "controlled_vietnamese_source_registry.jsonl"
                ),
                "--output-root",
                str(tmp_path / "missing-junit-release"),
            ]
        )


def test_authority_and_zero_api_tamper_fail_closed(tmp_path: Path) -> None:
    receipt = tmp_path / "authority_receipt.json"
    receipt.write_bytes(AUTHORITY_RECEIPT.read_bytes() + b" ")
    with pytest.raises(ValueError, match="receipt physical hash mismatch"):
        verify_contract_authority(
            repository_root=_repository_root(),
            receipt_path=receipt,
        )

    artifact = tmp_path / "artifact"
    shutil.copytree(ZERO_API_ARTIFACT, artifact)
    summary_path = artifact / "pilot_zero_api_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["candidate_count"] = 14
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="summary canonical self hash mismatch"):
        verify_zero_api_artifact(artifact)


def test_post_zero_api_release_is_commit_bound_cache_free_and_honest(
    tmp_path: Path,
) -> None:
    repository = _repository_root()
    commit = _git(repository, "rev-parse", "HEAD")
    summary = build_post_zero_api_release(
        repository_root=repository,
        authority_receipt=AUTHORITY_RECEIPT,
        zero_api_artifact_root=ZERO_API_ARTIFACT,
        controlled_registry=(
            repository
            / "dataset"
            / "dataset_methodology_hardening_v1"
            / "release"
            / "controlled_vietnamese_source_registry.jsonl"
        ),
        output_root=tmp_path / "release",
        implementation_commit=commit,
        junit_path=(
            _write_junit(tmp_path / "valid.xml")
        ),
    )

    assert summary["status"] == "PASS_WITH_EXTERNAL_HOLDS"
    assert summary["implementation_commit"] == commit
    assert summary["zero_api_replay"] == "15/15 PASS"
    assert summary["provider_call_count"] == 0
    assert summary["test_gate"]["tests"] == 74
    assert summary["test_gate"]["failures"] == 0
    assert summary["test_gate"]["errors"] == 0
    assert summary["holds"] == [
        "BLOCKED_BY_DATASET_AUTHORITY",
        "BLOCKED_BY_CONTROLLED_REGISTRY",
        "BLOCKED_BY_LIVE_CANARY_APPROVAL",
    ]

    release_root = Path(summary["release_root"])
    manifest = _load(release_root / "manifest.json")
    receipt = _load(release_root / "git_commit_receipt.json")
    findings = _load(release_root / "readiness_findings_report.json")
    dataset = _load(release_root / "dataset_input_conformance_report.json")
    projection = _load(release_root / "shared_projection_report.json")
    canary = _load(release_root / "provider_canary_report.json")
    junit = _load(release_root / "junit_verification_report.json")

    assert verify_self_sha256(manifest)
    assert verify_self_sha256(receipt)
    assert receipt["implementation_commit"] == commit
    assert receipt["source_snapshot_mode"] == "GIT_OBJECT_DATABASE"
    assert findings["status"] == "HOLD_EXTERNAL_INPUTS"
    assert dataset["status"] == "BLOCKED_BY_DATASET_AUTHORITY"
    assert projection["artifact_class"] == "OFFLINE_PROJECTION_CONFORMANCE_ONLY"
    assert projection["real_evidence_authority"] is False
    assert canary["status"] == "BLOCKED_BY_LIVE_CANARY_APPROVAL"
    assert canary["external_provider_call_count"] == 0
    assert junit["tests"] == 74

    for record in manifest["files"]:
        path = release_root / record["path"]
        assert path.is_file()
        assert path.stat().st_size == record["size_bytes"]
        assert file_sha256(path) == record["sha256"]
    assert not any(
        "__pycache__" in path.parts
        or ".pytest_cache" in path.parts
        or path.suffix in {".pyc", ".pyo"}
        for path in release_root.rglob("*")
    )

    zip_path = Path(summary["release_zip"])
    assert file_sha256(zip_path) == summary["release_zip_sha256"]
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert names == sorted(names)
    assert not any(
        "__pycache__" in name or ".pytest_cache" in name or name.endswith(".pyc")
        for name in names
    )

    second = build_post_zero_api_release(
        repository_root=repository,
        authority_receipt=AUTHORITY_RECEIPT,
        zero_api_artifact_root=ZERO_API_ARTIFACT,
        controlled_registry=(
            repository
            / "dataset"
            / "dataset_methodology_hardening_v1"
            / "release"
            / "controlled_vietnamese_source_registry.jsonl"
        ),
        output_root=tmp_path / "release-second",
        implementation_commit=commit,
        junit_path=tmp_path / "valid.xml",
    )
    assert second["release_zip_sha256"] == summary["release_zip_sha256"]


def _repository_root() -> Path:
    root = Path(__file__).resolve().parents[3]
    assert AUTHORITY_RECEIPT.is_file()
    assert ZERO_API_ARTIFACT.is_dir()
    return root


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_junit(path: Path) -> Path:
    path.write_text(_junit_xml(74), encoding="utf-8")
    return path


def _junit_xml(
    count: int,
    *,
    failures: int = 0,
    errors: int = 0,
    classname: str = "vietnamese_attestation.v1.tests.synthetic",
) -> str:
    cases = "".join(
        f'<testcase classname="{classname}" name="case-{index}" />'
        for index in range(count)
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites name="pytest tests">'
        f'<testsuite name="pytest" tests="{count}" failures="{failures}" '
        f'errors="{errors}" skipped="0">{cases}</testsuite>'
        '</testsuites>'
    )
