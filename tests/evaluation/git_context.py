"""Resolve the Git authority used by Evaluation tests in live or materialized source."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_COMMIT_ENV = "EVALUATION_AR2_SOURCE_COMMIT"
_REPO_ENV = "EVALUATION_AR2_GIT_REPO_ROOT"


def resolve_test_git_context(source_root: Path) -> tuple[Path, str]:
    """Return a real Git repository and exact commit without trusting archive metadata."""
    commit = os.environ.get(_COMMIT_ENV)
    repository = os.environ.get(_REPO_ENV)
    if bool(commit) != bool(repository):
        raise RuntimeError("materialized test Git authority is incomplete")
    git_root = Path(repository).resolve() if repository else source_root.resolve()
    if commit is None:
        commit = subprocess.run(
            ["git", "-C", str(git_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip().lower()
    if not _COMMIT.fullmatch(commit):
        raise RuntimeError("materialized test source commit is invalid")
    resolved = subprocess.run(
        ["git", "-C", str(git_root), "rev-parse", "--verify", f"{commit}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    if resolved != commit:
        raise RuntimeError("materialized test source commit does not resolve exactly")
    return git_root, commit
