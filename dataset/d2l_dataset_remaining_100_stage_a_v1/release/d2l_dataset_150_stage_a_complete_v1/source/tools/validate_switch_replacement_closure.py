from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_file_inventory,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_integrity,
    verify_record,
)


EXPECTED_STATUS = "DATASET_150_SOURCE_SLOTS_STAGE_A_COMPLETE_ZERO_PROVIDER"
REPLACED_SENSE_ID = "d2lce_91002293cea2184b43995f47"
REPLACEMENT_SENSE_ID = "d2lce_bad32719ece6439b4716d093"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


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
            root, {"CHECKSUMS.sha256"}
        ).items()
    }
    if expected != actual:
        errors.append("checksum inventory does not match artifact files")


def _validate_zero_provider(value: Any, prefix: str, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key == "provider_call_count" and child != 0:
                errors.append(f"nonzero provider call count: {path}")
            if key == "stage_b_gold_autofill_count" and child != 0:
                errors.append(f"nonzero Stage B gold autofill: {path}")
            if key in {"final_glossary_decision", "stage_b_gold_label"} and child is not None:
                errors.append(f"forbidden final/gold value: {path}")
            _validate_zero_provider(child, path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_zero_provider(child, f"{prefix}[{index}]", errors)


def validate_artifact(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return [str(exc)]
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self-hash mismatch")
    actual_files = build_file_inventory(
        root, {"CHECKSUMS.sha256", "manifest.json"}
    )
    if manifest.get("files") != actual_files:
        errors.append("manifest file inventory mismatch")
    if manifest.get("file_count") != len(actual_files):
        errors.append("manifest file count mismatch")
    if manifest.get("status") != EXPECTED_STATUS:
        errors.append("manifest status mismatch")
    _validate_checksums(root, errors)

    integrity_files = {
        "authority.json": "D2LDataset150StageACompletionAuthorityV1",
        "completion_summary.json": "D2LDataset150StageACompletionSummaryV1",
        "review_input_inventory.json": "D2LReplacementReviewInputInventoryV1",
        "source_term_inventory_150.json": "D2LStageACompleteSourceTermInventoryV1",
    }
    payloads: dict[str, Mapping[str, Any]] = {}
    for name, schema_id in integrity_files.items():
        try:
            payload = strict_json_object(root / name)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        payloads[name] = payload
        if payload.get("schema_id") != schema_id or not verify_integrity(payload):
            errors.append(f"{name}: integrity/schema mismatch")

    inventory = payloads.get("review_input_inventory.json", {})
    files = inventory.get("files")
    captured_roles: set[str] = set()
    captured_hashes: dict[str, str] = {}
    if not isinstance(files, list) or len(files) != 2:
        errors.append("review inventory must contain two files")
    else:
        for row in files:
            if not isinstance(row, Mapping):
                errors.append("invalid review inventory row")
                continue
            role = row.get("reviewer_slot")
            relative = row.get("captured_path")
            if not isinstance(role, str) or not isinstance(relative, str):
                errors.append("invalid review inventory identity")
                continue
            path = root / relative
            if not path.is_file() or sha256_file(path) != row.get("sha256"):
                errors.append(f"captured review hash mismatch: {relative}")
                continue
            payload = strict_json_object(path)
            if payload.get("reviewer_slot") != role:
                errors.append(f"captured review slot mismatch: {relative}")
            review = payload.get("cases", [{}])[0].get("review", {})
            if (
                review.get("review_status") != "COMPLETE"
                or review.get("sense_status")
                != "READY_FOR_CONTRACT_CONSTRUCTION"
                or any(
                    review.get(field) != "ACCEPT"
                    for field in (
                        "candidate_set_decision",
                        "definition_decision",
                        "evidence_decision",
                        "part_of_speech_decision",
                        "scope_decision",
                    )
                )
            ):
                errors.append(f"captured review is not unanimous ACCEPT: {relative}")
            captured_roles.add(role)
            captured_hashes[role] = str(row.get("sha256"))
    if captured_roles != {"reviewer_1", "reviewer_2"}:
        errors.append("captured reviewer role set mismatch")

    try:
        contract = strict_json_object(
            root / "replacement_effective_sense_contract.json"
        )
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
        contract = {}
    if contract and not verify_record(contract):
        errors.append("replacement contract self-hash mismatch")
    if (
        contract.get("sense_id") != REPLACEMENT_SENSE_ID
        or contract.get("source_term") != "hypothesis testing"
        or contract.get("stage_a_status") != "READY_FOR_CONTRACT_CONSTRUCTION"
        or contract.get("review_consensus", {}).get("decision") != "ACCEPT"
        or contract.get("review_consensus", {}).get("reviewer_count") != 2
        or contract.get("review_consensus", {}).get("reviewer_1_result_sha256")
        != captured_hashes.get("reviewer_1")
        or contract.get("review_consensus", {}).get("reviewer_2_result_sha256")
        != captured_hashes.get("reviewer_2")
    ):
        errors.append("replacement contract identity/review binding mismatch")

    try:
        slots = strict_jsonl(root / "stage_a_source_slot_index_150.jsonl")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
        slots = []
    if len(slots) != 150 or len(
        {row.get("source_slot_sense_id") for row in slots}
    ) != 150:
        errors.append("source slot index count/identity mismatch")
    for row in slots:
        if not verify_record(row):
            errors.append("source slot record self-hash mismatch")
    replacements = [row for row in slots if row.get("is_replacement")]
    if len(replacements) != 1 or (
        replacements[0].get("source_slot_sense_id") != REPLACED_SENSE_ID
        or replacements[0].get("effective_sense_id") != REPLACEMENT_SENSE_ID
        or replacements[0].get("source_slot_term") != "switch"
        or replacements[0].get("effective_source_term") != "hypothesis testing"
        or replacements[0].get("stage_a_status") != "READY"
        or replacements[0].get("stage_b_status") != "PENDING"
        or replacements[0].get("authority_record_sha256")
        != contract.get("record_sha256")
    ):
        errors.append("replacement source-slot binding mismatch")
    if any(row.get("stage_a_status") != "READY" for row in slots):
        errors.append("not every source slot is Stage A READY")
    if sum(row.get("stage_b_status") == "COMPLETE" for row in slots) != 50:
        errors.append("Stage B complete source-slot count mismatch")
    if sum(row.get("stage_b_status") == "PENDING" for row in slots) != 100:
        errors.append("Stage B pending source-slot count mismatch")

    terms = payloads.get("source_term_inventory_150.json", {})
    term_values = terms.get("source_terms_casefolded")
    if (
        terms.get("source_term_count") != 150
        or not isinstance(term_values, list)
        or len(term_values) != 150
        or len(set(term_values)) != 150
        or "switch" in term_values
        or "hypothesis testing" not in term_values
    ):
        errors.append("updated source-term inventory mismatch")

    summary = payloads.get("completion_summary.json", {})
    expected_summary = {
        "candidate_instance_count": 450,
        "effective_sense_count": 155,
        "original_source_slot_count": 150,
        "split_child_sense_count": 9,
        "split_source_slot_count": 4,
        "stage_a_blocked_source_slot_count": 0,
        "stage_a_ready_source_slot_count": 150,
        "stage_b_complete_candidate_count": 150,
        "stage_b_complete_effective_sense_count": 50,
        "stage_b_pending_candidate_count": 300,
        "stage_b_pending_effective_sense_count": 105,
        "status": EXPECTED_STATUS,
    }
    for field, value in expected_summary.items():
        if summary.get(field) != value:
            errors.append(f"completion summary mismatch: {field}")

    for path in root.rglob("*"):
        if not path.is_file() or path.name == "CHECKSUMS.sha256":
            continue
        if path.suffix in {".json", ".jsonl"}:
            try:
                if path.suffix == ".json":
                    values: list[Any] = [strict_json_object(path)]
                else:
                    values = strict_jsonl(path)
            except (OSError, UnicodeError, ValueError) as exc:
                errors.append(str(exc))
                continue
            _validate_zero_provider(values, path.as_posix(), errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root.resolve(strict=True))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
