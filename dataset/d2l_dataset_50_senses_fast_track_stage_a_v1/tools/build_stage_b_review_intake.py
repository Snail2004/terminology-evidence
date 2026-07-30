from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from .stage_b_review_result import (
        STAGE_B_ALLOWED_LABELS,
        ValidatedStageBReview,
        validate_completed_stage_b_review,
    )
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from stage_b_review_result import (  # type: ignore
        STAGE_B_ALLOWED_LABELS,
        ValidatedStageBReview,
        validate_completed_stage_b_review,
    )


ARTIFACT_NAME = "d2l_dataset_50_senses_stage_b_review_intake_v1"
POLICY_ID = "d2l-dataset-50-senses-stage-b-review-intake-v1.0"


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
        sum(
            left_counts[label] * right_counts[label]
            for label in STAGE_B_ALLOWED_LABELS
        )
        / (total * total)
    )
    if expected == 1.0:
        return 1.0
    return round((observed - expected) / (1.0 - expected), 6)


def _dimension_report(
    pairs: Sequence[Mapping[str, Any]],
    senses: Mapping[str, Mapping[str, Any]],
    field: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in pairs:
        grouped[str(senses[row["sense_id"]][field])].append(row)
    return {
        key: {
            "case_count": len(rows),
            "agreement_count": sum(bool(row["label_agreement"]) for row in rows),
            "disagreement_count": sum(
                not bool(row["label_agreement"]) for row in rows
            ),
            "raw_agreement": round(
                sum(bool(row["label_agreement"]) for row in rows) / len(rows), 6
            ),
        }
        for key, rows in sorted(grouped.items())
    }


def _adjudication_case(pair: Mapping[str, Any]) -> dict[str, Any]:
    return seal_record(
        {
            "schema_id": "D2LStageB50CandidateAdjudicationCaseV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "adjudication_case_id": "stageb50_adj_"
            + sha256_bytes(str(pair["candidate_id"]).encode("utf-8"))[:24],
            "candidate_id": pair["candidate_id"],
            "sense_id": pair["sense_id"],
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


def _write_reviewer_3_handoff(
    staging: Path, payload: Mapping[str, Any]
) -> tuple[str, str]:
    handoff = staging / ".handoff" / "reviewer_3"
    handoff.mkdir(parents=True)
    write_json(handoff / "adjudication_input.json", payload)
    (handoff / "REVIEW_INSTRUCTIONS.md").write_text(
        "# Stage B candidate-label adjudication\n\n"
        "Review all supplied disagreement cases as Reviewer 3. You may inspect both "
        "independent reviewer records because this is adjudication, not blind review. "
        "Use only the supplied sense, candidate, D2L contexts, and reviewer rationales. "
        "Fill only the `adjudication` object. Choose exactly one `adjudicator_label` "
        "from ACCEPT, CONDITIONAL, REJECT, SPLIT_REQUIRED, HUMAN_UNJUDGEABLE; provide "
        "a nonblank adjudication_reason; set adjudication_status=COMPLETE. Preserve all "
        "source fields, hashes, reviewer records, and case order. Do not assign a final "
        "glossary decision or call any provider. Return one completed JSON file.\n",
        encoding="utf-8",
        newline="\n",
    )
    (handoff / "MESSAGE.md").write_text(
        "Complete every case in adjudication_input.json and return the same structure "
        "as reviewer_3.json. Return the file only, without raw prose.\n",
        encoding="utf-8",
        newline="\n",
    )
    zip_path = staging / "handoff" / "reviewer_3.zip"
    build_deterministic_zip(handoff, zip_path)
    return zip_path.relative_to(staging).as_posix(), sha256_file(zip_path)


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/stage_b_review_result.py",
        "tools/build_stage_b_review_intake.py",
        "tools/validate_stage_b_review_intake.py",
        "tests/test_stage_b_review_intake.py",
    ):
        source = namespace / relative
        if source.is_file():
            destination = staging / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


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
        captured_paths = {
            "reviewer_1": staging / "raw_reviews" / "reviewer_1.json",
            "reviewer_2": staging / "raw_reviews" / "reviewer_2.json",
        }
        source_hashes = {
            "reviewer_1": _capture_stable(
                resolved_inputs[0], captured_paths["reviewer_1"]
            ),
            "reviewer_2": _capture_stable(
                resolved_inputs[1], captured_paths["reviewer_2"]
            ),
        }
        validated: dict[str, ValidatedStageBReview] = {}
        for slot in ("reviewer_1", "reviewer_2"):
            result, errors = validate_completed_stage_b_review(
                source_artifact_root / f"{slot}_full_input.json",
                captured_paths[slot],
                expected_reviewer_slot=slot,
            )
            if errors or result is None:
                raise ValueError("; ".join(errors))
            validated[slot] = result
        candidate_ids = set(validated["reviewer_1"].cases_by_candidate)
        if candidate_ids != set(validated["reviewer_2"].cases_by_candidate):
            raise ValueError("reviewer candidate coverage differs")

        senses = {
            row["sense_id"]: row
            for row in strict_jsonl(source_artifact_root / "term_senses_50.jsonl")
        }
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
            pair_counts[(label_1, label_2)] += 1
            source = case_1["source_payload"]
            pairs.append(
                seal_record(
                    {
                        "schema_id": "D2LStageB50CandidateReviewPairV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        "candidate_id": candidate_id,
                        "sense_id": source["sense_id"],
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
        disagreement_count = len(pairs) - agreement_count
        report = {
            "schema_id": "D2LStageB50AgreementReportV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "case_count": len(pairs),
            "reviewer_1_label_counts": validated["reviewer_1"].label_counts,
            "reviewer_2_label_counts": validated["reviewer_2"].label_counts,
            "agreement_count": agreement_count,
            "disagreement_count": disagreement_count,
            "raw_agreement": round(agreement_count / len(pairs), 6),
            "cohen_kappa": _cohen_kappa(pair_counts, len(pairs)),
            "adjudication_rate": round(disagreement_count / len(pairs), 6),
            "label_pair_counts": {
                f"{left}__{right}": count
                for (left, right), count in sorted(pair_counts.items())
            },
            "by_split": _dimension_report(pairs, senses, "split"),
            "by_stratum": _dimension_report(pairs, senses, "stratum"),
            "by_lane": _dimension_report(pairs, senses, "lane"),
            "final_gold_label_count": 0,
            "provider_call_count": 0,
            "final_glossary_decision": None,
        }
        write_jsonl(staging / "stage_b_review_pairs_150.jsonl", pairs)
        write_json(staging / "agreement_report.json", report)
        write_jsonl(
            staging / "stage_b_gold_pending_150.jsonl",
            [
                seal_record(
                    {
                        "candidate_id": row["candidate_id"],
                        "sense_id": row["sense_id"],
                        "reviewer_1_label": row["reviewer_1_label"],
                        "reviewer_2_label": row["reviewer_2_label"],
                        "label_agreement": row["label_agreement"],
                        "consensus_label": row["consensus_label"],
                        "adjudication_label": None,
                        "final_gold_label": None,
                        "gold_freeze_status": (
                            "CONSENSUS_READY_NOT_FROZEN"
                            if row["label_agreement"]
                            else "PENDING_ADJUDICATION"
                        ),
                    },
                    "gold_pending_sha256",
                )
                for row in pairs
            ],
        )
        adjudication_cases = [
            _adjudication_case(row)
            for row in pairs
            if row["adjudication_required"]
        ]
        adjudication_binding = [
            {
                "adjudication_case_id": row["adjudication_case_id"],
                "adjudication_case_sha256": row["adjudication_case_sha256"],
            }
            for row in adjudication_cases
        ]
        adjudication_payload = {
            "schema_id": "D2LStageB50CandidateAdjudicationInputV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "reviewer_slot": "reviewer_3_adjudicator",
            "case_count": len(adjudication_cases),
            "allowed_candidate_gold_labels": list(STAGE_B_ALLOWED_LABELS),
            "return_contract": "RETURN_THIS_JSON_WITH_ONLY_ADJUDICATION_FIELDS_FILLED",
            "cases": adjudication_cases,
            "source_input_sha256": sha256_bytes(
                canonical_json_bytes(adjudication_binding)
            ),
            "provider_call_count": 0,
            "final_gold_label_count": 0,
            "final_glossary_decision": None,
        }
        write_json(staging / "adjudication_input.json", adjudication_payload)
        handoff_relative, handoff_sha = _write_reviewer_3_handoff(
            staging, adjudication_payload
        )
        write_json(
            staging / "lineage.json",
            {
                "schema_id": "D2LStageB50ReviewIntakeLineageV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "source_artifact_name": source_manifest.get("artifact_name"),
                "source_artifact_manifest_sha256": source_manifest.get(
                    "manifest_sha256"
                ),
                "source_review_result_sha256": source_hashes,
                "reviewer_slots_distinct": True,
                "review_result_paths_distinct": True,
                "independence_attestation": "OWNER_DECLARED_INDEPENDENT_REVIEWERS",
                "provider_call_count": 0,
            },
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L Stage B 50-sense review intake\n\n"
            "- Valid reviewer results: 2 x 150 cases.\n"
            f"- Label agreements: {agreement_count}/150.\n"
            f"- Label disagreements routed to Reviewer 3: {disagreement_count}/150.\n"
            f"- Raw agreement: {report['raw_agreement']:.2%}.\n"
            f"- Cohen's kappa: {report['cohen_kappa']}.\n"
            "- Final gold labels remain null until adjudication is complete.\n"
            "- Provider calls: 0; final glossary decisions: 0.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "commands.txt").write_text(
            "python -m dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.validate_stage_b_review_intake --artifact-root <artifact> --source-artifact-root <source-artifact>\n",
            encoding="ascii",
            newline="\n",
        )
        _write_source_bundle(staging)
        shutil.rmtree(staging / ".handoff")
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        manifest = {
            "schema_id": "D2LStageB50ReviewIntakeManifestV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "artifact_name": ARTIFACT_NAME,
            "source_artifact_manifest_sha256": source_manifest.get(
                "manifest_sha256"
            ),
            "case_count": 150,
            "agreement_count": agreement_count,
            "disagreement_count": disagreement_count,
            "reviewer_3_handoff_path": handoff_relative,
            "reviewer_3_handoff_sha256": handoff_sha,
            "provider_call_count": 0,
            "final_gold_label_count": 0,
            "final_glossary_decision": None,
            "files": build_file_inventory(staging, {"manifest.json"}),
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        replace_directory(staging, output_root)
        release_zip = output_root.parent / f"{ARTIFACT_NAME}_release.zip"
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
