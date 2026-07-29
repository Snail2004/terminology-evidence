"""Publish or verify the Git-bound 50/150 analysis-plan freeze receipt."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from ..analysis_plan.publication import build_analysis_plan_publication, verify_analysis_plan_publication


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
    parser.add_argument("--content-commit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle-root", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            result = verify_analysis_plan_publication(args.repo, bundle_root=args.bundle_root)
        else:
            if args.output is None:
                parser.error("--output is required unless --verify-only is used")
            result = build_analysis_plan_publication(
                repo=args.repo,
                content_commit=args.content_commit or _head(args.repo),
                output=args.output,
            )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
