"""Paired tests fixed by the statistical analysis plan."""

from __future__ import annotations

import math
from typing import Iterable, Mapping


def _binomial_cdf(k: int, n: int) -> float:
    return sum(math.comb(n, i) for i in range(k + 1)) / (2**n)


def mcnemar_exact(pairs: Iterable[Mapping[str, bool]]) -> dict[str, float | int]:
    b = 0
    c = 0
    total = 0
    for pair in pairs:
        left = bool(pair.get("left"))
        right = bool(pair.get("right"))
        total += 1
        if left and not right:
            b += 1
        elif right and not left:
            c += 1
    discordant = b + c
    if discordant == 0:
        p_value = 1.0
    else:
        smaller = min(b, c)
        p_value = min(1.0, 2.0 * _binomial_cdf(smaller, discordant))
    return {
        "paired_n": total,
        "discordant_left_only": b,
        "discordant_right_only": c,
        "effect_size": (c - b) / total if total else 0.0,
        "p_value": p_value,
    }


def paired_bootstrap_difference(left: list[float], right: list[float], *, seed: int, replicates: int = 2000) -> dict[str, float | int]:
    if len(left) != len(right):
        raise ValueError("paired arrays must have equal length")
    if not left:
        return {"paired_n": 0, "estimate": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "seed": seed, "replicates": replicates}
    from .bootstrap import _quantile
    import random

    differences = [right_value - left_value for left_value, right_value in zip(left, right)]
    rng = random.Random(seed)
    values = [sum(rng.choice(differences) for _ in differences) / len(differences) for _ in range(replicates)]
    return {
        "paired_n": len(differences),
        "estimate": sum(differences) / len(differences),
        "ci95_low": _quantile(values, 0.025),
        "ci95_high": _quantile(values, 0.975),
        "seed": seed,
        "replicates": replicates,
    }
