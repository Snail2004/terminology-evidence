"""Deterministic, zero-data builder for the 50/150 analysis-plan content."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..jsonio import read_json, sha256_file, sha256_value, write_json
from ..registries.loader import REGISTRY_FILES, load_registries, registry_counts
from ..release_tools.junit import load_expected_test_manifest
from .specification import (
    FROZEN_AT,
    PLAN_ID,
    STAGE_ORDER,
    confidence_interval_policy,
    e_status_reporting_mapping,
    gold_access_templates,
    metric_specification,
    missing_data_policy,
    planned_tables,
)


CONTENT_DIRECTORY = Path("evaluation/v1/authority/analysis_plan_50_150_v1")
PLAN_FILE = "analysis_plan_50_150_v1.json"
TABLES_FILE = "planned_tables_v1.json"
ACCESS_TEMPLATES_FILE = "gold_access_event_templates_v1.json"
PLAN_DOCUMENT = Path("docs/evaluation/ANALYSIS_PLAN_50_150_V1.md")
REQUIREMENT_DOCUMENT = Path(
    "docs/evaluation/Yeu_cau_Agent_Evaluation_Freeze_Analysis_Plan_50_150_V1.md"
)
EXPECTED_TEST_MANIFEST = Path("evaluation/v1/authority/expected_test_manifest_v1.json")


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    sealed = dict(value)
    sealed["integrity"] = {"self_sha256": ""}
    unsigned = dict(sealed)
    unsigned["integrity"] = {}
    sealed["integrity"]["self_sha256"] = sha256_value(unsigned)
    return sealed


def _artifact_ref(path: Path, relative: Path, value: Mapping[str, Any]) -> dict[str, str]:
    return {
        "path": relative.as_posix(),
        "physical_sha256": sha256_file(path),
        "canonical_self_sha256": value["integrity"]["self_sha256"],
    }


def build_analysis_plan_content(
    repo_root: Path,
    *,
    source_parent_commit: str,
    output_directory: Path | None = None,
) -> dict[str, Any]:
    """Build frozen content without reading Dataset, producer, gold or result bytes."""
    root = Path(repo_root)
    output = output_directory or (root / CONTENT_DIRECTORY)
    document_path = root / PLAN_DOCUMENT
    requirement_path = root / REQUIREMENT_DOCUMENT
    expected_test_path = root / EXPECTED_TEST_MANIFEST
    if not document_path.is_file() or not requirement_path.is_file() or not expected_test_path.is_file():
        raise ValueError("analysis-plan source documents/test authority are missing")
    expected_test = load_expected_test_manifest(expected_test_path)
    registries_root = root / "evaluation" / "v1" / "registries"
    registries = load_registries(registries_root)
    registry_bindings = {
        name: sha256_file(registries_root / name) for name in REGISTRY_FILES
    }

    tables = _seal(
        {
            "schema_id": "EvaluationPlannedTables50_150V1",
            "schema_version": "1.0.0",
            "plan_id": PLAN_ID,
            "status": "FROZEN_EMPTY_TABLE_SHELLS",
            "result_cells_present": 0,
            "tables": planned_tables(),
        }
    )
    output.mkdir(parents=True, exist_ok=True)
    tables_path = output / TABLES_FILE
    write_json(tables_path, tables)

    access_templates = _seal(
        {
            "schema_id": "EvaluationGoldAccessTemplateSetV1",
            "schema_version": "1.0.0",
            "plan_id": PLAN_ID,
            "status": "TEMPLATE_ONLY_NO_ACCESS",
            "stage_order": list(STAGE_ORDER),
            "templates": gold_access_templates(),
            "actual_access_receipts": [],
        }
    )
    access_path = output / ACCESS_TEMPLATES_FILE
    write_json(access_path, access_templates)

    label_mapping = registries["label_mapping"]
    statistical_policy = registries["statistical_analysis_plan"]
    plan = _seal(
        {
            "schema_id": "EvaluationAnalysisPlan50_150V1",
            "schema_version": "1.0.0",
            "plan_id": PLAN_ID,
            "status": "ANALYSIS_PLAN_SPEC_LOCKED_BEFORE_EVIDENCE",
            "frozen_at": FROZEN_AT,
            "source_parent_commit": source_parent_commit,
            "scope": {
                "sense_count": 50,
                "candidate_count": 150,
                "candidates_per_sense": 3,
                "split_counts_source": "FUTURE_DATASET_SPLIT_MANIFEST_MUST_TOTAL_EXACT_SCOPE",
                "result_dependent_sampling": False,
            },
            "access_state": {
                "producer_outputs_opened": False,
                "gold_opened": False,
                "validation_opened": False,
                "held_out_test_opened": False,
                "actual_gold_access_receipt_count": 0,
            },
            "label_mapping": {
                "gold_labels": label_mapping["gold_labels"],
                "primary_binary": label_mapping["primary_binary"],
                "secondary_binary": label_mapping["secondary_binary"],
            },
            "registered_primary_metric_ids": registries["metric_registry"]["primary_metrics"],
            "metrics": metric_specification(),
            "e_status_reporting_mapping": e_status_reporting_mapping(),
            "missing_data_policy": missing_data_policy(),
            "confidence_interval_policy": confidence_interval_policy(),
            "registered_statistical_policy": {
                key: statistical_policy[key]
                for key in (
                    "primary_interval",
                    "grouped_interval",
                    "paired_binary_test",
                    "continuous_paired_test",
                    "multiple_comparison_correction",
                    "effect_size_required",
                    "p_value_alone_prohibited",
                )
            },
            "access_order": [
                {"stage": "D0", "scope": "development_canary", "rule": "seal C/E/Global outputs before authorized development-gold open"},
                {"stage": "D1", "scope": "development", "rule": "only preregistered amendments followed by a new refreeze are allowed"},
                {"stage": "V1", "scope": "validation", "rule": "requires D1 closure and policy freeze"},
                {"stage": "T1", "scope": "held_out_test", "rule": "requires validation closure and calibration freeze"},
            ],
            "amendment_policy": {
                "before_D0": "APPEND_ONLY_AMENDMENT_AND_REFREEZE",
                "after_D0_before_V1": "PRIMARY_CHANGE_REQUIRES_NEW_VERSION_DISCLOSURE_AND_REFREEZE",
                "after_T1": "PRIMARY_ANALYSIS_CHANGE_FORBIDDEN",
                "result_driven_silent_change": "FORBIDDEN",
            },
            "small_sample_policy": {
                "D0": "DESCRIPTIVE_ONLY_NO_CONFIRMATORY_CLAIM",
                "zero_cell_reporting": "REPORT_EXACT_COUNT_NO_CONTINUITY_FABRICATION",
                "unstable_interval_reporting": "REPORT_WIDE_INTERVAL_AND_LIMITATION",
            },
            "registry_bindings": dict(sorted(registry_bindings.items())),
            "registry_binding_sha256": sha256_value(dict(sorted(registry_bindings.items()))),
            "registry_counts": registry_counts(registries),
            "planned_tables_ref": _artifact_ref(
                tables_path,
                CONTENT_DIRECTORY / TABLES_FILE,
                tables,
            ),
            "gold_access_templates_ref": _artifact_ref(
                access_path,
                CONTENT_DIRECTORY / ACCESS_TEMPLATES_FILE,
                access_templates,
            ),
            "analysis_document_ref": {
                "path": PLAN_DOCUMENT.as_posix(),
                "physical_sha256": sha256_file(document_path),
            },
            "review_requirement_ref": {
                "path": REQUIREMENT_DOCUMENT.as_posix(),
                "physical_sha256": sha256_file(requirement_path),
            },
            "expected_test_authority_ref": {
                "path": EXPECTED_TEST_MANIFEST.as_posix(),
                "physical_sha256": sha256_file(expected_test_path),
                "canonical_self_sha256": expected_test["integrity"]["self_sha256"],
                "testcase_identity_sha256": expected_test["testcase_identity_sha256"],
                "test_count": expected_test["test_count"],
            },
        }
    )
    plan_path = output / PLAN_FILE
    write_json(plan_path, plan)
    return {
        "status": "PASS",
        "plan_path": plan_path,
        "plan_self_sha256": plan["integrity"]["self_sha256"],
        "tables_path": tables_path,
        "tables_self_sha256": tables["integrity"]["self_sha256"],
        "access_templates_path": access_path,
        "access_templates_self_sha256": access_templates["integrity"]["self_sha256"],
    }
