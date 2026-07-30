"""Deterministic local fixtures for E Live conformance tests and canaries."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .aggregation import aggregate_candidate
from .common import canonical_bytes, canonical_sha256
from .judge import FixtureJudge, make_judge_response
from .policies import make_aggregation_policy, make_budget, make_provider_role_plan, make_query_template_set, make_retrieval_policy
from .registry import make_registry
from .retrieval import extract_snapshot_evidence
from .service import ELiveService, make_authorization_receipt, make_run_request
from .snapshot import build_snapshot


def build_fixture_workspace(root: str | Path) -> dict[str, Any]:
    """Create a complete zero-provider workspace in a new output directory."""
    base = Path(root).absolute()
    base.mkdir(parents=True, exist_ok=True)
    source_root = base / "source"
    snapshot_root = base / "snapshot"
    run_root = base / "runs"
    source_root.mkdir(exist_ok=False)
    html_one = (
        "<html><main>Trong tài liệu kỹ thuật, mô hình ngôn ngữ là một khái niệm "
        "được dùng để mô tả hệ thống học từ dữ liệu và tạo ra dự đoán. "
        "Nguồn fixture này cung cấp ngữ cảnh tiếng Việt ổn định cho kiểm thử.</main></html>"
    ).encode("utf-8")
    html_two = (
        "<html><main>Tài liệu học thuật giải thích mô hình ngôn ngữ trong xử lý "
        "ngôn ngữ tự nhiên, bao gồm dữ liệu, huấn luyện và suy luận. "
        "Đây là một nguồn độc lập của fixture.</main></html>"
    ).encode("utf-8")
    (source_root / "one.html").write_bytes(html_one)
    (source_root / "two.html").write_bytes(html_two)
    authority_sha = hashlib.sha256(b"external-controlled-registry-approval-v1").hexdigest()
    registry = make_registry(
        [
            {"source_id": "fixture_one", "host_pattern": "one.example", "source_tier": "A", "source_type": "FIXTURE", "allowed_content_types": ["text/html"], "allowed": True, "domain_tags": ["nlp"]},
            {"source_id": "fixture_two", "host_pattern": "two.example", "source_tier": "B", "source_type": "FIXTURE", "allowed_content_types": ["text/html"], "allowed": True, "domain_tags": ["nlp"]},
        ],
        authority_receipt_ref="fixture/registry-approval.json",
        authority_receipt_sha256=authority_sha,
    )
    retrieval_policy = make_retrieval_policy(network_mode="LOCAL_FIXTURE_ONLY", max_queries_per_candidate=2, max_direct_fetches=2, max_accepted_documents=2)
    query_templates = make_query_template_set(max_queries=2)
    role_plan = make_provider_role_plan()
    aggregation_policy = make_aggregation_policy(min_same_clusters_for_attested=2, min_organizations_for_attested=2, min_coverage=0.5)
    budget = make_budget(max_semantic_calls=4, max_physical_requests=8)
    receipt = {
        "schema_id": "EControlledAcquisitionReceiptV1",
        "schema_version": "1.0.0",
        "mode": "LOCAL_FIXTURE_ONLY",
        "rows": [
            {"file_ref": "one.html", "source_id": "fixture_one", "canonical_url": "fixture://one.example/one", "final_url": "fixture://one.example/one", "content_type": "text/html", "retrieved_at_utc": "2026-07-30T00:00:00Z"},
            {"file_ref": "two.html", "source_id": "fixture_two", "canonical_url": "fixture://two.example/two", "final_url": "fixture://two.example/two", "content_type": "text/html", "retrieved_at_utc": "2026-07-30T00:00:00Z"},
        ],
    }
    snapshot = build_snapshot(source_root, snapshot_root, registry=registry, retrieval_policy=retrieval_policy, acquisition_receipt=receipt, producer_commit="0000000000000000000000000000000000000000", producer_tree="fixture-tree-v1")
    (base / "registry.json").write_bytes(canonical_bytes(registry))
    (base / "retrieval_policy.json").write_bytes(canonical_bytes(retrieval_policy))
    (base / "query_templates.json").write_bytes(canonical_bytes(query_templates))
    (base / "provider_role_plan.json").write_bytes(canonical_bytes(role_plan))
    (base / "aggregation_policy.json").write_bytes(canonical_bytes(aggregation_policy))
    (base / "budget.json").write_bytes(canonical_bytes(budget))
    policy_hashes = {
        "retrieval_policy": retrieval_policy["integrity"]["self_sha256"],
        "query_template_set": query_templates["integrity"]["self_sha256"],
        "provider_role_plan": role_plan["integrity"]["self_sha256"],
        "aggregation_policy": aggregation_policy["integrity"]["self_sha256"],
    }
    auth = make_authorization_receipt(cohort_id="fixture-cohort-v1", candidate_ids=["candidate_model"], registry_self_sha256=registry["integrity"]["self_sha256"], snapshot_manifest_sha256=snapshot["integrity"]["self_sha256"], policy_hashes=policy_hashes)
    candidate_key = {
        "candidate_id": "candidate_model",
        "candidate_version": "fixture-candidate-v1",
        "source_term": "language model",
        "candidate_vi": "mô hình ngôn ngữ",
        "sense_id": "sense_model_001",
        "scope_id": "nlp",
        "sense_inventory_version": "fixture-sense-v1",
        "dataset_manifest_sha256": hashlib.sha256(b"fixture-dataset-v1").hexdigest(),
        "effective_sense_contract_sha256": hashlib.sha256(b"fixture-sense-contract-v1").hexdigest(),
    }
    request = make_run_request(run_id="run_fixture_e_live_001", phase_id="E_CONTROLLED_CORPUS_CANARY", sense_id="sense_model_001", candidate_id="candidate_model", term_en="language model", candidate_vi="mô hình ngôn ngữ", sense_definition="a model used to process language", domain={"scope_id": "nlp", "anchors": ["ngôn ngữ"]}, candidate_variants=[], authority_refs={"cohort_id": "fixture-cohort-v1", "registry_self_sha256": registry["integrity"]["self_sha256"], "snapshot_manifest_sha256": snapshot["integrity"]["self_sha256"], "candidate_key": candidate_key, "input_contract_sha256": hashlib.sha256(canonical_bytes(candidate_key)).hexdigest()}, budget=budget, policy_hashes=policy_hashes)
    evidence = extract_snapshot_evidence(snapshot_root, candidate_id=request["candidate_id"], sense_id=request["sense_id"], term_en=request["term_en"], candidate_vi=request["candidate_vi"])
    responses = {
        row["evidence_id"]: make_judge_response(concept_relation="SAME", domain_relation="MATCH", usage_type="TECHNICAL_TERM", judgeability="JUDGEABLE", evidence_span=row["evidence_span"], reason_codes=["FIXTURE_SAME"], reason="controlled fixture same-concept evidence", snippet=row["snippet_original"])
        for row in evidence
    }
    service = ELiveService(root=run_root, registry=registry, snapshot_root=snapshot_root, policy_bundle={"retrieval_policy": retrieval_policy, "query_template_set": query_templates, "provider_role_plan": role_plan, "aggregation_policy": aggregation_policy}, authorization_receipt=auth, authorized_cohort_id="fixture-cohort-v1", authorized_candidate_ids=["candidate_model"], judge=FixtureJudge(responses))
    return {"base": base, "source_root": source_root, "snapshot_root": snapshot_root, "run_root": run_root, "registry": registry, "policy_bundle": {"retrieval_policy": retrieval_policy, "query_template_set": query_templates, "provider_role_plan": role_plan, "aggregation_policy": aggregation_policy}, "budget": budget, "authorization_receipt": auth, "request": request, "service": service, "evidence_count": len(evidence)}


__all__ = ["build_fixture_workspace"]
