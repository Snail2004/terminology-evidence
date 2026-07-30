from __future__ import annotations

import argparse
import copy
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        write_checksums,
        write_json,
    )
    from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.review_result import (
        validate_completed_result,
    )
except ImportError:  # pragma: no cover - direct execution from repository root
    raise SystemExit("Run with the repository root on PYTHONPATH")


ARTIFACT_NAME = "d2l_dataset_remaining_100_stage_a_reviewer2_repair_v1"
POLICY_ID = "d2l-remaining-100-stage-a-reviewer2-targeted-repair-v1.0"
SCHEMA_ID = "D2LRemaining100StageAReviewer2RepairV1"
STATUS = "REVIEWER_2_TARGETED_REPAIR_REQUIRED"
TARGET_ERROR = "REVISE candidate set requires replacements"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _batch_ids(canonical_root: Path) -> list[str]:
    index = strict_json_object(canonical_root / "batch_index.json")
    batches = index.get("batches")
    if not isinstance(batches, list):
        raise ValueError("batch_index.json: batches must be an array")
    result = [row.get("batch_id") for row in batches if isinstance(row, Mapping)]
    if len(result) != index.get("batch_count") or any(
        not isinstance(item, str) or not item for item in result
    ):
        raise ValueError("batch_index.json: invalid batch identities")
    return result


def _completed_name(batch_id: str, reviewer_slot: str) -> str:
    return f"{batch_id}_{reviewer_slot}_completed.json"


def _repair_case(
    *,
    batch_id: str,
    case_index: int,
    completed_case: Mapping[str, Any],
    completed_file_sha256: str,
) -> dict[str, Any]:
    source = completed_case["source_payload"]
    review = completed_case["review"]
    candidates = [
        {
            "candidate_id": candidate.get("candidate_id"),
            "candidate_slot": candidate.get("candidate_slot"),
            "candidate_target_vi": candidate.get("candidate_target_vi"),
        }
        for candidate in source.get("candidates", [])
    ]
    return {
        "batch_id": batch_id,
        "case_index": case_index,
        "case_id": completed_case.get("case_id"),
        "sense_id": source.get("sense_id"),
        "source_term": source.get("source_term"),
        "risk_class": source.get("risk_class"),
        "source_payload_sha256": completed_case.get("source_payload_sha256"),
        "completed_file_sha256": completed_file_sha256,
        "original_review_sha256": sha256_bytes(canonical_json_bytes(review)),
        "candidates": candidates,
        "current_sense_status": review.get("sense_status"),
        "current_proposed_split_labels": copy.deepcopy(
            review.get("proposed_split_labels")
        ),
        "current_review_notes": review.get("review_notes"),
        "repair": {
            "candidate_set_decision": "",
            "candidate_replacements": [],
        },
    }


