from __future__ import annotations

import argparse
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
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    write_checksums,
    write_json,
    write_jsonl,
)


ARTIFACT_NAME = "d2l_switch_replacement_hypothesis_testing_v1"
POLICY_ID = "d2l-switch-replacement-stage-a-v1.0"
CREATED_AT = "2026-07-30T00:00:00Z"
BASE_AUTHORITY_COMMIT = "0603573c8934fe457398554d33411d84709473f1"
REPLACED_TERM = "switch"
REPLACED_SENSE_ID = "d2lce_91002293cea2184b43995f47"
REPLACEMENT_TERM = "hypothesis testing"
REPLACEMENT_SENSE_ID = "d2lce_bad32719ece6439b4716d093"
SOURCE_MEMBER_IDS = {
    "cand_51bbb94487ca4ade2afc23f3",
    "cand_a13c1b81ada76bcdd1bc666c",
    "cand_c2bca10f77520f4e129d3f3a",
}
PRIMARY_BLOCKS = [
    "d2l_appendix_mathematics_for_deep_learning_statistics_b055",
    "d2l_appendix_mathematics_for_deep_learning_statistics_b056",
    "d2l_appendix_mathematics_for_deep_learning_statistics_b080",
    "d2l_appendix_mathematics_for_deep_learning_statistics_b082",
    "d2l_appendix_mathematics_for_deep_learning_statistics_b114",
]
BACKUP_BLOCKS = [
    "d2l_appendix_mathematics_for_deep_learning_index_b009",
    "d2l_appendix_mathematics_for_deep_learning_statistics_b069",
]
CANDIDATE_TARGETS = [
    ("kiểm định giả thuyết", "SEALED_D2L_GLOSSARY_TARGET"),
    ("kiểm tra giả thuyết", "PRODUCER_CANDIDATE_VARIANT"),
    ("phép thử giả thuyết", "PRODUCER_CANDIDATE_VARIANT"),
]


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_manifest(root: Path) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError(f"{root.name}: manifest self-hash mismatch")
    actual = build_file_inventory(root, {"CHECKSUMS.sha256", "manifest.json"})
    expected = manifest.get("files")
    if not isinstance(expected, dict) or set(expected) != set(actual):
        raise ValueError(f"{root.name}: manifest inventory mismatch")
    for relative_path, actual_record in actual.items():
        expected_record = expected.get(relative_path)
        if (
            not isinstance(expected_record, dict)
            or expected_record.get("sha256") != actual_record.get("sha256")
        ):
            raise ValueError(
                f"{root.name}: manifest hash mismatch for {relative_path}"
            )
    return manifest


def _candidate_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for target, origin in CANDIDATE_TARGETS:
        candidate_id = "candidate_" + sha256_bytes(
            f"{REPLACEMENT_SENSE_ID}|{target}".encode("utf-8")
        )[:24]
        slot = "candidate_slot_" + sha256_bytes(
            f"{candidate_id}|slot".encode("utf-8")
        )[:24]
        record = {
            "candidate_id": candidate_id,
            "candidate_slot": slot,
            "candidate_target_vi": target,
        }
        record["candidate_instance_sha256"] = sha256_bytes(
            canonical_json_bytes(record)
        )
        candidates.append(record)
        provenance.append(
            {
                "candidate_id": candidate_id,
                "candidate_instance_sha256": record["candidate_instance_sha256"],
                "candidate_origin": origin,
                "candidate_slot": slot,
                "policy_id": POLICY_ID,
                "schema_id": "D2LSwitchReplacementCandidateProvenanceV1",
                "schema_version": "1.0",
                "sense_id": REPLACEMENT_SENSE_ID,
            }
        )
    return sorted(candidates, key=lambda row: row["candidate_id"]), sorted(
        provenance, key=lambda row: row["candidate_id"]
    )


def _matched_surface(text: str) -> tuple[str, int, int]:
    surfaces = ["hypothesis testing", "hypothesis test", "hypothesis tests"]
    folded = text.casefold()
    for surface in surfaces:
        start = folded.find(surface)
        if start >= 0:
            return text[start : start + len(surface)], start, start + len(surface)
    raise ValueError("replacement context does not contain a source surface")


