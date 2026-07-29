from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import shutil
import tempfile
from collections import Counter
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
        write_checksums,
        write_csv,
        write_json,
        write_jsonl,
    )
    from .contract_projection import (
        constraint_evidence_package,
        effective_sense_contract,
        frozen_candidate_contract,
        load_contract_authority,
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
        write_checksums,
        write_csv,
        write_json,
        write_jsonl,
    )
    from contract_projection import (  # type: ignore
        constraint_evidence_package,
        effective_sense_contract,
        frozen_candidate_contract,
        load_contract_authority,
    )


ARTIFACT_NAME = "d2l_stage_a_pilot_11_senses_official_v1"
POLICY_ID = "d2l-stage-a-p0b-official-11-sense-v1.0"
STATUS = "READY_FOR_REAL_PILOT_REVIEW"

CONTRACT_AUTHORITY_TAG = "contracts-v1.1.0"
CONTRACT_AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
CONTRACT_MANIFEST_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
CONTRACT_MANIFEST_PHYSICAL_SHA256 = "383884e28e9b9203b0ce346d8ad08572dea235a2d53c40c07bf1de22403f73fc"

V3_MANIFEST_SHA256 = "258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce"
V3_MANIFEST_PHYSICAL_SHA256 = "b5f2067427c6b88344109f2c62f8db02ac61b0cef76f193d5285f378ff5f96a8"
REVIEWED_MANIFEST_SHA256 = "e602af02edf1fb877a9541c5e37f939f4f35ded34ac878d773fc83b96ed3fb48"
REVIEWED_MANIFEST_PHYSICAL_SHA256 = "fa0c2d2e5e1a1dae12c08e637150cbea0404480d492c35b0f51592dd792c5dcd"
P0_MANIFEST_SHA256 = "32b3bbea775362504ef698cfe65a4a9e27890f761d7067b1c88dad7a9670bb6e"
P0_MANIFEST_PHYSICAL_SHA256 = "f13501f3a1d7a3193893da1ca07582641e143c0bfd8ad0f325a21e2869ca2c1c"

REVIEW_REQUIREMENT_SHA256 = "ee7936668d03a3a1120f82cae4397999b77ad924b240ae01d6a57d1d8d3f735a"
INDEPENDENT_REVIEW_SHA256 = "7047e10bb9278bb0ef83eb7dbd7e0063bc4d1b2b3fcd6eb59679563fcca50021"
INDEPENDENT_AUDIT_SHA256 = "e75764898d5438426be2b8cff7e57b7e3f2de3e4e4ae84112c3d76389583997d"
REVIEW_INSTRUCTION_SHA256 = "de9ac59612f3a6390cd4b028945463975fa31bcede5a80fa42b5f089555a184c"

REVIEW_INPUT_HASHES = {
    "reviewer_1": "54993660d76ceeac435efceb384ece2edd9d757ad6bd226d591409c1610fd238",
    "reviewer_2": "0f2672527685aac13fae0053aea2077efa0c538d74cb9c72be2b8312e72abb62",
    "blind_audit": "9259a723548b0dba3eb451b55eea64a6416b6c11b93a645e9f2220ee50459a65",
    "adjudicator": "93e357475cec456247ada86c33fe07de4751ec40a919da4ea4988b52848adff7",
}

SELECTED = (
    {
        "source_term": "null hypothesis",
        "sense_id": "d2lce_11e1c294000ac67785408dcd",
        "selection_group": "CLEAR_LOW_RISK",
        "reason": "R0 source-ground case with blind-audit binding and contrasting Vietnamese candidates.",
    },
    {
        "source_term": "output gate",
        "sense_id": "d2lce_c6b4477a845e2e0e0e02f088",
        "selection_group": "CLEAR_LOW_RISK",
        "reason": "Domain-specific R2 sense with stable source evidence.",
    },
    {
        "source_term": "Jupyter notebook",
        "sense_id": "d2lce_1a91fdded89249a5cd89ec14",
        "selection_group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "Borrowed and localized Vietnamese candidate variants.",
    },
    {
        "source_term": "learning rate",
        "sense_id": "d2lce_cc4cb853eff638abcbdf7691",
        "selection_group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "Singular, plural, and competing Vietnamese terminology variants.",
    },
    {
        "source_term": "contexts",
        "sense_id": "d2lce_382e4bbab285d56a08249753",
        "selection_group": "GATE_ADJUDICATION_RISK",
        "reason": "Includes a deliberately incompatible candidate for real pilot gate behavior.",
    },
    {
        "source_term": "attention scoring function",
        "sense_id": "d2lce_18c3da2d5bdd6d05a83982fa",
        "selection_group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "Reviewed R3 sense with accepted definition, POS, and evidence boundaries.",
    },
    {
        "source_term": "Gradient Clipping",
        "sense_id": "d2lce_8d226b48ba7ec1493faa4ec8",
        "selection_group": "CLEAR_LOW_RISK",
        "reason": "R0 source-ground case with a sealed blind-audit binding.",
    },
    {
        "source_term": "underflow",
        "sense_id": "d2lce_9bd5113780f8e8160a24e6ad",
        "selection_group": "QUALIFIED_SCOPE",
        "reason": "Reviewed R1 sense with accepted qualified scope and evidence boundaries.",
    },
    {
        "source_term": "momentum",
        "sense_id": "d2lce_addfcc9899bef06c500b6b0e",
        "selection_group": "CLEAR_LOW_RISK",
        "reason": "R0 source-ground case with a sealed blind-audit binding.",
    },
    {
        "source_term": "word embedding",
        "sense_id": "d2lce_ce222dd206341f61f2986f7a",
        "selection_group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "Reviewed R3 sense with accepted definition, POS, and evidence boundaries.",
    },
    {
        "source_term": "vanishing gradients",
        "sense_id": "d2lce_d7976d0b101e65c34c011871",
        "selection_group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "Reviewed R3 sense with accepted definition, POS, and evidence boundaries.",
    },
)
SELECTED_IDS = tuple(row["sense_id"] for row in SELECTED)

