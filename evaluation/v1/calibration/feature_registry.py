"""Read-only validation against the published machine-readable feature registry."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..jsonio import read_json


class FeatureRegistryError(ValueError):
    """Raised when a calibration feature set is not registry-compatible."""


def registry_feature_names(path: Path) -> tuple[str, ...]:
    value = read_json(path)
    names: list[str] = []
    for key in ("core_features", "producer_context_features", "producer_attestation_features", "optional_probe_features"):
        values = value.get(key, [])
        if not isinstance(values, list):
            raise FeatureRegistryError(f"feature registry field is not a list: {key}")
        names.extend(str(item) for item in values)
    if len(names) != len(set(names)):
        names = list(dict.fromkeys(names))
    return tuple(names)


def validate_feature_names(names: Sequence[str], registry_path: Path) -> tuple[str, ...]:
    requested = tuple(names)
    if len(requested) != len(set(requested)) or any(not name for name in requested):
        raise FeatureRegistryError("feature names must be unique and non-empty")
    allowed = set(registry_feature_names(registry_path))
    unknown = sorted(set(requested) - allowed)
    if unknown:
        raise FeatureRegistryError(f"features absent from registry: {unknown}")
    return requested
