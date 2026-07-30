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
        write_checksums,
        write_csv,
        write_json,
        write_jsonl,
    )
    from .spec import (
        ADJUDICATION_CASES,
        ADJUDICATION_CSV_FIELDS,
        ADJUDICATION_OUTPUT_FIELDS,
        ADJUDICATION_SOURCE_FIELDS,
        ALLOWED_SPLIT_DECISIONS,
        ALLOWED_STANDARD_DECISIONS,
        ARTIFACT_NAME,
        CONSENSUS_CASES,
        CREATED_AT_DEFAULT,
        DECISION_FIELDS,
        POLICY_ID,
        REVIEW_CSV_FIELDS,
        REVIEW_HUMAN_FIELDS,
        REVIEW_INPUT_SHA256,
        REVIEW_SOURCE_FIELDS,
        REVIEWER_SLOTS,
        SOURCE_REVIEW_ARTIFACT_NAME,
        SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        SOURCE_REVIEW_MANIFEST_SHA256,
        SOURCE_REVIEW_ZIP_SHA256,
        STATUS,
    )
except ImportError:  # pragma: no cover
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
        write_checksums,
        write_csv,
        write_json,
        write_jsonl,
    )
    from spec import (  # type: ignore
        ADJUDICATION_CASES,
        ADJUDICATION_CSV_FIELDS,
        ADJUDICATION_OUTPUT_FIELDS,
        ADJUDICATION_SOURCE_FIELDS,
        ALLOWED_SPLIT_DECISIONS,
        ALLOWED_STANDARD_DECISIONS,
        ARTIFACT_NAME,
        CONSENSUS_CASES,
        CREATED_AT_DEFAULT,
        DECISION_FIELDS,
        POLICY_ID,
        REVIEW_CSV_FIELDS,
        REVIEW_HUMAN_FIELDS,
        REVIEW_INPUT_SHA256,
        REVIEW_SOURCE_FIELDS,
        REVIEWER_SLOTS,
        SOURCE_REVIEW_ARTIFACT_NAME,
        SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        SOURCE_REVIEW_MANIFEST_SHA256,
        SOURCE_REVIEW_ZIP_SHA256,
        STATUS,
    )


SOURCE_REVIEW_COMMIT = "d5fb0b4b3039cff6608e2c449997c4f85a71db39"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_source_review_artifact(root: Path) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    if sha256_file(manifest_path) != SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256:
        raise ValueError("source review manifest physical hash mismatch")
    manifest = strict_json_object(manifest_path)
    if manifest.get("manifest_sha256") != SOURCE_REVIEW_MANIFEST_SHA256:
        raise ValueError("source review manifest declared hash mismatch")
    if _manifest_self_hash(manifest) != SOURCE_REVIEW_MANIFEST_SHA256:
        raise ValueError("source review manifest self hash mismatch")
    if manifest.get("artifact_name") != SOURCE_REVIEW_ARTIFACT_NAME:
        raise ValueError("source review artifact identity mismatch")
    metadata = manifest.get("files", {}).get("repair_cases_5.csv")
    if not isinstance(metadata, Mapping):
        raise ValueError("source review manifest omits repair_cases_5.csv")
    cases_path = root / "repair_cases_5.csv"
    if sha256_file(cases_path) != metadata.get("sha256"):
        raise ValueError("source review case projection drift")
    return manifest


