from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_record,
        write_checksums,
        write_csv,
        write_json,
        write_jsonl,
    )
    from .spec import (
        ADJUDICATED_CASES,
        ADJUDICATION_CSV_FIELDS,
        ADJUDICATION_INPUT_SHA256,
        ADJUDICATION_OUTPUT_FIELDS,
        ADJUDICATION_SOURCE_FIELDS,
        ARTIFACT_NAME,
        CREATED_AT_DEFAULT,
        EXPECTED_CASES,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        POLICY_ID,
        SOURCE_RESULT_ARTIFACT_NAME,
        SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256,
        SOURCE_RESULT_MANIFEST_SHA256,
        SOURCE_RESULT_ZIP_SHA256,
        SOURCE_REVIEW_ARTIFACT_NAME,
        SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        SOURCE_REVIEW_MANIFEST_SHA256,
        SOURCE_REVIEW_ZIP_SHA256,
        STATUS,
        SUMMARY_CSV_FIELDS,
        stable_id,
    )
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_record,
        write_checksums,
        write_csv,
        write_json,
        write_jsonl,
    )
    from spec import (  # type: ignore
        ADJUDICATED_CASES,
        ADJUDICATION_CSV_FIELDS,
        ADJUDICATION_INPUT_SHA256,
        ADJUDICATION_OUTPUT_FIELDS,
        ADJUDICATION_SOURCE_FIELDS,
        ARTIFACT_NAME,
        CREATED_AT_DEFAULT,
        EXPECTED_CASES,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        POLICY_ID,
        SOURCE_RESULT_ARTIFACT_NAME,
        SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256,
        SOURCE_RESULT_MANIFEST_SHA256,
        SOURCE_RESULT_ZIP_SHA256,
        SOURCE_REVIEW_ARTIFACT_NAME,
        SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        SOURCE_REVIEW_MANIFEST_SHA256,
        SOURCE_REVIEW_ZIP_SHA256,
        STATUS,
        SUMMARY_CSV_FIELDS,
        stable_id,
    )


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_manifest(
    root: Path,
    *,
    artifact_name: str,
    expected_self: str,
    expected_physical: str,
) -> dict[str, Any]:
    path = root / "manifest.json"
    if sha256_file(path) != expected_physical:
        raise ValueError(f"physical manifest hash mismatch: {artifact_name}")
    manifest = strict_json_object(path)
    if manifest.get("artifact_name") != artifact_name:
        raise ValueError(f"artifact identity mismatch: {artifact_name}")
    if manifest.get("manifest_sha256") != expected_self:
        raise ValueError(f"declared manifest hash mismatch: {artifact_name}")
    if _manifest_self_hash(manifest) != expected_self:
        raise ValueError(f"manifest self hash mismatch: {artifact_name}")
    return manifest


def _verify_manifest_file(root: Path, manifest: Mapping[str, Any], relative: str) -> Path:
    metadata = manifest.get("files", {}).get(relative)
    if not isinstance(metadata, Mapping):
        raise ValueError(f"manifest omits required file: {relative}")
    path = root / relative
    if sha256_file(path) != metadata.get("sha256"):
        raise ValueError(f"manifest-bound file drift: {relative}")
    return path


