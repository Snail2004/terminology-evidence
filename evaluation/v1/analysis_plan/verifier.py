"""Strict verifier for frozen 50/150 analysis-plan content."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.authority import AuthorityError, secure_existing_directory, secure_existing_file
from ..jsonio import read_json, sha256_file, sha256_value
from ..registries.loader import REGISTRY_FILES, load_registries, registry_counts
from ..release_tools.junit import load_expected_test_manifest
from ..time_policy import TimestampError, parse_rfc3339
from .access import GENESIS_SHA256, verify_gold_access_ledger
from .builder import (
    ACCESS_TEMPLATES_FILE,
    CONTENT_DIRECTORY,
    EXPECTED_TEST_MANIFEST,
    PLAN_DOCUMENT,
    PLAN_FILE,
    REQUIREMENT_DOCUMENT,
    TABLES_FILE,
)
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


_OID = re.compile(r"^[0-9a-f]{40}$")


class AnalysisPlanError(ValueError):
    """Raised when the plan is mutable, result-aware or authority-drifted."""


def _verify_self_hash(value: Mapping[str, Any], field: str) -> str:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {"self_sha256"}:
        raise AnalysisPlanError(f"{field} integrity shape is invalid")
    unsigned = dict(value)
    unsigned["integrity"] = {}
    actual = sha256_value(unsigned)
    if integrity.get("self_sha256") != actual:
        raise AnalysisPlanError(f"{field} self hash mismatch")
    return actual


def _secure(root: Path, relative: Path, field: str) -> Path:
    try:
        return secure_existing_file(root / relative, trusted_root=root, field=field)
    except AuthorityError as exc:
        raise AnalysisPlanError(str(exc)) from exc


def _verify_ref(root: Path, value: Any, expected_path: Path, expected_self: str | None = None) -> None:
    if not isinstance(value, Mapping):
        raise AnalysisPlanError(f"artifact ref is invalid: {expected_path}")
    required = {"path", "physical_sha256"}
    if expected_self is not None:
        required.add("canonical_self_sha256")
    if set(value) != required or value.get("path") != expected_path.as_posix():
        raise AnalysisPlanError(f"artifact ref path/shape mismatch: {expected_path}")
    path = _secure(root, expected_path, f"analysis_plan_ref.{expected_path.name}")
    if value.get("physical_sha256") != sha256_file(path):
        raise AnalysisPlanError(f"artifact ref physical hash mismatch: {expected_path}")
    if expected_self is not None and value.get("canonical_self_sha256") != expected_self:
        raise AnalysisPlanError(f"artifact ref self hash mismatch: {expected_path}")


def _forbid_result_payloads(value: Any) -> None:
    forbidden = {"estimate", "observed_value", "gold_label_counts", "result_rows"}
    if isinstance(value, Mapping):
        if forbidden & set(value):
            raise AnalysisPlanError("analysis plan contains result-bearing fields")
        for item in value.values():
            _forbid_result_payloads(item)
    elif isinstance(value, list):
        for item in value:
            _forbid_result_payloads(item)


def verify_analysis_plan_content(repo_root: Path) -> dict[str, Any]:
    try:
        root = secure_existing_directory(repo_root, field="analysis_plan_repo_root")
    except AuthorityError as exc:
        raise AnalysisPlanError(str(exc)) from exc
    content = CONTENT_DIRECTORY
    plan_path = _secure(root, content / PLAN_FILE, "analysis_plan.plan")
    tables_path = _secure(root, content / TABLES_FILE, "analysis_plan.tables")
    access_path = _secure(root, content / ACCESS_TEMPLATES_FILE, "analysis_plan.access_templates")
    plan = read_json(plan_path)
    tables = read_json(tables_path)
    access = read_json(access_path)
    plan_self = _verify_self_hash(plan, "analysis plan")
    tables_self = _verify_self_hash(tables, "planned tables")
    access_self = _verify_self_hash(access, "gold access templates")

    expected_plan_keys = {
        "schema_id", "schema_version", "plan_id", "status", "frozen_at",
        "source_parent_commit", "scope", "access_state", "label_mapping",
        "registered_primary_metric_ids", "metrics", "e_status_reporting_mapping",
        "missing_data_policy",
        "confidence_interval_policy", "registered_statistical_policy",
        "access_order", "amendment_policy", "small_sample_policy",
        "registry_bindings", "registry_binding_sha256", "registry_counts",
        "planned_tables_ref", "gold_access_templates_ref",
        "analysis_document_ref", "review_requirement_ref",
        "expected_test_authority_ref", "integrity",
    }
    if set(plan) != expected_plan_keys:
        raise AnalysisPlanError("analysis plan shape is invalid")
    if (
        plan.get("schema_id") != "EvaluationAnalysisPlan50_150V1"
        or plan.get("schema_version") != "1.0.0"
        or plan.get("plan_id") != PLAN_ID
        or plan.get("status") != "ANALYSIS_PLAN_SPEC_LOCKED_BEFORE_EVIDENCE"
        or plan.get("frozen_at") != FROZEN_AT
        or not isinstance(plan.get("source_parent_commit"), str)
        or not _OID.fullmatch(plan["source_parent_commit"])
    ):
        raise AnalysisPlanError("analysis plan identity/status is invalid")
    try:
        parse_rfc3339(plan["frozen_at"], "analysis_plan.frozen_at")
    except TimestampError as exc:
        raise AnalysisPlanError(str(exc)) from exc
    if plan.get("scope") != {
        "sense_count": 50,
        "candidate_count": 150,
        "candidates_per_sense": 3,
        "split_counts_source": "FUTURE_DATASET_SPLIT_MANIFEST_MUST_TOTAL_EXACT_SCOPE",
        "result_dependent_sampling": False,
    }:
        raise AnalysisPlanError("analysis plan 50/150 scope drifted")
    if plan.get("access_state") != {
        "producer_outputs_opened": False,
        "gold_opened": False,
        "validation_opened": False,
        "held_out_test_opened": False,
        "actual_gold_access_receipt_count": 0,
    }:
        raise AnalysisPlanError("analysis plan is not frozen before evidence access")

    registries_root = root / "evaluation" / "v1" / "registries"
    registries = load_registries(registries_root)
    bindings = {name: sha256_file(registries_root / name) for name in REGISTRY_FILES}
    if plan.get("registry_bindings") != dict(sorted(bindings.items())):
        raise AnalysisPlanError("analysis plan registry bytes drifted")
    if plan.get("registry_binding_sha256") != sha256_value(dict(sorted(bindings.items()))):
        raise AnalysisPlanError("analysis plan registry aggregate hash drifted")
    if plan.get("registry_counts") != registry_counts(registries):
        raise AnalysisPlanError("analysis plan registry counts drifted")
    labels = registries["label_mapping"]
    if plan.get("label_mapping") != {
        "gold_labels": labels["gold_labels"],
        "primary_binary": labels["primary_binary"],
        "secondary_binary": labels["secondary_binary"],
    }:
        raise AnalysisPlanError("analysis plan label mapping drifted")
    if plan.get("registered_primary_metric_ids") != registries["metric_registry"]["primary_metrics"]:
        raise AnalysisPlanError("analysis plan primary metrics drifted")
    if plan.get("metrics") != metric_specification():
        raise AnalysisPlanError("analysis plan metric definitions drifted")
    if plan.get("e_status_reporting_mapping") != e_status_reporting_mapping():
        raise AnalysisPlanError("analysis plan E status reporting mapping drifted")
    if plan.get("missing_data_policy") != missing_data_policy():
        raise AnalysisPlanError("analysis plan missing-data policy drifted")
    if plan.get("confidence_interval_policy") != confidence_interval_policy():
        raise AnalysisPlanError("analysis plan confidence-interval policy drifted")
    statistical = registries["statistical_analysis_plan"]
    expected_statistical = {
        key: statistical[key]
        for key in (
            "primary_interval", "grouped_interval", "paired_binary_test",
            "continuous_paired_test", "multiple_comparison_correction",
            "effect_size_required", "p_value_alone_prohibited",
        )
    }
    if plan.get("registered_statistical_policy") != expected_statistical:
        raise AnalysisPlanError("analysis plan registered statistical policy drifted")
    if [row.get("stage") for row in plan.get("access_order", [])] != list(STAGE_ORDER):
        raise AnalysisPlanError("analysis plan access order drifted")

    if (
        tables.get("schema_id") != "EvaluationPlannedTables50_150V1"
        or tables.get("schema_version") != "1.0.0"
        or tables.get("plan_id") != PLAN_ID
        or tables.get("status") != "FROZEN_EMPTY_TABLE_SHELLS"
        or tables.get("result_cells_present") != 0
        or tables.get("tables") != planned_tables()
    ):
        raise AnalysisPlanError("planned tables drifted or contain results")
    if (
        access.get("schema_id") != "EvaluationGoldAccessTemplateSetV1"
        or access.get("schema_version") != "1.0.0"
        or access.get("plan_id") != PLAN_ID
        or access.get("status") != "TEMPLATE_ONLY_NO_ACCESS"
        or access.get("stage_order") != list(STAGE_ORDER)
        or access.get("templates") != gold_access_templates()
        or access.get("actual_access_receipts") != []
    ):
        raise AnalysisPlanError("gold access templates drifted or contain access receipts")
    verify_gold_access_ledger([], analysis_plan_freeze_receipt_sha256="f" * 64)

    _verify_ref(root, plan["planned_tables_ref"], content / TABLES_FILE, tables_self)
    _verify_ref(root, plan["gold_access_templates_ref"], content / ACCESS_TEMPLATES_FILE, access_self)
    _verify_ref(root, plan["analysis_document_ref"], PLAN_DOCUMENT)
    _verify_ref(root, plan["review_requirement_ref"], REQUIREMENT_DOCUMENT)

    expected_test = load_expected_test_manifest(root / EXPECTED_TEST_MANIFEST)
    expected_ref = plan.get("expected_test_authority_ref")
    if not isinstance(expected_ref, Mapping) or set(expected_ref) != {
        "path", "physical_sha256", "canonical_self_sha256",
        "testcase_identity_sha256", "test_count",
    }:
        raise AnalysisPlanError("expected-test authority ref shape is invalid")
    if expected_ref != {
        "path": EXPECTED_TEST_MANIFEST.as_posix(),
        "physical_sha256": sha256_file(root / EXPECTED_TEST_MANIFEST),
        "canonical_self_sha256": expected_test["integrity"]["self_sha256"],
        "testcase_identity_sha256": expected_test["testcase_identity_sha256"],
        "test_count": expected_test["test_count"],
    }:
        raise AnalysisPlanError("expected-test authority ref drifted")
    _forbid_result_payloads(plan)
    _forbid_result_payloads(tables)
    return {
        "status": "PASS",
        "plan_self_sha256": plan_self,
        "tables_self_sha256": tables_self,
        "gold_access_templates_self_sha256": access_self,
        "actual_gold_access_receipt_count": 0,
        "gold_access_ledger_head": GENESIS_SHA256,
    }
