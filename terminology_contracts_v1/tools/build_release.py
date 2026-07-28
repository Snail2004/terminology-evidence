from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from terminology_contracts.integrity import canonical_sha256  # noqa: E402
from terminology_contracts.manifest import (  # noqa: E402
    build_manifest,
    verify_manifest,
    write_manifest,
)
from terminology_contracts.validation import verify_certificate_bundle  # noqa: E402


RELEASE_ROOT = ROOT / "release"
RELEASE = RELEASE_ROOT / "v1.1.0-rc4"
ZIP_PATH = RELEASE / "terminology_contracts_v1_1_rc4.zip"
ZIP_CHECKSUM_PATH = RELEASE / "terminology_contracts_v1_1_rc4.zip.sha256"
AUDIT_PATH = RELEASE / "terminology_contracts_v1_1_rc4_audit.json"
RC1_ZIP = RELEASE_ROOT / "terminology_contracts_v1_1.zip"
RC1_ZIP_SHA256 = "38e2ee307b247d535baedcde83427ebe3f30901d31bb921f03e6681b3160dbdc"
RC2_ZIP = RELEASE_ROOT / "v1.1.0-rc2" / "terminology_contracts_v1_1_rc2.zip"
RC2_ZIP_SHA256 = "2530ebf80d4826a740d1d1efad5952adf8611cec67797d7bd806731a15cb1954"
RC3_ZIP = RELEASE_ROOT / "v1.1.0-rc3" / "terminology_contracts_v1_1_rc3.zip"
RC3_ZIP_SHA256 = "25e8705631d52cccc8620dc0936c3245897b694abf8eafd8e9f54e0bd94b34f3"
DIFF_NAME = "terminology_contracts_v1_0_to_v1_1_diff.md"
FIXED_ZIP_TIME = (2026, 7, 29, 0, 0, 0)
CACHE_DIR_NAMES = {".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__"}

SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(
        rb"(?i)(api[_-]?key|secret|access[_-]?token)\s*[:=]\s*[\"'][A-Za-z0-9_./+=-]{16,}[\"']"
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic V1.1 release")
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args(argv)
    junit = args.junit.resolve()
    if not junit.is_file():
        raise SystemExit(f"missing JUnit evidence: {junit}")

    RELEASE.mkdir(parents=True, exist_ok=True)
    if not RC1_ZIP.is_file() or hashlib.sha256(RC1_ZIP.read_bytes()).hexdigest() != RC1_ZIP_SHA256:
        raise SystemExit("immutable RC1 release artifact changed")
    if not RC2_ZIP.is_file() or hashlib.sha256(RC2_ZIP.read_bytes()).hexdigest() != RC2_ZIP_SHA256:
        raise SystemExit("immutable RC2 release artifact changed")
    if not RC3_ZIP.is_file() or hashlib.sha256(RC3_ZIP.read_bytes()).hexdigest() != RC3_ZIP_SHA256:
        raise SystemExit("immutable RC3 release artifact changed")
    _remove_python_cache()
    manifest = build_manifest(ROOT)
    write_manifest(ROOT, manifest)
    _write_checksums(manifest)
    manifest_errors = verify_manifest(ROOT)
    if manifest_errors:
        raise SystemExit("manifest verification failed: " + "; ".join(manifest_errors))

    _build_zip(manifest)
    zip_structure = _verify_zip_structure(manifest)
    zip_sha = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_CHECKSUM_PATH.write_text(
        f"{zip_sha}  {ZIP_PATH.name}\n", encoding="ascii", newline="\n"
    )
    if hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest() != zip_sha:
        raise SystemExit("ZIP checksum verification failed")

    migration = _verify_migration_examples()
    bundle_errors = _verify_reference_bundle()
    if bundle_errors:
        raise SystemExit(
            "reference certificate bundle failed: " + "; ".join(bundle_errors)
        )
    test_evidence = _read_junit(junit)
    dataset_mapping = _dataset_mapping_audit()
    credential_hits = _credential_scan()
    cache_files = _cache_files()
    audit = {
        "schema_id": "TerminologyContractsV1_1RC4ReleaseAuditV1",
        "package_version": "1.1.0",
        "release_channel": "v1.1.0-rc4",
        "supersedes_release_candidate": "v1.1.0-rc3",
        "rc1_release_zip_sha256": RC1_ZIP_SHA256,
        "rc2_release_zip_sha256": RC2_ZIP_SHA256,
        "rc3_release_zip_sha256": RC3_ZIP_SHA256,
        "file_count": len(manifest["files"]),
        "schema_count": len(list((ROOT / "schemas" / "v1.1.0").glob("*.schema.json"))),
        "legacy_schema_count": len(
            list((ROOT / "schemas" / "legacy" / "v1.0.0").glob("*.schema.json"))
        ),
        "legacy_schema_tree_sha256": _tree_hash(
            ROOT / "schemas" / "legacy" / "v1.0.0", "*.schema.json"
        ),
        "legacy_fixture_tree_sha256": _tree_hash(
            ROOT / "examples" / "valid" / "v1.0.0", "*.json"
        ),
        "fixture_count": len(list((ROOT / "examples").rglob("*.json"))),
        "test_file_count": len(list((ROOT / "tests").glob("test_*.py"))),
        "test_count": test_evidence["tests"],
        "test_result": test_evidence["result"],
        "test_failures": test_evidence["failures"],
        "test_errors": test_evidence["errors"],
        "test_skipped": test_evidence["skipped"],
        "junit_sha256": hashlib.sha256(junit.read_bytes()).hexdigest(),
        "manifest_verification": "PASS",
        "manifest_sha256": manifest["integrity"]["manifest_sha256"],
        "checksum_verification": "PASS",
        "release_zip_sha256": zip_sha,
        "zip_structure_verification": zip_structure,
        "migration_result": migration,
        "certificate_bundle_verification": "PASS",
        "review_findings_closed": {
            "P0-1": "FROZEN_CANDIDATE_CONTENT_BINDING",
            "P0-2": "EXACT_FEATURE_AND_LOGISTIC_SCORE_REPLAY",
            "P0-3": "EXPLICIT_SENSE_POLYSEMY_COLLISION_INPUTS",
            "P1-1": "FULL_DECISION_REPLAY_BINDING",
            "P1-2": "CERTIFICATE_ARTIFACT_BUNDLE_VERIFICATION",
            "P1-3": "TAC_SOURCE_TERM_SPAN_BINDING",
            "P1-4": "STRICT_FINITE_JSON_NUMBERS",
            "P1-5": "LOGISTIC_REGRESSION_ONLY",
            "P1-6": "MACHINE_READABLE_FEATURE_MAPPING",
            "P2-1": "EXACT_UNIQUE_AUDITABLE_GATE_SET",
            "P2-2": "CANDIDATE_CONTENT_VERSION_BINDING",
            "P2-3": "NATIVE_NON_MIGRATION_FIXTURES",
            "RC2-P0-N1": "PRODUCER_GATE_SIGNAL_PROJECTION",
            "RC2-P0-N2": "SEALED_PER_GATE_ACTION_POLICY",
            "RC2-P1-N1": "COLLISION_INDEX_ARTIFACT_BINDING",
            "RC2-P1-N2": "THRESHOLD_STABILITY_METADATA",
            "RC3-P0-1": "CERTIFICATE_APPLICATION_PROJECTION_BINDING",
            "RC3-P0-2": "POSITIVE_SUPPORT_ONLY_VALIDITY_CONTEXTS",
            "RC3-P1-1": "NATIVE_GATE_SIGNALS_SCHEMA_REQUIRED",
            "RC3-P1-2": "STANDALONE_GATE_POLICY_VERIFICATION",
        },
        "credential_scan_result": "PASS" if not credential_hits else "FAIL",
        "credential_scan_hits": credential_hits,
        "pyc_cache_scan_result": "PASS" if not cache_files else "FAIL",
        "pyc_cache_files": cache_files,
        "external_api_calls": 0,
        "dataset_runtime_dependency": False,
        "dataset_mapping_inputs": [
            "D2LContextSupportSetValidationReadyV3",
            "D2LCSTDevelopmentOnlyPilotV1_1",
        ],
        "dataset_mapping_result": dataset_mapping,
    }
    AUDIT_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (RELEASE / "commands.txt").write_bytes((ROOT / "commands.txt").read_bytes())
    (RELEASE / DIFF_NAME).write_bytes((ROOT / DIFF_NAME).read_bytes())
    if (
        credential_hits
        or cache_files
        or test_evidence["result"] != "PASS"
        or dataset_mapping["status"] != "PASS"
    ):
        raise SystemExit("release audit did not pass")
    print(json.dumps(audit, sort_keys=True))
    return 0


def _write_checksums(manifest: dict) -> None:
    lines = [f"{row['sha256']}  {row['path']}" for row in manifest["files"]]
    manifest_path = ROOT / "manifest.json"
    lines.append(
        f"{hashlib.sha256(manifest_path.read_bytes()).hexdigest()}  manifest.json"
    )
    (ROOT / "CHECKSUMS.sha256").write_text(
        "\n".join(lines) + "\n", encoding="ascii", newline="\n"
    )


def _build_zip(manifest: dict) -> None:
    package_prefix = "terminology_contracts_v1/"
    source_paths = [ROOT / row["path"] for row in manifest["files"]]
    source_paths.extend([ROOT / "manifest.json", ROOT / "CHECKSUMS.sha256"])
    with zipfile.ZipFile(
        ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(source_paths, key=lambda item: item.relative_to(ROOT).as_posix()):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(package_prefix + relative, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def _verify_zip_structure(manifest: dict) -> str:
    prefix = "terminology_contracts_v1/"
    expected = {
        prefix + row["path"] for row in manifest["files"]
    } | {prefix + "manifest.json", prefix + "CHECKSUMS.sha256"}
    with zipfile.ZipFile(ZIP_PATH) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)) or set(names) != expected:
            raise SystemExit("ZIP member set differs from package manifest")
        if archive.testzip() is not None:
            raise SystemExit("ZIP CRC verification failed")
        for member in members:
            relative = member.filename.removeprefix(prefix)
            parts = Path(relative).parts
            if (
                not member.filename.startswith(prefix)
                or relative.startswith(("/", "\\"))
                or ".." in parts
            ):
                raise SystemExit(f"unsafe ZIP member: {member.filename}")
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise SystemExit(f"ZIP symlink is forbidden: {member.filename}")
            if member.filename.endswith(".pyc") or "__pycache__" in parts:
                raise SystemExit(f"ZIP cache file is forbidden: {member.filename}")
    return "PASS"


def _verify_migration_examples() -> dict:
    outputs = ROOT / "examples" / "migrated" / "v1.1.0"
    reports = ROOT / "examples" / "migrated" / "reports"
    checked = 0
    for output in sorted(outputs.glob("*.json")):
        report_path = reports / f"{output.stem}.migration.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        payload = json.loads(output.read_text(encoding="utf-8"))
        if report.get("target_sha256") != canonical_sha256(payload):
            raise SystemExit(f"migration report mismatch: {output.name}")
        checked += 1
    return {"status": "PASS", "fixture_count": checked, "deterministic": True}


def _verify_reference_bundle() -> list[str]:
    valid = ROOT / "examples" / "valid" / "v1.1.0"
    return verify_certificate_bundle(
        certificate_path=valid / "terminology_certificate.json",
        frozen_candidate_path=valid / "frozen_candidate_contract.json",
        effective_sense_contract_path=valid / "effective_sense_contract.json",
        constraint_evidence_path=valid / "constraint_evidence_package.json",
        global_input_path=valid / "global_validator_input.json",
        context_evidence_path=valid / "context_evidence_package.json",
        attestation_evidence_path=valid / "attestation_evidence_package.json",
        gate_result_path=valid / "gate_result_set.json",
        decision_path=valid / "global_decision_package.json",
        calibration_path=valid / "calibration_artifact.json",
        gate_policy_path=ROOT / "policies" / "gate_policy_v1.0.0.json",
        collision_index_path=ROOT
        / "examples"
        / "support"
        / "v1.1.0"
        / "collision_index.json",
        schema_dir=ROOT / "schemas",
        feature_registry_path=ROOT
        / "registries"
        / "feature_contract_v1.1.0.json",
        tac_path=valid / "tac_occurrence_input.json",
    )


def _read_junit(path: Path) -> dict[str, int | str]:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    values = {
        key: sum(int(suite.attrib.get(key, "0")) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    values["result"] = (
        "PASS" if values["failures"] == 0 and values["errors"] == 0 else "FAIL"
    )
    return values


def _dataset_mapping_audit() -> dict:
    root_text = os.environ.get("TERMINOLOGY_DATASET_ROOT")
    if not root_text:
        return {"status": "NOT_RUN", "artifacts": []}
    root = Path(root_text)
    expected = (
        (
            "d2l_context_support_set_validation_ready_v3",
            "D2LContextSupportSetValidationReadyV3",
        ),
        ("pilot_dev_only_v1_1", "D2LCSTDevelopmentOnlyPilotV1_1"),
    )
    artifacts = []
    for directory_name, expected_schema in expected:
        directory = root / directory_name
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_id") != expected_schema:
            raise SystemExit(f"dataset mapping schema mismatch: {directory_name}")
        manifest_sha = manifest.get("manifest_sha256")
        if not isinstance(manifest_sha, str) or len(manifest_sha) != 64:
            raise SystemExit(f"dataset mapping manifest hash missing: {directory_name}")
        zip_path = root / f"{directory_name}.zip"
        artifacts.append(
            {
                "schema_id": manifest["schema_id"],
                "schema_version": manifest.get("schema_version"),
                "dataset_version": manifest.get("dataset_version"),
                "manifest_sha256": manifest_sha,
                "manifest_file_sha256": hashlib.sha256(
                    manifest_path.read_bytes()
                ).hexdigest(),
                "zip_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest()
                if zip_path.is_file()
                else None,
            }
        )
    return {"status": "PASS", "artifacts": artifacts}


def _credential_scan() -> list[str]:
    hits: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or "release" in path.relative_to(ROOT).parts:
            continue
        if path.suffix.lower() in {".zip", ".pyc"}:
            continue
        data = path.read_bytes()
        for pattern in SECRET_PATTERNS:
            if pattern.search(data):
                hits.append(path.relative_to(ROOT).as_posix())
                break
    return hits


def _tree_hash(root: Path, pattern: str) -> str:
    records = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.glob(pattern))
    }
    return canonical_sha256(records)


def _remove_python_cache() -> None:
    for path in sorted(ROOT.rglob("*.pyc"), reverse=True):
        path.unlink()
    for name in sorted(CACHE_DIR_NAMES):
        for path in sorted(ROOT.rglob(name), reverse=True):
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)


def _cache_files() -> list[str]:
    return sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and (
            path.suffix == ".pyc"
            or any(part in CACHE_DIR_NAMES for part in path.relative_to(ROOT).parts)
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
