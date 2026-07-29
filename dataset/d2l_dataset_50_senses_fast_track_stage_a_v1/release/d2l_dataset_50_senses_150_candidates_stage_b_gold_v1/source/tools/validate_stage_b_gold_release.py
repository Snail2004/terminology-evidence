from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_stage_b_gold_release import ARTIFACT_NAME, POLICY_ID, RELEASE_STATUS
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_record,
    )
    from .stage_b_adjudication_result import (
        validate_completed_stage_b_adjudication,
    )
except ImportError:  # pragma: no cover - direct script execution
    from build_stage_b_gold_release import (  # type: ignore
        ARTIFACT_NAME,
        POLICY_ID,
        RELEASE_STATUS,
    )
    from common import (  # type: ignore
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_record,
    )
    from stage_b_adjudication_result import (  # type: ignore
        validate_completed_stage_b_adjudication,
    )


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def validate_artifact(
    root: Path,
    *,
    dataset_artifact_root: Path,
    review_intake_root: Path,
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = strict_json_object(root / "manifest.json")
        dataset_manifest = strict_json_object(dataset_artifact_root / "manifest.json")
        intake_manifest = strict_json_object(review_intake_root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return [str(exc)]
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("artifact name mismatch")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("policy mismatch")
    if manifest.get("release_status") != RELEASE_STATUS:
        errors.append("release status mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self-hash mismatch")
    if manifest.get("dataset_artifact_manifest_sha256") != dataset_manifest.get(
        "manifest_sha256"
    ):
        errors.append("dataset artifact binding mismatch")
    if manifest.get("review_intake_manifest_sha256") != intake_manifest.get(
        "manifest_sha256"
    ):
        errors.append("review intake binding mismatch")
    files = manifest.get("files")
    if not isinstance(files, Mapping) or build_file_inventory(
        root, {"manifest.json"}
    ) != files:
        errors.append("artifact file inventory mismatch")

    for slot in ("reviewer_1", "reviewer_2"):
        source = review_intake_root / "raw_reviews" / f"{slot}.json"
        captured = root / "raw_reviews" / f"{slot}.json"
        if not source.is_file() or not captured.is_file() or sha256_file(source) != sha256_file(captured):
            errors.append(f"{slot} raw review bytes differ from intake")
    adjudication, adjudication_errors = validate_completed_stage_b_adjudication(
        review_intake_root / "adjudication_input.json",
        root / "raw_reviews" / "reviewer_3.json",
    )
    errors.extend(adjudication_errors)
    if adjudication is not None and adjudication.sha256 != manifest.get(
        "reviewer_3_result_sha256"
    ):
        errors.append("Reviewer 3 result hash mismatch")

    try:
        pairs = strict_jsonl(review_intake_root / "stage_b_review_pairs_150.jsonl")
        gold_rows = strict_jsonl(root / "stage_b_gold_150.jsonl")
        summary = strict_json_object(root / "stage_b_gold_summary.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return errors + [str(exc)]
    pair_by_candidate = {row.get("candidate_id"): row for row in pairs}
    if len(pairs) != 150 or len(pair_by_candidate) != 150:
        errors.append("review pair coverage is invalid")
    gold_by_candidate: dict[str, Mapping[str, Any]] = {}
    label_counts: Counter[str] = Counter()
    resolution_counts: Counter[str] = Counter()
    adjudication_candidates = (
        set(adjudication.cases_by_candidate) if adjudication is not None else set()
    )
    used_adjudication: set[str] = set()
    for row in gold_rows:
        candidate_id = row.get("candidate_id")
        if not verify_record(row, "stage_b_gold_sha256"):
            errors.append(f"gold record hash mismatch: {candidate_id}")
        if not isinstance(candidate_id, str) or candidate_id in gold_by_candidate:
            errors.append("gold records contain an invalid or duplicate candidate_id")
            continue
        gold_by_candidate[candidate_id] = row
        pair = pair_by_candidate.get(candidate_id)
        if pair is None:
            errors.append(f"gold record lacks review pair: {candidate_id}")
            continue
        expected_label: Any
        expected_resolution: str
        expected_adjudication_label: Any = None
        expected_adjudication_sha: Any = None
        if pair.get("label_agreement") is True:
            expected_label = pair.get("consensus_label")
            expected_resolution = "DUAL_REVIEW_CONSENSUS"
        else:
            case = (
                adjudication.cases_by_candidate.get(candidate_id)
                if adjudication is not None
                else None
            )
            if case is None:
                errors.append(f"gold record lacks adjudication: {candidate_id}")
                continue
            expected_label = case["adjudication"]["adjudicator_label"]
            expected_adjudication_label = expected_label
            expected_adjudication_sha = case["adjudication_case_sha256"]
            expected_resolution = "REVIEWER_3_ADJUDICATED"
            used_adjudication.add(candidate_id)
        if (
            row.get("review_pair_sha256") != pair.get("review_pair_sha256")
            or row.get("reviewer_1_label") != pair.get("reviewer_1_label")
            or row.get("reviewer_2_label") != pair.get("reviewer_2_label")
            or row.get("label_agreement") != pair.get("label_agreement")
            or row.get("adjudication_label") != expected_adjudication_label
            or row.get("adjudication_case_sha256") != expected_adjudication_sha
            or row.get("review_resolution") != expected_resolution
            or row.get("final_gold_label") != expected_label
            or row.get("gold_freeze_status") != "COMPLETE"
        ):
            errors.append(f"gold resolution projection mismatch: {candidate_id}")
        if row.get("provider_call_count") != 0:
            errors.append(f"provider_call_count is not zero: {candidate_id}")
        if row.get("final_glossary_decision") is not None:
            errors.append(f"final glossary decision is not null: {candidate_id}")
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
        sense_path = (
            dataset_artifact_root
            / "effective_sense_contracts_50"
            / f"{row.get('sense_id')}.json"
        )
        if (
            not frozen_path.is_file()
            or row.get("frozen_candidate_contract_sha256") != sha256_file(frozen_path)
            or not evidence_path.is_file()
            or row.get("constraint_evidence_package_sha256") != sha256_file(evidence_path)
            or not sense_path.is_file()
            or row.get("effective_sense_contract_sha256") != sha256_file(sense_path)
        ):
            errors.append(f"contract binding mismatch: {candidate_id}")
        label_counts[str(row.get("final_gold_label"))] += 1
        resolution_counts[str(row.get("review_resolution"))] += 1
    if len(gold_rows) != 150 or set(gold_by_candidate) != set(pair_by_candidate):
        errors.append("gold coverage is not exactly 150/150")
    if used_adjudication != adjudication_candidates:
        errors.append("adjudication coverage differs from gold resolutions")
    if summary.get("final_gold_label_count") != 150:
        errors.append("summary final gold count mismatch")
    if summary.get("final_gold_label_counts") != dict(sorted(label_counts.items())):
        errors.append("summary label distribution mismatch")
    if summary.get("resolution_counts") != dict(sorted(resolution_counts.items())):
        errors.append("summary resolution distribution mismatch")
    if summary.get("provider_call_count") != 0:
        errors.append("summary provider call count must remain zero")
    if summary.get("final_glossary_decision_count") != 0:
        errors.append("summary final glossary decision count must remain zero")
    return errors


def validate_zip(zip_path: Path, artifact_root: Path) -> list[str]:
    try:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            with zipfile.ZipFile(zip_path) as archive:
                for info in archive.infolist():
                    parts = Path(info.filename).parts
                    if (
                        info.filename.startswith("/")
                        or "\\" in info.filename
                        or ".." in parts
                    ):
                        return [f"unsafe ZIP path: {info.filename}"]
                archive.extractall(target)
            if build_file_inventory(artifact_root) != build_file_inventory(target):
                return ["release ZIP differs from artifact root"]
    except (OSError, zipfile.BadZipFile) as exc:
        return [str(exc)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--dataset-artifact-root", required=True, type=Path)
    parser.add_argument("--review-intake-root", required=True, type=Path)
    parser.add_argument("--release-zip", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(
        args.artifact_root,
        dataset_artifact_root=args.dataset_artifact_root,
        review_intake_root=args.review_intake_root,
    )
    if args.release_zip:
        errors.extend(validate_zip(args.release_zip, args.artifact_root))
    print(
        json.dumps(
            {"status": "PASS" if not errors else "FAIL", "errors": errors},
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
