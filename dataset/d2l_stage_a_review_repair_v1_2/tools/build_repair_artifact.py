from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from blind_audit import build_blind_pack, select_blind_cases
from common import (
    deterministic_zip,
    file_bindings,
    read_csv,
    read_json,
    read_jsonl,
    seal,
    sha256_file,
    sha256_object,
    write_checksums,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)
from consensus import SEMANTIC_DIRECTIVES, resolve_evidence_aware_consensus
from evidence import load_v3_context_authority, project_legacy_evidence_roles
from policy import (
    CONSENSUS_POLICY_PATH,
    POLICY_DOCUMENT_PATH,
    REVIEW_SCHEMA_PATH,
    policy_bindings,
)
from provenance import pending_provenance_template, validate_provenance_group


AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
AUTHORITY_MANIFEST_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
REVIEW_PACKAGE_SHA256 = "9eafa7afc797c8b4bcc249304dc2683bee7d996b96e31a6942399e949af1fc30"
BATCH_IDS = tuple(f"development_{index:03d}" for index in range(1, 5))


def _load_legacy_validator(repository_root: Path):
    tools = repository_root / "dataset" / "d2l_stage_a_review_batches_v1" / "tools"
    sys.path.insert(0, str(tools))
    try:
        from review_workflow import validate_review
    finally:
        sys.path.remove(str(tools))
    return validate_review


def _verify_authority(repository_root: Path) -> dict[str, Any]:
    tag_commit = subprocess.check_output(
        ["git", "rev-parse", f"refs/tags/{AUTHORITY_TAG}^{{commit}}"],
        cwd=repository_root,
        text=True,
    ).strip()
    if tag_commit != AUTHORITY_COMMIT:
        raise ValueError("Terminology authority tag resolves to an unexpected commit")
    manifest = read_json(repository_root / "terminology_contracts_v1" / "manifest.json")
    if (manifest.get("integrity") or {}).get("manifest_sha256") != AUTHORITY_MANIFEST_SHA256:
        raise ValueError("Terminology authority manifest identity mismatch")
    return {
        "contract_version": "1.1.0",
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "package_path": "terminology_contracts_v1/",
        "manifest_sha256": AUTHORITY_MANIFEST_SHA256,
        "manifest_file_sha256": sha256_file(
            repository_root / "terminology_contracts_v1" / "manifest.json"
        ),
        "final_glossary_decision": None,
    }


def _source_bundle_sha256(batch_root: Path) -> str:
    names = (
        "batch_manifest.json",
        "REVIEW_INSTRUCTIONS_CSV.md",
        "sense_review_cases.jsonl",
        "sense_review_cases.csv",
        "sense_review_contexts.csv",
    )
    return sha256_object({name: sha256_file(batch_root / name) for name in names})


def _load_reviews(path: Path) -> dict[str, dict[str, str]]:
    return {row["sense_id"]: row for row in read_csv(path)}


def _template_fields() -> list[str]:
    return [
        "schema_id",
        "policy_id",
        "case_sha256",
        "source_payload_sha256",
        "term_id",
        "sense_id",
        "definition_status",
        "effective_definition_en",
        "part_of_speech_status",
        "effective_part_of_speech",
        "positive_definition_evidence_ids",
        "positive_pos_evidence_ids",
        "boundary_context_ids",
        "scope_note",
        "confidence",
        "rationale",
        "risk_flags",
    ]


