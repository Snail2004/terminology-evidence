from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from terminology_contracts.validation import validate_file


def _check(directory: Path, *, expected_valid: bool, allow_legacy: bool) -> int:
    failures = 0
    for path in sorted(directory.glob("*.json")):
        errors = validate_file(
            path,
            ROOT / "schemas",
            allow_legacy_migration=allow_legacy,
        )
        passed = not errors if expected_valid else bool(errors)
        print(("PASS" if passed else "FAIL"), path.relative_to(ROOT))
        if not passed:
            failures += 1
            for error in errors:
                print("  -", error)
    return failures


def main() -> int:
    failures = 0
    failures += _check(
        ROOT / "examples" / "valid" / "v1.0.0",
        expected_valid=True,
        allow_legacy=True,
    )
    failures += _check(
        ROOT / "examples" / "valid" / "v1.1.0",
        expected_valid=True,
        allow_legacy=False,
    )
    failures += _check(
        ROOT / "examples" / "migrated" / "v1.1.0",
        expected_valid=True,
        allow_legacy=True,
    )
    failures += _check(
        ROOT / "examples" / "invalid" / "v1.1.0",
        expected_valid=False,
        allow_legacy=False,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