def _context_records(
    block_map: Mapping[str, str], source_sha256: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    contexts: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    selected = [(block_id, "PRIMARY") for block_id in PRIMARY_BLOCKS] + [
        (block_id, "BACKUP") for block_id in BACKUP_BLOCKS
    ]
    for index, (block_id, role) in enumerate(selected, 1):
        text = block_map[block_id]
        surface, start, end = _matched_surface(text)
        context_id = "ctxr_" + sha256_bytes(
            canonical_json_bytes({"block_id": block_id, "text": text})
        )[:24]
        record = {
            "block_id": block_id,
            "boundary_only": False,
            "content_sha256": sha256_bytes(text.encode("utf-8")),
            "context_id": context_id,
            "context_role": role,
            "context_slot": f"C{index}",
            "matched_surface": surface,
            "positive_evidence_eligible": True,
            "sense_relation": "SAME_SENSE",
            "source_match_end_local": end,
            "source_match_start_local": start,
            "source_text": text,
            "synthetic": False,
        }
        record["context_sha256"] = sha256_bytes(canonical_json_bytes(record))
        contexts.append(record)
        provenance.append(
            {
                "block_id": block_id,
                "block_text_sha256": record["content_sha256"],
                "context_id": context_id,
                "context_sha256": record["context_sha256"],
                "policy_id": POLICY_ID,
                "schema_id": "D2LSwitchReplacementContextProvenanceV1",
                "schema_version": "1.0",
                "source_artifact_file_name": "decisions.json",
                "source_artifact_sha256": source_sha256,
            }
        )
    return contexts, provenance


def _blank_review() -> dict[str, Any]:
    return {
        "candidate_replacements": [],
        "candidate_set_decision": "",
        "corrected_definition_en": "",
        "corrected_part_of_speech": "",
        "corrected_scope": "",
        "definition_decision": "",
        "evidence_decision": "",
        "invalid_evidence_context_ids": [],
        "part_of_speech_decision": "",
        "proposed_split_labels": [],
        "review_notes": "",
        "review_status": "",
        "scope_decision": "",
        "sense_status": "",
    }


def _review_input(source_payload: Mapping[str, Any], reviewer_role: str) -> dict[str, Any]:
    source_sha = sha256_bytes(canonical_json_bytes(source_payload))
    batch_id = f"switch_replacement_{reviewer_role}"
    case = {
        "batch_id": batch_id,
        "case_id": "replacement_" + sha256_bytes(
            f"{REPLACED_SENSE_ID}|{REPLACEMENT_SENSE_ID}".encode("utf-8")
        )[:24],
        "final_glossary_decision": None,
        "policy_id": POLICY_ID,
        "provider_call_count": 0,
        "review": _blank_review(),
        "reviewer_slot": reviewer_role,
        "schema_id": "D2LSwitchReplacementStageAReviewCaseV1",
        "schema_version": "1.0",
        "source_payload": source_payload,
        "source_payload_sha256": source_sha,
        "stage_b_gold_label": None,
    }
    return {
        "allowed_sense_status": [
            "READY_FOR_CONTRACT_CONSTRUCTION",
            "REVISION_REQUIRED",
            "SPLIT_REQUIRED",
            "UNRESOLVED",
        ],
        "allowed_standard_decisions": ["ACCEPT", "REVISE", "UNJUDGEABLE"],
        "batch_id": batch_id,
        "case_count": 1,
        "cases": [case],
        "dataset_version": ARTIFACT_NAME,
        "final_glossary_decision": None,
        "independence_requirement": "DO_NOT_VIEW_OTHER_REVIEWER_OUTPUT",
        "policy_id": POLICY_ID,
        "provider_call_count": 0,
        "return_contract": f"Return {batch_id}.json only.",
        "reviewer_slot": reviewer_role,
        "schema_id": "D2LSwitchReplacementStageAReviewBatchV1",
        "schema_version": "1.0",
        "sense_count": 1,
        "source_input_sha256": source_sha,
        "stage_b_gold_autofill_count": 0,
    }


def _copy_source_bundle(staging: Path) -> None:
    source_root = staging / "source"
    module_root = Path(__file__).resolve().parent
    project_root = module_root.parent
    for name in ("build_switch_replacement.py", "validate_switch_replacement.py"):
        destination = source_root / "tools" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module_root / name, destination)
    destination = source_root / "tests" / "test_switch_replacement.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project_root / "tests" / "test_switch_replacement.py", destination)


