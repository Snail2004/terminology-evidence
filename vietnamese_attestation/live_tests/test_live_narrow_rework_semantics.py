from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from vietnamese_attestation.v1.live.aggregation import aggregate_candidate
from vietnamese_attestation.v1.live.common import (
    LiveSchemaError,
    canonical_bytes,
    canonical_sha256,
)
from vietnamese_attestation.v1.live.execution import derive_coverage_from_ledger
from vietnamese_attestation.v1.live.fixtures import build_fixture_workspace
from vietnamese_attestation.v1.live.judge import FixtureJudge, make_judge_response
from vietnamese_attestation.v1.live.policies import (
    make_provider_role_plan,
    render_query_plan,
)
from vietnamese_attestation.v1.live.retrieval import (
    FixtureDiscovery,
    FixtureFetcher,
    cluster_global_evidence,
    extract_fetched_evidence,
)
from vietnamese_attestation.v1.live.schema_tools import SCHEMA_CATALOG
from vietnamese_attestation.v1.live.schemas import validate_run_request
from vietnamese_attestation.v1.live.service import (
    ELiveService,
    make_authorization_receipt,
    make_run_request,
)


def _evidence(index: int, *, text: str, url: str, source_id: str) -> dict[str, object]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "evidence_id": f"evidence_{index}",
        "candidate_id": "candidate_network",
        "sense_id": "sense_network",
        "term_en": "neural network",
        "candidate_vi": "mang no ron",
        "document_id": f"document_{index}",
        "document_text": text,
        "source_id": source_id,
        "source_tier": "A",
        "source_type": "FIXTURE",
        "canonical_url": url,
        "final_url": url,
        "content_sha256": digest,
        "snippet_original": text,
        "snippet_masked": text.replace("mang no ron", "[CANDIDATE]"),
        "evidence_span": "mang no ron",
        "span_start": 0,
        "span_end": 11,
        "occurrence_count": 1,
        "publisher": source_id,
        "organization": source_id,
        "document_ref": f"fixture://{source_id}/{index}",
        "snapshot_manifest_sha256": "0" * 64,
        "evidence_sha256": digest,
    }


def _decision(
    relation: str,
    *,
    domain: str = "MATCH",
    usage: str = "TECHNICAL_TERM",
) -> dict[str, object]:
    return make_judge_response(
        concept_relation=relation,
        domain_relation=domain,
        usage_type=usage,
        judgeability="JUDGEABLE",
        evidence_span="mang no ron",
        snippet="mang no ron duoc dung trong tai lieu ky thuat",
    )


def test_one_eligibility_predicate_blocks_false_positive_routes() -> None:
    policy = {
        "min_coverage": 0.5,
        "min_same_clusters_for_attested": 2,
        "min_organizations_for_attested": 2,
    }
    rows = [
        _evidence(
            1,
            text="mang no ron duoc dung trong tai lieu ky thuat",
            url="fixture://one.example/a",
            source_id="one",
        ),
        _evidence(
            2,
            text="mang no ron duoc dung trong mot tai lieu ky thuat khac",
            url="fixture://two.example/b",
            source_id="two",
        ),
    ]
    _, representatives = cluster_global_evidence(rows)
    general_same = {
        row["evidence_id"]: _decision("SAME", usage="GENERAL_LANGUAGE")
        for row in representatives
    }
    result = aggregate_candidate(
        representatives, general_same, policy=policy, coverage_fraction=1.0
    )
    assert result["status"] == "NOT_ATTESTED"
    assert result["counts"]["positive_eligible_count"] == 0

    related_mismatch = {
        row["evidence_id"]: _decision(
            "RELATED", domain="MISMATCH", usage="GENERAL_LANGUAGE"
        )
        for row in representatives
    }
    result = aggregate_candidate(
        representatives, related_mismatch, policy=policy, coverage_fraction=1.0
    )
    assert result["status"] == "NOT_ATTESTED"
    assert result["counts"]["supporting_eligible_count"] == 0


def test_snapshot_and_fetched_copies_share_one_global_cluster() -> None:
    text = "mang no ron duoc dung trong tai lieu ky thuat va nghien cuu"
    snapshot = _evidence(
        1,
        text=text,
        url="fixture://one.example/a",
        source_id="one",
    )
    snapshot["snapshot_manifest_sha256"] = "1" * 64
    fetched = _evidence(
        2,
        text=text,
        url="fixture://two.example/copied",
        source_id="two",
    )
    all_rows, representatives = cluster_global_evidence([snapshot, fetched])
    assert len(all_rows) == 2
    assert len(representatives) == 1
    assert len({row["duplicate_cluster_id"] for row in all_rows}) == 1

    policy = {
        "min_coverage": 0.5,
        "min_same_clusters_for_attested": 2,
        "min_organizations_for_attested": 2,
    }
    decisions = {
        representatives[0]["evidence_id"]: _decision("SAME")
    }
    result = aggregate_candidate(
        representatives, decisions, policy=policy, coverage_fraction=1.0
    )
    assert result["status"] == "WEAKLY_ATTESTED"
    assert result["status"] != "ATTESTED"


