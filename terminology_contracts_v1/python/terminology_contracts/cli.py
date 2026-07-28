from __future__ import annotations

import argparse
from pathlib import Path

from .migration import migrate_file
from .registries import SCHEMA_FILES
from .validation import validate_file


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_schema_dir() -> Path:
    candidates = [Path.cwd() / "schemas", _package_root() / "schemas"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def _add_validation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--schema-dir", type=Path, default=_default_schema_dir())
    parser.add_argument("--calibration", type=Path, default=None)
    parser.add_argument("--feature-registry", type=Path, default=None)
    parser.add_argument("--allow-legacy-migration", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and migrate terminology inter-module contracts"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("validate")
    one.add_argument("file", type=Path)
    _add_validation_options(one)

    many = sub.add_parser("validate-dir")
    many.add_argument("directory", type=Path)
    _add_validation_options(many)

    glob = sub.add_parser("validate-global")
    glob.add_argument("file", type=Path)
    _add_validation_options(glob)

    migrate = sub.add_parser("migrate")
    migrate.add_argument("source", type=Path)
    migrate.add_argument("target", type=Path)
    migrate.add_argument("report", type=Path)

    sub.add_parser("print-schema-ids")
    args = parser.parse_args(argv)

    if args.command == "print-schema-ids":
        print("\n".join(sorted(SCHEMA_FILES)))
        return 0
    if args.command == "migrate":
        result = migrate_file(args.source, args.target, args.report)
        print(f"MIGRATED {args.source} -> {args.target}")
        print(f"REPORT {args.report}")
        print(f"TARGET {result.report['target_sha256']}")
        return 0

    if args.command in {"validate", "validate-global"}:
        paths = [args.file]
    else:
        paths = sorted(args.directory.rglob("*.json"))
    failures = 0
    for path in paths:
        errors = validate_file(
            path,
            args.schema_dir,
            calibration_path=args.calibration,
            feature_registry_path=args.feature_registry,
            allow_legacy_migration=args.allow_legacy_migration,
        )
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
