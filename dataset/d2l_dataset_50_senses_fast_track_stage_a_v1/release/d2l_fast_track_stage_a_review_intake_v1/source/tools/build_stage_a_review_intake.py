from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from .review_result import (
        ValidatedResult,
        review_disagreement_fields,
        validate_completed_result,
    )
    from .spec import CREATED_AT_DEFAULT, POLICY_ID, REVIEW_FIELDS, stable_id
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from review_result import (  # type: ignore
        ValidatedResult,
        review_disagreement_fields,
        validate_completed_result,
    )
    from spec import CREATED_AT_DEFAULT, POLICY_ID, REVIEW_FIELDS, stable_id  # type: ignore


INTAKE_ARTIFACT_NAME = "d2l_fast_track_stage_a_review_intake_v1"
INTAKE_POLICY_ID = "d2l-fast-track-stage-a-review-intake-v1.0"
INTAKE_STATUS = "READY_FOR_REVIEWER_3_ADJUDICATION"
EXPECTED_REVIEW_COUNTS = {"reviewer_1": 44, "reviewer_2": 31}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _expected_result_name(batch_id: str, reviewer_slot: str) -> str:
    return f"{batch_id}_{reviewer_slot}_completed.json"


def _adjudication_blank() -> dict[str, Any]:
    result: dict[str, Any] = {field: "" for field in REVIEW_FIELDS}
    result["invalid_evidence_context_ids"] = []
    result["candidate_replacements"] = []
    result["proposed_split_labels"] = []
    result["adjudication_rationale"] = ""
    result["adjudication_status"] = ""
    return result


def _capture_and_validate_results(
    *,
    canonical_root: Path,
    reviewer_1_root: Path,
    reviewer_2_root: Path,
    capture_root: Path,
) -> tuple[dict[str, dict[str, ValidatedResult]], dict[str, Any]]:
    roots = {
        "reviewer_1": reviewer_1_root.resolve(strict=True),
        "reviewer_2": reviewer_2_root.resolve(strict=True),
    }
    if any(path.is_symlink() for path in roots.values()):
        raise ValueError("review result root must not be a symlink")
    expected_names = {
        slot: {
            _expected_result_name(f"batch_{sequence:03d}", slot)
            for sequence in range(1, 10)
        }
        for slot in roots
    }
    resolved_paths: set[Path] = set()
    validated: dict[str, dict[str, ValidatedResult]] = defaultdict(dict)
    inventory_rows: list[dict[str, Any]] = []
    metric_totals = Counter()
    ignored_entries: list[str] = []
    for slot, source_root in roots.items():
        for entry in source_root.iterdir():
            if entry.name not in expected_names[slot]:
                ignored_entries.append(f"{slot}/{entry.name}")
        for sequence in range(1, 10):
            batch_id = f"batch_{sequence:03d}"
            name = _expected_result_name(batch_id, slot)
            source_path = source_root / name
            if not source_path.is_file() or source_path.is_symlink():
                raise ValueError(f"missing or unsafe reviewer result: {slot}/{name}")
            resolved = source_path.resolve(strict=True)
            if resolved in resolved_paths:
                raise ValueError(f"reviewer result physical path reused: {source_path}")
            resolved_paths.add(resolved)
            before_sha = sha256_file(source_path)
            destination = capture_root / slot / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination)
            captured_sha = sha256_file(destination)
            after_sha = sha256_file(source_path)
            if before_sha != captured_sha or before_sha != after_sha:
                raise ValueError(f"reviewer result drift during capture: {slot}/{name}")
            canonical_input = (
                canonical_root / "batches" / batch_id / f"{slot}_input.json"
            )
            result, errors, metrics = validate_completed_result(
                canonical_input,
                destination,
                expected_batch_id=batch_id,
                expected_reviewer_slot=slot,
            )
            if errors or result is None:
                raise ValueError(
                    f"reviewer result validation failed for {slot}/{name}: "
                    + "; ".join(errors)
                )
            validated[slot][batch_id] = result
            metric_totals.update(metrics)
            inventory_rows.append(
                {
                    "reviewer_slot": slot,
                    "batch_id": batch_id,
                    "source_path": str(source_path.resolve()),
                    "source_sha256": before_sha,
                    "captured_relative_path": destination.relative_to(
                        capture_root.parent
                    ).as_posix(),
                    "captured_sha256": captured_sha,
                    "case_count": metrics["case_count"],
                }
            )
    actual_counts = {
        slot: sum(
            len(result.payload["cases"]) for result in batch_results.values()
        )
        for slot, batch_results in validated.items()
    }
    if actual_counts != EXPECTED_REVIEW_COUNTS:
        raise ValueError(f"completed review counts mismatch: {actual_counts}")
    inventory = seal_integrity(
        {
            "schema_id": "D2LFastTrackStageAReviewInputInventoryV1",
            "schema_version": "1.0.0",
            "policy_id": INTAKE_POLICY_ID,
            "result_file_count": len(inventory_rows),
            "review_counts": actual_counts,
            "metrics": dict(sorted(metric_totals.items())),
            "ignored_unconsumed_entries": sorted(ignored_entries),
            "files": sorted(
                inventory_rows,
                key=lambda row: (row["reviewer_slot"], row["batch_id"]),
            ),
        }
    )
    return dict(validated), inventory


