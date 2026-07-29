from __future__ import annotations

from pathlib import Path

import pytest

from global_validator.v1.tools.build_release_evidence import _verify_junit


def _write_junit(path: Path, body: str) -> Path:
    path.write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<testsuites><testsuite>"
        + body
        + "</testsuite></testsuites>\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _write_junit_with_counters(path: Path, counters: str, body: str) -> Path:
    path.write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        f"<testsuites><testsuite {counters}>"
        + body
        + "</testsuite></testsuites>\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def test_junit_identity_and_clean_counts_are_bound(tmp_path: Path) -> None:
    path = _write_junit(
        tmp_path / "global.xml",
        '<testcase classname="v1.tests.test_alpha" name="test_one" />'
        '<testcase classname="v1.tests.test_alpha" name="test_two" />',
    )
    evidence = _verify_junit(
        path,
        expected_count=2,
        expected_identities=(
            "v1.tests.test_alpha::test_one",
            "v1.tests.test_alpha::test_two",
        ),
    )
    assert evidence.test_count == 2
    assert evidence.failures == evidence.errors == evidence.skipped == 0
    assert len(evidence.identity_sha256) == 64


@pytest.mark.parametrize(
    "body,expected",
    [
        (
            '<testcase classname="tests.test_a" name="test_a">'
            "<failure />"
            "</testcase>",
            "clean gate",
        ),
        (
            '<testcase classname="tests.test_a" name="test_a">'
            "<skipped />"
            "</testcase>",
            "clean gate",
        ),
    ],
)
def test_junit_rejects_failure_or_skip(
    body: str, expected: str, tmp_path: Path
) -> None:
    path = _write_junit(tmp_path / "bad.xml", body)
    with pytest.raises(ValueError, match=expected):
        _verify_junit(
            path,
            expected_count=1,
            expected_identities=("tests.test_a::test_a",),
        )


def test_junit_rejects_stale_count_and_identity_set(tmp_path: Path) -> None:
    path = _write_junit(
        tmp_path / "stale.xml",
        '<testcase classname="tests.test_old" name="test_old" />',
    )
    with pytest.raises(ValueError, match="test count mismatch"):
        _verify_junit(
            path,
            expected_count=2,
            expected_identities=(
                "tests.test_new::test_one",
                "tests.test_new::test_two",
            ),
        )

    with pytest.raises(ValueError, match="identity set mismatch"):
        _verify_junit(
            path,
            expected_count=1,
            expected_identities=("tests.test_new::test_new",),
        )


def test_junit_rejects_counter_drift(tmp_path: Path) -> None:
    path = _write_junit_with_counters(
        tmp_path / "counter-drift.xml",
        'tests="2" failures="0" errors="0" skipped="0"',
        '<testcase classname="tests.test_a" name="test_a" />',
    )
    with pytest.raises(ValueError, match="counter mismatch"):
        _verify_junit(
            path,
            expected_count=1,
            expected_identities=("tests.test_a::test_a",),
        )
