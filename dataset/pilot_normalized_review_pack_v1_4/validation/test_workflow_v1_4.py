from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

from support_set_v3.review_workflow_v1_4.builder import (
    build_review_workflow_v1_4,
)
from support_set_v3.review_workflow_v1_4.finalize import finalize_annotations
from support_set_v3.review_workflow_v1_4.stage_a import (
    STAGE_A_FILE,
    finalize_sense_contract,
    validate_stage_a,
)
from support_set_v3.review_workflow_v1_4.stage_b import (
    TABLES,
    generate_stage_b,
    validate_stage_b,
)


PILOT_ROOT = Path(r"E:\Data-KL\pilot_dev_only_v1_1")
PREVIOUS_REVIEW_ROOT = Path(r"E:\Data-KL\pilot_normalized_review_pack_v1_2")
REVIEWER_1_AT = "2026-07-28T08:00:00+07:00"
REVIEWER_2_AT = "2026-07-28T08:05:00+07:00"
ADJUDICATED_AT = "2026-07-28T08:10:00+07:00"
COMPLETED_AT = "2026-07-28T08:15:00+07:00"


@pytest.fixture(scope="session")
def workflow_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not PILOT_ROOT.is_dir() or not PREVIOUS_REVIEW_ROOT.is_dir():
        pytest.skip("Accepted pilot/review artifacts are unavailable")
    root = tmp_path_factory.mktemp("workflow-template") / "review_v1_3"
    build_review_workflow_v1_4(
        PILOT_ROOT,
        Path(r"E:\Data-KL\pilot_normalized_review_pack_v1_3"),
        root,
    )
    return root


@pytest.fixture()
def workflow(workflow_template: Path, tmp_path: Path) -> Path:
    target = tmp_path / "workflow"
    shutil.copytree(workflow_template, target)
    return target


@pytest.fixture()
def completed_pipeline(workflow: Path, tmp_path: Path) -> dict[str, Path]:
    corrected_sense = _complete_stage_a(workflow)
    sense_contract = tmp_path / "sense-contract"
    finalize_sense_contract(
        workflow,
        PILOT_ROOT,
        sense_contract,
        completed_at=COMPLETED_AT,
    )
    stage_b = tmp_path / "stage-b"
    generate_stage_b(PILOT_ROOT, sense_contract, stage_b)
    _complete_stage_b(stage_b)
    return {
        "workflow": workflow,
        "sense_contract": sense_contract,
        "stage_b": stage_b,
        "corrected_sense": Path(corrected_sense),
    }


def test_blank_stage_a_is_valid_template_but_not_complete(workflow: Path) -> None:
    assert validate_stage_a(workflow, PILOT_ROOT)["status"] == "PASS"
    report = validate_stage_a(workflow, PILOT_ROOT, require_complete=True)
    assert report["status"] == "FAIL"
    assert any("reviewer_1 is incomplete" in error for error in report["errors"])


def test_agreement_needs_no_adjudication_and_disagreement_does(
    workflow: Path,
) -> None:
    corrected_sense = _complete_stage_a(workflow, adjudicate=False)
    report = validate_stage_a(workflow, PILOT_ROOT, require_complete=True)
    assert report["status"] == "FAIL"
    assert any("disagreement requires adjudication" in error for error in report["errors"])

    fields, rows = _read_csv(workflow / STAGE_A_FILE)
    row = next(item for item in rows if item["sense_id"] == corrected_sense)
    _adjudicate_stage_a_row(row)
    _write_csv(workflow / STAGE_A_FILE, fields, rows)
    report = validate_stage_a(workflow, PILOT_ROOT, require_complete=True)
    assert report["status"] == "PASS"
    assert report["resolution_counts"] == {
        "AGREEMENT": 4,
        "MAJORITY": 0,
        "ADJUDICATED": 1,
        "PENDING": 0,
    }


