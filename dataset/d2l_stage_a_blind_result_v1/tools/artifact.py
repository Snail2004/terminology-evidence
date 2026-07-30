from __future__ import annotations

from pathlib import Path
from typing import Any

from common import (
    file_bindings,
    read_csv,
    read_json,
    read_jsonl,
    seal,
    sha256_file,
    validate_self_hash,
    write_checksums,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)
from consensus import ADJUDICATION_REASONS, compare_with_anchors, load_anchor_records, resolve_blind_consensus
from intake import validate_and_normalize_reviews


ARTIFACT_STATUS = "BLOCKED_PENDING_REVIEWER_PROVENANCE_AND_ADJUDICATION"
ADJUDICATION_CASE_FIELDS = [
    "adjudication_case_id",
    "term_id",
    "sense_id",
    "source_term",
    "reason_codes",
    "anchored_definition_en",
    "anchored_part_of_speech",
    "anchored_split",
    "reviewer_1_definition_en",
    "reviewer_1_part_of_speech",
    "reviewer_1_split",
    "reviewer_2_definition_en",
    "reviewer_2_part_of_speech",
    "reviewer_2_split",
    "reviewer_3_definition_en",
    "reviewer_3_part_of_speech",
    "reviewer_3_split",
]
ADJUDICATOR_FIELDS = [
    "schema_id",
    "policy_id",
    "adjudication_case_id",
    "term_id",
    "sense_id",
    "definition_outcome",
    "effective_definition_en",
    "part_of_speech_outcome",
    "effective_part_of_speech",
    "split_outcome",
    "child_sense_notes",
    "rationale",
    "adjudicator_id",
    "completed_at",
]


def _pending_provenance(binding: dict[str, Any], pack_manifest: dict[str, Any]) -> dict[str, Any]:
    return seal(
        {
            "schema_id": "D2LCSTBlindReviewerProvenanceV1",
            "policy_id": "d2l_cst_stage_a_blind_result_provenance_v1",
            "status": "PENDING_OWNER_ATTESTATION",
            "reviewer_slot": binding["reviewer_slot"],
            "review_file_sha256": binding["sha256"],
            "review_file_size_bytes": binding["size_bytes"],
            "blind_pack_manifest_sha256": pack_manifest["manifest_sha256"],
            "reviewer_type": "",
            "reviewer_id": "",
            "started_at": "",
            "completed_at": "",
            "run_id": "",
            "independence_attestation": None,
            "other_reviewer_outputs_visible": None,
        },
        "provenance_sha256",
    )


