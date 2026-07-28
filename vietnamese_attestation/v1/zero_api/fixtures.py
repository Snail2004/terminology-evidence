"""Deterministic fixture scenarios for the 15-candidate pilot."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..config import AttestationConfig, RetrievalConfig
from ..contracts.frozen_candidate import seal_frozen_candidate
from ..contracts.judge import (
    JUDGE_SCHEMA_ID,
    JUDGE_SCHEMA_VERSION,
    validate_judge_payload_for_snippet,
)
from ..dataset.contracts import validate_adapter_candidate
from ..judging.base import (
    JudgeRequest,
    JudgeRouteResult,
    JudgeTransportError,
)
from ..judging.router import FallbackJudgeRouter
from ..retrieval.fetch import StaticDocumentFetcher
from ..retrieval.search import SearchProviderError, StaticSearchProvider
from ..retrieval.urls import canonicalize_url
from ..runtime.engine import AttestationEngine
from .artifacts import canonical_sha256


SCENARIOS = (
    "STRONG_POSITIVE",
    "DUPLICATE_ECHO",
    "SAME_ORGANIZATION_DIFFERENT_DOCUMENTS",
    "RELATED",
    "DIFFERENT",
    "UNCERTAIN",
    "JUDGE_UNAVAILABLE",
    "SEARCH_FAILURE",
    "FETCH_TIMEOUT",
    "EXTRACTION_FAILURE",
    "NON_VIETNAMESE",
    "CANDIDATE_SPAN_ABSENT",
    "MACHINE_TRANSLATION_SUSPECTED",
    "UNKNOWN_PDF",
    "CONFLICTING_ATTESTATION",
)


def build_internal_candidate(raw: Mapping[str, Any]) -> dict[str, Any]:
    candidate = validate_adapter_candidate(raw)
    return seal_frozen_candidate(
        {
            "source_contract_ref": {
                "schema_id": candidate["schema_id"],
                "schema_version": candidate["schema_version"],
                "artifact_ref": (
                    "artifact://d2l-pilot/candidate/"
                    f"{candidate['candidate_id']}"
                ),
                "artifact_sha256": candidate["integrity"][
                    "adapter_candidate_sha256"
                ],
            },
            "candidate_id": candidate["candidate_id"],
            "candidate_version": candidate["candidate_version"],
            "term_id": candidate["term_id"],
            "source_term": candidate["source_term"],
            "candidate_vi": candidate["candidate_vi"],
            "sense_id": candidate["sense_id"],
            "scope_id": candidate["scope_id"],
            "sense_contract": {
                "definition_en": candidate["sense_contract"]["definition_en"],
                "definition_review_status": "UNVERIFIED",
                "definition_provenance": [
                    candidate["sense_contract"]["term_sense_sha256"]
                ],
                "sense_inventory_version": candidate["sense_contract"][
                    "sense_inventory_version"
                ],
            },
            "known_surfaces": {
                "canonical": candidate["candidate_vi"],
                "validated_variants": [],
                "rejected_variants": [],
            },
            "domain_profile": {
                "domain_name": candidate["scope_id"],
                "vi_anchors": [],
                "en_anchors": [],
            },
            "run_policy": {
                "attestation_policy_version": "attestation-v1.1",
                "query_policy_version": "query-v1",
                "source_policy_version": "source-tier-v2",
                "dedup_policy_version": "dedup-v2",
                "judge_policy_version": "attestation-judge-v1",
            },
        }
    )


def build_scenario_engine(
    *,
    candidate: Mapping[str, Any],
    scenario: str,
    index: int,
    audit_root: Path,
) -> AttestationEngine:
    rows, documents = _scenario_documents(candidate, scenario)
    if scenario == "SEARCH_FAILURE":
        search: Any = _FailedFixtureSearch()
    else:
        search = StaticSearchProvider(
            "zero_api_fixture_search",
            {
                "EXACT_CANDIDATE": rows,
                "CANDIDATE_DOMAIN": rows,
                "CANDIDATE_SOURCE_TERM": rows,
            },
        )
    judge = _ScenarioJudgeProvider(scenario)
    started = datetime(2026, 7, 29, tzinfo=timezone.utc) + timedelta(
        minutes=index
    )
    timestamps = iter(
        (
            started.isoformat().replace("+00:00", "Z"),
            (started + timedelta(seconds=1)).isoformat().replace(
                "+00:00", "Z"
            ),
        )
    )
    execution_id = (
        f"zeroapi-{index + 1:02d}-"
        f"{candidate['candidate_id'][-12:]}-{scenario.casefold()}"
    )
    return AttestationEngine(
        search_providers=[search],
        document_fetcher=StaticDocumentFetcher(documents),
        judge_router=FallbackJudgeRouter([judge]),
        config=AttestationConfig(
            retrieval=RetrievalConfig(min_fetch_coverage=0.5),
            search_provider_ids=(search.provider_id,),
            judge_route_order=(judge.route_id,),
        ),
        source_overrides={},
        clock=lambda: next(timestamps),
        audit_store_root=audit_root,
        execution_id_factory=lambda run_spec_id, timestamp: execution_id,
    )


def _scenario_documents(
    candidate: Mapping[str, Any], scenario: str
) -> tuple[
    list[dict[str, str]],
    dict[str, tuple[str, str | bytes]],
]:
    urls = [
        "https://one.edu.vn/evidence/a",
        "https://two.gov.vn/evidence/b",
    ]
    documents: dict[str, tuple[str, str | bytes]] = {}
    if scenario == "SEARCH_FAILURE":
        return [], documents
    if scenario == "FETCH_TIMEOUT":
        return [_search_row(urls[0], "Fetch timeout")], documents
    if scenario == "EXTRACTION_FAILURE":
        documents[canonicalize_url(urls[0])] = (
            "application/octet-stream",
            b"unsupported fixture content",
        )
        return [_search_row(urls[0], "Extraction failure")], documents
    if scenario == "UNKNOWN_PDF":
        documents[canonicalize_url(urls[0])] = (
            "application/pdf",
            b"not-a-valid-pdf",
        )
        return [_search_row(urls[0], "Unknown PDF")], documents
    if scenario == "NON_VIETNAMESE":
        documents[canonicalize_url(urls[0])] = (
            "text/html",
            _document(
                "an unrelated English expression",
                "SCENARIO_SAME",
                english=True,
            ),
        )
        return [_search_row(urls[0], "Non Vietnamese")], documents
    if scenario == "CANDIDATE_SPAN_ABSENT":
        documents[canonicalize_url(urls[0])] = (
            "text/html",
            _document("một biểu thức hoàn toàn khác", "SCENARIO_SAME"),
        )
        return [_search_row(urls[0], "Missing span")], documents

    marker = {
        "RELATED": "SCENARIO_RELATED",
        "DIFFERENT": "SCENARIO_DIFFERENT",
        "UNCERTAIN": "SCENARIO_UNCERTAIN",
        "MACHINE_TRANSLATION_SUSPECTED": "SCENARIO_MACHINE_TRANSLATION",
    }.get(scenario, "SCENARIO_SAME")
    candidate_surface = str(candidate["candidate_vi"])
    if scenario == "CONFLICTING_ATTESTATION":
        documents[canonicalize_url(urls[0])] = (
            "text/html",
            _document(candidate_surface, "SCENARIO_SAME"),
        )
        documents[canonicalize_url(urls[1])] = (
            "text/html",
            _document(candidate_surface, "SCENARIO_DIFFERENT", variant=True),
        )
    elif scenario == "DUPLICATE_ECHO":
        urls.append("https://mirror.example.com/evidence/c")
        shared = _document(candidate_surface, marker)
        documents[canonicalize_url(urls[0])] = ("text/html", shared)
        documents[canonicalize_url(urls[2])] = ("text/html", shared)
        documents[canonicalize_url(urls[1])] = (
            "text/html",
            _document(candidate_surface, marker, variant=True),
        )
    elif scenario == "SAME_ORGANIZATION_DIFFERENT_DOCUMENTS":
        urls[1] = "https://one.edu.vn/evidence/b"
        documents[canonicalize_url(urls[0])] = (
            "text/html",
            _document(candidate_surface, marker),
        )
        documents[canonicalize_url(urls[1])] = (
            "text/html",
            _document(candidate_surface, marker, variant=True),
        )
    elif scenario in {
        "STRONG_POSITIVE",
        "MACHINE_TRANSLATION_SUSPECTED",
    }:
        documents[canonicalize_url(urls[0])] = (
            "text/html",
            _document(candidate_surface, marker),
        )
        documents[canonicalize_url(urls[1])] = (
            "text/html",
            _document(candidate_surface, marker, variant=True),
        )
    else:
        documents[canonicalize_url(urls[0])] = (
            "text/html",
            _document(candidate_surface, marker),
        )
        urls = urls[:1]
    return [_search_row(url, scenario) for url in urls], documents


def _document(
    candidate_vi: str,
    marker: str,
    *,
    variant: bool = False,
    english: bool = False,
) -> str:
    if english:
        return (
            "<html><main>This technical page contains only English prose about "
            "models, datasets, inference, and evaluation. It deliberately has "
            "no Vietnamese linguistic context for the candidate.</main></html>"
        )
    suffix = (
        "Nguồn thứ hai trình bày ví dụ độc lập và giải thích thêm phạm vi dùng."
        if variant
        else "Nguồn này trình bày định nghĩa và phạm vi sử dụng trong kỹ thuật."
    )
    return (
        "<html><main>Trong tài liệu kỹ thuật, "
        f"{candidate_vi} được mô tả rõ trong đúng ngữ cảnh chuyên ngành. "
        "Khái niệm này liên hệ với mô hình, dữ liệu và quy trình xử lý cụ thể. "
        f"{suffix} {marker}</main></html>"
    )


def _search_row(url: str, title: str) -> dict[str, str]:
    return {"url": url, "title": title, "description": "zero-API fixture"}


class _FailedFixtureSearch:
    provider_id = "zero_api_fixture_search"

    def search(self, query: Any, *, count: int) -> Sequence[Any]:
        del query, count
        raise SearchProviderError(
            "zero-API fixture search failure",
            code="ZERO_API_SEARCH_FAILURE",
        )

    def identity_payload(self) -> dict[str, str]:
        return {
            "component": type(self).__name__,
            "provider_id": self.provider_id,
        }


class _ScenarioJudgeProvider:
    route_id = "zero_api_fixture_judge"
    model_id = "zero-api-static-judge-v1"

    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    def judge(self, request: JudgeRequest) -> JudgeRouteResult:
        if self.scenario == "JUDGE_UNAVAILABLE":
            raise JudgeTransportError(
                "ZERO_API_JUDGE_UNAVAILABLE",
                "zero-API fixture judge unavailable",
            )
        snippet = request.snippet_original
        relation = "SAME"
        if "SCENARIO_RELATED" in snippet:
            relation = "RELATED"
        elif "SCENARIO_DIFFERENT" in snippet:
            relation = "DIFFERENT"
        elif "SCENARIO_UNCERTAIN" in snippet:
            relation = "UNCERTAIN"
        payload = validate_judge_payload_for_snippet(
            {
                "schema_id": JUDGE_SCHEMA_ID,
                "schema_version": JUDGE_SCHEMA_VERSION,
                "judgeability": "JUDGEABLE",
                "concept_relation": relation,
                "domain_match": True,
                "candidate_role": "TECHNICAL_TERM",
                "machine_translation_suspected": (
                    "SCENARIO_MACHINE_TRANSLATION" in snippet
                ),
                "evidence_span": request.candidate_vi,
                "reason": f"Deterministic zero-API fixture relation: {relation}",
            },
            snippet_original=snippet,
        )
        request_payload = {
            "evidence_id": request.evidence_id,
            "definition_en": request.definition_en,
            "scope_id": request.scope_id,
            "candidate_vi": request.candidate_vi,
            "snippet_original": request.snippet_original,
            "snippet_masked": request.snippet_masked,
            "source_type": request.source_type,
        }
        return JudgeRouteResult(
            route_id=self.route_id,
            model_id=self.model_id,
            payload=payload,
            request_sha256=canonical_sha256(request_payload),
            response_sha256=canonical_sha256(payload),
            input_tokens=0,
            output_tokens=0,
            raw_response=payload,
        )

    def identity_payload(self) -> dict[str, str]:
        return {
            "component": type(self).__name__,
            "route_id": self.route_id,
            "model_id": self.model_id,
            "scenario": self.scenario,
        }


__all__ = ["SCENARIOS", "build_internal_candidate", "build_scenario_engine"]
