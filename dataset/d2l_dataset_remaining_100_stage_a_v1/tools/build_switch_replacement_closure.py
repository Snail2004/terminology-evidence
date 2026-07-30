from __future__ import annotations

import argparse
import copy
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    replace_directory,
    seal_integrity,
    seal_record,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    write_checksums,
    write_json,
    write_jsonl,
)


ARTIFACT_NAME = "d2l_dataset_150_stage_a_complete_v1"
POLICY_ID = "d2l-dataset-150-stage-a-complete-v1.0"
CREATED_AT = "2026-07-30T00:00:00Z"
REPLACED_TERM = "switch"
REPLACEMENT_TERM = "hypothesis testing"
REPLACED_SENSE_ID = "d2lce_91002293cea2184b43995f47"
REPLACEMENT_SENSE_ID = "d2lce_bad32719ece6439b4716d093"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_manifest(
    root: Path, allowed_extras: set[str] | None = None
) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError(f"{root.name}: manifest self-hash mismatch")
    extras = allowed_extras or set()
    expected = manifest.get("files")
    if not isinstance(expected, dict):
        raise ValueError(f"{root.name}: manifest inventory is not an object")
    actual = build_file_inventory(root, {"manifest.json"})
    ignored = set(extras)
    if "CHECKSUMS.sha256" not in expected:
        ignored.add("CHECKSUMS.sha256")
    if set(expected) - set(actual) or set(actual) - set(expected) - ignored:
        raise ValueError(f"{root.name}: manifest inventory mismatch")
    for relative_path, expected_record in expected.items():
        actual_record = actual[relative_path]
        if (
            not isinstance(expected_record, Mapping)
            or expected_record.get("sha256") != actual_record.get("sha256")
        ):
            raise ValueError(
                f"{root.name}: manifest hash mismatch for {relative_path}"
            )
    return manifest


def _sentinelized_review(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(payload))
    cases = result.get("cases")
    if not isinstance(cases, list) or len(cases) != 1:
        raise ValueError("replacement review must contain exactly one case")
    if not isinstance(cases[0], dict):
        raise ValueError("replacement review case must be an object")
    cases[0]["review"] = "__REVIEW_SENTINEL__"
    return result


def _validate_completed_review(
    *,
    input_path: Path,
    response_path: Path,
    reviewer_role: str,
) -> tuple[dict[str, Any], bytes, str]:
    expected = strict_json_object(input_path)
    response_path = response_path.resolve(strict=True)
    raw = response_path.read_bytes()
    try:
        completed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{reviewer_role}: invalid UTF-8 JSON") from exc
    if not isinstance(completed, dict):
        raise ValueError(f"{reviewer_role}: response must be an object")
    if _sentinelized_review(expected) != _sentinelized_review(completed):
        raise ValueError(f"{reviewer_role}: immutable source payload changed")
    case = completed["cases"][0]
    if (
        completed.get("reviewer_slot") != reviewer_role
        or case.get("reviewer_slot") != reviewer_role
    ):
        raise ValueError(f"{reviewer_role}: reviewer slot mismatch")
    review = case.get("review")
    if not isinstance(review, Mapping):
        raise ValueError(f"{reviewer_role}: review must be an object")
    expected_accepts = {
        "candidate_set_decision": "ACCEPT",
        "definition_decision": "ACCEPT",
        "evidence_decision": "ACCEPT",
        "part_of_speech_decision": "ACCEPT",
        "scope_decision": "ACCEPT",
        "review_status": "COMPLETE",
        "sense_status": "READY_FOR_CONTRACT_CONSTRUCTION",
    }
    for field, value in expected_accepts.items():
        if review.get(field) != value:
            raise ValueError(f"{reviewer_role}: {field} is not {value}")
    expected_empty_lists = (
        "candidate_replacements",
        "invalid_evidence_context_ids",
        "proposed_split_labels",
    )
    if any(review.get(field) != [] for field in expected_empty_lists):
        raise ValueError(f"{reviewer_role}: ACCEPT review contains repair data")
    expected_empty_text = (
        "corrected_definition_en",
        "corrected_part_of_speech",
        "corrected_scope",
    )
    if any(review.get(field) != "" for field in expected_empty_text):
        raise ValueError(f"{reviewer_role}: ACCEPT review contains corrections")
    notes = review.get("review_notes")
    if not isinstance(notes, str) or not notes.strip():
        raise ValueError(f"{reviewer_role}: review notes are required")
    digest = sha256_bytes(raw)
    if sha256_file(response_path) != digest:
        raise ValueError(f"{reviewer_role}: response changed while captured")
    return completed, raw, digest


