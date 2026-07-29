from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pytest
import vietnamese_attestation.v1.readiness.release as release_module

from vietnamese_attestation.v1.readiness import (
    build_post_zero_api_release,
    verify_contract_authority,
    verify_junit,
    verify_zero_api_artifact,
)
from vietnamese_attestation.v1.readiness.authority import (
    R2_PUBLICATION_COMMIT,
    R2_RECEIPT_RELATIVE_PATH,
)
from vietnamese_attestation.v1.readiness.junit import (
    EXPECTED_E_SUITE_TEST_COUNT,
    EXPECTED_E_SUITE_TESTCASE_IDENTITIES,
)
from vietnamese_attestation.v1.cli.readiness import main as readiness_cli_main
from vietnamese_attestation.v1.dataset import (
    OFFICIAL_PILOT_MANIFEST_SHA256,
    OFFICIAL_PILOT_MEMBER_COUNT,
    OFFICIAL_PILOT_PIN_SHA256,
    OFFICIAL_PILOT_ZIP_SHA256,
)
from vietnamese_attestation.v1.zero_api.artifacts import (
    file_sha256,
    self_sha256,
    verify_self_sha256,
)
from vietnamese_attestation.v1.zero_api.pilot import run_zero_api_pilot


OFFICIAL_DATASET_RELATIVE = Path(
    "review_evidence/dataset/d2l-stage-a-official-5-sense-pilot-v1"
)


@pytest.fixture(scope="session")
def r2_repository(tmp_path_factory: pytest.TempPathFactory) -> Path:
    source = _repository_root()
    if (source / R2_RECEIPT_RELATIVE_PATH).is_file():
        return source

    repository = tmp_path_factory.mktemp("contracts-r2") / "repository"
    _run_git(None, "clone", "--quiet", "--shared", "--no-checkout", str(source), str(repository))
    _run_git(repository, "checkout", "--quiet", "--detach", R2_PUBLICATION_COMMIT)
    _run_git(
        repository,
        "update-ref",
        "refs/heads/main",
        _git(source, "rev-parse", "main^{commit}"),
    )
    return repository


@pytest.fixture(scope="session")
def zero_api_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repository = _repository_root()
    output = tmp_path_factory.mktemp("zero-api-readiness") / "artifact"
    summary = run_zero_api_pilot(
        source_zip=repository / "dataset" / "pilot_dev_only_v1_1.zip",
        parent_v3_zip=(
            repository
            / "dataset"
            / "d2l_context_support_set_validation_ready_v3.zip"
        ),
        output_root=output,
        controlled_registry=(
            repository
            / "dataset"
            / "dataset_methodology_hardening_v1"
            / "release"
            / "controlled_vietnamese_source_registry.jsonl"
        ),
    )
    assert summary["candidate_count"] == 15
    assert summary["replay_pass_count"] == 15
    assert summary["external_provider_call_count"] == 0
    return output


def test_r2_authority_and_zero_api_artifact_verify_without_provider_calls(
    r2_repository: Path,
    zero_api_artifact: Path,
) -> None:
    repository = r2_repository
    authority = verify_contract_authority(
        repository_root=repository,
        receipt_path=_r2_receipt(repository),
    )
    artifact = verify_zero_api_artifact(zero_api_artifact)

    assert authority["status"] == "PASS"
    assert authority["provider_call_count"] == 0
    assert authority["authority_receipt_revision"] == 2
    assert authority["release_delta_mode"] == "PINNED_R2_RELEASE_ONLY"
    assert authority["r2_publication_commit"] == R2_PUBLICATION_COMMIT
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


def test_strict_persisted_decoder_rejects_ambiguous_json(
    tmp_path: Path,
    zero_api_artifact: Path,
) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(zero_api_artifact, artifact)
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
    zero_api_artifact: Path,
) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(zero_api_artifact, artifact)
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


def test_provider_ledger_duplicate_key_is_rejected(
    tmp_path: Path,
    zero_api_artifact: Path,
) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(zero_api_artifact, artifact)
    ledger = artifact / "provider_attempts.jsonl"
    original = ledger.read_bytes()
    try:
        ledger.write_bytes(b'{"run_id":"a","run_id":"b"}\n')
        with pytest.raises(ValueError, match="JSONL"):
            verify_zero_api_artifact(artifact)
    finally:
        ledger.write_bytes(original)