def build_switch_replacement(
    *,
    v3_root: Path,
    final_closure_root: Path,
    glossary_json: Path,
    b2_decisions_json: Path,
    output_root: Path,
    zip_path: Path,
) -> dict[str, Any]:
    v3_root = v3_root.resolve(strict=True)
    final_closure_root = final_closure_root.resolve(strict=True)
    glossary_json = glossary_json.resolve(strict=True)
    b2_decisions_json = b2_decisions_json.resolve(strict=True)
    output_root = output_root.resolve()
    zip_path = zip_path.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    v3_manifest = _verify_manifest(v3_root)
    closure_manifest = _verify_manifest(final_closure_root)
    current_terms = sorted(
        {
            str(row["source_term"]).casefold().strip()
            for row in strict_jsonl(v3_root / "term_senses.jsonl")
        }
    )
    if len(current_terms) != 150 or REPLACEMENT_TERM in current_terms:
        raise ValueError("replacement term inventory is not eligible")
    if REPLACED_TERM not in current_terms:
        raise ValueError("replaced switch slot is missing from the current inventory")
    closure = strict_jsonl(final_closure_root / "closure_index_100.jsonl")
    switch = [row for row in closure if row["sense_id"] == REPLACED_SENSE_ID]
    if len(switch) != 1 or switch[0]["stage_a_status"] != "BLOCKED":
        raise ValueError("switch is not the exact blocked closure slot")

    glossary = strict_json_object(glossary_json)
    glossary_rows = [
        row
        for row in glossary.get("records", [])
        if row.get("record_id") == REPLACEMENT_SENSE_ID
    ]
    if len(glossary_rows) != 1:
        raise ValueError("sealed replacement glossary record is missing")
    glossary_record = glossary_rows[0]
    value = glossary_record["value"]
    if (
        value.get("canonical_source") != REPLACEMENT_TERM
        or value.get("canonical_target_vi") != "kiểm định giả thuyết"
        or value.get("status") != "ready_draft"
        or value.get("evidence_complete") is not True
        or set(value.get("source_member_candidate_ids", [])) != SOURCE_MEMBER_IDS
    ):
        raise ValueError("sealed replacement glossary record is not eligible")

    b2 = strict_json_object(b2_decisions_json)
    consolidation = b2.get("consolidation_index")
    if not isinstance(consolidation, Mapping):
        raise ValueError("B2 consolidation index is missing")
    block_map = {
        row["block_id"]: row["text"] for row in consolidation["source_blocks"]
    }
    evidence_ids = set(value["evidence_block_ids"])
    if evidence_ids != set(PRIMARY_BLOCKS + BACKUP_BLOCKS + [
        "d2l_appendix_mathematics_for_deep_learning_statistics_b048",
        "d2l_appendix_mathematics_for_deep_learning_statistics_b079",
    ]):
        raise ValueError("replacement evidence block set drifted")
    if not evidence_ids <= set(block_map):
        raise ValueError("replacement evidence text is incomplete")
    source_decisions = [
        row
        for row in consolidation["decisions"]
        if row.get("candidate_id") in SOURCE_MEMBER_IDS
    ]
    if len(source_decisions) != 3 or any(
        row.get("decision") != "admit" or row.get("evidence_complete") is not True
        for row in source_decisions
    ):
        raise ValueError("replacement B2 admission binding is incomplete")

    candidates, candidate_provenance = _candidate_records()
    contexts, context_provenance = _context_records(
        block_map, sha256_file(b2_decisions_json)
    )
    source_payload = {
        "candidates": candidates,
        "dataset_version": ARTIFACT_NAME,
        "evidence_contexts": contexts,
        "parent_binding": {
            "closure_manifest_sha256": closure_manifest["manifest_sha256"],
            "glossary_record_hash": glossary_record["record_hash"],
            "replacement_source_member_candidate_ids": sorted(SOURCE_MEMBER_IDS),
            "replaced_closure_record_sha256": switch[0]["record_sha256"],
            "v3_manifest_sha256": v3_manifest["manifest_sha256"],
        },
        "policy_id": POLICY_ID,
        "proposed_definition_en": "A statistical procedure and reasoning framework for evaluating evidence against a null hypothesis using a test statistic and a rejection rule.",
        "proposed_part_of_speech": "noun_phrase",
        "proposed_scope": "D2L statistics appendix; statistical hypothesis-testing procedure, excluding the natural-language-inference sense of hypothesis.",
        "provider_call_count": 0,
        "review_requirement": "TWO_INDEPENDENT_STAGE_A_REVIEWS",
        "risk_class": "R0_CLEAR",
        "schema_id": "D2LSwitchReplacementStageASourceV1",
        "schema_version": "1.0",
        "sense_id": REPLACEMENT_SENSE_ID,
        "source_review_status": {
            "definition": "PENDING_INDEPENDENT_REVIEW",
            "evidence": "CORPUS_BOUND_PENDING_INDEPENDENT_REVIEW",
            "part_of_speech": "PENDING_INDEPENDENT_REVIEW",
        },
        "source_term": REPLACEMENT_TERM,
        "stratum": "clear",
        "term_id": REPLACEMENT_SENSE_ID,
    }
    reviewer_inputs = {
        role: _review_input(source_payload, role)
        for role in ("reviewer_1", "reviewer_2")
    }

    with tempfile.TemporaryDirectory(
        prefix="switch-replacement-", dir=output_root.parent
    ) as name:
        staging = Path(name) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        write_json(
            staging / "source_evidence.json",
            seal_integrity(
                {
                    "b2_decisions_file_name": b2_decisions_json.name,
                    "b2_decisions_sha256": sha256_file(b2_decisions_json),
                    "evidence_blocks": [
                        {"block_id": block_id, "text": block_map[block_id]}
                        for block_id in sorted(evidence_ids)
                    ],
                    "glossary_file_name": glossary_json.name,
                    "glossary_record": glossary_record,
                    "glossary_sha256": sha256_file(glossary_json),
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LSwitchReplacementSourceEvidenceV1",
                    "schema_version": "1.0",
                    "source_decisions": sorted(
                        source_decisions, key=lambda row: row["candidate_id"]
                    ),
                }
            ),
        )
        write_json(
            staging / "current_source_term_inventory_150.json",
            seal_integrity(
                {
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LCurrentSourceTermInventory150V1",
                    "schema_version": "1.0",
                    "source_term_count": len(current_terms),
                    "source_terms_casefolded": current_terms,
                    "v3_manifest_sha256": v3_manifest["manifest_sha256"],
                }
            ),
        )
        write_json(staging / "replacement_source.json", seal_integrity(source_payload))
        write_jsonl(staging / "candidate_provenance_3.jsonl", candidate_provenance)
        write_jsonl(staging / "context_provenance_7.jsonl", context_provenance)
        write_json(
            staging / "replacement_selection.json",
            seal_integrity(
                {
                    "final_glossary_decision": None,
                    "policy_id": POLICY_ID,
                    "provider_call_count": 0,
                    "replacement_sense_id": REPLACEMENT_SENSE_ID,
                    "replacement_source_term": REPLACEMENT_TERM,
                    "replacement_status": "SELECTED_PENDING_TWO_INDEPENDENT_REVIEWS",
                    "replaced_sense_id": REPLACED_SENSE_ID,
                    "replaced_source_term": REPLACED_TERM,
                    "schema_id": "D2LSwitchReplacementSelectionV1",
                    "schema_version": "1.0",
                    "stage_b_gold_autofill_count": 0,
                    "stage_b_gold_label": None,
                }
            ),
        )
        handoff = staging / "handoff"
        for role, payload in reviewer_inputs.items():
            batch = staging / "review_batches" / role
            write_json(batch / "reviewer_input.json", payload)
            (batch / "INSTRUCTIONS.md").write_bytes(
                (
                    "# Independent Stage A replacement review\n\n"
                    "Review the single hypothesis-testing sense from the supplied D2L corpus contexts. Edit only the review object. Do not view another reviewer output. Return the completed JSON file only.\n"
                ).encode("utf-8")
            )
            build_deterministic_zip(batch, handoff / f"switch_replacement_{role}.zip")
            (handoff / f"{role.upper()}_MESSAGE.md").write_bytes(
                (
                    f"Review the one replacement sense in switch_replacement_{role}.zip independently. Follow INSTRUCTIONS.md, edit only review, and return switch_replacement_{role}.json only.\n"
                ).encode("utf-8")
            )
        write_json(
            staging / "authority.json",
            seal_integrity(
                {
                    "base_authority_commit": BASE_AUTHORITY_COMMIT,
                    "closure_manifest_physical_sha256": sha256_file(
                        final_closure_root / "manifest.json"
                    ),
                    "closure_manifest_self_sha256": closure_manifest[
                        "manifest_sha256"
                    ],
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LSwitchReplacementAuthorityV1",
                    "schema_version": "1.0",
                    "v3_manifest_physical_sha256": sha256_file(
                        v3_root / "manifest.json"
                    ),
                    "v3_manifest_self_sha256": v3_manifest["manifest_sha256"],
                }
            ),
        )
        write_json(
            staging / "validation_report.json",
            seal_integrity(
                {
                    "candidate_count": 3,
                    "context_count": 7,
                    "final_glossary_decision": None,
                    "nonduplicate_against_current_150": True,
                    "policy_id": POLICY_ID,
                    "primary_context_count": 5,
                    "provider_call_count": 0,
                    "reviewer_pack_count": 2,
                    "schema_id": "D2LSwitchReplacementValidationReportV1",
                    "schema_version": "1.0",
                    "stage_b_gold_autofill_count": 0,
                    "status": "REPLACEMENT_SELECTED_PENDING_TWO_INDEPENDENT_REVIEWS_ZERO_PROVIDER",
                    "synthetic_context_count": 0,
                }
            ),
        )
        (staging / "RELEASE_REPORT.md").write_bytes(
            (
                "# D2L switch replacement selection\n\n"
                "- Replaced blocked slot: `switch`.\n"
                "- Selected replacement: `hypothesis testing`.\n"
                "- Candidate instances: 3.\n"
                "- Real D2L contexts supplied to reviewers: 7 (5 primary, 2 backup).\n"
                "- Synthetic contexts: 0.\n"
                "- Required: two independent Stage A reviews.\n"
                "- Provider calls: 0.\n"
                "- Stage B gold autofill: 0.\n"
                "- Final glossary decision: null.\n"
            ).encode("utf-8")
        )
        _copy_source_bundle(staging)
        files = build_file_inventory(
            staging, excluded={"CHECKSUMS.sha256", "manifest.json"}
        )
        manifest = {
            "artifact_name": ARTIFACT_NAME,
            "base_authority_commit": BASE_AUTHORITY_COMMIT,
            "created_at": CREATED_AT,
            "file_count": len(files),
            "files": files,
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "schema_id": "D2LSwitchReplacementManifestV1",
            "schema_version": "1.0",
            "status": "REPLACEMENT_SELECTED_PENDING_TWO_INDEPENDENT_REVIEWS_ZERO_PROVIDER",
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from .validate_switch_replacement import validate_artifact

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
        "status": "REPLACEMENT_SELECTED_PENDING_TWO_INDEPENDENT_REVIEWS_ZERO_PROVIDER",
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v3-root", type=Path, required=True)
    parser.add_argument("--final-closure-root", type=Path, required=True)
    parser.add_argument("--glossary-json", type=Path, required=True)
    parser.add_argument("--b2-decisions-json", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path, required=True)
    args = parser.parse_args()
    result = build_switch_replacement(
        v3_root=args.v3_root,
        final_closure_root=args.final_closure_root,
        glossary_json=args.glossary_json,
        b2_decisions_json=args.b2_decisions_json,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
