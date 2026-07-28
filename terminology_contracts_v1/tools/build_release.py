from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
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


RELEASE = ROOT / "release"
ZIP_PATH = RELEASE / "terminology_contracts_v1_1.zip"
ZIP_CHECKSUM_PATH = RELEASE / "terminology_contracts_v1_1.zip.sha256"
AUDIT_PATH = RELEASE / "terminology_contracts_v1_1_audit.json"
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
    _remove_python_cache()
    manifest = build_manifest(ROOT)
    write_manifest(ROOT, manifest)
    _write_checksums(manifest)
    manifest_errors = verify_manifest(ROOT)
    if manifest_errors:
        raise SystemExit("manifest verification failed: " + "; ".join(manifest_errors))

    _build_zip(manifest)
    zip_sha = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    ZIP_CHECKSUM_PATH.write_text(
        f"{zip_sha}  {ZIP_PATH.name}\n", encoding="ascii", newline="\n"
    )
    if hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest() != zip_sha:
        raise SystemExit("ZIP checksum verification failed")

    migration = _verify_migration_examples()
    test_evidence = _read_junit(junit)
    dataset_mapping = _dataset_mapping_audit()
    credential_hits = _credential_scan()
    cache_files = _cache_files()
    audit = {
        "schema_id": "TerminologyContractsV1_1ReleaseAuditV1",
        "package_version": "1.1.0",
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
        "manifest_verification": "PASS",
        "manifest_sha256": manifest["integrity"]["manifest_sha256"],
        "checksum_verification": "PASS",
        "release_zip_sha256": zip_sha,
        "migration_result": migration,
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
    package_prefix = "terminology_contracts_v1_1/"
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
