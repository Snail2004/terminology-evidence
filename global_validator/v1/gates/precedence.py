from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from terminology_contracts.registries import GATE_ACTION_PRECEDENCE


def highest_blocking_action(observations: Sequence[Mapping[str, Any]]) -> str:
    triggered = {
        observation.get("action")
        for observation in observations
        if observation.get("triggered") is True
    }
    return next(
        (action for action in GATE_ACTION_PRECEDENCE if action in triggered),
        "NONE",
    )