def test_adjudicator_must_be_distinct_and_later(workflow: Path) -> None:
    corrected_sense = _complete_stage_a(workflow)
    fields, rows = _read_csv(workflow / STAGE_A_FILE)
    row = next(item for item in rows if item["sense_id"] == corrected_sense)
    row["adjudicator_id"] = row["reviewer_1_id"]
    row["adjudicated_at"] = "2026-07-28T07:00:00+07:00"
    _write_csv(workflow / STAGE_A_FILE, fields, rows)
    errors = validate_stage_a(
        workflow,
        PILOT_ROOT,
        require_complete=True,
    )["errors"]
    assert any("adjudicator must be distinct" in error for error in errors)
    assert any("timestamp precedes" in error for error in errors)


def test_exact_two_of_three_majority_needs_no_adjudication(
    workflow: Path,
) -> None:
    corrected_sense = _complete_stage_a(workflow, adjudicate=False)
    fields, rows = _read_csv(workflow / STAGE_A_FILE)
    row = next(item for item in rows if item["sense_id"] == corrected_sense)
    row["reviewer_3_definition_status"] = row["reviewer_2_definition_status"]
    row["reviewer_3_effective_definition_en"] = row[
        "reviewer_2_effective_definition_en"
    ]
    _write_csv(workflow / STAGE_A_FILE, fields, rows)
    report = validate_stage_a(workflow, PILOT_ROOT, require_complete=True)
    assert report["status"] == "PASS"
    assert report["resolution_counts"] == {
        "AGREEMENT": 4,
        "MAJORITY": 1,
        "ADJUDICATED": 0,
        "PENDING": 0,
    }


def test_stage_a_source_tamper_is_detected(workflow: Path) -> None:
    fields, rows = _read_csv(workflow / STAGE_A_FILE)
    rows[0]["model_definition_en"] = "tampered"
    _write_csv(workflow / STAGE_A_FILE, fields, rows)
    report = validate_stage_a(workflow, PILOT_ROOT)
    assert report["status"] == "FAIL"
    assert any("source payload was modified" in error for error in report["errors"])


def test_corrected_definition_and_pos_contract_flow_into_stage_b(
    completed_pipeline: dict[str, Path],
) -> None:
    sense_id = str(completed_pipeline["corrected_sense"])
    records = _read_jsonl(
        completed_pipeline["sense_contract"] / "reviewed_sense_contract.jsonl"
    )
    effective = next(row for row in records if row["sense_id"] == sense_id)
    assert effective["effective_definition_en"].startswith("Human-reviewed definition")
    assert effective["definition_source"] == "HUMAN_CORRECTED"

    for filename, _, _ in TABLES.values():
        _, rows = _read_csv(completed_pipeline["stage_b"] / filename)
        matching = [row for row in rows if row["sense_id"] == sense_id]
        assert matching
        assert {
            row["effective_definition_en"] for row in matching
        } == {effective["effective_definition_en"]}
        assert {
            row["effective_part_of_speech"] for row in matching
        } == {effective["effective_part_of_speech"]}


def test_stage_b_complete_and_group_ranking_policy(
    completed_pipeline: dict[str, Path],
) -> None:
    report = validate_stage_b(
        completed_pipeline["stage_b"],
        PILOT_ROOT,
        completed_pipeline["sense_contract"],
        require_complete=True,
    )
    assert report["status"] == "PASS"
    assert report["row_counts"] == {
        "contrastive": 5,
        "context": 33,
        "candidate": 15,
    }

    path = completed_pipeline["stage_b"] / TABLES["candidate"][0]
    fields, rows = _read_csv(path)
    variant = next(
        row
        for row in rows
        if row["reviewer_1_candidate_relation"] == "MORPHOLOGICAL_VARIANT"
    )
    variant["reviewer_1_candidate_rank"] = "3"
    variant["reviewer_2_candidate_rank"] = "3"
    _write_csv(path, fields, rows)
    errors = validate_stage_b(
        completed_pipeline["stage_b"],
        PILOT_ROOT,
        completed_pipeline["sense_contract"],
        require_complete=True,
    )["errors"]
    assert any("variant/duplicate rank must be blank" in error for error in errors)


