from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from hardening_common import (
    deterministic_zip,
    file_bindings,
    read_json,
    read_jsonl,
    seal,
    sha256_file,
    validate_file_bindings,
    validate_self_hash,
    write_checksums,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)
from corpus_audit import audit_contexts, load_source_blocks
from downstream_selection import select_downstream_blocks
from statistical_units import build_statistical_units


ARTIFACT_SCHEMA_ID = "D2LDatasetMethodologyHardeningV1"
ARTIFACT_SCHEMA_VERSION = "1.0.0"
GENERATION_POLICY_VERSION = "d2l_dataset_methodology_hardening_v1"
CREATED_AT = "2026-07-29T00:00:00Z"
AUDIT_FIELDS = [
    "context_id",
    "document_id",
    "chapter_id",
    "block_id",
    "sentence_id",
    "source_text",
    "source_start_offset",
    "source_end_offset",
    "term_start_offset",
    "term_end_offset",
    "source_hash",
    "origin",
    "extraction_method",
    "context_role",
    "context_type",
    "sense_id",
    "scope_id",
    "audit_status",
    "audit_reason",
    "eligible_for_c_primary_support",
    "eligible_for_c_support",
    "parent_record_id",
    "parent_record_sha256",
    "transformation_id",
    "transformation_version",
]


def _validate_parent(parent_root: Path) -> dict[str, Any]:
    manifest = read_json(parent_root / "manifest.json")
    errors: list[str] = []
    validate_self_hash(manifest, "manifest_sha256", "Parent manifest", errors)
    validate_file_bindings(parent_root, manifest["files"], "Parent", errors)
    if errors:
        raise ValueError(json.dumps(errors, ensure_ascii=False))
    return manifest


def _adversarial_manifest(parent_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": "D2LMethodologyAdversarialManifestV1",
        "schema_version": "1.0.0",
        "status": "BLOCKED_EXTERNAL_INPUTS",
        "parent_dataset_manifest_sha256": parent_manifest["manifest_sha256"],
        "creation_protocol_version": "d2l_adversarial_freeze_protocol_v1",
        "protocol_frozen_at": CREATED_AT,
        "allowed_generation_sources": ["AUTHOR_DESIGNED", "BLIND_SECOND_PARTY"],
        "allowed_attack_types": [
            "POPULAR_WRONG_CALQUE",
            "WRONG_SENSE_NATURAL_CANDIDATE",
            "UNRESOLVED_POLYSEMY",
            "TARGET_COLLISION",
            "HIGH_ROUNDTRIP_BUT_WRONG",
            "MODEL_SELF_PREFERENCE",
            "TAIL_CONTEXT_FAILURE",
            "CONTRADICTION",
            "INSUFFICIENT_EVIDENCE_TRAP",
        ],
        "case_count": 0,
        "source_counts": {"AUTHOR_DESIGNED": 0, "BLIND_SECOND_PARTY": 0},
        "cases": [],
        "blockers": [
            "AUTHOR_DESIGNED cases have not been independently authored and frozen.",
            "BLIND_SECOND_PARTY creator evidence is not available.",
        ],
        "runtime_input_policy": "EXPECTED_GATE_FORBIDDEN_FROM_RUNTIME_INPUT",
    }


def _tac_manifest(
    parent_manifest: dict[str, Any], senses: list[dict[str, Any]]
) -> dict[str, Any]:
    surfaces: dict[str, set[str]] = defaultdict(set)
    for sense in senses:
        surfaces[sense["source_term"].strip().casefold()].add(sense["sense_id"])
    natural_candidates = {
        surface: sorted(sense_ids)
        for surface, sense_ids in sorted(surfaces.items())
        if len(sense_ids) > 1
    }
    return {
        "schema_id": "D2LMethodologyTACDriftManifestV1",
        "schema_version": "1.0.0",
        "status": "BLOCKED_CASE_COLLECTION",
        "parent_dataset_manifest_sha256": parent_manifest["manifest_sha256"],
        "allowed_drift_types": ["NATURAL_DRIFT", "SYNTHETIC_CONTROLLED_DRIFT"],
        "expected_classes": ["SAME", "RELATED", "DIFFERENT", "AMBIGUOUS"],
        "natural_multi_sense_surface_count": len(natural_candidates),
        "natural_multi_sense_surfaces": natural_candidates,
        "natural_case_count": 0,
        "synthetic_controlled_case_count": 0,
        "cases": [],
        "c_evidence_policy": "SYNTHETIC_CONTROLLED_DRIFT_EXCLUDED_FROM_C",
        "blockers": [
            "The selected 150 senses contain no same-surface multi-sense natural pair."
            if not natural_candidates
            else "Natural drift occurrences have not been curated.",
            "Synthetic controlled drift cases have not been independently authored.",
        ],
    }