def test_coverage_is_derived_and_incomplete_work_is_not_semantic_negative() -> None:
    coverage = derive_coverage_from_ledger(
        [],
        counts={
            "search_expected": 0,
            "search_success": 0,
            "search_required": False,
            "fetch_expected": 0,
            "fetch_success": 0,
            "fetch_required": False,
            "extraction_expected": 4,
            "extraction_attempted": 4,
            "extraction_success": 4,
            "language_expected": 4,
            "language_attempted": 4,
            "language_success": 3,
            "span_expected": 4,
            "span_attempted": 4,
            "span_success": 2,
            "judge_expected": 2,
            "judge_attempted": 2,
            "judge_success": 2,
        },
    )
    assert coverage["overall_attestation_coverage"] == 0.5
    assert coverage["stages"]["language"]["fraction"] == 0.75
    assert coverage["stages"]["span"]["fraction"] == 0.5

    rows = [
        _evidence(
            1,
            text="mang no ron duoc dung trong tai lieu ky thuat",
            url="fixture://one.example/a",
            source_id="one",
        )
    ]
    _, rows = cluster_global_evidence(rows)
    policy = {
        "min_coverage": 0.75,
        "min_same_clusters_for_attested": 1,
        "min_organizations_for_attested": 1,
    }
    result = aggregate_candidate(
        rows,
        {rows[0]["evidence_id"]: _decision("SAME")},
        policy=policy,
        coverage=coverage,
    )
    assert result["status"] == "ATTESTATION_UNJUDGEABLE"
    assert result["coverage"]["sufficient"] is False


def test_query_plan_renders_only_frozen_fields_and_records_hashes(
    tmp_path: Path,
) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    request = workspace["request"]
    plan = render_query_plan(
        workspace["policy_bundle"]["query_template_set"],
        selected_template_ids=["exact_candidate", "candidate_definition"],
        request=request,
        max_queries=2,
    )
    assert [row["template_id"] for row in plan] == [
        "exact_candidate",
        "candidate_definition",
    ]
    for row in plan:
        assert row["rendered_query_sha256"] == hashlib.sha256(
            row["rendered_query"].encode("utf-8")
        ).hexdigest()
        assert len(row["template_sha256"]) == 64
    with pytest.raises(LiveSchemaError, match="approved cap"):
        render_query_plan(
            workspace["policy_bundle"]["query_template_set"],
            selected_template_ids=["exact_candidate", "candidate_definition"],
            request=request,
            max_queries=1,
        )


def test_run_request_runtime_and_json_schema_reject_nested_extra(
    tmp_path: Path,
) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    schema = SCHEMA_CATALOG["ERunRequestV1"]
    Draft202012Validator.check_schema(schema)
    assert not list(Draft202012Validator(schema).iter_errors(workspace["request"]))

    tampered = copy.deepcopy(workspace["request"])
    tampered["domain"]["unreviewed"] = True
    with pytest.raises(LiveSchemaError, match="unsupported keys"):
        validate_run_request(tampered)
    assert list(Draft202012Validator(schema).iter_errors(tampered))

    tampered = copy.deepcopy(workspace["request"])
    tampered["authority_refs"]["candidate_key"]["extra"] = "forbidden"
    with pytest.raises(LiveSchemaError, match="unsupported keys"):
        validate_run_request(tampered)
    assert list(Draft202012Validator(schema).iter_errors(tampered))


