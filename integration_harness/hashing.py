"""Content-addressing helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .jsonio import canonical_bytes, without_self_hash


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def self_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(without_self_hash(value)))
