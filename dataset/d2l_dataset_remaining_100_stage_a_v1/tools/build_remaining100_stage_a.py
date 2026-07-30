from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
COMMON_TOOLS = (
    REPO_ROOT
    / "dataset"
    / "d2l_dataset_50_senses_fast_track_stage_a_v1"
    / "tools"
)
if str(COMMON_TOOLS) not in sys.path:
    sys.path.insert(0, str(COMMON_TOOLS))

from common import (  # type: ignore  # noqa: E402
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    replace_directory,
    sha256_bytes,
    sha256_file,
    strict_json_file,
    strict_jsonl,
    write_checksums,
    write_json,
    write_jsonl,
)


ARTIFACT_NAME = "d2l_dataset_remaining_100_stage_a_v1"
POLICY_ID = "d2l-dataset-remaining-100-stage-a-v1.0"
STATUS = "READY_FOR_STAGE_A_RISK_REVIEW"
DATASET_VERSION = "d2l_dataset_remaining_100_stage_a_v1"
SPLIT_POLICY_ID = "d2l_sentence_disjoint_stratified_100_25_25_v1"
V3_ARTIFACT_NAME = "d2l_context_support_set_validation_ready_v3"
REVIEW_SCHEMA_ID = "D2LRemaining100StageAReviewSourceV1"
REVIEW_INPUT_SCHEMA_ID = "D2LRemaining100StageAReviewerInputV1"
RISK_BY_STRATUM = {
    "clear": "R0_CLEAR",
    "ambiguous": "R3_AMBIGUOUS",
    "collision_or_multi_target": "R4_SPLIT_OR_POS_RISK",
}
REVIEW_REQUIREMENT_BY_RISK = {
    "R0_CLEAR": "SOURCE_GROUND_PLUS_BLIND_AUDIT",
    "R3_AMBIGUOUS": "TWO_DISTINCT_BLIND_REVIEWERS",
    "R4_SPLIT_OR_POS_RISK": "TWO_DISTINCT_REVIEWERS_PLUS_MANDATORY_ADJUDICATION",
}
REVIEW_FIELDS = (
    "definition_decision",
    "corrected_definition_en",
    "part_of_speech_decision",
    "corrected_part_of_speech",
    "scope_decision",
    "corrected_scope",
    "evidence_decision",
    "invalid_evidence_context_ids",
    "candidate_set_decision",
    "candidate_replacements",
    "sense_status",
    "proposed_split_labels",
    "review_notes",
    "review_status",
)
ALLOWED_STANDARD_DECISIONS = ("ACCEPT", "REVISE", "UNJUDGEABLE")
ALLOWED_SENSE_STATUS = (
    "READY_FOR_CONTRACT_CONSTRUCTION",
    "REVISION_REQUIRED",
    "SPLIT_REQUIRED",
    "UNRESOLVED",
    "QUARANTINED",
)