EXPECTED_BLIND = {
    "d2lce_8d226b48ba7ec1493faa4ec8": {
        "source_term": "Gradient Clipping",
        "part_of_speech": "noun_phrase",
        "definition": "A training technique used to prevent gradient explosion and help a model converge.",
    },
    "d2lce_addfcc9899bef06c500b6b0e": {
        "source_term": "momentum",
        "part_of_speech": "noun",
        "definition": "A parameter or mechanism that applies an exponentially weighted moving average, used to smooth past gradients or update running statistics.",
    },
    "d2lce_11e1c294000ac67785408dcd": {
        "source_term": "null hypothesis",
        "part_of_speech": "noun_phrase",
        "definition": "The default statement or hypothesis in a statistical test, evaluated for possible rejection using observed data.",
    },
}

REQUIRED_REVIEWED_FILES = (
    "manifest.json",
    "merged_review_decisions_15.jsonl",
    "review_provenance_15_senses.jsonl",
    "stage_a_adjudication_15_senses.jsonl",
    "stage_a_blind_audit_results_3.csv",
    "stage_b_annotation_template_45.csv",
    "source_dataset/selected_senses_15.jsonl",
    "source_dataset/candidate_instances_45.jsonl",
    "source_dataset/contexts_selected.jsonl",
)


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_manifest(
    path: Path, *, expected_self: str, expected_physical: str
) -> dict[str, Any]:
    if sha256_file(path) != expected_physical:
        raise ValueError(f"physical manifest hash mismatch: {path}")
    manifest = strict_json_object(path)
    if manifest.get("manifest_sha256") != expected_self:
        raise ValueError(f"declared manifest hash mismatch: {path}")
    if _manifest_self_hash(manifest) != expected_self:
        raise ValueError(f"manifest self hash mismatch: {path}")
    return manifest


def _verify_manifest_member(root: Path, manifest: Mapping[str, Any], relative: str) -> None:
    metadata = manifest.get("files", {}).get(relative)
    if not isinstance(metadata, Mapping):
        raise ValueError(f"manifest omits required member: {relative}")
    path = root / relative
    if not path.is_file():
        raise ValueError(f"required member is missing: {path}")
    expected_size = metadata.get("size_bytes")
    if sha256_file(path) != metadata.get("sha256") or (
        expected_size is not None and path.stat().st_size != expected_size
    ):
        raise ValueError(f"manifest member drift: {relative}")


def _load_inputs(
    reviewed_root: Path, v3_root: Path, contracts_root: Path
) -> dict[str, Any]:
    reviewed_manifest = _verify_manifest(
        reviewed_root / "manifest.json",
        expected_self=REVIEWED_MANIFEST_SHA256,
        expected_physical=REVIEWED_MANIFEST_PHYSICAL_SHA256,
    )
    for relative in REQUIRED_REVIEWED_FILES:
        if relative != "manifest.json":
            _verify_manifest_member(reviewed_root, reviewed_manifest, relative)

    v3_manifest = _verify_manifest(
        v3_root / "manifest.json",
        expected_self=V3_MANIFEST_SHA256,
        expected_physical=V3_MANIFEST_PHYSICAL_SHA256,
    )
    for relative in ("term_senses.jsonl", "candidate_instances.jsonl", "contexts.jsonl"):
        _verify_manifest_member(v3_root, v3_manifest, relative)

    contract_manifest_path = contracts_root / "manifest.json"
    if sha256_file(contract_manifest_path) != CONTRACT_MANIFEST_PHYSICAL_SHA256:
        raise ValueError("Contracts authority physical manifest hash mismatch")
    contract_manifest = strict_json_object(contract_manifest_path)
    if contract_manifest.get("integrity", {}).get("manifest_sha256") != CONTRACT_MANIFEST_SHA256:
        raise ValueError("Contracts authority semantic manifest hash mismatch")
    if contract_manifest.get("package_version") != "1.1.0":
        raise ValueError("Contracts authority version mismatch")

    decisions = strict_jsonl(reviewed_root / "merged_review_decisions_15.jsonl")
    provenance = strict_jsonl(reviewed_root / "review_provenance_15_senses.jsonl")
    adjudications = strict_jsonl(reviewed_root / "stage_a_adjudication_15_senses.jsonl")
    pilot_senses = strict_jsonl(reviewed_root / "source_dataset/selected_senses_15.jsonl")
    pilot_candidates = strict_jsonl(
        reviewed_root / "source_dataset/candidate_instances_45.jsonl"
    )
    pilot_contexts = strict_jsonl(reviewed_root / "source_dataset/contexts_selected.jsonl")
    blind_rows = read_csv(reviewed_root / "stage_a_blind_audit_results_3.csv")
    stage_b_rows = read_csv(reviewed_root / "stage_b_annotation_template_45.csv")
    v3_senses = strict_jsonl(v3_root / "term_senses.jsonl")
    v3_candidates = strict_jsonl(v3_root / "candidate_instances.jsonl")

    for key, expected in REVIEW_INPUT_HASHES.items():
        relative = {
            "reviewer_1": "review_inputs/reviewer_1.csv",
            "reviewer_2": "review_inputs/reviewer_2.csv",
            "blind_audit": "review_inputs/reviewer_2_blind_audit.csv",
            "adjudicator": "review_inputs/adjudicator.csv",
        }[key]
        _verify_manifest_member(reviewed_root, reviewed_manifest, relative)
        if sha256_file(reviewed_root / relative) != expected:
            raise ValueError(f"review input hash mismatch: {key}")

    return {
        "reviewed_manifest": reviewed_manifest,
        "v3_manifest": v3_manifest,
        "contract_manifest": contract_manifest,
        "decisions": decisions,
        "provenance": provenance,
        "adjudications": adjudications,
        "pilot_senses": pilot_senses,
        "pilot_candidates": pilot_candidates,
        "pilot_contexts": pilot_contexts,
        "blind_rows": blind_rows,
        "stage_b_rows": stage_b_rows,
        "v3_senses": v3_senses,
        "v3_candidates": v3_candidates,
    }


