from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    replace_directory,
    seal_record,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_record,
    write_checksums,
    write_json,
    write_jsonl,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_gold import (
    _manifest_self_hash,
    _validate_manifest,
)


ARTIFACT_NAME = "d2l_stage_b_150x450_gold_v1"
POLICY_ID = "d2l-dataset-150-source-slots-450-candidates-stage-b-gold-v1.0"
RELEASE_STATUS = "STAGE_B_150X450_GOLD_COMPLETE_READY_FOR_C_E_EVALUATION"


def _dimension_report(
    rows: Sequence[Mapping[str, Any]], field: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(row)
    return {
        key: {
            "candidate_count": len(items),
            "label_counts": dict(
                sorted(Counter(row["final_gold_label"] for row in items).items())
            ),
        }
        for key, items in sorted(grouped.items())
    }


def _load_sources(
    *,
    stage_a_complete_root: Path,
    baseline_gold_root: Path,
    remaining_gold_root: Path,
) -> dict[str, Any]:
    stage_a_manifest = _validate_manifest(
        stage_a_complete_root, "d2l_dataset_150_stage_a_complete_v1"
    )
    baseline_manifest = _validate_manifest(
        baseline_gold_root,
        "d2l_dataset_50_senses_150_candidates_stage_b_gold_v1",
    )
    remaining_manifest = _validate_manifest(
        remaining_gold_root, "d2l_stage_b_300_gold_v1"
    )
    stage_a_summary = strict_json_object(stage_a_complete_root / "completion_summary.json")
    if (
        stage_a_summary.get("original_source_slot_count") != 150
        or stage_a_summary.get("effective_sense_count") != 155
        or stage_a_summary.get("candidate_instance_count") != 450
    ):
        raise ValueError("Stage A completion population mismatch")
    source_slots = strict_jsonl(
        stage_a_complete_root / "stage_a_source_slot_index_150.jsonl"
    )
    if len(source_slots) != 150 or any(
        not verify_record(row, "record_sha256") for row in source_slots
    ):
        raise ValueError("Stage A source-slot index is invalid")
    source_slot_map = {row["source_slot_sense_id"]: row for row in source_slots}
    if len(source_slot_map) != 150:
        raise ValueError("Stage A source-slot IDs are duplicated")
    baseline = strict_jsonl(baseline_gold_root / "stage_b_gold_150.jsonl")
    remaining = strict_jsonl(remaining_gold_root / "stage_b_gold_300.jsonl")
    if len(baseline) != 150 or any(
        not verify_record(row, "stage_b_gold_sha256") for row in baseline
    ):
        raise ValueError("baseline Stage B gold is invalid")
    if len(remaining) != 300 or any(
        not verify_record(row, "stage_b_gold_sha256") for row in remaining
    ):
        raise ValueError("remaining Stage B gold is invalid")
    baseline_candidates = {row["candidate_id"] for row in baseline}
    remaining_candidates = {row["candidate_id"] for row in remaining}
    if (
        len(baseline_candidates) != 150
        or len(remaining_candidates) != 300
        or baseline_candidates & remaining_candidates
    ):
        raise ValueError("Stage B candidate partitions overlap or contain duplicates")
    complete_slots = {
        row["source_slot_sense_id"]
        for row in source_slots
        if row["stage_b_status"] == "COMPLETE"
    }
    pending_slots = {
        row["source_slot_sense_id"]
        for row in source_slots
        if row["stage_b_status"] == "PENDING"
    }
    if complete_slots != {row["sense_id"] for row in baseline}:
        raise ValueError("baseline gold does not cover the 50 completed source slots")
    if pending_slots != {row["source_slot_sense_id"] for row in remaining}:
        raise ValueError("remaining gold does not cover the 100 pending source slots")
    return {
        "stage_a_manifest": stage_a_manifest,
        "baseline_manifest": baseline_manifest,
        "remaining_manifest": remaining_manifest,
        "source_slots": source_slots,
        "source_slot_map": source_slot_map,
        "baseline": baseline,
        "remaining": remaining,
    }


def _projection_row(
    *,
    source_row: Mapping[str, Any],
    source_partition: str,
    source_manifest_sha256: str,
    stage_a_manifest_sha256: str,
    source_slot: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = source_partition == "BASELINE_50"
    effective_sense_id = (
        source_row["sense_id"] if baseline else source_row["effective_sense_id"]
    )
    source_slot_sense_id = (
        source_row["sense_id"] if baseline else source_row["source_slot_sense_id"]
    )
    return seal_record(
        {
            "schema_id": "D2LStageB150x450CandidateGoldProjectionV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "stage_a_complete_manifest_sha256": stage_a_manifest_sha256,
            "source_partition": source_partition,
            "source_partition_manifest_sha256": source_manifest_sha256,
            "source_stage_b_gold_sha256": source_row["stage_b_gold_sha256"],
            "source_slot_sense_id": source_slot_sense_id,
            "effective_sense_id": effective_sense_id,
            "stage_a_source_slot_record_sha256": source_slot["record_sha256"],
            "stage_a_authority_sha256": source_slot.get("authority_record_sha256"),
            "source_term": source_row["source_term"],
            "scope_id": source_row["scope_id"],
            "candidate_id": source_row["candidate_id"],
            "candidate_version": source_row["candidate_version"],
            "candidate_target_vi": source_row["candidate_target_vi"],
            "candidate_instance_sha256": source_row["candidate_instance_sha256"],
            "candidate_evidence_sha256": (
                source_row["frozen_candidate_contract_sha256"]
                if baseline
                else source_row["candidate_instance_sha256"]
            ),
            "effective_sense_evidence_sha256": (
                source_row["effective_sense_contract_sha256"]
                if baseline
                else source_row["effective_sense_record_sha256"]
            ),
            "split": source_row["split"],
            "stratum": source_row["stratum"],
            "kind": "BASELINE_EFFECTIVE_SENSE" if baseline else source_row["kind"],
            "source_lane": source_row.get("lane"),
            "review_pair_sha256": source_row["review_pair_sha256"],
            "reviewer_1_label": source_row["reviewer_1_label"],
            "reviewer_2_label": source_row["reviewer_2_label"],
            "label_agreement": source_row["label_agreement"],
            "adjudication_label": source_row["adjudication_label"],
            "adjudication_case_sha256": source_row["adjudication_case_sha256"],
            "review_resolution": source_row["review_resolution"],
            "final_gold_label": source_row["final_gold_label"],
            "gold_freeze_status": "COMPLETE",
            "c_e_evaluation_status": "READY_NOT_RUN",
            "global_validator_status": "NOT_RUN",
            "provider_call_count": 0,
            "final_glossary_decision": None,
        },
        "stage_b_150x450_gold_sha256",
    )


def _project_rows(sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    stage_a_manifest = sources["stage_a_manifest"]
    source_slot_map = sources["source_slot_map"]
    rows: list[dict[str, Any]] = []
    for source_row in sources["baseline"]:
        slot_id = source_row["sense_id"]
        rows.append(
            _projection_row(
                source_row=source_row,
                source_partition="BASELINE_50",
                source_manifest_sha256=sources["baseline_manifest"][
                    "manifest_sha256"
                ],
                stage_a_manifest_sha256=stage_a_manifest["manifest_sha256"],
                source_slot=source_slot_map[slot_id],
            )
        )
    for source_row in sources["remaining"]:
        slot_id = source_row["source_slot_sense_id"]
        rows.append(
            _projection_row(
                source_row=source_row,
                source_partition="REMAINING_100",
                source_manifest_sha256=sources["remaining_manifest"][
                    "manifest_sha256"
                ],
                stage_a_manifest_sha256=stage_a_manifest["manifest_sha256"],
                source_slot=source_slot_map[slot_id],
            )
        )
    rows.sort(key=lambda row: row["candidate_id"])
    if len(rows) != 450 or len({row["candidate_id"] for row in rows}) != 450:
        raise ValueError("combined Stage B gold candidate population mismatch")
    if len({row["source_slot_sense_id"] for row in rows}) != 150:
        raise ValueError("combined Stage B gold source-slot population mismatch")
    if len({row["effective_sense_id"] for row in rows}) != 155:
        raise ValueError("combined Stage B gold effective-sense population mismatch")
    return rows


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        "tools/__init__.py",
        "tools/build_stage_b_150x450_gold.py",
        "tools/validate_stage_b_150x450_gold.py",
        "tests/test_stage_b_150x450_gold.py",
    ):
        source = namespace / relative
        if source.is_file():
            destination = staging / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def build_artifact(
    *,
    stage_a_complete_root: Path,
    baseline_gold_root: Path,
    remaining_gold_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    stage_a_complete_root = stage_a_complete_root.resolve(strict=True)
    baseline_gold_root = baseline_gold_root.resolve(strict=True)
    remaining_gold_root = remaining_gold_root.resolve(strict=True)
    sources = _load_sources(
        stage_a_complete_root=stage_a_complete_root,
        baseline_gold_root=baseline_gold_root,
        remaining_gold_root=remaining_gold_root,
    )
    rows = _project_rows(sources)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent)
    )
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        write_jsonl(staging / "stage_b_gold_450.jsonl", rows)
        partitions = staging / "partitions"
        partitions.mkdir()
        shutil.copy2(
            baseline_gold_root / "stage_b_gold_150.jsonl",
            partitions / "baseline_stage_b_gold_150.jsonl",
        )
        shutil.copy2(
            remaining_gold_root / "stage_b_gold_300.jsonl",
            partitions / "remaining_stage_b_gold_300.jsonl",
        )
        shutil.copy2(
            stage_a_complete_root / "stage_a_source_slot_index_150.jsonl",
            staging / "stage_a_source_slot_index_150.jsonl",
        )
        label_counts = Counter(row["final_gold_label"] for row in rows)
        resolution_counts = Counter(row["review_resolution"] for row in rows)
        summary = {
            "schema_id": "D2LStageB150x450GoldSummaryV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "release_status": RELEASE_STATUS,
            "source_slot_count": 150,
            "effective_sense_count": 155,
            "candidate_count": 450,
            "final_gold_label_count": 450,
            "final_gold_label_counts": dict(sorted(label_counts.items())),
            "resolution_counts": dict(sorted(resolution_counts.items())),
            "adjudication_count": resolution_counts.get(
                "REVIEWER_3_ADJUDICATED", 0
            ),
            "by_source_partition": _dimension_report(rows, "source_partition"),
            "by_split": _dimension_report(rows, "split"),
            "by_stratum": _dimension_report(rows, "stratum"),
            "c_e_evaluation_status": "READY_NOT_RUN",
            "global_validator_status": "NOT_RUN",
            "provider_call_count": 0,
            "final_glossary_decision_count": 0,
        }
        write_json(staging / "stage_b_gold_summary.json", summary)
        write_json(
            staging / "lineage.json",
            {
                "schema_id": "D2LStageB150x450GoldLineageV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "stage_a_complete_manifest_sha256": sources["stage_a_manifest"][
                    "manifest_sha256"
                ],
                "baseline_stage_b_gold_manifest_sha256": sources[
                    "baseline_manifest"
                ]["manifest_sha256"],
                "remaining_stage_b_gold_manifest_sha256": sources[
                    "remaining_manifest"
                ]["manifest_sha256"],
                "partition_file_sha256": {
                    "baseline_150": sha256_file(
                        partitions / "baseline_stage_b_gold_150.jsonl"
                    ),
                    "remaining_300": sha256_file(
                        partitions / "remaining_stage_b_gold_300.jsonl"
                    ),
                },
                "provider_call_count": 0,
                "final_glossary_decision_count": 0,
            },
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L Stage B full Dataset release\n\n"
            "- Source term-sense slots: 150/150.\n"
            "- Effective senses after approved splitting/replacement: 155.\n"
            "- Candidates with final Stage B labels: 450/450.\n"
            f"- Final labels: {dict(sorted(label_counts.items()))}.\n"
            f"- Resolution: {dict(sorted(resolution_counts.items()))}.\n"
            "- C/E evaluation is ready but has not run.\n"
            "- Global Validator has not run; final glossary decisions remain null.\n"
            "- Provider calls: 0.\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        manifest = {
            "schema_id": "D2LStageB150x450GoldManifestV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "artifact_name": ARTIFACT_NAME,
            "release_status": RELEASE_STATUS,
            "stage_a_complete_manifest_sha256": sources["stage_a_manifest"][
                "manifest_sha256"
            ],
            "baseline_stage_b_gold_manifest_sha256": sources["baseline_manifest"][
                "manifest_sha256"
            ],
            "remaining_stage_b_gold_manifest_sha256": sources[
                "remaining_manifest"
            ]["manifest_sha256"],
            "source_slot_count": 150,
            "effective_sense_count": 155,
            "candidate_count": 450,
            "final_gold_label_count": 450,
            "adjudication_count": resolution_counts.get(
                "REVIEWER_3_ADJUDICATED", 0
            ),
            "provider_call_count": 0,
            "final_glossary_decision_count": 0,
            "files": build_file_inventory(staging, {"manifest.json"}),
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        replace_directory(staging, output_root)
        release_zip = output_root.parent / f"{ARTIFACT_NAME}.zip"
        build_deterministic_zip(output_root, release_zip)
        release_zip.with_suffix(release_zip.suffix + ".sha256").write_text(
            f"{sha256_file(release_zip)} *{release_zip.name}\n",
            encoding="ascii",
            newline="\n",
        )
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-a-complete-root", required=True, type=Path)
    parser.add_argument("--baseline-gold-root", required=True, type=Path)
    parser.add_argument("--remaining-gold-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_artifact(
        stage_a_complete_root=args.stage_a_complete_root,
        baseline_gold_root=args.baseline_gold_root,
        remaining_gold_root=args.remaining_gold_root,
        output_root=args.output_root,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
