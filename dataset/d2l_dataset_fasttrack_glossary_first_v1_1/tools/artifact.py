from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from .blind import build_blind_pack
from .candidates import normalize_candidates
from .common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    read_json,
    read_jsonl,
    reset_directory,
    seal_record,
    sha256_bytes,
    sha256_file,
    write_checksums,
    write_csv,
    write_json,
    write_jsonl,
)
from .glossary import match_glossary, parse_glossary
from .grounding import (
    active_positive_ids,
    build_adjudication_records,
    build_projection,
    build_source_grounding_report,
    classify_risk,
)


POLICY_ID = "dataset-fasttrack-glossary-first-v1.1"
ARTIFACT_NAME = "d2l_dataset_fasttrack_glossary_first_v1_1"
EXPECTED_GLOSSARY_COMMIT = "c775d6b4998e6243ec5d11f950e67679555a2c74"
CONTRACT_AUTHORITY_TAG = "contracts-v1.1.0"
CONTRACT_AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
CONTRACT_MANIFEST_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
REQUIRED_ACCEPTANCE_CHECKS = {
    "all_required_r1_r2_r3_reviews_complete",
    "blind_audit_complete",
    "blind_audit_selection_matches_current_risk_policy",
    "controlled_independent_attestation_registry_ready",
    "cross_split_active_block_count_zero",
    "mapped_150_senses",
    "official_effective_sense_contract_count_150",
    "pilot_complete_constraint_evidence_packages_15",
    "pilot_frozen_candidate_contracts_15",
    "real_positive_context_coverage_150",
    "review_provenance_complete",
    "synthetic_positive_evidence_zero",
    "unresolved_r4_zero",
    "unresolved_sense_count_zero",
}


POLICY_TEXT = """# Dataset Fast-Track Policy V1.1

Policy ID: `dataset-fasttrack-glossary-first-v1.1`

This is a repair companion to the immutable `d2l_dataset_fasttrack_glossary_first_v1`.
It preserves the parent artifact and records its manifest and ZIP hashes in
`source_bindings.json`.

## Authority boundaries

- D2L English corpus contexts are the source-grounding authority.
- The pinned D2L-VI glossary is a Tier-3 candidate source, not gold truth.
- Model outputs improve recall but cannot finalize a sense or candidate label.
- Human review is required by risk: R1/R2 one reviewer, R3 two independent
  reviewers, and R4 formal adjudication.
- Validation and test candidate labels remain 100% human-reviewed and hidden
  from Global scoring.
- C and E produce evidence only; `final_glossary_decision` stays null.

## Evidence separation

Positive definition/POS evidence must be real D2L corpus context with
`SAME_SENSE` and `PRIMARY` or `BACKUP` role. Contrastive and synthetic contexts
are boundary evidence only and cannot support definition, POS, or primary C
scores.

## Blind audit selection

The development-only blind pack contains all three available development R0
cases, two deterministic clear controls, three registered disagreement cases,
and five ambiguous/polysemous cases. Historical blind outputs remain evidence
of their original selection only and cannot satisfy the current selection gate.

## Fail-closed publication

This companion release does not reinterpret unresolved V3 records as reviewed.
It emits pending projections and blank Stage B labels. Official Effective Sense,
Frozen Candidate, and COMPLETE Constraint Evidence contracts remain absent until
review provenance, adjudication, split leakage, and downstream evidence gates
are actually complete.
"""


STAGE_B_INSTRUCTIONS = """# Stage B Candidate Review Instructions

Review one candidate against its pending/finalized sense and real D2L contexts.
Do not use Global scores, thresholds, or another reviewer's decision.

Allowed labels:

- `ACCEPT`
- `CONDITIONAL`
- `REJECT`
- `SPLIT_REQUIRED`
- `HUMAN_UNJUDGEABLE`

Complete labels only after the corresponding Stage A sense is finalized. Keep
`candidate_gold_label` blank while `effective_sense_review_status` is
`UNRESOLVED`. D2L-VI glossary provenance alone cannot establish acceptance.
"""


