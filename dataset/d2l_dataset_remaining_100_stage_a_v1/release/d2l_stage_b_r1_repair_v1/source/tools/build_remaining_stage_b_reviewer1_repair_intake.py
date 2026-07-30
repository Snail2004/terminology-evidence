from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

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
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_review_preflight import (
    _capture_stable,
    _cohen_kappa,
    _manifest_self_hash,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.remaining_stage_b_review_result import (
    EXPECTED_CASE_COUNT,
    ValidatedReview,
    validate_completed_review,
)


ARTIFACT_NAME = "d2l_stage_b_r1_repair_v1"
POLICY_ID = "d2l-remaining-300-stage-b-reviewer1-repair-intake-v1.0"
STATUS = "REVIEWER_1_REPAIR_APPLIED_REVIEWER_3_ADJUDICATION_PENDING"


def _validate_parent(root: Path) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError("parent manifest self-hash mismatch")
    if (
        manifest.get("artifact_name")
        != "d2l_dataset_remaining_300_candidates_stage_b_review_preflight_v1"
        or manifest.get("case_count") != EXPECTED_CASE_COUNT
        or manifest.get("disagreement_count") != 55
        or manifest.get("reviewer_1_repair_case_count") != 1
    ):
        raise ValueError("parent artifact identity/count mismatch")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise ValueError("parent manifest file inventory is invalid")
    for relative, metadata in files.items():
        path = root / relative
        if (
            not isinstance(relative, str)
            or not isinstance(metadata, Mapping)
            or not path.is_file()
            or metadata.get("sha256") != sha256_file(path)
        ):
            raise ValueError(f"parent file hash mismatch: {relative}")
    return manifest


def _validate_repair_response(
    canonical_path: Path, response_path: Path
) -> dict[str, Any]:
    canonical = strict_json_object(canonical_path)
    response = strict_json_object(response_path)
    if set(canonical) != set(response):
        raise ValueError("repair response top-level keys changed")
    for key, value in canonical.items():
        if key != "cases" and response.get(key) != value:
            raise ValueError(f"repair immutable top-level field changed: {key}")
    source_cases = canonical.get("cases")
    result_cases = response.get("cases")
    if (
        not isinstance(source_cases, list)
        or not isinstance(result_cases, list)
        or len(source_cases) != 1
        or len(result_cases) != 1
    ):
        raise ValueError("repair response must contain exactly one case")
    source_case = source_cases[0]
    result_case = result_cases[0]
    if not isinstance(source_case, Mapping) or not isinstance(result_case, Mapping):
        raise ValueError("repair case must be an object")
    if set(source_case) != set(result_case):
        raise ValueError("repair case keys changed")
    for key, value in source_case.items():
        if key != "repair" and result_case.get(key) != value:
            raise ValueError(f"repair immutable case field changed: {key}")
    repair = result_case.get("repair")
    if not isinstance(repair, Mapping) or set(repair) != {
        "allowed_scope",
        "repair_notes",
        "repair_status",
    }:
        raise ValueError("repair fields do not match the contract")
    if not isinstance(repair.get("allowed_scope"), str) or not repair[
        "allowed_scope"
    ].strip():
        raise ValueError("repair allowed_scope must be nonblank")
    if not isinstance(repair.get("repair_notes"), str):
        raise ValueError("repair_notes must be a string")
    if repair.get("repair_status") != "COMPLETE":
        raise ValueError("repair_status must be COMPLETE")
    if (
        response.get("provider_call_count") != 0
        or response.get("final_gold_label_count") != 0
        or response.get("final_glossary_decision") is not None
    ):
        raise ValueError("repair response changed zero-provider/final guards")
    return response


def _apply_repair(
    original_review_path: Path,
    repair_response: Mapping[str, Any],
    destination: Path,
) -> str:
    payload = strict_json_object(original_review_path)
    repair_case = repair_response["cases"][0]
    candidate_id = repair_case["candidate_id"]
    matches = [
        case
        for case in payload.get("cases", [])
        if case.get("source_payload", {}).get("candidate_id") == candidate_id
    ]
    if len(matches) != 1:
        raise ValueError("repair candidate does not resolve to exactly one review case")
    case = matches[0]
    if (
        case.get("case_id") != repair_case.get("source_case_id")
        or case.get("case_sha256") != repair_case.get("source_case_sha256")
        or case.get("source_payload") != repair_case.get("source_payload")
        or case.get("source_payload_sha256")
        != repair_case.get("source_payload_sha256")
        or case.get("review") != repair_case.get("original_review")
    ):
        raise ValueError("repair case does not bind the original review record")
    review = dict(case["review"])
    if review.get("candidate_gold_label") != "SPLIT_REQUIRED":
        raise ValueError("repair target is not the expected SPLIT_REQUIRED review")
    review["allowed_scope"] = repair_case["repair"]["allowed_scope"].strip()
    case["review"] = review
    write_json(destination, payload)
    return str(candidate_id)


def _validated_reviews(
    source_artifact_root: Path,
    reviewer_1_path: Path,
    reviewer_2_path: Path,
) -> dict[str, ValidatedReview]:
    validated: dict[str, ValidatedReview] = {}
    for slot, path in (
        ("reviewer_1", reviewer_1_path),
        ("reviewer_2", reviewer_2_path),
    ):
        result, issues = validate_completed_review(
            source_artifact_root / f"{slot}_full_input.json",
            path,
            expected_reviewer_slot=slot,
        )
        if result is None or issues:
            raise ValueError(
                f"{slot} validation failed: "
                + "; ".join(issue.message for issue in issues)
            )
        validated[slot] = result
    if set(validated["reviewer_1"].cases_by_candidate) != set(
        validated["reviewer_2"].cases_by_candidate
    ):
        raise ValueError("reviewer candidate coverage differs")
    return validated


def _build_pairs(validated: Mapping[str, ValidatedReview]) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    pair_counts: Counter[tuple[str, str]] = Counter()
    candidate_ids = sorted(validated["reviewer_1"].cases_by_candidate)
    for candidate_id in candidate_ids:
        case_1 = validated["reviewer_1"].cases_by_candidate[candidate_id]
        case_2 = validated["reviewer_2"].cases_by_candidate[candidate_id]
        if case_1["source_payload"] != case_2["source_payload"]:
            raise ValueError(f"reviewer source payload mismatch: {candidate_id}")
        label_1 = case_1["review"]["candidate_gold_label"]
        label_2 = case_2["review"]["candidate_gold_label"]
        agreement = label_1 == label_2
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
                    "reviewer_repair_required": False,
                    "consensus_label": label_1 if agreement else None,
                    "adjudication_required": not agreement,
                    "adjudication_label": None,
                    "final_gold_label": None,
                    "final_glossary_decision": None,
                    "provider_call_count": 0,
                },
                "review_pair_sha256",
            )
        )
    agreement_count = sum(bool(row["label_agreement"]) for row in pairs)
    return {
        "pairs": pairs,
        "pair_counts": pair_counts,
        "agreement_count": agreement_count,
        "disagreement_count": len(pairs) - agreement_count,
    }


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        "tools/__init__.py",
        "tools/remaining_stage_b_review_result.py",
        "tools/build_remaining_stage_b_reviewer1_repair_intake.py",
        "tools/validate_remaining_stage_b_reviewer1_repair_intake.py",
        "tests/test_remaining_stage_b_reviewer1_repair_intake.py",
    ):
        source = namespace / relative
        if source.is_file():
            destination = staging / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def build_artifact(
    *,
    parent_artifact_root: Path,
    source_artifact_root: Path,
    repair_response_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    parent_artifact_root = parent_artifact_root.resolve(strict=True)
    source_artifact_root = source_artifact_root.resolve(strict=True)
    parent_manifest = _validate_parent(parent_artifact_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent)
    )
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        captured_repair = staging / "raw_repair" / "reviewer_1_repair.json"
        repair_sha = _capture_stable(repair_response_path, captured_repair)
        repair = _validate_repair_response(
            parent_artifact_root / "reviewer_1_repair_input.json",
            captured_repair,
        )
        repaired_reviewer_1 = staging / "repaired_reviews" / "reviewer_1.json"
        repaired_reviewer_1.parent.mkdir(parents=True)
        repaired_candidate_id = _apply_repair(
            parent_artifact_root / "raw_reviews" / "reviewer_1.json",
            repair,
            repaired_reviewer_1,
        )
        reviewer_2 = staging / "repaired_reviews" / "reviewer_2.json"
        shutil.copy2(parent_artifact_root / "raw_reviews" / "reviewer_2.json", reviewer_2)
        validated = _validated_reviews(
            source_artifact_root, repaired_reviewer_1, reviewer_2
        )
        analysis = _build_pairs(validated)
        if (
            analysis["agreement_count"] != 245
            or analysis["disagreement_count"] != 55
        ):
            raise ValueError("repair unexpectedly changed label agreement counts")
        pairs = analysis["pairs"]
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
                        "consensus_label": row["consensus_label"],
                        "adjudication_label": None,
                        "final_gold_label": None,
                        "gold_freeze_status": (
                            "PENDING_ADJUDICATION"
                            if row["adjudication_required"]
                            else "CONSENSUS_READY_NOT_FROZEN"
                        ),
                    },
                    "gold_pending_sha256",
                )
                for row in pairs
            ],
        )
        agreement_report = {
            "schema_id": "D2LRemainingStageBAgreementReportV1",
            "schema_version": "1.1.0",
            "policy_id": POLICY_ID,
            "status": STATUS,
            "case_count": EXPECTED_CASE_COUNT,
            "reviewer_1_label_counts": validated["reviewer_1"].label_counts,
            "reviewer_2_label_counts": validated["reviewer_2"].label_counts,
            "agreement_count": analysis["agreement_count"],
            "disagreement_count": analysis["disagreement_count"],
            "raw_agreement": round(
                analysis["agreement_count"] / EXPECTED_CASE_COUNT, 6
            ),
            "cohen_kappa": _cohen_kappa(
                analysis["pair_counts"], EXPECTED_CASE_COUNT
            ),
            "reviewer_1_repair_case_count": 0,
            "label_pair_counts": {
                f"{left}__{right}": count
                for (left, right), count in sorted(analysis["pair_counts"].items())
            },
            "final_gold_label_count": 0,
            "provider_call_count": 0,
            "final_glossary_decision": None,
        }
        write_json(staging / "agreement_report.json", agreement_report)

        parent_adjudication = parent_artifact_root / "reviewer_3_adjudication_input.json"
        child_adjudication = staging / "reviewer_3_adjudication_input.json"
        shutil.copy2(parent_adjudication, child_adjudication)
        parent_handoff = parent_artifact_root / "handoff" / "reviewer_3.zip"
        child_handoff = staging / "handoff" / "reviewer_3.zip"
        child_handoff.parent.mkdir(parents=True)
        shutil.copy2(parent_handoff, child_handoff)
        if (
            sha256_file(parent_adjudication) != sha256_file(child_adjudication)
            or sha256_file(parent_handoff) != sha256_file(child_handoff)
        ):
            raise ValueError("Reviewer 3 handoff changed during child projection")

        write_json(
            staging / "validation_report.json",
            {
                "schema_id": "D2LRemainingStageBReviewer1RepairIntakeReportV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "repair_response_sha256": repair_sha,
                "repaired_candidate_id": repaired_candidate_id,
                "repaired_field": "allowed_scope",
                "reviewer_1_valid_case_count": 300,
                "reviewer_2_valid_case_count": 300,
                "agreement_count": 245,
                "adjudication_case_count": 55,
                "reviewer_3_handoff_preserved": True,
                "stage_b_gold_autofill_count": 0,
                "provider_call_count": 0,
                "final_glossary_decision": None,
            },
        )
        write_json(
            staging / "lineage.json",
            {
                "schema_id": "D2LRemainingStageBReviewer1RepairLineageV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "parent_artifact_name": parent_manifest["artifact_name"],
                "parent_manifest_sha256": parent_manifest["manifest_sha256"],
                "repair_response_sha256": repair_sha,
                "original_reviewer_1_sha256": sha256_file(
                    parent_artifact_root / "raw_reviews" / "reviewer_1.json"
                ),
                "repaired_reviewer_1_sha256": sha256_file(repaired_reviewer_1),
                "reviewer_2_sha256": sha256_file(reviewer_2),
                "reviewer_3_input_sha256": sha256_file(child_adjudication),
                "reviewer_3_handoff_sha256": sha256_file(child_handoff),
                "provider_call_count": 0,
                "final_glossary_decision": None,
            },
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L remaining Stage B Reviewer 1 repair intake\n\n"
            "- Reviewer 1 repair: PASS, one allowed_scope applied.\n"
            "- Reviewer 1 and Reviewer 2: 300/300 structurally valid.\n"
            "- Candidate-label agreements: 245/300.\n"
            "- Reviewer 3 adjudication pending: 55/300.\n"
            "- Reviewer 3 input and ZIP are byte-identical to the parent handoff.\n"
            "- Final gold labels: 0; provider calls: 0.\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        manifest = {
            "schema_id": "D2LRemainingStageBReviewer1RepairIntakeManifestV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "artifact_name": ARTIFACT_NAME,
            "status": STATUS,
            "parent_manifest_sha256": parent_manifest["manifest_sha256"],
            "repair_response_sha256": repair_sha,
            "repaired_candidate_id": repaired_candidate_id,
            "case_count": EXPECTED_CASE_COUNT,
            "agreement_count": 245,
            "disagreement_count": 55,
            "reviewer_3_handoff_path": "handoff/reviewer_3.zip",
            "reviewer_3_handoff_sha256": sha256_file(child_handoff),
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
    parser.add_argument("--parent-artifact-root", required=True, type=Path)
    parser.add_argument("--source-artifact-root", required=True, type=Path)
    parser.add_argument("--repair-response", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_artifact(
        parent_artifact_root=args.parent_artifact_root,
        source_artifact_root=args.source_artifact_root,
        repair_response_path=args.repair_response,
        output_root=args.output_root,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
