from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    replace_directory,
    seal_record,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    write_checksums,
    write_json,
    write_jsonl,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.remaining_stage_b_review_result import (
    ALLOWED_LABELS,
    EXPECTED_CASE_COUNT,
    MISSING_ALLOWED_SCOPE,
    ReviewIssue,
    ValidatedReview,
    validate_completed_review,
)


ARTIFACT_NAME = "d2l_dataset_remaining_300_candidates_stage_b_review_preflight_v1"
POLICY_ID = "d2l-remaining-300-candidates-stage-b-review-preflight-v1.0"
STATUS = "REVIEWER_1_REPAIR_AND_REVIEWER_3_ADJUDICATION_REQUIRED"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _validate_source_artifact(root: Path) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError("source artifact manifest self-hash mismatch")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise ValueError("source artifact manifest files are invalid")
    for relative, metadata in files.items():
        path = root / relative
        if (
            not isinstance(relative, str)
            or not isinstance(metadata, Mapping)
            or not path.is_file()
        ):
            raise ValueError(f"source artifact manifest entry is invalid: {relative}")
        if metadata.get("sha256") != sha256_file(path):
            raise ValueError(f"source artifact file hash mismatch: {relative}")
    return manifest


def _capture_stable(source: Path, destination: Path) -> str:
    source = source.resolve(strict=True)
    before = sha256_file(source)
    payload = source.read_bytes()
    captured = sha256_bytes(payload)
    after = sha256_file(source)
    if before != captured or after != before:
        raise ValueError(f"review source changed during capture: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    if sha256_file(destination) != before:
        raise ValueError(f"captured review hash mismatch: {source}")
    return before


def _cohen_kappa(pair_counts: Mapping[tuple[str, str], int], total: int) -> float:
    observed = (
        sum(count for (left, right), count in pair_counts.items() if left == right)
        / total
    )
    left_counts: Counter[str] = Counter()
    right_counts: Counter[str] = Counter()
    for (left, right), count in pair_counts.items():
        left_counts[left] += count
        right_counts[right] += count
    expected = (
        sum(left_counts[label] * right_counts[label] for label in ALLOWED_LABELS)
        / (total * total)
    )
    if expected == 1.0:
        return 1.0
    return round((observed - expected) / (1.0 - expected), 6)


def _issue_projection(issue: ReviewIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "reviewer_slot": issue.reviewer_slot,
        "case_index": issue.case_index,
        "candidate_id": issue.candidate_id,
        "message": issue.message,
    }


def _repair_case(
    candidate_id: str,
    case: Mapping[str, Any],
    issue: ReviewIssue,
) -> dict[str, Any]:
    return seal_record(
        {
            "schema_id": "D2LRemainingStageBReviewerRepairCaseV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "repair_case_id": "stageb300_repair_"
            + sha256_bytes(candidate_id.encode("utf-8"))[:24],
            "reviewer_slot": issue.reviewer_slot,
            "candidate_id": candidate_id,
            "source_case_id": case["case_id"],
            "source_case_sha256": case["case_sha256"],
            "source_payload": case["source_payload"],
            "source_payload_sha256": case["source_payload_sha256"],
            "original_review": case["review"],
            "repair_requirement": {
                "field": "allowed_scope",
                "reason": issue.message,
                "immutable_fields": [
                    "candidate_gold_label",
                    "validated_variants",
                    "rejected_variants",
                    "reason_codes",
                    "positive_context_refs",
                    "vietnamese_evidence_refs",
                    "review_notes",
                    "review_status",
                ],
            },
            "repair": {
                "allowed_scope": "",
                "repair_notes": "",
                "repair_status": "",
            },
            "provider_call_count": 0,
            "final_gold_label": None,
            "final_glossary_decision": None,
        },
        "repair_case_sha256",
    )


def _adjudication_case(pair: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = str(pair["candidate_id"])
    return seal_record(
        {
            "schema_id": "D2LRemainingStageBCandidateAdjudicationCaseV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "adjudication_case_id": "stageb300_adj_"
            + sha256_bytes(candidate_id.encode("utf-8"))[:24],
            "candidate_id": candidate_id,
            "effective_sense_id": pair["effective_sense_id"],
            "source_payload": pair["source_payload"],
            "source_payload_sha256": pair["source_payload_sha256"],
            "reviewer_1": pair["reviewer_1"],
            "reviewer_2": pair["reviewer_2"],
            "disagreement": {
                "field": "candidate_gold_label",
                "reviewer_1_label": pair["reviewer_1_label"],
                "reviewer_2_label": pair["reviewer_2_label"],
            },
            "adjudication": {
                "adjudicator_label": None,
                "adjudication_reason": "",
                "adjudication_status": "",
            },
            "provider_call_count": 0,
            "final_gold_label": None,
            "final_glossary_decision": None,
        },
        "adjudication_case_sha256",
    )


def _write_handoff(
    staging: Path,
    *,
    name: str,
    input_name: str,
    payload: Mapping[str, Any],
    instructions: str,
    message: str,
) -> tuple[str, str]:
    handoff = staging / ".handoff" / name
    handoff.mkdir(parents=True)
    write_json(handoff / input_name, payload)
    (handoff / "REVIEW_INSTRUCTIONS.md").write_text(
        instructions, encoding="utf-8", newline="\n"
    )
    (handoff / "MESSAGE.md").write_text(
        message, encoding="utf-8", newline="\n"
    )
    zip_path = staging / "handoff" / f"{name}.zip"
    build_deterministic_zip(handoff, zip_path)
    return zip_path.relative_to(staging).as_posix(), sha256_file(zip_path)


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        "tools/__init__.py",
        "tools/remaining_stage_b_review_result.py",
        "tools/build_remaining_stage_b_review_preflight.py",
        "tools/validate_remaining_stage_b_review_preflight.py",
        "tests/test_remaining_stage_b_review_preflight.py",
    ):
        source = namespace / relative
        if source.is_file():
            destination = staging / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _analyze_reviews(
    source_artifact_root: Path,
    reviewer_1_path: Path,
    reviewer_2_path: Path,
) -> dict[str, Any]:
    validated: dict[str, ValidatedReview] = {}
    issues_by_slot: dict[str, list[ReviewIssue]] = {}
    for slot, path in (
        ("reviewer_1", reviewer_1_path),
        ("reviewer_2", reviewer_2_path),
    ):
        result, issues = validate_completed_review(
            source_artifact_root / f"{slot}_full_input.json",
            path,
            expected_reviewer_slot=slot,
        )
        if result is None:
            raise ValueError(
                "; ".join(issue.message for issue in issues)
                or f"{slot}: validation failed"
            )
        validated[slot] = result
        issues_by_slot[slot] = issues

    repair_issues = issues_by_slot["reviewer_1"]
    if (
        len(repair_issues) != 1
        or repair_issues[0].code != MISSING_ALLOWED_SCOPE
        or not repair_issues[0].candidate_id
    ):
        raise ValueError(
            "reviewer_1 must have exactly one repairable missing allowed_scope issue; "
            + "; ".join(issue.message for issue in repair_issues)
        )
    if issues_by_slot["reviewer_2"]:
        raise ValueError(
            "reviewer_2 validation failed: "
            + "; ".join(issue.message for issue in issues_by_slot["reviewer_2"])
        )
    repair_candidate = str(repair_issues[0].candidate_id)
    candidate_ids = set(validated["reviewer_1"].cases_by_candidate)
    if candidate_ids != set(validated["reviewer_2"].cases_by_candidate):
        raise ValueError("reviewer candidate coverage differs")

    pairs: list[dict[str, Any]] = []
    pair_counts: Counter[tuple[str, str]] = Counter()
    for candidate_id in sorted(candidate_ids):
        case_1 = validated["reviewer_1"].cases_by_candidate[candidate_id]
        case_2 = validated["reviewer_2"].cases_by_candidate[candidate_id]
        if case_1["source_payload"] != case_2["source_payload"]:
            raise ValueError(f"reviewer source payload mismatch: {candidate_id}")
        label_1 = case_1["review"]["candidate_gold_label"]
        label_2 = case_2["review"]["candidate_gold_label"]
        agreement = label_1 == label_2
        repair_required = candidate_id == repair_candidate
        if repair_required and not agreement:
            raise ValueError("repair candidate also has a label disagreement")
        pair_counts[(label_1, label_2)] += 1
        source = case_1["source_payload"]
        pairs.append(
            seal_record(
                {
                    "schema_id": "D2LRemainingStageBCandidateReviewPairV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "candidate_id": candidate_id,
                    "effective_sense_id": source["effective_sense_id"],
                    "source_payload": source,
                    "source_payload_sha256": case_1["source_payload_sha256"],
                    "reviewer_1": {
                        "result_file_sha256": validated["reviewer_1"].sha256,
                        "source_case_id": case_1["case_id"],
                        "source_case_sha256": case_1["case_sha256"],
                        "review": case_1["review"],
                    },
                    "reviewer_2": {
                        "result_file_sha256": validated["reviewer_2"].sha256,
                        "source_case_id": case_2["case_id"],
                        "source_case_sha256": case_2["case_sha256"],
                        "review": case_2["review"],
                    },
                    "reviewer_1_label": label_1,
                    "reviewer_2_label": label_2,
                    "label_agreement": agreement,
                    "reviewer_repair_required": repair_required,
                    "consensus_label": (
                        label_1 if agreement and not repair_required else None
                    ),
                    "adjudication_required": not agreement,
                    "adjudication_label": None,
                    "final_gold_label": None,
                    "final_glossary_decision": None,
                    "provider_call_count": 0,
                },
                "review_pair_sha256",
            )
        )
    repair_case = _repair_case(
        repair_candidate,
        validated["reviewer_1"].cases_by_candidate[repair_candidate],
        repair_issues[0],
    )
    adjudication_cases = [
        _adjudication_case(pair)
        for pair in pairs
        if pair["adjudication_required"]
    ]
    agreement_count = sum(bool(row["label_agreement"]) for row in pairs)
    return {
        "validated": validated,
        "issues": issues_by_slot,
        "pairs": pairs,
        "pair_counts": pair_counts,
        "repair_cases": [repair_case],
        "adjudication_cases": adjudication_cases,
        "agreement_count": agreement_count,
        "disagreement_count": len(pairs) - agreement_count,
    }


def build_artifact(
    *,
    source_artifact_root: Path,
    reviewer_1_path: Path,
    reviewer_2_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    source_artifact_root = source_artifact_root.resolve(strict=True)
    source_manifest = _validate_source_artifact(source_artifact_root)
    resolved_inputs = [
        reviewer_1_path.resolve(strict=True),
        reviewer_2_path.resolve(strict=True),
    ]
    if len(set(resolved_inputs)) != 2:
        raise ValueError("reviewer result paths must be two distinct physical files")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent)
    )
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        captured = {
            "reviewer_1": staging / "raw_reviews" / "reviewer_1.json",
            "reviewer_2": staging / "raw_reviews" / "reviewer_2.json",
        }
        source_hashes = {
            "reviewer_1": _capture_stable(resolved_inputs[0], captured["reviewer_1"]),
            "reviewer_2": _capture_stable(resolved_inputs[1], captured["reviewer_2"]),
        }
        analysis = _analyze_reviews(
            source_artifact_root, captured["reviewer_1"], captured["reviewer_2"]
        )
        pairs = analysis["pairs"]
        repair_cases = analysis["repair_cases"]
        adjudication_cases = analysis["adjudication_cases"]
        pair_counts = analysis["pair_counts"]
        validated = analysis["validated"]
        agreement_count = analysis["agreement_count"]
        disagreement_count = analysis["disagreement_count"]

        write_jsonl(staging / "review_pairs_300.jsonl", pairs)
        write_jsonl(
            staging / "stage_b_gold_pending_300.jsonl",
            [
                seal_record(
                    {
                        "candidate_id": row["candidate_id"],
                        "effective_sense_id": row["effective_sense_id"],
                        "reviewer_1_label": row["reviewer_1_label"],
                        "reviewer_2_label": row["reviewer_2_label"],
                        "label_agreement": row["label_agreement"],
                        "reviewer_repair_required": row["reviewer_repair_required"],
                        "consensus_label": row["consensus_label"],
                        "adjudication_label": None,
                        "final_gold_label": None,
                        "gold_freeze_status": (
                            "PENDING_REVIEWER_1_REPAIR"
                            if row["reviewer_repair_required"]
                            else (
                                "PENDING_ADJUDICATION"
                                if row["adjudication_required"]
                                else "CONSENSUS_READY_NOT_FROZEN"
                            )
                        ),
                    },
                    "gold_pending_sha256",
                )
                for row in pairs
            ],
        )
        repair_binding = [
            {
                "repair_case_id": row["repair_case_id"],
                "repair_case_sha256": row["repair_case_sha256"],
            }
            for row in repair_cases
        ]
        repair_payload = {
            "schema_id": "D2LRemainingStageBReviewerRepairInputV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "reviewer_slot": "reviewer_1",
            "case_count": len(repair_cases),
            "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REPAIR_FIELDS_FILLED",
            "cases": repair_cases,
            "source_input_sha256": sha256_bytes(canonical_json_bytes(repair_binding)),
            "provider_call_count": 0,
            "final_gold_label_count": 0,
            "final_glossary_decision": None,
        }
        write_json(staging / "reviewer_1_repair_input.json", repair_payload)

        adjudication_binding = [
            {
                "adjudication_case_id": row["adjudication_case_id"],
                "adjudication_case_sha256": row["adjudication_case_sha256"],
            }
            for row in adjudication_cases
        ]
        adjudication_payload = {
            "schema_id": "D2LRemainingStageBCandidateAdjudicationInputV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "reviewer_slot": "reviewer_3_adjudicator",
            "case_count": len(adjudication_cases),
            "allowed_candidate_gold_labels": list(ALLOWED_LABELS),
            "return_contract": "RETURN_THIS_JSON_WITH_ONLY_ADJUDICATION_FIELDS_FILLED",
            "cases": adjudication_cases,
            "source_input_sha256": sha256_bytes(
                canonical_json_bytes(adjudication_binding)
            ),
            "provider_call_count": 0,
            "final_gold_label_count": 0,
            "final_glossary_decision": None,
        }
        write_json(staging / "reviewer_3_adjudication_input.json", adjudication_payload)

        repair_path, repair_sha = _write_handoff(
            staging,
            name="reviewer_1_repair",
            input_name="reviewer_1_repair_input.json",
            payload=repair_payload,
            instructions=(
                "# Reviewer 1 Stage B repair\n\n"
                "This pack contains exactly one previously reviewed case. Fill only "
                "the `repair` object. Keep the original SPLIT_REQUIRED label and every "
                "source/review field unchanged. Enter a nonblank `allowed_scope` that "
                "states the D2L scope affected by the split, optionally add repair_notes, "
                "and set repair_status=COMPLETE. Return the same JSON structure as "
                "reviewer_1_repair.json. Do not call a provider or assign final gold.\n"
            ),
            message=(
                "Open reviewer_1_repair_input.json, fill only `repair`, and return the "
                "completed file as reviewer_1_repair.json. Return the file only.\n"
            ),
        )
        adjudication_path, adjudication_sha = _write_handoff(
            staging,
            name="reviewer_3",
            input_name="reviewer_3_adjudication_input.json",
            payload=adjudication_payload,
            instructions=(
                "# Reviewer 3 Stage B adjudication\n\n"
                f"Review all {disagreement_count} candidate-label disagreements. You may inspect both "
                "reviewer records because this is adjudication, not blind review. Use "
                "only the supplied fixed sense, Vietnamese candidate, real D2L contexts, "
                "and reviewer rationales. Fill only each `adjudication` object. Choose "
                "one adjudicator_label from ACCEPT, CONDITIONAL, REJECT, SPLIT_REQUIRED, "
                "HUMAN_UNJUDGEABLE; provide a nonblank adjudication_reason; set "
                "adjudication_status=COMPLETE. Preserve source bytes, hashes, order, and "
                "reviewer records. Do not assign final glossary decisions or call a provider.\n"
            ),
            message=(
                "Complete every case in reviewer_3_adjudication_input.json and return "
                "the same structure as reviewer_3.json. Fill only `adjudication`; return "
                "the file only, without raw prose.\n"
            ),
        )

        report = {
            "schema_id": "D2LRemainingStageBAgreementReportV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "status": STATUS,
            "case_count": EXPECTED_CASE_COUNT,
            "reviewer_1_label_counts": validated["reviewer_1"].label_counts,
            "reviewer_2_label_counts": validated["reviewer_2"].label_counts,
            "agreement_count": agreement_count,
            "disagreement_count": disagreement_count,
            "raw_agreement": round(agreement_count / EXPECTED_CASE_COUNT, 6),
            "cohen_kappa": _cohen_kappa(pair_counts, EXPECTED_CASE_COUNT),
            "adjudication_rate": round(
                disagreement_count / EXPECTED_CASE_COUNT, 6
            ),
            "reviewer_1_repair_case_count": len(repair_cases),
            "label_pair_counts": {
                f"{left}__{right}": count
                for (left, right), count in sorted(pair_counts.items())
            },
            "final_gold_label_count": 0,
            "provider_call_count": 0,
            "final_glossary_decision": None,
        }
        write_json(staging / "agreement_report.json", report)
        write_json(
            staging / "validation_report.json",
            {
                "schema_id": "D2LRemainingStageBReviewPreflightReportV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "reviewer_1_source_sha256": source_hashes["reviewer_1"],
                "reviewer_2_source_sha256": source_hashes["reviewer_2"],
                "reviewer_1_valid_case_count": 299,
                "reviewer_1_repair_issues": [
                    _issue_projection(issue)
                    for issue in analysis["issues"]["reviewer_1"]
                ],
                "reviewer_2_valid_case_count": 300,
                "reviewer_2_issues": [],
                "agreement_count": agreement_count,
                "adjudication_case_count": disagreement_count,
                "stage_b_gold_autofill_count": 0,
                "provider_call_count": 0,
                "final_glossary_decision": None,
            },
        )
        write_json(
            staging / "lineage.json",
            {
                "schema_id": "D2LRemainingStageBReviewPreflightLineageV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "source_artifact_name": source_manifest.get("artifact_name"),
                "source_artifact_manifest_sha256": source_manifest.get(
                    "manifest_sha256"
                ),
                "review_result_sha256": source_hashes,
                "review_result_paths_distinct": True,
                "reviewer_slots_distinct": True,
                "provider_call_count": 0,
                "final_glossary_decision": None,
            },
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L remaining Stage B review preflight\n\n"
            "- Reviewer 1: 299 valid cases; 1 missing allowed_scope repair.\n"
            "- Reviewer 2: 300 valid cases.\n"
            f"- Candidate-label agreements: {agreement_count}/300.\n"
            f"- Disagreements routed to Reviewer 3: {disagreement_count}/300.\n"
            f"- Raw agreement: {report['raw_agreement']:.2%}.\n"
            f"- Cohen's kappa: {report['cohen_kappa']}.\n"
            "- Final gold labels remain null. Provider calls: 0.\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        shutil.rmtree(staging / ".handoff")
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        manifest = {
            "schema_id": "D2LRemainingStageBReviewPreflightManifestV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "artifact_name": ARTIFACT_NAME,
            "status": STATUS,
            "source_artifact_manifest_sha256": source_manifest.get(
                "manifest_sha256"
            ),
            "case_count": EXPECTED_CASE_COUNT,
            "agreement_count": agreement_count,
            "disagreement_count": disagreement_count,
            "reviewer_1_repair_case_count": len(repair_cases),
            "reviewer_1_repair_handoff_path": repair_path,
            "reviewer_1_repair_handoff_sha256": repair_sha,
            "reviewer_3_handoff_path": adjudication_path,
            "reviewer_3_handoff_sha256": adjudication_sha,
            "provider_call_count": 0,
            "final_gold_label_count": 0,
            "final_glossary_decision": None,
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
    parser.add_argument("--source-artifact-root", required=True, type=Path)
    parser.add_argument("--reviewer-1", required=True, type=Path)
    parser.add_argument("--reviewer-2", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_artifact(
        source_artifact_root=args.source_artifact_root,
        reviewer_1_path=args.reviewer_1,
        reviewer_2_path=args.reviewer_2,
        output_root=args.output_root,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