def _adjudication_rows(
    *,
    consensus_records: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    normalized_by_slot: dict[int, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    comparison_by_sense = {row["sense_id"]: row for row in comparisons}
    review_by_slot = {
        slot: {row["sense_id"]: row for row in rows}
        for slot, rows in normalized_by_slot.items()
    }
    case_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    for consensus in sorted(consensus_records, key=lambda row: row["source_term"].casefold()):
        if consensus["source_term"] not in ADJUDICATION_REASONS:
            continue
        comparison = comparison_by_sense[consensus["sense_id"]]
        case_id = "adj_" + consensus["record_sha256"][:24]
        reviews = [review_by_slot[slot][consensus["sense_id"]] for slot in (1, 2, 3)]
        case_rows.append(
            {
                "adjudication_case_id": case_id,
                "term_id": consensus["term_id"],
                "sense_id": consensus["sense_id"],
                "source_term": consensus["source_term"],
                "reason_codes": ";".join(consensus["adjudication_reason_codes"]),
                "anchored_definition_en": comparison["anchored_definition_en"],
                "anchored_part_of_speech": comparison["anchored_pos"],
                "anchored_split": comparison["anchored_split"],
                "reviewer_1_definition_en": reviews[0]["blind_definition_en"],
                "reviewer_1_part_of_speech": reviews[0]["blind_part_of_speech"],
                "reviewer_1_split": reviews[0]["split_recommendation"],
                "reviewer_2_definition_en": reviews[1]["blind_definition_en"],
                "reviewer_2_part_of_speech": reviews[1]["blind_part_of_speech"],
                "reviewer_2_split": reviews[1]["split_recommendation"],
                "reviewer_3_definition_en": reviews[2]["blind_definition_en"],
                "reviewer_3_part_of_speech": reviews[2]["blind_part_of_speech"],
                "reviewer_3_split": reviews[2]["split_recommendation"],
            }
        )
        result_rows.append(
            {
                "schema_id": "D2LCSTStageAAdjudicationOutputV1",
                "policy_id": "d2l_cst_stage_a_blind_adjudication_v1",
                "adjudication_case_id": case_id,
                "term_id": consensus["term_id"],
                "sense_id": consensus["sense_id"],
                "definition_outcome": "",
                "effective_definition_en": "",
                "part_of_speech_outcome": "",
                "effective_part_of_speech": "",
                "split_outcome": "",
                "child_sense_notes": "",
                "rationale": "",
                "adjudicator_id": "",
                "completed_at": "",
            }
        )
    return case_rows, result_rows


def build_artifact(
    *,
    pack_root: Path,
    review_paths: list[Path],
    anchor_reference_path: Path,
    anchored_consensus_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    intake = validate_and_normalize_reviews(pack_root=pack_root, review_paths=review_paths)
    consensus_records = resolve_blind_consensus(
        cases=intake["cases"], normalized_by_slot=intake["normalized_by_slot"]
    )
    anchors = load_anchor_records(
        anchor_reference_path=anchor_reference_path,
        anchored_consensus_path=anchored_consensus_path,
    )
    comparisons = compare_with_anchors(
        consensus_records=consensus_records,
        anchors=anchors,
    )

    output_root.mkdir(parents=True)

    for slot, rows in intake["normalized_by_slot"].items():
        write_jsonl(output_root / "normalized_reviews" / f"reviewer_{slot}.jsonl", rows)
    provenance = [
        _pending_provenance(binding, intake["pack_manifest"])
        for binding in intake["input_bindings"]
    ]
    for row in provenance:
        write_json(
            output_root / "provenance" / f"reviewer_{row['reviewer_slot']}.json",
            row,
        )
    write_jsonl(output_root / "blind_consensus.jsonl", consensus_records)
    write_jsonl(output_root / "paired_comparison.jsonl", comparisons)
    input_bindings = seal(
        {
            "schema_id": "D2LCSTBlindResultInputBindingsV1",
            "policy_id": "d2l_cst_stage_a_blind_result_intake_v1",
            "blind_pack_manifest_sha256": intake["pack_manifest"]["manifest_sha256"],
            "anchor_reference_sha256": sha256_file(anchor_reference_path),
            "anchored_consensus_sha256": sha256_file(anchored_consensus_path),
            "review_files": intake["input_bindings"],
        },
        "bindings_sha256",
    )
    write_json(output_root / "input_bindings.json", input_bindings)

    adjudication_cases, adjudicator_rows = _adjudication_rows(
        consensus_records=consensus_records,
        comparisons=comparisons,
        normalized_by_slot=intake["normalized_by_slot"],
    )
    write_csv(
        output_root / "adjudication" / "adjudication_cases.csv",
        ADJUDICATION_CASE_FIELDS,
        adjudication_cases,
    )
    write_csv(
        output_root / "adjudication" / "adjudicator.csv",
        ADJUDICATOR_FIELDS,
        adjudicator_rows,
    )
    write_text(
        output_root / "adjudication" / "ADJUDICATION_INSTRUCTIONS.md",
        """# Stage A adjudication instructions

Review only the three listed cases using the anchored proposal, all three blind
reviews, and their cited corpus evidence. Resolve definition, part of speech,
and split scope at Stage A. Do not issue a final glossary decision; that remains
owned by the Global Validator.

Complete only `adjudicator.csv`. Preserve all identifiers and row order.
""",
    )

    summary = seal(
        {
            "schema_id": "D2LCSTBlindResultSummaryV1",
            "policy_id": "d2l_cst_stage_a_blind_result_summary_v1",
            "artifact_status": ARTIFACT_STATUS,
            "reviewer_slot_count": 3,
            "blind_case_count": len(consensus_records),
            "normalized_review_record_count": sum(
                len(rows) for rows in intake["normalized_by_slot"].values()
            ),
            "split_unanimous_count": sum(
                bool(row["split_vote"]["unanimous"]) for row in consensus_records
            ),
            "split_majority_matches_anchor_count": sum(
                bool(row["split_majority_matches_anchor"]) for row in comparisons
            ),
            "pos_unanimous_count": sum(
                bool(row["part_of_speech_vote"]["unanimous"])
                for row in consensus_records
            ),
            "pos_consensus_matches_anchor_count": sum(
                row["pos_consensus_matches_anchor"] is True for row in comparisons
            ),
            "definition_exact_unanimous_count": sum(
                bool(row["definition_exact_agreement"]) for row in consensus_records
            ),
            "adjudication_case_count": len(adjudication_cases),
            "adjudication_terms": sorted(ADJUDICATION_REASONS),
            "reviewer_provenance_status": "PENDING_OWNER_ATTESTATION",
            "anchoring_assessment_status": (
                "INCONCLUSIVE_PENDING_PROVENANCE_AND_SEMANTIC_ADJUDICATION"
            ),
            "final_glossary_decision": None,
        },
        "summary_sha256",
    )
    write_json(output_root / "summary.json", summary)

    manifest = seal(
        {
            "schema_id": "D2LCSTBlindResultArtifactManifestV1",
            "policy_id": "d2l_cst_stage_a_blind_result_artifact_v1",
            "artifact_status": ARTIFACT_STATUS,
            "summary_sha256": summary["summary_sha256"],
            "input_bindings_sha256": input_bindings["bindings_sha256"],
            "files": file_bindings(output_root),
        },
        "manifest_sha256",
    )
    write_json(output_root / "manifest.json", manifest)
    write_checksums(output_root, output_root / "CHECKSUMS.sha256")
    return summary


def validate_artifact(artifact_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    manifest = read_json(artifact_root / "manifest.json")
    summary = read_json(artifact_root / "summary.json")
    input_bindings = read_json(artifact_root / "input_bindings.json")
    if not validate_self_hash(manifest, "manifest_sha256"):
        errors.append("manifest self-hash is invalid")
    if not validate_self_hash(summary, "summary_sha256"):
        errors.append("summary self-hash is invalid")
    if not validate_self_hash(input_bindings, "bindings_sha256"):
        errors.append("input bindings self-hash is invalid")
    if manifest.get("summary_sha256") != summary.get("summary_sha256"):
        errors.append("manifest summary binding mismatch")
    if manifest.get("input_bindings_sha256") != input_bindings.get("bindings_sha256"):
        errors.append("manifest input binding mismatch")
    if manifest.get("artifact_status") != ARTIFACT_STATUS:
        errors.append("artifact status is not fail-closed")
    if summary.get("final_glossary_decision") is not None:
        errors.append("dataset artifact must not issue final_glossary_decision")
    if summary.get("blind_case_count") != 13:
        errors.append("expected 13 blind cases")
    if summary.get("normalized_review_record_count") != 39:
        errors.append("expected 39 normalized review records")
    if summary.get("adjudication_terms") != sorted(ADJUDICATION_REASONS):
        errors.append("adjudication term set is not exact")

    expected_files = manifest.get("files") or {}
    actual_files = file_bindings(
        artifact_root,
        excluded={"manifest.json", "CHECKSUMS.sha256"},
    )
    if actual_files != expected_files:
        errors.append("artifact file set or file bindings drifted")
    for relative, binding in expected_files.items():
        path = artifact_root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {relative}")
            continue
        if sha256_file(path) != binding.get("sha256") or path.stat().st_size != binding.get("size_bytes"):
            errors.append(f"bound file drift: {relative}")

    record_counts: dict[str, int] = {}
    for relative in (
        "blind_consensus.jsonl",
        "paired_comparison.jsonl",
        "normalized_reviews/reviewer_1.jsonl",
        "normalized_reviews/reviewer_2.jsonl",
        "normalized_reviews/reviewer_3.jsonl",
    ):
        records = read_jsonl(artifact_root / relative)
        record_counts[relative] = len(records)
        for record in records:
            if not validate_self_hash(record, "record_sha256"):
                errors.append(f"invalid record self-hash: {relative}")
            if record.get("final_glossary_decision") is not None:
                errors.append(f"unexpected final glossary decision: {relative}")

    if record_counts.get("blind_consensus.jsonl") != 13:
        errors.append("blind consensus must contain 13 records")
    if record_counts.get("paired_comparison.jsonl") != 13:
        errors.append("paired comparison must contain 13 records")
    for slot in (1, 2, 3):
        relative = f"normalized_reviews/reviewer_{slot}.jsonl"
        if record_counts.get(relative) != 13:
            errors.append(f"reviewer {slot} normalization must contain 13 records")

    for slot in (1, 2, 3):
        provenance = read_json(artifact_root / "provenance" / f"reviewer_{slot}.json")
        if not validate_self_hash(provenance, "provenance_sha256"):
            errors.append(f"reviewer {slot} provenance self-hash is invalid")
        if provenance.get("status") != "PENDING_OWNER_ATTESTATION":
            errors.append(f"reviewer {slot} provenance status is not fail-closed")

    adjudication = read_csv(artifact_root / "adjudication" / "adjudicator.csv")
    if len(adjudication) != 3 or any(row.get("definition_outcome") for row in adjudication):
        errors.append("adjudicator template must contain three blank result rows")
    adjudication_cases = read_csv(artifact_root / "adjudication" / "adjudication_cases.csv")
    if {row.get("source_term") for row in adjudication_cases} != set(ADJUDICATION_REASONS):
        errors.append("adjudication case term set is not exact")

    expected_checksums = [
        f"{binding['sha256']}  {relative}"
        for relative, binding in file_bindings(
            artifact_root,
            excluded={"CHECKSUMS.sha256"},
        ).items()
    ]
    actual_checksums = (artifact_root / "CHECKSUMS.sha256").read_text(
        encoding="utf-8"
    ).splitlines()
    if actual_checksums != expected_checksums:
        errors.append("CHECKSUMS.sha256 does not match the physical artifact")

    return {
        "status": "PASS" if not errors else "FAIL",
        "artifact_status": summary.get("artifact_status"),
        "blind_case_count": summary.get("blind_case_count"),
        "adjudication_case_count": summary.get("adjudication_case_count"),
        "errors": errors,
    }
