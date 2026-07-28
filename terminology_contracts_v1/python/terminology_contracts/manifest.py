from __future__ import annotations

import hashlib
import json
from pathlib import Path


def verify_manifest(root: Path) -> list[str]:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for record in manifest.get("files", []):
        path = root / record["path"]
        if not path.exists():
            errors.append(f"missing: {record['path']}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != record["sha256"]:
            errors.append(f"hash mismatch: {record['path']}")
    return errors
