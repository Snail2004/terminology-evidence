"""Seeded bootstrap grouped by sense_id, never by independent candidate."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Callable, Iterable, Mapping

from ..identities import row_sense_id


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def grouped_bootstrap(
    rows: Iterable[Mapping[str, Any]],
    statistic: Callable[[list[Mapping[str, Any]]], float],
    *,
    seed: int,
    replicates: int = 2000,
    group_field: str = "sense_id",
) -> dict[str, Any]:
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        group = row.get(group_field) or row_sense_id(row)
        groups[str(group)].append(row)
    if not groups:
        return {"seed": seed, "replicates": replicates, "group_count": 0, "estimate": 0.0, "ci95": (0.0, 0.0), "values": []}
    keys = sorted(groups)
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(replicates):
        sampled = [groups[key] for key in (rng.choice(keys) for _ in keys)]
        sample_rows = [row for group in sampled for row in group]
        values.append(float(statistic(sample_rows)))
    original = float(statistic([row for group in groups.values() for row in group]))
    return {
        "seed": seed,
        "replicates": replicates,
        "group_count": len(keys),
        "estimate": original,
        "ci95": (_quantile(values, 0.025), _quantile(values, 0.975)),
        "values": values,
    }


def decision_flip_rate(values: Iterable[float], threshold: float, baseline: float | None = None) -> float:
    values_list = list(values)
    if not values_list:
        return 0.0
    reference = threshold if baseline is None else baseline
    reference_decision = reference >= threshold
    flips = sum((value >= threshold) != reference_decision for value in values_list)
    return flips / len(values_list)
