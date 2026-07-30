"""Small-sample confidence intervals fixed by the preregistration."""

from __future__ import annotations

import math


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if successes < 0 or total < 0 or successes > total:
        raise ValueError("successes/total out of range")
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denominator
    radius = z * math.sqrt((p * (1.0 - p) / total) + (z * z / (4.0 * total * total))) / denominator
    return (max(0.0, centre - radius), min(1.0, centre + radius))
