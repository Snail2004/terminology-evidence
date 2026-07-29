from __future__ import annotations

import argparse
import json
from pathlib import Path

from vietnamese_attestation.v1.runtime.replay import (
    AuditReplayReader,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify and read a Vietnamese Attestation audit stage."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    reader = AuditReplayReader(
        args.manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
    )
    reader.verify_all_content()
    payload = reader.replay(args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