def _csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def _load_reviews(
    source_review_root: Path, review_paths: Mapping[str, Path]
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]]]:
    _verify_source_review_artifact(source_review_root)
    expected_rows = {
        row["review_case_id"]: row for row in read_csv(source_review_root / "repair_cases_5.csv")
    }
    if len(expected_rows) != 5:
        raise ValueError("source review case count must be five")
    if set(review_paths) != set(REVIEWER_SLOTS):
        raise ValueError("exactly the three named reviewer slots are required")
    resolved = [review_paths[slot].resolve(strict=True) for slot in REVIEWER_SLOTS]
    if len(set(resolved)) != 3:
        raise ValueError("reviewer inputs must be three distinct physical paths")

    reviews: dict[str, dict[str, dict[str, str]]] = {}
    for slot, path in zip(REVIEWER_SLOTS, resolved):
        if sha256_file(path) != REVIEW_INPUT_SHA256[slot]:
            raise ValueError(f"review input hash mismatch: {slot}")
        if _csv_headers(path) != list(REVIEW_CSV_FIELDS):
            raise ValueError(f"review input header mismatch: {slot}")
        rows = read_csv(path)
        if len(rows) != 5 or len({row.get("review_case_id") for row in rows}) != 5:
            raise ValueError(f"review input must contain five unique cases: {slot}")
        by_case: dict[str, dict[str, str]] = {}
        for row in rows:
            case_id = row.get("review_case_id", "")
            expected = expected_rows.get(case_id)
            if expected is None:
                raise ValueError(f"unknown review case: {slot}:{case_id}")
            for field in (*REVIEW_SOURCE_FIELDS, "source_payload_sha256"):
                if row.get(field, "") != expected.get(field, ""):
                    raise ValueError(f"source payload drift: {slot}:{case_id}:{field}")
            payload = {field: row[field] for field in REVIEW_SOURCE_FIELDS}
            if sha256_bytes(canonical_json_bytes(payload)) != row["source_payload_sha256"]:
                raise ValueError(f"source payload self hash mismatch: {slot}:{case_id}")
            if row.get("reviewer_slot") != slot:
                raise ValueError(f"reviewer slot mismatch: {slot}:{case_id}")
            if row.get("review_status") != "COMPLETE":
                raise ValueError(f"review is incomplete: {slot}:{case_id}")
            for field in (
                "definition_decision",
                "part_of_speech_decision",
                "scope_decision",
                "context_evidence_decision",
                "candidate_set_decision",
            ):
                if row.get(field) not in ALLOWED_STANDARD_DECISIONS:
                    raise ValueError(f"invalid decision: {slot}:{case_id}:{field}")
            if row.get("split_decision") not in ALLOWED_SPLIT_DECISIONS:
                raise ValueError(f"invalid split decision: {slot}:{case_id}")
            for decision_field, corrected_field in (
                ("definition_decision", "corrected_definition_en"),
                ("part_of_speech_decision", "corrected_part_of_speech"),
                ("scope_decision", "corrected_scope"),
            ):
                if row[decision_field] == "REVISE" and not row[corrected_field].strip():
                    raise ValueError(
                        f"revision omits corrected value: {slot}:{case_id}:{corrected_field}"
                    )
            by_case[case_id] = row
        reviews[slot] = by_case
    return expected_rows, reviews


def _review_votes(
    case_id: str, reviews: Mapping[str, Mapping[str, Mapping[str, str]]]
) -> list[dict[str, Any]]:
    votes = []
    for slot in REVIEWER_SLOTS:
        row = reviews[slot][case_id]
        vote = {
            "reviewer_slot": slot,
            "review_input_sha256": REVIEW_INPUT_SHA256[slot],
            **{field: row[field] for field in REVIEW_HUMAN_FIELDS},
        }
        vote["review_vote_sha256"] = sha256_bytes(canonical_json_bytes(vote))
        votes.append(vote)
    return votes