def _copy_source_bundle(staging: Path) -> None:
    source_root = staging / "source"
    module_root = Path(__file__).resolve().parent
    project_root = module_root.parent
    for name in (
        "build_switch_replacement_closure.py",
        "validate_switch_replacement_closure.py",
    ):
        destination = source_root / "tools" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module_root / name, destination)
    destination = source_root / "tests" / "test_switch_replacement_closure.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        project_root / "tests" / "test_switch_replacement_closure.py",
        destination,
    )


def _replacement_contract(
    source: Mapping[str, Any],
    reviewer_records: list[Mapping[str, Any]],
    review_hashes: Mapping[str, str],
) -> dict[str, Any]:
    return seal_record(
        {
            "candidates": source["candidates"],
            "definition_en": source["proposed_definition_en"],
            "evidence_contexts": source["evidence_contexts"],
            "final_glossary_decision": None,
            "parent_binding": source["parent_binding"],
            "part_of_speech": source["proposed_part_of_speech"],
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "review_consensus": {
                "decision": "ACCEPT",
                "reviewer_1_result_sha256": review_hashes["reviewer_1"],
                "reviewer_2_result_sha256": review_hashes["reviewer_2"],
                "reviewer_count": 2,
                "reviewer_slots": ["reviewer_1", "reviewer_2"],
            },
            "review_notes": {
                role: reviewer_records[index]["cases"][0]["review"][
                    "review_notes"
                ]
                for index, role in enumerate(("reviewer_1", "reviewer_2"))
            },
            "schema_id": "D2LReplacementEffectiveSenseContractV1",
            "schema_version": "1.0",
            "scope": source["proposed_scope"],
            "sense_id": source["sense_id"],
            "source_payload_sha256": reviewer_records[0]["cases"][0][
                "source_payload_sha256"
            ],
            "source_term": source["source_term"],
            "stage_a_status": "READY_FOR_CONTRACT_CONSTRUCTION",
            "stage_b_gold_label": None,
            "term_id": source["term_id"],
        }
    )


