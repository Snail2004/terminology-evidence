from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path

import pytest

from vietnamese_attestation.live_tests.test_live_narrow_rework_authority import _authority_fixture
from vietnamese_attestation.v1.live.authority_adapter.adapter import (
    PROTOCOL_SCHEMA_ROLES,
    load_authority_bundle,
    make_trusted_authority_profile,
)
from vietnamese_attestation.v1.live.common import canonical_bytes, canonical_sha256, file_sha256, load_object, seal
from vietnamese_attestation.v1.live.fixtures import build_fixture_workspace
from vietnamese_attestation.v1.live.judge import MockProviderAdapter, judge_request_sha256, make_judge_request
from vietnamese_attestation.v1.live.policies import validate_policy_bundle
from vietnamese_attestation.v1.live.retrieval import extract_snapshot_evidence
from vietnamese_attestation.v1.live.service import (
    RECORDED_PROVIDER_CONFORMANCE,
    ELiveService,
    compute_run_spec_id,
)


E_COMMIT = "6ff12925c3721ffeae5fced008fddc798cf095df"
E_TREE = "ff36542afa8d78b496d2404793c09ab9f6c8ad68"
E05_DELIVERY = Path(
    os.environ.get(
        "E05_EXACT_INPUT_DELIVERY",
        r"C:\work\terminology-evidence-artifacts\e05-exact-integration-input-v1\delivery.zip",
    )
)


def test_recorded_provider_conformance_and_nonzero_telemetry(tmp_path: Path) -> None:
    service, request, adapter = _recorded_conformance_service(tmp_path, unknown=False)
    result = service.create_run(request)
    assert result["status"] == "COMPLETED"
    assert adapter.call_count == 2
    assert result["provider_calls"] == 2
    assert result["physical_requests"] == 2
    assert result["input_tokens"] == 22
    assert result["output_tokens"] == 14
    assert result["reasoning_tokens"] == 6
    assert result["total_tokens"] == 42
    assert result["total_cost"] == pytest.approx(0.04)
    assert result["latency_total_ms"] == 50
    evidence_ledger = load_object(Path(result["run_root"]) / "evidence_ledger.json")
    assert evidence_ledger["provider_calls"] == result["provider_calls"]
    assert evidence_ledger["total_tokens"] == result["total_tokens"]
    assert evidence_ledger["total_cost"] == result["total_cost"]


def test_unknown_physical_outcome_stops_without_retry(tmp_path: Path) -> None:
    service, request, adapter = _recorded_conformance_service(tmp_path, unknown=True)
    result = service.create_run(request)
    assert result["status"] == "STOPPED"
    assert adapter.call_count == 1
    assert result["provider_calls"] == 1
    assert result["retry_count"] == 0
    events = (Path(result["run_root"]) / "events.jsonl").read_text(encoding="utf-8")
    assert "UNKNOWN_PHYSICAL_OUTCOME" in events


def test_known_retryable_failure_is_bounded_and_accounted(tmp_path: Path) -> None:
    service, request, adapter = _recorded_conformance_service(tmp_path, unknown=False, retry=True)
    result = service.create_run(request)
    assert result["status"] == "COMPLETED"
    assert adapter.call_count == 4
    assert result["provider_calls"] == 4
    assert result["retry_count"] == 2
    assert result["total_tokens"] == 84
    assert result["total_cost"] == pytest.approx(0.08)


