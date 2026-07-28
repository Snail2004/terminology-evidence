from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from terminology_contracts.migration import MigrationError, migrate_file  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministically migrate one terminology contract V1.0 payload to V1.1"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    try:
        result = migrate_file(args.source, args.target, args.report)
    except MigrationError as exc:
        parser.error(str(exc))
    print(result.report["target_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