def _source_slot_index(
    stage_b_rows: list[Mapping[str, Any]],
    remaining_rows: list[Mapping[str, Any]],
    replacement_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    stage_b_by_sense: dict[str, Mapping[str, Any]] = {}
    for row in stage_b_rows:
        sense_id = str(row["sense_id"])
        stage_b_by_sense.setdefault(sense_id, row)
    if len(stage_b_by_sense) != 50:
        raise ValueError("Stage B authority must contain 50 unique senses")
    records: list[dict[str, Any]] = []
    for sense_id, row in sorted(stage_b_by_sense.items()):
        records.append(
            seal_record(
                {
                    "approved_child_sense_ids": [],
                    "effective_sense_id": sense_id,
                    "effective_source_term": row["source_term"],
                    "is_replacement": False,
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LStageACompleteSourceSlotRecordV1",
                    "schema_version": "1.0",
                    "source_slot_sense_id": sense_id,
                    "source_slot_term": row["source_term"],
                    "stage_a_status": "READY",
                    "stage_b_status": "COMPLETE",
                }
            )
        )
    for row in remaining_rows:
        is_replacement = row["sense_id"] == REPLACED_SENSE_ID
        if is_replacement:
            if row["source_term"] != REPLACED_TERM or row["stage_a_status"] != "BLOCKED":
                raise ValueError("replacement slot is not the blocked switch record")
            effective_id = replacement_contract["sense_id"]
            effective_term = replacement_contract["source_term"]
            authority_sha = replacement_contract["record_sha256"]
            child_ids: list[str] = []
        else:
            if row["stage_a_status"] != "READY":
                raise ValueError(f"unexpected unresolved slot: {row['source_term']}")
            effective_id = row["sense_id"]
            effective_term = row["source_term"]
            authority_sha = row["record_sha256"]
            child_ids = list(row.get("approved_child_sense_ids", []))
        records.append(
            seal_record(
                {
                    "approved_child_sense_ids": child_ids,
                    "authority_record_sha256": authority_sha,
                    "effective_sense_id": effective_id,
                    "effective_source_term": effective_term,
                    "is_replacement": is_replacement,
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LStageACompleteSourceSlotRecordV1",
                    "schema_version": "1.0",
                    "source_slot_sense_id": row["sense_id"],
                    "source_slot_term": row["source_term"],
                    "stage_a_status": "READY",
                    "stage_b_status": "PENDING",
                }
            )
        )
    records.sort(key=lambda item: item["source_slot_sense_id"])
    if len(records) != 150 or len(
        {item["source_slot_sense_id"] for item in records}
    ) != 150:
        raise ValueError("combined Stage A closure must contain 150 source slots")
    return records


def build_switch_replacement_closure(
    *,
    stage_b_50_root: Path,
    remaining100_root: Path,
    replacement_root: Path,
    reviewer_1_response: Path,
    reviewer_2_response: Path,
    output_root: Path,
    zip_path: Path,
) -> dict[str, Any]:
    stage_b_50_root = stage_b_50_root.resolve(strict=True)
    remaining100_root = remaining100_root.resolve(strict=True)
    replacement_root = replacement_root.resolve(strict=True)
    output_root = output_root.resolve()
    zip_path = zip_path.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    manifests = {
        "stage_b_50": _verify_manifest(stage_b_50_root),
        "remaining100": _verify_manifest(remaining100_root),
        "replacement": _verify_manifest(
            replacement_root,
            {
                "handoff/switch_replacement_reviewer_1.json",
                "handoff/switch_replacement_reviewer_2.json",
            },
        ),
    }
    response_paths = {
        "reviewer_1": reviewer_1_response.resolve(strict=True),
        "reviewer_2": reviewer_2_response.resolve(strict=True),
    }
    if len(set(response_paths.values())) != 2:
        raise ValueError("reviewer responses must use two distinct paths")
    completed_reviews: list[dict[str, Any]] = []
    review_bytes: dict[str, bytes] = {}
    review_hashes: dict[str, str] = {}
    for role in ("reviewer_1", "reviewer_2"):
        completed, raw, digest = _validate_completed_review(
            input_path=replacement_root
            / "review_batches"
            / role
            / "reviewer_input.json",
            response_path=response_paths[role],
            reviewer_role=role,
        )
        completed_reviews.append(completed)
        review_bytes[role] = raw
        review_hashes[role] = digest
    if completed_reviews[0]["cases"][0]["source_payload_sha256"] != completed_reviews[1]["cases"][0]["source_payload_sha256"]:
        raise ValueError("reviewers did not review the same source payload")

    source = strict_json_object(replacement_root / "replacement_source.json")
    if (
        source.get("sense_id") != REPLACEMENT_SENSE_ID
        or source.get("source_term") != REPLACEMENT_TERM
    ):
        raise ValueError("unexpected replacement identity")
    stage_b_rows = strict_jsonl(stage_b_50_root / "stage_b_gold_150.jsonl")
    if len(stage_b_rows) != 150 or len({row["sense_id"] for row in stage_b_rows}) != 50:
        raise ValueError("Stage B authority must contain 50 senses and 150 candidates")
    remaining_rows = strict_jsonl(remaining100_root / "closure_index_100.jsonl")
    if len(remaining_rows) != 100:
        raise ValueError("remaining closure must contain 100 source slots")
    child_rows = strict_jsonl(
        remaining100_root / "approved_child_sense_projections_9.jsonl"
    )
    if len(child_rows) != 9:
        raise ValueError("remaining closure must contain nine split children")
    split_parent_count = sum(
        bool(row.get("approved_child_sense_ids")) for row in remaining_rows
    )
    if split_parent_count != 4:
        raise ValueError("remaining closure must contain four split source slots")

    with tempfile.TemporaryDirectory(
        prefix="dataset-150-stage-a-complete-", dir=output_root.parent
    ) as name:
        staging = Path(name) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        capture_root = staging / "captured_reviews"
        capture_root.mkdir()
        for role in ("reviewer_1", "reviewer_2"):
            (capture_root / f"{role}.json").write_bytes(review_bytes[role])
        write_json(
            staging / "review_input_inventory.json",
            seal_integrity(
                {
                    "files": [
                        {
                            "captured_path": f"captured_reviews/{role}.json",
                            "reviewer_slot": role,
                            "sha256": review_hashes[role],
                            "source_path_name": response_paths[role].name,
                        }
                        for role in ("reviewer_1", "reviewer_2")
                    ],
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LReplacementReviewInputInventoryV1",
                    "schema_version": "1.0",
                }
            ),
        )
        contract = _replacement_contract(
            source, completed_reviews, review_hashes
        )
        write_json(staging / "replacement_effective_sense_contract.json", contract)
        source_slots = _source_slot_index(
            stage_b_rows, remaining_rows, contract
        )
        write_jsonl(staging / "stage_a_source_slot_index_150.jsonl", source_slots)

        updated_terms = set(
            strict_json_object(
                replacement_root / "current_source_term_inventory_150.json"
            )["source_terms_casefolded"]
        )
        if REPLACED_TERM not in updated_terms or REPLACEMENT_TERM in updated_terms:
            raise ValueError("source-term replacement inventory precondition failed")
        updated_terms.remove(REPLACED_TERM)
        updated_terms.add(REPLACEMENT_TERM)
        if len(updated_terms) != 150:
            raise ValueError("updated source-term inventory must contain 150 terms")
        write_json(
            staging / "source_term_inventory_150.json",
            seal_integrity(
                {
                    "policy_id": POLICY_ID,
                    "replaced_source_term": REPLACED_TERM,
                    "replacement_source_term": REPLACEMENT_TERM,
                    "schema_id": "D2LStageACompleteSourceTermInventoryV1",
                    "schema_version": "1.0",
                    "source_term_count": 150,
                    "source_terms_casefolded": sorted(updated_terms),
                }
            ),
        )
        effective_remaining = 100 - split_parent_count + len(child_rows)
        effective_total = 50 + effective_remaining
        write_json(
            staging / "completion_summary.json",
            seal_integrity(
                {
                    "candidate_instance_count": 450,
                    "effective_sense_count": effective_total,
                    "final_glossary_decision": None,
                    "original_source_slot_count": 150,
                    "policy_id": POLICY_ID,
                    "provider_call_count": 0,
                    "replacement_review_consensus": "ACCEPT_2_OF_2",
                    "schema_id": "D2LDataset150StageACompletionSummaryV1",
                    "schema_version": "1.0",
                    "split_child_sense_count": len(child_rows),
                    "split_source_slot_count": split_parent_count,
                    "stage_a_blocked_source_slot_count": 0,
                    "stage_a_ready_source_slot_count": 150,
                    "stage_b_complete_candidate_count": 150,
                    "stage_b_complete_effective_sense_count": 50,
                    "stage_b_pending_candidate_count": 300,
                    "stage_b_pending_effective_sense_count": effective_remaining,
                    "stage_b_gold_autofill_count": 0,
                    "status": "DATASET_150_SOURCE_SLOTS_STAGE_A_COMPLETE_ZERO_PROVIDER",
                }
            ),
        )
        write_json(
            staging / "authority.json",
            seal_integrity(
                {
                    "manifests": {
                        key: {
                            "physical_sha256": sha256_file(root / "manifest.json"),
                            "self_sha256": manifests[key]["manifest_sha256"],
                        }
                        for key, root in {
                            "stage_b_50": stage_b_50_root,
                            "remaining100": remaining100_root,
                            "replacement": replacement_root,
                        }.items()
                    },
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LDataset150StageACompletionAuthorityV1",
                    "schema_version": "1.0",
                }
            ),
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L Dataset Stage A completion\n\n"
            "- Source slots resolved at Stage A: 150/150.\n"
            "- Replacement: `hypothesis testing` replaces blocked `switch`.\n"
            "- Replacement consensus: 2/2 ACCEPT.\n"
            "- Effective senses after four reviewed splits: 155.\n"
            "- Candidate instances remain: 450.\n"
            "- Stage B complete: 50 effective senses / 150 candidates.\n"
            "- Stage B pending: 105 effective senses / 300 candidates.\n"
            "- Provider calls: 0.\n"
            "- Final glossary decision: null.\n",
            encoding="utf-8",
            newline="\n",
        )
        _copy_source_bundle(staging)
        files = build_file_inventory(
            staging, excluded={"CHECKSUMS.sha256", "manifest.json"}
        )
        manifest = {
            "artifact_name": ARTIFACT_NAME,
            "created_at": CREATED_AT,
            "file_count": len(files),
            "files": files,
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "schema_id": "D2LDataset150StageACompleteManifestV1",
            "schema_version": "1.0",
            "status": "DATASET_150_SOURCE_SLOTS_STAGE_A_COMPLETE_ZERO_PROVIDER",
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from .validate_switch_replacement_closure import validate_artifact

        errors = validate_artifact(staging)
        if errors:
            raise ValueError("; ".join(errors))
        replace_directory(staging, output_root)
    build_deterministic_zip(output_root, zip_path)
    return {
        "artifact_root": str(output_root),
        "manifest_sha256": strict_json_object(output_root / "manifest.json")[
            "manifest_sha256"
        ],
        "status": "DATASET_150_SOURCE_SLOTS_STAGE_A_COMPLETE_ZERO_PROVIDER",
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-b-50-root", type=Path, required=True)
    parser.add_argument("--remaining100-root", type=Path, required=True)
    parser.add_argument("--replacement-root", type=Path, required=True)
    parser.add_argument("--reviewer-1-response", type=Path, required=True)
    parser.add_argument("--reviewer-2-response", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path, required=True)
    args = parser.parse_args()
    result = build_switch_replacement_closure(
        stage_b_50_root=args.stage_b_50_root,
        remaining100_root=args.remaining100_root,
        replacement_root=args.replacement_root,
        reviewer_1_response=args.reviewer_1_response,
        reviewer_2_response=args.reviewer_2_response,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
