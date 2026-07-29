"""CLI for the post-zero-API Evidence E readiness release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vietnamese_attestation.v1.readiness import build_post_zero_api_release


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a zero-network post-zero-API Evidence E release."
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--authority-receipt", type=Path, required=True)
    parser.add_argument("--zero-api-artifact-root", type=Path, required=True)
    parser.add_argument("--controlled-registry", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--implementation-commit", default="HEAD")
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = build_post_zero_api_release(
        repository_root=args.repository_root,
        authority_receipt=args.authority_receipt,
        zero_api_artifact_root=args.zero_api_artifact_root,
        controlled_registry=args.controlled_registry,
        output_root=args.output_root,
        implementation_commit=args.implementation_commit,
        junit_path=args.junit,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
