"""Build exact D0 1/15 zero-provider cohort authorities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from integration_harness.adapter_v1.producer_safe import (
    write_producer_safe_cohort_release,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-zip", type=Path, required=True)
    parser.add_argument("--publication-receipt", type=Path, required=True)
    parser.add_argument("--schema-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--issuer-id", required=True)
    parser.add_argument("--authority-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase-id", required=True)
    parser.add_argument("--split-id", required=True)
    args = parser.parse_args()
    result = write_producer_safe_cohort_release(
        args.dataset_zip.resolve(),
        args.output_root.resolve(),
        publication_receipt_path=args.publication_receipt.resolve(),
        schema_root=args.schema_root.resolve(),
        issuer_id=args.issuer_id,
        authority_id=args.authority_id,
        run_id=args.run_id,
        phase_id=args.phase_id,
        split_id=args.split_id,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
