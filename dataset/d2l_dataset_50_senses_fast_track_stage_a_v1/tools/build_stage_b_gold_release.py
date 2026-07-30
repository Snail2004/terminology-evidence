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
        verify_record,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from .stage_b_adjudication_result import (
        validate_completed_stage_b_adjudication,
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
        verify_record,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from stage_b_adjudication_result import (  # type: ignore
        validate_completed_stage_b_adjudication,
    )


ARTIFACT_NAME = "d2l_dataset_50_senses_150_candidates_stage_b_gold_v1"
POLICY_ID = "d2l-dataset-50-senses-stage-b-gold-v1.0"
RELEASE_STATUS = "STAGE_B_GOLD_COMPLETE_READY_FOR_C_E_EVALUATION"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _validate_artifact_manifest(root: Path) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError(f"manifest self-hash mismatch: {root}")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise ValueError(f"manifest file inventory is invalid: {root}")
    for relative, metadata in files.items():
        relative_path = Path(str(relative))
        if relative_path.is_absolute() or ".." in relative_path.parts or "\\" in str(relative):
            raise ValueError(f"unsafe manifest path: {relative}")
        path = root / relative_path
        if not isinstance(metadata, Mapping) or not path.is_file():
            raise ValueError(f"manifest entry is missing: {relative}")
        if metadata.get("sha256") != sha256_file(path):
            raise ValueError(f"manifest file hash mismatch: {relative}")
    return manifest


def _capture_stable(source: Path, destination: Path) -> str:
    source = source.resolve(strict=True)
    before = sha256_file(source)
    payload = source.read_bytes()
    after = sha256_file(source)
    if before != sha256_bytes(payload) or after != before:
        raise ValueError(f"adjudication source changed during capture: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    if sha256_file(destination) != before:
        raise ValueError("captured adjudication hash mismatch")
    return before


def _dimension_report(
    rows: Sequence[Mapping[str, Any]], field: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(row)
    return {
        key: {
            "candidate_count": len(items),
            "label_counts": dict(sorted(Counter(row["final_gold_label"] for row in items).items())),
        }
        for key, items in sorted(grouped.items())
    }


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/stage_b_adjudication_result.py",
        "tools/build_stage_b_gold_release.py",
        "tools/validate_stage_b_gold_release.py",
        "tests/test_stage_b_gold_release.py",
    ):
        source = namespace / relative
        if source.is_file():
            destination = staging / "source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def build_artifact(
    *,
    dataset_artifact_root: Path,
    review_intake_root: Path,
    reviewer_3_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    dataset_artifact_root = dataset_artifact_root.resolve(strict=True)
    review_intake_root = review_intake_root.resolve(strict=True)
    dataset_manifest = _validate_artifact_manifest(dataset_artifact_root)
    intake_manifest = _validate_artifact_manifest(review_intake_root)
    lineage = strict_json_object(review_intake_root / "lineage.json")
    if lineage.get("source_artifact_manifest_sha256") != dataset_manifest.get(
        "manifest_sha256"
    ):
        raise ValueError("review intake is not bound to the supplied dataset artifact")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent)
    )
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        for slot in ("reviewer_1", "reviewer_2"):
            source = review_intake_root / "raw_reviews" / f"{slot}.json"
            destination = staging / "raw_reviews" / f"{slot}.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha256_file(source) != sha256_file(destination):
                raise ValueError(f"failed to preserve {slot} review bytes")
        reviewer_3_copy = staging / "raw_reviews" / "reviewer_3.json"
        reviewer_3_sha = _capture_stable(reviewer_3_path, reviewer_3_copy)
        adjudication, errors = validate_completed_stage_b_adjudication(
            review_intake_root / "adjudication_input.json", reviewer_3_copy
        )
        if errors or adjudication is None:
            raise ValueError("; ".join(errors))

        pairs = strict_jsonl(review_intake_root / "stage_b_review_pairs_150.jsonl")
        if len(pairs) != 150 or any(
            not verify_record(row, "review_pair_sha256") for row in pairs
        ):
            raise ValueError("review pair source is invalid")
        senses = {
            row["sense_id"]: row
            for row in strict_jsonl(dataset_artifact_root / "term_senses_50.jsonl")
        }
        adjudication_cases = adjudication.cases_by_candidate
        gold_rows: list[dict[str, Any]] = []
        used_adjudication: set[str] = set()
        for pair in pairs:
            candidate_id = pair["candidate_id"]
            sense_id = pair["sense_id"]
            source_payload = pair["source_payload"]
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
            frozen_path = (
                dataset_artifact_root
                / "frozen_candidate_contracts_150"
                / f"{candidate_id}.json"
            )
            evidence_path = (
                dataset_artifact_root
                / "constraint_evidence_packages_150"
                / f"{candidate_id}.json"
            )
            sense_contract_path = (
                dataset_artifact_root
                / "effective_sense_contracts_50"
                / f"{sense_id}.json"
            )
            for path in (frozen_path, evidence_path, sense_contract_path):
                if not path.is_file():
                    raise ValueError(f"required contract is missing: {path.name}")
            sense = senses[sense_id]
            gold_rows.append(
                seal_record(
                    {
                        "schema_id": "D2LStageB50CandidateGoldV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        "dataset_manifest_sha256": dataset_manifest["manifest_sha256"],
                        "review_intake_manifest_sha256": intake_manifest[
                            "manifest_sha256"
                        ],
                        "reviewer_3_result_sha256": reviewer_3_sha,
                        "candidate_id": candidate_id,
                        "candidate_version": source_payload["candidate_version"],
                        "candidate_target_vi": source_payload["candidate_target_vi"],
                        "candidate_instance_sha256": source_payload[
                            "candidate_instance_sha256"
                        ],
                        "sense_id": sense_id,
                        "source_term": source_payload["source_term"],
                        "scope_id": source_payload["scope_id"],
                        "split": sense["split"],
                        "stratum": sense["stratum"],
                        "lane": sense["lane"],
                        "review_pair_sha256": pair["review_pair_sha256"],
                        "reviewer_1_label": pair["reviewer_1_label"],
                        "reviewer_2_label": pair["reviewer_2_label"],
                        "label_agreement": pair["label_agreement"],
                        "adjudication_label": adjudication_label,
                        "adjudication_case_sha256": adjudication_case_sha,
                        "review_resolution": resolution,
                        "final_gold_label": final_label,
                        "gold_freeze_status": "COMPLETE",
                        "frozen_candidate_contract_sha256": sha256_file(frozen_path),
                        "constraint_evidence_package_sha256": sha256_file(evidence_path),
                        "effective_sense_contract_sha256": sha256_file(
                            sense_contract_path
                        ),
                        "provider_call_count": 0,
                        "final_glossary_decision": None,
                    },
                    "stage_b_gold_sha256",
                )
            )
        if used_adjudication != set(adjudication_cases):
            raise ValueError("adjudication result contains an unused candidate")

        label_counts = Counter(row["final_gold_label"] for row in gold_rows)
        resolution_counts = Counter(row["review_resolution"] for row in gold_rows)
        report = {
            "schema_id": "D2LStageB50GoldSummaryV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "release_status": RELEASE_STATUS,
            "sense_count": 50,
            "candidate_count": 150,
            "final_gold_label_count": 150,
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
            "by_lane": _dimension_report(gold_rows, "lane"),
            "c_e_evaluation_status": "READY_NOT_RUN",
            "global_validator_status": "NOT_RUN",
            "provider_call_count": 0,
            "final_glossary_decision_count": 0,
        }
        write_jsonl(staging / "stage_b_gold_150.jsonl", gold_rows)
        write_json(staging / "stage_b_gold_summary.json", report)
        shutil.copy2(
            review_intake_root / "agreement_report.json",
            staging / "agreement_report.json",
        )
        shutil.copy2(
            review_intake_root / "stage_b_review_pairs_150.jsonl",
            staging / "stage_b_review_pairs_150.jsonl",
        )
        write_json(
            staging / "lineage.json",
            {
                "schema_id": "D2LStageB50GoldLineageV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "dataset_artifact_manifest_sha256": dataset_manifest[
                    "manifest_sha256"
                ],
                "review_intake_manifest_sha256": intake_manifest["manifest_sha256"],
                "review_result_sha256": {
                    "reviewer_1": sha256_file(
                        staging / "raw_reviews" / "reviewer_1.json"
                    ),
                    "reviewer_2": sha256_file(
                        staging / "raw_reviews" / "reviewer_2.json"
                    ),
                    "reviewer_3": reviewer_3_sha,
                },
                "reviewer_3_case_count": 19,
                "provider_call_count": 0,
                "final_glossary_decision_count": 0,
            },
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L 50-sense Stage B gold release\n\n"
            "- Senses: 50; candidates with final Stage B labels: 150/150.\n"
            "- Resolution: 131 dual-review consensus; 19 Reviewer 3 adjudications.\n"
            f"- Final labels: {dict(sorted(label_counts.items()))}.\n"
            "- C/E evaluation is ready but has not run.\n"
            "- Global Validator has not run; final glossary decisions remain null.\n"
            "- Provider calls: 0.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "commands.txt").write_text(
            "python -m dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.validate_stage_b_gold_release --artifact-root <artifact> --dataset-artifact-root <dataset-artifact> --review-intake-root <review-intake>\n",
            encoding="ascii",
            newline="\n",
        )
        _write_source_bundle(staging)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        manifest = {
            "schema_id": "D2LStageB50GoldManifestV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "artifact_name": ARTIFACT_NAME,
            "release_status": RELEASE_STATUS,
            "dataset_artifact_manifest_sha256": dataset_manifest["manifest_sha256"],
            "review_intake_manifest_sha256": intake_manifest["manifest_sha256"],
            "reviewer_3_result_sha256": reviewer_3_sha,
            "sense_count": 50,
            "candidate_count": 150,
            "final_gold_label_count": 150,
            "adjudication_count": 19,
            "provider_call_count": 0,
            "final_glossary_decision_count": 0,
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
