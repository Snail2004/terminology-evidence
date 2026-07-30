from __future__ import annotations

import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_file_inventory,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_record,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.review_result import (
    validate_completed_result,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.reviewer2_repair import (
    preflight_review_results,
    validate_repair_response,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.review_intake import (
    ARTIFACT_NAME,
    EXPECTED_COUNTS,
    POLICY_ID,
    STATUS,
    _batch_ids,
)


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _check_checksums(root: Path, errors: list[str]) -> None:
    checksum_path = root / "CHECKSUMS.sha256"
    if not checksum_path.is_file():
        errors.append("CHECKSUMS.sha256 is missing")
        return
    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        try:
            digest, relative = line.split(" *", 1)
        except ValueError:
            errors.append(f"invalid checksum line: {line}")
            continue
        expected[relative] = digest
    actual = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256"}
        ).items()
    }
    if expected != actual:
        errors.append("checksum inventory mismatch")


def _validate_manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"manifest: {exc}")
        return {}
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("manifest artifact name mismatch")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("manifest policy mismatch")
    if manifest.get("status") != STATUS:
        errors.append("manifest status mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self hash mismatch")
    if manifest.get("files") != build_file_inventory(
        root, {"manifest.json", "CHECKSUMS.sha256"}
    ):
        errors.append("manifest file inventory mismatch")
    for field, expected in {
        "review_result_file_count": 20,
        "completed_review_decision_count": 165,
        "reviewer_2_repair_case_count": 6,
        "adjudication_case_count": 45,
        "r0_repair_queue_count": 10,
        "r0_blind_audit_pool_count": 25,
        "r3_dual_agreement_count": 20,
        "provider_call_count": 0,
        "stage_b_gold_autofill_count": 0,
    }.items():
        if manifest.get(field) != expected:
            errors.append(f"manifest count mismatch: {field}")
    if manifest.get("final_glossary_decision") is not None:
        errors.append("final glossary decision must remain null")
    return manifest


