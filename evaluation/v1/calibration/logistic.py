"""A dependency-free, deterministic logistic regression implementation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .feature_registry import validate_feature_names


def _sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-value)
        return 1.0 / (1.0 + inverse)
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


@dataclass(frozen=True)
class LogisticModel:
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]
    intercept: float
    iterations: int

    def predict_probability(self, features: Sequence[float]) -> float:
        if len(features) != len(self.coefficients):
            raise ValueError("feature count does not match model")
        return _sigmoid(self.intercept + sum(weight * value for weight, value in zip(self.coefficients, features)))

    def to_dict(self) -> dict[str, object]:
        return {
            "model": "logistic_regression",
            "feature_names": list(self.feature_names),
            "coefficients": list(self.coefficients),
            "intercept": self.intercept,
            "iterations": self.iterations,
        }


def fit_logistic(
    rows: Iterable[tuple[Sequence[float], int]],
    *,
    feature_names: Sequence[str],
    iterations: int = 2000,
    learning_rate: float = 0.05,
    l2: float = 1e-6,
    feature_registry_path: Path | None = None,
) -> LogisticModel:
    samples = [(tuple(float(value) for value in features), int(label)) for features, label in rows]
    if not samples:
        raise ValueError("cannot fit with no samples")
    if feature_registry_path is not None:
        validate_feature_names(feature_names, feature_registry_path)
    width = len(feature_names)
    if any(len(features) != width or label not in (0, 1) for features, label in samples):
        raise ValueError("invalid logistic training row")
    weights = [0.0] * width
    intercept = 0.0
    for _ in range(iterations):
        grad_w = [0.0] * width
        grad_b = 0.0
        for features, label in samples:
            probability = _sigmoid(intercept + sum(weight * value for weight, value in zip(weights, features)))
            error = probability - label
            grad_b += error
            for index, value in enumerate(features):
                grad_w[index] += error * value
        scale = 1.0 / len(samples)
        intercept -= learning_rate * grad_b * scale
        for index in range(width):
            grad_w[index] = grad_w[index] * scale + l2 * weights[index]
            weights[index] -= learning_rate * grad_w[index]
    return LogisticModel(tuple(feature_names), tuple(weights), intercept, iterations)


def choose_threshold(
    probabilities: Sequence[float],
    labels: Sequence[int],
    *,
    precision_target: float = 0.95,
) -> dict[str, float | int | None]:
    if len(probabilities) != len(labels):
        raise ValueError("probabilities and labels must have equal length")
    if not probabilities:
        return {"threshold": None, "precision": None, "coverage": 0.0, "eligible_n": 0}
    candidates = sorted({0.0, 1.0, *[float(value) for value in probabilities]}, reverse=True)
    selected: dict[str, float | int | None] | None = None
    for threshold in candidates:
        predicted = [value >= threshold for value in probabilities]
        approved = sum(predicted)
        true_positive = sum(flag and label == 1 for flag, label in zip(predicted, labels))
        precision = true_positive / approved if approved else 1.0
        coverage = approved / len(labels)
        if precision >= precision_target:
            option = {"threshold": threshold, "precision": precision, "coverage": coverage, "eligible_n": len(labels)}
            if selected is None or float(option["coverage"]) > float(selected["coverage"]):
                selected = option
    if selected is not None:
        return selected
    threshold = max(probabilities)
    approved = sum(value >= threshold for value in probabilities)
    true_positive = sum(value >= threshold and label == 1 for value, label in zip(probabilities, labels))
    return {
        "threshold": threshold,
        "precision": true_positive / approved if approved else 0.0,
        "coverage": approved / len(labels),
        "eligible_n": len(labels),
        "target_met": False,
    }


def brier_score(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    if len(probabilities) != len(labels):
        raise ValueError("probabilities and labels must have equal length")
    return sum((float(probability) - int(label)) ** 2 for probability, label in zip(probabilities, labels)) / len(labels) if labels else 0.0


def log_loss(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    if len(probabilities) != len(labels):
        raise ValueError("probabilities and labels must have equal length")
    if not labels:
        return 0.0
    epsilon = 1e-15
    return -sum(
        label * math.log(max(epsilon, min(1.0 - epsilon, probability)))
        + (1 - label) * math.log(max(epsilon, min(1.0 - epsilon, 1.0 - probability)))
        for probability, label in zip(probabilities, labels)
    ) / len(labels)
