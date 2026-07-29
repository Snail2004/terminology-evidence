"""Registry loading and cross-registry validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constants import (
    ALLOWED_EXCLUSION_REASONS,
    ALLOWED_GLOBAL_STATUSES,
    ALLOWED_GOLD_LABELS,
    PRIMARY_METRIC_IDS,
)
from ..jsonio import read_json


class RegistryError(ValueError):
    """Raised for an invalid or internally inconsistent registry set."""


REGISTRY_FILES = (
    "research_questions_v1.json",
    "metric_registry_v1.json",
    "experiment_registry_v1.json",
    "label_mapping_v1.json",
    "split_policy_v1.json",
    "calibration_protocol_v1.json",
    "statistical_analysis_plan_v1.json",
    "exclusion_policy_v1.json",
    "ablation_registry_v1.json",
    "report_schema_v1.json",
)


def registry_root() -> Path:
    return Path(__file__).resolve().parent


def load_registries(root: Path | None = None) -> dict[str, Any]:
    base = root or registry_root()
    result: dict[str, Any] = {}
    for name in REGISTRY_FILES:
        path = base / name
        if not path.is_file():
            raise RegistryError(f"missing registry: {path}")
        result[name.removesuffix("_v1.json")] = read_json(path)
    validate_registries(result)
    return result


def _unique_ids(items: list[dict[str, Any]], label: str) -> None:
    ids = [item.get("id") for item in items]
    if any(not isinstance(item_id, str) or not item_id for item_id in ids):
        raise RegistryError(f"{label} contains an item without a non-empty id")
    if len(ids) != len(set(ids)):
        raise RegistryError(f"{label} contains duplicate ids")


def validate_registries(registries: dict[str, Any]) -> None:
    required = {
        "research_questions",
        "metric_registry",
        "experiment_registry",
        "label_mapping",
        "split_policy",
        "calibration_protocol",
        "statistical_analysis_plan",
        "exclusion_policy",
        "ablation_registry",
        "report_schema",
    }
    missing = required - registries.keys()
    if missing:
        raise RegistryError(f"missing registry objects: {sorted(missing)}")
    for name, value in registries.items():
        if not isinstance(value, dict):
            raise RegistryError(f"{name} must be an object")
        if value.get("schema_version") != "1.0.0":
            raise RegistryError(f"{name} has unsupported schema version")

    questions = registries["research_questions"].get("questions")
    metrics = registries["metric_registry"].get("metrics")
    experiments = registries["experiment_registry"].get("experiments")
    if not all(isinstance(items, list) for items in (questions, metrics, experiments)):
        raise RegistryError("questions, metrics and experiments must be arrays")
    _unique_ids(questions, "research questions")
    _unique_ids(metrics, "metrics")
    _unique_ids(experiments, "experiments")

    metric_ids = {item["id"] for item in metrics}
    for primary_id in PRIMARY_METRIC_IDS:
        if primary_id not in metric_ids:
            raise RegistryError(f"missing primary metric: {primary_id}")
    if registries["metric_registry"].get("primary_metrics") != list(PRIMARY_METRIC_IDS):
        raise RegistryError("primary metric order does not match preregistration")

    labels = registries["label_mapping"]
    if tuple(labels.get("gold_labels", ())) != ALLOWED_GOLD_LABELS:
        raise RegistryError("gold label mapping differs from frozen policy")
    if tuple(labels.get("global_statuses", ())) != ALLOWED_GLOBAL_STATUSES:
        raise RegistryError("global status mapping differs from frozen policy")
    primary = labels.get("primary_binary", {})
    if primary.get("positive") != ["ACCEPT"]:
        raise RegistryError("primary positive mapping must be ACCEPT only")
    if set(primary.get("negative", ())) != {"REJECT", "SPLIT_REQUIRED"}:
        raise RegistryError("primary negative mapping is incomplete")

    split = registries["split_policy"]
    if split.get("group_keys") != ["sense_id", "source_block_cluster"]:
        raise RegistryError("split grouping policy is not sense/source-block grouped")
    if split.get("test_access") != "ONE_TIME_AFTER_FREEZE":
        raise RegistryError("test access policy is not one-time-after-freeze")

    calibration = registries["calibration_protocol"]
    if calibration.get("model") != "logistic_regression":
        raise RegistryError("calibration model must be logistic_regression")
    if calibration.get("bootstrap_group") != "sense_id":
        raise RegistryError("calibration bootstrap must be grouped by sense_id")

    exclusions = registries["exclusion_policy"].get("allowed_reason_codes")
    if tuple(exclusions or ()) != ALLOWED_EXCLUSION_REASONS:
        raise RegistryError("exclusion reason codes differ from frozen policy")

    ablations = registries["ablation_registry"].get("ablations")
    _unique_ids(ablations, "ablations")
    if {item["id"] for item in ablations} != {"A0", "A1", "A2", "A3", "A4", "A5"}:
        raise RegistryError("minimum A0-A5 ablation matrix is incomplete")

    report = registries["report_schema"]
    if report.get("required_metric_fields") != [
        "name",
        "definition",
        "unit",
        "eligible_n",
        "excluded_n",
        "estimate",
        "confidence_interval",
        "split",
        "artifact_hashes",
    ]:
        raise RegistryError("report metric schema is incomplete")


def registry_counts(registries: dict[str, Any]) -> dict[str, int]:
    return {
        "research_questions": len(registries["research_questions"]["questions"]),
        "metrics": len(registries["metric_registry"]["metrics"]),
        "experiments": len(registries["experiment_registry"]["experiments"]),
        "ablations": len(registries["ablation_registry"]["ablations"]),
    }