# The 50-sense release contains the two repaired ``in place`` senses.  The
# original V3 parent is therefore not a second review target.  Statistical
# power remains the explicitly unresolved C-repair parent and is held out of
# this 100-sense package rather than silently pretending it is ready.
EXCLUDED_PARENT_IDS = {
    "d2lce_2684090fd4500122fec2a334",  # original unsplit in place parent
    "d2lce_2b76c0f26436945cdf880aed",  # statistical power, unresolved repair
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _blank_review() -> dict[str, Any]:
    result: dict[str, Any] = {field: "" for field in REVIEW_FIELDS}
    result["invalid_evidence_context_ids"] = []
    result["candidate_replacements"] = []
    result["proposed_split_labels"] = []
    return result


def _verify_parent_hash(row: Mapping[str, Any], field: str) -> bool:
    claimed = row.get(field)
    if not isinstance(claimed, str):
        return False
    payload = dict(row)
    payload.pop(field, None)
    return claimed == sha256_bytes(canonical_json_bytes(payload))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return strict_jsonl(path)


def _load_parent(
    v3_root: Path,
    selected50_root: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    set[str],
]:
    manifest = strict_json_file(v3_root / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("dataset_version") != V3_ARTIFACT_NAME:
        raise ValueError("unexpected V3 parent manifest")
    if _manifest_self_hash(manifest) != manifest.get("manifest_sha256"):
        raise ValueError("V3 parent manifest self hash mismatch")
    terms = _load_jsonl(v3_root / "term_senses.jsonl")
    candidates = _load_jsonl(v3_root / "candidate_instances.jsonl")
    contexts = _load_jsonl(v3_root / "contexts.jsonl")
    selected50 = _load_jsonl(selected50_root / "term_senses_50.jsonl")
    selected50_ids = {str(row.get("sense_id")) for row in selected50}
    if len(terms) != 150 or len(candidates) != 450:
        raise ValueError("V3 parent cardinality mismatch")
    if len(selected50_ids) != 50:
        raise ValueError("50-sense authority selection is not exactly 50 senses")
    term_ids = {str(row.get("sense_id")) for row in terms}
    if any(not _verify_parent_hash(row, "term_sense_sha256") for row in terms):
        raise ValueError("V3 term-sense parent hash mismatch")
    if any(not _verify_parent_hash(row, "candidate_instance_sha256") for row in candidates):
        raise ValueError("V3 candidate parent hash mismatch")
    if any(not _verify_parent_hash(row, "context_sha256") for row in contexts):
        raise ValueError("V3 context parent hash mismatch")
    candidate_senses = Counter(str(row.get("sense_id")) for row in candidates)
    if set(candidate_senses) != term_ids or any(value != 3 for value in candidate_senses.values()):
        raise ValueError("V3 candidate closure mismatch")
    return manifest, terms, candidates, contexts, selected50_ids


def _eligible_context(row: Mapping[str, Any]) -> bool:
    role = row.get("context_role")
    relation = row.get("sense_relation")
    return role in {"PRIMARY", "BACKUP", "CONTRASTIVE"} and relation in {
        "SAME_SENSE",
        "CONTRASTIVE",
    }


def _context_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    synthetic = bool(row.get("synthetic")) or row.get("binding_kind") == "SYNTHETIC_BOUNDARY_PROBE"
    return {
        "context_id": row["context_id"],
        "context_role": row.get("context_role"),
        "context_slot": row.get("context_slot"),
        "sense_relation": row.get("sense_relation"),
        "synthetic": synthetic,
        "boundary_only": bool(synthetic or row.get("sense_relation") != "SAME_SENSE"),
        "source_text": row.get("source_text"),
        "matched_surface": row.get("matched_surface"),
        "content_sha256": row.get("content_sha256"),
        "context_sha256": row.get("context_sha256"),
        "context_type": row.get("context_type"),
        "context_type_review_status": row.get("context_type_review_status"),
        "chapter_id": row.get("chapter_id"),
        "block_id": row.get("block_id"),
        "sentence_id": row.get("sentence_id"),
        "provenance": copy.deepcopy(row.get("provenance", {})),
        "source_artifact_sha256": row.get("source_artifact_sha256"),
        "source_match_start_absolute": row.get("source_match_start_absolute"),
        "source_match_end_absolute": row.get("source_match_end_absolute"),
    }


def _source_payload(
    sense: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    parent_manifest_sha256: str,
) -> dict[str, Any]:
    sense_id = str(sense["sense_id"])
    stratum = str(sense.get("stratum"))
    risk = RISK_BY_STRATUM.get(stratum)
    if risk is None:
        raise ValueError(f"unsupported stratum: {stratum}")
    return {
        "schema_id": REVIEW_SCHEMA_ID,
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "dataset_version": DATASET_VERSION,
        "sense_id": sense_id,
        "term_id": sense["term_id"],
        "source_term": sense["source_term"],
        "stratum": stratum,
        "risk_class": risk,
        "review_requirement": REVIEW_REQUIREMENT_BY_RISK[risk],
        "proposed_definition_en": sense["definition"],
        "proposed_part_of_speech": sense["part_of_speech"],
        "proposed_scope": sense["scope_id"],
        "candidates": [
            {
                "candidate_id": row["candidate_instance_id"],
                "candidate_slot": row["candidate_slot_id"],
                "candidate_target_vi": row["candidate_target_vi"],
                "candidate_instance_sha256": row["candidate_instance_sha256"],
            }
            for row in sorted(candidates, key=lambda item: str(item["candidate_instance_id"]))
        ],
        "evidence_contexts": [
            _context_projection(row)
            for row in sorted(contexts, key=lambda item: str(item["context_id"]))
        ],
        "parent_binding": {
            "parent_dataset": V3_ARTIFACT_NAME,
            "parent_manifest_sha256": parent_manifest_sha256,
            "parent_term_sense_sha256": sense["term_sense_sha256"],
            "parent_candidate_instance_sha256": [
                row["candidate_instance_sha256"]
                for row in sorted(candidates, key=lambda item: str(item["candidate_instance_id"]))
            ],
            "parent_context_sha256": [
                row["context_sha256"]
                for row in sorted(contexts, key=lambda item: str(item["context_id"]))
            ],
        },
        "source_review_status": {
            "definition": sense.get("definition_review_status"),
            "part_of_speech": sense.get("part_of_speech_status"),
            "contrastive": sense.get("contrastive_review_status"),
        },
        "provider_call_count": 0,
    }


def _case(source_payload: Mapping[str, Any], batch_id: str, reviewer_slot: str) -> dict[str, Any]:
    source_hash = sha256_bytes(canonical_json_bytes(source_payload))
    case_id = "remaining100_" + sha256_bytes(
        f"{batch_id}\x1f{source_payload['sense_id']}\x1f{reviewer_slot}".encode("utf-8")
    )[:24]
    return {
        "schema_id": "D2LRemaining100StageAReviewCaseV1",
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "case_id": case_id,
        "batch_id": batch_id,
        "reviewer_slot": reviewer_slot,
        "source_payload": copy.deepcopy(dict(source_payload)),
        "source_payload_sha256": source_hash,
        "review": _blank_review(),
        "provider_call_count": 0,
        "stage_b_gold_label": None,
        "final_glossary_decision": None,
    }


def _review_input(
    batch_id: str,
    reviewer_slot: str,
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_input = [
        {"case_id": row["case_id"], "source_payload_sha256": row["source_payload_sha256"]}
        for row in cases
    ]
    return {
        "schema_id": REVIEW_INPUT_SCHEMA_ID,
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "dataset_version": DATASET_VERSION,
        "batch_id": batch_id,
        "reviewer_slot": reviewer_slot,
        "case_count": len(cases),
        "sense_count": len(cases),
        "independence_requirement": "DO_NOT_VIEW_OTHER_REVIEWER_OUTPUTS",
        "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_FIELDS_FILLED",
        "allowed_standard_decisions": list(ALLOWED_STANDARD_DECISIONS),
        "allowed_sense_status": list(ALLOWED_SENSE_STATUS),
        "cases": [copy.deepcopy(dict(row)) for row in cases],
        "source_input_sha256": sha256_bytes(canonical_json_bytes(source_input)),
        "provider_call_count": 0,
        "stage_b_gold_autofill_count": 0,
        "final_glossary_decision": None,
    }


def _instructions(reviewer_slot: str) -> str:
    return (
        "# D2L remaining-100 Stage A review\n\n"
        f"You are {reviewer_slot}. Review only the supplied cases and work independently.\n\n"
        "Evaluate the proposed English sense definition, part of speech, scope, candidate set, "
        "and source-grounded evidence. Use only the supplied D2L contexts. A synthetic or "
        "boundary context is not positive evidence. Fill only the `review` object; preserve "
        "all source fields, IDs, text, and hashes. Set review_status=COMPLETE and provide a "
        "nonblank review_notes value. Do not assign Stage B gold, C/E results, or a final "
        "glossary decision. Do not inspect another reviewer's output.\n\n"
        "Allowed decisions: ACCEPT, REVISE, UNJUDGEABLE. Allowed sense statuses: "
        "READY_FOR_CONTRACT_CONSTRUCTION, REVISION_REQUIRED, SPLIT_REQUIRED, UNRESOLVED, "
        "QUARANTINED. Return the same JSON structure with only review fields completed.\n"
    )


def _write_handoff(
    staging: Path,
    batch_id: str,
    reviewer_slot: str,
    payload: Mapping[str, Any],
) -> tuple[str, str]:
    temp = staging / ".handoff" / f"{batch_id}_{reviewer_slot}"
    temp.mkdir(parents=True, exist_ok=True)
    write_json(temp / "review_input.json", payload)
    (temp / "REVIEW_INSTRUCTIONS.md").write_text(
        _instructions(reviewer_slot), encoding="utf-8", newline="\n"
    )
    (temp / "MESSAGE.md").write_text(
        f"Review {batch_id} as {reviewer_slot}. Return only the completed review_input.json.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_checksums(temp, temp / "CHECKSUMS.sha256")
    zip_path = staging / "handoff" / f"{batch_id}_{reviewer_slot}.zip"
    build_deterministic_zip(temp, zip_path)
    return zip_path.relative_to(staging).as_posix(), sha256_file(zip_path)


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        "README.md",
        "tools/__init__.py",
        "tools/build_remaining100_stage_a.py",
        "tools/validate_remaining100_stage_a.py",
        "tests/test_remaining100_stage_a.py",
    ):
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"missing source bundle file: {relative}")
        target = staging / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def build_remaining100_stage_a(
    *,
    v3_root: Path,
    selected50_root: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    v3_root = v3_root.resolve(strict=True)
    selected50_root = selected50_root.resolve(strict=True)
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    manifest, all_terms, all_candidates, all_contexts, selected50_ids = _load_parent(
        v3_root, selected50_root
    )
    term_by_id = {str(row["sense_id"]): row for row in all_terms}
    target_ids = set(term_by_id) - selected50_ids - EXCLUDED_PARENT_IDS
    if len(target_ids) != 100:
        raise ValueError(f"remaining target count is {len(target_ids)}, expected 100")
    senses = [term_by_id[sense_id] for sense_id in sorted(target_ids)]
    candidates_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_candidates:
        if str(row["sense_id"]) in target_ids:
            candidates_by_sense[str(row["sense_id"])].append(row)
    context_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_contexts:
        sense_id = str(row.get("sense_id"))
        if sense_id in target_ids and _eligible_context(row):
            context_by_sense[sense_id].append(row)
    if any(len(candidates_by_sense[sense_id]) != 3 for sense_id in target_ids):
        raise ValueError("remaining candidate closure is not exactly three per sense")
    if any(not context_by_sense[sense_id] for sense_id in target_ids):
        raise ValueError("remaining sense has no eligible review context")

    payload_by_id = {
        sense_id: _source_payload(
            term_by_id[sense_id],
            candidates_by_sense[sense_id],
            context_by_sense[sense_id],
            str(manifest["manifest_sha256"]),
        )
        for sense_id in sorted(target_ids)
    }
    # Interleave risk classes so every upload batch has a useful Reviewer 2
    # payload instead of producing empty handoffs for the clear prefix.
    risk_order = {"R0_CLEAR": 0, "R3_AMBIGUOUS": 1, "R4_SPLIT_OR_POS_RISK": 2}
    queues = {
        risk: sorted(
            (row for row in senses if RISK_BY_STRATUM[str(row["stratum"])] == risk),
            key=lambda row: (str(row["source_term"]).casefold(), str(row["sense_id"])),
        )
        for risk in risk_order
    }
    ordered_senses: list[dict[str, Any]] = []
    while any(queues.values()):
        for risk in sorted(risk_order, key=risk_order.get):
            if queues[risk]:
                ordered_senses.append(queues[risk].pop(0))
    batch_groups = [ordered_senses[index : index + 10] for index in range(0, 100, 10)]
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        write_jsonl(staging / "term_senses_100.jsonl", senses)
        write_jsonl(
            staging / "candidate_instances_300.jsonl",
            [row for sense_id in sorted(target_ids) for row in sorted(candidates_by_sense[sense_id], key=lambda item: item["candidate_instance_id"])],
        )
        selected_contexts = [
            row
            for sense_id in sorted(target_ids)
            for row in sorted(context_by_sense[sense_id], key=lambda item: item["context_id"])
        ]
        write_jsonl(staging / "contexts_selected_100.jsonl", selected_contexts)
        write_jsonl(
            staging / "parent_snapshot_term_senses.jsonl",
            [term_by_id[sense_id] for sense_id in sorted(target_ids)],
        )
        write_jsonl(
            staging / "parent_snapshot_candidates.jsonl",
            [row for sense_id in sorted(target_ids) for row in sorted(candidates_by_sense[sense_id], key=lambda item: item["candidate_instance_id"])],
        )
        write_jsonl(staging / "parent_snapshot_contexts.jsonl", selected_contexts)
        write_json(
            staging / "parent_binding.json",
            {
                "schema_id": "D2LRemaining100ParentBindingV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "parent_artifact": V3_ARTIFACT_NAME,
                "parent_manifest_sha256": manifest["manifest_sha256"],
                "parent_manifest_physical_sha256": sha256_file(v3_root / "manifest.json"),
                "source_term_sense_file_sha256": sha256_file(v3_root / "term_senses.jsonl"),
                "source_candidate_file_sha256": sha256_file(v3_root / "candidate_instances.jsonl"),
                "source_context_file_sha256": sha256_file(v3_root / "contexts.jsonl"),
                "selected_50_sense_ids": sorted(selected50_ids),
                "excluded_parent_ids": sorted(EXCLUDED_PARENT_IDS),
                "remaining_sense_ids": sorted(target_ids),
                "provider_call_count": 0,
            },
        )
        batch_index = []
        all_reviewer_cases: dict[str, list[dict[str, Any]]] = {"reviewer_1": [], "reviewer_2": []}
        handoffs = []
        for sequence, rows in enumerate(batch_groups, start=1):
            batch_id = f"batch_{sequence:03d}"
            batch_dir = staging / "batches" / batch_id
            batch_dir.mkdir(parents=True)
            source_rows = [payload_by_id[str(row["sense_id"])] for row in rows]
            write_json(batch_dir / "review_cases.json", source_rows)
            cases_1 = [_case(payload, batch_id, "reviewer_1") for payload in source_rows]
            cases_2 = [
                _case(payload, batch_id, "reviewer_2")
                for payload in source_rows
                if payload["risk_class"] in {"R3_AMBIGUOUS", "R4_SPLIT_OR_POS_RISK"}
            ]
            input_1 = _review_input(batch_id, "reviewer_1", cases_1)
            input_2 = _review_input(batch_id, "reviewer_2", cases_2)
            write_json(batch_dir / "reviewer_1_input.json", input_1)
            write_json(batch_dir / "reviewer_2_input.json", input_2)
            zip_1, sha_1 = _write_handoff(staging, batch_id, "reviewer_1", input_1)
            zip_2, sha_2 = _write_handoff(staging, batch_id, "reviewer_2", input_2)
            all_reviewer_cases["reviewer_1"].extend(cases_1)
            all_reviewer_cases["reviewer_2"].extend(cases_2)
            risk_counts = Counter(payload["risk_class"] for payload in source_rows)
            batch_index.append(
                {
                    "batch_id": batch_id,
                    "sequence": sequence,
                    "sense_count": len(rows),
                    "reviewer_1_case_count": len(cases_1),
                    "reviewer_2_case_count": len(cases_2),
                    "risk_counts": dict(sorted(risk_counts.items())),
                    "sense_ids": [row["sense_id"] for row in rows],
                    "reviewer_1_handoff_zip": zip_1,
                    "reviewer_1_handoff_zip_sha256": sha_1,
                    "reviewer_2_handoff_zip": zip_2,
                    "reviewer_2_handoff_zip_sha256": sha_2,
                }
            )
        for reviewer_slot, cases in all_reviewer_cases.items():
            payload = _review_input("all_batches", reviewer_slot, cases)
            write_json(staging / f"{reviewer_slot}_full_input.json", payload)
        # The temporary handoff trees are only inputs to ZIP creation. Keeping
        # them in the release would duplicate reviewer bytes and expose an
        # untracked staging namespace.
        shutil.rmtree(staging / ".handoff", ignore_errors=True)
        write_json(staging / "batch_index.json", {
            "schema_id": "D2LRemaining100BatchIndexV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "batch_count": 10,
            "batches": batch_index,
        })
        write_jsonl(
            staging / "stage_a_adjudication_100_template.jsonl",
            [
                {
                    "sense_id": sense_id,
                    "reviewer_1_status": None,
                    "reviewer_2_status": None,
                    "adjudication_required": payload_by_id[sense_id]["risk_class"] == "R4_SPLIT_OR_POS_RISK",
                    "adjudicator_status": None,
                    "adjudication_reason": "",
                    "final_stage_a_status": None,
                }
                for sense_id in sorted(target_ids)
            ],
        )
        gaps = []
        for sense_id in sorted(target_ids):
            rows = context_by_sense[sense_id]
            primary = sum(row.get("context_role") == "PRIMARY" for row in rows)
            backup = sum(row.get("context_role") == "BACKUP" for row in rows)
            contrastive = sum(row.get("context_role") == "CONTRASTIVE" for row in rows)
            if primary < 5 or backup < 1 or contrastive < 1:
                gaps.append({
                    "sense_id": sense_id,
                    "source_term": term_by_id[sense_id]["source_term"],
                    "primary_count": primary,
                    "backup_count": backup,
                    "contrastive_count": contrastive,
                    "gap_codes": [
                        code for code, present in (
                            ("PRIMARY_LT_5", primary < 5),
                            ("BACKUP_MISSING", backup < 1),
                            ("CONTRASTIVE_MISSING", contrastive < 1),
                        ) if present
                    ],
                })
        write_jsonl(staging / "source_gaps.jsonl", gaps)
        write_json(staging / "exclusion_report.json", {
            "schema_id": "D2LRemaining100ExclusionReportV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "parent_count": 150,
            "selected_50_count": 50,
            "remaining_count": 100,
            "excluded_parent_ids": sorted(EXCLUDED_PARENT_IDS),
            "excluded_parent_terms": [term_by_id[sense_id]["source_term"] for sense_id in sorted(EXCLUDED_PARENT_IDS)],
            "exclusion_reasons": {
                "d2lce_2684090fd4500122fec2a334": "SUPERSEDED_BY_TWO_REPAIRED_IN_PLACE_SENSES_IN_50_RELEASE",
                "d2lce_2b76c0f26436945cdf880aed": "UNRESOLVED_STAGE_A_REPAIR_PARENT_HELD_OUT",
            },
            "selected_50_ids_sha256": sha256_bytes(canonical_json_bytes(sorted(selected50_ids))),
            "provider_call_count": 0,
        })
        _write_source_bundle(staging)
        (staging / "README.md").write_text(
            "# D2L remaining 100 Stage A review package\n\n"
            f"Status: `{STATUS}`\n\n"
            "This is a derived review package for the 100 remaining sense records. "
            "It is not a gold dataset and contains no final glossary decisions. The "
            "50-sense authority is not copied or modified. The original unsplit `in place` "
            "parent is excluded because the 50 release already contains its two repaired "
            "senses; `statistical power` is held out as an unresolved Stage A repair parent.\n\n"
            "Reviewer 1 receives all 100 sense cases. Reviewer 2 receives the 65 R3/R4 "
            "risk cases. Reviewers must work independently. R4 cases require later "
            "adjudication; R0 cases may later be sampled for blind audit.\n\n"
            "Each batch contains 10 senses and is safe to send separately. Source rows, "
            "candidate IDs, context text, hashes, and provenance are bound to the V3 parent.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L remaining 100 Stage A review release\n\n"
            f"Status: `{STATUS}`\n\n"
            "Counts:\n\n"
            "- 100 term-sense records;\n"
            "- 300 candidate instances (three per sense);\n"
            f"- {len(selected_contexts)} eligible D2L contexts;\n"
            "- 10 batches of 10 senses;\n"
            "- Reviewer 1: 100 cases; Reviewer 2: 65 risk cases;\n"
            f"- {len(gaps)} senses with explicit context gaps;\n"
            "- zero provider calls, zero Stage B labels, zero final glossary decisions.\n\n"
            "This release is review staging only. It must not be described as human-reviewed "
            "or official until completed results pass the intake and adjudication gates.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "commands.txt").write_text(
            "python -B tools/build_remaining100_stage_a.py --output-root <OUTPUT_ROOT>\n"
            "python -B tools/validate_remaining100_stage_a.py --artifact-root <OUTPUT_ROOT>\n"
            "python -m unittest discover -s tests -p test_remaining100_stage_a.py\n",
            encoding="utf-8",
            newline="\n",
        )
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest_out = {
            "schema_id": "D2LRemaining100StageAManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "status": STATUS,
            "created_at": created_at,
            "counts": {
                "term_sense": 100,
                "candidate": 300,
                "context": len(selected_contexts),
                "batch": 10,
                "reviewer_1_case": 100,
                "reviewer_2_case": len(all_reviewer_cases["reviewer_2"]),
                "stage_a_adjudication_template": 100,
                "source_gap": len(gaps),
            },
            "split_counts": dict(sorted(Counter(row["split"] for row in senses).items())),
            "stratum_counts": dict(sorted(Counter(row["stratum"] for row in senses).items())),
            "risk_counts": dict(sorted(Counter(payload["risk_class"] for payload in payload_by_id.values()).items())),
            "parent_manifest_sha256": manifest["manifest_sha256"],
            "selected_50_ids_sha256": sha256_bytes(canonical_json_bytes(sorted(selected50_ids))),
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest_out["manifest_sha256"] = _manifest_self_hash(manifest_out)
        write_json(staging / "manifest.json", manifest_out)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from validate_remaining100_stage_a import validate_artifact

        errors = validate_artifact(staging)
        if errors:
            raise ValueError("internal validation failed: " + "; ".join(errors))
        zip_name = f"{ARTIFACT_NAME}_reviewer_handoff.zip"
        temp_zip = temporary / zip_name
        build_deterministic_zip(staging, temp_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temp_zip, final_zip)
        zip_sha = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_sha} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest_out["manifest_sha256"],
            "reviewer_handoff_zip": str(final_zip),
            "reviewer_handoff_zip_sha256": zip_sha,
            "counts": manifest_out["counts"],
            "split_counts": manifest_out["split_counts"],
            "risk_counts": manifest_out["risk_counts"],
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    namespace = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--v3-root",
        type=Path,
        default=repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3",
    )
    parser.add_argument(
        "--selected50-root",
        type=Path,
        default=repo_root
        / "dataset"
        / "d2l_dataset_50_senses_fast_track_stage_a_v1"
        / "release"
        / "d2l_dataset_50_senses_150_candidates_stage_b_review_v1",
    )
    parser.add_argument("--output-root", type=Path, default=namespace / "release" / ARTIFACT_NAME)
    parser.add_argument("--created-at", default="2026-07-30T12:00:00Z")
    args = parser.parse_args()
    result = build_remaining100_stage_a(
        v3_root=args.v3_root,
        selected50_root=args.selected50_root,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