def test_invalid_context_can_leave_type_blank(
    completed_pipeline: dict[str, Path],
) -> None:
    path = completed_pipeline["stage_b"] / TABLES["context"][0]
    fields, rows = _read_csv(path)
    row = rows[0]
    for prefix in ("reviewer_1", "reviewer_2"):
        row[f"{prefix}_same_sense_label"] = "NOT_SAME_SENSE"
        row[f"{prefix}_context_validity"] = "INVALID"
        row[f"{prefix}_context_type"] = ""
    _write_csv(path, fields, rows)
    report = validate_stage_b(
        completed_pipeline["stage_b"],
        PILOT_ROOT,
        completed_pipeline["sense_contract"],
        require_complete=True,
    )
    assert report["status"] == "PASS"


def test_stage_b_rejects_cross_table_context_duplicate_and_source_tamper(
    completed_pipeline: dict[str, Path],
) -> None:
    contrastive_path = completed_pipeline["stage_b"] / TABLES["contrastive"][0]
    context_path = completed_pipeline["stage_b"] / TABLES["context"][0]
    contrastive_fields, contrastive_rows = _read_csv(contrastive_path)
    _, context_rows = _read_csv(context_path)
    contrastive_rows[0]["context_id"] = context_rows[0]["context_id"]
    contrastive_rows[1]["source_text"] = "tampered"
    _write_csv(contrastive_path, contrastive_fields, contrastive_rows)
    errors = validate_stage_b(
        completed_pipeline["stage_b"],
        PILOT_ROOT,
        completed_pipeline["sense_contract"],
    )["errors"]
    assert any("context IDs occur in both tables" in error for error in errors)
    assert any("source payload was modified" in error for error in errors)


def test_metadata_without_status_and_whitespace_are_rejected(workflow: Path) -> None:
    fields, rows = _read_csv(workflow / STAGE_A_FILE)
    rows[0]["reviewer_1_id"] = " reviewer-a "
    rows[0]["reviewer_1_notes"] = "started"
    _write_csv(workflow / STAGE_A_FILE, fields, rows)
    errors = validate_stage_a(workflow, PILOT_ROOT)["errors"]
    assert any("data but status is blank" in error for error in errors)
    assert any("whitespace in reviewer_1_id" in error for error in errors)


