from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .common import read_csv, read_json, read_jsonl, seal_record, sha256_file


POLICY_ID = "dataset-stage-a-pilot-15-senses-reviewed-v1.0"
ARTIFACT_NAME = "d2l_stage_a_pilot_15_senses_reviewed_v1"
SCHEMA_ID = "D2LStageAPilot15ReviewedManifestV1"
SOURCE_ARTIFACT_NAME = "d2l_stage_a_pilot_15_senses_v1"
SOURCE_MANIFEST_SHA256 = "32b3bbea775362504ef698cfe65a4a9e27890f761d7067b1c88dad7a9670bb6e"
SOURCE_MANIFEST_FILE_SHA256 = "f13501f3a1d7a3193893da1ca07582641e143c0bfd8ad0f325a21e2869ca2c1c"
CONTRACT_AUTHORITY_TAG = "contracts-v1.1.0"
CONTRACT_AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
CONTRACT_MANIFEST_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
SOURCE_PARENT_COMMIT = "30c08622e7252ba888c5715d8ce13a7a2ff42749"

SOURCE_DATASET_FILES = (
    "manifest.json",
    "CHECKSUMS.sha256",
    "pilot_15_sense_selection_receipt.json",
    "selected_senses_15.jsonl",
    "candidate_instances_45.jsonl",
    "contexts_selected.jsonl",
    "candidate_index_15.json",
    "stage_b_annotation_template_45.csv",
)

STAGE_B_FIELDS = [
    "term_id", "sense_id", "candidate_id", "candidate_role", "candidate_vi",
    "effective_sense_review_status", "candidate_gold_label", "allowed_scope",
    "validated_variants", "rejected_variants", "reason_codes",
    "positive_context_refs", "vietnamese_evidence_refs", "reviewer_provenance_ref",
    "adjudication_ref",
]

REVIEW_FIELDS = [
    "term_id", "sense_id", "source_term", "split", "selection_group", "risk_class",
    "review_requirement", "review_status", "blind_audit_required",
    "reviewer_1_id", "reviewer_1_type", "reviewer_1_role", "reviewer_1_status",
    "reviewer_1_definition_decision", "reviewer_1_pos_decision", "reviewer_1_scope_decision",
    "reviewer_1_reason_codes", "reviewer_1_confidence", "reviewer_1_artifact_sha256",
    "reviewer_2_id", "reviewer_2_type", "reviewer_2_role", "reviewer_2_status",
    "reviewer_2_definition_decision", "reviewer_2_pos_decision", "reviewer_2_scope_decision",
    "reviewer_2_reason_codes", "reviewer_2_confidence", "reviewer_2_artifact_sha256",
    "adjudicator_id", "adjudicator_type", "adjudicator_status", "adjudication_decision",
    "adjudication_reason", "adjudication_artifact_sha256", "completed_at",
    "reviewer_1_completed_at", "reviewer_2_completed_at", "adjudicator_completed_at",
    "final_definition_decision", "final_pos_decision", "final_scope_decision",
    "final_decision", "resolution_basis", "resolution_status", "review_record_sha256",
]

PENDING_ACTIONS = {
    "Adam": "PROVIDE_EXACT_CORRECTED_DEFINITION_TEXT_OR_ADDITIONAL_PRIMARY_EVIDENCE",
    "fully-connected layers": "ADD_SAME_SENSE_DEFINITION_EVIDENCE_BEFORE_DEFINITION_ACCEPTANCE",
    "in place": "CONSTRUCT_SEPARATE_SENSE_RECORDS_AND_REVIEW_POS_PER_SPLIT",
    "statistical power": "REPLACE_WRONG_SENSE_POSITIVE_CONTEXT_WITH_VALID_PRIMARY_EVIDENCE",
}


