from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from vietnamese_attestation.v1.live.aggregation import aggregate_candidate
from vietnamese_attestation.v1.live.common import LiveSchemaError, canonical_sha256, seal
from vietnamese_attestation.v1.live.fixtures import build_fixture_workspace
from vietnamese_attestation.v1.live.judge import make_judge_response
from vietnamese_attestation.v1.live.judge import MockProviderAdapter
from vietnamese_attestation.v1.live.schemas import validate_provider_role_plan
from vietnamese_attestation.v1.live.service import compute_run_spec_id
from vietnamese_attestation.live_tests.test_live_narrow_rework_semantics import _discovery_service


def test_preflight_binds_exact_loaded_authority_and_input_contract(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    for field in ("registry_self_sha256", "snapshot_manifest_sha256", "input_contract_sha256"):
        request = copy.deepcopy(workspace["request"])
        request["authority_refs"][field] = "f" * 64
        request["run_spec_id"] = compute_run_spec_id(request)
        result = workspace["service"].preflight(request)
        assert result["status"] == "BLOCKED"
        assert f"REQUEST_{field.upper()}_MISMATCH" in result["blockers"]
        assert result["provider_calls"] == 0


def test_final_uncertain_is_unjudgeable() -> None:
    evidence = {
        "evidence_id": "e1",
        "duplicate_cluster_id": "c1",
        "source_id": "s1",
        "organization": "o1",
    }
    judge = make_judge_response(
        concept_relation="UNCERTAIN",
        domain_relation="MATCH",
        usage_type="TECHNICAL_TERM",
        judgeability="JUDGEABLE",
        evidence_span="term",
        reason_codes=["FINAL_UNCERTAIN"],
    )
    result = aggregate_candidate(
        [evidence],
        {"e1": judge},
        policy={"min_coverage": 0.5, "min_same_clusters_for_attested": 1, "min_organizations_for_attested": 1},
        coverage_fraction=1.0,
    )
    assert result["status"] == "ATTESTATION_UNJUDGEABLE"


def test_generation_config_is_strict_and_bound_to_model_event(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    invalid = copy.deepcopy(workspace["policy_bundle"]["provider_role_plan"])
    invalid["roles"][0]["generation_config"]["temperature"] = "hot"
    invalid = seal({**invalid, "integrity": {}})
    with pytest.raises(LiveSchemaError, match="temperature must be numeric"):
        validate_provider_role_plan(invalid)

    result = workspace["service"].create_run(workspace["request"])
    events = [json.loads(line) for line in (Path(result["run_root"]) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    model = next(row for row in events if row["event_kind"] == "E_MODEL_REQUEST")
    role = workspace["policy_bundle"]["provider_role_plan"]["roles"][0]
    assert model["payload"]["generation_config"] == role["generation_config"]
    assert model["payload"]["provider_role_plan_sha256"] == workspace["request"]["provider_role_plan_sha256"]


def test_production_shaped_mock_adapter_refuses_non_live_role() -> None:
    adapter = MockProviderAdapter({"e1": make_judge_response(concept_relation="SAME", domain_relation="MATCH", usage_type="TECHNICAL_TERM", judgeability="JUDGEABLE", evidence_span="x")})
    with pytest.raises(LiveSchemaError, match="LIVE_PROVIDER"):
        adapter.invoke({"evidence_id": "e1", "snippet_original": "x"}, role_config={"mode": "ZERO_PROVIDER_FIXTURE"})
    assert adapter.call_count == 0


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("redirect", "MAX_REDIRECT_HOPS_EXCEEDED"),
        ("download", "MAX_DOWNLOAD_BYTES_EXCEEDED"),
    ],
)
def test_retrieval_caps_stop_before_evidence_acceptance(tmp_path: Path, mutation: str, expected_code: str) -> None:
    service, request = _discovery_service(tmp_path, copied=True)
    first_url = sorted(service.fetcher.documents)[0]
    if mutation == "redirect":
        service.fetcher.documents[first_url]["redirect_chain"] = [f"fixture://hop/{i}" for i in range(4)]
    else:
        service.fetcher.documents[first_url]["body"] = b"x" * 2_000_001
    result = service.create_run(request)
    assert result["status"] == "STOPPED"
    events = [json.loads(line) for line in (Path(result["run_root"]) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["payload"]["code"] == expected_code