def _validate_inventory(root: Path, errors: list[str]) -> dict[str, Any]:
    try:
        inventory = strict_json_object(root / "input_inventory.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"input inventory: {exc}")
        return {}
    integrity = inventory.get("integrity", {})
    claimed = integrity.get("self_sha256") if isinstance(integrity, Mapping) else None
    payload = dict(inventory)
    payload_integrity = payload.get("integrity")
    if isinstance(payload_integrity, dict):
        payload_integrity.pop("self_sha256", None)
    if claimed != sha256_bytes(canonical_json_bytes(payload)):
        errors.append("input inventory self hash mismatch")
    if inventory.get("input_file_count") != 23:
        errors.append("input inventory count mismatch")
    for row in inventory.get("files", []):
        path = root / row["captured_relative_path"]
        if not path.is_file():
            errors.append(f"captured input missing: {row['captured_relative_path']}")
            continue
        if path.stat().st_size != row["size_bytes"] or sha256_file(path) != row[
            "captured_sha256"
        ]:
            errors.append(f"captured input hash mismatch: {path}")
        if row["source_sha256"] != row["captured_sha256"]:
            errors.append(f"source/capture hash mismatch: {path}")
    return inventory


def _validate_jsonl_records(
    root: Path,
    filename: str,
    expected_count: int,
    hash_field: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    try:
        rows = strict_jsonl(root / filename)
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"{filename}: {exc}")
        return []
    if len(rows) != expected_count:
        errors.append(f"{filename}: expected {expected_count}, got {len(rows)}")
    for index, row in enumerate(rows, start=1):
        if not verify_record(row, hash_field):
            errors.append(f"{filename}:{index}: invalid {hash_field}")
        if row.get("provider_call_count") != 0:
            errors.append(f"{filename}:{index}: provider call count is nonzero")
        if row.get("final_glossary_decision") is not None:
            errors.append(f"{filename}:{index}: final decision is not null")
    return rows


def _validate_handoffs(
    root: Path,
    adjudication: list[dict[str, Any]],
    errors: list[str],
) -> None:
    by_batch: dict[str, list[dict[str, Any]]] = {}
    for row in adjudication:
        by_batch.setdefault(row["batch_id"], []).append(row)
    index = strict_json_object(root / "reviewer_3_batch_index.json")
    if index.get("case_count") != len(adjudication):
        errors.append("Reviewer 3 batch index case count mismatch")
    if index.get("batch_count") != len(by_batch):
        errors.append("Reviewer 3 batch index batch count mismatch")
    for batch in index.get("batches", []):
        relative = batch.get("zip_path")
        zip_path = root / relative
        if not zip_path.is_file():
            errors.append(f"Reviewer 3 handoff missing: {relative}")
            continue
        if sha256_file(zip_path) != batch.get("zip_sha256"):
            errors.append(f"{relative}: ZIP hash mismatch")
        try:
            with zipfile.ZipFile(zip_path) as archive:
                names = sorted(archive.namelist())
                expected_names = [
                    "CHECKSUMS.sha256",
                    "MESSAGE.md",
                    "REVIEW_INSTRUCTIONS.md",
                    "reviewer_3_input.json",
                ]
                if names != expected_names:
                    errors.append(f"{relative}: unexpected file set")
                checksum_rows = archive.read("CHECKSUMS.sha256").decode("ascii").splitlines()
                claimed = {}
                for line in checksum_rows:
                    digest, name = line.split(" *", 1)
                    claimed[name] = digest
                actual = {
                    name: sha256_bytes(archive.read(name))
                    for name in names
                    if name != "CHECKSUMS.sha256"
                }
                if claimed != actual:
                    errors.append(f"{relative}: internal checksum mismatch")
                payload = __import__("json").loads(
                    archive.read("reviewer_3_input.json").decode("utf-8")
                )
        except (OSError, ValueError, zipfile.BadZipFile, KeyError) as exc:
            errors.append(f"{relative}: {exc}")
            continue
        cases = payload.get("cases")
        expected_cases = by_batch.get(batch.get("batch_id"), [])
        if payload.get("case_count") != len(expected_cases) or not isinstance(
            cases, list
        ):
            errors.append(f"{relative}: case count mismatch")
            continue
        if {
            row.get("adjudication_case_id") for row in cases
        } != {row["adjudication_case_id"] for row in expected_cases}:
            errors.append(f"{relative}: case identities mismatch")
        for case in cases:
            adjudication = case.get("adjudication")
            if not isinstance(adjudication, Mapping):
                errors.append(f"{relative}: adjudication is not an object")
                continue
            if any(
                value not in ("", [], None)
                for key, value in adjudication.items()
                if key != "adjudication_status"
            ) or adjudication.get("adjudication_status") not in ("", None):
                errors.append(f"{relative}: adjudication is not blank")


def validate_intake(root: Path, *, canonical_root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    manifest = _validate_manifest(root, errors)
    _check_checksums(root, errors)
    inventory = _validate_inventory(root, errors)
    if not manifest or not inventory:
        return errors

    repair_input = root / "repair" / "reviewer_2_repair_input.json"
    repair_response = root / "repair" / "reviewer_2_repair_response.json"
    repair_errors = validate_repair_response(repair_input, repair_response)[1]
    if repair_errors:
        errors.extend("repair response: " + error for error in repair_errors)
    raw1 = root / "raw_reviews" / "reviewer_1"
    raw2 = root / "raw_reviews" / "reviewer_2"
    try:
        preflight, repair_cases = preflight_review_results(canonical_root, raw1, raw2)
        packaged = strict_json_object(root / "repair" / "preflight_report.json")
        if preflight != packaged or len(repair_cases) != 6:
            errors.append("raw review preflight does not match packaged repair report")
    except (OSError, ValueError) as exc:
        errors.append(f"raw review preflight: {exc}")
    corrected = root / "corrected_reviews" / "reviewer_2"
    try:
        for batch_id in _batch_ids(canonical_root):
            for slot, review_root in (
                ("reviewer_1", raw1),
                ("reviewer_2", corrected),
            ):
                _, result_errors, _ = validate_completed_result(
                    canonical_root / "batches" / batch_id / f"{slot}_input.json",
                    review_root / f"{batch_id}_{slot}_completed.json",
                    expected_batch_id=batch_id,
                    expected_reviewer_slot=slot,
                )
                errors.extend(
                    f"corrected {slot}/{batch_id}: {error}" for error in result_errors
                )
    except (OSError, ValueError) as exc:
        errors.append(f"corrected review validation: {exc}")

    route_index = _validate_jsonl_records(
        root, "route_index_100.jsonl", 100, "route_record_sha256", errors
    )
    adjudication = _validate_jsonl_records(
        root, "adjudication_cases_45.jsonl", 45, "adjudication_case_sha256", errors
    )
    _validate_jsonl_records(
        root, "r0_repair_queue_10.jsonl", 10, "repair_queue_record_sha256", errors
    )
    _validate_jsonl_records(
        root,
        "r0_blind_audit_pool_25.jsonl",
        25,
        "blind_audit_pool_record_sha256",
        errors,
    )
    _validate_jsonl_records(
        root, "r3_dual_agreement_20.jsonl", 20, "agreement_record_sha256", errors
    )
    sense_ids = [row.get("sense_id") for row in route_index]
    if len(set(sense_ids)) != 100:
        errors.append("route index sense IDs are not unique")
    route_counts = Counter(row.get("route") for row in route_index)
    expected_routes = {
        "R0_PENDING_BLIND_AUDIT": 25,
        "R0_REPAIR_REQUIRED": 10,
        "R3_DUAL_AGREEMENT": 20,
        "R3_REVIEWER_DISAGREEMENT": 11,
        "R4_MANDATORY_ADJUDICATION": 34,
    }
    if dict(route_counts) != expected_routes:
        errors.append(f"route count mismatch: {dict(route_counts)}")
    _validate_handoffs(root, adjudication, errors)
    report = strict_json_object(root / "comparison_report.json")
    integrity = report.get("integrity", {})
    claimed = integrity.get("self_sha256") if isinstance(integrity, Mapping) else None
    payload = dict(report)
    if isinstance(payload.get("integrity"), dict):
        payload["integrity"].pop("self_sha256", None)
    if claimed != sha256_bytes(canonical_json_bytes(payload)):
        errors.append("comparison report self hash mismatch")
    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--canonical-root", type=Path, required=True)
    args = parser.parse_args()
    errors = validate_intake(args.artifact_root, canonical_root=args.canonical_root)
    if errors:
        print("\n".join(errors))
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
