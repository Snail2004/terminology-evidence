from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def calculate_self_sha256(value: dict[str, Any]) -> str:
    clone = copy.deepcopy(value)
    integrity = clone.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("self_sha256", None)
    return hashlib.sha256(canonical_bytes(clone)).hexdigest()


def verify_self_sha256(value: dict[str, Any]) -> bool:
    integrity = value.get("integrity")
    return isinstance(integrity, dict) and integrity.get("self_sha256") == calculate_self_sha256(value)