def test_finalizer_emits_immutable_annotation_manifest(
    completed_pipeline: dict[str, Path],
    tmp_path: Path,
) -> None:
    output = tmp_path / "human-annotations"
    result = finalize_annotations(
        completed_pipeline["workflow"],
        PILOT_ROOT,
        completed_pipeline["sense_contract"],
        completed_pipeline["stage_b"],
        output,
        completed_at=COMPLETED_AT,
    )
    manifest = json.loads(
        (output / "annotation_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_id"] == "D2LPilotHumanAnnotationsV1"
    assert manifest["status"] == "COMPLETE_IMMUTABLE"
    assert result["annotation_manifest_sha256"] == manifest[
        "annotation_manifest_sha256"
    ]
    assert manifest["agreement_adjudication"]["total"] == {
        "agreement": 57,
        "majority": 0,
        "adjudicated": 1,
        "pending": 0,
    }


def test_packaged_validator_imports_without_builder_module(
    workflow_template: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(workflow_template / "validate_stage_a.py"),
            str(workflow_template),
            "--pilot-root",
            str(PILOT_ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert '"status": "PASS"' in result.stdout


def _complete_stage_a(workflow: Path, *, adjudicate: bool = True) -> str:
    path = workflow / STAGE_A_FILE
    fields, rows = _read_csv(path)
    corrected_sense = rows[0]["sense_id"]
    for row in rows:
        for prefix, reviewer_id, reviewed_at in (
            ("reviewer_1", "reviewer-a", REVIEWER_1_AT),
            ("reviewer_2", "reviewer-b", REVIEWER_2_AT),
            ("reviewer_3", "reviewer-c", "2026-07-28T08:07:00+07:00"),
        ):
            row[f"{prefix}_id"] = reviewer_id
            row[f"{prefix}_status"] = "REVIEWED"
            row[f"{prefix}_definition_status"] = "ACCEPTED"
            row[f"{prefix}_effective_definition_en"] = row["model_definition_en"]
            row[f"{prefix}_part_of_speech_status"] = "ACCEPTED"
            row[f"{prefix}_effective_part_of_speech"] = row[
                "model_part_of_speech"
            ]
            row[f"{prefix}_scope_note"] = ""
            row[f"{prefix}_reviewed_at"] = reviewed_at
        if row["sense_id"] == corrected_sense:
            row["reviewer_2_definition_status"] = "CORRECTED"
            row["reviewer_2_effective_definition_en"] = (
                f"Human-reviewed definition for {row['source_term']}."
            )
            row["reviewer_3_definition_status"] = "REJECTED"
            row["reviewer_3_effective_definition_en"] = ""
            if adjudicate:
                _adjudicate_stage_a_row(row)
    _write_csv(path, fields, rows)
    return corrected_sense


def _adjudicate_stage_a_row(row: dict[str, str]) -> None:
    row["adjudicator_id"] = "reviewer-d"
    row["adjudication_status"] = "ADJUDICATED"
    row["adjudicated_definition_status"] = "CORRECTED"
    row["adjudicated_effective_definition_en"] = (
        f"Human-reviewed definition for {row['source_term']}."
    )
    row["adjudicated_part_of_speech_status"] = "ACCEPTED"
    row["adjudicated_effective_part_of_speech"] = row["model_part_of_speech"]
    row["adjudicated_scope_note"] = ""
    row["adjudicated_at"] = ADJUDICATED_AT


def _complete_stage_b(stage_b_root: Path) -> None:
    for table, (filename, _, _) in TABLES.items():
        path = stage_b_root / filename
        fields, rows = _read_csv(path)
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            groups[row["sense_id"]].append(row)
        for group in groups.values():
            group.sort(key=lambda row: row.get("candidate_slot_id", row.get("context_id", "")))
        for row in rows:
            for prefix, reviewer_id, reviewed_at in (
                ("reviewer_1", "reviewer-a", REVIEWER_1_AT),
                ("reviewer_2", "reviewer-b", REVIEWER_2_AT),
                ("reviewer_3", "reviewer-c", "2026-07-28T08:07:00+07:00"),
            ):
                row[f"{prefix}_id"] = reviewer_id
                row[f"{prefix}_status"] = "REVIEWED"
                row[f"{prefix}_reviewed_at"] = reviewed_at
                if table == "contrastive":
                    row[f"{prefix}_contrastive_label"] = "VALID_BOUNDARY"
                    row[f"{prefix}_use_in_sense_boundary_test"] = "TRUE"
                elif table == "context":
                    proposed = row["model_proposed_context_type"]
                    row[f"{prefix}_same_sense_label"] = "SAME_SENSE"
                    row[f"{prefix}_context_type"] = (
                        proposed if proposed in {"C1", "C2", "C3", "C4", "C5"} else "C1"
                    )
                    row[f"{prefix}_context_validity"] = "VALID"
                else:
                    group = groups[row["sense_id"]]
                    index = group.index(row)
                    row[f"{prefix}_applicability"] = "IN_SCOPE"
                    row[f"{prefix}_semantic_fit_label"] = "PASS"
                    row[f"{prefix}_candidate_decision"] = "ACCEPT"
                    if index == 1:
                        row[f"{prefix}_candidate_rank"] = ""
                        row[f"{prefix}_candidate_relation"] = (
                            "MORPHOLOGICAL_VARIANT"
                        )
                        row[f"{prefix}_relation_to_candidate_instance_id"] = group[0][
                            "candidate_instance_id"
                        ]
                    else:
                        row[f"{prefix}_candidate_rank"] = "1" if index == 0 else "2"
                        row[f"{prefix}_candidate_relation"] = (
                            "INDEPENDENT_ALTERNATIVE"
                        )
                        row[f"{prefix}_relation_to_candidate_instance_id"] = ""
        _write_csv(path, fields, rows)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(
    path: Path,
    fields: list[str],
    rows: list[dict[str, str]],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
