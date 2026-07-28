from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from terminology_contracts.validation import validate_file

failures = 0
for path in sorted((ROOT / "examples" / "valid").glob("*.json")):
    errors = validate_file(path, ROOT / "schemas")
    print(("PASS" if not errors else "FAIL"), path.name)
    for error in errors:
        print("  -", error)
    failures += bool(errors)
raise SystemExit(1 if failures else 0)
