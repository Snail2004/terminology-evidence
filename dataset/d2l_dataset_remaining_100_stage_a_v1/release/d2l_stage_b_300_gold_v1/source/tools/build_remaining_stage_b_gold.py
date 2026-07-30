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
    canonical_json_bytes,
    replace_directory,
    seal_record,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_record,
    write_checksums,
    write_json,
    write_jsonl,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_review_preflight import (
    _capture_stable,
    _manifest_self_hash,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.remaining_stage_b_adjudication_result import (
    validate_completed_adjudication,
)


ARTIFACT_NAME = "d2l_stage_b_300_gold_v1"
POLICY_ID = "d2l-remaining-300-candidates-stage-b-gold-v1.0"
RELEASE_STATUS = "STAGE_B_300_GOLD_COMPLETE_READY_FOR_C_E_EVALUATION"


def _validate_manifest(root: Path, expected_name: str) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError(f"manifest self-hash mismatch: {root}")
    if manifest.get("artifact_name") != expected_name:
        raise ValueError(f"artifact identity mismatch: {root}")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise ValueError(f"manifest file inventory is invalid: {root}")
    for relative, metadata in files.items():
        relative_path = Path(str(relative))
        if relative_path.is_absolute() or ".." in relative_path.parts or "\\" in str(
            relative
        ):
            raise ValueError(f"unsafe manifest path: {relative}")
        path = root / relative_path
        if (
            not isinstance(metadata, Mapping)
            or not path.is_file()
            or metadata.get("sha256") != sha256_file(path)
        ):
            raise ValueError(f"manifest file hash mismatch: {relative}")
    return manifest


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


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        "tools/__init__.py",
        "tools/remaining_stage_b_adjudication_result.py",
        "tools/build_remaining_stage_b_gold.py",
        "tools/validate_remaining_stage_b_gold.py",
        "tests/test_remaining_stage_b_gold.py",
    ):
        source = namespace / relative
        if source.is_file():
            destination = staging / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _source_maps(
    dataset_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    senses = {
        row["effective_sense_id"]: row
        for row in strict_jsonl(dataset_root / "effective_senses_105.jsonl")
    }
    candidates = {
        row["candidate_id"]: row
        for row in strict_jsonl(dataset_root / "candidate_instances_300.jsonl")
    }
    if len(senses) != 105 or len(candidates) != 300:
        raise ValueError("source sense/candidate counts are invalid")
    if any(not verify_record(row, "record_sha256") for row in senses.values()):
        raise ValueError("source effective-sense record hash mismatch")
    listed_candidates = {
        candidate_id for row in senses.values() for candidate_id in row["candidate_ids"]
    }
    if listed_candidates != set(candidates):
        raise ValueError("effective-sense candidate inventory mismatch")
    return senses, candidates


def _validate_pair_source(
    pair: Mapping[str, Any],
    senses: Mapping[str, Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    candidate_id = pair["candidate_id"]
    candidate = candidates.get(candidate_id)
    if candidate is None:
        raise ValueError(f"unknown candidate in review pair: {candidate_id}")
    source = pair["source_payload"]
    sense_id = source["effective_sense_id"]
    sense = senses.get(sense_id)
    if sense is None:
        raise ValueError(f"unknown effective sense in review pair: {sense_id}")
    for key in (
        "candidate_id",
        "candidate_target_vi",
        "candidate_version",
        "candidate_instance_sha256",
        "effective_sense_id",
        "source_slot_sense_id",
    ):
        if source.get(key) != candidate.get(key):
            raise ValueError(f"candidate source binding mismatch: {candidate_id}/{key}")
    if (
        source.get("source_term") != sense.get("source_term")
        or source.get("scope_id") != sense.get("scope_id")
        or source.get("definition_en") != sense.get("definition_en")
        or source.get("part_of_speech") != sense.get("part_of_speech")
    ):
        raise ValueError(f"effective-sense source binding mismatch: {candidate_id}")
    return sense, candidate


def build_artifact(
    *,
    dataset_artifact_root: Path,
    review_intake_root: Path,
    reviewer_3_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    dataset_artifact_root = dataset_artifact_root.resolve(strict=True)
    review_intake_root = review_intake_root.resolve(strict=True)
    dataset_manifest = _validate_manifest(
        dataset_artifact_root,
        "d2l_dataset_remaining_300_candidates_stage_b_review_v1",
    )
    intake_manifest = _validate_manifest(
        review_intake_root, "d2l_stage_b_r1_repair_v1"
    )
    if (
        intake_manifest.get("case_count") != 300
        or intake_manifest.get("agreement_count") != 245
        or intake_manifest.get("disagreement_count") != 55
    ):
        raise ValueError("review intake counts are invalid")
    senses, candidates = _source_maps(dataset_artifact_root)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent)
    )
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        raw_reviews = staging / "raw_reviews"
        raw_reviews.mkdir()
        for slot in ("reviewer_1", "reviewer_2"):
            source = review_intake_root / "repaired_reviews" / f"{slot}.json"
            destination = raw_reviews / f"{slot}.json"
            shutil.copy2(source, destination)
            if sha256_file(source) != sha256_file(destination):
                raise ValueError(f"failed to preserve {slot} review bytes")
        reviewer_3_copy = raw_reviews / "reviewer_3.json"
        reviewer_3_sha = _capture_stable(reviewer_3_path, reviewer_3_copy)
        adjudication, errors = validate_completed_adjudication(
            review_intake_root / "reviewer_3_adjudication_input.json",
            reviewer_3_copy,
        )
        if errors or adjudication is None:
            raise ValueError("; ".join(errors))

        pairs = strict_jsonl(review_intake_root / "review_pairs_300.jsonl")
        if len(pairs) != 300 or any(
            not verify_record(row, "review_pair_sha256") for row in pairs
        ):
            raise ValueError("review pair source is invalid")
        adjudication_cases = adjudication.cases_by_candidate
        gold_rows: list[dict[str, Any]] = []
        used_adjudication: set[str] = set()
        for pair in pairs:
            candidate_id = pair["candidate_id"]
            sense, candidate = _validate_pair_source(pair, senses, candidates)
            if pair["label_agreement"]:
                final_label = pair["consensus_label"]
                resolution = "DUAL_REVIEW_CONSENSUS"
                adjudication_label = None
                adjudication_case_sha = None
            else:
                case = adjudication_cases.get(candidate_id)
                if case is None:
                    raise ValueError(f"missing adjudication for {candidate_id}")
                final_label = case["adjudication"]["adjudicator_label"]
                resolution = "REVIEWER_3_ADJUDICATED"
                adjudication_label = final_label
                adjudication_case_sha = case["adjudication_case_sha256"]
                used_adjudication.add(candidate_id)
            if not isinstance(final_label, str):
                raise ValueError(f"final Stage B label is missing: {candidate_id}")
            gold_rows.append(
                seal_record(
                    {
                        "schema_id": "D2LRemainingStageBCandidateGoldV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        "dataset_manifest_sha256": dataset_manifest[
                            "manifest_sha256"
                        ],
                        "review_intake_manifest_sha256": intake_manifest[
                            "manifest_sha256"
                        ],
                        "reviewer_3_result_sha256": reviewer_3_sha,
                        "candidate_id": candidate_id,
                        "candidate_version": candidate["candidate_version"],
                        "candidate_target_vi": candidate["candidate_target_vi"],
                        "candidate_instance_sha256": candidate[
                            "candidate_instance_sha256"
                        ],
                        "effective_sense_id": sense["effective_sense_id"],
                        "source_slot_sense_id": sense["source_slot_sense_id"],
                        "source_term": sense["source_term"],
                        "scope_id": sense["scope_id"],
                        "split": sense["split"],
                        "stratum": sense["stratum"],
                        "kind": sense["kind"],
                        "stage_a_authority_sha256": sense[
                            "stage_a_authority_sha256"
                        ],
                        "effective_sense_record_sha256": sense["record_sha256"],
                        "review_pair_sha256": pair["review_pair_sha256"],
                        "reviewer_1_label": pair["reviewer_1_label"],
                        "reviewer_2_label": pair["reviewer_2_label"],
                        "label_agreement": pair["label_agreement"],
                        "adjudication_label": adjudication_label,
                        "adjudication_case_sha256": adjudication_case_sha,
                        "review_resolution": resolution,
                        "final_gold_label": final_label,
                        "gold_freeze_status": "COMPLETE",
                        "provider_call_count": 0,
                        "final_glossary_decision": None,
                    },
                    "stage_b_gold_sha256",
                )
            )
        if used_adjudication != set(adjudication_cases):
            raise ValueError("adjudication result contains an unused candidate")
        if {row["candidate_id"] for row in gold_rows} != set(candidates):
            raise ValueError("Stage B gold candidate coverage mismatch")

        label_counts = Counter(row["final_gold_label"] for row in gold_rows)
        resolution_counts = Counter(row["review_resolution"] for row in gold_rows)
        source_slot_count = len({row["source_slot_sense_id"] for row in gold_rows})
        summary = {
            "schema_id": "D2LRemainingStageBGoldSummaryV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "release_status": RELEASE_STATUS,
            "source_slot_count": source_slot_count,
            "effective_sense_count": len(senses),
            "candidate_count": len(gold_rows),
            "final_gold_label_count": len(gold_rows),
            "final_gold_label_counts": dict(sorted(label_counts.items())),
            "resolution_counts": dict(sorted(resolution_counts.items())),
            "raw_agreement": strict_json_object(
                review_intake_root / "agreement_report.json"
            )["raw_agreement"],
            "cohen_kappa": strict_json_object(
                review_intake_root / "agreement_report.json"
            )["cohen_kappa"],
            "adjudication_count": len(adjudication_cases),
            "adjudication_label_counts": adjudication.label_counts,
            "human_unjudgeable_count": label_counts.get("HUMAN_UNJUDGEABLE", 0),
            "by_split": _dimension_report(gold_rows, "split"),
            "by_stratum": _dimension_report(gold_rows, "stratum"),
            "by_kind": _dimension_report(gold_rows, "kind"),
            "c_e_evaluation_status": "READY_NOT_RUN",
            "global_validator_status": "NOT_RUN",
            "provider_call_count": 0,
            "final_glossary_decision_count": 0,
        }
        if (
            source_slot_count != 100
            or len(senses) != 105
            or len(gold_rows) != 300
        ):
            raise ValueError("remaining Stage B gold population mismatch")
        write_jsonl(staging / "stage_b_gold_300.jsonl", gold_rows)
        write_json(staging / "stage_b_gold_summary.json", summary)
        shutil.copy2(
            review_intake_root / "agreement_report.json",
            staging / "agreement_report.json",
        )
        shutil.copy2(
            review_intake_root / "review_pairs_300.jsonl",
            staging / "review_pairs_300.jsonl",
        )
        write_json(
            staging / "lineage.json",
            {
                "schema_id": "D2LRemainingStageBGoldLineageV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "dataset_manifest_sha256": dataset_manifest["manifest_sha256"],
                "review_intake_manifest_sha256": intake_manifest[
                    "manifest_sha256"
                ],
                "review_result_sha256": {
                    "reviewer_1": sha256_file(raw_reviews / "reviewer_1.json"),
                    "reviewer_2": sha256_file(raw_reviews / "reviewer_2.json"),
                    "reviewer_3": reviewer_3_sha,
                },
                "source_inventory_sha256": {
                    "effective_senses": dataset_manifest["files"][
                        "effective_senses_105.jsonl"
                    ]["sha256"],
                    "candidates": dataset_manifest["files"][
                        "candidate_instances_300.jsonl"
                    ]["sha256"],
                    "contexts": dataset_manifest["files"][
                        "contexts_selected.jsonl"
                    ]["sha256"],
                },
                "reviewer_3_case_count": 55,
                "provider_call_count": 0,
                "final_glossary_decision_count": 0,
            },
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L remaining 300-candidate Stage B gold release\n\n"
            "- Source slots: 100; effective senses: 105.\n"
            "- Candidates with final Stage B labels: 300/300.\n"
            "- Resolution: 245 dual-review consensus; 55 Reviewer 3 adjudications.\n"
            f"- Final labels: {dict(sorted(label_counts.items()))}.\n"
            "- C/E evaluation is ready but has not run.\n"
            "- Global Validator has not run; final glossary decisions remain null.\n"
            "- Provider calls: 0.\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        manifest = {
            "schema_id": "D2LRemainingStageBGoldManifestV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "artifact_name": ARTIFACT_NAME,
            "release_status": RELEASE_STATUS,
            "dataset_manifest_sha256": dataset_manifest["manifest_sha256"],
            "review_intake_manifest_sha256": intake_manifest["manifest_sha256"],
            "reviewer_3_result_sha256": reviewer_3_sha,
            "source_slot_count": 100,
            "effective_sense_count": 105,
            "candidate_count": 300,
            "final_gold_label_count": 300,
            "adjudication_count": 55,
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
    parser.add_argument("--dataset-artifact-root", required=True, type=Path)
    parser.add_argument("--review-intake-root", required=True, type=Path)
    parser.add_argument("--reviewer-3", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_artifact(
        dataset_artifact_root=args.dataset_artifact_root,
        review_intake_root=args.review_intake_root,
        reviewer_3_path=args.reviewer_3,
        output_root=args.output_root,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
