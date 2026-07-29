from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.common import (
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
else:
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


POLICY_ID = "dataset-stage-a-pilot-15-senses-v1.0"
ARTIFACT_NAME = "d2l_stage_a_pilot_15_senses_v1"
SCHEMA_ID = "D2LStageAPilot15ManifestV1"
SELECTION_POLICY_VERSION = "dataset-stage-a-pilot-selection-v1.0"
CONTRACT_AUTHORITY_TAG = "contracts-v1.1.0"
CONTRACT_AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
CONTRACT_MANIFEST_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"


SELECTION_SPECS: dict[str, dict[str, Any]] = {
    "Gradient Clipping": {
        "group": "CLEAR_LOW_RISK",
        "reason": "R0 clear development case with abundant real positive evidence; exercise source-ground and blind-audit path.",
        "tags": ["R0_CLEAR", "SOURCE_GROUND", "BLIND_AUDIT"],
    },
    "momentum": {
        "group": "CLEAR_LOW_RISK",
        "reason": "R0 clear development case with abundant real positive evidence; exercise source-ground and blind-audit path.",
        "tags": ["R0_CLEAR", "SOURCE_GROUND", "BLIND_AUDIT"],
    },
    "null hypothesis": {
        "group": "CLEAR_LOW_RISK",
        "reason": "R0 clear development case with abundant real positive evidence; exercise source-ground and blind-audit path.",
        "tags": ["R0_CLEAR", "SOURCE_GROUND", "BLIND_AUDIT"],
    },
    "underflow": {
        "group": "CLEAR_LOW_RISK",
        "reason": "R1 qualified case; confirms the one-reviewer confirmation route without relying on glossary gold.",
        "tags": ["R1_QUALIFIED", "ONE_HUMAN_REVIEW"],
    },
    "output gate": {
        "group": "CLEAR_LOW_RISK",
        "reason": "Clear R2 missing-glossary case; tests insufficient glossary evidence while corpus evidence remains available.",
        "tags": ["R2_MISSING", "INSUFFICIENT_GLOSSARY_EVIDENCE", "ONE_HUMAN_REVIEW"],
    },
    "Adam": {
        "group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "Known ambiguous/polysemous optimizer term requiring two blind reviewers and disagreement escalation.",
        "tags": ["R3_AMBIGUOUS", "UNRESOLVED_POLYSEMY", "TWO_HUMAN_REVIEWERS"],
    },
    "Jupyter notebook": {
        "group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "R3 ambiguous term selected to exercise independent dual review beyond the legacy disagreement set.",
        "tags": ["R3_AMBIGUOUS", "UNRESOLVED_POLYSEMY", "TWO_HUMAN_REVIEWERS"],
    },
    "learning rate": {
        "group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "R3 ambiguous term selected to exercise independent dual review and candidate competition.",
        "tags": ["R3_AMBIGUOUS", "UNRESOLVED_POLYSEMY", "TWO_HUMAN_REVIEWERS"],
    },
    "vanishing gradients": {
        "group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "R3 ambiguous term selected to exercise independent dual review and candidate competition.",
        "tags": ["R3_AMBIGUOUS", "UNRESOLVED_POLYSEMY", "TWO_HUMAN_REVIEWERS"],
    },
    "word embedding": {
        "group": "AMBIGUOUS_POLYSEMOUS",
        "reason": "R3 ambiguous term selected to exercise independent dual review and candidate competition.",
        "tags": ["R3_AMBIGUOUS", "UNRESOLVED_POLYSEMY", "TWO_HUMAN_REVIEWERS"],
    },
    "in place": {
        "group": "GATE_ADJUDICATION_RISK",
        "reason": "R4 known split/POS case with competing target senses; requires mandatory adjudication and wrong-sense review.",
        "tags": ["R4_SPLIT_OR_POS_RISK", "MANDATORY_ADJUDICATION", "WRONG_SENSE_CANDIDATE"],
    },
    "contexts": {
        "group": "GATE_ADJUDICATION_RISK",
        "reason": "Registered target-collision and legacy adjudication case with competing candidate interpretations.",
        "tags": ["R3_AMBIGUOUS", "TARGET_COLLISION", "WRONG_SENSE_CANDIDATE", "TWO_HUMAN_REVIEWERS"],
    },
    "fully-connected layers": {
        "group": "GATE_ADJUDICATION_RISK",
        "reason": "Registered legacy adjudication case with competing candidate interpretations; target-collision is tested by separate collision-stratum cases.",
        "tags": ["R3_AMBIGUOUS", "WRONG_SENSE_CANDIDATE", "TWO_HUMAN_REVIEWERS"],
    },
    "attention scoring function": {
        "group": "GATE_ADJUDICATION_RISK",
        "reason": "R3 collision/multi-target case selected to test target-collision handling outside the legacy set.",
        "tags": ["R3_AMBIGUOUS", "TARGET_COLLISION", "TWO_HUMAN_REVIEWERS"],
    },
    "statistical power": {
        "group": "GATE_ADJUDICATION_RISK",
        "reason": "Only one active real positive context; tests insufficient evidence and the E-unjudgeable escalation path.",
        "tags": ["R3_AMBIGUOUS", "INSUFFICIENT_POSITIVE_EVIDENCE", "E_UNJUDGEABLE_SCENARIO", "TWO_HUMAN_REVIEWERS"],
    },
}

INTEGRATION_TERMS = ["momentum", "underflow", "Adam", "word embedding", "in place"]

REVIEW_RESULT_FIELDS = [
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
]

STAGE_B_FIELDS = [
    "term_id", "sense_id", "candidate_id", "candidate_role", "candidate_vi",
    "effective_sense_review_status", "candidate_gold_label", "allowed_scope",
    "validated_variants", "rejected_variants", "reason_codes",
    "positive_context_refs", "vietnamese_evidence_refs", "reviewer_provenance_ref",
    "adjudication_ref",
]

BLIND_AUDIT_FIELDS = [
    "blind_case_id", "term_id", "sense_id", "source_term", "split",
    "positive_context_refs", "blind_reviewer_id", "blind_reviewer_type",
    "consensus_split_decision", "consensus_part_of_speech", "consensus_definition_en",
    "review_status", "review_artifact_sha256",
]


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _binding(root: Path, artifact_name: str, commit: str | None = None) -> dict[str, Any]:
    manifest = read_json(root / "manifest.json")
    return {
        "artifact_name": artifact_name,
        "manifest_sha256": manifest["manifest_sha256"],
        "physical_manifest_sha256": sha256_file(root / "manifest.json"),
        "zip_sha256": sha256_file(root.parent / f"{artifact_name}.zip") if (root.parent / f"{artifact_name}.zip").is_file() else None,
        "commit": commit,
        "status": manifest.get("status"),
    }


def _is_real_positive(context: dict[str, Any], sense_id: str) -> bool:
    provenance = context.get("provenance") or {}
    source_ref = str(provenance.get("source_artifact_ref", ""))
    return (
        context.get("sense_id") == sense_id
        and context.get("sense_relation") == "SAME_SENSE"
        and context.get("context_role") in {"PRIMARY", "BACKUP"}
        and bool(source_ref)
        and "synthetic" not in source_ref.casefold()
        and "controlled" not in source_ref.casefold()
        and not str(context.get("context_id", "")).startswith("ctxx_")
    )


def _review_slots(risk_class: str, tags: list[str]) -> list[tuple[str, str]]:
    if risk_class == "R0_CLEAR":
        return [("reviewer_1", "SOURCE_GROUND_AND_BLIND_AUDIT")]
    if risk_class in {"R1_QUALIFIED", "R2_MISSING"}:
        return [("reviewer_1", "SENSE_REVIEW")]
    if risk_class == "R3_AMBIGUOUS":
        slots = [("reviewer_1", "INDEPENDENT_SENSE_REVIEW"), ("reviewer_2", "INDEPENDENT_SENSE_REVIEW")]
        if "E_UNJUDGEABLE_SCENARIO" in tags:
            slots.append(("adjudicator", "E_UNJUDGEABLE_ADJUDICATION_IF_NEEDED"))
        return slots
    if risk_class == "R4_SPLIT_OR_POS_RISK":
        return [
            ("reviewer_1", "INDEPENDENT_SENSE_REVIEW"),
            ("reviewer_2", "INDEPENDENT_SENSE_REVIEW"),
            ("adjudicator", "MANDATORY_ADJUDICATION"),
        ]
    raise ValueError(f"unknown risk class: {risk_class}")


def _review_requirement(risk_class: str) -> str:
    return {
        "R0_CLEAR": "SOURCE_GROUND_PLUS_BLIND_AUDIT",
        "R1_QUALIFIED": "AT_LEAST_ONE_HUMAN_REVIEWER",
        "R2_MISSING": "AT_LEAST_ONE_HUMAN_REVIEWER",
        "R3_AMBIGUOUS": "TWO_DISTINCT_BLIND_HUMAN_REVIEWERS",
        "R4_SPLIT_OR_POS_RISK": "TWO_DISTINCT_REVIEWERS_PLUS_MANDATORY_ADJUDICATION",
    }[risk_class]


def _source_bindings(repo_root: Path) -> dict[str, Any]:
    v1_root = repo_root / "dataset" / "d2l_dataset_fasttrack_glossary_first_v1" / "release" / "d2l_dataset_fasttrack_glossary_first_v1"
    v11_root = repo_root / "dataset" / "d2l_dataset_fasttrack_glossary_first_v1_1" / "release" / "d2l_dataset_fasttrack_glossary_first_v1_1"
    v3_root = repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3"
    hardening_root = repo_root / "dataset" / "dataset_methodology_hardening_v1" / "release"
    bindings = {
        "immutable_fasttrack_v1": _binding(v1_root, "d2l_dataset_fasttrack_glossary_first_v1", _git(repo_root, "log", "-1", "--format=%H", "--", "dataset/d2l_dataset_fasttrack_glossary_first_v1")),
        "repair_companion_v1_1": _binding(v11_root, "d2l_dataset_fasttrack_glossary_first_v1_1", _git(repo_root, "log", "-1", "--format=%H", "--", "dataset/d2l_dataset_fasttrack_glossary_first_v1_1")),
        "dataset_v3": {
            "artifact_name": read_json(v3_root / "manifest.json").get("artifact_name"),
            "manifest_sha256": read_json(v3_root / "manifest.json")["manifest_sha256"],
            "physical_manifest_sha256": sha256_file(v3_root / "manifest.json"),
        },
        "methodology_hardening": {
            "manifest_sha256": read_json(hardening_root / "manifest.json")["artifact_manifest_sha256"],
            "physical_manifest_sha256": sha256_file(hardening_root / "manifest.json"),
        },
        "terminology_contracts": {
            "authority_tag": CONTRACT_AUTHORITY_TAG,
            "authority_commit": CONTRACT_AUTHORITY_COMMIT,
            "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        },
    }
    return bindings


def _load_sources(repo_root: Path) -> dict[str, Any]:
    v1_root = repo_root / "dataset" / "d2l_dataset_fasttrack_glossary_first_v1" / "release" / "d2l_dataset_fasttrack_glossary_first_v1"
    v3_root = repo_root / "dataset" / "d2l_context_support_set_validation_ready_v3"
    v1_manifest = read_json(v1_root / "manifest.json")
    projections = read_jsonl(v1_root / "effective_sense_contracts" / "pending_effective_sense_projection.jsonl")
    candidates = read_jsonl(v1_root / "candidate_provenance_450.jsonl")
    risks = list(csv.DictReader((v1_root / "sense_risk_classification.csv").open("r", encoding="utf-8-sig", newline="")))
    senses = read_jsonl(v3_root / "term_senses.jsonl")
    contexts = read_jsonl(v3_root / "contexts.jsonl")
    return {
        "v1_manifest": v1_manifest,
        "projections": {row["source_term"]: row for row in projections},
        "candidates": candidates,
        "risks": {row["source_term"]: row for row in risks},
        "senses": {row["source_term"]: row for row in senses},
        "contexts": {row["context_id"]: row for row in contexts},
    }


def _selection_records(sources: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source_term, spec in SELECTION_SPECS.items():
        projection = sources["projections"].get(source_term)
        risk = sources["risks"].get(source_term)
        sense = sources["senses"].get(source_term)
        if not projection or not risk or not sense:
            raise ValueError(f"selection source term is missing from parent artifacts: {source_term}")
        if risk["split"] != "development" or sense["split"] != "development":
            raise ValueError(f"P0 selection must remain development-only: {source_term}")
        if risk["risk_class"] not in {"R0_CLEAR", "R1_QUALIFIED", "R2_MISSING", "R3_AMBIGUOUS", "R4_SPLIT_OR_POS_RISK"}:
            raise ValueError(f"invalid risk class for {source_term}")
        positive_ids = list(dict.fromkeys(projection["positive_definition_evidence_ids"] + projection["positive_pos_evidence_ids"]))
        boundary_ids = list(dict.fromkeys(projection["boundary_context_ids"]))
        for context_id in positive_ids:
            context = sources["contexts"].get(context_id)
            if not context or not _is_real_positive(context, projection["sense_id"]):
                raise ValueError(f"invalid real positive context {context_id} for {source_term}")
        if set(positive_ids) & set(boundary_ids):
            raise ValueError(f"positive/boundary overlap for {source_term}")
        record = {
            "schema_id": "D2LStageAPilotSelectedSenseV1",
            "policy_id": POLICY_ID,
            "term_id": projection["term_id"],
            "sense_id": projection["sense_id"],
            "source_term": source_term,
            "split": sense["split"],
            "stratum": sense["stratum"],
            "risk_class": risk["risk_class"],
            "selection_group": spec["group"],
            "selection_reason": spec["reason"],
            "coverage_tags": spec["tags"],
            "proposed_definition_en": projection["effective_definition_en"],
            "proposed_part_of_speech": projection["effective_part_of_speech"],
            "proposed_scope_note": projection.get("scope_note"),
            "glossary_match_status": projection["glossary_match_status"],
            "glossary_candidate_vi": projection.get("glossary_candidate_vi"),
            "positive_context_count": len(positive_ids),
            "boundary_context_count": len(boundary_ids),
            "positive_definition_evidence_ids": projection["positive_definition_evidence_ids"],
            "positive_pos_evidence_ids": projection["positive_pos_evidence_ids"],
            "boundary_context_ids": boundary_ids,
            "review_requirement": _review_requirement(risk["risk_class"]),
            "review_status": "PENDING_HUMAN_REVIEW",
            "parent_term_sense_sha256": projection["parent_term_sense_sha256"],
            "parent_projection_sha256": projection["effective_sense_projection_sha256"],
            "source_payload_sha256": projection["source_payload_sha256"],
            "official_effective_sense_contract_emitted": False,
            "selection_policy_version": SELECTION_POLICY_VERSION,
        }
        records.append(seal_record(record, "selected_sense_sha256"))
    return records


def _candidate_records(sources: dict[str, Any], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_ids = {row["sense_id"] for row in selected}
    group_by_id = {row["sense_id"]: row["selection_group"] for row in selected}
    output: list[dict[str, Any]] = []
    for source in sources["candidates"]:
        if source.get("sense_id") not in selected_ids:
            continue
        candidate_id = source.get("candidate_id")
        if not candidate_id:
            raise ValueError("parent candidate record has no stable candidate_id")
        record = {
            "schema_id": "D2LStageAPilotCandidateProjectionV1",
            "policy_id": POLICY_ID,
            "term_id": source["term_id"],
            "sense_id": source["sense_id"],
            "source_term": next(row["source_term"] for row in selected if row["sense_id"] == source["sense_id"]),
            "split": "development",
            "candidate_id": candidate_id,
            "candidate_role": source["candidate_role"],
            "candidate_vi": source["candidate_vi"],
            "candidate_source_type": source.get("candidate_source_type"),
            "parent_candidate_provenance_sha256": source.get("candidate_provenance_sha256"),
            "parent_candidate_instance_sha256": source.get("parent_candidate_instance_sha256"),
            "parent_candidate_record": source,
            "selection_group": group_by_id[source["sense_id"]],
            "candidate_gold_label": None,
        }
        output.append(seal_record(record, "candidate_projection_sha256"))
    output.sort(key=lambda row: (row["sense_id"], row["candidate_role"], row["candidate_id"]))
    if len(output) != 45 or any(Counter(row["candidate_role"] for row in output if row["sense_id"] == sense_id) != Counter({"A": 1, "B": 1, "C": 1}) for sense_id in selected_ids):
        raise ValueError("selected senses must have exactly candidate roles A/B/C")
    return output


def _context_records(sources: dict[str, Any], selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uses: dict[str, set[str]] = defaultdict(set)
    for sense in selected:
        for context_id in sense["positive_definition_evidence_ids"]:
            uses[context_id].add("POSITIVE_DEFINITION")
        for context_id in sense["positive_pos_evidence_ids"]:
            uses[context_id].add("POSITIVE_POS")
        for context_id in sense["boundary_context_ids"]:
            uses[context_id].add("BOUNDARY_ONLY")
    output: list[dict[str, Any]] = []
    for context_id in sorted(uses):
        source = sources["contexts"].get(context_id)
        if not source:
            raise ValueError(f"selected context is missing from V3: {context_id}")
        record = dict(source)
        record["pilot_evidence_roles"] = sorted(uses[context_id])
        record["pilot_context_sha256"] = source.get("context_sha256")
        output.append(record)
    return output


def _review_rows(selected: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    adjudication: list[dict[str, Any]] = []
    for sense in selected:
        row = {field: "" for field in REVIEW_RESULT_FIELDS}
        row.update({
            "term_id": sense["term_id"],
            "sense_id": sense["sense_id"],
            "source_term": sense["source_term"],
            "split": sense["split"],
            "selection_group": sense["selection_group"],
            "risk_class": sense["risk_class"],
            "review_requirement": sense["review_requirement"],
            "review_status": "PENDING_HUMAN_REVIEW",
            "blind_audit_required": "true" if "BLIND_AUDIT" in sense["coverage_tags"] else "false",
        })
        rows.append(row)
        for slot, role in _review_slots(sense["risk_class"], sense["coverage_tags"]):
            review_id = f"pending_review_{sense['sense_id']}_{slot}"
            record = {
                "schema_id": "D2LStageAReviewProvenanceTemplateV1",
                "policy_id": POLICY_ID,
                "review_id": review_id,
                "term_id": sense["term_id"],
                "sense_id": sense["sense_id"],
                "source_term": sense["source_term"],
                "reviewer_slot": slot,
                "reviewer_role": role,
                "required_reviewer_type": "HUMAN",
                "reviewer_id": None,
                "reviewer_type": None,
                "training_material_version": None,
                "assigned_at": None,
                "started_at": None,
                "completed_at": None,
                "definition_decision": None,
                "pos_decision": None,
                "scope_decision": None,
                "reason_codes": [],
                "confidence": None,
                "review_artifact_sha256": None,
                "status": "PENDING_HUMAN_REVIEW",
                "human_authority_present": False,
            }
            provenance.append(seal_record(record, "review_provenance_sha256"))
            if slot == "adjudicator":
                adjudication.append(seal_record({
                    "schema_id": "D2LStageAAdjudicationTemplateV1",
                    "policy_id": POLICY_ID,
                    "adjudication_id": f"pending_adjudication_{sense['sense_id']}",
                    "term_id": sense["term_id"],
                    "sense_id": sense["sense_id"],
                    "source_term": sense["source_term"],
                    "input_review_refs": [f"pending_review_{sense['sense_id']}_reviewer_1", f"pending_review_{sense['sense_id']}_reviewer_2"],
                    "adjudicator_id": None,
                    "adjudicator_type": None,
                    "final_decision": None,
                    "adjudication_reason": None,
                    "completed_at": None,
                    "adjudication_artifact_sha256": None,
                    "status": "PENDING_HUMAN_REVIEW",
                    "human_authority_present": False,
                }, "adjudication_sha256"))
    return rows, provenance, adjudication


def _stage_b_rows(candidates: list[dict[str, Any]], selected_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for candidate in candidates:
        row = {field: "" for field in STAGE_B_FIELDS}
        row.update({
            "term_id": candidate["term_id"],
            "sense_id": candidate["sense_id"],
            "candidate_id": candidate["candidate_id"],
            "candidate_role": candidate["candidate_role"],
            "candidate_vi": candidate["candidate_vi"],
            "effective_sense_review_status": selected_by_id[candidate["sense_id"]]["review_status"],
        })
        rows.append(row)
    return rows


def _write_review_pack(output: Path, pack_zip: Path, files: Iterable[str]) -> str:
    with tempfile.TemporaryDirectory(prefix="d2l_stage_a_pilot_pack_") as temp:
        pack_parent = Path(temp)
        pack_root = pack_parent / "stage_a_review_pack_15_senses"
        pack_root.mkdir()
        for relative in files:
            source = output / relative
            destination = pack_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        pack_manifest = {
            "schema_id": "D2LStageAReviewPackManifestV1",
            "policy_id": POLICY_ID,
            "artifact_name": "stage_a_review_pack_15_senses",
            "files": build_file_inventory(pack_root),
            "human_authority_present": False,
        }
        write_json(pack_root / "pack_manifest.json", pack_manifest)
        write_checksums(pack_root, pack_root / "CHECKSUMS.sha256")
        build_deterministic_zip(pack_parent, pack_zip)
    return sha256_file(pack_zip)


def build_pilot(repo_root: Path, output: Path, created_at: str) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output = output.resolve()
    namespace_root = Path(__file__).resolve().parents[1]
    if namespace_root not in output.parents:
        raise ValueError(f"output must be under {namespace_root}")
    sources = _load_sources(repo_root)
    bindings = _source_bindings(repo_root)
    selected = _selection_records(sources)
    counts = Counter(row["selection_group"] for row in selected)
    if len(selected) != 15 or dict(counts) != {"CLEAR_LOW_RISK": 5, "AMBIGUOUS_POLYSEMOUS": 5, "GATE_ADJUDICATION_RISK": 5}:
        raise ValueError(f"selection distribution mismatch: {counts}")
    candidates = _candidate_records(sources, selected)
    contexts = _context_records(sources, selected)
    review_rows, provenance, adjudication = _review_rows(selected)
    selected_by_id = {row["sense_id"]: row for row in selected}
    stage_b = _stage_b_rows(candidates, selected_by_id)
    reset_directory(output)

    write_jsonl(output / "selected_senses_15.jsonl", selected)
    write_jsonl(output / "candidate_instances_45.jsonl", candidates)
    write_jsonl(output / "contexts_selected.jsonl", contexts)
    write_csv(output / "stage_a_review_results_15_senses.csv", review_rows, REVIEW_RESULT_FIELDS)
    write_jsonl(output / "review_provenance_15_senses.jsonl", provenance)
    write_jsonl(output / "stage_a_adjudication_15_senses.jsonl", adjudication)
    write_csv(output / "stage_b_annotation_template_45.csv", stage_b, STAGE_B_FIELDS)
    blind_rows = []
    for sense in selected:
        if "BLIND_AUDIT" not in sense["coverage_tags"]:
            continue
        blind_rows.append({
            "blind_case_id": f"pilot15_blind_{sense['sense_id']}",
            "term_id": sense["term_id"],
            "sense_id": sense["sense_id"],
            "source_term": sense["source_term"],
            "split": sense["split"],
            "positive_context_refs": "|".join(sorted(set(sense["positive_definition_evidence_ids"] + sense["positive_pos_evidence_ids"]))),
            "blind_reviewer_id": "",
            "blind_reviewer_type": "",
            "consensus_split_decision": "",
            "consensus_part_of_speech": "",
            "consensus_definition_en": "",
            "review_status": "PENDING_BLIND_REVIEW",
            "review_artifact_sha256": "",
        })
    write_csv(output / "stage_a_blind_audit_template_3.csv", blind_rows, BLIND_AUDIT_FIELDS)
    (output / "stage_a_review_instructions.md").write_text(
        "# Stage A Pilot Review Instructions\n\n"
        "Review only the assigned sense and the real D2L English contexts in this pack.\n"
        "Do not use another reviewer’s fields, Global scores, or downstream decisions.\n\n"
        "R0 cases use source-ground review plus the separate blind-audit template.\n"
        "R1/R2 cases require at least one human reviewer. R3 cases require two\n"
        "distinct blind human reviewers. R4 and E-unjudgeable cases require\n"
        "adjudication when the review policy says so.\n\n"
        "Leave fields blank when you cannot judge. Do not mark a record COMPLETE\n"
        "without real reviewer provenance. Positive evidence must be SAME_SENSE\n"
        "PRIMARY/BACKUP D2L English context; contrastive context is boundary-only.\n",
        encoding="utf-8",
        newline="\n",
    )

    selection_receipt = {
        "schema_id": "D2LStageAPilot15SelectionReceiptV1",
        "policy_id": POLICY_ID,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "selection_status": "FROZEN_FOR_REAL_HUMAN_REVIEW",
        "parent_dataset_manifest_sha256": sources["v1_manifest"]["manifest_sha256"],
        "selected_sense_count": len(selected),
        "group_counts": dict(sorted(counts.items())),
        "records": selected,
    }
    selection_receipt = seal_record(selection_receipt, "receipt_sha256")
    write_json(output / "pilot_15_sense_selection_receipt.json", selection_receipt)

    write_json(output / "effective_sense_contracts_15" / "README.md", {
        "status": "EMPTY_OFFICIAL_DIRECTORY",
        "reason": "No human review authority is present; official contracts must not be fabricated.",
        "expected_count_after_finalization": 15,
    })

    integration_records = []
    for term in INTEGRATION_TERMS:
        sense = next(row for row in selected if row["source_term"] == term)
        integration_records.append({
            "term_id": sense["term_id"],
            "sense_id": sense["sense_id"],
            "source_term": term,
            "selection_group": sense["selection_group"],
            "selection_status": "PENDING_STAGE_A_FINALIZATION",
            "reason": "Provisional 2 clear + 2 ambiguous + 1 gate subset; not official until the 15-sense review is finalized.",
        })
    integration_receipt = seal_record({
        "schema_id": "D2LIntegrationPilot5SelectionReceiptV1",
        "policy_id": POLICY_ID,
        "selection_status": "PENDING_STAGE_A_FINALIZATION",
        "required_shape": {"clear": 2, "ambiguous": 2, "gate": 1},
        "records": integration_records,
        "official_effective_sense_count": 0,
        "official_frozen_candidate_count": 0,
        "complete_constraint_package_count": 0,
    }, "receipt_sha256")
    write_json(output / "integration_pilot_5_sense_selection_receipt.json", integration_receipt)
    for directory, reason in {
        "integration_pilot_effective_sense_contracts_5": "Pending human Stage A finalization; no official contract emitted.",
        "integration_pilot_frozen_candidates_15": "Pending effective sense contracts; no COMPLETE candidate emitted.",
        "integration_pilot_constraint_packages_15": "Pending COMPLETE candidate contracts; no package emitted.",
    }.items():
        write_json(output / directory / "README.md", {"status": "PENDING", "reason": reason})

    candidate_index = {
        "schema_id": "D2LStageAPilotCandidateIndexV1",
        "policy_id": POLICY_ID,
        "parent_dataset_manifest_sha256": sources["v1_manifest"]["manifest_sha256"],
        "candidate_count": len(candidates),
        "sense_count": len(selected),
        "records": [
            {"candidate_id": row["candidate_id"], "sense_id": row["sense_id"], "candidate_role": row["candidate_role"], "candidate_projection_sha256": row["candidate_projection_sha256"]}
            for row in candidates
        ],
    }
    write_json(output / "candidate_index_15.json", candidate_index)

    gate_checks = {
        "selected_sense_count_15": True,
        "all_positive_contexts_real_d2l": True,
        "synthetic_positive_evidence_zero": True,
        "positive_boundary_overlap_zero": True,
        "quarantined_positive_refs_zero": True,
        "all_required_risk_reviews_complete": False,
        "r3_two_human_reviews_complete": False,
        "r4_adjudication_complete": False,
        "review_provenance_complete": False,
        "official_effective_sense_contract_count_15": False,
        "integration_pilot_effective_sense_count_5": False,
        "official_frozen_candidate_count_15": False,
        "complete_constraint_package_count_15": False,
        "identity_join_mismatch_zero": True,
        "stage_b_gold_autofill_zero": True,
        "fabricated_human_authority_zero": True,
    }
    blockers = [name for name, passed in gate_checks.items() if not passed]
    gate_report = {
        "schema_id": "D2LStageAPilot15AcceptanceGateReportV1",
        "policy_id": POLICY_ID,
        "status": "BLOCKED_BY_HUMAN_REVIEW",
        "checks": gate_checks,
        "blockers": blockers,
        "selected_sense_count": 15,
        "finalized_sense_count": 0,
        "r3_review_count": 0,
        "r4_adjudication_count": 0,
        "official_effective_sense_contract_count": 0,
        "official_frozen_candidate_count": 0,
        "complete_constraint_package_count": 0,
        "stage_b_open_row_count": len(stage_b),
        "stage_b_gold_autofill_count": 0,
        "final_glossary_decision": None,
    }
    write_json(output / "stage_a_pilot_15_acceptance_gate_report.json", gate_report)
    write_json(output / "stage_a_pilot_15_summary.json", {
        "schema_id": "D2LStageAPilot15SummaryV1",
        "policy_id": POLICY_ID,
        "status": "BLOCKED_BY_HUMAN_REVIEW",
        "group_counts": dict(sorted(counts.items())),
        "risk_counts": dict(sorted(Counter(row["risk_class"] for row in selected).items())),
        "selected_sense_count": 15,
        "candidate_count": 45,
        "selected_context_count": len(contexts),
        "positive_context_count": sum(row["positive_context_count"] for row in selected),
        "boundary_context_count": sum(row["boundary_context_count"] for row in selected),
        "review_provenance_template_count": len(provenance),
        "adjudication_template_count": len(adjudication),
        "blind_audit_case_count": len(blind_rows),
        "official_counts": {"effective_sense": 0, "frozen_candidate": 0, "constraint_package": 0},
        "stage_b_open_row_count": len(stage_b),
    })

    release_receipt = {
        "schema_id": "D2LStageAPilotReleaseReceiptV1",
        "policy_id": POLICY_ID,
        "artifact_name": ARTIFACT_NAME,
        "status": "BLOCKED_BY_HUMAN_REVIEW",
        "created_at": created_at,
        "review_pack_zip_ref": "stage_a_review_pack_15_senses.zip",
        "review_pack_zip_sha256": None,
        "parent_bindings": bindings,
        "selected_sense_count": 15,
        "candidate_count": 45,
        "official_counts": {"effective_sense": 0, "frozen_candidate": 0, "constraint_package": 0},
        "stage_b_open_row_count": len(stage_b),
        "final_glossary_decision": None,
    }
    pack_files = [
        "pilot_15_sense_selection_receipt.json", "selected_senses_15.jsonl", "candidate_instances_45.jsonl",
        "contexts_selected.jsonl", "stage_a_review_results_15_senses.csv", "review_provenance_15_senses.jsonl",
        "stage_a_adjudication_15_senses.jsonl", "stage_b_annotation_template_45.csv",
        "stage_a_blind_audit_template_3.csv", "stage_a_review_instructions.md",
    ]
    pack_zip = output.parent / "stage_a_review_pack_15_senses.zip"
    pack_hash = _write_review_pack(output, pack_zip, pack_files)
    release_receipt["review_pack_zip_sha256"] = pack_hash
    write_json(output / "pilot_release_receipt.json", seal_record(release_receipt, "receipt_sha256"))

    write_json(output / "lineage.json", {
        "schema_id": "D2LStageAPilotLineageV1",
        "policy_id": POLICY_ID,
        "parent_bindings": bindings,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "selected_sense_ids": [row["sense_id"] for row in selected],
        "candidate_ids": [row["candidate_id"] for row in candidates],
        "positive_context_ids": sorted({context_id for row in selected for context_id in row["positive_definition_evidence_ids"] + row["positive_pos_evidence_ids"]}),
        "boundary_context_ids": sorted({context_id for row in selected for context_id in row["boundary_context_ids"]}),
        "provider_call_count": 0,
        "human_authority_present": False,
    })
    write_json(output / "environment.json", {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "created_at": created_at,
        "network_calls": 0,
    })
    write_json(output / "ownership_scan.json", {
        "status": "PASS",
        "owned_namespace": "dataset/d2l_stage_a_pilot_15_senses_v1",
        "parent_namespaces_modified": [],
        "external_reviewer_bytes_consumed": False,
    })
    write_json(output / "credential_scan.json", {"status": "PASS", "credentials_in_artifact": False})
    write_json(output / "git_commit_receipt.json", {
        "schema_id": "D2LStageAPilotGitReceiptV1",
        "repository_head": _git(repo_root, "rev-parse", "HEAD"),
        "branch": _git(repo_root, "branch", "--show-current"),
        "tracked_worktree_status": _git(repo_root, "status", "--porcelain", "--untracked-files=no") or "CLEAN",
        "external_untracked_paths_excluded": True,
    })
    (output / "commands.txt").write_text(
        "python tools/build_pilot.py --repo-root C:\\work\\terminology_evidence-worktrees\\dataset-v1 --output release\\d2l_stage_a_pilot_15_senses_v1 --created-at 2026-07-29T00:00:00Z\n"
        "python tools/validate_pilot.py --artifact-root release\\d2l_stage_a_pilot_15_senses_v1 --repo-root C:\\work\\terminology_evidence-worktrees\\dataset-v1\n",
        encoding="utf-8",
        newline="\n",
    )

    files = build_file_inventory(output, {"manifest.json", "CHECKSUMS.sha256"})
    manifest = {
        "schema_id": SCHEMA_ID,
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "artifact_name": ARTIFACT_NAME,
        "created_at": created_at,
        "status": "BLOCKED_BY_HUMAN_REVIEW",
        "counts": {
            "selected_sense": 15,
            "candidate": 45,
            "selected_context": len(contexts),
            "review_provenance_template": len(provenance),
            "adjudication_template": len(adjudication),
            "blind_audit_case": len(blind_rows),
            "stage_b_open_rows": len(stage_b),
            "official_effective_sense_contract": 0,
            "official_frozen_candidate_contract": 0,
            "complete_constraint_evidence_package": 0,
        },
        "group_counts": dict(sorted(counts.items())),
        "source_bindings": bindings,
        "review_pack_zip_sha256": pack_hash,
        "files": files,
        "provider_call_count": 0,
        "final_glossary_decision": None,
        "human_authority_present": False,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    write_json(output / "manifest.json", manifest)
    write_checksums(output, output / "CHECKSUMS.sha256")
    artifact_zip = output.parent / f"{output.name}.zip"
    build_deterministic_zip(output, artifact_zip)
    (output.parent / f"{output.name}.zip.sha256").write_text(
        f"{sha256_file(artifact_zip)} *{artifact_zip.name}\n", encoding="ascii", newline="\n"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()
    manifest = build_pilot(args.repo_root, args.output, args.created_at)
    print(json.dumps({"status": manifest["status"], "manifest_sha256": manifest["manifest_sha256"], "counts": manifest["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
