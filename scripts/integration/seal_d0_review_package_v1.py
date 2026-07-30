"""Seal or verify a D0 System Integration reviewer package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from integration_harness.jsonio import loads_strict
from integration_harness.review_package import seal_review_package, verify_review_package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--receipt-input", type=Path)
    args = parser.parse_args()
    if args.receipt_input is None:
        result = verify_review_package(
            args.package_root.resolve(), schema_path=args.schema.resolve()
        )
    else:
        receipt = loads_strict(args.receipt_input.read_bytes(), require_object=True)
        result = seal_review_package(
            args.package_root.resolve(), receipt, schema_path=args.schema.resolve()
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
