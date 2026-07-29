from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from xml.etree import ElementTree
from pathlib import Path
from typing import Any, Mapping

import pytest

from context_substitution.v2.cli import parser
from context_substitution.v2.contracts.common import REQUIRED_SAME_SENSE_CONTEXT_TYPES
from context_substitution.v2.contracts.input import seal_context_substitution_input
from context_substitution.v2.contracts.run import seal_context_substitution_run
from context_substitution.v2.contracts.validation import ContractValidationError
from context_substitution.v2.dataset.reviewed_support import (
    reviewed_support_to_context_substitution_input,
)
from context_substitution.v2.dataset.reviewed_selection import (
    ANNOTATION_POLICY_ID,
    ANNOTATION_SCHEMA_ID,
    ANNOTATION_SCHEMA_VERSION,
    FINALIZED_SELECTION_FILE,
    load_frozen_review_selection,
)
from context_substitution.v2.integration.authority import (
    AUTHORITY_COMMIT,
    AUTHORITY_RECEIPT_PHYSICAL_SHA256,
    AUTHORITY_RECEIPT_SELF_SHA256,
    AUTHORITY_TAG,
    CONTRACT_MANIFEST_SHA256,
    DEFAULT_AUTHORITY_RECEIPT_PATH,
    AuthorityConformanceError,
    contract_package_root,
    seal_frozen_candidate_contract,
    validate_authority,
    validate_authority_receipt,
)
from context_substitution.v2.integration.common import object_sha256, seal_object, write_json
from context_substitution.v2.integration.development_fixtures import (
    FIXTURE_HOLD_STATUS,
    build_development_frozen_candidate_fixtures,
)
from context_substitution.v2.integration.fake_provider import run_fake_provider_pilot
from context_substitution.v2.integration.pilot import run_zero_api_pilot_smoke
from context_substitution.v2.integration.projection import (
    PACKAGE_SET_COMPLETE_STATUS,
    PACKAGE_SET_SYNTHETIC_STATUS,
    build_projection_binding_from_ledger,
    project_context_evidence_packages,
    write_context_evidence_package_set,
)
from context_substitution.v2.integration.release import build_integration_release
from context_substitution.v2.integration.release_validation import (
    DATASET_FROZEN_SET_SCHEMA_ID,
    DATASET_FROZEN_SET_SCHEMA_VERSION,
)
from context_substitution.v2.integration.replay import replay_context_run
from context_substitution.v2.jsonio import StrictJSONError, loads_strict
from context_substitution.v2.runtime.aggregation import (
    compute_context_result,
    merge_judge_labels,
)
from context_substitution.v2.runtime.engine import _classify_and_select_contexts


ROOT = Path(__file__).resolve().parents[3]
DATASET = Path(os.environ.get("CST_DATASET_ROOT", ROOT / "dataset"))
PILOT = DATASET / "pilot_dev_only_v1_1"
PILOT_ZIP = DATASET / "pilot_dev_only_v1_1.zip"
V3 = DATASET / "d2l_context_support_set_validation_ready_v3"
V3_ZIP = DATASET / "d2l_context_support_set_validation_ready_v3.zip"
PENDING_REVIEW = DATASET / "pilot_normalized_review_pack_v1_4"
HASH_A = "a" * 64
HASH_B = "b" * 64