def _classify_results(
    expected_rows: Mapping[str, Mapping[str, str]],
    reviews: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    consensus = []
    adjudication = []
    for case_id, source in sorted(expected_rows.items()):
        key = (source["source_term"], source["split_label"])
        votes = _review_votes(case_id, reviews)
        decision_vectors = {
            tuple(reviews[slot][case_id][field] for field in DECISION_FIELDS)
            for slot in REVIEWER_SLOTS
        }
        common = {
            "review_case_id": case_id,
            "output_sense_id": source["output_sense_id"],
            "parent_sense_id": source["parent_sense_id"],
            "source_term": source["source_term"],
            "split_label": source["split_label"],
            "source_payload_sha256": source["source_payload_sha256"],
            "reviewer_votes": votes,
            "review_input_sha256": dict(REVIEW_INPUT_SHA256),
            "provider_call_count": 0,
            "final_glossary_decision": None,
        }
        if key in CONSENSUS_CASES:
            if len(decision_vectors) != 1:
                raise ValueError(f"expected 3-of-3 consensus is absent: {key}")
            decisions = {field: reviews["reviewer_1"][case_id][field] for field in DECISION_FIELDS}
            if any(value != "ACCEPT" for field, value in decisions.items() if field != "split_decision"):
                raise ValueError(f"consensus case is not accepted: {key}")
            consensus.append(
                seal_record(
                    {
                        "schema_id": "D2LTargetedRepairReviewConsensusV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        **common,
                        "consensus_status": "AGREEMENT_3_OF_3",
                        "consensus_decisions": decisions,
                        "official_contract_emitted": False,
                    },
                    "consensus_record_sha256",
                )
            )
        elif key in ADJUDICATION_CASES:
            adjudication.append(
                seal_record(
                    {
                        "schema_id": "D2LTargetedRepairAdjudicationRequiredV1",
                        "schema_version": "1.0.0",
                        "policy_id": POLICY_ID,
                        **common,
                        "issue_type": ADJUDICATION_CASES[key],
                        "decision_vector_count": len(decision_vectors),
                        "status": "ADJUDICATION_REQUIRED",
                        "official_contract_emitted": False,
                    },
                    "adjudication_record_sha256",
                )
            )
        else:
            raise ValueError(f"unexpected result case: {key}")
    if len(consensus) != 3 or len(adjudication) != 2:
        raise ValueError("review classification must yield 3 consensus and 2 adjudication cases")
    return consensus, adjudication


def _adjudication_rows(
    adjudication: list[Mapping[str, Any]],
    expected_rows: Mapping[str, Mapping[str, str]],
    reviews: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> list[dict[str, str]]:
    rows = []
    for record in adjudication:
        case_id = record["review_case_id"]
        source = expected_rows[case_id]
        row: dict[str, str] = {
            "schema_id": "D2LTargetedRepairAdjudicationRowV1",
            "review_case_id": case_id,
            "output_sense_id": source["output_sense_id"],
            "parent_sense_id": source["parent_sense_id"],
            "source_term": source["source_term"],
            "split_label": source["split_label"],
            "issue_type": record["issue_type"],
            "proposed_definition_en": source["proposed_definition_en"],
            "candidate_ids": source["candidate_ids"],
            "candidate_targets_vi": source["candidate_targets_vi"],
        }
        for slot in REVIEWER_SLOTS:
            review = reviews[slot][case_id]
            row[f"{slot}_definition_decision"] = review["definition_decision"]
            row[f"{slot}_corrected_definition_en"] = review["corrected_definition_en"]
            row[f"{slot}_candidate_set_decision"] = review["candidate_set_decision"]
            row[f"{slot}_review_notes"] = review["review_notes"]
        source_payload = {field: row[field] for field in ADJUDICATION_SOURCE_FIELDS}
        row["source_payload_sha256"] = sha256_bytes(canonical_json_bytes(source_payload))
        row.update({field: "" for field in ADJUDICATION_OUTPUT_FIELDS})
        rows.append(row)
    return sorted(rows, key=lambda row: row["source_term"])


def _write_metadata(
    staging: Path,
    created_at: str,
    consensus: list[Mapping[str, Any]],
    adjudication: list[Mapping[str, Any]],
) -> None:
    report = f"""# D2L Targeted Repair Review Result - 5 senses

Status: `{STATUS}`

Three reviewer files passed source-payload, slot, cardinality, completion, and
decision validation. Three cases have exact 3-of-3 agreement:

- fully-connected layers
- in place / IN_PLACE_MUTATION
- in place / ESTABLISHED_CONFIGURATION

Two cases require adjudication:

- Adam: one ACCEPT versus two REVISE definition decisions, with two different
  corrected definitions.
- statistical power: all three reviewers require candidate-set revision, but
  the exact replacement for candidate 2 is not yet fixed.

No reviewer must repeat the five-case review. Only the two-row adjudication
template remains. This artifact emits no official contract, gold label,
provider call, or final glossary decision.
"""
    (staging / "REVIEW_RESULT_REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    instructions = """# Huong dan adjudication

Chi xu ly hai dong trong `adjudication_template_2.csv`.

1. `Adam`: chon ACCEPT cho dinh nghia de xuat, hoac REVISE va ghi mot dinh
   nghia cuoi cung vao `adjudicated_definition_en`.
2. `statistical power`: chon quyet dinh cho candidate set va ghi chinh xac
   candidate thay the cho CANDIDATE_2 vao `adjudicated_candidate_2_vi`.
3. Ghi ly do vao `adjudication_notes` va dat
   `adjudication_status=COMPLETE` cho tung dong.

Khong sua cac cot tu `schema_id` den `source_payload_sha256`. Adjudicator duoc
xem ca ba review vi day la vong phan xu sau review doc lap.
"""
    (staging / "ADJUDICATION_INSTRUCTIONS.md").write_text(
        instructions, encoding="utf-8", newline="\n"
    )
    write_json(
        staging / "review_summary.json",
        seal_integrity(
            {
                "schema_id": "D2LTargetedRepairReviewSummaryV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "counts": {
                    "review_case": 5,
                    "review_input": 3,
                    "consensus_3_of_3": len(consensus),
                    "adjudication_required": len(adjudication),
                },
                "review_input_sha256": dict(REVIEW_INPUT_SHA256),
                "provider_call_count": 0,
                "official_contract_count": 0,
                "final_glossary_decision": None,
                "created_at": created_at,
            }
        ),
    )
    write_json(
        staging / "lineage.json",
        seal_integrity(
            {
                "schema_id": "D2LTargetedRepairReviewResultLineageV1",
                "schema_version": "1.0.0",
                "source_review_artifact": SOURCE_REVIEW_ARTIFACT_NAME,
                "source_review_manifest_sha256": SOURCE_REVIEW_MANIFEST_SHA256,
                "source_review_manifest_physical_sha256": SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
                "source_review_zip_sha256": SOURCE_REVIEW_ZIP_SHA256,
                "source_review_commit": SOURCE_REVIEW_COMMIT,
                "review_input_sha256": dict(REVIEW_INPUT_SHA256),
                "provider_call_count": 0,
                "final_glossary_decision": None,
            }
        ),
    )
    write_json(
        staging / "environment.json",
        {
            "schema_id": "D2LTargetedRepairReviewResultEnvironmentV1",
            "created_at": created_at,
            "network_calls": 0,
            "provider_calls": 0,
        },
    )
    (staging / "commands.txt").write_text(
        "python -B source/tools/validate_review_result.py --artifact-root .\n",
        encoding="ascii",
        newline="\n",
    )
    (staging / "junit.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testsuite name="targeted-repair-review-result" tests="1" failures="0" '
        'errors="0" skipped="0"><testcase classname="release" '
        'name="internal_validation"/></testsuite>\n',
        encoding="utf-8",
        newline="\n",
    )


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/build_review_result.py",
        "tools/validate_review_result.py",
        "tests/test_review_result.py",
    ):
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"release source file is missing: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def build_review_result(
    *,
    source_review_root: Path,
    review_paths: Mapping[str, Path],
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    source_review_root = source_review_root.resolve(strict=True)
    output_root = output_root.resolve()
    expected_rows, reviews = _load_reviews(source_review_root, review_paths)
    consensus, adjudication = _classify_results(expected_rows, reviews)
    adjudication_rows = _adjudication_rows(adjudication, expected_rows, reviews)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        review_input_dir = staging / "review_inputs"
        review_input_dir.mkdir()
        for slot in REVIEWER_SLOTS:
            shutil.copy2(review_paths[slot].resolve(strict=True), review_input_dir / f"{slot}.csv")
        write_jsonl(staging / "consensus_3_of_3_3.jsonl", consensus)
        write_jsonl(staging / "adjudication_required_2.jsonl", adjudication)
        write_csv(
            staging / "adjudication_template_2.csv",
            adjudication_rows,
            ADJUDICATION_CSV_FIELDS,
        )
        _write_metadata(staging, created_at, consensus, adjudication)
        _write_source_bundle(staging)

        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LTargetedRepairReviewResultManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "created_at": created_at,
            "status": STATUS,
            "counts": {
                "review_case": 5,
                "review_input": 3,
                "consensus_3_of_3": 3,
                "adjudication_required": 2,
            },
            "source_review_manifest_sha256": SOURCE_REVIEW_MANIFEST_SHA256,
            "review_input_sha256": dict(REVIEW_INPUT_SHA256),
            "provider_call_count": 0,
            "official_contract_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")

        try:
            from .validate_review_result import validate_artifact
        except ImportError:  # pragma: no cover
            from validate_review_result import validate_artifact  # type: ignore
        errors = validate_artifact(staging)
        if errors:
            raise ValueError("internal validation failed: " + "; ".join(errors))

        zip_name = f"{ARTIFACT_NAME}_adjudication_handoff.zip"
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
            "adjudication_handoff_zip": str(final_zip),
            "adjudication_handoff_zip_sha256": zip_sha256,
            "counts": manifest["counts"],
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
    for slot in REVIEWER_SLOTS:
        parser.add_argument(
            f"--{slot.replace('_', '-')}",
            type=Path,
            default=namespace / "inputs" / f"{slot}.csv",
        )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default=CREATED_AT_DEFAULT)
    args = parser.parse_args()
    result = build_review_result(
        source_review_root=args.source_review_root,
        review_paths={slot: getattr(args, slot) for slot in REVIEWER_SLOTS},
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
