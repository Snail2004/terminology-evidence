"""Strict JUnit gate for the post-zero-API release."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .jsonio import reject_link


EXPECTED_E_SUITE_TEST_COUNT = 75
E_TESTCASE_PREFIX = "vietnamese_attestation.v1.tests."


def verify_junit(
    path: str | Path, *, expected_count: int = EXPECTED_E_SUITE_TEST_COUNT
) -> dict[str, Any]:
    junit_path = Path(path).absolute()
    reject_link(junit_path)
    try:
        raw = junit_path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
        if "<!DOCTYPE" in text or "<!ENTITY" in text:
            raise ValueError("DOCTYPE/entity declarations are forbidden")
        root = ET.fromstring(text)
    except (OSError, UnicodeError, ET.ParseError, ValueError) as exc:
        raise ValueError(f"invalid JUnit report: {junit_path}") from exc

    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise ValueError("JUnit report contains no test suites")
    leaf_suites = [suite for suite in suites if not suite.findall("testsuite")]
    if not leaf_suites:
        raise ValueError("JUnit report contains no leaf test suites")

    testcases = [case for suite in leaf_suites for case in suite.findall("testcase")]
    declared_tests = _sum_nonnegative(leaf_suites, "tests")
    declared_failures = _sum_nonnegative(leaf_suites, "failures")
    declared_errors = _sum_nonnegative(leaf_suites, "errors")
    declared_skipped = _sum_nonnegative(leaf_suites, "skipped")
    if declared_tests <= 0 or not testcases:
        raise ValueError("JUnit report has no tests")
    if declared_tests != len(testcases):
        raise ValueError("JUnit declared test count differs from testcase count")
    if declared_tests != expected_count:
        raise ValueError(
            f"JUnit E-suite count mismatch: expected {expected_count}, got {declared_tests}"
        )
    if declared_failures or declared_errors:
        raise ValueError("JUnit report contains failures or errors")

    identities: list[str] = []
    for case in testcases:
        classname = case.get("classname") or ""
        name = case.get("name") or ""
        if not classname.startswith(E_TESTCASE_PREFIX):
            raise ValueError("JUnit contains a testcase outside the E suite")
        if not name:
            raise ValueError("JUnit testcase name is empty")
        if case.find("failure") is not None or case.find("error") is not None:
            raise ValueError("JUnit testcase contains failure/error element")
        identities.append(f"{classname}::{name}")
    if len(set(identities)) != len(identities):
        raise ValueError("JUnit testcase identities are not unique")

    identity_sha256 = hashlib.sha256(
        ("\n".join(sorted(identities)) + "\n").encode("utf-8")
    ).hexdigest()
    return {
        "schema_id": "VietnameseAttestationJunitVerificationReportV1",
        "schema_version": "1.0.0",
        "status": "PASS",
        "path": junit_path.as_posix(),
        "physical_sha256": hashlib.sha256(raw).hexdigest(),
        "tests": declared_tests,
        "failures": declared_failures,
        "errors": declared_errors,
        "skipped": declared_skipped,
        "testcase_identity_sha256": identity_sha256,
        "policy_id": "vietnamese-attestation-e-suite-v1",
        "policy_version": "1.0.0",
    }


def _sum_nonnegative(suites: list[ET.Element], field: str) -> int:
    total = 0
    for suite in suites:
        value = suite.get(field, "0")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"JUnit {field} is not an integer") from exc
        if parsed < 0:
            raise ValueError(f"JUnit {field} is negative")
        total += parsed
    return total


__all__ = [
    "E_TESTCASE_PREFIX",
    "EXPECTED_E_SUITE_TEST_COUNT",
    "verify_junit",
]