STAGE_B_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://thesis.local/dataset/d2l-stage-b-review-v1.schema.json",
    "title": "D2L Stage B Candidate Gold Review V1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "term_id",
        "sense_id",
        "candidate_id",
        "candidate_vi",
        "candidate_gold_label",
        "allowed_scope",
        "validated_variants",
        "rejected_variants",
        "reason_codes",
        "positive_context_refs",
        "vietnamese_evidence_refs",
        "reviewer_provenance_ref",
        "adjudication_ref",
    ],
    "properties": {
        "term_id": {"type": "string", "minLength": 1},
        "sense_id": {"type": "string", "minLength": 1},
        "candidate_id": {"type": "string", "minLength": 1},
        "candidate_vi": {"type": "string", "minLength": 1},
        "candidate_gold_label": {
            "type": ["string", "null"],
            "enum": [None, "ACCEPT", "CONDITIONAL", "REJECT", "SPLIT_REQUIRED", "HUMAN_UNJUDGEABLE"],
        },
        "allowed_scope": {"type": ["string", "null"]},
        "validated_variants": {"type": "array", "items": {"type": "string"}},
        "rejected_variants": {"type": "array", "items": {"type": "string"}},
        "reason_codes": {"type": "array", "items": {"type": "string"}},
        "positive_context_refs": {"type": "array", "items": {"type": "string"}},
        "vietnamese_evidence_refs": {"type": "array", "items": {"type": "string"}},
        "reviewer_provenance_ref": {"type": ["string", "null"]},
        "adjudication_ref": {"type": ["string", "null"]},
    },
}


MAPPING_FIELDS = [
    "term_id",
    "sense_id",
    "source_term",
    "split",
    "stratum",
    "glossary_match_status",
    "glossary_source_entry",
    "glossary_candidate_vi",
    "glossary_qualifier",
    "glossary_commit",
    "glossary_entry_sha256",
    "glossary_source_line",
    "matched_entry_count",
    "matched_entries_json",
    "mapping_sha256",
]

RISK_FIELDS = [
    "term_id",
    "sense_id",
    "source_term",
    "split",
    "risk_class",
    "risk_reasons",
    "active_real_positive_context_count",
    "review_requirement",
    "risk_record_sha256",
]

STAGE_B_FIELDS = [
    "term_id",
    "sense_id",
    "split",
    "source_term",
    "effective_sense_review_status",
    "candidate_id",
    "candidate_role",
    "candidate_vi",
    "candidate_source_type",
    "candidate_gold_label",
    "allowed_scope",
    "validated_variants",
    "rejected_variants",
    "reason_codes",
    "positive_context_refs",
    "vietnamese_evidence_refs",
    "reviewer_provenance_ref",
    "adjudication_ref",
]


def acceptance_gate_status(checks: dict[str, bool]) -> str:
    if set(checks) != REQUIRED_ACCEPTANCE_CHECKS:
        return "BLOCKED_BEFORE_REAL_CE_PILOT"
    return "PASS" if all(checks.values()) else "BLOCKED_BEFORE_REAL_CE_PILOT"


def _git_text(repository: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repository), *args],
        text=True,
        encoding="utf-8",
    ).strip()