def _csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def _load_completed_adjudication(
    path: Path, source_result_root: Path
) -> dict[str, dict[str, str]]:
    path = path.resolve(strict=True)
    if sha256_file(path) != ADJUDICATION_INPUT_SHA256:
        raise ValueError("completed adjudication input hash mismatch")
    source_path = source_result_root / "adjudication_template_2.csv"
    if _csv_headers(path) != list(ADJUDICATION_CSV_FIELDS):
        raise ValueError("completed adjudication header mismatch")
    completed = read_csv(path)
    source = {row["review_case_id"]: row for row in read_csv(source_path)}
    if len(completed) != 2 or len({row.get("review_case_id") for row in completed}) != 2:
        raise ValueError("completed adjudication must contain two unique rows")
    by_case: dict[str, dict[str, str]] = {}
    for row in completed:
        case_id = row.get("review_case_id", "")
        expected = source.get(case_id)
        if expected is None:
            raise ValueError(f"unknown adjudication case: {case_id}")
        for field in (*ADJUDICATION_SOURCE_FIELDS, "source_payload_sha256"):
            if row.get(field, "") != expected.get(field, ""):
                raise ValueError(f"adjudication source drift: {case_id}:{field}")
        payload = {field: row[field] for field in ADJUDICATION_SOURCE_FIELDS}
        if sha256_bytes(canonical_json_bytes(payload)) != row["source_payload_sha256"]:
            raise ValueError(f"adjudication source self hash mismatch: {case_id}")
        if row.get("adjudication_status") != "COMPLETE":
            raise ValueError(f"adjudication is incomplete: {case_id}")
        if not row.get("adjudication_notes", "").strip():
            raise ValueError(f"adjudication notes are required: {case_id}")
        key = (row["source_term"], row["split_label"])
        if key == ("Adam", "NO_SPLIT"):
            if row["adjudicated_definition_decision"] != "REVISE":
                raise ValueError("Adam adjudication must resolve the definition revision")
            if not row["adjudicated_definition_en"].strip():
                raise ValueError("Adam adjudication omits the final definition")
            if row["adjudicated_candidate_set_decision"] != "ACCEPT":
                raise ValueError("Adam candidate set must remain accepted")
            if row["adjudicated_candidate_2_vi"].strip():
                raise ValueError("Adam adjudication unexpectedly replaces candidate 2")
        elif key == ("statistical power", "NO_SPLIT"):
            if row["adjudicated_definition_decision"] != "ACCEPT":
                raise ValueError("statistical power definition must remain accepted")
            if row["adjudicated_definition_en"].strip():
                raise ValueError("accepted statistical power definition has replacement text")
            if row["adjudicated_candidate_set_decision"] != "REVISE":
                raise ValueError("statistical power candidate set must be revised")
            replacement = row["adjudicated_candidate_2_vi"].strip()
            if not replacement:
                raise ValueError("statistical power candidate 2 replacement is missing")
            original = row["candidate_targets_vi"].split("|")
            if len(original) != 3 or replacement.casefold() in {
                original[0].casefold(),
                original[2].casefold(),
            }:
                raise ValueError("statistical power replacement is not distinct")
        else:
            raise ValueError(f"unexpected adjudication case: {key}")
        by_case[case_id] = row
    if {(row["source_term"], row["split_label"]) for row in completed} != ADJUDICATED_CASES:
        raise ValueError("completed adjudication case identities mismatch")
    return by_case


