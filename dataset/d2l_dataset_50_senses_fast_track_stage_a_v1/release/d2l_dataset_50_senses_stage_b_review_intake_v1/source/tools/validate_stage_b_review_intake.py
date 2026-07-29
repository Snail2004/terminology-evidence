from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_stage_b_review_intake import ARTIFACT_NAME, POLICY_ID
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_record,
    )
    from .stage_b_review_result import validate_completed_stage_b_review
except ImportError:  # pragma: no cover - direct script execution
    from build_stage_b_review_intake import ARTIFACT_NAME, POLICY_ID  # type: ignore
    from common import (  # type: ignore
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_record,
    )
    from stage_b_review_result import validate_completed_stage_b_review  # type: ignore


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def validate_artifact(root: Path, *, source_artifact_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return [str(exc)]
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("artifact name mismatch")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("policy mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self-hash mismatch")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        errors.append("manifest files are invalid")
        files = {}
    if build_file_inventory(root, {"manifest.json"}) != files:
        errors.append("artifact file inventory mismatch")

    validated = {}
    for slot in ("reviewer_1", "reviewer_2"):
        result, result_errors = validate_completed_stage_b_review(
            source_artifact_root / f"{slot}_full_input.json",
            root / "raw_reviews" / f"{slot}.json",
            expected_reviewer_slot=slot,
        )
        errors.extend(result_errors)
        if result is not None:
            validated[slot] = result
    if (
        len(validated) == 2
        and validated["reviewer_1"].sha256 == validated["reviewer_2"].sha256
    ):
        errors.append("review result hashes unexpectedly match")

    try:
        pairs = strict_jsonl(root / "stage_b_review_pairs_150.jsonl")
        pending = strict_jsonl(root / "stage_b_gold_pending_150.jsonl")
        report = strict_json_object(root / "agreement_report.json")
        adjudication = strict_json_object(root / "adjudication_input.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return errors + [str(exc)]
    if len(pairs) != 150 or any(
        not verify_record(row, "review_pair_sha256") for row in pairs
    ):
        errors.append("review pair coverage or hashes are invalid")
    if len(pending) != 150 or any(
        not verify_record(row, "gold_pending_sha256") for row in pending
    ):
        errors.append("pending gold coverage or hashes are invalid")
    agreement_count = sum(row.get("label_agreement") is True for row in pairs)
    disagreement_count = 150 - agreement_count
    pair_by_candidate: dict[str, Mapping[str, Any]] = {}
    if len(validated) == 2:
        expected_candidates = set(validated["reviewer_1"].cases_by_candidate)
        for row in pairs:
            candidate_id = row.get("candidate_id")
            if not isinstance(candidate_id, str) or candidate_id in pair_by_candidate:
                errors.append("review pairs contain an invalid or duplicate candidate_id")
                continue
            pair_by_candidate[candidate_id] = row
            source_1 = validated["reviewer_1"].cases_by_candidate.get(candidate_id)
            source_2 = validated["reviewer_2"].cases_by_candidate.get(candidate_id)
            if source_1 is None or source_2 is None:
                errors.append(f"review pair is not bound to both raw reviews: {candidate_id}")
                continue
            label_1 = source_1["review"]["candidate_gold_label"]
            label_2 = source_2["review"]["candidate_gold_label"]
            expected_agreement = label_1 == label_2
            if (
                row.get("source_payload") != source_1["source_payload"]
                or row.get("source_payload_sha256")
                != source_1["source_payload_sha256"]
                or row.get("reviewer_1", {}).get("review") != source_1["review"]
                or row.get("reviewer_2", {}).get("review") != source_2["review"]
                or row.get("reviewer_1_label") != label_1
                or row.get("reviewer_2_label") != label_2
                or row.get("label_agreement") is not expected_agreement
                or row.get("consensus_label")
                != (label_1 if expected_agreement else None)
                or row.get("adjudication_required") is expected_agreement
            ):
                errors.append(f"review pair projection mismatch: {candidate_id}")
        if set(pair_by_candidate) != expected_candidates:
            errors.append("review pair candidate set differs from raw reviews")
    pending_by_candidate: dict[str, Mapping[str, Any]] = {}
    for row in pending:
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in pending_by_candidate:
            errors.append("pending gold rows contain an invalid or duplicate candidate_id")
            continue
        pending_by_candidate[candidate_id] = row
        pair = pair_by_candidate.get(candidate_id)
        if pair is None:
            errors.append(f"pending gold row lacks a review pair: {candidate_id}")
            continue
        expected_status = (
            "CONSENSUS_READY_NOT_FROZEN"
            if pair["label_agreement"]
            else "PENDING_ADJUDICATION"
        )
        if (
            row.get("sense_id") != pair.get("sense_id")
            or row.get("reviewer_1_label") != pair.get("reviewer_1_label")
            or row.get("reviewer_2_label") != pair.get("reviewer_2_label")
            or row.get("label_agreement") != pair.get("label_agreement")
            or row.get("consensus_label") != pair.get("consensus_label")
            or row.get("gold_freeze_status") != expected_status
            or row.get("adjudication_label") is not None
            or row.get("final_gold_label") is not None
        ):
            errors.append(f"pending gold projection mismatch: {candidate_id}")
    if (
        report.get("agreement_count") != agreement_count
        or report.get("disagreement_count") != disagreement_count
    ):
        errors.append("agreement report count mismatch")
    if (
        manifest.get("agreement_count") != agreement_count
        or manifest.get("disagreement_count") != disagreement_count
    ):
        errors.append("manifest agreement count mismatch")
    cases = adjudication.get("cases")
    if not isinstance(cases, list) or len(cases) != disagreement_count:
        errors.append("adjudication case count mismatch")
        cases = []
    if any(
        not verify_record(row, "adjudication_case_sha256")
        for row in cases
        if isinstance(row, Mapping)
    ):
        errors.append("adjudication case hash mismatch")
    adjudication_candidates: set[str] = set()
    for row in cases:
        if not isinstance(row, Mapping):
            continue
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in adjudication_candidates:
            errors.append("adjudication cases contain an invalid or duplicate candidate_id")
            continue
        adjudication_candidates.add(candidate_id)
        pair = pair_by_candidate.get(candidate_id)
        if pair is None or pair.get("label_agreement") is not False:
            errors.append(f"adjudication case is not a label disagreement: {candidate_id}")
            continue
        expected_disagreement = {
            "field": "candidate_gold_label",
            "reviewer_1_label": pair["reviewer_1_label"],
            "reviewer_2_label": pair["reviewer_2_label"],
        }
        if (
            row.get("source_payload") != pair.get("source_payload")
            or row.get("source_payload_sha256") != pair.get("source_payload_sha256")
            or row.get("reviewer_1") != pair.get("reviewer_1")
            or row.get("reviewer_2") != pair.get("reviewer_2")
            or row.get("disagreement") != expected_disagreement
        ):
            errors.append(f"adjudication projection mismatch: {candidate_id}")
    expected_adjudication = {
        candidate_id
        for candidate_id, row in pair_by_candidate.items()
        if row.get("label_agreement") is False
    }
    if adjudication_candidates != expected_adjudication:
        errors.append("adjudication candidate set differs from label disagreements")
    binding = [
        {
            "adjudication_case_id": row.get("adjudication_case_id"),
            "adjudication_case_sha256": row.get("adjudication_case_sha256"),
        }
        for row in cases
        if isinstance(row, Mapping)
    ]
    if adjudication.get("source_input_sha256") != sha256_bytes(
        canonical_json_bytes(binding)
    ):
        errors.append("adjudication source binding mismatch")
    if any(
        row.get("adjudication", {}).get("adjudicator_label") is not None
        or row.get("final_gold_label") is not None
        or row.get("final_glossary_decision") is not None
        for row in cases
        if isinstance(row, Mapping)
    ):
        errors.append("adjudication or final labels were prefilled")
    if (
        report.get("final_gold_label_count") != 0
        or manifest.get("final_gold_label_count") != 0
    ):
        errors.append("final gold label count must remain zero")
    if (
        report.get("provider_call_count") != 0
        or manifest.get("provider_call_count") != 0
    ):
        errors.append("provider call count must remain zero")
    handoff = root / str(manifest.get("reviewer_3_handoff_path"))
    if (
        not handoff.is_file()
        or sha256_file(handoff) != manifest.get("reviewer_3_handoff_sha256")
    ):
        errors.append("Reviewer 3 handoff hash mismatch")
    else:
        try:
            with zipfile.ZipFile(handoff) as archive:
                names = set(archive.namelist())
                if names != {
                    "MESSAGE.md",
                    "REVIEW_INSTRUCTIONS.md",
                    "adjudication_input.json",
                }:
                    errors.append("Reviewer 3 handoff contents are invalid")
                packaged = json.loads(
                    archive.read("adjudication_input.json").decode("utf-8")
                )
                if packaged != adjudication:
                    errors.append("Reviewer 3 handoff payload differs from artifact")
        except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as exc:
            errors.append(str(exc))
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
    parser.add_argument("--source-artifact-root", required=True, type=Path)
    parser.add_argument("--release-zip", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(
        args.artifact_root, source_artifact_root=args.source_artifact_root
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