def verify_glossary_repository(repository: Path) -> dict[str, Any]:
    commit = _git_text(repository, "rev-parse", "HEAD")
    if commit != EXPECTED_GLOSSARY_COMMIT:
        raise ValueError(f"unexpected D2L-VI commit: {commit}")
    if _git_text(repository, "status", "--porcelain"):
        raise ValueError("D2L-VI source repository is dirty")
    glossary = repository / "glossary.md"
    license_path = repository / "LICENSE"
    license_summary = repository / "LICENSE-SUMMARY"
    for path in (glossary, license_path, license_summary):
        if not path.is_file():
            raise FileNotFoundError(path)
    commit_payload = subprocess.check_output(
        ["git", "-C", str(repository), "cat-file", "commit", "HEAD"]
    )
    git_object_header = f"commit {len(commit_payload)}\0".encode("ascii")
    computed_commit = hashlib.sha1(git_object_header + commit_payload).hexdigest()
    if computed_commit != commit:
        raise ValueError("Git commit object payload does not reconstruct pinned commit")
    commit_lines = commit_payload.decode("utf-8", errors="strict").splitlines()
    parent_lines = [line.split(" ", 1)[1] for line in commit_lines if line.startswith("parent ")]
    signature_present = any(line.startswith("gpgsig ") for line in commit_lines)
    return {
        "commit": commit,
        "commit_timestamp": _git_text(repository, "show", "-s", "--format=%cI", "HEAD"),
        "glossary_sha256": sha256_file(glossary),
        "license_sha256": sha256_file(license_path),
        "license_summary_sha256": sha256_file(license_summary),
        "commit_object_payload": commit_payload,
        "commit_object_payload_sha256": sha256_bytes(commit_payload),
        "tree_sha1": _git_text(repository, "show", "-s", "--format=%T", "HEAD"),
        "parent_sha1": " ".join(parent_lines),
        "commit_signature_present": signature_present,
        "subject": _git_text(repository, "show", "-s", "--format=%s", "HEAD"),
        "remote_url": _git_text(repository, "remote", "get-url", "origin"),
        "source_is_shallow": _git_text(repository, "rev-parse", "--is-shallow-repository") == "true",
    }


def _blind_case_refs(blind_root: Path) -> dict[str, str]:
    return {
        row["sense_id"]: f"historical_stage_a_blind_audit_results.csv#sense_id={row['sense_id']}"
        for row in read_jsonl(blind_root / "paired_comparison.jsonl")
    }


def _review_requirement(risk_class: str) -> str:
    return {
        "R0_CLEAR": "BLIND_AUDIT_RANDOM_10_TO_20_PERCENT",
        "R1_QUALIFIED": "ONE_REVIEWER_CONFIRMATION",
        "R2_MISSING": "ONE_REVIEWER_REQUIRED",
        "R3_AMBIGUOUS": "TWO_INDEPENDENT_REVIEWERS_THEN_ADJUDICATE_DISAGREEMENT",
        "R4_SPLIT_OR_POS_RISK": "MANDATORY_ADJUDICATION",
    }[risk_class]


def _write_glossary_snapshot(output: Path, glossary_repository: Path) -> None:
    snapshot = output / "d2l_vi_glossary_snapshot"
    snapshot.mkdir(parents=True)
    for name in ("glossary.md", "LICENSE", "LICENSE-SUMMARY"):
        shutil.copyfile(glossary_repository / name, snapshot / name)


def _write_blind_results(path: Path, blind_root: Path) -> None:
    rows = []
    for record in read_jsonl(blind_root / "paired_comparison.jsonl"):
        rows.append(
            {
                "term_id": record["term_id"],
                "sense_id": record["sense_id"],
                "source_term": record["source_term"],
                "selection_stratum": record["selection_stratum"],
                "blind_split_majority": record["blind_split_majority"],
                "split_majority_matches_anchor": record["split_majority_matches_anchor"],
                "blind_pos_consensus": record["blind_pos_consensus"],
                "pos_consensus_matches_anchor": record["pos_consensus_matches_anchor"],
                "definition_comparison_status": record["definition_comparison_status"],
                "anchoring_assessment_status": record["anchoring_assessment_status"],
                "adjudication_reason_codes": "|".join(record["adjudication_reason_codes"]),
                "source_record_sha256": record["record_sha256"],
            }
        )
    write_csv(
        path,
        rows,
        [
            "term_id",
            "sense_id",
            "source_term",
            "selection_stratum",
            "blind_split_majority",
            "split_majority_matches_anchor",
            "blind_pos_consensus",
            "pos_consensus_matches_anchor",
            "definition_comparison_status",
            "anchoring_assessment_status",
            "adjudication_reason_codes",
            "source_record_sha256",
        ],
    )