def require_iso8601(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is blank")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is not ISO-8601: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return value


def reason_codes(value: str) -> list[str]:
    return sorted({part.strip() for part in re.split(r"[;|]", value or "") if part.strip()})


def float_or_none(value: str) -> float | None:
    return None if not (value or "").strip() else float(value)


def normalized_decision(row: dict[str, str], prefix: str, name: str) -> str:
    value = (row.get(f"{prefix}_{name}") or "").strip().upper()
    if value not in {"", "ACCEPT", "REVISE", "SPLIT_REQUIRED", "UNJUDGEABLE"}:
        raise ValueError(f"invalid {prefix}_{name}: {value}")
    return value or "UNJUDGEABLE"


def review_summary(row: dict[str, str], prefix: str) -> dict[str, Any]:
    status = (row.get(f"{prefix}_status") or "").strip().upper()
    if status not in {"COMPLETE", "UNJUDGEABLE"}:
        raise ValueError(f"invalid {prefix}_status: {status}")
    return {
        "id": (row.get(f"{prefix}_id") or "").strip(),
        "type": (row.get(f"{prefix}_type") or "").strip(),
        "role": (row.get(f"{prefix}_role") or "").strip(),
        "status": status,
        "definition_decision": normalized_decision(row, prefix, "definition_decision"),
        "pos_decision": normalized_decision(row, prefix, "pos_decision"),
        "scope_decision": normalized_decision(row, prefix, "scope_decision"),
        "reason_codes": reason_codes(row.get(f"{prefix}_reason_codes", "")),
        "confidence": float_or_none(row.get(f"{prefix}_confidence", "")),
        "submitted_review_artifact_sha256": (row.get(f"{prefix}_artifact_sha256") or "").strip(),
    }


def load_source_records(p0_root: Path) -> dict[str, Any]:
    manifest_path = p0_root / "manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("manifest_sha256") != SOURCE_MANIFEST_SHA256:
        raise ValueError("P0 manifest self hash mismatch")
    if sha256_file(manifest_path) != SOURCE_MANIFEST_FILE_SHA256:
        raise ValueError("P0 manifest physical hash mismatch")
    for relative in SOURCE_DATASET_FILES:
        path = p0_root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        if relative in {"manifest.json", "CHECKSUMS.sha256"}:
            continue
        binding = manifest.get("files", {}).get(relative)
        if not isinstance(binding, dict) or sha256_file(path) != binding.get("sha256"):
            raise ValueError(f"P0 source binding mismatch: {relative}")
    selected = read_jsonl(p0_root / "selected_senses_15.jsonl")
    candidates = read_jsonl(p0_root / "candidate_instances_45.jsonl")
    contexts = read_jsonl(p0_root / "contexts_selected.jsonl")
    if (len(selected), len(candidates), len(contexts)) != (15, 45, 73):
        raise ValueError("P0 source cardinality mismatch")
    sense_ids = {row["sense_id"] for row in selected}
    if len(sense_ids) != 15:
        raise ValueError("P0 selected senses are not unique")
    if any(row.get("sense_id") not in sense_ids for row in candidates + contexts):
        raise ValueError("P0 source identity join mismatch")
    if set(Counter(row["sense_id"] for row in candidates).values()) != {3}:
        raise ValueError("P0 must contain exactly three candidates per sense")
    return {
        "manifest": manifest,
        "selected": selected,
        "candidates": candidates,
        "contexts": contexts,
    }


def parse_receipt_output_hashes(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    in_output = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "output_hashes:":
            in_output = True
            continue
        if in_output and line and not line.startswith("  "):
            break
        if in_output and "=" in line:
            key, value = line.strip().split("=", 1)
            result[key] = value.strip().lower()
    return result


def check_receipt_hashes(paths: dict[str, Path], receipt: Path) -> dict[str, str]:
    names = {
        "reviewer_1": "stage_a_review_results_15_senses-review1.csv",
        "reviewer_2": "stage_a_review_results_15_senses-review2.csv",
        "blind_audit": "stage_a_blind_audit_template_3-review2.csv",
        "adjudicator": "file-review3.csv",
    }
    expected = parse_receipt_output_hashes(receipt)
    hashes = {label: sha256_file(path) for label, path in paths.items()}
    for label, name in names.items():
        if expected.get(name) != hashes[label]:
            raise ValueError(f"receipt hash mismatch for {label}")
    return hashes


def _check_static_fields(row: dict[str, str], sense: dict[str, Any]) -> None:
    fields = (
        "term_id", "sense_id", "source_term", "split", "selection_group",
        "risk_class", "review_requirement",
    )
    for field in fields:
        if (row.get(field) or "").strip() != str(sense.get(field, "")):
            raise ValueError(f"review identity mismatch for {sense['source_term']}: {field}")


def validate_review_inputs(
    source: dict[str, Any],
    paths: dict[str, Path],
    reviewer_1_completed_at: str,
    reviewer_2_completed_at: str,
) -> dict[str, Any]:
    selected = source["selected"]
    contexts = source["contexts"]
    selected_by_id = {row["sense_id"]: row for row in selected}
    r1_rows = read_csv(paths["reviewer_1"])
    r2_rows = read_csv(paths["reviewer_2"])
    blind_rows = read_csv(paths["blind_audit"])
    adj_rows = read_csv(paths["adjudicator"])
    if (len(r1_rows), len(r2_rows), len(blind_rows), len(adj_rows)) != (15, 15, 3, 4):
        raise ValueError("review input cardinality mismatch")
    r1_by_id = {row["sense_id"]: row for row in r1_rows}
    r2_by_id = {row["sense_id"]: row for row in r2_rows}
    if set(r1_by_id) != set(selected_by_id) or set(r2_by_id) != set(selected_by_id):
        raise ValueError("review sense identity mismatch")
    for row in r1_rows + r2_rows:
        _check_static_fields(row, selected_by_id[row["sense_id"]])

    if {row["reviewer_1_id"].strip() for row in r1_rows} != {"diemphuong"}:
        raise ValueError("reviewer 1 identity mismatch")
    if any(row["reviewer_1_type"].strip() != "HUMAN" or row["reviewer_1_status"].strip().upper() != "COMPLETE" for row in r1_rows):
        raise ValueError("reviewer 1 type/status mismatch")
    if any(require_iso8601(row["completed_at"], "reviewer 1 completed_at") != reviewer_1_completed_at for row in r1_rows):
        raise ValueError("reviewer 1 completion timestamp mismatch")
    if any(row.get("reviewer_2_id", "").strip() or row.get("adjudicator_id", "").strip() for row in r1_rows):
        raise ValueError("reviewer 1 input contains downstream slots")

    dual_ids = {
        sense_id for sense_id, sense in selected_by_id.items()
        if sense["risk_class"] in {"R3_AMBIGUOUS", "R4_SPLIT_OR_POS_RISK"}
    }
    r2_assigned = {row["sense_id"] for row in r2_rows if row.get("reviewer_2_id", "").strip()}
    if r2_assigned != dual_ids or len(r2_assigned) != 10:
        raise ValueError("reviewer 2 assignment mismatch")
    for row in r2_rows:
        assigned = row["sense_id"] in r2_assigned
        if assigned:
            if row["reviewer_2_id"].strip() != "reviewer_2" or row["reviewer_2_type"].strip() != "HUMAN":
                raise ValueError("reviewer 2 identity/type mismatch")
            if row["reviewer_2_status"].strip().upper() not in {"COMPLETE", "UNJUDGEABLE"}:
                raise ValueError("reviewer 2 status mismatch")
            if require_iso8601(row["completed_at"], "reviewer 2 completed_at") != reviewer_2_completed_at:
                raise ValueError("reviewer 2 completion timestamp mismatch")
        else:
            owned = [key for key in row if key.startswith("reviewer_2_")]
            if any(row.get(key, "").strip() for key in owned) or row.get("completed_at", "").strip():
                raise ValueError("reviewer 2 unassigned row is not blank")
    if any(row.get("reviewer_1_id", "").strip() or row.get("adjudicator_id", "").strip() for row in r2_rows):
        raise ValueError("reviewer 2 input contains other slots")

    context_by_id = {row["context_id"]: row for row in contexts}
    expected_blind = {
        row["sense_id"] for row in selected if "BLIND_AUDIT" in row["coverage_tags"]
    }
    if {row["sense_id"] for row in blind_rows} != expected_blind:
        raise ValueError("blind audit identity mismatch")
    for row in blind_rows:
        if row["blind_reviewer_id"].strip() != "reviewer_2" or row["blind_reviewer_type"].strip() != "HUMAN" or row["review_status"].strip().upper() != "COMPLETE":
            raise ValueError("blind audit type/status mismatch")
        for context_id in row.get("positive_context_refs", "").split("|"):
            context = context_by_id.get(context_id)
            if not context or context.get("sense_id") != row["sense_id"]:
                raise ValueError(f"blind audit context mismatch: {context_id}")

    r1_summaries = {sense_id: review_summary(row, "reviewer_1") for sense_id, row in r1_by_id.items()}
    r2_summaries = {sense_id: review_summary(r2_by_id[sense_id], "reviewer_2") for sense_id in dual_ids}
    expected_adj_ids: set[str] = set()
    for sense_id, sense in selected_by_id.items():
        first = r1_summaries[sense_id]
        second = r2_summaries.get(sense_id)
        if sense["risk_class"] == "R4_SPLIT_OR_POS_RISK" or first["status"] == "UNJUDGEABLE" or (second and second["status"] == "UNJUDGEABLE"):
            expected_adj_ids.add(sense_id)
        if second and any(first[field] != second[field] for field in ("definition_decision", "pos_decision", "scope_decision")):
            expected_adj_ids.add(sense_id)

    adj_by_id: dict[str, dict[str, str]] = {}
    for row in adj_rows:
        sense = selected_by_id.get(row.get("sense_id", ""))
        if not sense or row.get("term_id") != sense["term_id"] or row.get("source_term") != sense["source_term"] or row.get("risk_class") != sense["risk_class"]:
            raise ValueError("adjudication identity mismatch")
        if row["sense_id"] in adj_by_id:
            raise ValueError("duplicate adjudication")
        if row["adjudicator_id"].strip() != "snail" or row["adjudicator_type"].strip() != "HUMAN" or row["adjudicator_status"].strip().upper() != "COMPLETE":
            raise ValueError("adjudicator identity/type/status mismatch")
        if row["final_decision"].strip().upper() not in {"ACCEPT", "REVISE", "SPLIT_REQUIRED", "UNRESOLVED"}:
            raise ValueError("invalid adjudication final decision")
        require_iso8601(row["completed_at"], "adjudicator completed_at")
        refs = re.findall(r"ctxx?_[0-9a-f]+", row.get("adjudication_reason", ""))
        if any(ref not in context_by_id or context_by_id[ref]["sense_id"] != row["sense_id"] for ref in refs):
            raise ValueError(f"adjudication context mismatch for {row['source_term']}")
        adj_by_id[row["sense_id"]] = row
    if set(adj_by_id) != expected_adj_ids:
        raise ValueError("adjudication set mismatch")
    if {"diemphuong", "reviewer_2", "snail"} != {
        next(iter({row["reviewer_1_id"].strip() for row in r1_rows})),
        next(iter({row["reviewer_2_id"].strip() for row in r2_rows if row["reviewer_2_id"].strip()})),
        next(iter({row["adjudicator_id"].strip() for row in adj_rows})),
    }:
        raise ValueError("three distinct reviewer identities are required")
    return {
        "selected_by_id": selected_by_id,
        "r1_by_id": r1_by_id,
        "r2_by_id": r2_by_id,
        "blind_rows": blind_rows,
        "adj_by_id": adj_by_id,
        "r1_summaries": r1_summaries,
        "r2_summaries": r2_summaries,
    }


def build_provenance_record(
    sense: dict[str, Any],
    slot: str,
    summary: dict[str, Any],
    source_path: str,
    source_sha256: str,
    completed_at: str,
) -> dict[str, Any]:
    return seal_record({
        "schema_id": "D2LStageAReviewProvenanceV1",
        "policy_id": POLICY_ID,
        "review_id": f"review_{sense['sense_id']}_{slot}",
        "term_id": sense["term_id"],
        "sense_id": sense["sense_id"],
        "source_term": sense["source_term"],
        "reviewer_slot": slot,
        "reviewer_role": summary["role"] or "INDEPENDENT_SENSE_REVIEW",
        "required_reviewer_type": "HUMAN",
        "reviewer_id": summary["id"],
        "reviewer_type": summary["type"],
        "completed_at": completed_at,
        "definition_decision": summary["definition_decision"],
        "pos_decision": summary["pos_decision"],
        "scope_decision": summary["scope_decision"],
        "reason_codes": summary["reason_codes"],
        "confidence": summary["confidence"],
        "source_review_file": source_path,
        "source_review_file_sha256": source_sha256,
        "submitted_review_artifact_sha256": summary["submitted_review_artifact_sha256"],
        "status": summary["status"],
        "human_authority_present": True,
    }, "review_provenance_sha256")


def build_adjudication_record(
    sense: dict[str, Any],
    row: dict[str, str],
    review_ids: list[str],
    source_sha256: str,
) -> dict[str, Any]:
    return seal_record({
        "schema_id": "D2LStageAAdjudicationRecordV1",
        "policy_id": POLICY_ID,
        "adjudication_id": f"adjudication_{sense['sense_id']}",
        "term_id": sense["term_id"],
        "sense_id": sense["sense_id"],
        "source_term": sense["source_term"],
        "input_review_refs": review_ids,
        "adjudicator_id": row["adjudicator_id"].strip(),
        "adjudicator_type": row["adjudicator_type"].strip(),
        "adjudicator_status": row["adjudicator_status"].strip().upper(),
        "final_definition_decision": row["final_definition_decision"].strip().upper(),
        "final_pos_decision": row["final_pos_decision"].strip().upper(),
        "final_scope_decision": row["final_scope_decision"].strip().upper(),
        "final_decision": row["final_decision"].strip().upper(),
        "adjudication_reason": row["adjudication_reason"].strip(),
        "confidence": float_or_none(row["confidence"]),
        "completed_at": row["completed_at"].strip(),
        "source_review_file": "review_inputs/adjudicator.csv",
        "source_review_file_sha256": source_sha256,
        "human_authority_present": True,
        "final_glossary_decision": None,
    }, "adjudication_sha256")


def build_decision_record(
    sense: dict[str, Any],
    review_data: dict[str, Any],
    provenance: list[dict[str, Any]],
    adjudication: dict[str, Any] | None,
    input_hashes: dict[str, str],
) -> dict[str, Any]:
    first = review_data["r1_summaries"][sense["sense_id"]]
    second = review_data["r2_summaries"].get(sense["sense_id"])
    if adjudication:
        final_definition = adjudication["final_definition_decision"]
        final_pos = adjudication["final_pos_decision"]
        final_scope = adjudication["final_scope_decision"]
        final_decision = adjudication["final_decision"]
        status = {
            "ACCEPT": "READY_FOR_CONTRACT_CONSTRUCTION",
            "REVISE": "REVISION_REQUIRED",
            "SPLIT_REQUIRED": "SPLIT_REQUIRED",
            "UNRESOLVED": "UNRESOLVED",
        }[final_decision]
        basis = "ADJUDICATION"
    else:
        final_definition = first["definition_decision"]
        final_pos = first["pos_decision"]
        final_scope = first["scope_decision"]
        if {final_definition, final_pos, final_scope} != {"ACCEPT"}:
            raise ValueError(f"non-adjudicated decision is not fully accepted: {sense['source_term']}")
        final_decision = "ACCEPT"
        status = "READY_FOR_CONTRACT_CONSTRUCTION"
        basis = "SOURCE_GROUND_PLUS_BLIND_AUDIT" if "BLIND_AUDIT" in sense["coverage_tags"] else (
            "TWO_REVIEWER_CONSENSUS" if second else "SINGLE_HUMAN_REVIEW"
        )
    slots = [{
        "reviewer_slot": "reviewer_1",
        "reviewer_id": first["id"],
        "status": first["status"],
        "definition_decision": first["definition_decision"],
        "pos_decision": first["pos_decision"],
        "scope_decision": first["scope_decision"],
        "reason_codes": first["reason_codes"],
        "confidence": first["confidence"],
    }]
    if second:
        slots.append({
            "reviewer_slot": "reviewer_2",
            "reviewer_id": second["id"],
            "status": second["status"],
            "definition_decision": second["definition_decision"],
            "pos_decision": second["pos_decision"],
            "scope_decision": second["scope_decision"],
            "reason_codes": second["reason_codes"],
            "confidence": second["confidence"],
        })
    return seal_record({
        "schema_id": "D2LStageAMergedReviewDecisionV1",
        "policy_id": POLICY_ID,
        "term_id": sense["term_id"],
        "sense_id": sense["sense_id"],
        "source_term": sense["source_term"],
        "split": sense["split"],
        "risk_class": sense["risk_class"],
        "source_selected_sense_sha256": sense["selected_sense_sha256"],
        "parent_source_payload_sha256": sense["source_payload_sha256"],
        "reviewer_slots": slots,
        "review_provenance_refs": [row["review_provenance_sha256"] for row in provenance],
        "adjudication_ref": adjudication["adjudication_sha256"] if adjudication else None,
        "final_definition_decision": final_definition,
        "final_pos_decision": final_pos,
        "final_scope_decision": final_scope,
        "final_decision": final_decision,
        "resolution_basis": basis,
        "resolution_status": status,
        "official_effective_sense_contract_emitted": False,
        "final_glossary_decision": None,
        "input_review_file_sha256": input_hashes,
    }, "review_record_sha256")
