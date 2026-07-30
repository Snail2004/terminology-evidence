from __future__ import annotations

import argparse
import copy
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.adjudication_result import (
    validate_completed_adjudication,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    replace_directory,
    sha256_bytes,
    sha256_file,
    strict_json_loads,
    strict_json_object,
    write_checksums,
    write_json,
)


ARTIFACT_NAME = "d2l_dataset_remaining_100_stage_a_reviewer3_repair_v1"
POLICY_ID = "d2l-remaining-100-stage-a-reviewer3-targeted-repair-v1.0"
SCHEMA_ID = "D2LRemaining100StageAReviewer3RepairV1"
STATUS = "REVIEWER_3_TARGETED_REPAIR_REQUIRED"
TARGET_ERROR = "REVISE evidence requires invalid context IDs"
EXPECTED_BATCH_COUNT = 10
EXPECTED_CASE_COUNT = 45
EXPECTED_REPAIR_CASE_COUNT = 8
ALLOWED_EVIDENCE_DECISIONS = {"ACCEPT", "REVISE", "UNJUDGEABLE"}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _batch_rows(intake_root: Path) -> list[dict[str, Any]]:
    index = strict_json_object(intake_root / "reviewer_3_batch_index.json")
    rows = index.get("batches")
    if not isinstance(rows, list) or index.get("batch_count") != len(rows):
        raise ValueError("reviewer_3_batch_index.json: invalid batch inventory")
    if len(rows) != EXPECTED_BATCH_COUNT or index.get("case_count") != EXPECTED_CASE_COUNT:
        raise ValueError("reviewer_3_batch_index.json: unexpected release cardinality")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("reviewer_3_batch_index.json: batch row is not an object")
        batch_id = row.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id or batch_id in seen:
            raise ValueError("reviewer_3_batch_index.json: invalid batch identity")
        if not isinstance(row.get("case_count"), int) or row["case_count"] <= 0:
            raise ValueError(f"{batch_id}: invalid case count")
        zip_path = row.get("zip_path")
        zip_sha = row.get("zip_sha256")
        if not isinstance(zip_path, str) or not isinstance(zip_sha, str):
            raise ValueError(f"{batch_id}: invalid handoff ZIP binding")
        seen.add(batch_id)
        result.append(dict(row))
    if sum(row["case_count"] for row in result) != EXPECTED_CASE_COUNT:
        raise ValueError("reviewer_3_batch_index.json: case total mismatch")
    return result


def _load_canonical_input(
    intake_root: Path, row: Mapping[str, Any]
) -> tuple[dict[str, Any], str]:
    batch_id = row["batch_id"]
    zip_path = intake_root / row["zip_path"]
    if not zip_path.is_file() or zip_path.is_symlink():
        raise ValueError(f"{batch_id}: missing or unsafe canonical handoff ZIP")
    zip_sha = sha256_file(zip_path)
    if zip_sha != row["zip_sha256"]:
        raise ValueError(f"{batch_id}: canonical handoff ZIP hash mismatch")
    try:
        with zipfile.ZipFile(zip_path) as archive:
            raw = archive.read("reviewer_3_input.json")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"{batch_id}: cannot read canonical adjudicator input") from exc
    try:
        payload = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"{batch_id}: invalid canonical adjudicator input") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{batch_id}: canonical adjudicator input is not an object")
    return payload, sha256_bytes(raw)


def _result_path(reviewer_3_root: Path, batch_id: str) -> Path:
    return reviewer_3_root / batch_id / "reviewer_3_input.json"


def _validate_result_tree(reviewer_3_root: Path, batch_ids: list[str]) -> None:
    reviewer_3_root = reviewer_3_root.resolve(strict=True)
    if reviewer_3_root.is_symlink():
        raise ValueError("Reviewer 3 result root must not be a symlink")
    expected = set(batch_ids)
    actual = {entry.name for entry in reviewer_3_root.iterdir()}
    if actual != expected:
        raise ValueError(
            "Reviewer 3 batch directory set mismatch; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    for batch_id in batch_ids:
        directory = reviewer_3_root / batch_id
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError(f"{batch_id}: unsafe result directory")
        entries = {entry.name for entry in directory.iterdir()}
        if entries != {"reviewer_3_input.json"}:
            raise ValueError(f"{batch_id}: result file set mismatch")
        path = _result_path(reviewer_3_root, batch_id)
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"{batch_id}: missing or unsafe Reviewer 3 result")


def _context_projection(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "context_id": context.get("context_id"),
        "context_role": context.get("context_role"),
        "context_type": context.get("context_type"),
        "boundary_only": context.get("boundary_only"),
        "synthetic": context.get("synthetic"),
        "source_text": context.get("source_text"),
        "content_sha256": context.get("content_sha256"),
    }


