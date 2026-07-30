from __future__ import annotations

import argparse
import json
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

from .followup_handoffs import blank_proposal_audit, blank_standard_review


EXPECTED_ROUTING = {
    "routing/accepted_blind_23.jsonl": 23,
    "routing/blocked_1.jsonl": 1,
    "routing/high_risk_audit_pending_10.jsonl": 10,
    "routing/r0_reaudit_pending_12.jsonl": 12,
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _validate_checksums(root: Path, errors: list[str]) -> None:
    checksum_path = root / "CHECKSUMS.sha256"
    try:
        rows = checksum_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(str(exc))
        return
    actual: dict[str, str] = {}
    for row in rows:
        if " *" not in row:
            errors.append("malformed checksum row")
            continue
        claimed, relative = row.split(" *", 1)
        if relative in actual:
            errors.append(f"duplicate checksum path: {relative}")
            continue
        actual[relative] = claimed
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256"}
        ).items()
    }
    if actual != expected:
        errors.append("checksum inventory does not match artifact files")


def _forbidden_review_keys(value: Any, prefix: str = "") -> list[str]:
    forbidden = {
        "final_glossary_decision",
        "reviewer_1_findings",
        "reviewer_1_review",
        "reviewer_1_result_sha256",
        "risk_class",
        "source_review_status",
        "stage_b_gold_label",
    }
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in forbidden:
                matches.append(path)
            matches.extend(_forbidden_review_keys(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_forbidden_review_keys(child, f"{prefix}[{index}]"))
    return matches


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
        if inventory.get("file_count") != 10 or len(inventory.get("files", [])) != 10:
            errors.append("captured review inventory must contain 10 files")
        for row in inventory.get("files", []):
            path = root / "captures" / row["captured_relative_path"]
            if not path.is_file() or sha256_file(path) != row["sha256"]:
                errors.append(f"captured review mismatch: {row.get('source_file_name')}")
        all_sense_ids: list[str] = []
        for relative, expected_count in EXPECTED_ROUTING.items():
            records = strict_jsonl(root / relative)
            if len(records) != expected_count:
                errors.append(f"routing count mismatch: {relative}")
            for record in records:
                if not verify_record(record, "record_sha256"):
                    errors.append(f"routing record hash mismatch: {record.get('sense_id')}")
                all_sense_ids.append(str(record.get("sense_id")))
        if len(all_sense_ids) != 46 or len(set(all_sense_ids)) != 46:
            errors.append("routing senses must be 46 unique source senses")
        review_batches = sorted((root / "review_batches").glob("*"))
        if len(review_batches) != 6:
            errors.append("expected six follow-up review batches")
        for name in ("ASSIGNMENT.md", "REVIEWER_4_MESSAGE.md", "REVIEWER_5_MESSAGE.md"):
            if not (root / "handoff" / name).is_file():
                errors.append(f"missing reviewer handoff instruction: {name}")
        for batch_root in review_batches:
            json_files = sorted(batch_root.glob("*.json"))
            if len(json_files) != 1:
                errors.append(f"{batch_root.name}: expected one JSON input")
                continue
            payload = strict_json_object(json_files[0])
            if payload.get("case_count") != len(payload.get("cases", [])):
                errors.append(f"{batch_root.name}: case count mismatch")
            leaks = _forbidden_review_keys(payload)
            if leaks:
                errors.append(f"{batch_root.name}: protected fields leaked")
            for case in payload.get("cases", []):
                source = case.get("source_payload")
                if not isinstance(source, Mapping) or case.get(
                    "source_payload_sha256"
                ) != sha256_bytes(canonical_json_bytes(source)):
                    errors.append(f"{batch_root.name}: source payload hash mismatch")
                if "review" in case and case["review"] != blank_standard_review():
                    errors.append(f"{batch_root.name}: review is not blank")
                if "audit" in case and case["audit"] != blank_proposal_audit():
                    errors.append(f"{batch_root.name}: audit is not blank")
        if report.get("provider_call_count") != 0:
            errors.append("provider_call_count must remain zero")
        if report.get("stage_b_gold_autofill_count") != 0:
            errors.append("Stage B gold autofill must remain zero")
        if report.get("final_glossary_decision") is not None:
            errors.append("final glossary decision must remain null")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return errors


def validate_zip(zip_path: Path, artifact_root: Path) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="followup-zip-check-") as temp_name:
        rebuilt = Path(temp_name) / zip_path.name
        build_deterministic_zip(artifact_root, rebuilt)
        if sha256_file(rebuilt) != sha256_file(zip_path):
            return ["deterministic ZIP mismatch"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path, args.artifact_root))
    print(json.dumps({"errors": errors, "status": "PASS" if not errors else "FAIL"}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
