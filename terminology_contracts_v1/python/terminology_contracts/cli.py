from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .validation import SCHEMA_FILES, validate_file


def _default_schema_dir() -> Path:
    cwd = Path.cwd()
    candidates = [cwd / "schemas", cwd.parent / "schemas", Path(__file__).resolve().parents[2] / "schemas"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return cwd / "schemas"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate terminology inter-module contracts")
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("validate")
    one.add_argument("file", type=Path)
    one.add_argument("--schema-dir", type=Path, default=_default_schema_dir())

    many = sub.add_parser("validate-dir")
    many.add_argument("directory", type=Path)
    many.add_argument("--schema-dir", type=Path, default=_default_schema_dir())

    glob = sub.add_parser("validate-global")
    glob.add_argument("file", type=Path)
    glob.add_argument("--schema-dir", type=Path, default=_default_schema_dir())

    sub.add_parser("print-schema-ids")
    args = parser.parse_args(argv)

    if args.command == "print-schema-ids":
        print("\n".join(sorted(SCHEMA_FILES)))
        return 0

    paths = [args.file] if args.command in {"validate", "validate-global"} else sorted(args.directory.glob("*.json"))
    failures = 0
    for path in paths:
        errors = validate_file(path, args.schema_dir)
        if errors:
            failures += 1
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