def test_artifact_symlink_is_rejected_when_supported(
    tmp_path: Path,
    zero_api_artifact: Path,
) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(zero_api_artifact, artifact)
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
    r2_repository: Path,
    zero_api_artifact: Path,
) -> None:
    missing = tmp_path / "missing.xml"
    with pytest.raises(ValueError):
        verify_junit(missing)

    cases = (
        ("malformed.xml", "<testsuites>"),
        ("empty.xml", _junit_xml(0)),
        (
            "red.xml",
            _junit_xml(EXPECTED_E_SUITE_TEST_COUNT, failures=1),
        ),
        (
            "wrong-count.xml",
            _junit_xml(EXPECTED_E_SUITE_TEST_COUNT - 1),
        ),
        (
            "unrelated.xml",
            _junit_xml(
                EXPECTED_E_SUITE_TEST_COUNT,
                classname="other.tests.Case",
            ),
        ),
        (
            "skipped-declared.xml",
            _junit_xml(
                EXPECTED_E_SUITE_TEST_COUNT,
                skipped=EXPECTED_E_SUITE_TEST_COUNT,
            ),
        ),
        (
            "skipped-element.xml",
            _junit_xml(
                EXPECTED_E_SUITE_TEST_COUNT,
                testcase_skipped=True,
            ),
        ),
        (
            "fabricated-prefix.xml",
            _junit_xml(
                EXPECTED_E_SUITE_TEST_COUNT,
                classname="vietnamese_attestation.v1.tests.fabricated",
            ),
        ),
        (
            "renamed.xml",
            _junit_xml(
                EXPECTED_E_SUITE_TEST_COUNT,
                identities=(
                    "vietnamese_attestation.v1.tests.renamed::forged",
                    *EXPECTED_E_SUITE_TESTCASE_IDENTITIES[1:],
                ),
            ),
        ),
        (
            "missing-with-fake.xml",
            _junit_xml(
                EXPECTED_E_SUITE_TEST_COUNT,
                identities=(
                    *EXPECTED_E_SUITE_TESTCASE_IDENTITIES[:-1],
                    "vietnamese_attestation.v1.tests.synthetic::replacement",
                ),
            ),
        ),
    )
    for filename, content in cases:
        path = tmp_path / filename
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            verify_junit(path)

    wrong_count = tmp_path / "wrong-count-release.xml"
    wrong_count.write_text(
        _junit_xml(EXPECTED_E_SUITE_TEST_COUNT - 1), encoding="utf-8"
    )
    output = tmp_path / "wrong-count-release"
    with pytest.raises(ValueError, match="count mismatch"):
        build_post_zero_api_release(
            repository_root=r2_repository,
            authority_receipt=_r2_receipt(r2_repository),
            zero_api_artifact_root=zero_api_artifact,
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
                str(r2_repository),
                "--authority-receipt",
                str(_r2_receipt(r2_repository)),
                "--zero-api-artifact-root",
                str(zero_api_artifact),
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


def test_r2_authority_and_zero_api_tamper_fail_closed(
    tmp_path: Path,
    r2_repository: Path,
    zero_api_artifact: Path,
) -> None:
    tampered_repository = _clone_repository(
        r2_repository, tmp_path / "tampered-repository"
    )
    receipt = _r2_receipt(tampered_repository)
    receipt.write_bytes(receipt.read_bytes() + b" ")
    with pytest.raises(ValueError, match="receipt physical hash mismatch"):
        verify_contract_authority(
            repository_root=tampered_repository,
            receipt_path=receipt,
        )

    legacy_receipt = (
        r2_repository
        / "terminology_contracts_v1"
        / "release"
        / "v1.1.0-final"
        / "history"
        / "contracts_v1_1_0_authority_receipt_r1_resealed.json"
    )
    with pytest.raises(ValueError, match="canonical in-repo.*R2"):
        verify_contract_authority(
            repository_root=r2_repository,
            receipt_path=legacy_receipt,
        )

    artifact = tmp_path / "artifact"
    shutil.copytree(zero_api_artifact, artifact)
    summary_path = artifact / "pilot_zero_api_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["candidate_count"] = 14
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="summary canonical self hash mismatch"):
        verify_zero_api_artifact(artifact)


