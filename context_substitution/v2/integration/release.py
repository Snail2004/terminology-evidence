from __future__ import annotations

import ast
import hashlib
import json
import platform
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

from context_substitution.v2.integration.common import file_sha256, seal_object, write_json


RELEASE_NAME = "context_substitution_v2_2_integration_rc"
RELEASE_SCHEMA_ID = "ContextSubstitutionIntegrationReleaseAuditV1"
RELEASE_SCHEMA_VERSION = "1.0.0"

_REQUIRED_EVIDENCE = (
    "junit.xml",
    "pilot_adapter_receipt.json",
    "pilot_runtime_receipt.json",
    "pilot_zero_api_summary.json",
    "development_frozen_candidates.json",
    "context_evidence_packages/manifest.json",
    "replay_report.json",
    "fake_run.json",
    "pilot_input.json",
)
_SECRET_PATTERNS = {
    "google_api_key": re.compile(rb"AIza[0-9A-Za-z_-]{20,}"),
    "openai_api_key": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def build_integration_release(
    *,
    source_root: Path,
    evidence_root: Path,
    output_directory: Path,
    commands: Iterable[str],
    known_gaps: Iterable[str],
) -> dict[str, Any]:
    source_root = Path(source_root).resolve()
    evidence_root = Path(evidence_root).resolve()
    output_directory = Path(output_directory).resolve()
    if source_root.name != "context_substitution":
        raise ValueError("release source root must be context_substitution")
    for name in _REQUIRED_EVIDENCE:
        if not (evidence_root / name).is_file():
            raise ValueError(f"required integration evidence is missing: {name}")
    ledger_root = evidence_root / "fake_ledger"
    if not (ledger_root / "provider_attempts.jsonl").is_file():
        raise ValueError("provider attempt ledger is missing")

    staging = output_directory / RELEASE_NAME
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "source").mkdir(parents=True)
    (staging / "evidence").mkdir(parents=True)
    _copy_source(source_root, staging / "source" / "context_substitution")
    for name in _REQUIRED_EVIDENCE:
        destination = staging / "evidence" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(evidence_root / name, destination)
    shutil.copytree(
        evidence_root / "context_evidence_packages" / "packages",
        staging / "evidence" / "context_evidence_packages" / "packages",
    )
    shutil.copytree(
        ledger_root / "provider_responses",
        staging / "evidence" / "provider_responses",
    )
    shutil.copy2(
        ledger_root / "provider_attempts.jsonl",
        staging / "evidence" / "provider_attempts.jsonl",
    )

    (staging / "commands.txt").write_text(
        "\n".join(commands) + "\n", encoding="utf-8", newline="\n"
    )
    environment = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable_name": Path(sys.executable).name,
        "provider_call_count": 0,
    }
    write_json(staging / "environment.json", environment)
    static_scan = _static_scan(staging)
    credential_scan = _credential_scan(staging)
    write_json(staging / "static_scan.json", static_scan)
    write_json(staging / "credential_scan.json", credential_scan)
    if static_scan["status"] != "PASS" or credential_scan["status"] != "PASS":
        raise ValueError("release scan failed")

    inventory = _inventory(staging)
    junit = ElementTree.parse(staging / "evidence" / "junit.xml").getroot()
    junit_summary = _junit_summary(junit)
    audit = {
        "schema_id": RELEASE_SCHEMA_ID,
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_name": RELEASE_NAME,
        "status": "INTEGRATION_READY_ZERO_API",
        "source_file_count": sum(
            1 for path in (staging / "source").rglob("*") if path.is_file()
        ),
        "evidence_file_count": sum(
            1 for path in (staging / "evidence").rglob("*") if path.is_file()
        ),
        "junit": junit_summary,
        "provider_call_count": 0,
        "final_glossary_decision": None,
        "contract_authority_status": "ADOPTED_CONTRACTS_V1_1_0",
        "known_gaps": sorted(set(known_gaps)),
        "file_inventory": inventory,
        "integrity": {},
    }
    audit = seal_object(audit, integrity_key="audit_sha256")
    write_json(staging / "context_substitution_v2_2_audit.json", audit)

    archive = output_directory / f"{RELEASE_NAME}.zip"
    _write_deterministic_zip(staging, archive)
    archive_hash = file_sha256(archive)
    hash_path = output_directory / f"{RELEASE_NAME}.zip.sha256"
    hash_path.write_text(
        f"{archive_hash}  {archive.name}\n", encoding="ascii", newline="\n"
    )
    return {
        "archive": str(archive),
        "archive_sha256": archive_hash,
        "sha256_file": str(hash_path),
        "audit_sha256": audit["integrity"]["audit_sha256"],
        "source_file_count": audit["source_file_count"],
        "evidence_file_count": audit["evidence_file_count"],
        "junit": audit["junit"],
        "status": audit["status"],
    }


def _copy_source(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file() or _excluded(path):
            continue
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _excluded(path: Path) -> bool:
    return any(part in {"__pycache__", ".pytest_cache"} for part in path.parts) or path.suffix in {
        ".pyc",
        ".pyo",
    }


def _static_scan(root: Path) -> dict[str, Any]:
    python_files = [path for path in root.rglob("*.py") if not _excluded(path)]
    errors = []
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f"{path.relative_to(root).as_posix()}:{exc}")
    forbidden = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and (
            path.suffix in {".pyc", ".pyo"}
            or "__pycache__" in path.parts
            or "API-Key" in path.parts
        )
    ]
    return {
        "status": "PASS" if not errors and not forbidden else "FAIL",
        "python_source_files": len(python_files),
        "parse_errors": errors,
        "forbidden_files": sorted(forbidden),
    }


def _credential_scan(root: Path) -> dict[str, Any]:
    findings = []
    scanned = 0
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file() or path.name == "credential_scan.json":
            continue
        data = path.read_bytes()
        scanned += 1
        for name, pattern in _SECRET_PATTERNS.items():
            if pattern.search(data):
                findings.append(
                    {
                        "path": path.relative_to(root).as_posix(),
                        "pattern": name,
                    }
                )
    return {
        "status": "PASS" if not findings else "FAIL",
        "scanned_file_count": scanned,
        "findings": findings,
    }


def _inventory(root: Path) -> list[dict[str, Any]]:
    excluded_names = {
        "context_substitution_v2_2_audit.json",
        "static_scan.json",
        "credential_scan.json",
    }
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"), key=lambda value: value.as_posix())
        if path.is_file() and path.name not in excluded_names
    ]


def _write_deterministic_zip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*"), key=lambda value: value.as_posix()):
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _junit_summary(root: ElementTree.Element) -> dict[str, int]:
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    return {
        name: sum(int(suite.attrib.get(name, 0)) for suite in suites)
        for name in ("tests", "failures", "errors", "skipped")
    }
