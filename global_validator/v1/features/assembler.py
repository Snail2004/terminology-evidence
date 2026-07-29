from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from terminology_contracts.registries import RegistryError, load_registry
from terminology_contracts.scoring import ScoringError, assemble_decision_features

from ..errors import FeatureAssemblyError


def assemble_registered_features(
    global_input: Mapping[str, Any], feature_registry_path: Path
) -> tuple[dict[str, float], dict[str, Any]]:
    try:
        registry = load_registry(feature_registry_path)
        features = assemble_decision_features(global_input, registry)
    except (RegistryError, ScoringError, OSError, ValueError) as exc:
        raise FeatureAssemblyError(str(exc)) from exc
    return features, registry
