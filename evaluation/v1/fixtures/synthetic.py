"""Deterministic fixtures covering the evaluation protocol without network calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..jsonio import sha256_value, write_json


def build_synthetic_rows() -> list[dict[str, Any]]:
    labels = ("ACCEPT", "CONDITIONAL", "REJECT", "SPLIT_REQUIRED", "HUMAN_UNJUDGEABLE")
    statuses = ("AUTO_APPROVED", "PROVISIONAL", "REJECTED", "SPLIT_REQUIRED", "HUMAN_REVIEW")
    rows: list[dict[str, Any]] = []
    for index in range(15):
        sense_index = index // 3
        label = labels[index % len(labels)]
        status = statuses[index % len(statuses)]
        if index == 5:
            label = "REJECT"
            status = "AUTO_APPROVED"
        key = {
            "source_term": f"term_{sense_index}",
            "sense_id": f"sense_{sense_index}",
            "scope_id": "global",
            "candidate_vi": f"ứng viên {index}",
        }
        rows.append(
            {
                "candidate_key": key,
                "split": "development",
                "source_block_cluster": f"cluster_{sense_index}",
                "evidence_source_ids": [f"source_{index}"],
                "gold_label": label,
                "global_status": status,
                "C_status": "PASS" if index % 2 else "MINOR",
                "E_status": "SAME" if index % 3 else "INSUFFICIENT_EVIDENCE",
                "C_score": round(0.55 + index * 0.02, 6),
                "E_score": round(0.50 + index * 0.015, 6),
                "approval_score": round(0.40 + index * 0.04, 6),
                "features": {"C_mean": round(0.55 + index * 0.02, 6), "E_authority": round(0.50 + index * 0.015, 6)},
                "fixture_only": True,
            }
        )
    return rows


def build_fixture_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_id": "EvaluationSyntheticFixtureManifestV1",
        "schema_version": "1.0.0",
        "status": "SYNTHETIC_LOCAL_CONFORMANCE",
        "candidate_count": len(rows),
        "rows_sha256": sha256_value(rows),
        "network_calls": 0,
    }


def write_synthetic_release(root: Path) -> dict[str, Any]:
    rows = build_synthetic_rows()
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "rows.json", {"schema_id": "EvaluationSyntheticRowsV1", "rows": rows})
    manifest = build_fixture_manifest(rows)
    write_json(root / "manifest.json", manifest)
    return manifest
