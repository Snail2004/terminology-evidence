from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from .common import (
    POLICY_ID,
    agreement_summary,
    conditional_resolution,
    file_bindings,
    read_csv,
    read_json,
    read_jsonl,
    seal,
    sha256_file,
    validate_manifest,
    validate_pilot,
    validate_iso8601,
    write_json,
    write_text,
)
from .stage_a import STAGE_A_FILE, STAGE_A_OPTIONAL_SIGNATURE, STAGE_A_SIGNATURE
from .stage_b import OPTIONAL_SIGNATURES, SIGNATURES, TABLES, validate_stage_b


def finalize_annotations(
    workflow_root: Path,
    pilot_root: Path,
    sense_contract_root: Path,
    stage_b_root: Path,
    output_root: Path,
    *,
    completed_at: str,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    validate_iso8601(completed_at)
    pilot_manifest, pilot_errors = validate_pilot(pilot_root)
    if pilot_errors:
        raise ValueError(f"Pilot validation failed: {pilot_errors}")
    workflow_manifest, workflow_errors = validate_manifest(
        workflow_root,
        expected_schema="D2LCSTReviewWorkflowV1_4",
        mutable_files_may_differ=True,
    )
    if workflow_errors:
        raise ValueError(f"Workflow validation failed: {workflow_errors}")
    sense_manifest, sense_errors = validate_manifest(
        sense_contract_root,
        expected_schema="D2LReviewedSenseContractV1",
    )
    if sense_errors:
        raise ValueError(f"Sense contract validation failed: {sense_errors}")
    if sense_manifest.get("source_pilot", {}).get(
        "manifest_sha256"
    ) != pilot_manifest.get("manifest_sha256"):
        raise ValueError("Sense contract source pilot binding mismatch")
    if sense_manifest.get("source_review_workflow", {}).get(
        "manifest_sha256"
    ) != workflow_manifest.get("manifest_sha256"):
        raise ValueError("Sense contract source workflow binding mismatch")
    if sense_manifest.get("source_review_workflow", {}).get(
        "stage_a_csv_sha256"
    ) != sha256_file(workflow_root / STAGE_A_FILE):
        raise ValueError("Sense contract Stage A source hash mismatch")
    stage_b_manifest, stage_b_errors = validate_manifest(
        stage_b_root,
        expected_schema="D2LCSTStageBAnnotationPackV1",
        mutable_files_may_differ=True,
    )
    if stage_b_errors:
        raise ValueError(f"Stage B package validation failed: {stage_b_errors}")
    validation = validate_stage_b(
        stage_b_root,
        pilot_root,
        sense_contract_root,
        require_complete=True,
    )
    if validation["status"] != "PASS":
        raise ValueError(f"Stage B annotation is incomplete: {validation['errors']}")

    stage_a_rows = read_csv(sense_contract_root / "sense_contract_review.csv")
    rows_by_table = {
        "stage_a": stage_a_rows,
        **{
            table: read_csv(stage_b_root / filename)
            for table, (filename, _, _) in TABLES.items()
        },
    }
    signatures = {"stage_a": STAGE_A_SIGNATURE, **SIGNATURES}
    summary = agreement_summary(
        rows_by_table,
        signatures,
        {"stage_a": STAGE_A_OPTIONAL_SIGNATURE, **OPTIONAL_SIGNATURES},
    )
    summary["candidate_effective_relation_counts"] = _candidate_relation_counts(
        rows_by_table["candidate"]
    )
    summary["completed_at"] = completed_at

    output_root.mkdir(parents=True)
    (output_root / "stage_a").mkdir()
    (output_root / "stage_b").mkdir()
    shutil.copyfile(
        sense_contract_root / "sense_contract_review.csv",
        output_root / "stage_a" / "sense_contract_review.csv",
    )
    shutil.copyfile(
        sense_contract_root / "reviewed_sense_contract.jsonl",
        output_root / "stage_a" / "reviewed_sense_contract.jsonl",
    )
    for _, (filename, _, _) in TABLES.items():
        shutil.copyfile(stage_b_root / filename, output_root / "stage_b" / filename)
    shutil.copyfile(
        workflow_root / "annotation_contract.json",
        output_root / "stage_a" / "annotation_contract.json",
    )
    shutil.copyfile(
        stage_b_root / "stage_b_contract.json",
        output_root / "stage_b" / "stage_b_contract.json",
    )
    write_json(output_root / "final_validation_report.json", validation)
    write_json(output_root / "agreement_adjudication_summary.json", summary)
    write_text(
        output_root / "README.md",
        "# D2L pilot human annotations v1\n\n"
        "This directory is immutable. It contains the reviewed sense contract, "
        "completed Stage B annotations, final validation, and agreement evidence.\n",
    )

    validator_files = sorted(
        path
        for path in (workflow_root / "tools" / "review_workflow_v1_4").glob("*.py")
        if path.is_file()
    )
    annotation_manifest = {
        "schema_id": "D2LPilotHumanAnnotationsV1",
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "status": "COMPLETE_IMMUTABLE",
        "completed_at": completed_at,
        "source_pilot": {
            "manifest_sha256": pilot_manifest["manifest_sha256"],
            "manifest_file_sha256": sha256_file(pilot_root / "manifest.json"),
        },
        "source_workflow": {
            "manifest_sha256": workflow_manifest["manifest_sha256"],
            "stage_a_csv_sha256": sha256_file(workflow_root / STAGE_A_FILE),
        },
        "source_sense_contract": {
            "manifest_sha256": sense_manifest["manifest_sha256"],
            "manifest_file_sha256": sha256_file(
                sense_contract_root / "manifest.json"
            ),
        },
        "source_stage_b": {
            "manifest_sha256": stage_b_manifest["manifest_sha256"],
            "manifest_file_sha256": sha256_file(stage_b_root / "manifest.json"),
        },
        "input_csv_hashes": {
            "stage_a": sha256_file(
                sense_contract_root / "sense_contract_review.csv"
            ),
            **{
                table: sha256_file(stage_b_root / filename)
                for table, (filename, _, _) in TABLES.items()
            },
        },
        "validator_hashes": {
            path.name: sha256_file(path) for path in validator_files
        },
        "contract_hashes": {
            "stage_a": sha256_file(workflow_root / "annotation_contract.json"),
            "stage_b": sha256_file(stage_b_root / "stage_b_contract.json"),
        },
        "row_counts": validation["row_counts"],
        "agreement_adjudication": summary,
    }
    annotation_manifest["files"] = file_bindings(output_root)
    annotation_manifest = seal(
        annotation_manifest,
        "annotation_manifest_sha256",
    )
    write_json(output_root / "annotation_manifest.json", annotation_manifest)
    return {
        "root": output_root.as_posix(),
        "annotation_manifest_sha256": annotation_manifest[
            "annotation_manifest_sha256"
        ],
        "annotation_manifest_file_sha256": sha256_file(
            output_root / "annotation_manifest.json"
        ),
        "agreement_adjudication": summary,
    }


def _candidate_relation_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter()
    for row in rows:
        _, decision, errors = conditional_resolution(
            row,
            SIGNATURES["candidate"],
            require_complete=True,
            optional_signature_fields=OPTIONAL_SIGNATURES["candidate"],
        )
        if errors or decision is None:
            raise ValueError(f"Candidate resolution failed: {errors}")
        counts[decision["candidate_relation"]] += 1
    return dict(sorted(counts.items()))
