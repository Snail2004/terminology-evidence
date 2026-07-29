from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from vietnamese_attestation.v1.readiness import (
    build_post_zero_api_release,
    verify_contract_authority,
    verify_zero_api_artifact,
)
from vietnamese_attestation.v1.zero_api.artifacts import (
    file_sha256,
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
            repository
            / "vietnamese_attestation"
            / "v1"
            / "docs"
            / "test-results-v1.1.xml"
        ),
    )

    assert summary["status"] == "PASS_WITH_EXTERNAL_HOLDS"
    assert summary["implementation_commit"] == commit
    assert summary["zero_api_replay"] == "15/15 PASS"
    assert summary["provider_call_count"] == 0
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
