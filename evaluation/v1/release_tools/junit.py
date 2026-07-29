"""Exact pytest testcase authority and parsed JUnit verification."""

from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..jsonio import canonical_bytes, read_json, sha256_bytes, sha256_file, sha256_value


MANIFEST_SCHEMA_ID = "EvaluationExpectedTestManifestV1"
MANIFEST_SCHEMA_VERSION = "1.0.0"
MANIFEST_FILE = "expected_test_manifest_v1.json"


class JUnitAuthorityError(ValueError):
    """Raised when test execution or JUnit identities are not exact green authority."""


def manifest_path() -> Path:
    return Path(__file__).parents[1] / "authority" / MANIFEST_FILE


def identity_set_sha256(identities: Iterable[str]) -> str:
    values = sorted(identities)
    return sha256_bytes(("\n".join(values) + "\n").encode("utf-8"))


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    integrity = dict(result.get("integrity", {}))
    integrity.pop("self_sha256", None)
    result["integrity"] = integrity
    return result


def load_expected_test_manifest(path: Path | None = None) -> dict[str, Any]:
    value = read_json(path or manifest_path())
    expected_keys = {
        "schema_id",
        "schema_version",
        "manifest_id",
        "runner",
        "identity_format",
        "test_count",
        "testcase_identities",
        "testcase_identity_sha256",
        "integrity",
    }
    if set(value) != expected_keys or value.get("schema_id") != MANIFEST_SCHEMA_ID or value.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise JUnitAuthorityError("unsupported expected-test manifest")
    if value.get("manifest_id") != "evaluation-ar2-test-authority-v1" or value.get("runner") != "pytest" or value.get("identity_format") != "JUNIT_CLASSNAME_DOT_NAME":
        raise JUnitAuthorityError("expected-test manifest identity policy mismatch")
    identities = value.get("testcase_identities")
    if not isinstance(identities, list) or not identities or identities != sorted(identities) or len(set(identities)) != len(identities):
        raise JUnitAuthorityError("expected testcase identities are empty, duplicated or unsorted")
    if value.get("test_count") != len(identities) or value.get("testcase_identity_sha256") != identity_set_sha256(identities):
        raise JUnitAuthorityError("expected testcase count/hash mismatch")
    declared = value.get("integrity", {}).get("self_sha256") if isinstance(value.get("integrity"), Mapping) else None
    if declared != sha256_value(_without_self_hash(value)):
        raise JUnitAuthorityError("expected-test manifest self hash mismatch")
    return value


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_junit(path: Path) -> dict[str, Any]:
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as exc:
        raise JUnitAuthorityError("JUnit XML is missing or malformed") from exc
    if _local_name(root.tag) not in {"testsuite", "testsuites"}:
        raise JUnitAuthorityError("JUnit root is not testsuite/testsuites")
    cases = [element for element in root.iter() if _local_name(element.tag) == "testcase"]
    identities: list[str] = []
    failures = errors = skipped = 0
    for case in cases:
        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", "")
        identifier = f"{classname}.{name}" if classname and name else ""
        if not identifier or identifier in identities:
            raise JUnitAuthorityError("JUnit testcase identity is missing or duplicated")
        identities.append(identifier)
        child_types = {_local_name(child.tag) for child in list(case)}
        failures += int("failure" in child_types)
        errors += int("error" in child_types)
        skipped += int("skipped" in child_types)
    if not cases:
        raise JUnitAuthorityError("JUnit contains zero testcases")
    summary_root = root
    try:
        declared_tests = int(summary_root.attrib.get("tests", len(cases)))
        declared_failures = int(summary_root.attrib.get("failures", failures))
        declared_errors = int(summary_root.attrib.get("errors", errors))
        declared_skipped = int(summary_root.attrib.get("skipped", skipped))
    except ValueError as exc:
        raise JUnitAuthorityError("JUnit summary counts are invalid") from exc
    if (declared_tests, declared_failures, declared_errors, declared_skipped) != (len(cases), failures, errors, skipped):
        raise JUnitAuthorityError("JUnit summary and testcase outcomes disagree")
    return {
        "tests": len(cases),
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "testcase_identities": sorted(identities),
        "testcase_identity_sha256": identity_set_sha256(identities),
        "physical_sha256": sha256_file(path),
    }


def verify_junit(path: Path, *, expected_manifest_path: Path | None = None) -> dict[str, Any]:
    manifest = load_expected_test_manifest(expected_manifest_path)
    report = parse_junit(path)
    if report["failures"] != 0 or report["errors"] != 0 or report["skipped"] != 0:
        raise JUnitAuthorityError("JUnit is not 0 failures / 0 errors / 0 skipped")
    if report["testcase_identities"] != manifest["testcase_identities"] or report["testcase_identity_sha256"] != manifest["testcase_identity_sha256"]:
        raise JUnitAuthorityError("JUnit testcase identity set differs from committed authority")
    return report


def normalized_junit_bytes(report: Mapping[str, Any]) -> bytes:
    suite = ET.Element(
        "testsuite",
        {
            "name": "evaluation-ar2",
            "tests": str(report["tests"]),
            "failures": "0",
            "errors": "0",
            "skipped": "0",
        },
    )
    for identifier in report["testcase_identities"]:
        classname, _, name = identifier.rpartition(".")
        ET.SubElement(suite, "testcase", {"classname": classname, "name": name, "time": "0"})
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(suite, encoding="utf-8") + b"\n"


def run_evaluation_pytest(materialized_root: Path, junit_path: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(materialized_root)
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "tests/evaluation",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        f"--junitxml={junit_path}",
    ]
    completed = subprocess.run(command, cwd=materialized_root, env=env, capture_output=True, text=True)
    if completed.returncode != 0:
        raise JUnitAuthorityError(f"Evaluation pytest failed: {completed.stdout}\n{completed.stderr}")
    expected = materialized_root / "evaluation" / "v1" / "authority" / MANIFEST_FILE
    return verify_junit(junit_path, expected_manifest_path=expected)