def test_service_executes_query_and_exact_provider_role_plan(tmp_path: Path) -> None:
    service, request = _discovery_service(tmp_path, copied=True)
    result = service.create_run(request)
    assert result["status"] == "COMPLETED"
    assert result["local_status"] == "WEAKLY_ATTESTED"
    assert result["package"]["accepted_evidence_refs"]
    run_root = Path(result["run_root"])
    events = [
        json.loads(line)
        for line in (run_root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    query_events = [row for row in events if row["event_kind"] == "E_DISCOVERY_QUERY"]
    assert [row["payload"]["template_id"] for row in query_events] == [
        "exact_candidate",
        "candidate_definition",
    ]
    for event in query_events:
        assert event["payload"]["rendered_query_sha256"] == hashlib.sha256(
            event["payload"]["rendered_query"].encode("utf-8")
        ).hexdigest()
    model_events = [row for row in events if row["event_kind"] == "E_MODEL_REQUEST"]
    assert len(model_events) == 1
    assert model_events[0]["payload"]["provider_id"] == "reviewed-primary"
    assert model_events[0]["payload"]["model_id"] == "reviewed-model-primary"
    assert result["provider_calls"] == 0
    assert result["network_calls"] == 0


def test_independent_cluster_conflict_triggers_secondary_role(tmp_path: Path) -> None:
    service, request = _discovery_service(tmp_path, copied=False)
    result = service.create_run(request)
    events = [
        json.loads(line)
        for line in (Path(result["run_root"]) / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    routes = [
        row["payload"]["route"]
        for row in events
        if row["event_kind"] == "E_MODEL_REQUEST"
    ]
    assert routes.count("PRIMARY_ATTESTATION_JUDGE") == 2
    assert routes.count("SECONDARY_ATTESTATION_JUDGE") == 2
    assert result["local_status"] == "ATTESTED"


def _discovery_service(
    tmp_path: Path, *, copied: bool
) -> tuple[ELiveService, dict[str, object]]:
    workspace = build_fixture_workspace(tmp_path / "base")
    candidate_id = "candidate_network"
    candidate_vi = "mang no ron"
    term_en = "neural network"
    sense_id = "sense_network"
    urls = ["fixture://one.example/a", "fixture://two.example/b"]
    first = (
        b"<html><body>Trong tai lieu ky thuat mang no ron la mot he thong "
        b"hoc tu du lieu va tao du doan on dinh.</body></html>"
    )
    second = first if copied else (
        b"<html><body>Nghien cuu doc lap mo ta mang no ron nhu mot mo hinh "
        b"tinh toan gom nhieu nut ket noi voi nhau.</body></html>"
    )
    documents = {
        urls[0]: {
            "body": first,
            "content_type": "text/html",
            "source_id": "fixture_one",
        },
        urls[1]: {
            "body": second,
            "content_type": "text/html",
            "source_id": "fixture_two",
        },
    }
    response_map: dict[str, object] = {}
    for index, url in enumerate(urls):
        probe = FixtureFetcher({url: documents[url]})
        fetched = probe.fetch(url)
        rows = extract_fetched_evidence(
            fetched,
            source_id=documents[url]["source_id"],
            source_tier="A" if index == 0 else "B",
            source_type="FIXTURE",
            candidate_id=candidate_id,
            sense_id=sense_id,
            term_en=term_en,
            candidate_vi=candidate_vi,
        )
        assert len(rows) == 1
        primary_relation = "SAME" if copied or index == 0 else "DIFFERENT"
        response_map[rows[0]["evidence_id"]] = {
            "PRIMARY_ATTESTATION_JUDGE": _decision(primary_relation),
            "SECONDARY_ATTESTATION_JUDGE": _decision("SAME"),
        }

    role_plan = make_provider_role_plan(
        primary_provider_id="reviewed-primary",
        secondary_provider_id="reviewed-secondary",
        primary_model_id="reviewed-model-primary",
        secondary_model_id="reviewed-model-secondary",
    )
    policies = dict(workspace["policy_bundle"])
    policies["provider_role_plan"] = role_plan
    policy_hashes = {
        "retrieval_policy": policies["retrieval_policy"]["integrity"]["self_sha256"],
        "query_template_set": policies["query_template_set"]["integrity"]["self_sha256"],
        "provider_role_plan": role_plan["integrity"]["self_sha256"],
        "aggregation_policy": policies["aggregation_policy"]["integrity"]["self_sha256"],
    }
    receipt = make_authorization_receipt(
        cohort_id="fixture-cohort-v1",
        candidate_ids=[candidate_id],
        registry_self_sha256=workspace["registry"]["integrity"]["self_sha256"],
        snapshot_manifest_sha256=workspace["service"].snapshot["integrity"]["self_sha256"],
        policy_hashes=policy_hashes,
    )
    candidate_key = {
        "candidate_id": candidate_id,
        "candidate_version": hashlib.sha256(candidate_id.encode("ascii")).hexdigest(),
        "source_term": term_en,
        "candidate_vi": candidate_vi,
        "sense_id": sense_id,
        "scope_id": "nlp",
        "sense_inventory_version": "fixture-sense-v1",
        "dataset_manifest_sha256": hashlib.sha256(b"fixture-dataset").hexdigest(),
        "effective_sense_contract_sha256": hashlib.sha256(b"fixture-contract").hexdigest(),
    }
    request = make_run_request(
        run_id="run_discovery_narrow",
        phase_id="E_CONTROLLED_CORPUS_CANARY",
        sense_id=sense_id,
        candidate_id=candidate_id,
        term_en=term_en,
        candidate_vi=candidate_vi,
        sense_definition="a connected computational learning model",
        domain={"scope_id": "nlp", "anchors": ["learning"]},
        candidate_variants=[],
        query_template_ids=["exact_candidate", "candidate_definition"],
        authority_refs={
            "cohort_id": "fixture-cohort-v1",
            "registry_self_sha256": workspace["registry"]["integrity"]["self_sha256"],
            "snapshot_manifest_sha256": workspace["service"].snapshot["integrity"]["self_sha256"],
            "candidate_key": candidate_key,
            "input_contract_sha256": canonical_sha256(candidate_key),
        },
        budget=workspace["budget"],
        policy_hashes=policy_hashes,
    )
    service = ELiveService(
        root=tmp_path / "service-runs",
        registry=workspace["registry"],
        snapshot_root=workspace["snapshot_root"],
        policy_bundle=policies,
        authorization_receipt=receipt,
        authorized_cohort_id="fixture-cohort-v1",
        authorized_candidate_ids=[candidate_id],
        discovery=FixtureDiscovery({candidate_id: urls}),
        fetcher=FixtureFetcher(documents),
        judge=FixtureJudge(response_map),
    )
    return service, request