def preflight_review_results(
    canonical_root: Path,
    reviewer_1_root: Path,
    reviewer_2_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    batch_ids = _batch_ids(canonical_root)
    inventory: list[dict[str, Any]] = []
    repair_cases: list[dict[str, Any]] = []
    unexpected_errors: list[str] = []
    counts = {"reviewer_1": 0, "reviewer_2": 0}

    for reviewer_slot, result_root in (
        ("reviewer_1", reviewer_1_root),
        ("reviewer_2", reviewer_2_root),
    ):
        expected_names = {
            _completed_name(batch_id, reviewer_slot) for batch_id in batch_ids
        }
        actual_names = {path.name for path in result_root.iterdir() if path.is_file()}
        if actual_names != expected_names:
            missing = sorted(expected_names - actual_names)
            extra = sorted(actual_names - expected_names)
            raise ValueError(
                f"{reviewer_slot}: result file set mismatch; missing={missing}, extra={extra}"
            )

        for batch_id in batch_ids:
            canonical_path = (
                canonical_root / "batches" / batch_id / f"{reviewer_slot}_input.json"
            )
            completed_path = result_root / _completed_name(batch_id, reviewer_slot)
            completed_sha = sha256_file(completed_path)
            inventory.append(
                {
                    "reviewer_slot": reviewer_slot,
                    "batch_id": batch_id,
                    "file_name": completed_path.name,
                    "size_bytes": completed_path.stat().st_size,
                    "sha256": completed_sha,
                }
            )
            validated, errors, metrics = validate_completed_result(
                canonical_path,
                completed_path,
                expected_batch_id=batch_id,
                expected_reviewer_slot=reviewer_slot,
            )
            counts[reviewer_slot] += metrics["case_count"]
            if not errors:
                if validated is None:
                    raise ValueError(f"{batch_id}/{reviewer_slot}: missing validation result")
                continue
            if reviewer_slot != "reviewer_2":
                unexpected_errors.extend(errors)
                continue
            target_errors = [error for error in errors if TARGET_ERROR in error]
            unexpected_errors.extend(
                error for error in errors if TARGET_ERROR not in error
            )
            if not target_errors:
                continue
            completed = strict_json_object(completed_path)
            cases = completed.get("cases")
            if not isinstance(cases, list):
                unexpected_errors.append(f"{batch_id}/{reviewer_slot}: invalid cases")
                continue
            matched = 0
            for case_index, completed_case in enumerate(cases, start=1):
                if not isinstance(completed_case, Mapping):
                    continue
                review = completed_case.get("review")
                if not isinstance(review, Mapping):
                    continue
                if (
                    review.get("candidate_set_decision") == "REVISE"
                    and review.get("candidate_replacements") == []
                ):
                    expected_error = (
                        f"{batch_id}/{reviewer_slot}/case_{case_index}: {TARGET_ERROR}"
                    )
                    if expected_error in target_errors:
                        repair_cases.append(
                            _repair_case(
                                batch_id=batch_id,
                                case_index=case_index,
                                completed_case=completed_case,
                                completed_file_sha256=completed_sha,
                            )
                        )
                        matched += 1
            if matched != len(target_errors):
                unexpected_errors.append(
                    f"{batch_id}/{reviewer_slot}: could not bind every repair error"
                )

    if unexpected_errors:
        raise ValueError("review preflight failed:\n" + "\n".join(unexpected_errors))
    repair_cases.sort(key=lambda row: (row["batch_id"], row["case_index"]))
    if counts != {"reviewer_1": 100, "reviewer_2": 65}:
        raise ValueError(f"review case totals mismatch: {counts}")
    if not repair_cases:
        raise ValueError("no targeted Reviewer 2 repair cases were found")
    report = {
        "schema_id": "D2LRemaining100StageAReviewPreflightV1",
        "policy_id": POLICY_ID,
        "status": STATUS,
        "reviewer_1_case_count": counts["reviewer_1"],
        "reviewer_1_valid_case_count": counts["reviewer_1"],
        "reviewer_2_case_count": counts["reviewer_2"],
        "reviewer_2_targeted_repair_case_count": len(repair_cases),
        "reviewer_2_other_error_count": 0,
        "affected_batch_ids": sorted({row["batch_id"] for row in repair_cases}),
        "source_review_file_count": len(inventory),
        "source_review_inventory": inventory,
        "provider_call_count": 0,
        "stage_b_gold_autofill_count": 0,
        "final_glossary_decision": None,
    }
    return report, repair_cases


def _repair_payload(
    canonical_root: Path,
    report: Mapping[str, Any],
    repair_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical_manifest = strict_json_object(canonical_root / "manifest.json")
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": "1.0",
        "policy_id": POLICY_ID,
        "status": "AWAITING_REVIEWER_2_REPAIR",
        "reviewer_slot": "reviewer_2",
        "repair_scope": "CANDIDATE_SET_CONSISTENCY_ONLY",
        "canonical_stage_a_manifest_sha256": canonical_manifest.get(
            "manifest_sha256"
        ),
        "source_review_inventory_sha256": sha256_bytes(
            canonical_json_bytes(report["source_review_inventory"])
        ),
        "case_count": len(repair_cases),
        "cases": repair_cases,
        "return_contract": "RETURN_THIS_JSON_WITH_ONLY_CASES_REPAIR_FIELDS_FILLED",
        "provider_call_count": 0,
        "stage_b_gold_autofill_count": 0,
        "final_glossary_decision": None,
    }


def validate_repair_response(
    repair_input_path: Path,
    response_path: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        source = strict_json_object(repair_input_path)
        response = strict_json_object(response_path)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [str(exc)]
    if set(source) != set(response):
        errors.append("top-level keys changed")
    for key, value in source.items():
        if key != "cases" and response.get(key) != value:
            errors.append(f"immutable top-level field changed: {key}")
    source_cases = source.get("cases")
    response_cases = response.get("cases")
    if not isinstance(source_cases, list) or not isinstance(response_cases, list):
        return None, errors + ["cases must be arrays"]
    if len(source_cases) != len(response_cases):
        errors.append("case count changed")
    for index, (source_case, response_case) in enumerate(
        zip(source_cases, response_cases), start=1
    ):
        prefix = f"case_{index}"
        if not isinstance(source_case, Mapping) or not isinstance(
            response_case, Mapping
        ):
            errors.append(f"{prefix}: case must be an object")
            continue
        if set(source_case) != set(response_case):
            errors.append(f"{prefix}: case keys changed")
        for key, value in source_case.items():
            if key != "repair" and response_case.get(key) != value:
                errors.append(f"{prefix}: immutable field changed: {key}")
        repair = response_case.get("repair")
        if not isinstance(repair, Mapping) or set(repair) != {
            "candidate_set_decision",
            "candidate_replacements",
        }:
            errors.append(f"{prefix}: repair fields do not match the contract")
            continue
        decision = repair.get("candidate_set_decision")
        replacements = repair.get("candidate_replacements")
        if decision not in {"ACCEPT", "REVISE"}:
            errors.append(f"{prefix}: candidate_set_decision must be ACCEPT or REVISE")
        if not isinstance(replacements, list):
            errors.append(f"{prefix}: candidate_replacements must be an array")
            continue
        if decision == "ACCEPT" and replacements:
            errors.append(f"{prefix}: ACCEPT cannot contain replacements")
        if decision == "REVISE" and not replacements:
            errors.append(f"{prefix}: REVISE requires at least one replacement")
        candidates = {
            (row.get("candidate_id"), row.get("candidate_slot"))
            for row in source_case.get("candidates", [])
            if isinstance(row, Mapping)
        }
        for replacement_index, replacement in enumerate(replacements, start=1):
            if not isinstance(replacement, Mapping) or set(replacement) != {
                "candidate_id",
                "candidate_slot",
                "replacement_target_vi",
            }:
                errors.append(
                    f"{prefix}: invalid replacement object {replacement_index}"
                )
                continue
            identity = (
                replacement.get("candidate_id"),
                replacement.get("candidate_slot"),
            )
            if identity not in candidates:
                errors.append(
                    f"{prefix}: replacement {replacement_index} is not source-bound"
                )
            target = replacement.get("replacement_target_vi")
            if not isinstance(target, str) or not target.strip():
                errors.append(
                    f"{prefix}: replacement {replacement_index} target is blank"
                )
    return (response if not errors else None), errors


def apply_repair_response(
    *,
    canonical_root: Path,
    reviewer_2_root: Path,
    repair_input_path: Path,
    response_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    response, errors = validate_repair_response(repair_input_path, response_path)
    if errors or response is None:
        raise ValueError("repair response validation failed:\n" + "\n".join(errors))
    source_input = strict_json_object(repair_input_path)
    preflight = strict_json_object(repair_input_path.parent / "preflight_report.json")
    inventory = {
        row["batch_id"]: row
        for row in preflight["source_review_inventory"]
        if row["reviewer_slot"] == "reviewer_2"
    }
    patches = {
        (row["batch_id"], row["case_id"]): row["repair"]
        for row in response["cases"]
    }
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".d2l-r2-corrected-", dir=output_root.parent
    ) as temp_dir:
        staging = Path(temp_dir) / "corrected_reviewer_2"
        staging.mkdir(parents=True)
        for batch_id in _batch_ids(canonical_root):
            source_path = reviewer_2_root / _completed_name(batch_id, "reviewer_2")
            expected = inventory[batch_id]
            if (
                source_path.stat().st_size != expected["size_bytes"]
                or sha256_file(source_path) != expected["sha256"]
            ):
                raise ValueError(f"{batch_id}: Reviewer 2 source drifted after preflight")
            payload = strict_json_object(source_path)
            for case in payload["cases"]:
                patch = patches.get((batch_id, case["case_id"]))
                if patch is None:
                    continue
                case["review"]["candidate_set_decision"] = patch[
                    "candidate_set_decision"
                ]
                case["review"]["candidate_replacements"] = copy.deepcopy(
                    patch["candidate_replacements"]
                )
            destination = staging / source_path.name
            write_json(destination, payload)
            canonical_path = (
                canonical_root / "batches" / batch_id / "reviewer_2_input.json"
            )
            _, validation_errors, _ = validate_completed_result(
                canonical_path,
                destination,
                expected_batch_id=batch_id,
                expected_reviewer_slot="reviewer_2",
            )
            if validation_errors:
                raise ValueError(
                    f"{batch_id}: corrected result is invalid:\n"
                    + "\n".join(validation_errors)
                )
        write_json(
            staging / "correction_receipt.json",
            {
                "schema_id": "D2LRemaining100StageAReviewer2CorrectionReceiptV1",
                "policy_id": POLICY_ID,
                "repair_input_sha256": sha256_file(repair_input_path),
                "repair_response_sha256": sha256_file(response_path),
                "corrected_case_count": len(patches),
                "source_review_inventory_sha256": source_input[
                    "source_review_inventory_sha256"
                ],
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            },
        )
        replace_directory(staging, output_root)
    return {
        "corrected_case_count": len(patches),
        "corrected_file_count": 10,
        "output_root": str(output_root),
    }


def build_repair_package(
    *,
    canonical_root: Path,
    reviewer_1_root: Path,
    reviewer_2_root: Path,
    output_root: Path,
    zip_path: Path,
) -> dict[str, Any]:
    report, repair_cases = preflight_review_results(
        canonical_root, reviewer_1_root, reviewer_2_root
    )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".d2l-r2-repair-", dir=output_root.parent
    ) as temp_dir:
        staging = Path(temp_dir) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        payload = _repair_payload(canonical_root, report, repair_cases)
        write_json(staging / "reviewer_2_repair_input.json", payload)
        write_json(staging / "preflight_report.json", report)
        (staging / "REPAIR_INSTRUCTIONS.md").write_text(
            "# Reviewer 2 targeted repair\n\n"
            "Review only the six listed cases. Fill only each `repair` object. "
            "If the existing three candidates remain valid and only need to be "
            "partitioned across the proposed split senses, set "
            "`candidate_set_decision` to `ACCEPT` and keep "
            "`candidate_replacements` empty. If candidate wording itself must change, "
            "set the decision to `REVISE` and provide at least one source-bound object "
            "with `candidate_id`, `candidate_slot`, and `replacement_target_vi`. "
            "Do not change any other field. Return only the completed "
            "`reviewer_2_repair_input.json`.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "MESSAGE.md").write_text(
            "Please complete the six `repair` objects in "
            "`reviewer_2_repair_input.json` and return only that JSON file. "
            "Do not alter IDs, source text, review notes, split labels, or hashes.\n",
            encoding="utf-8",
            newline="\n",
        )
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "artifact_name": ARTIFACT_NAME,
            "schema_id": SCHEMA_ID,
            "schema_version": "1.0",
            "policy_id": POLICY_ID,
            "status": STATUS,
            "repair_case_count": len(repair_cases),
            "affected_batch_count": len(report["affected_batch_ids"]),
            "source_review_file_count": report["source_review_file_count"],
            "files": files,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        replace_directory(staging, output_root)
    build_deterministic_zip(output_root, zip_path)
    zip_sha = sha256_file(zip_path)
    zip_path.with_suffix(zip_path.suffix + ".sha256").write_text(
        f"{zip_sha} *{zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        "artifact_root": str(output_root),
        "zip_path": str(zip_path),
        "zip_sha256": zip_sha,
        "manifest_sha256": strict_json_object(output_root / "manifest.json")[
            "manifest_sha256"
        ],
        "repair_case_count": len(repair_cases),
        "affected_batch_ids": report["affected_batch_ids"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-root", type=Path)
    parser.add_argument("--reviewer-1-root", type=Path)
    parser.add_argument("--reviewer-2-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--zip-path", type=Path)
    parser.add_argument("--validate-response", type=Path)
    parser.add_argument("--repair-input", type=Path)
    args = parser.parse_args()
    if args.validate_response:
        if not args.repair_input:
            parser.error("--repair-input is required with --validate-response")
        _, errors = validate_repair_response(args.repair_input, args.validate_response)
        print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}))
        return 0 if not errors else 1
    required = (
        args.canonical_root,
        args.reviewer_1_root,
        args.reviewer_2_root,
        args.output_root,
        args.zip_path,
    )
    if any(value is None for value in required):
        parser.error("build mode requires all root and ZIP arguments")
    result = build_repair_package(
        canonical_root=args.canonical_root,
        reviewer_1_root=args.reviewer_1_root,
        reviewer_2_root=args.reviewer_2_root,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