def test_production_rejects_ram_bundle_and_arbitrary_schema(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    with pytest.raises(Exception, match="only the exact E-05 Main delivery"):
        ELiveService(
            root=tmp_path / "runs",
            registry=workspace["registry"], snapshot_root=workspace["snapshot_root"],
            policy_bundle=workspace["policy_bundle"], authorization_receipt={},
            authorized_cohort_id="fixture-cohort-v1", authorized_candidate_ids=["candidate_model"],
            execution_mode="PRODUCTION_AUTHORITY", authority_bundle={"forged": True},
            production_authorization_schema=tmp_path / "forged.schema.json",
            provider_adapter=MockProviderAdapter({}),
        )


def test_production_exact_e05_delivery_remains_run_authorized_hold(
    tmp_path: Path,
) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    service = ELiveService(
        root=tmp_path / "runs",
        registry=workspace["registry"],
        snapshot_root=workspace["snapshot_root"],
        policy_bundle=workspace["policy_bundle"],
        authorization_receipt={},
        authorized_cohort_id="fixture-cohort-v1",
        authorized_candidate_ids=["candidate_model"],
        execution_mode="PRODUCTION_AUTHORITY",
        e05_delivery_path=E05_DELIVERY,
    )
    result = service.preflight(workspace["request"])
    assert result["status"] == "BLOCKED"
    assert "E05_RUN_AUTHORIZED_NO" in result["blockers"]
    assert result["provider_calls"] == 0
    assert result["checks"]["network_calls"] == 0


def _recorded_conformance_service(tmp_path: Path, *, unknown: bool, retry: bool = False) -> tuple[ELiveService, dict, MockProviderAdapter]:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    policies = copy.deepcopy(workspace["policy_bundle"])
    for role in policies["provider_role_plan"]["roles"]:
        role["mode"] = "LIVE_PROVIDER"
        if retry:
            role["max_retries"] = 1
    policies["provider_role_plan"] = seal({**policies["provider_role_plan"], "integrity": {}})
    policy_hashes = validate_policy_bundle(policies)
    request = copy.deepcopy(workspace["request"])
    request["provider_role_plan_sha256"] = policy_hashes["provider_role_plan"]
    request["run_spec_id"] = compute_run_spec_id(request)

    authority = _recorded_authority_fixture(
        tmp_path / "authority", request=request, workspace=workspace,
        policy_hashes=policy_hashes,
    )
    evidence = extract_snapshot_evidence(
        workspace["snapshot_root"], candidate_id=request["candidate_id"], sense_id=request["sense_id"],
        term_en=request["term_en"], candidate_vi=request["candidate_vi"],
    )
    results = {}
    for index, row in enumerate(evidence):
        role = policies["provider_role_plan"]["roles"][0]["semantic_role"]
        judge_request = make_judge_request(
            candidate_id=request["candidate_id"], sense_id=request["sense_id"], evidence_id=row["evidence_id"],
            term_en=request["term_en"], candidate_vi=request["candidate_vi"], sense_definition=request["sense_definition"],
            snippet_original=row["snippet_original"], snippet_masked=row["snippet_masked"], source_id=row["source_id"],
            source_tier=row["source_tier"], semantic_role=role,
        )
        response = workspace["service"].judge.responses[row["evidence_id"]]
        outcome = "UNKNOWN_PHYSICAL_OUTCOME" if unknown else "SUCCESS"
        response_value = None if outcome != "SUCCESS" else response
        response_sha = canonical_sha256(response_value)
        success = {
            "provider_request_id": f"provider-request-{index + 1}", "outcome": outcome,
            "response": response_value, "request_sha256": judge_request_sha256(judge_request),
            "response_physical_sha256": hashlib.sha256(canonical_bytes(response_value)).hexdigest(),
            "response_canonical_sha256": response_sha,
            "started_at": f"2026-07-30T00:00:0{index}.000Z", "completed_at": f"2026-07-30T00:00:0{index}.025Z",
            "latency_ms": 25, "input_tokens": 11, "output_tokens": 7, "reasoning_tokens": 3,
            "total_tokens": 21, "cost": 0.02, "currency": "USD", "physical_request_count": 1, "retry_index": 0,
        }
        if retry:
            first = dict(success)
            first.update({"provider_request_id": f"provider-retry-{index + 1}", "outcome": "RETRYABLE_FAILURE", "response": None,
                          "response_physical_sha256": hashlib.sha256(canonical_bytes(None)).hexdigest(),
                          "response_canonical_sha256": canonical_sha256(None)})
            success["retry_index"] = 1
            results[row["evidence_id"]] = [first, success]
        else:
            results[row["evidence_id"]] = success
    adapter = MockProviderAdapter(results)
    service = ELiveService(
        root=tmp_path / "production-runs", registry=workspace["registry"], snapshot_root=workspace["snapshot_root"],
        policy_bundle=policies, authorization_receipt={}, authorized_cohort_id="fixture-cohort-v1",
        authorized_candidate_ids=["candidate_model"], execution_mode=RECORDED_PROVIDER_CONFORMANCE,
        production_authority_inputs=authority, provider_adapter=adapter,
    )
    return service, request, adapter


def _recorded_authority_fixture(root: Path, *, request: dict, workspace: dict, policy_hashes: dict) -> dict:
    fixture = _authority_fixture(root, production=True)
    auth_role = "LIVE_AUTHORIZATION_RECEIPT"
    auth_schema = _authorization_schema()
    auth_schema_path = fixture["schema_paths"][auth_role]
    auth_schema_path.write_bytes(canonical_bytes(auth_schema))
    old_profile = load_object(fixture["profile_path"])
    protocol_bindings = []
    for role in sorted(PROTOCOL_SCHEMA_ROLES):
        path = fixture["schema_paths"][role]
        schema = load_object(path)
        protocol_bindings.append({"role": role, "artifact_ref": schema["$id"], "artifact_physical_sha256": file_sha256(path), "artifact_self_sha256": canonical_sha256(schema)})
    profile = make_trusted_authority_profile(
        trusted_issuers=old_profile["trusted_issuers"], trusted_authorities=old_profile["trusted_authorities"],
        receipt_bindings=old_profile["receipt_bindings"], protocol_schema_bindings=protocol_bindings,
        status="MAIN_PINNED_RUNTIME_AUTHORITY",
    )
    fixture["profile_path"].write_bytes(canonical_bytes(profile))
    bundle = load_authority_bundle(
        profile_path=fixture["profile_path"], receipt_paths=fixture["receipt_paths"], protocol_schema_paths=fixture["schema_paths"],
        execution_mode="PRODUCTION_AUTHORITY", expected_profile_physical_sha256=file_sha256(fixture["profile_path"]),
    )
    binding = {
        "cohort_id": "fixture-cohort-v1", "candidate_ids": ["candidate_model"], "run_id": request["run_id"],
        "phase_id": request["phase_id"], "run_spec_id": request["run_spec_id"],
        "registry_self_sha256": workspace["registry"]["integrity"]["self_sha256"],
        "snapshot_manifest_sha256": workspace["service"].snapshot["integrity"]["self_sha256"],
        "policy_hashes": policy_hashes, "e_commit": E_COMMIT, "e_tree": E_TREE,
        "provider_role_plan_sha256": policy_hashes["provider_role_plan"],
        "budget_sha256": canonical_sha256(request["budget"]),
        "authority_bundle_self_sha256": bundle["integrity"]["self_sha256"],
    }
    receipt = seal({
        "schema_id": "LiveAuthorizationReceiptV1_1", "schema_version": "1.1.0-draft.4-e-binding",
        "receipt_id": "main-e-authorized-fixture", "authorization_status": "RUN_AUTHORIZED", "test_only": False,
        "phase_id": request["phase_id"], "issued_at": "2026-07-30T00:00:00Z", "valid_from": "2026-07-29T00:00:00Z",
        "valid_until": "2099-01-01T00:00:00Z", "issuer_id": "main-maintainer", "authority_id": "terminology-evidence-main",
        "e_execution_binding": binding, "integrity": {},
    })
    receipt_path = root / "live_authorization_receipt.json"
    receipt_path.write_bytes(canonical_bytes(receipt))
    return {
        "profile_path": fixture["profile_path"], "expected_profile_physical_sha256": file_sha256(fixture["profile_path"]),
        "receipt_paths": fixture["receipt_paths"], "protocol_schema_paths": fixture["schema_paths"],
        "authorization_receipt_path": receipt_path, "expected_authorization_receipt_physical_sha256": file_sha256(receipt_path),
        "expected_e_commit": E_COMMIT, "expected_e_tree": E_TREE,
    }


def _authorization_schema() -> dict:
    sha = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.invalid/e/live_authorization_receipt.schema.json",
        "type": "object", "additionalProperties": False,
        "required": ["schema_id", "schema_version", "receipt_id", "authorization_status", "test_only", "phase_id", "issued_at", "valid_from", "valid_until", "issuer_id", "authority_id", "e_execution_binding", "integrity"],
        "properties": {
            "schema_id": {"const": "LiveAuthorizationReceiptV1_1"}, "schema_version": {"const": "1.1.0-draft.4-e-binding"},
            "receipt_id": {"type": "string"}, "authorization_status": {"const": "RUN_AUTHORIZED"}, "test_only": {"const": False},
            "phase_id": {"type": "string"}, "issued_at": {"type": "string"}, "valid_from": {"type": "string"}, "valid_until": {"type": "string"},
            "issuer_id": {"type": "string"}, "authority_id": {"type": "string"},
            "e_execution_binding": {"type": "object"},
            "integrity": {"type": "object", "additionalProperties": False, "required": ["self_sha256"], "properties": {"self_sha256": sha}},
        },
    }
