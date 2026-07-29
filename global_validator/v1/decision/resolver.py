from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from terminology_contracts.registries import GATE_IDS
from terminology_contracts.scoring import expected_decision

from ..config import ExecutionMode
from ..gates import highest_blocking_action


@dataclass(frozen=True)
class DecisionResolution:
    blocking_action: str
    decision: str
    reasons: tuple[str, ...]


def resolve_decision(
    observations: Sequence[Mapping[str, Any]],
    *,
    mode: ExecutionMode,
    approval_score: float | None,
    threshold: float | None,
) -> DecisionResolution:
    blocking = highest_blocking_action(observations)
    if mode is ExecutionMode.DEVELOPMENT_HEURISTIC:
        decision = _development_decision(blocking)
    else:
        if approval_score is None or threshold is None:
            raise ValueError("frozen decision requires approval score and threshold")
        decision = expected_decision(approval_score, threshold, blocking)
    reasons = _decision_reasons(
        observations,
        mode=mode,
        blocking=blocking,
        approval_score=approval_score,
        threshold=threshold,
    )
    return DecisionResolution(blocking, decision, tuple(reasons))


def _development_decision(blocking: str) -> str:
    return {
        "FATAL_SPLIT": "SPLIT_REQUIRED",
        "FATAL_REJECT": "REJECTED",
        "ESCALATE_HUMAN": "HUMAN_REVIEW",
        "CAP_PROVISIONAL": "PROVISIONAL",
        "NONE": "PROVISIONAL",
    }[blocking]


def _decision_reasons(
    observations: Sequence[Mapping[str, Any]],
    *,
    mode: ExecutionMode,
    blocking: str,
    approval_score: float | None,
    threshold: float | None,
) -> list[str]:
    result: list[str] = []
    if blocking != "NONE":
        result.append(f"GATE_{blocking}")
    by_id = {
        observation.get("gate_id"): observation
        for observation in observations
        if observation.get("triggered") is True
    }
    for gate_id in GATE_IDS:
        observation = by_id.get(gate_id)
        if observation is None:
            continue
        result.append(gate_id.upper())
        result.extend(sorted(observation.get("reason_codes", [])))
    if blocking == "NONE":
        if mode is ExecutionMode.DEVELOPMENT_HEURISTIC:
            result.append("DEVELOPMENT_NO_FROZEN_CALIBRATION")
        elif approval_score is not None and threshold is not None:
            result.append(
                "CALIBRATED_SCORE_AT_OR_ABOVE_THRESHOLD"
                if approval_score >= threshold
                else "CALIBRATED_SCORE_BELOW_AUTO_APPROVAL_THRESHOLD"
            )
    return _stable_unique(result)


def _stable_unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