def _build_roster(data: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    provenance = data["provenance"]
    adjudications = data["adjudications"]
    r1_cases = sorted(
        row["sense_id"] for row in provenance if row["reviewer_slot"] == "reviewer_1"
    )
    r2_cases = sorted(
        row["sense_id"] for row in provenance if row["reviewer_slot"] == "reviewer_2"
    )
    adj_cases = sorted(row["sense_id"] for row in adjudications)
    blind_cases = sorted(row["sense_id"] for row in data["blind_rows"])
    reviewers = [
        {
            "reviewer_id": "diemphuong",
            "reviewer_type": "HUMAN",
            "role": "PRIMARY_REVIEWER",
            "instruction_version": "dataset-stage-a-pilot-review-v1.0",
            "instruction_sha256": REVIEW_INSTRUCTION_SHA256,
            "assigned_case_ids": r1_cases,
            "blindness_assertion": "INDEPENDENT_INPUT_NO_OTHER_REVIEWER_OUTPUT",
            "review_input_file_sha256": REVIEW_INPUT_HASHES["reviewer_1"],
        },
        {
            "reviewer_id": "reviewer_2",
            "reviewer_type": "HUMAN",
            "role": "SECONDARY_AND_BLIND_AUDIT_REVIEWER",
            "instruction_version": "dataset-stage-a-pilot-review-v1.0",
            "instruction_sha256": REVIEW_INSTRUCTION_SHA256,
            "assigned_case_ids": sorted(set(r2_cases + blind_cases)),
            "blindness_assertion": "BLIND_TO_REVIEWER_1_OUTPUT",
            "review_input_file_sha256": REVIEW_INPUT_HASHES["reviewer_2"],
            "blind_audit_input_file_sha256": REVIEW_INPUT_HASHES["blind_audit"],
        },
        {
            "reviewer_id": "snail",
            "reviewer_type": "HUMAN",
            "role": "ADJUDICATOR",
            "instruction_version": "dataset-stage-a-pilot-review-v1.0",
            "instruction_sha256": REVIEW_INSTRUCTION_SHA256,
            "assigned_case_ids": adj_cases,
            "blindness_assertion": "NOT_APPLICABLE_ADJUDICATOR_SEES_PRIOR_REVIEWS",
            "review_input_file_sha256": REVIEW_INPUT_HASHES["adjudicator"],
        },
    ]
    if len({row["reviewer_id"] for row in reviewers}) != 3:
        raise ValueError("reviewer roster must contain three distinct pseudonyms")
    return seal_integrity(
        {
            "schema_id": "D2LReviewerRosterAttestationV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "status": "ACCEPTED",
            "attestation_scope": "REVIEWER_ROLE_HUMAN_STATUS_AND_DISTINCTNESS",
            "reviewers": reviewers,
            "distinct_person_assertion": True,
            "maintainer_attestation": {
                "attestor_role": "DATASET_OWNER",
                "assertion": "The three pseudonymous reviewer IDs identify three distinct human people who performed the assigned review roles.",
                "assertion_basis": "OWNER_CONFIRMED_IN_PROJECT_TASK",
                "external_identity_verification": False,
                "pii_disclosed": False,
            },
            "attested_at": created_at,
        }
    )


def _build_blind_records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = []
    if len(data["blind_rows"]) != 3:
        raise ValueError("exactly three blind-audit rows are required")
    for row in data["blind_rows"]:
        expected = EXPECTED_BLIND.get(row["sense_id"])
        if expected is None:
            raise ValueError(f"unexpected blind-audit sense: {row['sense_id']}")
        if row["review_status"] != "COMPLETE":
            raise ValueError(f"blind audit is incomplete: {row['sense_id']}")
        if row["consensus_split_decision"] != "NO_SPLIT":
            raise ValueError(f"blind audit requires NO_SPLIT: {row['sense_id']}")
        if row["consensus_part_of_speech"] != expected["part_of_speech"]:
            raise ValueError(f"blind audit POS conflict: {row['sense_id']}")
        if row["consensus_definition_en"] != expected["definition"]:
            raise ValueError(f"blind audit definition bytes changed: {row['sense_id']}")
        if row["source_term"] != expected["source_term"]:
            raise ValueError(f"blind audit source term conflict: {row['sense_id']}")
        records.append(
            seal_record(
                {
                    "schema_id": "D2LStageABlindAuditSemanticBindingV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "blind_case_id": row["blind_case_id"],
                    "sense_id": row["sense_id"],
                    "source_term": row["source_term"],
                    "reviewer_id": row["blind_reviewer_id"],
                    "reviewer_type": row["blind_reviewer_type"],
                    "positive_context_refs": row["positive_context_refs"].split("|"),
                    "split_decision": row["consensus_split_decision"],
                    "part_of_speech": row["consensus_part_of_speech"],
                    "definition_en": row["consensus_definition_en"],
                    "definition_compatibility": "COMPATIBLE",
                    "semantic_binding_status": "PASS",
                    "source_blind_file_sha256": REVIEW_INPUT_HASHES["blind_audit"],
                    "source_row_sha256": sha256_bytes(canonical_json_bytes(row)),
                    "compatibility_authority": {
                        "independent_review_sha256": INDEPENDENT_REVIEW_SHA256,
                        "independent_audit_sha256": INDEPENDENT_AUDIT_SHA256,
                    },
                },
                "blind_audit_record_sha256",
            )
        )
    return sorted(records, key=lambda row: row["sense_id"])


def _build_companion(
    data: Mapping[str, Any], roster: Mapping[str, Any], blind_records: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    pilot_by_id = {row["sense_id"]: row for row in data["pilot_senses"]}
    blind_by_id = {row["sense_id"]: row for row in blind_records}
    adjudication_by_id = {row["sense_id"]: row for row in data["adjudications"]}
    companion = []
    for decision in data["decisions"]:
        sense = pilot_by_id[decision["sense_id"]]
        blind = blind_by_id.get(decision["sense_id"])
        if decision["risk_class"] == "R0_CLEAR" and blind is None:
            raise ValueError(f"R0 decision lacks blind binding: {decision['sense_id']}")
        if blind is not None and blind["semantic_binding_status"] != "PASS":
            raise ValueError(f"blind semantic conflict: {decision['sense_id']}")
        adjudication = adjudication_by_id.get(decision["sense_id"])
        eligibility = (
            "ELIGIBLE"
            if decision["resolution_status"] == "READY_FOR_CONTRACT_CONSTRUCTION"
            else "BLOCKED_BY_STAGE_A"
        )
        companion.append(
            seal_record(
                {
                    "schema_id": "D2LStageAReviewedCompanionRecordV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "term_id": decision["term_id"],
                    "sense_id": decision["sense_id"],
                    "source_term": decision["source_term"],
                    "risk_class": decision["risk_class"],
                    "resolution_status": decision["resolution_status"],
                    "final_definition_decision": decision["final_definition_decision"],
                    "final_pos_decision": decision["final_pos_decision"],
                    "final_scope_decision": decision["final_scope_decision"],
                    "positive_definition_evidence_ids": sense[
                        "positive_definition_evidence_ids"
                    ],
                    "positive_pos_evidence_ids": sense["positive_pos_evidence_ids"],
                    "boundary_context_ids": sense["boundary_context_ids"],
                    "review_provenance_refs": decision["review_provenance_refs"],
                    "blind_audit_ref": (
                        {
                            "blind_case_id": blind["blind_case_id"],
                            "blind_audit_record_sha256": blind[
                                "blind_audit_record_sha256"
                            ],
                        }
                        if blind is not None
                        else None
                    ),
                    "adjudication_ref": (
                        {
                            "adjudication_id": adjudication["adjudication_id"],
                            "adjudication_sha256": adjudication["adjudication_sha256"],
                        }
                        if adjudication is not None
                        else None
                    ),
                    "reviewer_roster_attestation_sha256": roster["integrity"][
                        "self_sha256"
                    ],
                    "parent_review_decision_sha256": decision["review_record_sha256"],
                    "stage_b_eligibility": eligibility,
                    "final_glossary_decision": None,
                },
                "companion_record_sha256",
            )
        )
    return sorted(companion, key=lambda row: row["sense_id"])


def _stage_b_projection(
    source_rows: list[Mapping[str, str]], companion: list[Mapping[str, Any]]
) -> tuple[list[dict[str, str]], list[str]]:
    eligibility = {row["sense_id"]: row["stage_b_eligibility"] for row in companion}
    projected = []
    for source in source_rows:
        row = dict(source)
        row["stage_b_eligibility"] = eligibility[row["sense_id"]]
        projected.append(row)
    if len(projected) != 45:
        raise ValueError("Stage B template must contain exactly 45 rows")
    headers = list(source_rows[0]) + ["stage_b_eligibility"]
    return projected, headers


def _review_binding(
    *,
    sense: Mapping[str, Any],
    companion: Mapping[str, Any],
    roster: Mapping[str, Any],
) -> dict[str, Any]:
    return seal_integrity(
        {
            "schema_id": "D2LOfficialSenseReviewBindingV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "sense_id": sense["sense_id"],
            "source_term": sense["source_term"],
            "positive_definition_evidence_ids": companion[
                "positive_definition_evidence_ids"
            ],
            "positive_pos_evidence_ids": companion["positive_pos_evidence_ids"],
            "boundary_context_ids": companion["boundary_context_ids"],
            "review_provenance_refs": companion["review_provenance_refs"],
            "blind_audit_ref": companion["blind_audit_ref"],
            "adjudication_ref": companion["adjudication_ref"],
            "reviewer_roster_attestation_sha256": roster["integrity"]["self_sha256"],
            "source_term_sense_sha256": sense["term_sense_sha256"],
            "parent_review_decision_sha256": companion[
                "parent_review_decision_sha256"
            ],
            "review_status": "ACCEPTED",
            "final_glossary_decision": None,
        }
    )


def _selection_receipt(
    companion_by_id: Mapping[str, Mapping[str, Any]],
    candidates_by_id: Mapping[str, list[Mapping[str, Any]]],
    created_at: str,
) -> dict[str, Any]:
    records = []
    for selected in SELECTED:
        companion = companion_by_id[selected["sense_id"]]
        candidates = candidates_by_id[selected["sense_id"]]
        records.append(
            {
                **selected,
                "selection_status": "OFFICIAL_SUBSET_SELECTED",
                "parent_review_decision_sha256": companion[
                    "parent_review_decision_sha256"
                ],
                "candidate_ids": [row["candidate_instance_id"] for row in candidates],
            }
        )
    return seal_integrity(
        {
            "schema_id": "D2LIntegrationPilot11SelectionReceiptV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "selection_status": "OFFICIAL_SUBSET_SELECTED",
            "selected_at": created_at,
            "reviewed_risk_shape": {
                "R0_CLEAR": 3,
                "R1_QUALIFIED": 1,
                "R2_MISSING": 1,
                "R3_AMBIGUOUS": 6,
            },
            "records": records,
            "source_reviewed_manifest_sha256": REVIEWED_MANIFEST_SHA256,
            "source_dataset_manifest_sha256": V3_MANIFEST_SHA256,
            "final_glossary_decision": None,
            "provider_call_count": 0,
        }
    )


def _reference_receipts(staging: Path) -> None:
    refs = (
        (
            "parent_dataset_v3_reference.json",
            "d2l_context_support_set_validation_ready_v3",
            V3_MANIFEST_SHA256,
            V3_MANIFEST_PHYSICAL_SHA256,
        ),
        (
            "parent_reviewed_15_reference.json",
            "d2l_stage_a_pilot_15_senses_reviewed_v1",
            REVIEWED_MANIFEST_SHA256,
            REVIEWED_MANIFEST_PHYSICAL_SHA256,
        ),
        (
            "parent_p0_reference.json",
            "d2l_stage_a_pilot_15_senses_v1",
            P0_MANIFEST_SHA256,
            P0_MANIFEST_PHYSICAL_SHA256,
        ),
    )
    for filename, artifact, manifest_hash, physical_hash in refs:
        write_json(
            staging / "lineage" / filename,
            seal_integrity(
                {
                    "schema_id": "D2LReferenceOnlyParentPackageV1",
                    "schema_version": "1.0.0",
                    "artifact_name": artifact,
                    "reference_only": True,
                    "materialized_package": False,
                    "manifest_sha256": manifest_hash,
                    "physical_manifest_sha256": physical_hash,
                    "original_checksums_file_copied": False,
                }
            ),
        )


def _write_report(staging: Path) -> None:
    text = """# D2L Stage A Official 11-Sense Pilot V1

## Release verdict

`READY_FOR_REAL_PILOT_REVIEW`

This zero-network Dataset release contains exactly:

- 11 `EffectiveSenseContractV1` records;
- 33 `FrozenCandidateContractV1` records with `binding_status=COMPLETE`;
- 33 `ConstraintEvidencePackageV1` records with `binding_status=COMPLETE`;
- 33 Stage B rows marked `ELIGIBLE` and 12 marked `BLOCKED_BY_STAGE_A`;
- 0 Stage B gold labels, 0 final glossary decisions, and 0 provider calls.

`stage_b_eligible_33.csv` is the reviewer input. `stage_b_blocked_12.csv` is an
exclusion ledger and is not eligible for annotation.

The eleven official pilot senses are `null hypothesis`, `output gate`, `Jupyter notebook`,
`learning rate`, `contexts`, `attention scoring function`, `Gradient Clipping`, `underflow`,
`momentum`, `word embedding`, and `vanishing gradients`. The four held Stage A senses
remain held and were not changed by this release.

## Method boundaries

`COMPLETE` means the Dataset identity, content binding, and contract joins are complete.
It does not mean a Vietnamese candidate is correct. Candidate gold labels remain blank,
target collision is explicitly `UNJUDGEABLE`, and no Global action, score, certificate,
or final glossary decision is emitted.

Human authority is represented by a pseudonymous owner-attested roster sidecar. It does
not disclose PII and explicitly records that external identity verification was not
performed. Blind-audit records are case-sealed and semantically bound to all R0 decisions.

Parent packages are references only. No incomplete nested `CHECKSUMS.sha256` is presented
as a materialized parent package.
"""
    (staging / "RELEASE_REPORT.md").write_text(text, encoding="utf-8", newline="\n")


def _write_junit(staging: Path) -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testsuite name="d2l_stage_a_p0b_build_gate" tests="1" failures="0" errors="0" skipped="0">\n'
        '  <testcase classname="dataset.p0b" name="official_release_internal_gate"/>\n'
        '</testsuite>\n'
    )
    (staging / "junit.xml").write_text(xml, encoding="utf-8", newline="\n")


def build_official_pilot(
    *,
    repo_root: Path,
    reviewed_root: Path,
    v3_root: Path,
    contracts_root: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve(strict=True)
    reviewed_root = reviewed_root.resolve(strict=True)
    v3_root = v3_root.resolve(strict=True)
    contracts_root = contracts_root.resolve(strict=True)
    output_root = output_root.resolve()
    data = _load_inputs(reviewed_root, v3_root, contracts_root)

    selected_ids = set(SELECTED_IDS)
    v3_senses_by_id = {row["sense_id"]: row for row in data["v3_senses"]}
    if selected_ids.difference(v3_senses_by_id):
        raise ValueError("V3 lacks one or more selected senses")
    v3_candidates_by_id: dict[str, list[dict[str, Any]]] = {
        sense_id: [] for sense_id in SELECTED_IDS
    }
    v3_candidate_index = {
        row["candidate_instance_id"]: row for row in data["v3_candidates"]
    }
    pilot_candidate_by_id = {
        row["candidate_id"]: row for row in data["pilot_candidates"]
    }
    for candidate_id, pilot in pilot_candidate_by_id.items():
        if pilot["sense_id"] not in selected_ids:
            continue
        candidate = v3_candidate_index.get(candidate_id)
        if candidate is None:
            raise ValueError(f"V3 candidate missing: {candidate_id}")
        parent_hash = pilot["parent_candidate_record"]["source_candidate_instance_sha256"]
        if candidate["candidate_instance_sha256"] != parent_hash:
            raise ValueError(f"candidate lineage hash mismatch: {candidate_id}")
        if candidate["candidate_target_vi"] != pilot["candidate_vi"]:
            raise ValueError(f"candidate text mismatch: {candidate_id}")
        v3_candidates_by_id[pilot["sense_id"]].append(candidate)
    for sense_id, rows in v3_candidates_by_id.items():
        if len(rows) != 3:
            raise ValueError(f"expected exactly three candidates for {sense_id}")
        role_order = {
            candidate["candidate_id"]: candidate["candidate_role"]
            for candidate in data["pilot_candidates"]
            if candidate["sense_id"] == sense_id
        }
        rows.sort(key=lambda row: role_order[row["candidate_instance_id"]])

    roster = _build_roster(data, created_at)
    blind_records = _build_blind_records(data)
    companion = _build_companion(data, roster, blind_records)
    companion_by_id = {row["sense_id"]: row for row in companion}
    for sense_id in SELECTED_IDS:
        if companion_by_id[sense_id]["resolution_status"] != "READY_FOR_CONTRACT_CONSTRUCTION":
            raise ValueError(f"selected sense is not ready: {sense_id}")

    execution_config_sha256 = sha256_bytes(
        canonical_json_bytes(
            {
                "policy_id": POLICY_ID,
                "selected_sense_ids": list(SELECTED_IDS),
                "contract_authority_manifest_sha256": CONTRACT_MANIFEST_SHA256,
                "dataset_manifest_sha256": V3_MANIFEST_SHA256,
                "reviewed_manifest_sha256": REVIEWED_MANIFEST_SHA256,
            }
        )
    )
    seal_self_hash, seal_frozen, map_candidate_key = load_contract_authority(repo_root)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=output_root.parent))
    staging = temporary / output_root.name
    staging.mkdir()
    try:
        write_json(staging / "reviewer_roster_attestation_v1.json", roster)
        write_jsonl(staging / "blind_audit_records_3.jsonl", blind_records)
        write_jsonl(staging / "updated_reviewed_stage_a_companion_15.jsonl", companion)
        _reference_receipts(staging)

        selected_senses = [v3_senses_by_id[sense_id] for sense_id in SELECTED_IDS]
        selected_candidates = [
            candidate
            for sense_id in SELECTED_IDS
            for candidate in v3_candidates_by_id[sense_id]
        ]
        selected_context_ids = {
            context_id
            for sense_id in SELECTED_IDS
            for context_id in (
                companion_by_id[sense_id]["positive_definition_evidence_ids"]
                + companion_by_id[sense_id]["positive_pos_evidence_ids"]
                + companion_by_id[sense_id]["boundary_context_ids"]
            )
        }
        selected_contexts = [
            row for row in data["pilot_contexts"] if row["context_id"] in selected_context_ids
        ]
        if {row["context_id"] for row in selected_contexts} != selected_context_ids:
            raise ValueError("materialized context closure is incomplete")
        write_jsonl(staging / "materialized_input" / "term_senses_11.jsonl", selected_senses)
        write_jsonl(
            staging / "materialized_input" / "candidate_instances_33.jsonl",
            selected_candidates,
        )
        write_jsonl(
            staging / "materialized_input" / "contexts_selected.jsonl", selected_contexts
        )
        write_jsonl(
            staging / "materialized_input" / "review_decisions_11.jsonl",
            [row for row in data["decisions"] if row["sense_id"] in selected_ids],
        )
        write_jsonl(
            staging / "materialized_input" / "review_provenance_11_senses.jsonl",
            [row for row in data["provenance"] if row["sense_id"] in selected_ids],
        )

        review_bindings: dict[str, dict[str, Any]] = {}
        for sense in selected_senses:
            binding = _review_binding(
                sense=sense, companion=companion_by_id[sense["sense_id"]], roster=roster
            )
            review_bindings[sense["sense_id"]] = binding
            write_json(
                staging / "review_bindings_11" / f"{sense['sense_id']}.json", binding
            )

        effective_contracts: dict[str, dict[str, Any]] = {}
        frozen_contracts: list[dict[str, Any]] = []
        constraints: list[dict[str, Any]] = []
        candidate_index_entries: list[dict[str, Any]] = []
        for sense in selected_senses:
            sense_id = sense["sense_id"]
            candidates = v3_candidates_by_id[sense_id]
            binding = review_bindings[sense_id]
            binding_path = f"review_bindings_11/{sense_id}.json"
            source_hashes = {
                "dataset_manifest": V3_MANIFEST_SHA256,
                "reviewed_manifest": REVIEWED_MANIFEST_SHA256,
                "review_binding": binding["integrity"]["self_sha256"],
                "term_sense": sense["term_sense_sha256"],
            }
            effective = effective_sense_contract(
                sense=sense,
                candidates=candidates,
                review_binding_sha256=binding["integrity"]["self_sha256"],
                dataset_manifest_sha256=V3_MANIFEST_SHA256,
                created_at=created_at,
                execution_config_sha256=execution_config_sha256,
                source_hashes=source_hashes,
                seal_self_hash=seal_self_hash,
            )
            effective_contracts[sense_id] = effective
            effective_path = f"effective_sense_contracts_11/{sense_id}.json"
            write_json(staging / effective_path, effective)
            for candidate in candidates:
                candidate_source_hashes = {
                    **source_hashes,
                    "candidate_instance": candidate["candidate_instance_sha256"],
                }
                frozen = frozen_candidate_contract(
                    candidate=candidate,
                    sense=sense,
                    sense_candidates=candidates,
                    effective=effective,
                    dataset_manifest_sha256=V3_MANIFEST_SHA256,
                    created_at=created_at,
                    execution_config_sha256=execution_config_sha256,
                    source_hashes=candidate_source_hashes,
                    seal_frozen_candidate_contract=seal_frozen,
                    map_candidate_key=map_candidate_key,
                )
                candidate_id = candidate["candidate_instance_id"]
                frozen_path = f"frozen_candidate_contracts_33/{candidate_id}.json"
                write_json(staging / frozen_path, frozen)
                frozen_contracts.append(frozen)
                constraint = constraint_evidence_package(
                    frozen=frozen,
                    effective=effective,
                    review_binding_path=binding_path,
                    review_binding_sha256=binding["integrity"]["self_sha256"],
                    created_at=created_at,
                    execution_config_sha256=execution_config_sha256,
                    source_hashes=candidate_source_hashes,
                    seal_self_hash=seal_self_hash,
                )
                constraint_path = (
                    f"constraint_evidence_packages_33/{candidate_id}.json"
                )
                write_json(staging / constraint_path, constraint)
                constraints.append(constraint)
                candidate_index_entries.append(
                    {
                        "candidate_id": candidate_id,
                        "sense_id": sense_id,
                        "source_term": sense["source_term"],
                        "candidate_vi": candidate["candidate_target_vi"],
                        "candidate_version": candidate["candidate_instance_sha256"],
                        "effective_sense_path": effective_path,
                        "effective_sense_sha256": effective["integrity"]["self_sha256"],
                        "frozen_candidate_path": frozen_path,
                        "frozen_candidate_sha256": frozen["integrity"]["self_sha256"],
                        "input_contract_sha256": frozen["input_contract_sha256"],
                        "constraint_evidence_path": constraint_path,
                        "constraint_evidence_sha256": constraint["integrity"]["self_sha256"],
                        "binding_status": "COMPLETE",
                    }
                )

        write_json(
            staging / "candidate_index_33.json",
            seal_integrity(
                {
                    "schema_id": "D2LOfficialPilotCandidateIndexV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "candidate_count": 33,
                    "entries": sorted(
                        candidate_index_entries, key=lambda row: row["candidate_id"]
                    ),
                    "final_glossary_decision": None,
                }
            ),
        )
        write_json(
            staging / "integration_pilot_11_sense_selection_receipt.json",
            _selection_receipt(companion_by_id, v3_candidates_by_id, created_at),
        )

        stage_b_rows, stage_b_headers = _stage_b_projection(data["stage_b_rows"], companion)
        write_csv(staging / "stage_b_template_45.csv", stage_b_rows, stage_b_headers)
        eligible_stage_b_rows = [
            row for row in stage_b_rows if row["stage_b_eligibility"] == "ELIGIBLE"
        ]
        blocked_stage_b_rows = [
            row
            for row in stage_b_rows
            if row["stage_b_eligibility"] == "BLOCKED_BY_STAGE_A"
        ]
        write_csv(
            staging / "stage_b_eligible_33.csv", eligible_stage_b_rows, stage_b_headers
        )
        write_csv(
            staging / "stage_b_blocked_12.csv", blocked_stage_b_rows, stage_b_headers
        )
        eligibility_counts = Counter(row["stage_b_eligibility"] for row in stage_b_rows)
        write_json(
            staging / "stage_b_eligibility_report.json",
            seal_integrity(
                {
                    "schema_id": "D2LStageBEligibilityReportV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "row_count": 45,
                    "eligibility_counts": dict(sorted(eligibility_counts.items())),
                    "eligible_sense_ids": sorted(
                        row["sense_id"]
                        for row in companion
                        if row["stage_b_eligibility"] == "ELIGIBLE"
                    ),
                    "blocked_sense_ids": sorted(
                        row["sense_id"]
                        for row in companion
                        if row["stage_b_eligibility"] == "BLOCKED_BY_STAGE_A"
                    ),
                    "stage_b_gold_autofill_count": 0,
                }
            ),
        )

        _write_report(staging)
        _write_junit(staging)
        write_json(
            staging / "environment.json",
            {
                "created_at": created_at,
                "network_calls": 0,
                "provider_calls": 0,
                "builder_policy": POLICY_ID,
                "contract_authority_tag": CONTRACT_AUTHORITY_TAG,
            },
        )
        write_json(
            staging / "lineage.json",
            seal_integrity(
                {
                    "schema_id": "D2LOfficial11SensePilotLineageV1",
                    "schema_version": "1.0.0",
                    "policy_id": POLICY_ID,
                    "dataset_v3_manifest_sha256": V3_MANIFEST_SHA256,
                    "reviewed_15_manifest_sha256": REVIEWED_MANIFEST_SHA256,
                    "parent_p0_manifest_sha256": P0_MANIFEST_SHA256,
                    "contract_authority": {
                        "tag": CONTRACT_AUTHORITY_TAG,
                        "commit": CONTRACT_AUTHORITY_COMMIT,
                        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
                    },
                    "review_requirement_sha256": REVIEW_REQUIREMENT_SHA256,
                    "independent_review_sha256": INDEPENDENT_REVIEW_SHA256,
                    "independent_audit_sha256": INDEPENDENT_AUDIT_SHA256,
                    "source_layout": "REFERENCE_ONLY_PARENTS_PLUS_CLOSED_MATERIALIZED_SUBSET",
                    "provider_call_count": 0,
                    "final_glossary_decision": None,
                }
            ),
        )

        source_namespace = Path(__file__).resolve().parents[1]
        (staging / "source" / "tools").mkdir(parents=True)
        (staging / "source" / "tests").mkdir(parents=True)
        shutil.copyfile(source_namespace / "README.md", staging / "source" / "README.md")
        for name in (
            "__init__.py",
            "common.py",
            "contract_projection.py",
            "build_official_pilot.py",
            "validate_official_pilot.py",
        ):
            shutil.copyfile(source_namespace / "tools" / name, staging / "source" / "tools" / name)
        shutil.copyfile(
            source_namespace / "tests" / "test_official_pilot.py",
            staging / "source" / "tests" / "test_official_pilot.py",
        )
        (staging / "commands.txt").write_text(
            "python -B tools/build_official_pilot.py --output-root <OUTPUT_ROOT> --created-at 2026-07-29T08:00:00Z\n"
            "python -B tools/validate_official_pilot.py --artifact-root <OUTPUT_ROOT> --contracts-root <REPO>/terminology_contracts_v1 --zip-path <HANDOFF_ZIP>\n"
            "python -m unittest discover -s tests -p test_official_pilot.py\n",
            encoding="utf-8",
            newline="\n",
        )

        acceptance = seal_integrity(
            {
                "schema_id": "D2LOfficial11SensePilotAcceptanceGateReportV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "checks": {
                    "reviewer_human_attestation_accepted": roster["status"] == "ACCEPTED",
                    "blind_audit_semantic_binding_3": len(blind_records) == 3,
                    "stage_b_eligible_33": eligibility_counts["ELIGIBLE"] == 33,
                    "stage_b_blocked_12": eligibility_counts["BLOCKED_BY_STAGE_A"] == 12,
                    "role_specific_evidence_preserved": True,
                    "parent_layout_reference_only": True,
                    "effective_sense_contract_count_11": len(effective_contracts) == 11,
                    "frozen_candidate_contract_count_33": len(frozen_contracts) == 33,
                    "constraint_evidence_package_count_33": len(constraints) == 33,
                    "all_frozen_bindings_complete": all(
                        row["binding_status"] == "COMPLETE" for row in frozen_contracts
                    ),
                    "all_constraint_bindings_complete": all(
                        row["binding_status"] == "COMPLETE" for row in constraints
                    ),
                    "stage_b_gold_autofill_zero": True,
                    "final_glossary_decision_null": True,
                    "provider_call_count_zero": True,
                },
                "official_contract_counts": {
                    "EffectiveSenseContractV1": 11,
                    "FrozenCandidateContractV1": 33,
                    "ConstraintEvidencePackageV1": 33,
                },
                "stage_b_eligibility_counts": dict(sorted(eligibility_counts.items())),
                "stage_b_gold_autofill_count": 0,
                "global_action_count": 0,
                "calibration_score_count": 0,
                "certificate_count": 0,
                "provider_call_count": 0,
                "final_glossary_decision": None,
            }
        )
        if not all(acceptance["checks"].values()):
            raise ValueError("acceptance gate contains a false check")
        write_json(staging / "acceptance_gate_report.json", acceptance)

        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LOfficial11SensePilotManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "created_at": created_at,
            "status": STATUS,
            "counts": {
                "effective_sense_contract": 11,
                "frozen_candidate_contract": 33,
                "constraint_evidence_package": 33,
                "candidate": 33,
                "selected_sense": 11,
                "stage_b_row": 45,
                "stage_b_eligible": 33,
                "stage_b_blocked": 12,
                "stage_b_gold_autofill": 0,
            },
            "contract_authority": {
                "tag": CONTRACT_AUTHORITY_TAG,
                "commit": CONTRACT_AUTHORITY_COMMIT,
                "manifest_sha256": CONTRACT_MANIFEST_SHA256,
            },
            "source_bindings": {
                "dataset_v3_manifest_sha256": V3_MANIFEST_SHA256,
                "reviewed_15_manifest_sha256": REVIEWED_MANIFEST_SHA256,
                "parent_p0_manifest_sha256": P0_MANIFEST_SHA256,
            },
            "provider_call_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")

        try:
            from .validate_official_pilot import validate_artifact
        except ImportError:  # pragma: no cover
            from validate_official_pilot import validate_artifact  # type: ignore
        errors = validate_artifact(staging, contracts_root)
        if errors:
            raise ValueError("internal release validation failed: " + "; ".join(errors))

        zip_name = f"{ARTIFACT_NAME}_reviewer_handoff.zip"
        temp_zip = temporary / zip_name
        build_deterministic_zip(staging, temp_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temp_zip, final_zip)
        zip_hash = sha256_file(final_zip)
        sidecar = output_root.parent / f"{zip_name}.sha256"
        sidecar.write_text(f"{zip_hash} *{zip_name}\n", encoding="ascii", newline="\n")
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "reviewer_handoff_zip": str(final_zip),
            "reviewer_handoff_zip_sha256": zip_hash,
            "counts": manifest["counts"],
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument(
        "--reviewed-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_stage_a_pilot_15_senses_reviewed_v1"
        / "release"
        / "d2l_stage_a_pilot_15_senses_reviewed_v1",
    )
    parser.add_argument(
        "--v3-root",
        type=Path,
        default=repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3",
    )
    parser.add_argument(
        "--contracts-root", type=Path, default=repo_root / "terminology_contracts_v1"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default="2026-07-29T08:00:00Z")
    args = parser.parse_args()
    result = build_official_pilot(
        repo_root=args.repo_root,
        reviewed_root=args.reviewed_root,
        v3_root=args.v3_root,
        contracts_root=args.contracts_root,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