def _repair_case(
    *,
    batch_id: str,
    case_index: int,
    completed_case: Mapping[str, Any],
    completed_file_sha256: str,
) -> dict[str, Any]:
    source = completed_case["source_payload"]
    adjudication = completed_case["adjudication"]
    return {
        "batch_id": batch_id,
        "case_index": case_index,
        "adjudication_case_id": completed_case.get("adjudication_case_id"),
        "sense_id": completed_case.get("sense_id"),
        "source_term": completed_case.get("source_term"),
        "source_payload_sha256": completed_case.get("source_payload_sha256"),
        "completed_file_sha256": completed_file_sha256,
        "original_adjudication_sha256": sha256_bytes(
            canonical_json_bytes(adjudication)
        ),
        "available_evidence_contexts": [
            _context_projection(context)
            for context in source.get("evidence_contexts", [])
            if isinstance(context, Mapping)
        ],
        "current_evidence_decision": adjudication.get("evidence_decision"),
        "current_invalid_evidence_context_ids": copy.deepcopy(
            adjudication.get("invalid_evidence_context_ids")
        ),
        "current_sense_status": adjudication.get("sense_status"),
        "current_proposed_split_labels": copy.deepcopy(
            adjudication.get("proposed_split_labels")
        ),
        "current_review_notes": adjudication.get("review_notes"),
        "current_adjudication_rationale": adjudication.get(
            "adjudication_rationale"
        ),
        "repair": {
            "evidence_decision": "",
            "invalid_evidence_context_ids": [],
        },
    }


