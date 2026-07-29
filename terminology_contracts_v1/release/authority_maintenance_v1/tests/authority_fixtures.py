from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


MAINTENANCE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = MAINTENANCE_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from authority_common import RECEIPT_NAME, read_strict_json  # noqa: E402
from build_authority_release import build_release  # noqa: E402


@pytest.fixture(scope="session")
def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


@pytest.fixture(scope="session")
def authority_candidate(tmp_path_factory, repository_root: Path) -> dict[str, object]:
    root = tmp_path_factory.mktemp("authority-candidate")
    repo = root / "repo"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(repository_root), str(repo)],
        check=True,
    )
    _git(repo, "config", "user.name", "Authority Test")
    _git(repo, "config", "user.email", "authority-test@example.invalid")
    base = _git(repo, "rev-parse", "HEAD")
    marker = repo / "terminology_contracts_v1" / "release" / "authority-test-marker.txt"
    marker.write_text("authority maintenance test marker\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "terminology_contracts_v1/release/authority-test-marker.txt")
    _git(repo, "commit", "--quiet", "-m", "test: authority maintenance candidate")
    implementation = _git(repo, "rev-parse", "HEAD")

    junit = root / "junit.xml"
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuites tests="1" failures="0" errors="0" skipped="0">'
        '<testsuite name="authority" tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="authority" name="pass" />'
        "</testsuite></testsuites>\n",
        encoding="utf-8",
        newline="\n",
    )
    distribution = root / "distribution"
    receipt = build_release(
        repo_root=repo,
        distribution_root=distribution,
        junit_path=junit,
        base_main_commit=base,
        implementation_commit=implementation,
        issued_at="2026-07-29T00:00:00Z",
    )
    return {
        "root": root,
        "repo": repo,
        "base": base,
        "implementation": implementation,
        "junit": junit,
        "distribution": distribution,
        "receipt": receipt,
        "receipt_payload": read_strict_json(receipt),
    }


@pytest.fixture
def candidate_copy(tmp_path: Path, authority_candidate: dict[str, object]) -> dict[str, Path]:
    source = authority_candidate["distribution"]
    assert isinstance(source, Path)
    distribution = tmp_path / "distribution"
    shutil.copytree(source, distribution)
    receipt = (
        distribution
        / "terminology_contracts_v1"
        / "release"
        / "v1.1.0-final"
        / RECEIPT_NAME
    )
    repo = authority_candidate["repo"]
    assert isinstance(repo, Path)
    return {"repo": repo, "distribution": distribution, "receipt": receipt}


@pytest.fixture
def candidate_payload(candidate_copy: dict[str, Path]) -> dict:
    return json.loads(candidate_copy["receipt"].read_text(encoding="utf-8"))
