from __future__ import annotations

import argparse
import tempfile
from collections import Counter
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

from .followup_result_handoffs import blank_proposal_repair


EXPECTED_ROUTING = {
    "routing/high_risk_approved_6.jsonl": 6,
    "routing/high_risk_revision_required_4.jsonl": 4,
    "routing/prior_accepted_blind_23.jsonl": 23,
    "routing/prior_blocked_1.jsonl": 1,
    "routing/reaudit_ready_12.jsonl": 12,
}


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


def _validate_repair_handoffs(
    root: Path, revision_ids: set[str], errors: list[str]
) -> None:
    batches = sorted((root / "repair_batches").glob("*"))
    expected = {
        "high_risk_proposal_repair_reviewer_2": ("reviewer_2", 3),
        "high_risk_proposal_repair_reviewer_3": ("reviewer_3", 1),
    }
    if {batch.name for batch in batches} != set(expected):
        errors.append("repair batch identity mismatch")
        return
    seen: set[str] = set()
    for batch in batches:
        reviewer, count = expected[batch.name]
        payload = strict_json_object(batch / "repair_input.json")
        if payload.get("reviewer_slot") != reviewer:
            errors.append(f"{batch.name}: reviewer slot mismatch")
        cases = payload.get("cases", [])
        if payload.get("case_count") != count or len(cases) != count:
            errors.append(f"{batch.name}: case count mismatch")
        for case in cases:
            sense_id = str(case.get("sense_id"))
            seen.add(sense_id)
            if case.get("source_result_role") != reviewer:
                errors.append(f"{sense_id}: proposal author mismatch")
            if case.get("repair") != blank_proposal_repair(
                case.get("original_proposal", {})
            ):
                errors.append(f"{sense_id}: repair input is not pristine")
        handoff_zip = root / "handoff" / f"{batch.name}.zip"
        with tempfile.TemporaryDirectory(prefix="followup-result-zip-") as temp_name:
            rebuilt = Path(temp_name) / "rebuilt.zip"
            build_deterministic_zip(batch, rebuilt)
            if not handoff_zip.is_file() or sha256_file(handoff_zip) != sha256_file(
                rebuilt
            ):
                errors.append(f"{batch.name}: handoff ZIP mismatch")
    if seen != revision_ids:
        errors.append("repair handoffs do not cover exactly the revision-required senses")


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
        if inventory.get("file_count") != 6 or len(inventory_rows) != 6:
            errors.append("captured review inventory must contain six files")
        for row in inventory_rows:
            path = root / "captures" / row["captured_relative_path"]
            if not path.is_file() or sha256_file(path) != row["sha256"]:
                errors.append(f"captured result mismatch: {row.get('source_file_name')}")

        routed_ids: list[str] = []
        revision_ids: set[str] = set()
        routing_records: dict[str, list[dict[str, Any]]] = {}
        for relative, expected_count in EXPECTED_ROUTING.items():
            records = strict_jsonl(root / relative)
            routing_records[relative] = records
            if len(records) != expected_count:
                errors.append(f"routing count mismatch: {relative}")
            for record in records:
                if not verify_record(record):
                    errors.append(f"routing record hash mismatch: {record.get('sense_id')}")
                _validate_zero_provider(record, relative, errors)
                sense_id = str(record.get("sense_id"))
                routed_ids.append(sense_id)
                if relative.endswith("revision_required_4.jsonl"):
                    revision_ids.add(sense_id)
        if len(routed_ids) != 46 or len(set(routed_ids)) != 46:
            errors.append("follow-up routing must contain 46 unique source senses")

        closure = strict_jsonl(root / "closure_index_100.jsonl")
        closure_ids = [str(row.get("sense_id")) for row in closure]
        if len(closure) != 100 or len(set(closure_ids)) != 100:
            errors.append("closure index must contain 100 unique senses")
        statuses = Counter(str(row.get("stage_a_status")) for row in closure)
        if statuses != Counter({"READY": 95, "REVISION_REQUIRED": 4, "BLOCKED": 1}):
            errors.append("closure status distribution mismatch")
        for record in closure:
            if not verify_record(record):
                errors.append(f"closure record hash mismatch: {record.get('sense_id')}")
            _validate_zero_provider(record, "closure", errors)

        authority_index: dict[tuple[str, str], tuple[str, str, str]] = {}

        def add_authority(
            kind: str,
            records: list[dict[str, Any]],
            *,
            hash_field: str | None,
            source_hash_field: str,
            nested_term: bool = False,
        ) -> None:
            for row in records:
                sense_id = str(row.get("sense_id"))
                record_hash = (
                    str(row.get(hash_field))
                    if hash_field is not None
                    else sha256_bytes(canonical_json_bytes(row))
                )
                source_term = (
                    str(row.get("source_payload", {}).get("source_term"))
                    if nested_term
                    else str(row.get("source_term"))
                )
                key = (kind, sense_id)
                if key in authority_index:
                    errors.append(f"duplicate closure authority: {kind}/{sense_id}")
                authority_index[key] = (
                    record_hash,
                    str(row.get(source_hash_field)),
                    source_term,
                )

        r3_records = strict_jsonl(
            root / "references" / "direct_r3_agreement_18.jsonl"
        )
        adjudication_records = strict_jsonl(
            root / "references" / "direct_adjudication_36.jsonl"
        )
        if len(r3_records) != 18 or any(
            not verify_record(row, "agreement_record_sha256") for row in r3_records
        ):
            errors.append("direct R3 agreement references are invalid")
        if len(adjudication_records) != 36:
            errors.append("direct adjudication reference count mismatch")
        add_authority(
            "R3_DUAL_AGREEMENT",
            r3_records,
            hash_field="agreement_record_sha256",
            source_hash_field="source_payload_sha256",
            nested_term=True,
        )
        add_authority(
            "REVIEWER_3_ADJUDICATION",
            adjudication_records,
            hash_field=None,
            source_hash_field="source_payload_sha256",
        )
        add_authority(
            "PRIOR_BLIND_AUDIT",
            routing_records["routing/prior_accepted_blind_23.jsonl"],
            hash_field="record_sha256",
            source_hash_field="source_payload_sha256",
        )
        add_authority(
            "PRIOR_INSUFFICIENT_EVIDENCE_BLOCK",
            routing_records["routing/prior_blocked_1.jsonl"],
            hash_field="record_sha256",
            source_hash_field="parent_source_payload_sha256",
        )
        add_authority(
            "FOLLOWUP_BLIND_REAUDIT",
            routing_records["routing/reaudit_ready_12.jsonl"],
            hash_field="record_sha256",
            source_hash_field="source_payload_sha256",
        )
        add_authority(
            "HIGH_RISK_PROPOSAL_AUDIT",
            [
                *routing_records["routing/high_risk_approved_6.jsonl"],
                *routing_records[
                    "routing/high_risk_revision_required_4.jsonl"
                ],
            ],
            hash_field="record_sha256",
            source_hash_field="source_payload_sha256",
        )
        if len(authority_index) != 100:
            errors.append("closure authority index must contain 100 records")
        for row in closure:
            key = (str(row.get("authority_kind")), str(row.get("sense_id")))
            expected = authority_index.get(key)
            actual = (
                str(row.get("authority_record_sha256")),
                str(row.get("source_payload_sha256")),
                str(row.get("source_term")),
            )
            if expected != actual:
                errors.append(f"closure authority binding mismatch: {row.get('sense_id')}")
        _validate_repair_handoffs(root, revision_ids, errors)
        for name in (
            "ASSIGNMENT.md",
            "REVIEWER_2_MESSAGE.md",
            "REVIEWER_3_MESSAGE.md",
        ):
            if not (root / "handoff" / name).is_file():
                errors.append(f"missing handoff instruction: {name}")
        if report.get("ready_stage_a_source_sense_count") != 95:
            errors.append("validation report ready count mismatch")
        if report.get("high_risk_revision_required_case_count") != 4:
            errors.append("validation report revision count mismatch")
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