def preflight_adjudication_results(
    intake_root: Path,
    reviewer_3_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    intake_root = intake_root.resolve(strict=True)
    rows = _batch_rows(intake_root)
    batch_ids = [row["batch_id"] for row in rows]
    _validate_result_tree(reviewer_3_root, batch_ids)

    inventory: list[dict[str, Any]] = []
    repair_cases: list[dict[str, Any]] = []
    unexpected_errors: list[str] = []
    total_cases = 0
    failed_batches: set[str] = set()

    for row in rows:
        batch_id = row["batch_id"]
        canonical, canonical_input_sha = _load_canonical_input(intake_root, row)
        result_path = _result_path(reviewer_3_root, batch_id)
        before_sha = sha256_file(result_path)
        before_size = result_path.stat().st_size
        validated, errors, metrics = validate_completed_adjudication(
            canonical,
            result_path,
            expected_batch_id=batch_id,
        )
        after_sha = sha256_file(result_path)
        if before_sha != after_sha:
            raise ValueError(f"{batch_id}: Reviewer 3 result drifted during preflight")
        case_count = metrics.get("case_count", 0)
        if case_count != row["case_count"]:
            unexpected_errors.append(f"{batch_id}: validated case count mismatch")
        total_cases += case_count
        inventory.append(
            {
                "batch_id": batch_id,
                "relative_path": f"{batch_id}/reviewer_3_input.json",
                "size_bytes": before_size,
                "sha256": before_sha,
                "canonical_handoff_zip_sha256": row["zip_sha256"],
                "canonical_input_physical_sha256": canonical_input_sha,
                "case_count": row["case_count"],
            }
        )
        if not errors:
            if validated is None:
                unexpected_errors.append(f"{batch_id}: missing validation result")
            continue
        failed_batches.add(batch_id)
        target_errors = [error for error in errors if TARGET_ERROR in error]
        unexpected_errors.extend(error for error in errors if TARGET_ERROR not in error)
        completed = strict_json_object(result_path)
        cases = completed.get("cases")
        if not isinstance(cases, list):
            unexpected_errors.append(f"{batch_id}: invalid completed case array")
            continue
        matched = 0
        for case_index, completed_case in enumerate(cases, start=1):
            if not isinstance(completed_case, Mapping):
                continue
            adjudication = completed_case.get("adjudication")
            if not isinstance(adjudication, Mapping):
                continue
            expected_error = (
                f"{batch_id}/reviewer_3_adjudicator/case_{case_index}: {TARGET_ERROR}"
            )
            if (
                expected_error in target_errors
                and adjudication.get("evidence_decision") == "REVISE"
                and adjudication.get("invalid_evidence_context_ids") == []
            ):
                repair_cases.append(
                    _repair_case(
                        batch_id=batch_id,
                        case_index=case_index,
                        completed_case=completed_case,
                        completed_file_sha256=before_sha,
                    )
                )
                matched += 1
        if matched != len(target_errors):
            unexpected_errors.append(
                f"{batch_id}: could not bind every evidence repair error"
            )

    if unexpected_errors:
        raise ValueError("Reviewer 3 preflight failed:\n" + "\n".join(unexpected_errors))
    repair_cases.sort(key=lambda case: (case["batch_id"], case["case_index"]))
    if total_cases != EXPECTED_CASE_COUNT:
        raise ValueError(f"Reviewer 3 case total mismatch: {total_cases}")
    if len(repair_cases) != EXPECTED_REPAIR_CASE_COUNT:
        raise ValueError(
            f"Reviewer 3 repair case count mismatch: {len(repair_cases)}"
        )
    report = {
        "schema_id": "D2LRemaining100StageAReviewer3PreflightV1",
        "schema_version": "1.0",
        "policy_id": POLICY_ID,
        "status": STATUS,
        "reviewer_slot": "reviewer_3_adjudicator",
        "source_result_file_count": len(inventory),
        "source_case_count": total_cases,
        "valid_case_count": total_cases - len(repair_cases),
        "targeted_repair_case_count": len(repair_cases),
        "other_error_count": 0,
        "affected_batch_ids": sorted(failed_batches),
        "source_result_inventory": inventory,
        "provider_call_count": 0,
        "stage_b_gold_autofill_count": 0,
        "final_glossary_decision": None,
    }
    return report, repair_cases


def _repair_payload(
    intake_root: Path,
    report: Mapping[str, Any],
    repair_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest = strict_json_object(intake_root / "manifest.json")
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": "1.0",
        "policy_id": POLICY_ID,
        "status": "AWAITING_REVIEWER_3_REPAIR",
        "reviewer_slot": "reviewer_3_adjudicator",
        "repair_scope": "EVIDENCE_DECISION_CONSISTENCY_ONLY",
        "canonical_intake_manifest_sha256": manifest.get("manifest_sha256"),
        "source_result_inventory_sha256": sha256_bytes(
            canonical_json_bytes(report["source_result_inventory"])
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
            "evidence_decision",
            "invalid_evidence_context_ids",
        }:
            errors.append(f"{prefix}: repair fields do not match the contract")
            continue
        decision = repair.get("evidence_decision")
        invalid_ids = repair.get("invalid_evidence_context_ids")
        if decision not in ALLOWED_EVIDENCE_DECISIONS:
            errors.append(
                f"{prefix}: evidence_decision must be ACCEPT, REVISE, or UNJUDGEABLE"
            )
        if not isinstance(invalid_ids, list) or len(invalid_ids) != len(
            set(invalid_ids)
        ):
            errors.append(f"{prefix}: invalid context IDs must be a unique array")
            continue
        available_ids = {
            context.get("context_id")
            for context in source_case.get("available_evidence_contexts", [])
            if isinstance(context, Mapping)
        }
        if any(item not in available_ids for item in invalid_ids):
            errors.append(f"{prefix}: invalid context ID is not source-bound")
        if decision == "REVISE" and not invalid_ids:
            errors.append(f"{prefix}: REVISE requires at least one invalid context ID")
        if decision in {"ACCEPT", "UNJUDGEABLE"} and invalid_ids:
            errors.append(f"{prefix}: {decision} cannot list invalid context IDs")
    return (response if not errors else None), errors


def apply_repair_response(
    *,
    intake_root: Path,
    reviewer_3_root: Path,
    repair_input_path: Path,
    response_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    response, errors = validate_repair_response(repair_input_path, response_path)
    if errors or response is None:
        raise ValueError("repair response validation failed:\n" + "\n".join(errors))
    source_input = strict_json_object(repair_input_path)
    preflight = strict_json_object(repair_input_path.parent / "preflight_report.json")
    inventory = {row["batch_id"]: row for row in preflight["source_result_inventory"]}
    patches = {
        (row["batch_id"], row["adjudication_case_id"]): row["repair"]
        for row in response["cases"]
    }
    rows = _batch_rows(intake_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".d2l-r3-corrected-", dir=output_root.parent
    ) as temp_dir:
        staging = Path(temp_dir) / "corrected_reviewer_3"
        staging.mkdir(parents=True)
        for row in rows:
            batch_id = row["batch_id"]
            source_path = _result_path(reviewer_3_root, batch_id)
            expected = inventory[batch_id]
            if (
                source_path.stat().st_size != expected["size_bytes"]
                or sha256_file(source_path) != expected["sha256"]
            ):
                raise ValueError(f"{batch_id}: Reviewer 3 source drifted after preflight")
            payload = strict_json_object(source_path)
            applied = 0
            for case in payload["cases"]:
                patch = patches.get((batch_id, case["adjudication_case_id"]))
                if patch is None:
                    continue
                case["adjudication"]["evidence_decision"] = patch[
                    "evidence_decision"
                ]
                case["adjudication"]["invalid_evidence_context_ids"] = copy.deepcopy(
                    patch["invalid_evidence_context_ids"]
                )
                applied += 1
            destination = staging / batch_id / "reviewer_3_input.json"
            write_json(destination, payload)
            canonical, _ = _load_canonical_input(intake_root, row)
            _, validation_errors, _ = validate_completed_adjudication(
                canonical,
                destination,
                expected_batch_id=batch_id,
            )
            if validation_errors:
                raise ValueError(
                    f"{batch_id}: corrected result is invalid:\n"
                    + "\n".join(validation_errors)
                )
            expected_applied = sum(
                1 for patch_batch, _ in patches if patch_batch == batch_id
            )
            if applied != expected_applied:
                raise ValueError(f"{batch_id}: repair target was not applied exactly once")
        write_json(
            staging / "correction_receipt.json",
            {
                "schema_id": "D2LRemaining100StageAReviewer3CorrectionReceiptV1",
                "schema_version": "1.0",
                "policy_id": POLICY_ID,
                "repair_input_sha256": sha256_file(repair_input_path),
                "repair_response_sha256": sha256_file(response_path),
                "corrected_case_count": len(patches),
                "source_result_inventory_sha256": source_input[
                    "source_result_inventory_sha256"
                ],
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            },
        )
        replace_directory(staging, output_root)
    return {
        "corrected_case_count": len(patches),
        "corrected_file_count": len(rows),
        "output_root": str(output_root),
    }


def build_repair_package(
    *,
    intake_root: Path,
    reviewer_3_root: Path,
    output_root: Path,
    zip_path: Path,
) -> dict[str, Any]:
    report, repair_cases = preflight_adjudication_results(
        intake_root, reviewer_3_root
    )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".d2l-r3-repair-", dir=output_root.parent
    ) as temp_dir:
        staging = Path(temp_dir) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        payload = _repair_payload(intake_root, report, repair_cases)
        write_json(staging / "reviewer_3_repair_input.json", payload)
        write_json(staging / "preflight_report.json", report)
        (staging / "REPAIR_INSTRUCTIONS.md").write_text(
            "# Reviewer 3 targeted evidence repair\n\n"
            "Review only the eight listed cases and fill only each `repair` object. "
            "If every listed source context remains valid evidence and the contexts "
            "only need to be partitioned between split senses, set "
            "`evidence_decision` to `ACCEPT` and keep "
            "`invalid_evidence_context_ids` empty. If one or more contexts are not "
            "valid evidence for any resulting sense, keep `REVISE` and list every "
            "invalid source-bound context ID. Use `UNJUDGEABLE` only when the evidence "
            "cannot support either conclusion, with an empty ID list. Do not change "
            "any other field. Return only `reviewer_3_repair_input.json`.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "MESSAGE.md").write_text(
            "Please complete only the eight `repair` objects in "
            "`reviewer_3_repair_input.json` and return that JSON file. Preserve all "
            "IDs, context text, hashes, prior notes, rationale, and split labels.\n",
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
            "source_case_count": report["source_case_count"],
            "valid_case_count": report["valid_case_count"],
            "repair_case_count": len(repair_cases),
            "affected_batch_count": len(report["affected_batch_ids"]),
            "source_result_file_count": report["source_result_file_count"],
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
        "source_case_count": report["source_case_count"],
        "valid_case_count": report["valid_case_count"],
        "repair_case_count": len(repair_cases),
        "affected_batch_ids": report["affected_batch_ids"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake-root", type=Path)
    parser.add_argument("--reviewer-3-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--zip-path", type=Path)
    parser.add_argument("--validate-response", type=Path)
    parser.add_argument("--repair-input", type=Path)
    parser.add_argument("--apply-response", type=Path)
    parser.add_argument("--corrected-output-root", type=Path)
    args = parser.parse_args()
    if args.validate_response:
        if not args.repair_input:
            parser.error("--repair-input is required with --validate-response")
        _, errors = validate_repair_response(args.repair_input, args.validate_response)
        print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}))
        return 0 if not errors else 1
    if args.apply_response:
        required = (
            args.intake_root,
            args.reviewer_3_root,
            args.repair_input,
            args.corrected_output_root,
        )
        if any(value is None for value in required):
            parser.error(
                "apply mode requires intake, Reviewer 3, repair-input, and corrected-output roots"
            )
        result = apply_repair_response(
            intake_root=args.intake_root,
            reviewer_3_root=args.reviewer_3_root,
            repair_input_path=args.repair_input,
            response_path=args.apply_response,
            output_root=args.corrected_output_root,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    required = (
        args.intake_root,
        args.reviewer_3_root,
        args.output_root,
        args.zip_path,
    )
    if any(value is None for value in required):
        parser.error("build mode requires intake, Reviewer 3, output, and ZIP paths")
    result = build_repair_package(
        intake_root=args.intake_root,
        reviewer_3_root=args.reviewer_3_root,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
