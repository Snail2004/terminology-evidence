from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .common import (
    POLICY_ID,
    SCHEMA_VERSION,
    conditional_resolution,
    file_bindings,
    pilot_records,
    read_csv,
    read_json,
    seal,
    sha256_file,
    sha256_object,
    source_payload_hash,
    validate_manifest,
    validate_pilot,
    validate_self_hash,
    validate_iso8601,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)


STAGE_A_FILE = "stage_a/sense_contract_review.csv"
STAGE_A_BINDINGS_FILE = "stage_a/source_bindings.json"
STAGE_A_SIGNATURE = [
    "definition_status",
    "effective_definition_en",
    "part_of_speech_status",
    "effective_part_of_speech",
    "scope_note",
]
STAGE_A_OPTIONAL_SIGNATURE = {
    "effective_definition_en",
    "effective_part_of_speech",
    "scope_note",
}


def build_stage_a_rows(
    pilot_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    records = pilot_records(pilot_root)["TERM_SENSE"]
    source_fields = [
        "workflow_policy_id",
        "annotation_unit",
        "term_id",
        "sense_id",
        "split",
        "stratum",
        "source_term",
        "model_definition_en",
        "model_definition_confidence",
        "model_part_of_speech",
        "model_part_of_speech_confidence",
        "definition_evidence_context_ids",
        "part_of_speech_evidence_context_ids",
        "source_record_sha256",
    ]
    rows = []
    bindings = {}
    for sense_id, sense in sorted(records.items()):
        source = {
            "workflow_policy_id": POLICY_ID,
            "annotation_unit": "SENSE_CONTRACT",
            "term_id": sense["term_id"],
            "sense_id": sense_id,
            "split": sense["split"],
            "stratum": sense["stratum"],
            "source_term": sense["source_term"],
            "model_definition_en": sense["definition"],
            "model_definition_confidence": sense["definition_confidence"],
            "model_part_of_speech": sense["part_of_speech"],
            "model_part_of_speech_confidence": sense["part_of_speech_confidence"],
            "definition_evidence_context_ids": "|".join(
                sense.get("definition_evidence_context_ids") or []
            ),
            "part_of_speech_evidence_context_ids": "|".join(
                sense.get("part_of_speech_evidence_context_ids") or []
            ),
            "source_record_sha256": sense["term_sense_sha256"],
        }
        payload_hash = source_payload_hash(source, source_fields)
        row = {
            **source,
            "source_payload_sha256": payload_hash,
            **_human_fields(),
        }
        rows.append(row)
        bindings[sense_id] = {
            "source_payload_sha256": payload_hash,
            "source_record_sha256": sense["term_sense_sha256"],
        }
    binding_file = {
        "schema_id": "D2LCSTStageASourceBindingsV1_4",
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "unit_field": "sense_id",
        "source_fields": source_fields,
        "rows": bindings,
    }
    binding_file["source_bindings_sha256"] = sha256_object(binding_file)
    return rows, binding_file, source_fields


def validate_stage_a(
    workflow_root: Path,
    pilot_root: Path,
    *,
    require_complete: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    manifest, manifest_errors = validate_manifest(
        workflow_root,
        expected_schema="D2LCSTReviewWorkflowV1_4",
        mutable_files_may_differ=True,
    )
    errors.extend(manifest_errors)
    pilot_manifest, pilot_errors = validate_pilot(pilot_root)
    errors.extend(pilot_errors)
    source_pilot = manifest.get("source_pilot", {})
    if source_pilot.get("manifest_sha256") != pilot_manifest.get("manifest_sha256"):
        errors.append("workflow source pilot semantic hash mismatch")
    if source_pilot.get("manifest_file_sha256") != sha256_file(
        pilot_root / "manifest.json"
    ):
        errors.append("workflow source pilot physical hash mismatch")

    contract = read_json(workflow_root / "annotation_contract.json")
    validate_self_hash(contract, "contract_sha256", "annotation contract", errors)
    if contract.get("policy_id") != POLICY_ID:
        errors.append("annotation contract policy mismatch")
    if contract.get("source_pilot_manifest_sha256") != pilot_manifest.get(
        "manifest_sha256"
    ):
        errors.append("annotation contract pilot hash mismatch")
    bindings = read_json(workflow_root / STAGE_A_BINDINGS_FILE)
    validate_self_hash(bindings, "source_bindings_sha256", "stage A bindings", errors)
    if bindings.get("policy_id") != POLICY_ID:
        errors.append("stage A binding policy mismatch")
    stage_a_contract = contract.get("stage_a", {})
    if stage_a_contract.get("filename") != STAGE_A_FILE:
        errors.append("annotation contract Stage A filename mismatch")
    if stage_a_contract.get("source_fields") != bindings.get("source_fields"):
        errors.append("annotation contract Stage A source fields mismatch")
    if stage_a_contract.get("signature_fields") != STAGE_A_SIGNATURE:
        errors.append("annotation contract Stage A signature mismatch")

    rows = read_csv(workflow_root / STAGE_A_FILE)
    if len(rows) != manifest.get("stage_a", {}).get("row_count"):
        errors.append(f"stage A row count differs: {len(rows)}")
    units = [row.get("sense_id", "") for row in rows]
    if len(units) != len(set(units)) or any(not value for value in units):
        errors.append("stage A sense IDs are blank or duplicated")

    source_fields = bindings.get("source_fields", [])
    expected_rows = bindings.get("rows", {})
    pilot_senses = pilot_records(pilot_root)["TERM_SENSE"]
    if set(units) != set(expected_rows) or set(units) != set(pilot_senses):
        errors.append("stage A unit set differs from source bindings or pilot")

    modes = {"AGREEMENT": 0, "MAJORITY": 0, "ADJUDICATED": 0, "PENDING": 0}
    for row_number, row in enumerate(rows, start=2):
        sense_id = row.get("sense_id", "")
        expected = expected_rows.get(sense_id, {})
        computed = source_payload_hash(row, source_fields)
        if row.get("source_payload_sha256") != computed:
            errors.append(f"stage A:{row_number}: source payload was modified")
        if row.get("source_payload_sha256") != expected.get(
            "source_payload_sha256"
        ):
            errors.append(f"stage A:{row_number}: source binding differs")
        pilot_hash = pilot_senses.get(sense_id, {}).get("term_sense_sha256")
        if row.get("source_record_sha256") != pilot_hash:
            errors.append(f"stage A:{row_number}: source record differs from pilot")

        _validate_structured_whitespace(row_number, row, errors)
        _validate_stage_a_values(row_number, row, errors)
        mode, _, resolution_errors = conditional_resolution(
            row,
            STAGE_A_SIGNATURE,
            require_complete=require_complete,
            optional_signature_fields=STAGE_A_OPTIONAL_SIGNATURE,
        )
        errors.extend(f"stage A:{row_number}: {value}" for value in resolution_errors)
        if mode in {"AGREEMENT", "MAJORITY", "ADJUDICATED"}:
            modes[mode] += 1
        else:
            modes["PENDING"] += 1

    return {
        "schema_id": "D2LCSTStageAValidationReportV1_4",
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "mode": "COMPLETE" if require_complete else "PARTIAL_OR_TEMPLATE",
        "row_count": len(rows),
        "resolution_counts": modes,
        "error_count": len(errors),
        "errors": errors,
    }


def finalize_sense_contract(
    workflow_root: Path,
    pilot_root: Path,
    output_root: Path,
    *,
    completed_at: str,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    validate_iso8601(completed_at)
    validation = validate_stage_a(
        workflow_root,
        pilot_root,
        require_complete=True,
    )
    if validation["status"] != "PASS":
        raise ValueError(f"Stage A is incomplete: {validation['errors']}")

    pilot_manifest, pilot_errors = validate_pilot(pilot_root)
    if pilot_errors:
        raise ValueError(f"Pilot validation failed: {pilot_errors}")
    rows = read_csv(workflow_root / STAGE_A_FILE)
    pilot_senses = pilot_records(pilot_root)["TERM_SENSE"]
    records = []
    for row in rows:
        mode, decision, errors = conditional_resolution(
            row,
            STAGE_A_SIGNATURE,
            require_complete=True,
            optional_signature_fields=STAGE_A_OPTIONAL_SIGNATURE,
        )
        if errors or decision is None:
            raise ValueError(f"Stage A resolution failed for {row['sense_id']}: {errors}")
        definition_status = decision["definition_status"]
        pos_status = decision["part_of_speech_status"]
        if definition_status == "REJECTED":
            raise ValueError(f"Rejected definition blocks sense contract: {row['sense_id']}")
        if pos_status in {"REJECTED", "UNCERTAIN"}:
            raise ValueError(f"Unresolved POS blocks sense contract: {row['sense_id']}")
        record = {
            "schema_id": "D2LReviewedSenseContractRecordV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "term_id": row["term_id"],
            "sense_id": row["sense_id"],
            "source_term": row["source_term"],
            "scope_id": pilot_senses[row["sense_id"]]["scope_id"],
            "effective_definition_en": decision["effective_definition_en"],
            "effective_part_of_speech": decision["effective_part_of_speech"],
            "scope_note": decision["scope_note"],
            "definition_source": (
                "MODEL_ACCEPTED"
                if definition_status == "ACCEPTED"
                else "HUMAN_CORRECTED"
            ),
            "part_of_speech_source": (
                "MODEL_ACCEPTED" if pos_status == "ACCEPTED" else "HUMAN_CORRECTED"
            ),
            "resolution_mode": mode,
            "review_status": {
                "AGREEMENT": "AGREED",
                "MAJORITY": "MAJORITY_2_OF_3",
                "ADJUDICATED": "ADJUDICATED",
            }[mode],
            "review_provenance": {
                "reviewer_1_id": row["reviewer_1_id"],
                "reviewer_1_reviewed_at": row["reviewer_1_reviewed_at"],
                "reviewer_2_id": row["reviewer_2_id"],
                "reviewer_2_reviewed_at": row["reviewer_2_reviewed_at"],
                "reviewer_3_id": row["reviewer_3_id"],
                "reviewer_3_reviewed_at": row["reviewer_3_reviewed_at"],
                "adjudicator_id": row["adjudicator_id"],
                "adjudicated_at": row["adjudicated_at"],
                "source_stage_a_row_sha256": sha256_object(row),
            },
            "source_term_sense_sha256": row["source_record_sha256"],
            "completed_at": completed_at,
        }
        records.append(seal(record, "reviewed_sense_contract_sha256"))

    output_root.mkdir(parents=True)
    write_jsonl(output_root / "reviewed_sense_contract.jsonl", records)
    shutil.copyfile(
        workflow_root / STAGE_A_FILE,
        output_root / "sense_contract_review.csv",
    )
    write_json(output_root / "final_validation_report.json", validation)
    write_text(
        output_root / "README.md",
        "# Pilot reviewed sense contract v1\n\n"
        "This immutable artifact is the only definition/POS authority for Stage B.\n",
    )
    manifest = {
        "schema_id": "D2LReviewedSenseContractV1",
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "status": "COMPLETE",
        "completed_at": completed_at,
        "source_pilot": {
            "manifest_sha256": pilot_manifest["manifest_sha256"],
            "manifest_file_sha256": sha256_file(pilot_root / "manifest.json"),
        },
        "source_review_workflow": {
            "manifest_sha256": read_json(workflow_root / "manifest.json")[
                "manifest_sha256"
            ],
            "stage_a_csv_sha256": sha256_file(workflow_root / STAGE_A_FILE),
        },
        "sense_count": len(records),
        "resolution_counts": validation["resolution_counts"],
    }
    manifest["files"] = file_bindings(output_root)
    manifest = seal(manifest, "manifest_sha256")
    write_json(output_root / "manifest.json", manifest)
    return {
        "root": output_root.as_posix(),
        "manifest_sha256": manifest["manifest_sha256"],
        "manifest_file_sha256": sha256_file(output_root / "manifest.json"),
        "sense_count": len(records),
        "resolution_counts": validation["resolution_counts"],
    }


def _validate_stage_a_values(
    row_number: int,
    row: dict[str, str],
    errors: list[str],
) -> None:
    for prefix in ("reviewer_1", "reviewer_2", "reviewer_3", "adjudicated"):
        status_field = (
            "adjudication_status" if prefix == "adjudicated" else f"{prefix}_status"
        )
        active = bool(row.get(status_field))
        definition_status = row.get(f"{prefix}_definition_status", "")
        definition = row.get(f"{prefix}_effective_definition_en", "")
        pos_status = row.get(f"{prefix}_part_of_speech_status", "")
        pos = row.get(f"{prefix}_effective_part_of_speech", "")
        if definition_status and definition_status not in {
            "ACCEPTED",
            "CORRECTED",
            "REJECTED",
        }:
            errors.append(f"stage A:{row_number}: invalid {prefix} definition status")
        if pos_status and pos_status not in {
            "ACCEPTED",
            "CORRECTED",
            "UNCERTAIN",
            "REJECTED",
        }:
            errors.append(f"stage A:{row_number}: invalid {prefix} POS status")
        if active:
            if definition_status == "ACCEPTED" and definition != row["model_definition_en"]:
                errors.append(f"stage A:{row_number}: accepted definition must equal model")
            if definition_status == "CORRECTED" and not definition.strip():
                errors.append(f"stage A:{row_number}: corrected definition is blank")
            if definition_status == "REJECTED" and definition:
                errors.append(f"stage A:{row_number}: rejected definition must be blank")
            if pos_status == "ACCEPTED" and pos != row["model_part_of_speech"]:
                errors.append(f"stage A:{row_number}: accepted POS must equal model")
            if pos_status == "CORRECTED" and not pos.strip():
                errors.append(f"stage A:{row_number}: corrected POS is blank")
            if pos_status in {"UNCERTAIN", "REJECTED"} and pos:
                errors.append(f"stage A:{row_number}: unresolved POS must be blank")


def _validate_structured_whitespace(
    row_number: int,
    row: dict[str, str],
    errors: list[str],
) -> None:
    for key, value in row.items():
        if not key.startswith(("reviewer_", "adjudicat")) or not value:
            continue
        if key.endswith(("_id", "_status", "_reviewed_at", "adjudicated_at")):
            if value != value.strip():
                errors.append(f"stage A:{row_number}: whitespace in {key}")


def _human_fields() -> dict[str, str]:
    fields = {}
    for prefix in ("reviewer_1", "reviewer_2", "reviewer_3"):
        fields.update(
            {
                f"{prefix}_id": "",
                f"{prefix}_status": "",
                f"{prefix}_definition_status": "",
                f"{prefix}_effective_definition_en": "",
                f"{prefix}_part_of_speech_status": "",
                f"{prefix}_effective_part_of_speech": "",
                f"{prefix}_scope_note": "",
                f"{prefix}_reviewed_at": "",
                f"{prefix}_notes": "",
            }
        )
    fields.update(
        {
            "adjudicator_id": "",
            "adjudication_status": "",
            "adjudicated_definition_status": "",
            "adjudicated_effective_definition_en": "",
            "adjudicated_part_of_speech_status": "",
            "adjudicated_effective_part_of_speech": "",
            "adjudicated_scope_note": "",
            "adjudicated_at": "",
            "adjudication_notes": "",
        }
    )
    return fields
