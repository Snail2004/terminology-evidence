"""Deterministic public Contract-verifier protocol fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


RECEIPT_SHA256 = "acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--distribution-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.receipt.read_bytes()).hexdigest() != RECEIPT_SHA256:
        print("R2 receipt hash mismatch", file=sys.stderr)
        return 2
    source = (
        args.distribution_root
        / "terminology_contracts_v1"
        / "release"
        / "v1.1.0-final"
        / "authority_verification_report.json"
    )
    raw = source.read_bytes()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(raw)
    value = json.loads(raw.decode("utf-8"))
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
