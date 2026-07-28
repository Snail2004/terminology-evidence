"""CLI for the development-only, zero-network Evidence E pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vietnamese_attestation.v1.zero_api import run_zero_api_pilot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run all 15 Vietnamese Attestation pilot candidates offline."
    )
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--parent-v3-zip", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--controlled-registry", type=Path)
    args = parser.parse_args(argv)
    summary = run_zero_api_pilot(
        source_zip=args.source_zip,
        parent_v3_zip=args.parent_v3_zip,
        output_root=args.output_root,
        controlled_registry=args.controlled_registry,
    )
    print(
        json.dumps(
            {
                "candidate_count": summary["candidate_count"],
                "external_provider_call_count": summary[
                    "external_provider_call_count"
                ],
                "replay_pass_count": summary["replay_pass_count"],
                "contract_projection_status": summary[
                    "contract_projection_status"
                ],
                "controlled_corpus_status": summary[
                    "controlled_corpus_status"
                ],
                "summary_sha256": summary["integrity"]["self_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
