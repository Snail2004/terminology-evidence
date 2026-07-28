from __future__ import annotations

import copy
import hashlib
import zipfile
from pathlib import Path

import pytest

from context_substitution.v2.contracts.input import seal_context_substitution_input
from context_substitution.v2.contracts.validation import ContractValidationError
from context_substitution.v2.dataset.reviewed_support import (
    reviewed_support_to_context_substitution_input,
    validate_reviewed_support_bundle,
    validate_reviewed_support_receipt,
)
from context_substitution.v2.providers.base import ContextProviderRoute
from context_substitution.v2.providers.ledger import ProviderResponseLedger
from context_substitution.v2.runtime.aggregation import global_recommendation
from context_substitution.v2.runtime.calibration import (
    FROZEN_POLICY_STATUS,
    frozen_validation_policy,
)
from context_substitution.v2.runtime.calibration_artifact import (
    build_calibration_artifact,
    validate_calibration_artifact,
)


ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "dataset"
V3 = DATASET / "d2l_context_support_set_validation_ready_v3"
PILOT = DATASET / "pilot_dev_only_v1_1"
HASH_A = "a" * 64
HASH_B = "b" * 64


def test_real_v3_bundle_validates_all_rows() -> None:
    result = validate_reviewed_support_bundle(V3)
    assert result["status"] == "PASS"
    assert result["counts"] == {
        "term_senses": 150,
        "candidate_instances": 450,
        "contexts": 1340,
    }
    assert result["provider_call_count"] == 0
    assert result["final_glossary_decision"] is None


def test_zip_traversal_and_unbound_bytes_reject(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../manifest.json", "{}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(ContractValidationError, match="path is not canonical"):
        validate_reviewed_support_bundle(archive, expected_zip_sha256=digest)
    with pytest.raises(ContractValidationError, match="physical ZIP hash mismatch"):
        validate_reviewed_support_bundle(archive, expected_zip_sha256="f" * 64)


def test_real_v3_requires_split_and_adapts_development() -> None:
    with pytest.raises(ContractValidationError, match="explicit development"):
        reviewed_support_to_context_substitution_input(V3)
    adapted = reviewed_support_to_context_substitution_input(
        V3, source_split="development"
    )
    payload = adapted["input"]
    assert len(payload["terms"]) == 100
    assert sum(len(row["candidate_targets"]) for row in payload["terms"]) == 300
    assert sum(len(row["contexts"]) for row in payload["terms"]) == 894


def test_adapter_receipt_rejects_self_consistent_shape_tamper() -> None:
    receipt = reviewed_support_to_context_substitution_input(
        PILOT, parent_v3_source=V3
    )["receipt"]
    forged = dict(receipt)
    forged["provider_call_count"] = 1
    with pytest.raises(ContractValidationError, match="zero-API"):
        validate_reviewed_support_receipt(forged)


def test_calibration_requires_nonzero_self_hashed_artifact() -> None:
    artifact = build_calibration_artifact(
        dataset_manifest_sha256=HASH_A,
        gold_dataset_sha256=HASH_B,
        policy_version="cst-calibrated-test-v1",
        supported_min_c=0.82,
        unsupported_below_c=0.58,
        supported_min_pass=4,
        supported_max_minor=1,
        unsupported_min_fail=2,
        second_judge_thresholds=(0.58, 0.7, 0.82),
        second_judge_tolerance=0.03,
        pairwise_close_margin=0.05,
        case_count=100,
        positive_case_count=50,
        negative_case_count=50,
        measured_auto_approval_precision=0.97,
    )
    assert validate_calibration_artifact(artifact) == artifact
    assert frozen_validation_policy(
        calibration_artifact=artifact
    ).policy_status == FROZEN_POLICY_STATUS
    forged = copy.deepcopy(artifact)
    forged["dataset_manifest_sha256"] = "0" * 64
    with pytest.raises(ContractValidationError, match="zero hash"):
        validate_calibration_artifact(forged)


def test_provider_response_ledger_is_content_addressed(tmp_path: Path) -> None:
    ledger = ProviderResponseLedger(tmp_path)
    first = ledger.capture('{"ok":true}')
    second = ledger.capture('{"ok":true}')
    assert first == second
    target = tmp_path / first["raw_response_ref"]
    assert target.read_text(encoding="utf-8") == '{"ok":true}'


def test_pinned_non_gemini_model_is_allowed_but_latest_alias_is_not() -> None:
    route = ContextProviderRoute(
        route_id="shopaikey_gemini",
        model_id="gpt-5.5-pinned-2026-07",
        model_family="gpt-5.5",
        independence_group="shopai-gpt-5.5",
        sender=lambda **_: None,  # type: ignore[arg-type]
    )
    assert route.model_family == "gpt-5.5"
    with pytest.raises(ValueError, match="latest alias"):
        ContextProviderRoute(
            route_id="gemini_official",
            model_id="gemini-latest",
            sender=lambda **_: None,  # type: ignore[arg-type]
        )


def test_development_input_cannot_smuggle_reviewed_selection() -> None:
    payload = reviewed_support_to_context_substitution_input(
        PILOT, parent_v3_source=V3
    )["input"]
    forged = copy.deepcopy(payload)
    forged["terms"][0]["contexts"][0]["reviewed_selection"] = {
        "sense_relation": "SAME_SENSE",
        "context_type": "definition",
        "judgeability": "JUDGEABLE",
        "reason": "forged authority",
        "review_row_sha256": HASH_A,
    }
    with pytest.raises(ContractValidationError, match="cannot carry frozen"):
        seal_context_substitution_input(forged)


@pytest.mark.parametrize(
    "flag",
    ["MISSING_CONTRASTIVE_CONTEXT", "INCOMPLETE_CONTEXT_TYPE_COVERAGE"],
)
def test_incomplete_context_support_cannot_become_globally_eligible(flag: str) -> None:
    assert global_recommendation(
        contextual_status_value="CONTEXT_SUPPORTED",
        context_flags=[flag],
        threshold_policy_status=FROZEN_POLICY_STATUS,
    ) == "REQUIRES_GLOBAL_REVIEW"
