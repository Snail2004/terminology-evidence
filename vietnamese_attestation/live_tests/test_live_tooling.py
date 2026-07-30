from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vietnamese_attestation.v1.live.aggregation import aggregate_candidate
from vietnamese_attestation.v1.live.common import LiveSchemaError, canonical_bytes, load_object
from vietnamese_attestation.v1.live.fixtures import build_fixture_workspace
from vietnamese_attestation.v1.live.judge import FixtureJudge, make_judge_request, make_judge_response
from vietnamese_attestation.v1.live.ledger import EventLedger, verify_event_chain
from vietnamese_attestation.v1.live.registry import admit_source, make_registry
from vietnamese_attestation.v1.live.retrieval import FixtureDiscovery, FixtureFetcher, FixtureTransientFetchError, UnknownPhysicalOutcome
from vietnamese_attestation.v1.live.replay import replay_run
from vietnamese_attestation.v1.live.snapshot import build_snapshot, verify_snapshot, zip_snapshot
from vietnamese_attestation.v1.live.schemas import LOCAL_STATUSES
from vietnamese_attestation.v1.live.schemas import compute_run_spec_id, validate_judge_response
from vietnamese_attestation.v1.live.policies import make_budget
from vietnamese_attestation.v1.live.schema_tools import SCHEMA_CATALOG, export_schemas