def _dataset_frozen_set_for_test(
    local_fixture: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = []
    for source in local_fixture["candidates"]:
        row = copy.deepcopy(source)
        row["schema_id"] = "FrozenCandidateContractV1"
        row["schema_version"] = "1.1.0"
        row.pop("status")
        row.pop("source_input_sha256")
        row.pop("source_run_sha256")
        row["input_provenance"]["component_id"] = "dataset-adapter-test-fixture"
        row["input_provenance"]["policy_version"] = "DATASET_TEST_FIXTURE_V1"
        row["input_provenance"]["notes"] = "pytest-only Dataset authority fixture"
        row["integrity"] = {}
        row["input_contract_sha256"] = "0" * 64
        row["binding_status"] = "COMPLETE"
        candidates.append(seal_frozen_candidate_contract(row))
    result = {
        "schema_id": DATASET_FROZEN_SET_SCHEMA_ID,
        "schema_version": DATASET_FROZEN_SET_SCHEMA_VERSION,
        "status": "COMPLETE_IMMUTABLE",
        "authority_owner": "DATASET_ADAPTER",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "final_glossary_decision": None,
        "integrity": {},
    }
    return seal_object(result, integrity_key="self_sha256")


def _require_external_dependencies(*paths: Path) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        pytest.skip("external integration dependencies are not materialized: " + ", ".join(missing))


@pytest.fixture(scope="module")
def integration_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    _require_external_dependencies(PILOT, PILOT_ZIP, V3, V3_ZIP)
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
    local_fixture = build_development_frozen_candidate_fixtures(
        input_payload=adapted["input"],
        run_payload=result["run"],
        started_at=binding["started_at"],
        completed_at=binding["completed_at"],
    )
    frozen = _dataset_frozen_set_for_test(local_fixture)
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
    adapter_receipt = run_zero_api_pilot_smoke(
        pilot_directory=PILOT,
        pilot_zip=PILOT_ZIP,
        parent_directory=V3,
        parent_zip=V3_ZIP,
    )
    write_json(root / "pilot_input.json", adapted["input"])
    write_json(root / "pilot_adapter_receipt.json", adapter_receipt)
    write_json(root / "pilot_runtime_receipt.json", adapted["receipt"])
    write_json(root / "pilot_zero_api_summary.json", result["summary"])
    write_json(root / "fake_run.json", result["run"])
    write_json(root / "replay_report.json", replay)
    write_json(root / "frozen_candidates.json", frozen)
    shutil.move(str(root / "ledger"), str(root / "fake_ledger"))
    ledger_path = root / "fake_ledger" / "provider_attempts.jsonl"
    return {
        "root": root,
        "input": adapted["input"],
        "run": result["run"],
        "summary": result["summary"],
        "replay": replay,
        "ledger_path": ledger_path,
        "binding": binding,
        "frozen": frozen,
        "local_fixture": local_fixture,
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


@pytest.mark.parametrize(
    "payload",
    (
        '{"key":1,"key":2}',
        '{"outer":{"key":1,"key":2}}',
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":-Infinity}',
        '{"value":1e9999}',
        '{"value":1} trailing',
        '[1,2,3]',
    ),
)
def test_strict_json_rejects_ambiguous_persisted_values(payload: str) -> None:
    with pytest.raises(StrictJSONError):
        loads_strict(payload, require_object=True)


def test_real_pilot_directory_and_zip_zero_api_equivalence() -> None:
    _require_external_dependencies(PILOT, PILOT_ZIP, V3, V3_ZIP)
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
    ledger_path = integration_run["ledger_path"]
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
    source = integration_run["root"] / "fake_ledger"
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


@pytest.mark.parametrize(
    "variant",
    ("extra_capture", "orphan_capture", "missing_capture", "reordered_capture", "attempt_drift"),
)
def test_direct_replay_rejects_full_ledger_contract_drift(
    integration_run: dict[str, Any], tmp_path: Path, variant: str
) -> None:
    forged = tmp_path / variant
    shutil.copytree(integration_run["root"] / "fake_ledger", forged)
    path = forged / "provider_attempts.jsonl"
    rows = _ledger_rows(path)
    capture_indexes = [
        index for index, row in enumerate(rows) if row["record_kind"] == "RAW_RESPONSE_CAPTURED"
    ]
    attempt_indexes = [
        index for index, row in enumerate(rows) if row["record_kind"] == "PROVIDER_ATTEMPT"
    ]
    if variant == "extra_capture":
        rows.insert(capture_indexes[0] + 1, copy.deepcopy(rows[capture_indexes[0]]))
    elif variant == "orphan_capture":
        rows.append(copy.deepcopy(rows[capture_indexes[0]]))
    elif variant == "missing_capture":
        del rows[capture_indexes[0]]
    elif variant == "reordered_capture":
        first, second = capture_indexes[:2]
        rows[first], rows[second] = rows[second], rows[first]
    else:
        rows[attempt_indexes[0]]["model_id"] = "drifted-model-pinned-v1"
    _write_ledger(path, rows)
    with pytest.raises(ValueError):
        replay_context_run(
            input_payload=integration_run["input"],
            original_run=integration_run["run"],
            ledger_root=forged,
        )


@pytest.mark.parametrize(
    "variant",
    ("top_duplicate", "nested_duplicate", "nan", "infinity"),
)
def test_provider_ledger_rejects_ambiguous_jsonl(
    integration_run: dict[str, Any], tmp_path: Path, variant: str
) -> None:
    forged = tmp_path / variant
    shutil.copytree(integration_run["root"] / "fake_ledger", forged)
    path = forged / "provider_attempts.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    if variant in {"top_duplicate", "nested_duplicate"}:
        index = next(
            i
            for i, line in enumerate(lines)
            if json.loads(line)["record_kind"] == "PROVIDER_ATTEMPT"
        )
        row = json.loads(lines[index])
        lines[index] = (
            _json_with_duplicate(row, "record_kind")
            if variant == "top_duplicate"
            else _json_with_duplicate(row, "input_tokens", nested_object="token_usage")
        )
    else:
        constant = "NaN" if variant == "nan" else "Infinity"
        lines[0] = f'{{"record_kind":"RAW_RESPONSE_CAPTURED","value":{constant}}}'
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(StrictJSONError):
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
    assert integration_run["local_fixture"]["status"] == FIXTURE_HOLD_STATUS
    assert integration_run["manifest"]["status"] == PACKAGE_SET_COMPLETE_STATUS
    assert integration_run["manifest"]["global_gate_action"] is None


def test_synthetic_package_set_is_distinct_from_official_complete(
    integration_run: dict[str, Any], tmp_path: Path
) -> None:
    output = tmp_path / "synthetic_packages"
    manifest = write_context_evidence_package_set(
        run_payload=integration_run["run"],
        frozen_candidates=integration_run["frozen"]["candidates"],
        binding=integration_run["binding"],
        output_directory=output,
        package_set_status=PACKAGE_SET_SYNTHETIC_STATUS,
    )
    report = json.loads((output / "projection_report.json").read_text(encoding="utf-8"))
    assert manifest["status"] == PACKAGE_SET_SYNTHETIC_STATUS
    assert report["status"] == PACKAGE_SET_SYNTHETIC_STATUS


def test_release_rejects_synthetic_package_set(
    integration_run: dict[str, Any], tmp_path: Path
) -> None:
    evidence = tmp_path / "evidence"
    shutil.copytree(integration_run["root"], evidence)
    shutil.rmtree(evidence / "context_evidence_packages")
    write_context_evidence_package_set(
        run_payload=integration_run["run"],
        frozen_candidates=integration_run["frozen"]["candidates"],
        binding=integration_run["binding"],
        output_directory=evidence / "context_evidence_packages",
        package_set_status=PACKAGE_SET_SYNTHETIC_STATUS,
    )
    _write_junit(evidence / "junit.xml", tests=1)
    with pytest.raises(ValueError, match="package manifest status mismatch"):
        build_integration_release(
            source_root=ROOT / "context_substitution",
            evidence_root=evidence,
            output_directory=tmp_path / "release",
            commands=("pytest",),
            known_gaps=("synthetic conformance only",),
        )


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
    forged["integrity"] = {}
    forged = seal_object(forged, integrity_key="binding_sha256")
    with pytest.raises(ValueError, match="authority commit mismatch"):
        project_context_evidence_packages(
            run_payload=integration_run["run"],
            frozen_candidates=integration_run["frozen"]["candidates"],
            binding=forged,
        )


def test_frozen_authority_receipt_matches_published_contract() -> None:
    _require_external_dependencies(contract_package_root(), DEFAULT_AUTHORITY_RECEIPT_PATH)
    receipt = validate_authority()
    assert receipt["authority_tag"] == AUTHORITY_TAG
    assert receipt["authority_commit"] == AUTHORITY_COMMIT
    assert receipt["manifest_sha256"] == CONTRACT_MANIFEST_SHA256
    published = validate_authority_receipt()
    assert published["integrity"]["self_sha256"] == AUTHORITY_RECEIPT_SELF_SHA256
    assert published["physical_sha256"] == AUTHORITY_RECEIPT_PHYSICAL_SHA256


def test_authority_receipt_tamper_is_rejected(tmp_path: Path) -> None:
    forged = tmp_path / "authority_receipt.json"
    payload = json.loads(DEFAULT_AUTHORITY_RECEIPT_PATH.read_text(encoding="utf-8"))
    payload["consumer_rule"] = "forged"
    write_json(forged, payload)
    with pytest.raises(AuthorityConformanceError, match="physical SHA mismatch"):
        validate_authority_receipt(forged)


@pytest.mark.parametrize(
    "payload",
    (
        '{"schema_id":"one","schema_id":"two"}',
        '{"integrity":{"self_sha256":"one","self_sha256":"two"}}',
    ),
)
def test_authority_receipt_rejects_duplicate_keys(
    tmp_path: Path, payload: str
) -> None:
    forged = tmp_path / "authority_receipt.json"
    forged.write_text(payload, encoding="utf-8", newline="\n")
    with pytest.raises(AuthorityConformanceError, match="duplicate object key"):
        validate_authority_receipt(forged)


@pytest.mark.parametrize(
    "payload",
    (
        '{"package_version":"1.1.0","package_version":"forged"}',
        '{"integrity":{"manifest_sha256":"one","manifest_sha256":"two"}}',
    ),
)
def test_authority_manifest_rejects_duplicate_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    (tmp_path / "manifest.json").write_text(payload, encoding="utf-8", newline="\n")
    monkeypatch.setenv("TERMINOLOGY_CONTRACTS_ROOT", str(tmp_path))
    with pytest.raises(AuthorityConformanceError, match="duplicate object key"):
        validate_authority()


def test_pending_review_pack_cannot_claim_frozen_authority() -> None:
    _require_external_dependencies(PILOT, V3, PENDING_REVIEW)
    with pytest.raises(ContractValidationError, match="Dataset authority must publish"):
        reviewed_support_to_context_substitution_input(
            PILOT,
            parent_v3_source=V3,
            source_split="development",
            review_artifact=PENDING_REVIEW,
        )


def test_c_local_candidate_fixture_cannot_enter_official_projection(
    integration_run: dict[str, Any],
) -> None:
    with pytest.raises(AuthorityConformanceError):
        project_context_evidence_packages(
            run_payload=integration_run["run"],
            frozen_candidates=integration_run["local_fixture"]["candidates"],
            binding=integration_run["binding"],
        )


@pytest.mark.parametrize("variant", ("foreign", "subset", "extra", "drift"))
def test_projection_rejects_foreign_subset_extra_or_drifted_ledger(
    integration_run: dict[str, Any], tmp_path: Path, variant: str
) -> None:
    forged_root = tmp_path / variant
    shutil.copytree(integration_run["root"] / "fake_ledger", forged_root)
    path = forged_root / "provider_attempts.jsonl"
    rows = _ledger_rows(path)
    attempt_indexes = [
        index for index, row in enumerate(rows) if row["record_kind"] == "PROVIDER_ATTEMPT"
    ]
    if variant == "foreign":
        for row in rows:
            if row["record_kind"] == "PROVIDER_ATTEMPT":
                row["run_id"] = "completely-foreign-run"
    elif variant == "subset":
        last = attempt_indexes[-1]
        remove = {last}
        if last > 0 and rows[last - 1]["record_kind"] == "RAW_RESPONSE_CAPTURED":
            remove.add(last - 1)
        rows = [row for index, row in enumerate(rows) if index not in remove]
    elif variant == "extra":
        last = attempt_indexes[-1]
        if last > 0 and rows[last - 1]["record_kind"] == "RAW_RESPONSE_CAPTURED":
            rows.extend((copy.deepcopy(rows[last - 1]), copy.deepcopy(rows[last])))
        else:
            rows.append(copy.deepcopy(rows[last]))
    else:
        rows[attempt_indexes[0]]["model_id"] = "foreign-model-pinned-v1"
    _write_ledger(path, rows)
    with pytest.raises(ValueError):
        build_projection_binding_from_ledger(
            run_payload=integration_run["run"], ledger_path=path
        )


def test_replay_rejects_raw_response_path_traversal(
    integration_run: dict[str, Any], tmp_path: Path
) -> None:
    forged_root = tmp_path / "traversal"
    shutil.copytree(integration_run["root"] / "fake_ledger", forged_root)
    path = forged_root / "provider_attempts.jsonl"
    rows = _ledger_rows(path)
    capture = next(row for row in rows if row["record_kind"] == "RAW_RESPONSE_CAPTURED")
    original_ref = capture["raw_response_ref"]
    raw_sha = capture["raw_response_sha256"]
    unsafe_ref = f"provider_responses/{raw_sha}/../{raw_sha}.txt"
    capture["raw_response_ref"] = unsafe_ref
    attempt = next(
        row
        for row in rows
        if row["record_kind"] == "PROVIDER_ATTEMPT"
        and row.get("raw_response_ref") == original_ref
    )
    attempt["raw_response_ref"] = unsafe_ref
    _write_ledger(path, rows)
    forged_run = copy.deepcopy(integration_run["run"])
    forged_attempt = next(
        row
        for row in forged_run["provider_attempts"]
        if row.get("raw_response_ref") == original_ref
    )
    forged_attempt["raw_response_ref"] = unsafe_ref
    forged_run["integrity"] = {}
    forged_run = seal_context_substitution_run(forged_run)
    with pytest.raises(ValueError, match="raw response.*escapes"):
        replay_context_run(
            input_payload=integration_run["input"],
            original_run=forged_run,
            ledger_root=forged_root,
        )


def test_asserted_gate_signals_reference_only_triggering_diagnostics(
    integration_run: dict[str, Any],
) -> None:
    asserted = [
        signal
        for package in integration_run["packages"]
        for signal in package["gate_signals"]
        if signal["asserted"]
    ]
    assert asserted and all(signal["evidence_refs"] for signal in asserted)
    for signal in asserted:
        refs = signal["evidence_refs"]
        if signal["gate_id"] in {
            "missing_contrastive_context",
            "incomplete_context_type_coverage",
        }:
            assert len(refs) == 1
            assert refs[0]["evidence_type"] == "SUPPORT_SET"
        elif signal["gate_id"] == "insufficient_evidence":
            assert len(refs) == 1
            assert refs[0]["evidence_type"] == "OTHER"
        else:
            assert all(ref["evidence_type"] == "CONTEXT" for ref in refs)
    candidates = {
        row["candidate_id"]: row for row in integration_run["run"]["candidates"]
    }
    for package in integration_run["packages"]:
        signal = next(
            row for row in package["gate_signals"] if row["gate_id"] == "judge_disagreement"
        )
        expected = sorted(
            row["context_id"]
            for row in candidates[package["candidate_key"]["candidate_id"]][
                "context_results"
            ]
            if _test_judges_disagree(row)
        )
        assert sorted(ref["evidence_id"] for ref in signal["evidence_refs"]) == expected


def test_dataset_finalized_selection_is_consumed_without_vote_resolution(
    tmp_path: Path,
) -> None:
    sense_source = {
        "term_id": "term-1",
        "sense_id": "sense-1",
        "source_term": "channel",
        "scope_id": "scope-1",
        "term_sense_sha256": HASH_A,
    }
    context_source = {"context_id": "ctx-1", "context_sha256": HASH_B}
    candidate_source = {
        "candidate_instance_id": "cand-1",
        "candidate_instance_sha256": "c" * 64,
    }
    sense = {
        **sense_source,
        "source_term_sense_sha256": sense_source["term_sense_sha256"],
        "effective_definition_en": "A finalized Dataset-owned definition.",
        "effective_part_of_speech": "noun",
    }
    sense.pop("term_sense_sha256")
    sense["reviewed_sense_contract_sha256"] = object_sha256(sense)
    selection = {
        "sense_relation": "SAME_SENSE",
        "context_type": "definition",
        "judgeability": "JUDGEABLE",
        "reason": "dataset authority finalized row",
        "review_row_sha256": "d" * 64,
    }
    context = {
        "context_id": "ctx-1",
        "source_record_sha256": HASH_B,
        "reviewed_selection": selection,
    }
    context["row_sha256"] = object_sha256(context)
    candidate = {
        "candidate_instance_id": "cand-1",
        "source_record_sha256": "c" * 64,
        "review_status": "REVIEWED_FINAL",
    }
    candidate["row_sha256"] = object_sha256(candidate)
    artifact = {
        "schema_id": ANNOTATION_SCHEMA_ID,
        "schema_version": ANNOTATION_SCHEMA_VERSION,
        "status": "COMPLETE_IMMUTABLE",
        "authority_owner": ANNOTATION_POLICY_ID,
        "policy_id": "dataset-adjudication-policy-v1",
        "source_pilot_manifest_sha256": "e" * 64,
        "effective_sense_contract_ref": "artifact://dataset/effective-sense",
        "effective_sense_contract_sha256": "f" * 64,
        "sense_inventory_version": "dataset-reviewed-v1",
        "senses": [sense],
        "contexts": [context],
        "candidates": [candidate],
        "final_glossary_decision": None,
        "integrity": {},
    }
    artifact = seal_object(artifact, integrity_key="self_sha256")
    write_json(tmp_path / FINALIZED_SELECTION_FILE, artifact)
    result = load_frozen_review_selection(
        tmp_path,
        source_pilot_manifest_sha256="e" * 64,
        pilot_terms=[sense_source],
        pilot_contexts=[context_source],
        pilot_candidates=[candidate_source],
    )
    assert result["contexts"]["ctx-1"] == selection
    assert result["candidate_review_count"] == 1


@pytest.mark.parametrize(
    "payload",
    (
        '{"schema_id":"one","schema_id":"two"}',
        '{"review":{"status":"one","status":"two"}}',
    ),
)
def test_finalized_review_rejects_duplicate_keys(
    tmp_path: Path, payload: str
) -> None:
    (tmp_path / FINALIZED_SELECTION_FILE).write_text(
        payload,
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ContractValidationError, match="duplicate object key"):
        load_frozen_review_selection(
            tmp_path,
            source_pilot_manifest_sha256="e" * 64,
        )


@pytest.mark.parametrize(
    "payload",
    (
        '{"status":"PASS","status":"FAIL"}',
        '{"integrity":{"summary_sha256":"one","summary_sha256":"two"}}',
        '{"provider_attempt_count":NaN}',
        '{"provider_attempt_count":Infinity}',
    ),
)
def test_release_evidence_rejects_ambiguous_json(
    integration_run: dict[str, Any], tmp_path: Path, payload: str
) -> None:
    forged = tmp_path / "evidence"
    shutil.copytree(integration_run["root"], forged)
    _write_junit(forged / "junit.xml", tests=1)
    (forged / "pilot_zero_api_summary.json").write_text(
        payload,
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(StrictJSONError):
        build_integration_release(
            source_root=ROOT / "context_substitution",
            evidence_root=forged,
            output_directory=tmp_path / "release",
            commands=("pytest",),
            known_gaps=("strict JSON regression",),
        )


@pytest.mark.parametrize(
    ("tests", "failures", "errors", "skipped", "message"),
    (
        (0, 0, 0, 0, "no tests executed"),
        (22, 1, 0, 0, "test suite did not pass"),
        (22, 0, 0, 1, "unexpected skipped tests"),
    ),
)
def test_release_rejects_zero_or_failing_junit(
    integration_run: dict[str, Any],
    tmp_path: Path,
    tests: int,
    failures: int,
    errors: int,
    skipped: int,
    message: str,
) -> None:
    _write_junit(
        integration_run["root"] / "junit.xml",
        tests=tests,
        failures=failures,
        errors=errors,
        skipped=skipped,
    )
    with pytest.raises(ValueError, match=message):
        build_integration_release(
            source_root=ROOT / "context_substitution",
            evidence_root=integration_run["root"],
            output_directory=tmp_path,
            commands=("pytest",),
            known_gaps=("real Dataset/E package availability",),
        )


def test_release_rejects_validly_resealed_fake_summary_drift(
    integration_run: dict[str, Any], tmp_path: Path
) -> None:
    forged = tmp_path / "evidence"
    shutil.copytree(integration_run["root"], forged)
    _write_junit(forged / "junit.xml", tests=22)
    summary = json.loads(
        (forged / "pilot_zero_api_summary.json").read_text(encoding="utf-8")
    )
    summary["provider_attempt_count"] += 1
    summary["integrity"] = {}
    summary = seal_object(summary, integrity_key="summary_sha256")
    write_json(forged / "pilot_zero_api_summary.json", summary)
    completed = _run_release_cli(forged, tmp_path / "release")
    assert completed.returncode != 0
    assert "provider attempt count mismatch" in completed.stderr


def test_release_builder_emits_semantically_valid_rc2(
    integration_run: dict[str, Any], tmp_path: Path
) -> None:
    _write_junit(integration_run["root"] / "junit.xml", tests=22)
    completed = _run_release_cli(integration_run["root"], tmp_path / "first")
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "INTEGRATION_READY_ZERO_API"
    assert result["junit"] == {"tests": 22, "failures": 0, "errors": 0, "skipped": 0}
    assert Path(result["archive"]).is_file()
    repeated = _run_release_cli(integration_run["root"], tmp_path / "second")
    assert repeated.returncode == 0, repeated.stderr
    repeated_result = json.loads(repeated.stdout)
    assert repeated_result["archive_sha256"] == result["archive_sha256"]


def _run_release_cli(evidence_root: Path, output_directory: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "context_substitution.v2",
            "integration-release",
            "--evidence-root",
            str(evidence_root),
            "--output-directory",
            str(output_directory),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _ledger_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_ledger(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )


def _json_with_duplicate(
    value: Mapping[str, Any],
    duplicate_key: str,
    *,
    nested_object: str | None = None,
) -> str:
    def encode_object(row: Mapping[str, Any], repeated: str) -> str:
        parts: list[str] = []
        found = False
        for key, item in row.items():
            encoded = json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            pair = f"{json.dumps(key)}:{encoded}"
            parts.append(pair)
            if key == repeated:
                parts.append(pair)
                found = True
        if not found:
            raise AssertionError(f"duplicate test key is missing: {repeated}")
        return "{" + ",".join(parts) + "}"

    if nested_object is None:
        return encode_object(value, duplicate_key)
    parts: list[str] = []
    found = False
    for key, item in value.items():
        if key == nested_object:
            if not isinstance(item, Mapping):
                raise AssertionError(f"nested duplicate target is not an object: {key}")
            encoded = encode_object(item, duplicate_key)
            found = True
        else:
            encoded = json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        parts.append(f"{json.dumps(key)}:{encoded}")
    if not found:
        raise AssertionError(f"nested duplicate object is missing: {nested_object}")
    return "{" + ",".join(parts) + "}"


def _write_junit(
    path: Path,
    *,
    tests: int,
    failures: int = 0,
    errors: int = 0,
    skipped: int = 0,
) -> None:
    suite = ElementTree.Element(
        "testsuite",
        {
            "tests": str(tests),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": str(skipped),
        },
    )
    ElementTree.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def _test_judges_disagree(row: Mapping[str, Any]) -> bool:
    secondary = row.get("secondary_judge")
    if secondary is None:
        return False
    secondary_output = secondary["output"]
    if secondary_output["judgeability"] != "JUDGEABLE":
        return True
    primary_label = compute_context_result(row["primary_judge"]["output"])[1]
    secondary_label = compute_context_result(secondary_output)[1]
    return merge_judge_labels(primary_label, secondary_label)[1]


def test_frozen_selector_uses_reviewed_rows_and_requires_complete_cover() -> None:
    _require_external_dependencies(PILOT, V3)
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