def build_fasttrack_artifact(
    repo_root: Path,
    glossary_repository: Path,
    output: Path,
    created_at: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    glossary_repository = glossary_repository.resolve()
    output = output.resolve()
    namespace_root = Path(__file__).resolve().parents[1]
    if namespace_root not in output.parents:
        raise ValueError(f"output must be under {namespace_root}")

    glossary_identity = verify_glossary_repository(glossary_repository)
    v3_root = repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3"
    hardening_root = repo_root / "dataset" / "dataset_methodology_hardening_v1" / "release"
    blind_root = repo_root / "dataset" / "d2l_stage_a_blind_result_v1" / "release" / "blind_audit_result_v1"
    blind_result_zip = repo_root / "dataset" / "d2l_stage_a_blind_result_v1" / "release" / "blind_audit_result_v1.zip"
    blind_pack_zip = repo_root / "dataset" / "d2l_stage_a_review_repair_v1_2" / "release" / "blind_audit_pack_development_v1.zip"

    v3_manifest = read_json(v3_root / "manifest.json")
    senses = read_jsonl(v3_root / "term_senses.jsonl")
    contexts = read_jsonl(v3_root / "contexts.jsonl")
    candidates = read_jsonl(v3_root / "candidate_instances.jsonl")
    slots = read_jsonl(v3_root / "candidate_slots.jsonl")
    leakage_records = read_jsonl(hardening_root / "source_block_split_leakage.jsonl")
    blind_summary = read_json(blind_root / "summary.json")
    glossary_entries = parse_glossary(glossary_repository / "glossary.md")

    if len(senses) != 150 or len(candidates) != 450:
        raise ValueError("Dataset V3 cardinality drift")
    if len(leakage_records) != 45:
        raise ValueError("methodology-hardening leakage cardinality drift")

    contexts_by_id = {row["context_id"]: row for row in contexts}
    quarantined_blocks = {row["block_id"] for row in leakage_records}
    blind_refs = _blind_case_refs(blind_root)

    mappings: list[dict[str, Any]] = []
    mapping_by_sense: dict[str, dict[str, Any]] = {}
    for sense in sorted(senses, key=lambda row: row["sense_id"]):
        match = match_glossary(sense["source_term"], glossary_entries)
        matched_entries = match.pop("matched_entries")
        row = {
            "term_id": sense["term_id"],
            "sense_id": sense["sense_id"],
            "source_term": sense["source_term"],
            "split": sense["split"],
            "stratum": sense["stratum"],
            **match,
            "glossary_commit": glossary_identity["commit"],
            "glossary_source_line": matched_entries[0]["line_number"] if len(matched_entries) == 1 else None,
            "matched_entries_json": canonical_json_bytes(matched_entries).decode("utf-8"),
        }
        row["mapping_sha256"] = sha256_bytes(canonical_json_bytes(row))
        mappings.append(row)
        mapping_by_sense[sense["sense_id"]] = row

    risk_rows: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []
    active_ids_by_sense: dict[str, list[str]] = {}
    for sense in sorted(senses, key=lambda row: row["sense_id"]):
        active_ids = active_positive_ids(sense, contexts_by_id, quarantined_blocks)
        active_ids_by_sense[sense["sense_id"]] = active_ids
        risk_class, reasons = classify_risk(sense, mapping_by_sense[sense["sense_id"]], len(active_ids))
        risk_row = {
            "term_id": sense["term_id"],
            "sense_id": sense["sense_id"],
            "source_term": sense["source_term"],
            "split": sense["split"],
            "risk_class": risk_class,
            "risk_reasons": "|".join(reasons),
            "active_real_positive_context_count": len(active_ids),
            "review_requirement": _review_requirement(risk_class),
        }
        risk_row["risk_record_sha256"] = sha256_bytes(canonical_json_bytes(risk_row))
        risk_rows.append(risk_row)
        projections.append(
            build_projection(
                sense,
                mapping_by_sense[sense["sense_id"]],
                risk_class,
                reasons,
                active_ids,
                contexts_by_id,
                v3_manifest["manifest_sha256"],
                blind_refs,
            )
        )

    projection_by_sense = {row["sense_id"]: row for row in projections}
    normalized_candidates = normalize_candidates(candidates, slots, mapping_by_sense)

    reset_directory(output)
    (output / "dataset_fasttrack_policy_v1_1.md").write_text(POLICY_TEXT, encoding="utf-8", newline="\n")
    _write_glossary_snapshot(output, glossary_repository)
    commit_object_path = output / "d2l_vi_glossary_commit_object.bin"
    commit_object_path.write_bytes(glossary_identity["commit_object_payload"])
    git_acquisition_receipt = seal_record(
        {
            "schema_id": "D2LVIGlossaryGitAcquisitionReceiptV1",
            "policy_id": POLICY_ID,
            "repository": glossary_identity["remote_url"],
            "remote_ref": "refs/remotes/origin/main",
            "commit": glossary_identity["commit"],
            "tree_sha1": glossary_identity["tree_sha1"],
            "parent_sha1": glossary_identity["parent_sha1"],
            "subject": glossary_identity["subject"],
            "commit_timestamp": glossary_identity["commit_timestamp"],
            "commit_object_ref": commit_object_path.name,
            "commit_object_payload_sha256": glossary_identity["commit_object_payload_sha256"],
            "offline_commit_object_hash_verified": True,
            "source_repository_was_shallow": glossary_identity["source_is_shallow"],
            "commit_signature_present": glossary_identity["commit_signature_present"],
            "remote_signature_verified": False,
            "remote_signature_verification_note": "PUBLIC_KEY_NOT_BUNDLED; REMOTE AUTHENTICITY NOT CLAIMED",
            "acquired_at": created_at,
        },
        "receipt_sha256",
    )
    write_json(output / "d2l_vi_glossary_git_acquisition_receipt.json", git_acquisition_receipt)
    glossary_receipt = seal_record(
        {
            "schema_id": "D2LVIGlossaryAuthorityReceiptV1",
            "policy_id": POLICY_ID,
            "authority_role": "TIER_3_CANDIDATE_SOURCE_NOT_GOLD",
            "repository": "https://github.com/d2l-ai/d2l-vi.git",
            "commit": glossary_identity["commit"],
            "commit_timestamp": glossary_identity["commit_timestamp"],
            "file_path": "glossary.md",
            "physical_sha256": glossary_identity["glossary_sha256"],
            "license_path": "LICENSE",
            "license_sha256": glossary_identity["license_sha256"],
            "license_summary_path": "LICENSE-SUMMARY",
            "license_summary_sha256": glossary_identity["license_summary_sha256"],
            "retrieved_at": created_at,
            "entry_count": len(glossary_entries),
            "auto_approval_permitted": False,
        },
        "receipt_sha256",
    )
    write_json(output / "d2l_vi_glossary_authority_receipt.json", glossary_receipt)
    write_csv(output / "glossary_mapping_150_senses.csv", mappings, MAPPING_FIELDS)
    write_csv(output / "sense_risk_classification.csv", risk_rows, RISK_FIELDS)

    current_blind_cases, current_blind_receipt = build_blind_pack(
        output / "stage_a_blind_audit_pack.zip",
        senses,
        risk_rows,
        projections,
        contexts_by_id,
        sha256_bytes(canonical_json_bytes(projections)),
    )
    write_json(output / "stage_a_blind_selection_receipt.json", current_blind_receipt)
    selection_fields = [
        "blind_case_id",
        "selection_stratum",
        "term_id",
        "sense_id",
        "source_term",
        "split",
        "risk_class",
        "v3_stratum",
        "active_real_positive_context_count",
        "review_status",
        "record_sha256",
    ]
    write_csv(
        output / "stage_a_blind_selection.csv",
        [{field: row[field] for field in selection_fields} for row in current_blind_cases],
        selection_fields,
    )
    current_result_fields = [
        "blind_case_id",
        "sense_id",
        "source_term",
        "consensus_split_decision",
        "consensus_part_of_speech",
        "consensus_definition_en",
        "review_status",
        "adjudication_status",
    ]
    write_csv(
        output / "stage_a_blind_audit_results.csv",
        [
            {
                "blind_case_id": row["blind_case_id"],
                "sense_id": row["sense_id"],
                "source_term": row["source_term"],
                "consensus_split_decision": "",
                "consensus_part_of_speech": "",
                "consensus_definition_en": "",
                "review_status": "",
                "adjudication_status": "",
            }
            for row in current_blind_cases
        ],
        current_result_fields,
    )

    source_report = build_source_grounding_report(mappings, risk_rows, projections, leakage_records)
    source_report["blind_audit_status"] = "PENDING_CURRENT_FASTTRACK_BLIND_REVIEW"
    source_report["blind_case_count"] = len(current_blind_cases)
    source_report["blind_selection_matches_current_risk_policy"] = True
    source_report["historical_blind_audit_status"] = blind_summary["artifact_status"]
    source_report["historical_blind_case_count"] = blind_summary["blind_case_count"]
    source_report["historical_blind_adjudication_case_count"] = blind_summary["adjudication_case_count"]
    source_report = seal_record(source_report, "report_sha256")
    write_json(output / "stage_a_source_grounding_report.json", source_report)

    shutil.copyfile(blind_pack_zip, output / "historical_stage_a_blind_audit_pack.zip")
    shutil.copyfile(blind_result_zip, output / "historical_stage_a_blind_audit_result.zip")
    _write_blind_results(output / "historical_stage_a_blind_audit_results.csv", blind_root)
    write_jsonl(output / "stage_a_adjudication_001_004.jsonl", build_adjudication_records(senses))

    contracts_root = output / "effective_sense_contracts"
    contracts_root.mkdir()
    write_jsonl(contracts_root / "pending_effective_sense_projection.jsonl", projections)
    (contracts_root / "official_effective_sense_contracts.jsonl").write_bytes(b"")
    (contracts_root / "README.md").write_text(
        "# Effective Sense publication status\n\n"
        "All 150 rows are pending projections. Official Contracts V1.1 records: 0.\n"
        "Review/adjudication provenance must close before official publication.\n",
        encoding="utf-8",
        newline="\n",
    )

    write_jsonl(output / "candidate_provenance_450.jsonl", normalized_candidates)
    candidate_receipt = seal_record(
        {
            "schema_id": "D2LFastTrackCandidateGenerationReceiptV1",
            "policy_id": POLICY_ID,
            "status": "PROVENANCE_NORMALIZED_NO_NEW_GENERATION",
            "candidate_count": len(normalized_candidates),
            "sense_count": len({row["sense_id"] for row in normalized_candidates}),
            "source_type_counts": dict(sorted(Counter(row["candidate_source_type"] for row in normalized_candidates).items())),
            "parent_candidate_instances_sha256": sha256_file(v3_root / "candidate_instances.jsonl"),
            "parent_candidate_slots_sha256": sha256_file(v3_root / "candidate_slots.jsonl"),
            "provider_call_count": 0,
            "gold_label_count": 0,
            "final_glossary_decision": None,
        },
        "receipt_sha256",
    )
    write_json(output / "candidate_generation_receipt.json", candidate_receipt)

    write_json(output / "stage_b_review_schema.json", STAGE_B_SCHEMA)
    (output / "stage_b_review_instructions.md").write_text(STAGE_B_INSTRUCTIONS, encoding="utf-8", newline="\n")
    sense_by_id = {sense["sense_id"]: sense for sense in senses}
    stage_b_rows = []
    for candidate in normalized_candidates:
        sense = sense_by_id[candidate["sense_id"]]
        projection = projection_by_sense[candidate["sense_id"]]
        stage_b_rows.append(
            {
                "term_id": candidate["term_id"],
                "sense_id": candidate["sense_id"],
                "split": sense["split"],
                "source_term": sense["source_term"],
                "effective_sense_review_status": projection["review_status"],
                "candidate_id": candidate["candidate_id"],
                "candidate_role": candidate["candidate_role"],
                "candidate_vi": candidate["candidate_vi"],
                "candidate_source_type": candidate["candidate_source_type"],
                "candidate_gold_label": "",
                "allowed_scope": "",
                "validated_variants": "",
                "rejected_variants": "",
                "reason_codes": "",
                "positive_context_refs": "|".join(projection["positive_definition_evidence_ids"]),
                "vietnamese_evidence_refs": "",
                "reviewer_provenance_ref": "",
                "adjudication_ref": "",
            }
        )
    write_csv(output / "stage_b_annotation_template_450.csv", stage_b_rows, STAGE_B_FIELDS)

    write_jsonl(output / "quarantined_cross_split_source_blocks.jsonl", leakage_records)
    leakage_report = seal_record(
        {
            "schema_id": "D2LFastTrackSplitClusterRepairReportV1",
            "policy_id": POLICY_ID,
            "repair_mode": "COMPANION_ACTIVE_CONTEXT_QUARANTINE",
            "parent_split_assignments_mutated": False,
            "cross_split_cluster_count_before": len(leakage_records),
            "quarantined_block_count": len(quarantined_blocks),
            "cross_split_active_block_count_after": 0,
            "sense_count_with_zero_active_real_positive_context": sum(not ids for ids in active_ids_by_sense.values()),
            "status": "PASS" if all(active_ids_by_sense.values()) else "BLOCKED_ZERO_CONTEXT_AFTER_QUARANTINE",
        },
        "report_sha256",
    )
    write_json(output / "split_cluster_repair_report.json", leakage_report)

    controlled_registry = {
        "schema_id": "D2LFastTrackControlledVietnameseSourceRegistryV1",
        "policy_id": POLICY_ID,
        "entries": [
            {
                "source_id": "d2l_vi_glossary_c775d6b",
                "tier": 3,
                "source_kind": "COMMUNITY_TRANSLATION_GLOSSARY",
                "authority_receipt_ref": "d2l_vi_glossary_authority_receipt.json",
                "permitted_roles": ["CANDIDATE_ORIGIN", "VARIANT_SOURCE", "QUALIFIER_HINT"],
                "auto_approval_permitted_alone": False,
                "self_attestation_permitted": False,
            }
        ],
    }
    write_json(output / "controlled_vietnamese_source_registry.json", controlled_registry)

    risk_rank = {
        "R0_CLEAR": 0,
        "R1_QUALIFIED": 1,
        "R2_MISSING": 2,
        "R3_AMBIGUOUS": 3,
        "R4_SPLIT_OR_POS_RISK": 4,
    }
    pilot = sorted(
        (
            row
            for row in risk_rows
            if row["split"] == "development"
            and int(row["active_real_positive_context_count"]) > 0
        ),
        key=lambda row: (risk_rank[row["risk_class"]], row["sense_id"]),
    )[:15]
    pilot_report = seal_record(
        {
            "schema_id": "D2LFastTrackPilotReadinessV1",
            "policy_id": POLICY_ID,
            "selection_status": "SELECTED_PENDING_STAGE_A_FINALIZATION",
            "selected_sense_count": len(pilot),
            "selected_sense_ids": [row["sense_id"] for row in pilot],
            "selected_risk_counts": dict(sorted(Counter(row["risk_class"] for row in pilot).items())),
            "official_frozen_candidate_contract_count": 0,
            "complete_constraint_evidence_package_count": 0,
            "real_ce_pilot_allowed": False,
            "blockers": [
                "STAGE_A_REVIEW_PROVENANCE_INCOMPLETE",
                "RISK_REVIEW_AND_ADJUDICATION_INCOMPLETE",
                "FROZEN_CANDIDATE_CONTRACTS_NOT_EMITTED",
                "COMPLETE_CONSTRAINT_EVIDENCE_PACKAGES_NOT_EMITTED",
            ],
        },
        "report_sha256",
    )
    write_json(output / "pilot_15_readiness_report.json", pilot_report)

    acceptance_checks = {
        "mapped_150_senses": len(mappings) == 150,
        "real_positive_context_coverage_150": all(active_ids_by_sense.values()),
        "synthetic_positive_evidence_zero": True,
        "unresolved_r4_zero": not any(row["risk_class"] == "R4_SPLIT_OR_POS_RISK" for row in risk_rows),
        "blind_audit_selection_matches_current_risk_policy": current_blind_receipt["matches_current_risk_policy"],
        "blind_audit_complete": False,
        "review_provenance_complete": False,
        "all_required_r1_r2_r3_reviews_complete": False,
        "official_effective_sense_contract_count_150": False,
        "unresolved_sense_count_zero": False,
        "controlled_independent_attestation_registry_ready": False,
        "cross_split_active_block_count_zero": True,
        "pilot_frozen_candidate_contracts_15": False,
        "pilot_complete_constraint_evidence_packages_15": False,
    }
    acceptance = {
        "schema_id": "D2LFastTrackAcceptanceGateV1",
        "policy_id": POLICY_ID,
        "status": acceptance_gate_status(acceptance_checks),
        "checks": acceptance_checks,
        "provider_call_count": 0,
        "final_glossary_decision": None,
    }
    write_json(output / "acceptance_gate_report.json", acceptance)

    hardening_manifest = read_json(hardening_root / "manifest.json")
    blind_manifest = read_json(blind_root / "manifest.json")
    parent_fasttrack_root = repo_root / "dataset" / "d2l_dataset_fasttrack_glossary_first_v1" / "release" / "d2l_dataset_fasttrack_glossary_first_v1"
    parent_fasttrack_zip = parent_fasttrack_root.parent / "d2l_dataset_fasttrack_glossary_first_v1.zip"
    if not parent_fasttrack_root.is_dir() or not parent_fasttrack_zip.is_file():
        raise FileNotFoundError("immutable V1 fast-track parent artifact is missing")
    parent_fasttrack_manifest = read_json(parent_fasttrack_root / "manifest.json")
    source_bindings = {
        "parent_fasttrack_v1": {
            "artifact_name": parent_fasttrack_manifest["artifact_name"],
            "policy_id": parent_fasttrack_manifest["policy_id"],
            "manifest_sha256": parent_fasttrack_manifest["manifest_sha256"],
            "physical_manifest_sha256": sha256_file(parent_fasttrack_root / "manifest.json"),
            "zip_sha256": sha256_file(parent_fasttrack_zip),
            "status": parent_fasttrack_manifest["status"],
        },
        "dataset_v3": {
            "manifest_sha256": v3_manifest["manifest_sha256"],
            "physical_manifest_sha256": sha256_file(v3_root / "manifest.json"),
        },
        "methodology_hardening": {
            "manifest_sha256": hardening_manifest["artifact_manifest_sha256"],
            "physical_manifest_sha256": sha256_file(hardening_root / "manifest.json"),
        },
        "historical_blind_result": {
            "manifest_sha256": blind_manifest["manifest_sha256"],
            "physical_manifest_sha256": sha256_file(blind_root / "manifest.json"),
        },
        "terminology_contracts": {
            "authority_tag": CONTRACT_AUTHORITY_TAG,
            "authority_commit": CONTRACT_AUTHORITY_COMMIT,
            "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        },
    }
    write_json(output / "source_bindings.json", source_bindings)

    files = build_file_inventory(output, {"manifest.json", "CHECKSUMS.sha256"})
    manifest = {
        "schema_id": "D2LDatasetFastTrackGlossaryFirstManifestV1_1",
        "schema_version": "1.1.0",
        "policy_id": POLICY_ID,
        "artifact_name": ARTIFACT_NAME,
        "created_at": created_at,
        "status": "BLOCKED_PENDING_HUMAN_REVIEW_AND_PILOT_CONTRACTS",
        "counts": {
            "sense": len(senses),
            "candidate": len(normalized_candidates),
            "glossary_entry": len(glossary_entries),
            "quarantined_cross_split_cluster": len(leakage_records),
            "blind_case": len(current_blind_cases),
            "historical_blind_case": blind_summary["blind_case_count"],
            "official_effective_sense_contract": 0,
            "complete_frozen_candidate_contract": 0,
            "complete_constraint_evidence_package": 0,
        },
        "source_bindings": source_bindings,
        "files": files,
        "provider_call_count": 0,
        "final_glossary_decision": None,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    write_json(output / "manifest.json", manifest)
    write_checksums(output, output / "CHECKSUMS.sha256")

    zip_path = output.parent / f"{output.name}.zip"
    build_deterministic_zip(output, zip_path)
    (output.parent / f"{output.name}.zip.sha256").write_text(
        f"{sha256_file(zip_path)} *{zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return manifest