def _generator_bindings(repository_root: Path, package_root: Path) -> dict[str, Any]:
    paths = sorted((package_root / "tools").glob("*.py"))
    return {
        path.relative_to(repository_root).as_posix(): {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in paths
    }


def build_repair_artifact(repository_root: Path, output_root: Path) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    repository_root = repository_root.resolve()
    authority = _verify_authority(repository_root)
    package_root = Path(__file__).resolve().parents[1]
    batches_root = repository_root / "dataset" / "d2l_stage_a_review_batches_v1" / "release" / "batches"
    dataset_root = repository_root / "dataset" / "d2l_context_support_set_validation_ready_v3"
    hardening_root = repository_root / "dataset" / "dataset_methodology_hardening_v1"
    dataset_manifest, context_authority = load_v3_context_authority(dataset_root)
    hardening_manifest = read_json(hardening_root / "release" / "manifest.json")
    validate_legacy = _load_legacy_validator(repository_root)

    output_root.mkdir(parents=True)
    for source in (POLICY_DOCUMENT_PATH, REVIEW_SCHEMA_PATH, CONSENSUS_POLICY_PATH):
        shutil.copyfile(source, output_root / source.name)
    write_csv(output_root / "review_record_template_v1_2.csv", _template_fields(), [])

    all_cases: list[dict[str, Any]] = []
    all_consensus: list[dict[str, Any]] = []
    all_provenance: list[dict[str, Any]] = []
    source_review_bindings: list[dict[str, Any]] = []
    evidence_projection_count = 0
    provenance_batch_reports: dict[str, Any] = {}

    for batch_id in BATCH_IDS:
        batch_root = batches_root / batch_id
        cases = read_jsonl(batch_root / "sense_review_cases.jsonl")
        case_by_id = {str(case["sense_id"]): case for case in cases}
        all_cases.extend(cases)
        review_paths = [batch_root / "result" / f"human_{slot}.csv" for slot in (1, 2, 3)]
        for path in review_paths:
            if not path.is_file():
                raise FileNotFoundError(f"Missing returned review file: {path}")
            report = validate_legacy(batch_root, path, True)
            if report["status"] != "PASS":
                raise ValueError(json.dumps(report, ensure_ascii=False))
        source_bundle_sha256 = _source_bundle_sha256(batch_root)
        instruction_sha256 = sha256_file(batch_root / "REVIEW_INSTRUCTIONS_CSV.md")
        sidecars = []
        review_maps = []
        evidence_maps = []
        for slot, review_path in enumerate(review_paths, start=1):
            relative = review_path.relative_to(repository_root).as_posix()
            source_review_bindings.append(
                {
                    "batch_id": batch_id,
                    "reviewer_slot": slot,
                    "ref": relative,
                    "sha256": sha256_file(review_path),
                    "size_bytes": review_path.stat().st_size,
                }
            )
            sidecar = pending_provenance_template(
                review_path=review_path,
                reviewer_output_ref=relative,
                reviewer_slot=slot,
                batch_id=batch_id,
                source_bundle_sha256=source_bundle_sha256,
                instruction_sha256=instruction_sha256,
            )
            sidecars.append(sidecar)
            all_provenance.append(sidecar)
            write_json(
                output_root / "reviewer_provenance" / batch_id / f"reviewer_{slot}.json",
                sidecar,
            )
            review_map = _load_reviews(review_path)
            review_maps.append(review_map)
            evidence_map = {}
            projections = []
            for sense_id, row in sorted(review_map.items()):
                projection = project_legacy_evidence_roles(
                    case=case_by_id[sense_id],
                    review_row=row,
                    context_authority=context_authority,
                    reviewer_slot=slot,
                )
                projection = seal(projection, "record_sha256")
                projections.append(projection)
                evidence_map[sense_id] = projection
            evidence_projection_count += len(projections)
            evidence_maps.append(evidence_map)
            write_jsonl(
                output_root / "evidence_validation_sidecars" / batch_id / f"reviewer_{slot}.jsonl",
                projections,
            )
        provenance_report = validate_provenance_group(sidecars, review_paths)
        provenance_batch_reports[batch_id] = provenance_report
        for case in cases:
            sense_id = str(case["sense_id"])
            consensus = resolve_evidence_aware_consensus(
                term=str(case["source_term"]),
                term_id=str(case["term_id"]),
                sense_id=sense_id,
                case_sha256=str(case["case_sha256"]),
                decisions=[review_map[sense_id] for review_map in review_maps],
                evidence_reports=[evidence_map[sense_id] for evidence_map in evidence_maps],
                provenance_status=provenance_report["status"],
            )
            all_consensus.append(consensus)

    write_json(
        output_root / "source_review_bindings.json",
        seal(
            {
                "schema_id": "D2LCSTSourceReviewBindingsV1",
                "source_review_package_sha256": REVIEW_PACKAGE_SHA256,
                "review_file_count": len(source_review_bindings),
                "files": source_review_bindings,
            },
            "bindings_sha256",
        ),
    )
    write_jsonl(output_root / "recomputed_consensus_records_v2.jsonl", all_consensus)
    consensus_rows = [
        {
            "source_term": row["source_term"],
            "sense_id": row["sense_id"],
            "agreement": row["agreement"],
            "finalization_status": row["finalization_status"],
            "blocker_codes": ";".join(row["blocker_codes"]),
            "semantic_directive": (
                (row.get("semantic_directive") or {}).get("directive", "")
            ),
            "record_sha256": row["record_sha256"],
        }
        for row in all_consensus
    ]
    write_csv(
        output_root / "recomputed_consensus_audit_v2.csv",
        [
            "source_term",
            "sense_id",
            "agreement",
            "finalization_status",
            "blocker_codes",
            "semantic_directive",
            "record_sha256",
        ],
        consensus_rows,
    )
    adjudication_rows = [
        seal(
            {
                "schema_id": "D2LCSTStageAAdjudicationDirectiveV1",
                "policy_id": "d2l_cst_stage_a_evidence_aware_consensus_v1_2",
                "source_term": row["source_term"],
                "term_id": row["term_id"],
                "sense_id": row["sense_id"],
                "case_sha256": row["case_sha256"],
                "directive": row["semantic_directive"],
                "status": "PENDING_ADJUDICATOR_ATTESTATION",
                "adjudicator_id": None,
                "adjudicated_at": None,
                "final_glossary_decision": None,
            },
            "record_sha256",
        )
        for row in all_consensus
        if row.get("source_term") in SEMANTIC_DIRECTIVES
    ]
    write_jsonl(output_root / "adjudication_batch_001_004.jsonl", adjudication_rows)

    selected = select_blind_cases(all_cases, all_consensus)
    blind_root = output_root / "blind_audit_pack_development_v1"
    blind_manifest = build_blind_pack(
        output_root=blind_root,
        selected=selected,
        context_authority=context_authority,
    )
    blind_zip = output_root / "blind_audit_pack_development_v1.zip"
    deterministic_zip(blind_root, blind_zip)
    write_text(
        output_root / "blind_audit_pack_development_v1.zip.sha256",
        f"{sha256_file(blind_zip)}  {blind_zip.name}",
    )
    anchor_rows = [
        seal(
            {
                "schema_id": "D2LCSTBlindAuditAnchorReferenceV1",
                "policy_id": "d2l_cst_stage_a_blind_paired_audit_development_v1",
                "sense_id": case["sense_id"],
                "source_term": case["source_term"],
                "selection_stratum": stratum,
                "anchored_consensus_record_sha256": next(
                    row["record_sha256"]
                    for row in all_consensus
                    if row["sense_id"] == case["sense_id"]
                ),
                "comparison_status": "PENDING_BLIND_REVIEW",
            },
            "record_sha256",
        )
        for stratum, case in selected
    ]
    write_jsonl(output_root / "blind_audit_anchor_reference.jsonl", anchor_rows)

    resolution_counts = Counter(row["agreement"] for row in all_consensus)
    finalization_counts = Counter(row["finalization_status"] for row in all_consensus)
    report = seal(
        {
            "schema_id": "D2LCSTStageARepairValidationReportV1",
            "policy_id": "d2l_cst_stage_a_evidence_aware_review_v1_2",
            "structural_status": "PASS",
            "readiness_status": "BLOCKED_PENDING_PROVENANCE_ADJUDICATION_AND_BLIND_AUDIT",
            "definition_of_done": False,
            "review_batch_count": len(BATCH_IDS),
            "sense_count": len(all_consensus),
            "review_file_count": len(source_review_bindings),
            "evidence_projection_count": evidence_projection_count,
            "provenance_sidecar_count": len(all_provenance),
            "provenance_complete_count": sum(
                1 for row in all_provenance if row.get("status") == "COMPLETE"
            ),
            "agreement_counts": dict(sorted(resolution_counts.items())),
            "finalization_counts": dict(sorted(finalization_counts.items())),
            "adjudication_case_count": len(adjudication_rows),
            "blind_audit_sense_count": blind_manifest["sense_count"],
            "completed_controls": {
                "v1_sources_preserved": True,
                "v1_2_policy_versioned": True,
                "positive_boundary_fields_separated": True,
                "synthetic_positive_rejected_by_validator": True,
                "majority_auto_finalization_disabled": True,
                "blind_pack_development_only": True,
                "authority_v1_1_bound": True,
            },
            "remaining_blockers": [
                "12 reviewer provenance sidecars require truthful owner attestation",
                "legacy evidence-role projections require reviewer confirmation",
                "three semantic directives require adjudicator attestation or split construction",
                "13-sense blind audit has not been annotated",
                "45 cross-split source-block clusters remain a methodology blocker",
                "controlled Vietnamese, adversarial, and TAC drift inputs remain absent",
            ],
            "provenance_batch_reports": provenance_batch_reports,
            "final_glossary_decision": None,
        },
        "report_sha256",
    )
    write_json(output_root / "repair_validation_report.json", report)

    manifest = seal(
        {
            "schema_id": "D2LCSTStageAReviewRepairArtifactV1",
            "artifact_version": "1.2.0",
            "status": report["readiness_status"],
            "authority": authority,
            "dataset": {
                "schema_id": dataset_manifest["schema_id"],
                "dataset_version": dataset_manifest["dataset_version"],
                "manifest_sha256": dataset_manifest["manifest_sha256"],
                "manifest_file_sha256": sha256_file(dataset_root / "manifest.json"),
            },
            "methodology_hardening": {
                "manifest_sha256": hardening_manifest["artifact_manifest_sha256"],
                "manifest_file_sha256": sha256_file(hardening_root / "release" / "manifest.json"),
                "zip_sha256": sha256_file(hardening_root / "dataset_methodology_hardening_v1.zip"),
            },
            "source_review_package_sha256": REVIEW_PACKAGE_SHA256,
            "policy_bindings": policy_bindings(),
            "generator_bindings": _generator_bindings(repository_root, package_root),
            "sense_count": len(all_consensus),
            "review_file_count": len(source_review_bindings),
            "blind_audit_sense_count": blind_manifest["sense_count"],
            "files": file_bindings(
                output_root,
                excluded={"manifest.json", "CHECKSUMS.sha256"},
            ),
            "final_glossary_decision": None,
        },
        "manifest_sha256",
    )
    write_json(output_root / "manifest.json", manifest)
    write_checksums(output_root, output_root / "CHECKSUMS.sha256")
    outer_zip = (
        output_root.parent / "d2l_stage_a_review_repair_v1_2.zip"
        if output_root.name == "release"
        else output_root.with_suffix(".zip")
    )
    deterministic_zip(output_root, outer_zip)
    write_text(
        outer_zip.with_suffix(".zip.sha256"),
        f"{sha256_file(outer_zip)}  {outer_zip.name}",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_repair_artifact(args.repository_root, args.output_root)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "sense_count": manifest["sense_count"],
                "review_file_count": manifest["review_file_count"],
                "manifest_sha256": manifest["manifest_sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
