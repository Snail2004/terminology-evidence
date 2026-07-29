"""CLI entrypoint for AR-2 external release construction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..release_tools.builder import ReleaseBuildError, _write_worker_payload, build_release


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=_repo_root())
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--detached-object", action="store_true")
    parser.add_argument("--external-junit", type=Path)
    parser.add_argument("--worker-stage", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--git-repo-root", type=Path, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.worker_stage is not None:
            if args.git_repo_root is None:
                raise ReleaseBuildError("worker requires --git-repo-root")
            result = _write_worker_payload(
                args.worker_stage.resolve(),
                args.source_commit,
                args.git_repo_root.resolve(),
                Path.cwd().resolve(),
            )
        else:
            if args.output is None:
                raise ReleaseBuildError("release requires an external --output")
            result = build_release(
                repo=args.repo.resolve(),
                output=args.output.resolve(),
                source_commit=args.source_commit,
                detached_object=args.detached_object,
                external_junit=args.external_junit.resolve() if args.external_junit else None,
            )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
