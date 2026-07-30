"""Build or verify the result-independent 50/150 analysis-plan content."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from ..analysis_plan import build_analysis_plan_content, verify_analysis_plan_content


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=_repo_root())
    parser.add_argument("--source-parent-commit")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.verify_only:
            build_analysis_plan_content(
                args.repo,
                source_parent_commit=args.source_parent_commit or _head(args.repo),
            )
        result = verify_analysis_plan_content(args.repo)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
