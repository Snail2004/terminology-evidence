from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_integrity,
    verify_record,
)

from .followup_handoffs import blank_proposal_audit
from .proposal_repair_validation import validate_split_proposal


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


def _validate_handoffs(
    root: Path, records_by_id: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> None:
    expected = {
        "proposal_reaudit_reviewer_4": ("reviewer_4", 1),
        "proposal_reaudit_reviewer_5": ("reviewer_5", 3),
    }
    batches = sorted((root / "reaudit_batches").glob("*"))
    if {batch.name for batch in batches} != set(expected):
        errors.append("re-audit batch identity mismatch")
        return
    seen: set[str] = set()
    for batch in batches:
        reviewer, count = expected[batch.name]
        payload = strict_json_object(batch / "auditor_input.json")
        cases = payload.get("cases", [])
        if payload.get("reviewer_slot") != reviewer:
            errors.append(f"{batch.name}: reviewer slot mismatch")
        if payload.get("case_count") != count or len(cases) != count:
            errors.append(f"{batch.name}: case count mismatch")
        for case in cases:
            sense_id = str(case.get("sense_id"))
            seen.add(sense_id)
            source = records_by_id.get(sense_id)
            if source is None:
                errors.append(f"{sense_id}: missing repair record")
                continue
            if case.get("audit") != blank_proposal_audit():
                errors.append(f"{sense_id}: re-audit input is not blank")
            if (
                case.get("parent_repair_record_sha256") != source["record_sha256"]
                or case.get("repaired_proposal") != source["repaired_proposal"]
                or case.get("proposal_repair") != source["proposal_repair"]
                or case.get("source_payload") != source["source_payload"]
            ):
                errors.append(f"{sense_id}: re-audit source binding mismatch")
            if source["reaudit_reviewer_role"] != reviewer:
                errors.append(f"{sense_id}: re-audit reviewer assignment mismatch")
        handoff_zip = root / "handoff" / f"{batch.name}.zip"
        with tempfile.TemporaryDirectory(prefix="proposal-reaudit-zip-") as temp_name:
            rebuilt = Path(temp_name) / "rebuilt.zip"
            build_deterministic_zip(batch, rebuilt)
            if not handoff_zip.is_file() or sha256_file(handoff_zip) != sha256_file(
                rebuilt
            ):
                errors.append(f"{batch.name}: handoff ZIP mismatch")
    if seen != set(records_by_id):
        errors.append("re-audit handoffs do not cover exactly four repaired proposals")


def validate_artifact(root: Path) -> list[str]:
    root = root.resolve(strict=True)
    errors: list[str] = []
    try:
        manifest = strict_json_object(root / "manifest.json")
        if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
            errors.append("manifest self-hash mismatch")
        expected_files = build_file_inventory(
            root, {"CHECKSUMS.sha256", "manifest.json"}
        )
        if manifest.get("files") != expected_files:
            errors.append("manifest file inventory mismatch")
        if manifest.get("file_count") != len(expected_files):
            errors.append("manifest file count mismatch")
        _validate_checksums(root, errors)
        authority = strict_json_object(root / "authority.json")
        inventory = strict_json_object(root / "input_inventory.json")
        report = strict_json_object(root / "validation_report.json")
        for name, record in (
            ("authority", authority),
            ("input inventory", inventory),
            ("validation report", report),
        ):
            if not verify_integrity(record):
                errors.append(f"{name} integrity mismatch")
            _validate_zero_provider(record, name, errors)
        inventory_rows = inventory.get("files", [])
        if inventory.get("file_count") != 2 or len(inventory_rows) != 2:
            errors.append("proposal repair inventory must contain two files")
        for row in inventory_rows:
            path = root / "captures" / row["captured_relative_path"]
            if not path.is_file() or sha256_file(path) != row["sha256"]:
                errors.append(f"captured repair mismatch: {row.get('source_file_name')}")
        records = strict_jsonl(root / "proposal_repairs_pending_reaudit_4.jsonl")
        records_by_id = {str(record.get("sense_id")): record for record in records}
        if len(records) != 4 or len(records_by_id) != 4:
            errors.append("proposal repair records must contain four unique senses")
        if {record.get("source_term") for record in records} != {
            "attention",
            "blocks",
            "inverse",
            "shape",
        }:
            errors.append("proposal repair term set mismatch")
        for record in records:
            sense_id = str(record.get("sense_id"))
            if not verify_record(record):
                errors.append(f"proposal repair record hash mismatch: {sense_id}")
            source_payload = record.get("source_payload")
            if not isinstance(source_payload, Mapping) or record.get(
                "source_payload_sha256"
            ) != sha256_bytes(canonical_json_bytes(source_payload)):
                errors.append(f"proposal repair source hash mismatch: {sense_id}")
                continue
            repaired = record.get("repaired_proposal")
            if not isinstance(repaired, Mapping):
                errors.append(f"repaired proposal is invalid: {sense_id}")
                continue
            child_ids = {
                str(child.get("temporary_child_sense_id"))
                for child in repaired.get("child_sense_repairs", [])
                if isinstance(child, Mapping)
            }
            errors.extend(
                validate_split_proposal(
                    repaired, source_payload, child_ids, f"record/{sense_id}"
                )
            )
            if record.get("repair_result_role") == record.get(
                "reaudit_reviewer_role"
            ):
                errors.append(f"repair/re-audit reviewer collision: {sense_id}")
            _validate_zero_provider(record, "repair record", errors)
        _validate_handoffs(root, records_by_id, errors)
        for name in (
            "ASSIGNMENT.md",
            "REVIEWER_4_MESSAGE.md",
            "REVIEWER_5_MESSAGE.md",
        ):
            if not (root / "handoff" / name).is_file():
                errors.append(f"missing handoff instruction: {name}")
        if report.get("pending_reaudit_case_count") != 4:
            errors.append("validation report pending count mismatch")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