def _index_cases(
    results: Mapping[str, Mapping[str, ValidatedResult]]
) -> dict[str, dict[str, dict[str, Any]]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for slot, batches in results.items():
        for batch_id, result in batches.items():
            for case in result.payload["cases"]:
                sense_id = case["source_payload"]["sense_id"]
                if sense_id in indexed[slot]:
                    raise ValueError(f"duplicate reviewed sense for {slot}: {sense_id}")
                indexed[slot][sense_id] = {
                    "batch_id": batch_id,
                    "result_sha256": result.sha256,
                    "case": case,
                }
    return dict(indexed)


def _build_routes(
    indexed: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    reviewer_1 = indexed["reviewer_1"]
    reviewer_2 = indexed["reviewer_2"]
    adjudication: list[dict[str, Any]] = []
    r0_repair: list[dict[str, Any]] = []
    counts = Counter()
    for sense_id, reviewer_1_entry in reviewer_1.items():
        case_1 = reviewer_1_entry["case"]
        source = case_1["source_payload"]
        risk = source["risk_class"]
        review_1 = case_1["review"]
        if risk == "R0_CLEAR":
            if review_1["sense_status"] == "READY_FOR_CONTRACT_CONSTRUCTION":
                counts["r0_ready"] += 1
            else:
                counts["r0_repair_required"] += 1
                r0_repair.append(
                    seal_record(
                        {
                            "schema_id": "D2LFastTrackStageAR0RepairQueueRecordV1",
                            "schema_version": "1.0.0",
                            "policy_id": INTAKE_POLICY_ID,
                            "batch_id": reviewer_1_entry["batch_id"],
                            "sense_id": sense_id,
                            "source_payload": source,
                            "source_payload_sha256": case_1["source_payload_sha256"],
                            "reviewer_1_review": review_1,
                            "reviewer_1_result_sha256": reviewer_1_entry[
                                "result_sha256"
                            ],
                            "route": "DATASET_REPAIR_THEN_REAUDIT",
                            "provider_call_count": 0,
                            "final_glossary_decision": None,
                        },
                        "repair_queue_record_sha256",
                    )
                )
            continue
        reviewer_2_entry = reviewer_2.get(sense_id)
        if reviewer_2_entry is None:
            raise ValueError(f"missing Reviewer 2 result for {risk}: {sense_id}")
        case_2 = reviewer_2_entry["case"]
        if case_2["source_payload"] != source:
            raise ValueError(f"reviewer source mismatch: {sense_id}")
        review_2 = case_2["review"]
        disagreement_fields = review_disagreement_fields(review_1, review_2)
        if risk == "R3_AMBIGUOUS" and not disagreement_fields:
            counts["r3_agreement"] += 1
            continue
        if risk == "R3_AMBIGUOUS":
            route = "R3_REVIEWER_DISAGREEMENT"
            counts["r3_disagreement"] += 1
        elif risk == "R4_SPLIT_OR_POS_RISK":
            route = "R4_MANDATORY_ADJUDICATION"
            counts["r4_mandatory"] += 1
            if disagreement_fields:
                counts["r4_with_disagreement"] += 1
            else:
                counts["r4_with_agreement"] += 1
        else:
            raise ValueError(f"unsupported review risk class: {risk}")
        adjudication.append(
            seal_record(
                {
                    "schema_id": "D2LFastTrackStageAAdjudicationCaseV1",
                    "schema_version": "1.0.0",
                    "policy_id": INTAKE_POLICY_ID,
                    "adjudication_case_id": stable_id(
                        "adj_", sense_id, reviewer_1_entry["batch_id"], "v1"
                    ),
                    "batch_id": reviewer_1_entry["batch_id"],
                    "sense_id": sense_id,
                    "source_term": source["source_term"],
                    "risk_class": risk,
                    "routing_reason": route,
                    "disagreement_fields": disagreement_fields,
                    "source_payload": source,
                    "source_payload_sha256": case_1["source_payload_sha256"],
                    "reviewer_1": {
                        "review": review_1,
                        "result_file_sha256": reviewer_1_entry["result_sha256"],
                    },
                    "reviewer_2": {
                        "review": review_2,
                        "result_file_sha256": reviewer_2_entry["result_sha256"],
                    },
                    "adjudication": _adjudication_blank(),
                    "provider_call_count": 0,
                    "stage_b_gold_label": None,
                    "final_glossary_decision": None,
                },
                "adjudication_case_sha256",
            )
        )
    adjudication.sort(key=lambda row: (row["batch_id"], row["source_term"].casefold()))
    r0_repair.sort(key=lambda row: (row["batch_id"], row["source_payload"]["source_term"].casefold()))
    if len(adjudication) != 24 or len(r0_repair) != 4:
        raise ValueError(
            f"review route count mismatch: adjudication={len(adjudication)}, "
            f"r0_repair={len(r0_repair)}"
        )
    summary = {
        "r0_ready": counts["r0_ready"],
        "r0_repair_required": counts["r0_repair_required"],
        "r3_agreement": counts["r3_agreement"],
        "r3_disagreement": counts["r3_disagreement"],
        "r4_mandatory": counts["r4_mandatory"],
        "r4_with_agreement": counts["r4_with_agreement"],
        "r4_with_disagreement": counts["r4_with_disagreement"],
        "reviewer_3_adjudication_cases": len(adjudication),
    }
    expected = {
        "r0_ready": 9,
        "r0_repair_required": 4,
        "r3_agreement": 7,
        "r3_disagreement": 8,
        "r4_mandatory": 16,
        "r4_with_agreement": 5,
        "r4_with_disagreement": 11,
        "reviewer_3_adjudication_cases": 24,
    }
    if summary != expected:
        raise ValueError(f"review comparison result drift: {summary}")
    return adjudication, r0_repair, summary


def _write_handoff_zip(
    staging: Path, batch_id: str, cases: list[Mapping[str, Any]]
) -> tuple[str, str]:
    handoff_root = staging / ".handoff" / batch_id
    handoff_root.mkdir(parents=True)
    payload = {
        "schema_id": "D2LFastTrackStageAAdjudicatorInputV1",
        "schema_version": "1.0.0",
        "policy_id": INTAKE_POLICY_ID,
        "batch_id": batch_id,
        "reviewer_slot": "reviewer_3_adjudicator",
        "independence_mode": "ADJUDICATION_SEES_REVIEWER_1_AND_REVIEWER_2",
        "return_contract": "RETURN_THIS_JSON_WITH_ONLY_ADJUDICATION_FIELDS_FILLED",
        "case_count": len(cases),
        "cases": cases,
        "source_input_sha256": sha256_bytes(
            canonical_json_bytes(
                [
                    {
                        "adjudication_case_id": row["adjudication_case_id"],
                        "adjudication_case_sha256": row[
                            "adjudication_case_sha256"
                        ],
                    }
                    for row in cases
                ]
            )
        ),
    }
    write_json(handoff_root / "reviewer_3_input.json", payload)
    (handoff_root / "MESSAGE.md").write_text(
        f"Adjudicate Stage A {batch_id}. Read REVIEW_INSTRUCTIONS.md, fill only "
        "the adjudication object in every case, preserve all source and reviewer "
        "fields, and return only the completed reviewer_3_input.json file.\n",
        encoding="utf-8",
        newline="\n",
    )
    (handoff_root / "REVIEW_INSTRUCTIONS.md").write_text(
        "# Reviewer 3 adjudication instructions\n\n"
        "Resolve each case from the D2L evidence and the two independent reviews. "
        "R4 cases require a decision even when the reviewers agree. Fill only "
        "`adjudication`; preserve every other byte-level field. For candidate "
        "replacements, return objects with exactly `candidate_id`, "
        "`candidate_slot`, and `replacement_target_vi`; do not return unbound "
        "strings. Set review_status and adjudication_status to COMPLETE. Do not "
        "create Stage B gold or a final glossary decision.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_checksums(handoff_root, handoff_root / "CHECKSUMS.sha256")
    relative = f"handoff/{batch_id}_reviewer_3_adjudication.zip"
    zip_path = staging / relative
    build_deterministic_zip(handoff_root, zip_path)
    return relative, sha256_file(zip_path)


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    files = (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/review_result.py",
        "tools/build_stage_a_review_intake.py",
        "tools/validate_stage_a_review_intake.py",
        "tests/test_stage_a_review_intake.py",
    )
    for relative in files:
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"source bundle file is missing: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def build_review_intake(
    *,
    canonical_root: Path,
    reviewer_1_root: Path,
    reviewer_2_root: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    canonical_root = canonical_root.resolve(strict=True)
    canonical_manifest = strict_json_object(canonical_root / "manifest.json")
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{INTAKE_ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / INTAKE_ARTIFACT_NAME
    staging.mkdir()
    try:
        results, inventory = _capture_and_validate_results(
            canonical_root=canonical_root,
            reviewer_1_root=reviewer_1_root,
            reviewer_2_root=reviewer_2_root,
            capture_root=staging / "raw_reviews",
        )
        indexed = _index_cases(results)
        adjudication, r0_repair, comparison = _build_routes(indexed)
        write_json(staging / "input_inventory.json", inventory)
        write_jsonl(staging / "adjudication_cases_24.jsonl", adjudication)
        write_jsonl(staging / "r0_repair_queue_4.jsonl", r0_repair)
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in adjudication:
            grouped[row["batch_id"]].append(row)
        handoffs = []
        for sequence in range(1, 10):
            batch_id = f"batch_{sequence:03d}"
            relative, digest = _write_handoff_zip(staging, batch_id, grouped[batch_id])
            handoffs.append(
                {
                    "batch_id": batch_id,
                    "case_count": len(grouped[batch_id]),
                    "zip_path": relative,
                    "zip_sha256": digest,
                }
            )
        report = seal_integrity(
            {
                "schema_id": "D2LFastTrackStageAReviewComparisonReportV1",
                "schema_version": "1.0.0",
                "policy_id": INTAKE_POLICY_ID,
                "status": INTAKE_STATUS,
                "created_at": created_at,
                "canonical_stage_a_manifest_sha256": canonical_manifest[
                    "manifest_sha256"
                ],
                "validated_result_files": 18,
                "completed_review_decisions": 75,
                "comparison": comparison,
                "candidate_replacement_binding": {
                    "legacy_unbound_text_cases": inventory["metrics"][
                        "legacy_unbound_replacement_case_count"
                    ],
                    "candidate_bound_object_cases": inventory["metrics"][
                        "candidate_bound_replacement_case_count"
                    ],
                    "resolution": "REVIEWER_3_MUST_RETURN_CANDIDATE_BOUND_OBJECTS",
                },
                "reviewer_3_handoffs": handoffs,
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            }
        )
        write_json(staging / "comparison_report.json", report)
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L Fast-Track Stage A review intake\n\n"
            "- 18/18 completed result files validated against canonical inputs.\n"
            "- 75/75 assigned Stage A review decisions complete.\n"
            "- 24 cases routed to Reviewer 3: 16 mandatory R4 and 8 R3 disagreements.\n"
            "- 4 R0 cases routed to dataset repair and re-audit; 9 R0 cases are ready.\n"
            "- Raw reviewer decisions remain unchanged; no Stage B gold or final glossary decision exists.\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        shutil.rmtree(staging / ".handoff")
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LFastTrackStageAReviewIntakeManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": INTAKE_ARTIFACT_NAME,
            "policy_id": INTAKE_POLICY_ID,
            "status": INTAKE_STATUS,
            "created_at": created_at,
            "canonical_stage_a_manifest_sha256": canonical_manifest[
                "manifest_sha256"
            ],
            "review_result_file_count": 18,
            "completed_review_decision_count": 75,
            "adjudication_case_count": 24,
            "r0_repair_queue_count": 4,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        try:
            from .validate_stage_a_review_intake import validate_intake
        except ImportError:  # pragma: no cover
            from validate_stage_a_review_intake import validate_intake  # type: ignore
        errors = validate_intake(staging, canonical_root=canonical_root)
        if errors:
            raise ValueError("internal intake validation failed: " + "; ".join(errors))
        zip_name = f"{INTAKE_ARTIFACT_NAME}_release.zip"
        temporary_zip = temporary / zip_name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temporary_zip, final_zip)
        zip_sha = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_sha} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": INTAKE_STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "release_zip": str(final_zip),
            "release_zip_sha256": zip_sha,
            "comparison": comparison,
            "reviewer_3_handoffs": handoffs,
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    namespace = Path(__file__).resolve().parents[1]
    canonical_default = namespace / "release" / "d2l_dataset_50_senses_fast_track_stage_a_v1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-root", type=Path, default=canonical_default)
    parser.add_argument(
        "--reviewer-1-root",
        type=Path,
        default=canonical_default / "handoff" / "result-reviewer1",
    )
    parser.add_argument(
        "--reviewer-2-root",
        type=Path,
        default=canonical_default / "handoff" / "result-reviewer2",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default=CREATED_AT_DEFAULT)
    args = parser.parse_args()
    result = build_review_intake(
        canonical_root=args.canonical_root,
        reviewer_1_root=args.reviewer_1_root,
        reviewer_2_root=args.reviewer_2_root,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