def _load_sources(
    source_review_root: Path,
    source_result_root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    review_manifest = _verify_manifest(
        source_review_root,
        artifact_name=SOURCE_REVIEW_ARTIFACT_NAME,
        expected_self=SOURCE_REVIEW_MANIFEST_SHA256,
        expected_physical=SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
    )
    result_manifest = _verify_manifest(
        source_result_root,
        artifact_name=SOURCE_RESULT_ARTIFACT_NAME,
        expected_self=SOURCE_RESULT_MANIFEST_SHA256,
        expected_physical=SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256,
    )
    proposals = strict_jsonl(
        _verify_manifest_file(
            source_review_root, review_manifest, "repair_sense_proposals_5.jsonl"
        )
    )
    candidates = strict_jsonl(
        _verify_manifest_file(
            source_review_root, review_manifest, "candidate_proposals_15.jsonl"
        )
    )
    consensus = strict_jsonl(
        _verify_manifest_file(
            source_result_root, result_manifest, "consensus_3_of_3_3.jsonl"
        )
    )
    if len(proposals) != 5 or len(candidates) != 15 or len(consensus) != 3:
        raise ValueError("source review/result cardinality mismatch")
    for row in proposals:
        if not verify_record(row, "sense_proposal_sha256"):
            raise ValueError(f"sense proposal self hash mismatch: {row.get('review_case_id')}")
    for row in candidates:
        if not verify_record(row, "candidate_proposal_sha256"):
            raise ValueError(f"candidate proposal self hash mismatch: {row.get('candidate_id')}")
    consensus_by_case = {row["review_case_id"]: row for row in consensus}
    for row in consensus:
        if not verify_record(row, "consensus_record_sha256"):
            raise ValueError(f"consensus record self hash mismatch: {row.get('review_case_id')}")
    return review_manifest, result_manifest, proposals, candidates, consensus_by_case


def _assert_common_review_acceptance(record: Mapping[str, Any]) -> None:
    votes = record.get("reviewer_votes")
    if not isinstance(votes, list) or len(votes) != 3:
        raise ValueError("review record must contain three votes")
    for vote in votes:
        for field in (
            "part_of_speech_decision",
            "scope_decision",
            "context_evidence_decision",
        ):
            if vote.get(field) != "ACCEPT":
                raise ValueError(f"review record has unresolved {field}")


def _build_resolved_records(
    proposals: list[Mapping[str, Any]],
    source_candidates: list[Mapping[str, Any]],
    consensus_by_case: Mapping[str, Mapping[str, Any]],
    adjudication_by_case: Mapping[str, Mapping[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    source_candidates_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in source_candidates:
        source_candidates_by_sense.setdefault(candidate["output_sense_id"], []).append(
            candidate
        )
    resolved_senses: list[dict[str, Any]] = []
    resolved_candidates: list[dict[str, Any]] = []
    summaries: list[dict[str, str]] = []
    for proposal in sorted(proposals, key=lambda row: row["review_case_id"]):
        case_id = proposal["review_case_id"]
        key = (proposal["source_term"], proposal["split_label"])
        if key not in EXPECTED_CASES:
            raise ValueError(f"unexpected source proposal case: {key}")
        if case_id in consensus_by_case:
            review_record = consensus_by_case[case_id]
            _assert_common_review_acceptance(review_record)
            decisions = review_record.get("consensus_decisions")
            if not isinstance(decisions, Mapping):
                raise ValueError(f"consensus decision projection is missing: {case_id}")
            if any(
                decisions.get(field) != "ACCEPT"
                for field in (
                    "definition_decision",
                    "part_of_speech_decision",
                    "scope_decision",
                    "context_evidence_decision",
                    "candidate_set_decision",
                )
            ):
                raise ValueError(f"consensus case is not fully accepted: {case_id}")
            definition_en = proposal["proposed_definition_en"]
            resolution_method = "CONSENSUS_3_OF_3"
            resolution_sha256 = review_record["consensus_record_sha256"]
            candidate_replacement = None
        else:
            adjudication = adjudication_by_case.get(case_id)
            if adjudication is None:
                raise ValueError(f"review resolution is missing: {case_id}")
            definition_en = (
                adjudication["adjudicated_definition_en"]
                if adjudication["adjudicated_definition_decision"] == "REVISE"
                else proposal["proposed_definition_en"]
            )
            resolution_method = "ADJUDICATED"
            resolution_sha256 = sha256_bytes(
                canonical_json_bytes(
                    {
                        field: adjudication[field]
                        for field in (*ADJUDICATION_OUTPUT_FIELDS, "source_payload_sha256")
                    }
                )
            )
            candidate_replacement = (
                adjudication["adjudicated_candidate_2_vi"].strip()
                if adjudication["adjudicated_candidate_set_decision"] == "REVISE"
                else None
            )

        candidate_rows = sorted(
            source_candidates_by_sense[proposal["output_sense_id"]],
            key=lambda row: row["candidate_slot"],
        )
        if len(candidate_rows) != 3:
            raise ValueError(f"source candidate count is not three: {case_id}")
        reviewed_ids: list[str] = []
        reviewed_targets: list[str] = []
        for source in candidate_rows:
            target = source["candidate_target_vi"]
            candidate_id = source["candidate_id"]
            candidate_resolution = "ACCEPTED_UNCHANGED"
            if candidate_replacement and source["candidate_slot"] == "CANDIDATE_2":
                target = candidate_replacement
                candidate_id = stable_id(
                    "candidate_", proposal["output_sense_id"], target, "v1"
                )
                candidate_resolution = "REPLACED_BY_ADJUDICATION"
            reviewed_ids.append(candidate_id)
            reviewed_targets.append(target)
            resolved_candidates.append(
                seal_record(
                    {
                        "schema_id": "D2LTargetedRepairReviewedCandidateV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        "candidate_id": candidate_id,
                        "candidate_slot": source["candidate_slot"],
                        "candidate_target_vi": target,
                        "output_sense_id": proposal["output_sense_id"],
                        "parent_sense_id": proposal["parent_sense_id"],
                        "source_term": proposal["source_term"],
                        "split_label": proposal["split_label"],
                        "candidate_resolution": candidate_resolution,
                        "source_candidate_id": source["candidate_id"],
                        "source_candidate_proposal_sha256": source[
                            "candidate_proposal_sha256"
                        ],
                        "review_case_id": case_id,
                        "review_resolution_sha256": resolution_sha256,
                        "human_review_status": "COMPLETE",
                        "provider_call_count": 0,
                        "official_contract_emitted": False,
                        "final_glossary_decision": None,
                    },
                    "reviewed_candidate_sha256",
                )
            )
        if len({target.casefold() for target in reviewed_targets}) != 3:
            raise ValueError(f"resolved candidates are not distinct: {case_id}")
        resolved_senses.append(
            seal_record(
                {
                    "schema_id": "D2LTargetedRepairReviewedSenseV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "review_case_id": case_id,
                    "output_sense_id": proposal["output_sense_id"],
                    "parent_sense_id": proposal["parent_sense_id"],
                    "parent_term_id": proposal["parent_term_id"],
                    "source_term": proposal["source_term"],
                    "split": proposal["split"],
                    "split_label": proposal["split_label"],
                    "definition_en": definition_en,
                    "part_of_speech": proposal["proposed_part_of_speech"],
                    "scope": proposal["proposed_scope"],
                    "evidence_context_ids": proposal["evidence_context_ids"],
                    "candidate_ids": reviewed_ids,
                    "candidate_targets_vi": reviewed_targets,
                    "resolution_method": resolution_method,
                    "review_resolution_sha256": resolution_sha256,
                    "source_sense_proposal_sha256": proposal[
                        "sense_proposal_sha256"
                    ],
                    "review_status": "COMPLETE",
                    "provider_call_count": 0,
                    "official_contract_emitted": False,
                    "final_glossary_decision": None,
                },
                "reviewed_sense_sha256",
            )
        )
        summaries.append(
            {
                "review_case_id": case_id,
                "output_sense_id": proposal["output_sense_id"],
                "source_term": proposal["source_term"],
                "split_label": proposal["split_label"],
                "definition_en": definition_en,
                "part_of_speech": proposal["proposed_part_of_speech"],
                "scope": proposal["proposed_scope"],
                "candidate_1_vi": reviewed_targets[0],
                "candidate_2_vi": reviewed_targets[1],
                "candidate_3_vi": reviewed_targets[2],
                "resolution_method": resolution_method,
                "review_status": "COMPLETE",
            }
        )
    if len(resolved_senses) != 5 or len(resolved_candidates) != 15:
        raise ValueError("resolved output cardinality mismatch")
    return resolved_senses, resolved_candidates, summaries


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/build_complete_review.py",
        "tools/validate_complete_review.py",
        "tests/test_complete_review.py",
    ):
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"release source file is missing: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _write_metadata(staging: Path, created_at: str) -> None:
    report = """# Completed targeted Stage A review - 5 senses

All five targeted repair cases have complete review outcomes.

- 3 cases: exact agreement from all three reviewers.
- 2 cases: completed adjudication.
- 1 candidate replacement: statistical power candidate 2 is now
  `độ mạnh của phép kiểm định`.
- 1 definition revision: Adam now has the adjudicated adaptive first/second
  moment definition.

This is a Dataset Stage A review-complete artifact. It is not a final glossary
decision, an official contract package, Stage B gold, or provider output.
"""
    (staging / "REVIEW_COMPLETE_REPORT.md").write_text(
        report, encoding="utf-8", newline="\n"
    )
    write_json(
        staging / "lineage.json",
        seal_integrity(
            {
                "schema_id": "D2LTargetedRepairReviewCompleteLineageV1",
                "schema_version": "1.0.0",
                "source_review_artifact": SOURCE_REVIEW_ARTIFACT_NAME,
                "source_review_manifest_sha256": SOURCE_REVIEW_MANIFEST_SHA256,
                "source_review_manifest_physical_sha256": SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
                "source_review_zip_sha256": SOURCE_REVIEW_ZIP_SHA256,
                "source_result_artifact": SOURCE_RESULT_ARTIFACT_NAME,
                "source_result_manifest_sha256": SOURCE_RESULT_MANIFEST_SHA256,
                "source_result_manifest_physical_sha256": SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256,
                "source_result_zip_sha256": SOURCE_RESULT_ZIP_SHA256,
                "completed_adjudication_sha256": ADJUDICATION_INPUT_SHA256,
                "canonical_main_dataset_authority": {
                    "main_commit": MAIN_DATASET_AUTHORITY_COMMIT,
                    "manifest_sha256": MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
                    "accepted_zip_sha256": MAIN_DATASET_AUTHORITY_ZIP_SHA256,
                    "relationship": "SEPARATE_TARGETED_REPAIR_REVIEW_ARTIFACT",
                },
                "provider_call_count": 0,
                "final_glossary_decision": None,
            }
        ),
    )
    write_json(
        staging / "review_complete_summary.json",
        seal_integrity(
            {
                "schema_id": "D2LTargetedRepairReviewCompleteSummaryV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "counts": {
                    "reviewed_sense": 5,
                    "reviewed_candidate": 15,
                    "review_context": 25,
                    "consensus_3_of_3": 3,
                    "adjudicated": 2,
                    "candidate_replacement": 1,
                },
                "provider_call_count": 0,
                "official_contract_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
                "created_at": created_at,
            }
        ),
    )
    write_json(
        staging / "environment.json",
        {
            "schema_id": "D2LTargetedRepairReviewCompleteEnvironmentV1",
            "created_at": created_at,
            "network_calls": 0,
            "provider_calls": 0,
        },
    )
    (staging / "commands.txt").write_text(
        "python -B source/tools/validate_complete_review.py --artifact-root .\n",
        encoding="ascii",
        newline="\n",
    )
    (staging / "junit.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testsuite name="targeted-repair-review-complete" tests="1" failures="0" '
        'errors="0" skipped="0"><testcase classname="release" '
        'name="internal_validation"/></testsuite>\n',
        encoding="utf-8",
        newline="\n",
    )


def build_complete_review(
    *,
    source_review_root: Path,
    source_result_root: Path,
    adjudication_path: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    source_review_root = source_review_root.resolve(strict=True)
    source_result_root = source_result_root.resolve(strict=True)
    output_root = output_root.resolve()
    (
        review_manifest,
        result_manifest,
        proposals,
        source_candidates,
        consensus_by_case,
    ) = _load_sources(source_review_root, source_result_root)
    adjudication_by_case = _load_completed_adjudication(
        adjudication_path, source_result_root
    )
    resolved_senses, resolved_candidates, summaries = _build_resolved_records(
        proposals, source_candidates, consensus_by_case, adjudication_by_case
    )

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        write_jsonl(staging / "reviewed_senses_5.jsonl", resolved_senses)
        write_jsonl(staging / "reviewed_candidates_15.jsonl", resolved_candidates)
        write_csv(staging / "review_complete_summary_5.csv", summaries, SUMMARY_CSV_FIELDS)
        shutil.copy2(
            adjudication_path.resolve(strict=True),
            staging / "adjudication_template_2_completed.csv",
        )
        source_inputs = staging / "source_inputs"
        source_inputs.mkdir()
        for relative in (
            "repair_sense_proposals_5.jsonl",
            "candidate_proposals_15.jsonl",
            "evidence_contexts_25.jsonl",
            "repair_cases_5.csv",
        ):
            source = _verify_manifest_file(source_review_root, review_manifest, relative)
            shutil.copy2(source, source_inputs / relative)
        shutil.copy2(
            source_review_root / "manifest.json",
            source_inputs / "source_review_manifest.json",
        )
        shutil.copy2(
            source_result_root / "manifest.json",
            source_inputs / "source_result_manifest.json",
        )
        for relative in (
            "consensus_3_of_3_3.jsonl",
            "adjudication_required_2.jsonl",
        ):
            source = _verify_manifest_file(source_result_root, result_manifest, relative)
            shutil.copy2(source, source_inputs / relative)
        _write_metadata(staging, created_at)
        _write_source_bundle(staging)

        counts = {
            "reviewed_sense": 5,
            "reviewed_candidate": 15,
            "review_context": 25,
            "consensus_3_of_3": 3,
            "adjudicated": 2,
            "candidate_replacement": 1,
        }
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LTargetedRepairReviewCompleteManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "created_at": created_at,
            "status": STATUS,
            "counts": counts,
            "source_review_manifest_sha256": SOURCE_REVIEW_MANIFEST_SHA256,
            "source_result_manifest_sha256": SOURCE_RESULT_MANIFEST_SHA256,
            "completed_adjudication_sha256": ADJUDICATION_INPUT_SHA256,
            "provider_call_count": 0,
            "official_contract_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")

        try:
            from .validate_complete_review import validate_artifact
        except ImportError:  # pragma: no cover
            from validate_complete_review import validate_artifact  # type: ignore
        errors = validate_artifact(staging)
        if errors:
            raise ValueError("internal validation failed: " + "; ".join(errors))

        zip_name = f"{ARTIFACT_NAME}_reviewer_handoff.zip"
        temporary_zip = temporary / zip_name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temporary_zip, final_zip)
        zip_sha256 = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_sha256} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "reviewer_handoff_zip": str(final_zip),
            "reviewer_handoff_zip_sha256": zip_sha256,
            "counts": counts,
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    namespace = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-review-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
        / "release"
        / SOURCE_REVIEW_ARTIFACT_NAME,
    )
    parser.add_argument(
        "--source-result-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_stage_a_targeted_repair_review_result_5_senses_v1"
        / "release"
        / SOURCE_RESULT_ARTIFACT_NAME,
    )
    parser.add_argument(
        "--adjudication-path",
        type=Path,
        default=namespace / "inputs" / "adjudication_template_2_completed.csv",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default=CREATED_AT_DEFAULT)
    args = parser.parse_args()
    result = build_complete_review(
        source_review_root=args.source_review_root,
        source_result_root=args.source_result_root,
        adjudication_path=args.adjudication_path,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
