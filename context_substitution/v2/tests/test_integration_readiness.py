from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from context_substitution.v2.cli import parser
from context_substitution.v2.contracts.common import REQUIRED_SAME_SENSE_CONTEXT_TYPES
from context_substitution.v2.contracts.input import seal_context_substitution_input
from context_substitution.v2.contracts.validation import ContractValidationError
from context_substitution.v2.dataset.reviewed_support import (
    reviewed_support_to_context_substitution_input,
)
from context_substitution.v2.integration.authority import (
    AUTHORITY_COMMIT,
    AUTHORITY_TAG,
    CONTRACT_MANIFEST_SHA256,
    seal_frozen_candidate_contract,
    validate_authority,
)
from context_substitution.v2.integration.development_fixtures import (
    FIXTURE_HOLD_STATUS,
    build_development_frozen_candidate_fixtures,
)
from context_substitution.v2.integration.fake_provider import run_fake_provider_pilot
from context_substitution.v2.integration.pilot import run_zero_api_pilot_smoke
from context_substitution.v2.integration.projection import (
    PACKAGE_SET_HOLD_STATUS,
    build_projection_binding_from_ledger,
    project_context_evidence_packages,
    write_context_evidence_package_set,
)
from context_substitution.v2.integration.replay import replay_context_run
from context_substitution.v2.runtime.engine import _classify_and_select_contexts


ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "dataset"
PILOT = DATASET / "pilot_dev_only_v1_1"
PILOT_ZIP = DATASET / "pilot_dev_only_v1_1.zip"
V3 = DATASET / "d2l_context_support_set_validation_ready_v3"
V3_ZIP = DATASET / "d2l_context_support_set_validation_ready_v3.zip"
PENDING_REVIEW = DATASET / "pilot_normalized_review_pack_v1_4"
HASH_A = "a" * 64
HASH_B = "b" * 64


@pytest.fixture(scope="module")
def integration_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("cst-integration")
    adapted = reviewed_support_to_context_substitution_input(
        PILOT,
        parent_v3_source=V3,
        source_split="development",
    )
    result = run_fake_provider_pilot(adapted["input"], ledger_root=root / "ledger")
    replay = replay_context_run(
        input_payload=adapted["input"],
        original_run=result["run"],
        ledger_root=root / "ledger",
    )
    ledger_path = root / "ledger" / "provider_attempts.jsonl"
    binding = build_projection_binding_from_ledger(
        run_payload=result["run"], ledger_path=ledger_path
    )
    frozen = build_development_frozen_candidate_fixtures(
        input_payload=adapted["input"],
        run_payload=result["run"],
        started_at=binding["started_at"],
        completed_at=binding["completed_at"],
    )
    packages = project_context_evidence_packages(
        run_payload=result["run"],
        frozen_candidates=frozen["candidates"],
        binding=binding,
    )
    manifest = write_context_evidence_package_set(
        run_payload=result["run"],
        frozen_candidates=frozen["candidates"],
        binding=binding,
        output_directory=root / "context_evidence_packages",
    )
    return {
        "root": root,
        "input": adapted["input"],
        "run": result["run"],
        "summary": result["summary"],
        "replay": replay,
        "ledger_path": ledger_path,
        "binding": binding,
        "frozen": frozen,
        "packages": packages,
        "manifest": manifest,
    }


def test_standalone_cli_exposes_required_commands() -> None:
    choices = {
        command
        for action in parser()._actions
        if getattr(action, "choices", None)
        for command in action.choices
    }
    assert {
        "reviewed-support-validate",
        "reviewed-support-to-runtime",
        "context-run",
        "run-validate",
        "project-context-evidence",
        "development-fixture-freeze",
        "authority-validate",
        "gold-evaluate",
    } <= choices


def test_real_pilot_directory_and_zip_zero_api_equivalence() -> None:
    receipt = run_zero_api_pilot_smoke(
        pilot_directory=PILOT,
        pilot_zip=PILOT_ZIP,
        parent_directory=V3,
        parent_zip=V3_ZIP,
    )
    assert receipt["status"] == "PASS"
    assert receipt["counts"] == {
        "term_senses": 5,
        "candidates": 15,
        "primary_contexts": 25,
        "backup_contexts": 8,
        "contrastive_contexts": 5,
        "missing_references": 0,
    }
    assert receipt["provider_call_count"] == 0
    assert receipt["final_glossary_decision"] is None


def test_fake_provider_covers_all_required_scenarios(
    integration_run: dict[str, Any],
) -> None:
    summary = integration_run["summary"]
    assert summary["status"] == "PASS"
    assert summary["candidate_count"] == 15
    assert all(summary["scenario_coverage"].values())
    assert summary["raw_response_storage_complete"] is True
    assert summary["final_glossary_decision"] is None


def test_provider_ledger_has_audit_fields_and_replays_exactly(
    integration_run: dict[str, Any],
) -> None:
    ledger_path = integration_run["root"] / "ledger" / "provider_attempts.jsonl"
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    attempts = [row for row in rows if row["record_kind"] == "PROVIDER_ATTEMPT"]
    required = {
        "run_id",
        "candidate_id",
        "context_id",
        "provider_id",
        "model_id",
        "prompt_sha256",
        "request_sha256",
        "response_sha256",
        "status",
        "retry_index",
        "failure_reason",
        "started_at",
        "completed_at",
        "token_usage",
        "latency",
        "tag",
    }
    assert attempts and all(required <= set(row) for row in attempts)
    assert integration_run["replay"]["status"] == "PASS"
    assert integration_run["replay"]["normalized_output_equal"] is True
    assert integration_run["replay"]["provider_call_count"] == 0


