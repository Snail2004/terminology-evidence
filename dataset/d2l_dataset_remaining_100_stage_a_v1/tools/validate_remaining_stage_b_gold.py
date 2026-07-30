from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_file_inventory,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_record,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_gold import (
    ARTIFACT_NAME,
    POLICY_ID,
    RELEASE_STATUS,
    _manifest_self_hash,
    _source_maps,
    _validate_manifest,
    _validate_pair_source,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.remaining_stage_b_adjudication_result import (
    validate_completed_adjudication,
)


def _validate_checksums(root: Path, errors: list[str]) -> None:
    expected: dict[str, str] = {}
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(str(exc))
        return
    for line in lines:
        if " *" not in line:
            errors.append("malformed checksum row")
            continue
        digest, relative = line.split(" *", 1)
        if relative in expected:
            errors.append(f"duplicate checksum path: {relative}")
        expected[relative] = digest
    actual = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256", "manifest.json"}
        ).items()
    }
    if expected != actual:
        errors.append("checksum inventory does not match artifact files")


def _scan_guards(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == "provider_call_count" and child != 0:
                errors.append(f"nonzero provider call count: {child_path}")
            if key == "final_glossary_decision" and child is not None:
                errors.append(f"non-null final glossary decision: {child_path}")
            if key == "final_glossary_decision_count" and child != 0:
                errors.append(f"nonzero final glossary decision count: {child_path}")
            _scan_guards(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_guards(child, f"{path}[{index}]", errors)


def validate_artifact(
    root: Path,
    *,
    dataset_artifact_root: Path,
    review_intake_root: Path,
) -> list[str]:
    root = root.resolve()
    dataset_artifact_root = dataset_artifact_root.resolve()
    review_intake_root = review_intake_root.resolve()
    errors: list[str] = []
    try:
        dataset_manifest = _validate_manifest(
            dataset_artifact_root,
            "d2l_dataset_remaining_300_candidates_stage_b_review_v1",
        )
        intake_manifest = _validate_manifest(
            review_intake_root, "d2l_stage_b_r1_repair_v1"
        )
        manifest = strict_json_object(root / "manifest.json")
        if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
            errors.append("manifest self-hash mismatch")
        if (
            manifest.get("artifact_name") != ARTIFACT_NAME
            or manifest.get("policy_id") != POLICY_ID
            or manifest.get("release_status") != RELEASE_STATUS
            or manifest.get("dataset_manifest_sha256")
            != dataset_manifest.get("manifest_sha256")
            or manifest.get("review_intake_manifest_sha256")
            != intake_manifest.get("manifest_sha256")
        ):
            errors.append("manifest identity/lineage mismatch")
        if manifest.get("files") != build_file_inventory(root, {"manifest.json"}):
            errors.append("manifest file inventory mismatch")
        _validate_checksums(root, errors)

        reviewer_3_path = root / "raw_reviews" / "reviewer_3.json"
        adjudication, adjudication_errors = validate_completed_adjudication(
            review_intake_root / "reviewer_3_adjudication_input.json",
            reviewer_3_path,
        )
        if adjudication_errors or adjudication is None:
            errors.extend(adjudication_errors)
            return errors
        if manifest.get("reviewer_3_result_sha256") != sha256_file(reviewer_3_path):
            errors.append("Reviewer 3 manifest hash mismatch")
        for slot in ("reviewer_1", "reviewer_2"):
            if sha256_file(root / "raw_reviews" / f"{slot}.json") != sha256_file(
                review_intake_root / "repaired_reviews" / f"{slot}.json"
            ):
                errors.append(f"{slot} raw review changed")

        pairs = strict_jsonl(review_intake_root / "review_pairs_300.jsonl")
        packaged_pairs = strict_jsonl(root / "review_pairs_300.jsonl")
        if packaged_pairs != pairs:
            errors.append("packaged review pairs changed")
        if len(pairs) != 300 or any(
            not verify_record(row, "review_pair_sha256") for row in pairs
        ):
            errors.append("review pair source is invalid")
        pair_by_candidate = {row["candidate_id"]: row for row in pairs}
        senses, candidates = _source_maps(dataset_artifact_root)
        gold = strict_jsonl(root / "stage_b_gold_300.jsonl")
        if len(gold) != 300 or any(
            not verify_record(row, "stage_b_gold_sha256") for row in gold
        ):
            errors.append("Stage B gold count/self-hash mismatch")
        if len({row.get("candidate_id") for row in gold}) != 300:
            errors.append("Stage B gold candidate IDs are invalid or duplicated")
        used_adjudication: set[str] = set()
        for row in gold:
            candidate_id = row.get("candidate_id")
            pair = pair_by_candidate.get(candidate_id)
            if pair is None:
                errors.append(f"gold row has unknown candidate: {candidate_id}")
                continue
            sense, candidate = _validate_pair_source(pair, senses, candidates)
            if pair["label_agreement"]:
                expected_label = pair["consensus_label"]
                expected_resolution = "DUAL_REVIEW_CONSENSUS"
                expected_adjudication_label = None
                expected_case_sha = None
            else:
                case = adjudication.cases_by_candidate.get(str(candidate_id))
                if case is None:
                    errors.append(f"missing adjudication for gold row: {candidate_id}")
                    continue
                expected_label = case["adjudication"]["adjudicator_label"]
                expected_resolution = "REVIEWER_3_ADJUDICATED"
                expected_adjudication_label = expected_label
                expected_case_sha = case["adjudication_case_sha256"]
                used_adjudication.add(str(candidate_id))
            expected = {
                "dataset_manifest_sha256": dataset_manifest["manifest_sha256"],
                "review_intake_manifest_sha256": intake_manifest["manifest_sha256"],
                "reviewer_3_result_sha256": adjudication.sha256,
                "candidate_version": candidate["candidate_version"],
                "candidate_target_vi": candidate["candidate_target_vi"],
                "candidate_instance_sha256": candidate["candidate_instance_sha256"],
                "effective_sense_id": sense["effective_sense_id"],
                "source_slot_sense_id": sense["source_slot_sense_id"],
                "source_term": sense["source_term"],
                "scope_id": sense["scope_id"],
                "split": sense["split"],
                "stratum": sense["stratum"],
                "kind": sense["kind"],
                "stage_a_authority_sha256": sense["stage_a_authority_sha256"],
                "effective_sense_record_sha256": sense["record_sha256"],
                "review_pair_sha256": pair["review_pair_sha256"],
                "reviewer_1_label": pair["reviewer_1_label"],
                "reviewer_2_label": pair["reviewer_2_label"],
                "label_agreement": pair["label_agreement"],
                "adjudication_label": expected_adjudication_label,
                "adjudication_case_sha256": expected_case_sha,
                "review_resolution": expected_resolution,
                "final_gold_label": expected_label,
                "gold_freeze_status": "COMPLETE",
                "provider_call_count": 0,
                "final_glossary_decision": None,
            }
            for key, value in expected.items():
                if row.get(key) != value:
                    errors.append(f"gold row mismatch: {candidate_id}/{key}")
        if used_adjudication != set(adjudication.cases_by_candidate):
            errors.append("adjudication coverage differs from gold disagreements")
        if {row["candidate_id"] for row in gold} != set(candidates):
            errors.append("gold candidate coverage differs from source inventory")

        summary = strict_json_object(root / "stage_b_gold_summary.json")
        label_counts = dict(sorted(Counter(row["final_gold_label"] for row in gold).items()))
        resolution_counts = dict(
            sorted(Counter(row["review_resolution"] for row in gold).items())
        )
        if (
            summary.get("release_status") != RELEASE_STATUS
            or summary.get("source_slot_count") != 100
            or summary.get("effective_sense_count") != 105
            or summary.get("candidate_count") != 300
            or summary.get("final_gold_label_count") != 300
            or summary.get("final_gold_label_counts") != label_counts
            or summary.get("resolution_counts") != resolution_counts
            or summary.get("adjudication_count") != 55
            or summary.get("adjudication_label_counts")
            != adjudication.label_counts
        ):
            errors.append("Stage B gold summary mismatch")
        for name, value in (
            ("manifest", manifest),
            ("gold", gold),
            ("summary", summary),
        ):
            _scan_guards(value, name, errors)
    except (KeyError, OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--dataset-artifact-root", required=True, type=Path)
    parser.add_argument("--review-intake-root", required=True, type=Path)
    args = parser.parse_args()
    errors = validate_artifact(
        args.artifact_root,
        dataset_artifact_root=args.dataset_artifact_root,
        review_intake_root=args.review_intake_root,
    )
    print(
        json.dumps(
            {"status": "PASS" if not errors else "FAIL", "errors": errors},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
