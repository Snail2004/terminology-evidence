from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


class ScoringError(ValueError):
    pass


def assemble_decision_features(
    global_input: Mapping[str, Any], feature_registry: Mapping[str, Any]
) -> dict[str, float]:
    mappings = feature_registry.get("feature_mappings")
    if not isinstance(mappings, list) or not mappings:
        raise ScoringError("feature registry requires feature_mappings")
    result: dict[str, float] = {}
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, Mapping):
            raise ScoringError(f"feature_mappings[{index}] must be an object")
        source_package = mapping.get("source_package")
        source_path = mapping.get("source_path")
        target = mapping.get("target_feature")
        if not all(isinstance(value, str) and value for value in (source_package, source_path, target)):
            raise ScoringError(f"feature_mappings[{index}] is incomplete")
        source = _source_package(global_input, source_package)
        if source is None:
            continue
        found, value = _lookup(source, source_path)
        if not found or value is None:
            continue
        number = finite_number(value, field=f"{source_package}.{source_path}")
        if target in result:
            raise ScoringError(f"duplicate mapped target feature: {target}")
        result[target] = number
    return result


def select_model_features(
    assembled: Mapping[str, float], feature_names: Sequence[str]
) -> dict[str, float]:
    expected = tuple(feature_names)
    if not expected or len(expected) != len(set(expected)):
        raise ScoringError("model feature_names must be non-empty and unique")
    missing = [name for name in expected if name not in assembled]
    if missing:
        raise ScoringError("missing assembled model features: " + ", ".join(missing))
    return {name: finite_number(assembled[name], field=name) for name in expected}


def evaluate_calibration_model(
    calibration: Mapping[str, Any], decision_features: Mapping[str, Any]
) -> float:
    model = calibration.get("model")
    if not isinstance(model, Mapping) or model.get("model_type") != "LOGISTIC_REGRESSION":
        raise ScoringError("only LOGISTIC_REGRESSION is replayable in V1.1")
    feature_names = model.get("feature_names")
    if not isinstance(feature_names, list):
        raise ScoringError("model.feature_names must be an array")
    if set(decision_features) != set(feature_names):
        missing = sorted(set(feature_names).difference(decision_features))
        unknown = sorted(set(decision_features).difference(feature_names))
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise ScoringError("decision feature set mismatch: " + "; ".join(details))
    parameters = model.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ScoringError("model.parameters must be an object")
    if parameters.get("link_function") != "LOGIT":
        raise ScoringError("LOGISTIC_REGRESSION requires link_function=LOGIT")
    coefficients = parameters.get("coefficients")
    if not isinstance(coefficients, Mapping) or set(coefficients) != set(feature_names):
        raise ScoringError("coefficients must exactly cover model.feature_names")
    linear = finite_number(parameters.get("intercept"), field="model.intercept")
    for name in feature_names:
        linear += finite_number(
            coefficients[name], field=f"model.coefficients.{name}"
        ) * finite_number(decision_features[name], field=f"decision_features.{name}")
    if linear >= 0:
        return 1.0 / (1.0 + math.exp(-linear))
    exponential = math.exp(linear)
    return exponential / (1.0 + exponential)


def expected_decision(score: float, threshold: float, blocking_action: str) -> str:
    if blocking_action == "FATAL_SPLIT":
        return "SPLIT_REQUIRED"
    if blocking_action == "FATAL_REJECT":
        return "REJECTED"
    if blocking_action == "ESCALATE_HUMAN":
        return "HUMAN_REVIEW"
    if blocking_action == "CAP_PROVISIONAL":
        return "PROVISIONAL"
    return "AUTO_APPROVED" if score >= threshold else "PROVISIONAL"


def finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScoringError(f"{field}: finite number required")
    number = float(value)
    if not math.isfinite(number):
        raise ScoringError(f"{field}: finite number required")
    return number


def _source_package(
    global_input: Mapping[str, Any], source_package: str
) -> Mapping[str, Any] | None:
    if source_package in {"context_evidence", "attestation_evidence"}:
        value = global_input.get(source_package)
        return value if isinstance(value, Mapping) else None
    if source_package.startswith("optional_probe:"):
        probe_type = source_package.split(":", 1)[1]
        for probe in global_input.get("optional_probes", []):
            if (
                isinstance(probe, Mapping)
                and probe.get("probe_type") == probe_type
                and probe.get("status") == "AVAILABLE"
            ):
                return probe
        return None
    raise ScoringError(f"unknown feature source package: {source_package}")


def _lookup(value: Mapping[str, Any], dotted_path: str) -> tuple[bool, Any]:
    current: Any = value
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current
