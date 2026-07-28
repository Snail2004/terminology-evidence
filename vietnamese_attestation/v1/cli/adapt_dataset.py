from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Sequence

from vietnamese_attestation.v1.dataset import (
    adapt_dataset_zip,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and normalize the immutable D2L V3 or pilot V1.1 ZIP "
            "for Vietnamese Attestation Evidence E without API calls."
        )
    )
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--parent-v3-zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    package = adapt_dataset_zip(
        args.source_zip,
        parent_v3_zip=args.parent_v3_zip,
    )
    _atomic_write_json(args.output, package)
    if args.receipt_output is not None:
        _atomic_write_json(args.receipt_output, package["receipt"])
    print(
        json.dumps(
            {
                "schema_id": package["schema_id"],
                "schema_version": package["schema_version"],
                "source_schema_id": package["source"]["schema_id"],
                "source_manifest_sha256": package["source"][
                    "manifest_sha256"
                ],
                "candidate_count": len(package["candidates"]),
                "provider_call_count": package["receipt"][
                    "provider_call_count"
                ],
                "final_glossary_decision": None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _atomic_write_json(path: Path, payload: Any) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    raw = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    try:
        with temporary.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
