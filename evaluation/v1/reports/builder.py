"""Build JSON, CSV and Markdown evaluation reports from exact rows."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..jsonio import canonical_bytes, sha256_value, write_json
from ..metrics.bootstrap import grouped_bootstrap
from ..metrics.components import summarize_c, summarize_downstream, summarize_e, summarize_gates, summarize_tac
from ..metrics.core import summarize_global, summarize_labels


def _metric_record(
    name: str,
    definition: str,
    unit: str,
    summary: Mapping[str, Any],
    *,
    eligible_n: int,
    excluded_n: int,
    split: str,
    artifact_hashes: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "name": name,
        "definition": definition,
        "unit": unit,
        "eligible_n": eligible_n,
        "excluded_n": excluded_n,
        "estimate": summary.get("estimate", summary),
        "confidence_interval": summary.get("confidence_interval", (0.0, 0.0)),
        "split": split,
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
    }


def build_evaluation_report(
    rows: Iterable[Mapping[str, Any]],
    output_root: Path,
    *,
    split: str,
    artifact_hashes: Mapping[str, str] | None = None,
    bootstrap_seed: int = 20260729,
    bootstrap_replicates: int = 200,
) -> dict[str, Any]:
    records = [dict(row) for row in rows]
    hashes = artifact_hashes or {}
    global_summary = summarize_global(records)
    label_summary = summarize_labels(records)
    metric_rows = [
        _metric_record("auto_approved_precision", "true AUTO_APPROVED divided by AUTO_APPROVED", "proportion", global_summary["auto_approved_precision"], eligible_n=global_summary["eligible_n"], excluded_n=global_summary["excluded_n"], split=split, artifact_hashes=hashes),
        _metric_record("auto_approved_coverage", "AUTO_APPROVED divided by eligible candidates", "proportion", global_summary["auto_approved_coverage"], eligible_n=global_summary["eligible_n"], excluded_n=global_summary["excluded_n"], split=split, artifact_hashes=hashes),
        _metric_record("false_approval_count", "AUTO_APPROVED candidates whose gold is not ACCEPT", "count", {"estimate": global_summary["false_approval_count"], "confidence_interval": (0.0, 0.0)}, eligible_n=global_summary["eligible_n"], excluded_n=global_summary["excluded_n"], split=split, artifact_hashes=hashes),
        _metric_record("human_review_rate", "PROVISIONAL or HUMAN_REVIEW divided by eligible candidates", "proportion", global_summary["human_review_rate"], eligible_n=global_summary["eligible_n"], excluded_n=global_summary["excluded_n"], split=split, artifact_hashes=hashes),
        _metric_record("hard_rejection_accuracy", "correct REJECTED or SPLIT_REQUIRED decisions", "proportion", global_summary["hard_rejection_accuracy"], eligible_n=global_summary["eligible_n"], excluded_n=global_summary["excluded_n"], split=split, artifact_hashes=hashes),
    ]
    bootstrap = grouped_bootstrap(
        records,
        lambda sample: summarize_global(sample)["auto_approved_precision"]["estimate"],
        seed=bootstrap_seed,
        replicates=bootstrap_replicates,
    )
    report = {
        "schema_id": "EvaluationReportV1",
        "schema_version": "1.0.0",
        "status": "SYNTHETIC_LOCAL_CONFORMANCE" if any(row.get("fixture_only") for row in records) else "DEVELOPMENT",
        "split": split,
        "candidate_count": len(records),
        "primary_metrics": metric_rows,
        "label_summary": label_summary,
        "global_summary": global_summary,
        "component_summaries": {
            "C": summarize_c(records),
            "E": summarize_e(records),
            "gates": summarize_gates(records),
            "TAC": summarize_tac(records),
            "downstream": summarize_downstream(records),
        },
        "bootstrap_summary": {
            "metric": "auto_approved_precision",
            "seed": bootstrap["seed"],
            "replicates": bootstrap["replicates"],
            "group_count": bootstrap["group_count"],
            "estimate": bootstrap["estimate"],
            "ci95": bootstrap["ci95"],
        },
        "artifact_hashes": dict(sorted(hashes.items())),
        "semantic_sha256": "",
    }
    report["semantic_sha256"] = sha256_value({key: value for key, value in report.items() if key != "semantic_sha256"})
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / "primary_metrics.json", {"metrics": metric_rows})
    write_json(output_root / "secondary_metrics.json", {"labels": label_summary, "global": global_summary})
    write_json(output_root / "bootstrap_summary.json", report["bootstrap_summary"])
    write_json(output_root / "evaluation_report.json", report)
    with (output_root / "candidate_results.csv").open("w", encoding="utf-8", newline="") as handle:
        columns = ["candidate_key", "split", "gold_label", "global_status", "C_status", "E_status", "approval_score"]
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in sorted(records, key=lambda item: str(item.get("candidate_key"))):
            output = dict(row)
            output["candidate_key"] = str(output.get("candidate_key"))
            writer.writerow({column: output.get(column, "") for column in columns})
    (output_root / "EVALUATION_REPORT.md").write_text(_markdown_report(report), encoding="utf-8", newline="\n")
    (output_root / "LIMITATIONS.md").write_text(_limitations(report), encoding="utf-8", newline="\n")
    return report


def _markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Evaluation Report V1",
        "",
        f"Status: `{report['status']}`",
        f"Split: `{report['split']}`",
        f"Candidates: `{report['candidate_count']}`",
        "",
        "| Metric | Estimate | CI95 | Eligible | Excluded |",
        "|---|---:|---|---:|---:|",
    ]
    for metric in report["primary_metrics"]:
        estimate = metric["estimate"]
        ci = metric["confidence_interval"]
        lines.append(f"| {metric['name']} | {estimate} | {ci} | {metric['eligible_n']} | {metric['excluded_n']} |")
    lines.extend(["", f"Semantic report SHA256: `{report['semantic_sha256']}`", ""])
    return "\n".join(lines)


def _limitations(report: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Limitations",
            "",
            "This report is not evidence for the thesis when status is `SYNTHETIC_LOCAL_CONFORMANCE`.",
            "Synthetic fixtures validate schema, determinism and metric plumbing only.",
            "Real Stage B gold and complete provider packages require independent authority verification.",
            "",
        ]
    )
