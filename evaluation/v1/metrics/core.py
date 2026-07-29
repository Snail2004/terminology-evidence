"""Primary and secondary deterministic metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

from ..constants import ALLOWED_GOLD_LABELS, ALLOWED_GLOBAL_STATUSES
from ..identities import row_candidate_key, row_sense_id
from .intervals import wilson_interval


def _proportion(successes: int, total: int) -> dict[str, Any]:
    estimate = successes / total if total else 0.0
    return {
        "successes": successes,
        "total": total,
        "estimate": estimate,
        "confidence_interval": wilson_interval(successes, total),
    }


def summarize_global(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(rows)
    eligible = [row for row in records if row.get("gold_label") not in (None, "CONDITIONAL", "HUMAN_UNJUDGEABLE")]
    auto = [row for row in eligible if row.get("global_status") == "AUTO_APPROVED"]
    auto_true = [row for row in auto if row.get("gold_label") == "ACCEPT"]
    hard = [row for row in eligible if row.get("global_status") in ("REJECTED", "SPLIT_REQUIRED")]
    hard_true = [
        row
        for row in hard
        if (row.get("global_status") == "REJECTED" and row.get("gold_label") == "REJECT")
        or (row.get("global_status") == "SPLIT_REQUIRED" and row.get("gold_label") == "SPLIT_REQUIRED")
    ]
    review = [row for row in eligible if row.get("global_status") in ("HUMAN_REVIEW", "PROVISIONAL")]
    status_counts = Counter(row.get("global_status") for row in records)
    return {
        "eligible_n": len(eligible),
        "excluded_n": len(records) - len(eligible),
        "status_counts": dict(sorted(status_counts.items(), key=lambda item: str(item[0]))),
        "auto_approved_precision": _proportion(len(auto_true), len(auto)),
        "auto_approved_coverage": _proportion(len(auto), len(eligible)),
        "false_approval_count": len(auto) - len(auto_true),
        "human_review_rate": _proportion(len(review), len(eligible)),
        "hard_rejection_accuracy": _proportion(len(hard_true), len(hard)),
    }


def summarize_labels(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(rows)
    labels = [row.get("gold_label") for row in records]
    unknown = set(labels) - set(ALLOWED_GOLD_LABELS)
    if unknown:
        raise ValueError(f"unknown gold labels: {sorted(unknown)}")
    counts = Counter(labels)
    binary_rows = [row for row in records if row.get("gold_label") in ("ACCEPT", "REJECT", "SPLIT_REQUIRED")]
    positive = sum(row.get("gold_label") == "ACCEPT" for row in binary_rows)
    negative = len(binary_rows) - positive
    return {
        "label_counts": dict(sorted(counts.items())),
        "primary_binary": _proportion(positive, len(binary_rows)),
        "primary_negative_count": negative,
    }


def grouped_confusion(rows: Iterable[Mapping[str, Any]], *, group_field: str = "sense_id") -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(group_field) or row_sense_id(row))].append(row)
    per_group: dict[str, dict[str, int]] = {}
    for group, group_rows in sorted(groups.items()):
        per_group[group] = {
            "n": len(group_rows),
            "accept": sum(row.get("gold_label") == "ACCEPT" for row in group_rows),
            "auto_approved": sum(row.get("global_status") == "AUTO_APPROVED" for row in group_rows),
        }
    return {"groups": per_group, "group_count": len(per_group)}


def component_summary(rows: Iterable[Mapping[str, Any]], component: str) -> dict[str, Any]:
    records = list(rows)
    prefix = component.upper()
    statuses = Counter(row.get(f"{component}_status", row.get(f"{prefix}_status")) for row in records)
    values = [row.get(f"{component}_score", row.get(f"{prefix}_score")) for row in records]
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return {
        "component": component,
        "n": len(records),
        "status_counts": dict(sorted((str(k), v) for k, v in statuses.items())),
        "score_mean": (sum(numeric) / len(numeric)) if numeric else None,
        "score_n": len(numeric),
    }
