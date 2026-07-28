from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import sha256_file

from ..errors import IntegrityValidationError
from ..jsonio import assert_strict_json_file


def verify_collision_index_binding(
    global_input: Mapping[str, Any], collision_index_path: Path | None
) -> None:
    collision = global_input.get("constraint_evidence", {}).get(
        "target_collision", {}
    )
    expected = collision.get("collision_index_sha256")
    reference = collision.get("collision_index_ref")
    if expected is None:
        if collision_index_path is not None:
            raise IntegrityValidationError(
                "unbound collision index was supplied for this candidate"
            )
        return
    if collision_index_path is None:
        raise IntegrityValidationError(
            "constraint evidence requires the bound collision index file"
        )
    try:
        assert_strict_json_file(collision_index_path)
        actual = sha256_file(collision_index_path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise IntegrityValidationError(
            f"cannot verify collision index: {exc}"
        ) from exc
    if actual != expected:
        raise IntegrityValidationError("collision index physical SHA-256 mismatch")
    if not isinstance(reference, Mapping) or reference.get("sha256") != actual:
        raise IntegrityValidationError("collision index evidence reference mismatch")
