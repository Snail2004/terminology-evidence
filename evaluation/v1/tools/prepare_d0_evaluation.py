"""CLI for deterministic, no-gold D0 preparation and publication."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..d0_preparation.builder import build_d0_content
from ..d0_preparation.publication import build_d0_publication
from ..d0_preparation.verifier import verify_d0_content


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    content = sub.add_parser("build-content")
    content.add_argument("--repo", type=Path, required=True)
    content.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-content")
    verify.add_argument("--repo", type=Path, required=True)
    verify.add_argument("--content", type=Path, required=True)
    publication = sub.add_parser("publish")
    publication.add_argument("--repo", type=Path, required=True)
    publication.add_argument("--content-commit", required=True)
    publication.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build-content":
            result = build_d0_content(args.repo.resolve(), args.output.resolve())
        elif args.command == "verify-content":
            result = verify_d0_content(args.repo.resolve(), args.content.resolve())
        else:
            result = build_d0_publication(args.repo.resolve(), args.content_commit, args.output.resolve())
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
