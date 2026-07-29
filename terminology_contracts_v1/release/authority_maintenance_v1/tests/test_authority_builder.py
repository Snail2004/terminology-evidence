from __future__ import annotations

from pathlib import Path

import pytest

from authority_fixtures import authority_candidate, repository_root  # noqa: F401
from authority_common import (
    APPROVED_FINAL_ZIP_SHA256,
    AUTHORITY_TAG,
    AuthorityError,
    sha256_file,
)
from build_authority_release import build_release


def _build_with_junit(
    authority_candidate: dict[str, object],
    tmp_path: Path,
    junit_text: str,
    *,
    source_ref: str = AUTHORITY_TAG,
) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(junit_text, encoding="utf-8", newline="\n")
    build_release(
        repo_root=authority_candidate["repo"],
        distribution_root=tmp_path / "distribution",
        junit_path=junit,
        base_main_commit=authority_candidate["base"],
        implementation_commit=authority_candidate["implementation"],
        issued_at="2026-07-29T00:00:00Z",
        source_ref=source_ref,
    )


def test_final_zip_is_byte_identical_to_approved_rc4(authority_candidate) -> None:
    receipt = authority_candidate["receipt"]
    assert isinstance(receipt, Path)
    final_zip = receipt.parent / "terminology_contracts_v1_1_0_final.zip"
    assert sha256_file(final_zip) == APPROVED_FINAL_ZIP_SHA256


def test_builder_rejects_non_tag_source(authority_candidate, tmp_path) -> None:
    with pytest.raises(AuthorityError, match="exact tag"):
        _build_with_junit(
            authority_candidate,
            tmp_path,
            '<testsuite tests="1" failures="0" errors="0" skipped="0" />',
            source_ref="HEAD",
        )


@pytest.mark.parametrize(
    "junit",
    [
        '<testsuite tests="0" failures="0" errors="0" skipped="0" />',
        '<testsuite tests="1" failures="1" errors="0" skipped="0" />',
        '<testsuite tests="1" failures="0" errors="1" skipped="0" />',
        '<testsuite tests="1" failures="0" errors="0" skipped="1" />',
    ],
)
def test_builder_rejects_invalid_junit(authority_candidate, tmp_path, junit: str) -> None:
    with pytest.raises(AuthorityError, match="zero-test|zero failures"):
        _build_with_junit(authority_candidate, tmp_path, junit)


def test_builder_is_idempotent_for_identical_output(authority_candidate) -> None:
    receipt = authority_candidate["receipt"]
    distribution = authority_candidate["distribution"]
    assert isinstance(receipt, Path)
    assert isinstance(distribution, Path)
    rebuilt = build_release(
        repo_root=authority_candidate["repo"],
        distribution_root=distribution,
        junit_path=authority_candidate["junit"],
        base_main_commit=authority_candidate["base"],
        implementation_commit=authority_candidate["implementation"],
        issued_at="2026-07-29T00:00:00Z",
    )
    assert rebuilt.read_bytes() == receipt.read_bytes()