def _validation_report(
    senses: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    statistical_rows: list[dict[str, Any]],
    leakage_rows: list[dict[str, Any]],
    downstream_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    audit_counts = Counter(row["audit_status"] for row in audit_rows)
    human_pending = sum(
        row.get("official_cst_status") == "HUMAN_REVIEW_REQUIRED" for row in senses
    )
    blockers = [
        {
            "code": "PARENT_HUMAN_REVIEW_PENDING",
            "count": human_pending,
            "detail": "Parent term-sense definitions/POS remain pending human review.",
        },
        {
            "code": "CROSS_SPLIT_SOURCE_BLOCK_CLUSTER",
            "count": len(leakage_rows),
            "detail": "Sentence-safe V3 still shares source blocks across splits.",
        },
        {
            "code": "CONTROLLED_VIETNAMESE_REGISTRY_EMPTY",
            "count": 0,
            "detail": "No external controlled Vietnamese source has been supplied.",
        },
        {
            "code": "BLIND_ADVERSARIAL_SUBSET_PENDING",
            "count": 0,
            "detail": "Independent blind creator evidence is unavailable.",
        },
        {
            "code": "TAC_DRIFT_CASES_PENDING",
            "count": 0,
            "detail": "Natural and synthetic controlled drift cases are not frozen.",
        },
    ]
    return {
        "schema_id": "D2LMethodologyHardeningValidationReportV1",
        "schema_version": "1.0.0",
        "status": "PASS_WITH_BLOCKERS",
        "structural_integrity": "PASS",
        "methodology_readiness": "BLOCKED_REPAIR_AND_EXTERNAL_INPUTS",
        "definition_of_done": False,
        "errors": [],
        "blockers": blockers,
        "checks": {
            "context_count": len(audit_rows),
            "audit_status_counts": dict(sorted(audit_counts.items())),
            "corpus_context_count": audit_counts["PASS_CORPUS_EXTRACTED"],
            "synthetic_context_count": audit_counts["FAIL_SYNTHETIC"],
            "synthetic_in_c_primary_support": sum(
                row["origin"] == "SYNTHETIC_CONTROLLED"
                and row["eligible_for_c_primary_support"]
                for row in audit_rows
            ),
            "statistical_unit_count": len(statistical_rows),
            "duplicate_occurrence_id_count": (
                len(statistical_rows)
                - len({row["occurrence_id"] for row in statistical_rows})
            ),
            "cross_split_source_block_cluster_count": len(leakage_rows),
            "controlled_vietnamese_source_count": 0,
            "adversarial_case_count": 0,
            "tac_drift_case_count": 0,
            "downstream_selected_block_count": len(downstream_rows),
            "downstream_experiment_arms": ["A", "B", "C", "D"],
        },
    }


def build_artifact(
    parent_root: Path,
    source_document: Path,
    output_root: Path,
    archive_path: Path,
    protocol_path: Path,
) -> dict[str, Any]:
    parent_root = parent_root.resolve(strict=True)
    source_document = source_document.resolve(strict=True)
    output_root = output_root.resolve(strict=False)
    archive_path = archive_path.resolve(strict=False)
    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    if archive_path.exists() or Path(str(archive_path) + ".sha256").exists():
        raise FileExistsError(f"Archive output already exists: {archive_path}")
    parent_manifest = _validate_parent(parent_root)
    senses = read_jsonl(parent_root / "term_senses.jsonl")
    candidates = read_jsonl(parent_root / "candidate_instances.jsonl")
    contexts = read_jsonl(parent_root / "contexts.jsonl")
    source_document_sha256, source_blocks = load_source_blocks(source_document)
    bound_hashes = {
        row.get("provenance", {}).get("source_artifact_sha256")
        for row in contexts
        if row.get("binding_kind") != "SYNTHETIC_BOUNDARY_PROBE"
    }
    if bound_hashes != {source_document_sha256}:
        raise ValueError("V3 corpus contexts do not bind the supplied source document")

    sense_scope_ids = {row["sense_id"]: row["scope_id"] for row in senses}
    audit_rows, source_registry = audit_contexts(
        contexts, source_document_sha256, source_blocks, sense_scope_ids
    )
    statistical_rows, leakage_rows = build_statistical_units(
        audit_rows, contexts, senses, candidates
    )
    downstream_rows = select_downstream_blocks(
        audit_rows, senses, candidates, source_registry
    )
    validation = _validation_report(
        senses, audit_rows, statistical_rows, leakage_rows, downstream_rows
    )

    output_root.mkdir(parents=True)
    write_text(
        output_root / "methodology_protocol.md",
        protocol_path.read_text(encoding="utf-8"),
    )
    write_csv(output_root / "corpus_origin_audit.csv", AUDIT_FIELDS, audit_rows)
    write_jsonl(output_root / "source_block_registry.jsonl", source_registry)
    write_jsonl(output_root / "statistical_units.jsonl", statistical_rows)
    write_jsonl(output_root / "source_block_split_leakage.jsonl", leakage_rows)
    write_jsonl(output_root / "controlled_vietnamese_source_registry.jsonl", [])
    write_json(output_root / "adversarial_manifest.json", _adversarial_manifest(parent_manifest))
    write_json(output_root / "tac_drift_manifest.json", _tac_manifest(parent_manifest, senses))
    write_jsonl(output_root / "downstream_block_selection.jsonl", downstream_rows)
    write_json(output_root / "validation_report.json", validation)

    split_summary = dict(sorted(Counter(row["split"] for row in senses).items()))
    record_counts = {
        "corpus_origin_audit": len(audit_rows),
        "source_blocks": len(source_registry),
        "statistical_units": len(statistical_rows),
        "source_block_split_leakage": len(leakage_rows),
        "controlled_vietnamese_sources": 0,
        "adversarial_cases": 0,
        "tac_drift_cases": 0,
        "downstream_blocks": len(downstream_rows),
    }
    manifest = seal(
        {
            "parent_dataset_schema_id": parent_manifest["schema_id"],
            "parent_dataset_schema_version": parent_manifest["schema_version"],
            "parent_dataset_manifest_sha256": parent_manifest["manifest_sha256"],
            "parent_dataset_manifest_file_sha256": sha256_file(
                parent_root / "manifest.json"
            ),
            "artifact_schema_id": ARTIFACT_SCHEMA_ID,
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "generation_policy_version": GENERATION_POLICY_VERSION,
            "created_at": CREATED_AT,
            "created_by": "dataset_agent",
            "status": validation["status"],
            "methodology_readiness": validation["methodology_readiness"],
            "record_count": sum(record_counts.values()),
            "record_counts": record_counts,
            "split_summary": split_summary,
            "source_document_sha256": source_document_sha256,
            "source_document_ref": str(source_document).replace("\\", "/"),
            "leakage_audit_ref": "source_block_split_leakage.jsonl",
            "files": file_bindings(
                output_root, {"manifest.json", "CHECKSUMS.sha256"}
            ),
        },
        "artifact_manifest_sha256",
    )
    write_json(output_root / "manifest.json", manifest)
    write_checksums(output_root, output_root / "CHECKSUMS.sha256")
    deterministic_zip(
        output_root, archive_path, "dataset_methodology_hardening_v1"
    )
    archive_sha256 = sha256_file(archive_path)
    write_text(
        Path(str(archive_path) + ".sha256"),
        f"{archive_sha256}  {archive_path.name}",
    )
    return {
        "status": validation["status"],
        "methodology_readiness": validation["methodology_readiness"],
        "artifact_manifest_sha256": manifest["artifact_manifest_sha256"],
        "archive_sha256": archive_sha256,
        "record_counts": record_counts,
        "blocker_count": len(validation["blockers"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", type=Path, required=True)
    parser.add_argument("--source-document", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--archive-path", type=Path, required=True)
    parser.add_argument(
        "--protocol-path",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "methodology_protocol.md",
    )
    args = parser.parse_args()
    result = build_artifact(
        args.parent_root,
        args.source_document,
        args.output_root,
        args.archive_path,
        args.protocol_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