def test_raw_response_tamper_breaks_replay(
    integration_run: dict[str, Any], tmp_path: Path
) -> None:
    source = integration_run["root"] / "ledger"
    forged = tmp_path / "ledger"
    shutil.copytree(source, forged)
    response = next((forged / "provider_responses").glob("*.txt"))
    response.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="raw response hash mismatch"):
        replay_context_run(
            input_payload=integration_run["input"],
            original_run=integration_run["run"],
            ledger_root=forged,
        )


def test_projection_emits_official_v1_1_packages_and_remains_decision_neutral(
    integration_run: dict[str, Any],
) -> None:
    packages = integration_run["packages"]
    assert len(packages) == 15
    assert all(package["schema_id"] == "ContextEvidencePackageV1" for package in packages)
    assert all(package["schema_version"] == "1.1.0" for package in packages)
    assert all(package["final_glossary_decision"] is None for package in packages)
    assert all(len(package["gate_signals"]) == 7 for package in packages)
    assert all("global_gate_action" not in package for package in packages)
    assert integration_run["frozen"]["status"] == FIXTURE_HOLD_STATUS
    assert integration_run["manifest"]["status"] == PACKAGE_SET_HOLD_STATUS
    assert integration_run["manifest"]["global_gate_action"] is None


def test_projection_preserves_candidate_and_input_contract_bindings(
    integration_run: dict[str, Any],
) -> None:
    frozen = {
        row["candidate_key"]["candidate_id"]: row
        for row in integration_run["frozen"]["candidates"]
    }
    for package in integration_run["packages"]:
        source = frozen[package["candidate_key"]["candidate_id"]]
        assert package["candidate_key"] == source["candidate_key"]
        assert package["input_contract_sha256"] == source["input_contract_sha256"]


def test_projection_rejects_validly_resealed_foreign_candidate(
    integration_run: dict[str, Any],
) -> None:
    forged = copy.deepcopy(integration_run["frozen"]["candidates"])
    forged[0]["candidate_key"]["source_term"] = "foreign-source-term"
    forged[0] = seal_frozen_candidate_contract(forged[0])
    with pytest.raises(ValueError, match="source_term differs"):
        project_context_evidence_packages(
            run_payload=integration_run["run"],
            frozen_candidates=forged,
            binding=integration_run["binding"],
        )


def test_projection_rejects_authority_binding_drift(
    integration_run: dict[str, Any],
) -> None:
    forged = copy.deepcopy(integration_run["binding"])
    forged["authority_commit"] = HASH_A
    with pytest.raises(ValueError, match="authority commit mismatch"):
        project_context_evidence_packages(
            run_payload=integration_run["run"],
            frozen_candidates=integration_run["frozen"]["candidates"],
            binding=forged,
        )


def test_frozen_authority_receipt_matches_published_contract() -> None:
    receipt = validate_authority()
    assert receipt["authority_tag"] == AUTHORITY_TAG
    assert receipt["authority_commit"] == AUTHORITY_COMMIT
    assert receipt["manifest_sha256"] == CONTRACT_MANIFEST_SHA256


def test_pending_review_pack_cannot_claim_frozen_authority() -> None:
    with pytest.raises(ContractValidationError, match="STAGE_A_HUMAN_REVIEW_PENDING"):
        reviewed_support_to_context_substitution_input(
            PILOT,
            parent_v3_source=V3,
            source_split="development",
            review_artifact=PENDING_REVIEW,
        )


def test_frozen_selector_uses_reviewed_rows_and_requires_complete_cover() -> None:
    payload = reviewed_support_to_context_substitution_input(
        PILOT,
        parent_v3_source=V3,
        source_split="development",
    )["input"]
    frozen = copy.deepcopy(payload)
    frozen["input_origin"]["kind"] = "FROZEN_HUMAN_REVIEWED_PILOT_V1"
    frozen["selection_contract"].update(
        {
            "selector_mode": "FROZEN_HUMAN_REVIEWED_SELECTION",
            "authority_status": "FROZEN_HUMAN_REVIEWED",
            "review_artifact_ref": f"artifact://review/{HASH_A}",
            "review_artifact_sha256": HASH_A,
            "effective_sense_contract_ref": f"artifact://sense/{HASH_B}",
            "effective_sense_contract_sha256": HASH_B,
        }
    )
    for term in frozen["terms"]:
        for index, context in enumerate(term["contexts"]):
            context["reviewed_selection"] = {
                "sense_relation": "SAME_SENSE" if index < 5 else "CONTRASTIVE",
                "context_type": (
                    REQUIRED_SAME_SENSE_CONTEXT_TYPES[index]
                    if index < 5
                    else "contrastive"
                ),
                "judgeability": "JUDGEABLE",
                "reason": "frozen reviewed row",
                "review_row_sha256": HASH_A,
            }
    sealed = seal_context_substitution_input(frozen)

    class NoModelCall:
        def call(self, **_: object) -> object:
            raise AssertionError("frozen selector must not call a provider")

    selection = _classify_and_select_contexts(
        model=NoModelCall(),
        term=sealed["terms"][0],
        selection_contract=sealed["selection_contract"],
    )
    assert selection["provenance"] is None
    assert len(selection["same_sense"]) == 5

    missing = copy.deepcopy(sealed)
    missing["terms"][0]["contexts"][0]["reviewed_selection"] = None
    with pytest.raises(ContractValidationError, match="reviewed row for every context"):
        seal_context_substitution_input(missing)