def test_r2_authority_rejects_nonrelease_and_arbitrary_release_drift(
    tmp_path: Path,
    r2_repository: Path,
) -> None:
    mutations = (
        ("nonrelease", "terminology_contracts_v1/README.md", "\nR2 drift\n"),
        (
            "release",
            "terminology_contracts_v1/release/unreviewed.txt",
            "unreviewed release mutation\n",
        ),
    )
    for name, relative, payload in mutations:
        repository = _clone_repository(
            r2_repository, tmp_path / f"{name}-repository"
        )
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.write_text(
                path.read_text(encoding="utf-8") + payload,
                encoding="utf-8",
            )
        else:
            path.write_text(payload, encoding="utf-8")
        _run_git(repository, "add", "--", relative)
        _run_git(
            repository,
            "-c",
            "user.name=E readiness test",
            "-c",
            "user.email=e-readiness@example.invalid",
            "commit",
            "--quiet",
            "-m",
            f"test {name} drift",
        )
        with pytest.raises(ValueError, match="contracts tree differs"):
            verify_contract_authority(
                repository_root=repository,
                receipt_path=_r2_receipt(repository),
            )


def test_post_zero_api_release_is_commit_bound_cache_free_and_honest(
    tmp_path: Path,
    r2_repository: Path,
    zero_api_artifact: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = r2_repository
    source = _repository_root()
    commit = _git(source, "rev-parse", "HEAD")
    official_dataset = _official_dataset_paths()
    summary = build_post_zero_api_release(
        repository_root=repository,
        authority_receipt=_r2_receipt(repository),
        zero_api_artifact_root=zero_api_artifact,
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
        dataset_release_zip=official_dataset["zip"],
        dataset_input_pin=official_dataset["pin"],
    )

    assert summary["status"] == "PASS_WITH_EXTERNAL_HOLDS"
    assert summary["implementation_commit"] == commit
    assert summary["zero_api_replay"] == "15/15 PASS"
    assert summary["provider_call_count"] == 0
    assert summary["test_gate"]["tests"] == EXPECTED_E_SUITE_TEST_COUNT
    assert summary["test_gate"]["failures"] == 0
    assert summary["test_gate"]["errors"] == 0
    assert summary["holds"] == [
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
    zero_api_report = _load(release_root / "zero_api_verification_report.json")
    controlled_report = _load(
        release_root / "controlled_registry_adapter_report.json"
    )

    assert verify_self_sha256(manifest)
    assert verify_self_sha256(receipt)
    assert receipt["implementation_commit"] == commit
    assert receipt["source_snapshot_mode"] == "GIT_OBJECT_DATABASE"
    assert findings["status"] == "HOLD_EXTERNAL_INPUTS"
    findings_by_id = {row["finding_id"]: row for row in findings["findings"]}
    assert findings_by_id["E-RDY-002"]["status"] == "RESOLVED"
    assert dataset["status"] == "PASS_EXACT_OFFICIAL_DATASET_BINDING"
    assert dataset["dataset_release_zip_sha256"] == OFFICIAL_PILOT_ZIP_SHA256
    assert dataset["dataset_manifest_sha256"] == OFFICIAL_PILOT_MANIFEST_SHA256
    assert dataset["dataset_input_pin_sha256"] == OFFICIAL_PILOT_PIN_SHA256
    assert dataset["official_candidate_count"] == OFFICIAL_PILOT_MEMBER_COUNT
    assert projection["artifact_class"] == "OFFICIAL_INPUT_CONFORMANCE_ONLY"
    assert projection["real_evidence_authority"] is False
    assert canary["status"] == "BLOCKED_BY_LIVE_CANARY_APPROVAL"
    assert canary["external_provider_call_count"] == 0
    assert junit["tests"] == EXPECTED_E_SUITE_TEST_COUNT
    assert junit["path"] == "junit.xml"
    assert zero_api_report["artifact_ref"] == "inputs/zero_api_artifact"
    assert controlled_report["registry_ref"] == (
        "inputs/controlled_vietnamese_source_registry.jsonl"
    )
    assert _absolute_json_path_findings(release_root) == []

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
        authority_receipt=_r2_receipt(repository),
        zero_api_artifact_root=zero_api_artifact,
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
        dataset_release_zip=official_dataset["zip"],
        dataset_input_pin=official_dataset["pin"],
    )
    assert second["release_zip_sha256"] == summary["release_zip_sha256"]

    original_findings_report = release_module.findings_report

    def stale_findings_report(
        canonical_main: str,
        *,
        dataset_conformance: dict[str, object] | None = None,
    ) -> dict[str, object]:
        del dataset_conformance
        return original_findings_report(canonical_main)

    contradictory_output = tmp_path / "release-contradictory"
    with monkeypatch.context() as patcher:
        patcher.setattr(
            release_module,
            "findings_report",
            stale_findings_report,
        )
        with pytest.raises(ValueError, match="E-RDY-002 status conflict"):
            build_post_zero_api_release(
                repository_root=repository,
                authority_receipt=_r2_receipt(repository),
                zero_api_artifact_root=zero_api_artifact,
                controlled_registry=(
                    repository
                    / "dataset"
                    / "dataset_methodology_hardening_v1"
                    / "release"
                    / "controlled_vietnamese_source_registry.jsonl"
                ),
                output_root=contradictory_output,
                implementation_commit=commit,
                junit_path=tmp_path / "valid.xml",
                dataset_release_zip=official_dataset["zip"],
                dataset_input_pin=official_dataset["pin"],
            )
    assert not (contradictory_output / "manifest.json").exists()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _absolute_json_path_findings(root: Path) -> list[str]:
    windows_absolute = re.compile(r"^[A-Za-z]:[/\\]")
    findings: list[str] = []

    def visit(value: object, location: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{location}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{location}[{index}]")
        elif isinstance(value, str) and (
            value.startswith("/")
            or value.startswith("\\\\")
            or windows_absolute.match(value)
        ):
            findings.append(location)

    for path in sorted(root.glob("*.json")):
        visit(_load(path), path.name)
    return findings


def _official_dataset_paths() -> dict[str, Path]:
    supplied = os.environ.get("D2L_OFFICIAL_DATASET_AUTHORITY_ROOT")
    root = (
        Path(supplied)
        if supplied
        else _repository_root() / OFFICIAL_DATASET_RELATIVE
    )
    zip_path = (
        root / "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip"
    )
    pin_path = root / "official_dataset_input_pin_v1.json"
    assert zip_path.is_file()
    assert pin_path.is_file()
    return {"zip": zip_path, "pin": pin_path}


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run_git(repository: Path | None, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _r2_receipt(repository: Path) -> Path:
    return repository / R2_RECEIPT_RELATIVE_PATH


def _clone_repository(source: Path, target: Path) -> Path:
    _run_git(
        None,
        "clone",
        "--quiet",
        "--shared",
        "--no-checkout",
        str(source),
        str(target),
    )
    _run_git(
        target,
        "checkout",
        "--quiet",
        "--detach",
        _git(source, "rev-parse", "HEAD^{commit}"),
    )
    return target


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_junit(path: Path) -> Path:
    path.write_text(
        _junit_xml(EXPECTED_E_SUITE_TEST_COUNT), encoding="utf-8"
    )
    return path


def _junit_xml(
    count: int,
    *,
    failures: int = 0,
    errors: int = 0,
    skipped: int = 0,
    classname: str | None = None,
    identities: tuple[str, ...] | None = None,
    testcase_skipped: bool = False,
) -> str:
    if identities is None:
        if classname is None and count <= len(EXPECTED_E_SUITE_TESTCASE_IDENTITIES):
            identities = EXPECTED_E_SUITE_TESTCASE_IDENTITIES[:count]
        else:
            testcase_class = classname or "vietnamese_attestation.v1.tests.synthetic"
            identities = tuple(
                f"{testcase_class}::case-{index}" for index in range(count)
            )
    if len(identities) != count:
        raise ValueError("JUnit fixture identity count mismatch")
    child = "<skipped />" if testcase_skipped else ""
    cases = "".join(
        f"<testcase classname={quoteattr(identity.split('::', 1)[0])} "
        f"name={quoteattr(identity.split('::', 1)[1])}>{child}</testcase>"
        for identity in identities
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites name="pytest tests">'
        f'<testsuite name="pytest" tests="{count}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}">{cases}</testsuite>'
        '</testsuites>'
    )
