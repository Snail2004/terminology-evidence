from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
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
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.review_result import (
    ValidatedResult,
    review_disagreement_fields,
    validate_completed_result,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.spec import (
    REVIEW_FIELDS,
    stable_id,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.reviewer2_repair import (
    apply_repair_response,
    preflight_review_results,
    validate_repair_response,
)


ARTIFACT_NAME = "d2l_dataset_remaining_100_stage_a_review_intake_v1"
POLICY_ID = "d2l-remaining-100-stage-a-review-intake-v1.0"
STATUS = "READY_FOR_REVIEWER_3_ADJUDICATION_AND_R0_FOLLOWUP"
EXPECTED_COUNTS = {
    "r0_pending_blind_audit": 25,
    "r0_repair_required": 10,
    "r3_dual_agreement": 20,
    "r3_reviewer_disagreement": 11,
    "r4_mandatory_adjudication": 34,
    "r4_with_agreement": 16,
    "r4_with_disagreement": 18,
    "reviewer_3_adjudication_cases": 45,
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _adjudication_blank() -> dict[str, Any]:
    result: dict[str, Any] = {field: "" for field in REVIEW_FIELDS}
    result["invalid_evidence_context_ids"] = []
    result["candidate_replacements"] = []
    result["proposed_split_labels"] = []
    result["adjudication_rationale"] = ""
    result["adjudication_status"] = ""
    return result


def _capture_file(source: Path, destination: Path) -> dict[str, Any]:
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"missing or unsafe intake file: {source}")
    before_sha = sha256_file(source)
    before_size = source.stat().st_size
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    captured_sha = sha256_file(destination)
    after_sha = sha256_file(source)
    if before_sha != captured_sha or before_sha != after_sha:
        raise ValueError(f"input drift during capture: {source}")
    return {
        "source_file_name": source.name,
        "size_bytes": before_size,
        "source_sha256": before_sha,
        "captured_relative_path": destination.as_posix(),
        "captured_sha256": captured_sha,
    }


def _batch_ids(canonical_root: Path) -> list[str]:
    index = strict_json_object(canonical_root / "batch_index.json")
    return [row["batch_id"] for row in index["batches"]]


def _capture_inputs(
    *,
    canonical_root: Path,
    reviewer_1_root: Path,
    reviewer_2_root: Path,
    repair_source_root: Path,
    repair_response_path: Path,
    staging: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    batch_ids = _batch_ids(canonical_root)
    rows: list[dict[str, Any]] = []
    captured_roots: dict[str, Path] = {}
    for slot, source_root in (
        ("reviewer_1", reviewer_1_root.resolve(strict=True)),
        ("reviewer_2", reviewer_2_root.resolve(strict=True)),
    ):
        if source_root.is_symlink():
            raise ValueError(f"{slot} root must not be a symlink")
        expected = {
            f"{batch_id}_{slot}_completed.json" for batch_id in batch_ids
        }
        actual = {path.name for path in source_root.iterdir() if path.is_file()}
        if actual != expected:
            raise ValueError(
                f"{slot} file set mismatch: missing={sorted(expected-actual)}, "
                f"extra={sorted(actual-expected)}"
            )
        captured_root = staging / "raw_reviews" / slot
        captured_roots[slot] = captured_root
        for batch_id in batch_ids:
            name = f"{batch_id}_{slot}_completed.json"
            source = source_root / name
            destination = captured_root / name
            metadata = _capture_file(source, destination)
            metadata.update({"input_role": slot, "batch_id": batch_id})
            metadata["captured_relative_path"] = destination.relative_to(
                staging
            ).as_posix()
            rows.append(metadata)

    repair_input_source = repair_source_root / "reviewer_2_repair_input.json"
    preflight_source = repair_source_root / "preflight_report.json"
    repair_input = staging / "repair" / "reviewer_2_repair_input.json"
    preflight = staging / "repair" / "preflight_report.json"
    response = staging / "repair" / "reviewer_2_repair_response.json"
    for role, source, destination in (
        ("repair_input", repair_input_source, repair_input),
        ("repair_preflight", preflight_source, preflight),
        ("repair_response", repair_response_path, response),
    ):
        metadata = _capture_file(source.resolve(strict=True), destination)
        metadata.update({"input_role": role, "batch_id": None})
        metadata["source_file_name"] = destination.name
        metadata["captured_relative_path"] = destination.relative_to(staging).as_posix()
        rows.append(metadata)

    _, repair_errors = validate_repair_response(repair_input, response)
    if repair_errors:
        raise ValueError("repair response is invalid: " + "; ".join(repair_errors))
    raw_preflight, repair_cases = preflight_review_results(
        canonical_root,
        captured_roots["reviewer_1"],
        captured_roots["reviewer_2"],
    )
    packaged_preflight = strict_json_object(preflight)
    if raw_preflight != packaged_preflight or len(repair_cases) != 6:
        raise ValueError("captured raw reviews do not match the sealed repair preflight")

    corrected_root = staging / "corrected_reviews" / "reviewer_2"
    apply_repair_response(
        canonical_root=canonical_root,
        reviewer_2_root=captured_roots["reviewer_2"],
        repair_input_path=repair_input,
        response_path=response,
        output_root=corrected_root,
    )
    inventory = seal_integrity(
        {
            "schema_id": "D2LRemaining100StageAIntakeInventoryV1",
            "schema_version": "1.0",
            "policy_id": POLICY_ID,
            "input_file_count": len(rows),
            "raw_review_file_count": 20,
            "repair_case_count": len(repair_cases),
            "files": sorted(
                rows,
                key=lambda row: (
                    row["input_role"],
                    row["batch_id"] or "",
                    row["source_file_name"],
                ),
            ),
        }
    )
    return captured_roots["reviewer_1"], corrected_root, inventory


def _validate_and_index(
    canonical_root: Path,
    reviewer_1_root: Path,
    reviewer_2_root: Path,
) -> dict[str, dict[str, dict[str, Any]]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    totals = Counter()
    for slot, root in (
        ("reviewer_1", reviewer_1_root),
        ("reviewer_2", reviewer_2_root),
    ):
        for batch_id in _batch_ids(canonical_root):
            path = root / f"{batch_id}_{slot}_completed.json"
            result, errors, metrics = validate_completed_result(
                canonical_root / "batches" / batch_id / f"{slot}_input.json",
                path,
                expected_batch_id=batch_id,
                expected_reviewer_slot=slot,
            )
            if errors or result is None:
                raise ValueError(
                    f"corrected review validation failed for {slot}/{batch_id}: "
                    + "; ".join(errors)
                )
            totals[slot] += metrics["case_count"]
            for case in result.payload["cases"]:
                sense_id = case["source_payload"]["sense_id"]
                if sense_id in indexed[slot]:
                    raise ValueError(f"duplicate reviewed sense: {slot}/{sense_id}")
                indexed[slot][sense_id] = {
                    "batch_id": batch_id,
                    "result_sha256": result.sha256,
                    "case": case,
                }
    if totals != {"reviewer_1": 100, "reviewer_2": 65}:
        raise ValueError(f"review totals mismatch: {dict(totals)}")
    return dict(indexed)


def _route_record(
    *,
    sense_id: str,
    entry: Mapping[str, Any],
    route: str,
    disagreement_fields: list[str],
) -> dict[str, Any]:
    source = entry["case"]["source_payload"]
    return seal_record(
        {
            "schema_id": "D2LRemaining100StageARouteRecordV1",
            "schema_version": "1.0",
            "policy_id": POLICY_ID,
            "batch_id": entry["batch_id"],
            "sense_id": sense_id,
            "source_term": source["source_term"],
            "risk_class": source["risk_class"],
            "route": route,
            "disagreement_fields": disagreement_fields,
            "provider_call_count": 0,
            "stage_b_gold_label": None,
            "final_glossary_decision": None,
        },
        "route_record_sha256",
    )


def _build_routes(
    indexed: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    outputs: dict[str, list[dict[str, Any]]] = {
        "route_index": [],
        "adjudication": [],
        "r0_repair": [],
        "r0_blind_audit": [],
        "r3_agreement": [],
    }
    counts = Counter()
    for sense_id, entry_1 in indexed["reviewer_1"].items():
        case_1 = entry_1["case"]
        source = case_1["source_payload"]
        review_1 = case_1["review"]
        risk = source["risk_class"]
        disagreement_fields: list[str] = []
        if risk == "R0_CLEAR":
            if review_1["sense_status"] == "READY_FOR_CONTRACT_CONSTRUCTION":
                route = "R0_PENDING_BLIND_AUDIT"
                counts["r0_pending_blind_audit"] += 1
                outputs["r0_blind_audit"].append(
                    seal_record(
                        {
                            "schema_id": "D2LRemaining100StageAR0BlindAuditPoolRecordV1",
                            "schema_version": "1.0",
                            "policy_id": POLICY_ID,
                            "batch_id": entry_1["batch_id"],
                            "sense_id": sense_id,
                            "source_payload": source,
                            "source_payload_sha256": case_1["source_payload_sha256"],
                            "reviewer_1_review": review_1,
                            "reviewer_1_result_sha256": entry_1["result_sha256"],
                            "route": route,
                            "provider_call_count": 0,
                            "final_glossary_decision": None,
                        },
                        "blind_audit_pool_record_sha256",
                    )
                )
            else:
                route = "R0_REPAIR_REQUIRED"
                counts["r0_repair_required"] += 1
                outputs["r0_repair"].append(
                    seal_record(
                        {
                            "schema_id": "D2LRemaining100StageAR0RepairQueueRecordV1",
                            "schema_version": "1.0",
                            "policy_id": POLICY_ID,
                            "batch_id": entry_1["batch_id"],
                            "sense_id": sense_id,
                            "source_payload": source,
                            "source_payload_sha256": case_1["source_payload_sha256"],
                            "reviewer_1_review": review_1,
                            "reviewer_1_result_sha256": entry_1["result_sha256"],
                            "route": "DATASET_REPAIR_THEN_BLIND_REAUDIT",
                            "provider_call_count": 0,
                            "final_glossary_decision": None,
                        },
                        "repair_queue_record_sha256",
                    )
                )
        else:
            entry_2 = indexed["reviewer_2"].get(sense_id)
            if entry_2 is None:
                raise ValueError(f"missing Reviewer 2 result: {sense_id}")
            case_2 = entry_2["case"]
            if case_2["source_payload"] != source:
                raise ValueError(f"reviewer source mismatch: {sense_id}")
            review_2 = case_2["review"]
            disagreement_fields = review_disagreement_fields(review_1, review_2)
            if risk == "R3_AMBIGUOUS" and not disagreement_fields:
                route = "R3_DUAL_AGREEMENT"
                counts["r3_dual_agreement"] += 1
                outputs["r3_agreement"].append(
                    seal_record(
                        {
                            "schema_id": "D2LRemaining100StageAR3AgreementRecordV1",
                            "schema_version": "1.0",
                            "policy_id": POLICY_ID,
                            "batch_id": entry_1["batch_id"],
                            "sense_id": sense_id,
                            "source_payload": source,
                            "source_payload_sha256": case_1["source_payload_sha256"],
                            "reviewer_1_review": review_1,
                            "reviewer_2_review": review_2,
                            "route": route,
                            "provider_call_count": 0,
                            "final_glossary_decision": None,
                        },
                        "agreement_record_sha256",
                    )
                )
            elif risk == "R3_AMBIGUOUS":
                route = "R3_REVIEWER_DISAGREEMENT"
                counts["r3_reviewer_disagreement"] += 1
            elif risk == "R4_SPLIT_OR_POS_RISK":
                route = "R4_MANDATORY_ADJUDICATION"
                counts["r4_mandatory_adjudication"] += 1
                if disagreement_fields:
                    counts["r4_with_disagreement"] += 1
                else:
                    counts["r4_with_agreement"] += 1
            else:
                raise ValueError(f"unsupported risk class: {risk}")

            if route in {
                "R3_REVIEWER_DISAGREEMENT",
                "R4_MANDATORY_ADJUDICATION",
            }:
                outputs["adjudication"].append(
                    seal_record(
                        {
                            "schema_id": "D2LRemaining100StageAAdjudicationCaseV1",
                            "schema_version": "1.0",
                            "policy_id": POLICY_ID,
                            "adjudication_case_id": stable_id(
                                "adj100_", sense_id, entry_1["batch_id"], "v1"
                            ),
                            "batch_id": entry_1["batch_id"],
                            "sense_id": sense_id,
                            "source_term": source["source_term"],
                            "risk_class": risk,
                            "routing_reason": route,
                            "disagreement_fields": disagreement_fields,
                            "source_payload": source,
                            "source_payload_sha256": case_1["source_payload_sha256"],
                            "reviewer_1": {
                                "review": review_1,
                                "result_file_sha256": entry_1["result_sha256"],
                            },
                            "reviewer_2": {
                                "review": review_2,
                                "result_file_sha256": entry_2["result_sha256"],
                            },
                            "adjudication": _adjudication_blank(),
                            "provider_call_count": 0,
                            "stage_b_gold_label": None,
                            "final_glossary_decision": None,
                        },
                        "adjudication_case_sha256",
                    )
                )
        outputs["route_index"].append(
            _route_record(
                sense_id=sense_id,
                entry=entry_1,
                route=route,
                disagreement_fields=disagreement_fields,
            )
        )

    for rows in outputs.values():
        rows.sort(
            key=lambda row: (
                row["batch_id"],
                str(row.get("source_term") or row.get("source_payload", {}).get("source_term", "")).casefold(),
            )
        )
    counts["reviewer_3_adjudication_cases"] = len(outputs["adjudication"])
    summary = {key: counts[key] for key in EXPECTED_COUNTS}
    if summary != EXPECTED_COUNTS:
        raise ValueError(f"review routing drift: {summary}")
    if len(outputs["route_index"]) != 100:
        raise ValueError("route index must contain exactly 100 senses")
    return outputs, summary


def _write_handoff_zip(
    staging: Path,
    batch_id: str,
    cases: list[Mapping[str, Any]],
) -> tuple[str, str]:
    handoff_root = staging / ".handoff" / batch_id
    handoff_root.mkdir(parents=True)
    payload = {
        "schema_id": "D2LRemaining100StageAAdjudicatorInputV1",
        "schema_version": "1.0",
        "policy_id": POLICY_ID,
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
                        "adjudication_case_sha256": row["adjudication_case_sha256"],
                    }
                    for row in cases
                ]
            )
        ),
        "provider_call_count": 0,
        "stage_b_gold_autofill_count": 0,
        "final_glossary_decision": None,
    }
    write_json(handoff_root / "reviewer_3_input.json", payload)
    (handoff_root / "REVIEW_INSTRUCTIONS.md").write_text(
        "# Reviewer 3 Stage A adjudication\n\n"
        "Resolve every supplied case using the D2L evidence and both independent "
        "reviews. Every R4 case requires adjudication even when Reviewers 1 and 2 "
        "agree. Fill only `adjudication`, preserve all other fields, set "
        "`review_status` and `adjudication_status` to `COMPLETE`, and return only "
        "`reviewer_3_input.json`. Candidate replacements must be objects bound to "
        "the supplied candidate ID and slot. Do not create Stage B gold or a final "
        "glossary decision.\n",
        encoding="utf-8",
        newline="\n",
    )
    (handoff_root / "MESSAGE.md").write_text(
        f"Adjudicate all cases in {batch_id}. Return only the completed "
        "reviewer_3_input.json and do not alter source or reviewer fields.\n",
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
    for relative in (
        "README.md",
        "tools/reviewer2_repair.py",
        "tools/review_intake.py",
        "tools/validate_review_intake.py",
        "tests/test_review_intake.py",
    ):
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"source bundle file missing: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def build_review_intake(
    *,
    canonical_root: Path,
    reviewer_1_root: Path,
    reviewer_2_root: Path,
    repair_source_root: Path,
    repair_response_path: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    canonical_root = canonical_root.resolve(strict=True)
    canonical_manifest = strict_json_object(canonical_root / "manifest.json")
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent)
    )
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        reviewer_1_captured, reviewer_2_corrected, inventory = _capture_inputs(
            canonical_root=canonical_root,
            reviewer_1_root=reviewer_1_root,
            reviewer_2_root=reviewer_2_root,
            repair_source_root=repair_source_root,
            repair_response_path=repair_response_path,
            staging=staging,
        )
        indexed = _validate_and_index(
            canonical_root, reviewer_1_captured, reviewer_2_corrected
        )
        routes, comparison = _build_routes(indexed)
        write_json(staging / "input_inventory.json", inventory)
        write_jsonl(staging / "route_index_100.jsonl", routes["route_index"])
        write_jsonl(staging / "adjudication_cases_45.jsonl", routes["adjudication"])
        write_jsonl(staging / "r0_repair_queue_10.jsonl", routes["r0_repair"])
        write_jsonl(
            staging / "r0_blind_audit_pool_25.jsonl", routes["r0_blind_audit"]
        )
        write_jsonl(
            staging / "r3_dual_agreement_20.jsonl", routes["r3_agreement"]
        )

        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in routes["adjudication"]:
            grouped[row["batch_id"]].append(row)
        handoffs: list[dict[str, Any]] = []
        for batch_id in _batch_ids(canonical_root):
            if not grouped[batch_id]:
                continue
            relative, digest = _write_handoff_zip(
                staging, batch_id, grouped[batch_id]
            )
            handoffs.append(
                {
                    "batch_id": batch_id,
                    "case_count": len(grouped[batch_id]),
                    "zip_path": relative,
                    "zip_sha256": digest,
                }
            )
        write_json(
            staging / "reviewer_3_batch_index.json",
            {
                "schema_id": "D2LRemaining100StageAReviewer3BatchIndexV1",
                "policy_id": POLICY_ID,
                "batch_count": len(handoffs),
                "case_count": len(routes["adjudication"]),
                "batches": handoffs,
            },
        )
        report = seal_integrity(
            {
                "schema_id": "D2LRemaining100StageAComparisonReportV1",
                "schema_version": "1.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "created_at": created_at,
                "canonical_stage_a_manifest_sha256": canonical_manifest[
                    "manifest_sha256"
                ],
                "validated_raw_review_files": 20,
                "completed_review_decisions": 165,
                "reviewer_2_repair_case_count": 6,
                "comparison": comparison,
                "reviewer_3_handoffs": handoffs,
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            }
        )
        write_json(staging / "comparison_report.json", report)
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L remaining-100 Stage A review intake\n\n"
            "- Reviewer 1: 100/100 decisions validated.\n"
            "- Reviewer 2: 65/65 decisions validated after the sealed six-case correction.\n"
            "- Reviewer 3: 45 cases (34 mandatory R4 and 11 R3 disagreements).\n"
            "- R0 follow-up: 25 pending blind audit and 10 requiring dataset repair.\n"
            "- R3 dual agreement: 20 cases.\n"
            "- No Stage B gold, provider call, or final glossary decision is present.\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        shutil.rmtree(staging / ".handoff")
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LRemaining100StageAReviewIntakeManifestV1",
            "schema_version": "1.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "status": STATUS,
            "created_at": created_at,
            "canonical_stage_a_manifest_sha256": canonical_manifest[
                "manifest_sha256"
            ],
            "review_result_file_count": 20,
            "completed_review_decision_count": 165,
            "reviewer_2_repair_case_count": 6,
            "adjudication_case_count": 45,
            "r0_repair_queue_count": 10,
            "r0_blind_audit_pool_count": 25,
            "r3_dual_agreement_count": 20,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_review_intake import (
            validate_intake,
        )

        errors = validate_intake(staging, canonical_root=canonical_root)
        if errors:
            raise ValueError("internal intake validation failed: " + "; ".join(errors))
        zip_name = f"{ARTIFACT_NAME}_reviewer_handoff.zip"
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
            "status": STATUS,
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-root", type=Path, required=True)
    parser.add_argument("--reviewer-1-root", type=Path, required=True)
    parser.add_argument("--reviewer-2-root", type=Path, required=True)
    parser.add_argument("--repair-source-root", type=Path, required=True)
    parser.add_argument("--repair-response", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default="2026-07-30T00:00:00Z")
    args = parser.parse_args()
    result = build_review_intake(
        canonical_root=args.canonical_root,
        reviewer_1_root=args.reviewer_1_root,
        reviewer_2_root=args.reviewer_2_root,
        repair_source_root=args.repair_source_root,
        repair_response_path=args.repair_response,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
