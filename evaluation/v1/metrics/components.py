"""Component, gate, TAC and downstream metric projections."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def _rate(successes: int, total: int) -> dict[str, Any]:
    return {"successes": successes, "total": total, "estimate": successes / total if total else 0.0}


def summarize_c(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(rows)
    statuses = Counter(row.get("C_status") for row in records)
    predictions = [row for row in records if row.get("C_predicted_wrong_sense") is not None]
    true_positive = sum(bool(row.get("C_predicted_wrong_sense")) and bool(row.get("C_gold_wrong_sense")) for row in predictions)
    predicted_positive = sum(bool(row.get("C_predicted_wrong_sense")) for row in predictions)
    gold_positive = sum(bool(row.get("C_gold_wrong_sense")) for row in predictions)
    return {
        "n": len(records),
        "status_counts": dict(sorted((str(key), value) for key, value in statuses.items())),
        "wrong_sense_precision": _rate(true_positive, predicted_positive),
        "wrong_sense_recall": _rate(true_positive, gold_positive),
    }


def summarize_e(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(rows)
    statuses = Counter(row.get("E_status") for row in records)
    evaluated = [row for row in records if row.get("E_gold") in {"SAME", "DIFFERENT"}]
    same_true = sum(row.get("E_status") == "SAME" and row.get("E_gold") == "SAME" for row in evaluated)
    same_pred = sum(row.get("E_status") == "SAME" for row in evaluated)
    same_gold = sum(row.get("E_gold") == "SAME" for row in evaluated)
    return {
        "n": len(records),
        "status_counts": dict(sorted((str(key), value) for key, value in statuses.items())),
        "same_precision": _rate(same_true, same_pred),
        "same_recall": _rate(same_true, same_gold),
        "unjudgeable_rate": _rate(sum(row.get("E_status") in {"UNJUDGEABLE", "INSUFFICIENT_EVIDENCE"} for row in records), len(records)),
    }


def summarize_gates(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(rows)
    triggered = [row for row in records if row.get("gate_triggered") is True]
    correct = [row for row in triggered if row.get("gate_gold_trigger") is True]
    return {"trigger_rate": _rate(len(triggered), len(records)), "trigger_precision": _rate(len(correct), len(triggered))}


def summarize_tac(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(rows)
    labels = Counter(row.get("tac_label") for row in records)
    wrong = [row for row in records if row.get("tac_gold") == "WRONG_SENSE"]
    detected = sum(row.get("tac_label") == "WRONG_SENSE" for row in wrong)
    return {"label_counts": dict(sorted((str(key), value) for key, value in labels.items())), "wrong_sense_recall": _rate(detected, len(wrong))}


def summarize_downstream(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = list(rows)
    by_arm: dict[str, list[Mapping[str, Any]]] = {}
    for row in records:
        arm = str(row.get("arm", "unknown"))
        by_arm.setdefault(arm, []).append(row)
    result: dict[str, Any] = {}
    for arm, arm_rows in sorted(by_arm.items()):
        values = [float(row["terminology_correctness"]) for row in arm_rows if isinstance(row.get("terminology_correctness"), (int, float))]
        result[arm] = {"n": len(arm_rows), "terminology_correctness_mean": sum(values) / len(values) if values else None}
    return result