def test_fixture_run_is_zero_provider_and_replayable(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    result = workspace["service"].create_run(workspace["request"])
    assert result["status"] == "COMPLETED"
    assert result["local_status"] == "ATTESTED"
    assert result["provider_calls"] == 0
    assert result["network_calls"] == 0
    assert result["package"]["final_glossary_decision"] is None
    replay = workspace["service"].replay(result["run_id"])
    assert replay["status"] == "REPLAYED_ZERO_PROVIDER"
    assert replay["provider_calls"] == 0
    assert replay["network_calls"] == 0


def test_preflight_blocked_emits_no_run_or_ledger(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    request = dict(workspace["request"])
    request["retrieval_policy_sha256"] = "0" * 64
    response = workspace["service"].preflight(request)
    assert response["status"] == "BLOCKED"
    assert response["provider_calls"] == 0
    assert "RETRIEVAL_POLICY_SHA256_MISMATCH" in response["blockers"]
    assert not (workspace["run_root"] / "runs" / request["run_id"]).exists()


def test_internal_endpoint_shapes_are_transport_independent(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    response = workspace["service"].handle("POST", "/e/v1/preflight", workspace["request"])
    assert response["status"] == "READY"
    run = workspace["service"].handle("POST", "/e/v1/runs", workspace["request"])
    run_id = run["run_id"]
    assert workspace["service"].handle("GET", f"/e/v1/runs/{run_id}")["status"] == "COMPLETED"
    assert workspace["service"].handle("GET", f"/e/v1/runs/{run_id}/artifacts")["artifacts"]
    assert workspace["service"].handle("POST", "/e/v1/replay", {"run_id": run_id})["provider_calls"] == 0


def test_corpus_first_does_not_issue_discovery_query(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    discovery = FixtureDiscovery({"candidate_model": ["fixture://one.example/lead"]})
    workspace["service"].discovery = discovery
    workspace["service"].create_run(workspace["request"])
    assert discovery.query_count == 0


def test_snapshot_two_builds_have_identical_zip_bytes(tmp_path: Path) -> None:
    first = build_fixture_workspace(tmp_path / "first")
    second_root = tmp_path / "second"
    second = build_fixture_workspace(second_root)
    first_zip = zip_snapshot(first["snapshot_root"], tmp_path / "first.zip")
    second_zip = zip_snapshot(second["snapshot_root"], tmp_path / "second.zip")
    assert first_zip.read_bytes() == second_zip.read_bytes()
    assert verify_snapshot(first_zip)["integrity"]["self_sha256"] == verify_snapshot(second_zip)["integrity"]["self_sha256"]


def test_snapshot_rejects_unlisted_source_file(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    (workspace["source_root"] / "unlisted.html").write_text("unlisted", encoding="utf-8")
    with pytest.raises(LiveSchemaError, match="enumerate exactly"):
        build_snapshot(
            workspace["source_root"],
            tmp_path / "bad-snapshot",
            registry=workspace["registry"],
            retrieval_policy=workspace["policy_bundle"]["retrieval_policy"],
            acquisition_receipt=load_object(workspace["snapshot_root"] / "acquisition_receipt.json"),
        )


def test_registry_rejects_unknown_source_redirect_and_content() -> None:
    registry = make_registry(
        [{"source_id": "one", "host_pattern": "one.example", "source_tier": "A", "source_type": "FIXTURE", "allowed_content_types": ["text/html"], "allowed": True, "domain_tags": ["nlp"]}],
        authority_receipt_ref="authority.json",
        authority_receipt_sha256=hashlib.sha256(b"authority").hexdigest(),
    )
    assert admit_source(registry, source_id="one", canonical_url="fixture://one.example/a", final_url="fixture://one.example/a", content_type="text/html")["source_id"] == "one"
    with pytest.raises(LiveSchemaError):
        admit_source(registry, source_id="missing", canonical_url="fixture://one.example/a", final_url="fixture://one.example/a", content_type="text/html")
    with pytest.raises(LiveSchemaError):
        admit_source(registry, source_id="one", canonical_url="fixture://one.example/a", final_url="fixture://evil.example/a", content_type="text/html")
    with pytest.raises(LiveSchemaError):
        admit_source(registry, source_id="one", canonical_url="fixture://one.example/a", final_url="fixture://one.example/a", content_type="application/pdf")


def test_registry_without_external_authority_is_rejected() -> None:
    registry = make_registry(
        [{"source_id": "one", "host_pattern": "one.example", "source_tier": "A", "source_type": "FIXTURE", "allowed_content_types": ["text/html"], "allowed": True, "domain_tags": ["nlp"]}],
        authority_receipt_ref="authority.json",
        authority_receipt_sha256=hashlib.sha256(b"authority").hexdigest(),
    )
    registry["authority"]["approval_status"] = "SELF_HASH_ONLY"
    with pytest.raises(LiveSchemaError):
        from vietnamese_attestation.v1.live.registry import validate_registry
        validate_registry(registry)


def test_discovery_is_lead_only_and_fetch_unknown_outcome_stops() -> None:
    discovery = FixtureDiscovery({"candidate": ["fixture://one.example/a"]})
    leads = discovery.query('"ứng viên"', candidate_id="candidate", max_queries=2)
    assert leads[0]["url"].startswith("fixture://")
    fetcher = FixtureFetcher({"fixture://one.example/a": {"physical_outcome": "UNKNOWN"}})
    with pytest.raises(UnknownPhysicalOutcome):
        fetcher.fetch("fixture://one.example/a")


def test_direct_fetch_retry_and_redirect_are_physical_attempts() -> None:
    fetcher = FixtureFetcher(
        {
            "fixture://one.example/a": {
                "body": b"fixture bytes",
                "content_type": "text/plain",
                "failures_before_success": 1,
                "redirect_chain": ["fixture://one.example/r"],
            }
        }
    )
    with pytest.raises(FixtureTransientFetchError):
        fetcher.fetch("fixture://one.example/a", retry_index=0)
    document = fetcher.fetch("fixture://one.example/a", retry_index=1)
    assert fetcher.request_count == 2
    assert document.redirect_chain == ("fixture://one.example/r",)


def test_ledger_chain_detects_tamper() -> None:
    ledger = EventLedger(run_id="run", phase_id="phase", clock=lambda: "2026-07-30T00:00:00Z")
    ledger.append("E_DISCOVERY_QUERY", candidate_replicate_id="candidate", semantic_role="DISCOVERY", semantic_call_id="call", transport_attempt_id="transport", payload={"template_id": "exact_candidate", "query_class": "EXACT_CANDIDATE", "template_sha256": "1" * 64, "rendered_query": '"ứng viên"', "rendered_query_sha256": "2" * 64, "result_count": 0, "lead_urls": [], "is_evidence": False})
    assert len(verify_event_chain(ledger.events, run_id="run")) == 1
    tampered = [dict(ledger.events[0])]
    tampered[0]["payload"] = {"is_evidence": True}
    with pytest.raises(LiveSchemaError):
        verify_event_chain(tampered, run_id="run")


def test_conditional_secondary_is_used_only_for_uncertain_primary() -> None:
    request = make_judge_request(candidate_id="c", sense_id="s", evidence_id="e", term_en="term", candidate_vi="ứng viên", sense_definition="definition", snippet_original="ứng viên được dùng trong kỹ thuật", snippet_masked="[CANDIDATE] được dùng trong kỹ thuật", source_id="source", source_tier="A")
    primary = make_judge_response(concept_relation="UNCERTAIN", domain_relation="MATCH", usage_type="TECHNICAL_TERM", judgeability="JUDGEABLE", evidence_span="ứng viên", snippet=request["snippet_original"])
    secondary = make_judge_response(concept_relation="SAME", domain_relation="MATCH", usage_type="TECHNICAL_TERM", judgeability="JUDGEABLE", evidence_span="ứng viên", snippet=request["snippet_original"])
    judge = FixtureJudge({"e": {"PRIMARY_ATTESTATION_JUDGE": primary, "SECONDARY_ATTESTATION_JUDGE": secondary}})
    role, response = judge.route(request)
    assert role == "SECONDARY_ATTESTATION_JUDGE"
    assert response["concept_relation"] == "SAME"


def test_judge_response_rejects_final_action_field() -> None:
    response = make_judge_response(concept_relation="SAME", domain_relation="MATCH", usage_type="TECHNICAL_TERM", judgeability="JUDGEABLE", evidence_span="ứng viên", snippet="ứng viên")
    response["final_status"] = "ATTESTED"
    with pytest.raises(LiveSchemaError, match="final/action"):
        validate_judge_response(response, snippet="ứng viên")


def _row(index: int, cluster: str, organization: str = "org") -> dict[str, object]:
    return {"evidence_id": f"e{index}", "independent_cluster_id": cluster, "duplicate_cluster_id": cluster, "organization": organization, "organization_id": organization, "source_id": organization, "source_tier": "A", "snippet_original": "mô hình ngôn ngữ trong kỹ thuật", "snippet_masked": "[CANDIDATE] trong kỹ thuật"}


def _judge(relation: str, *, judgeability: str = "JUDGEABLE") -> dict[str, object]:
    return make_judge_response(concept_relation=relation, domain_relation="MATCH", usage_type="TECHNICAL_TERM", judgeability=judgeability, evidence_span="mô hình ngôn ngữ" if judgeability == "JUDGEABLE" else "", snippet="mô hình ngôn ngữ trong kỹ thuật")


def test_aggregation_emits_all_five_local_statuses() -> None:
    policy = {"min_coverage": 0.5, "min_same_clusters_for_attested": 2, "min_organizations_for_attested": 2}
    assert aggregate_candidate([], {}, policy=policy, coverage_fraction=0.0)["status"] == "ATTESTATION_UNJUDGEABLE"
    conflict_rows = [_row(1, "c1", "o1"), _row(2, "c2", "o2")]
    assert aggregate_candidate(conflict_rows, {"e1": _judge("SAME"), "e2": _judge("DIFFERENT")}, policy=policy, coverage_fraction=1.0)["status"] == "CONFLICTING_ATTESTATION"
    same_rows = [_row(1, "c1", "o1"), _row(2, "c2", "o2")]
    assert aggregate_candidate(same_rows, {"e1": _judge("SAME"), "e2": _judge("SAME")}, policy=policy, coverage_fraction=1.0)["status"] == "ATTESTED"
    assert aggregate_candidate([_row(1, "c1", "o1")], {"e1": _judge("RELATED")}, policy=policy, coverage_fraction=1.0)["status"] == "WEAKLY_ATTESTED"
    assert aggregate_candidate([_row(1, "c1", "o1")], {"e1": _judge("DIFFERENT")}, policy=policy, coverage_fraction=1.0)["status"] == "NOT_ATTESTED"


def test_malformed_judge_response_stops_one_candidate_canary(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    evidence = __import__("vietnamese_attestation.v1.live.retrieval", fromlist=["extract_snapshot_evidence"]).extract_snapshot_evidence(workspace["snapshot_root"], candidate_id="candidate_model", sense_id="sense_model_001", term_en="language model", candidate_vi="mô hình ngôn ngữ")
    workspace["service"].judge = FixtureJudge({row["evidence_id"]: {"bad": True} for row in evidence})
    result = workspace["service"].create_run(workspace["request"])
    assert result["status"] == "STOPPED"
    assert not (Path(result["run_root"]) / "attestation_package.json").exists()
    events = json.loads("[" + ",".join((Path(result["run_root"]) / "events.jsonl").read_text(encoding="utf-8").splitlines()) + "]")
    assert events[-1]["event_kind"] == "STOP_EVENT"


def test_budget_exhaustion_stops_before_model_requests(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    request = dict(workspace["request"])
    request["budget"] = make_budget(max_semantic_calls=1, max_physical_requests=8)
    request["run_id"] = "run_fixture_budget"
    request["run_spec_id"] = compute_run_spec_id(request)
    result = workspace["service"].create_run(request)
    assert result["status"] == "STOPPED"
    events = [json.loads(line) for line in (Path(result["run_root"]) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["failure_disposition"] == "BUDGET_EXCEEDED"
    assert all(event["event_kind"] != "E_MODEL_REQUEST" for event in events)


def test_replay_rejects_raw_judge_response_tamper(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    result = workspace["service"].create_run(workspace["request"])
    raw = next((Path(result["run_root"]) / "raw_responses").glob("*.json"))
    raw.write_bytes(b"{}")
    with pytest.raises(LiveSchemaError, match="raw Judge response"):
        replay_run(result["run_root"])


def test_snapshot_rejects_unlisted_artifact_member(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    (workspace["snapshot_root"] / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(LiveSchemaError, match="CHECKSUMS"):
        verify_snapshot(workspace["snapshot_root"])


def test_snapshot_rejects_symlink_member_when_supported(tmp_path: Path) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    target = workspace["snapshot_root"] / "documents" / "one.html"
    original = tmp_path / "outside.html"
    original.write_bytes(target.read_bytes())
    target.unlink()
    try:
        target.symlink_to(original)
    except OSError:
        pytest.skip("symlink creation is unavailable on this Windows host")
    with pytest.raises(ValueError, match="symlink|reparse|junction"):
        verify_snapshot(workspace["snapshot_root"])


def test_strict_json_rejects_duplicate_and_nonfinite() -> None:
    from vietnamese_attestation.v1.strict_json import strict_json_loads
    with pytest.raises(ValueError):
        strict_json_loads('{"a":1,"a":2}')
    with pytest.raises(ValueError):
        strict_json_loads('{"a":NaN}')


def test_schema_catalog_exports_all_required_live_contracts(tmp_path: Path) -> None:
    manifest = export_schemas(tmp_path / "schemas")
    assert manifest["schema_count"] == len(SCHEMA_CATALOG) == 15
    assert (tmp_path / "schemas" / "ControlledVietnameseSourceRegistryV1.schema.json").is_file()
    assert (tmp_path / "schemas" / "EAttestationJudgeResponseV1.schema.json").is_file()
    assert (tmp_path / "schemas" / "EControlledAcquisitionReceiptV1.schema.json").is_file()
    assert (tmp_path / "schemas" / "ETrustedAuthorityProfileV1.schema.json").is_file()
