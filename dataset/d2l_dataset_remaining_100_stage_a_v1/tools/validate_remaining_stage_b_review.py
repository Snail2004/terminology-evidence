from __future__ import annotations

import argparse
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
    verify_integrity,
    verify_record,
)


EXPECTED_STATUS = "READY_FOR_STAGE_B_DUAL_REVIEW_ZERO_PROVIDER"
BLANK_REVIEW = {
    "allowed_scope": "",
    "candidate_gold_label": "",
    "positive_context_refs": [],
    "reason_codes": [],
    "rejected_variants": [],
    "review_notes": "",
    "review_status": "",
    "validated_variants": [],
    "vietnamese_evidence_refs": [],
}
FORBIDDEN_REVIEW_KEYS = {
    "applicability",
    "candidate_rank",
    "final_glossary_decision_source",
    "formation_method",
    "formation_provenance",
    "intended_role",
    "winner",
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


def _scan_forbidden_keys(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key in FORBIDDEN_REVIEW_KEYS:
                errors.append(f"forbidden reviewer-facing key: {child_path}")
            if key == "provider_call_count" and child != 0:
                errors.append(f"nonzero provider call count: {child_path}")
            if key == "final_gold_label" and child is not None:
                errors.append(f"non-null final gold label: {child_path}")
            if key == "final_glossary_decision" and child is not None:
                errors.append(f"non-null final glossary decision: {child_path}")
            _scan_forbidden_keys(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_forbidden_keys(child, f"{path}[{index}]", errors)


def _validate_full_payload(
    payload: Mapping[str, Any], reviewer_slot: str, errors: list[str]
) -> dict[str, Mapping[str, Any]]:
    prefix = reviewer_slot
    if (
        payload.get("reviewer_slot") != reviewer_slot
        or payload.get("case_count") != 300
        or payload.get("effective_sense_count") != 105
        or payload.get("batch_count") != 10
    ):
        errors.append(f"{prefix}: full input counts/slot mismatch")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 300:
        errors.append(f"{prefix}: cases must contain 300 rows")
        return {}
    candidate_map: dict[str, Mapping[str, Any]] = {}
    source_binding = []
    for index, case in enumerate(cases):
        case_prefix = f"{prefix}/case_{index + 1}"
        if not isinstance(case, Mapping) or not verify_record(case, "case_sha256"):
            errors.append(f"{case_prefix}: case hash mismatch")
            continue
        if case.get("reviewer_slot") != reviewer_slot:
            errors.append(f"{case_prefix}: reviewer slot mismatch")
        if case.get("review") != BLANK_REVIEW:
            errors.append(f"{case_prefix}: review is not blank")
        source = case.get("source_payload")
        if not isinstance(source, Mapping):
            errors.append(f"{case_prefix}: source payload is invalid")
            continue
        if case.get("source_payload_sha256") != sha256_bytes(
            canonical_json_bytes(source)
        ):
            errors.append(f"{case_prefix}: source payload hash mismatch")
        candidate_id = source.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id in candidate_map:
            errors.append(f"{case_prefix}: duplicate/invalid candidate ID")
        else:
            candidate_map[candidate_id] = source
        contexts = source.get("contexts")
        if not isinstance(contexts, list) or not contexts:
            errors.append(f"{case_prefix}: contexts are missing")
        source_binding.append(
            {"case_id": case.get("case_id"), "case_sha256": case.get("case_sha256")}
        )
    if payload.get("source_input_sha256") != sha256_bytes(
        canonical_json_bytes(source_binding)
    ):
        errors.append(f"{prefix}: source input binding mismatch")
    if len(candidate_map) != 300:
        errors.append(f"{prefix}: candidate coverage is not 300/300")
    _scan_forbidden_keys(payload, prefix, errors)
    return candidate_map


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
    expected_counts = {
        "batch": 10,
        "candidate": 300,
        "effective_sense": 105,
        "reviewer": 2,
        "reviewer_case_each": 300,
        "stage_b_gold_autofill": 0,
    }
    if manifest.get("counts") != expected_counts:
        errors.append("manifest counts mismatch")
    _validate_checksums(root, errors)

    for name, schema in {
        "authority.json": "D2LRemainingStageBReviewAuthorityV1",
        "batch_index.json": "D2LRemainingStageBBatchIndexV1",
        "release_summary.json": "D2LRemainingStageBReviewSummaryV1",
    }.items():
        try:
            payload = strict_json_object(root / name)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if payload.get("schema_id") != schema or not verify_integrity(payload):
            errors.append(f"{name}: integrity/schema mismatch")

    try:
        senses = strict_jsonl(root / "effective_senses_105.jsonl")
        candidates = strict_jsonl(root / "candidate_instances_300.jsonl")
        contexts = strict_jsonl(root / "contexts_selected.jsonl")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
        return errors
    if len(senses) != 105 or len({row.get("effective_sense_id") for row in senses}) != 105:
        errors.append("effective sense count/identity mismatch")
    if any(not verify_record(row) for row in senses):
        errors.append("effective sense self-hash mismatch")
    if len(candidates) != 300 or len({row.get("candidate_id") for row in candidates}) != 300:
        errors.append("candidate count/identity mismatch")
    candidate_ids_by_sense: dict[str, set[str]] = {}
    for row in candidates:
        candidate_ids_by_sense.setdefault(str(row.get("effective_sense_id")), set()).add(
            str(row.get("candidate_id"))
        )
    context_ids = {row.get("context_id") for row in contexts}
    if len(context_ids) != len(contexts):
        errors.append("context IDs are not unique")
    for sense in senses:
        if set(sense.get("candidate_ids", [])) != candidate_ids_by_sense.get(
            str(sense.get("effective_sense_id")), set()
        ):
            errors.append(f"candidate binding mismatch: {sense.get('effective_sense_id')}")
        if not set(sense.get("context_ids", [])) <= context_ids:
            errors.append(f"context binding mismatch: {sense.get('effective_sense_id')}")
    if Counter(len(values) for values in candidate_ids_by_sense.values()) != {
        1: 6,
        2: 3,
        3: 96,
    }:
        errors.append("candidate-per-effective-sense distribution mismatch")

    batch_index = strict_json_object(root / "batch_index.json")
    batches = batch_index.get("batches", [])
    if (
        not isinstance(batches, list)
        or len(batches) != 10
        or any(row.get("candidate_count") != 30 for row in batches)
        or sum(row.get("effective_sense_count", 0) for row in batches) != 105
    ):
        errors.append("batch index distribution mismatch")

    reviewer_maps: dict[str, dict[str, Mapping[str, Any]]] = {}
    for role in ("reviewer_1", "reviewer_2"):
        try:
            payload = strict_json_object(root / f"{role}_full_input.json")
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        reviewer_maps[role] = _validate_full_payload(payload, role, errors)
        handoff = root / "handoff" / f"{role}.zip"
        if not handoff.is_file():
            errors.append(f"missing reviewer handoff: {role}")
    if set(reviewer_maps) == {"reviewer_1", "reviewer_2"}:
        left = reviewer_maps["reviewer_1"]
        right = reviewer_maps["reviewer_2"]
        if set(left) != set(right) or set(left) != {
            row["candidate_id"] for row in candidates
        }:
            errors.append("reviewer candidate inventories differ")
        else:
            for candidate_id in left:
                if left[candidate_id] != right[candidate_id]:
                    errors.append(
                        f"reviewer source payload differs: {candidate_id}"
                    )
                    break
    _scan_forbidden_keys(
        {
            "reviewer_1": strict_json_object(root / "reviewer_1_full_input.json"),
            "reviewer_2": strict_json_object(root / "reviewer_2_full_input.json"),
        },
        "reviewer_inputs",
        errors,
    )
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
