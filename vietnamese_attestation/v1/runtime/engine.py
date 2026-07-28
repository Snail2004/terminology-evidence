from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from ..config import AttestationConfig
from ..contracts.frozen_candidate import validate_frozen_candidate
from ..contracts.judge import (
    JUDGE_SCHEMA_ID,
    JUDGE_SCHEMA_VERSION,
    validate_judge_payload,
)
from ..contracts.output import seal_attestation_package
from ..evidence.dedup import (
    DEDUP_POLICY_VERSION,
    build_duplicate_cluster_ledger,
    cluster_evidence_documents,
)
from ..evidence.sources import SOURCE_POLICY_VERSION, profile_source
from ..evidence.spans import (
    build_candidate_snippet,
    count_candidate_occurrences,
)
from ..judging.base import AllJudgeRoutesFailed, JudgeRequest
from ..judging.prompt import prompt_sha256
from ..judging.router import FallbackJudgeRouter
from ..retrieval.extraction import (
    EXTRACTOR_VERSION,
    ExtractionError,
    extract_document,
)
from ..retrieval.fetch import DocumentFetcher, FetchError
from ..retrieval.language import (
    LANGUAGE_DETECTOR_VERSION,
    detect_vietnamese,
    is_vietnamese_eligible,
)
from ..retrieval.query import build_query_plan
from ..retrieval.search import (
    SearchProvider,
    SearchProviderError,
    SearchResult,
    merge_search_results,
)
from .aggregation import aggregate_attestation
from .audit import FileRunAuditStore, MemoryRunAuditStore, RunAuditStore
from .cost import build_cost_report
from ..contracts.evidence_policy import (
    ATTESTATION_POLICY_VERSION,
    rejection_reasons,
)


Clock = Callable[[], str]
ExecutionIdFactory = Callable[[str, str], str]


class AttestationEngine:
    def __init__(
        self,
        *,
        search_providers: Sequence[SearchProvider],
        document_fetcher: DocumentFetcher,
        judge_router: FallbackJudgeRouter,
        config: AttestationConfig | None = None,
        source_overrides: Mapping[str, Mapping[str, Any]] | None = None,
        clock: Clock | None = None,
        audit_store_root: Path | None = None,
        execution_id_factory: ExecutionIdFactory | None = None,
    ) -> None:
        if not search_providers:
            raise ValueError("at least one search provider is required")
        provider_ids = [provider.provider_id for provider in search_providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("search provider IDs must be unique")
        self.search_providers = tuple(search_providers)
        self.document_fetcher = document_fetcher
        self.judge_router = judge_router
        self.config = config or AttestationConfig()
        self.config.validate()
        if tuple(provider_ids) != self.config.search_provider_ids:
            raise ValueError("search provider order differs from sealed config")
        if judge_router.route_order != self.config.judge_route_order:
            raise ValueError("judge route order differs from sealed config")
        self.source_overrides = dict(source_overrides or {})
        self.clock = clock or _utc_now
        self.audit_store_root = (
            Path(audit_store_root) if audit_store_root is not None else None
        )
        self.execution_id_factory = (
            execution_id_factory or _new_execution_id
        )

    def run(self, frozen_candidate: Mapping[str, Any]) -> dict[str, Any]:
        candidate = validate_frozen_candidate(frozen_candidate)
        _validate_policy_binding(candidate["run_policy"])
        started_at = self.clock()
        plan = build_query_plan(
            candidate,
            max_queries=self.config.retrieval.max_queries_per_candidate,
            restricted_source_domains=(
                self.config.retrieval.restricted_source_domains
            ),
        )
        frozen_sha = candidate["integrity"]["frozen_candidate_sha256"]
        execution_config_sha = _execution_config_sha256(
            config=self.config,
            search_providers=self.search_providers,
            document_fetcher=self.document_fetcher,
            source_overrides=self.source_overrides,
            judge_router=self.judge_router,
        )
        run_spec_id = _run_spec_id(
            frozen_sha=frozen_sha,
            query_plan_id=plan.query_plan_id,
            execution_config_sha256=execution_config_sha,
            run_policy=candidate["run_policy"],
        )
        execution_id = self.execution_id_factory(run_spec_id, started_at)
        if not re.fullmatch(r"[A-Za-z0-9._-]{8,128}", execution_id):
            raise ValueError("attestation execution ID is not path-safe")
        audit: RunAuditStore = (
            FileRunAuditStore(self.audit_store_root, execution_id)
            if self.audit_store_root is not None
            else MemoryRunAuditStore(execution_id)
        )
        raw_results, search_counts = self._search(plan.queries, audit=audit)
        merged = merge_search_results(
            raw_results,
            max_unique_urls=self.config.retrieval.max_unique_urls,
        )
        selected_rows = merged[: self.config.retrieval.max_fetches]
        for skipped in merged[self.config.retrieval.max_fetches :]:
            audit.append(
                "url_attempts",
                _url_terminal(
                    skipped,
                    status="FETCH_LIMIT_NOT_SELECTED",
                    error_code="FETCH_LIMIT_NOT_SELECTED",
                ),
            )
        prepared, retrieval_counts = self._prepare_evidence(
            candidate=candidate,
            rows=selected_rows,
            query_count=len(plan.queries),
            raw_result_count=len(raw_results),
            unique_url_count=len(merged),
            audit=audit,
        )
        clustered = cluster_evidence_documents(prepared)
        representatives = _cluster_representatives(clustered)
        dedup_clusters = build_duplicate_cluster_ledger(
            clustered, representatives
        )
        for cluster in dedup_clusters:
            audit.append("dedup_clusters", cluster)
        judged, judge_attempts, unavailable = self._judge(
            candidate=candidate,
            rows=representatives,
            audit=audit,
        )
        accepted, rejected = _partition_evidence(
            judged,
            machine_translation_policy=(
                self.config.status.machine_translation_suspicion_policy
            ),
        )
        aggregation = aggregate_attestation(
            judged,
            config=self.config,
            retrieval_counts={
                **retrieval_counts,
                **search_counts,
                "duplicate_document_count": len(clustered)
                - len(representatives),
                "post_dedup_cluster_count": len(representatives),
                "judged_cluster_count": len(judged),
                "judgeable_cluster_count": sum(
                    row["judge"]["judgeability"] == "JUDGEABLE"
                    for row in judged
                ),
            },
            judge_unavailable_count=unavailable,
        )
        completed_at = self.clock()
        cost_report = build_cost_report(
            pricing=self.config.pricing,
            search_provider_ids=[
                provider.provider_id for provider in self.search_providers
            ],
            search_attempts=search_counts["search_query_attempt_count"],
            search_successes=search_counts["search_query_success_count"],
            judge_attempts=judge_attempts,
            fetch_count=retrieval_counts["fetch_attempt_count"],
            judged_cluster_count=len(judged),
            accepted_cluster_count=len(accepted),
            started_at=started_at,
            completed_at=completed_at,
        )
        audit_descriptor = audit.finalize(
            run_spec_id=run_spec_id,
            started_at=started_at,
            completed_at=completed_at,
        )
        return seal_attestation_package(
            {
                "frozen_candidate_sha256": frozen_sha,
                "candidate_id": candidate["candidate_id"],
                "candidate_version": candidate["candidate_version"],
                "term_id": candidate["term_id"],
                "source_term": candidate["source_term"],
                "candidate_vi": candidate["candidate_vi"],
                "sense_id": candidate["sense_id"],
                "scope_id": candidate["scope_id"],
                "sense_inventory_version": candidate["sense_contract"][
                    "sense_inventory_version"
                ],
                "attestation_evidence": {
                    "features": aggregation["features"],
                    "coverage_breakdown": aggregation[
                        "coverage_breakdown"
                    ],
                    "coverage_policy_version": aggregation[
                        "coverage_policy_version"
                    ],
                    "status_policy": aggregation["status_policy"],
                    "counts": aggregation["counts"],
                    "status": aggregation["status"],
                    "flags": _package_flags(
                        candidate=candidate,
                        base_flags=aggregation["flags"],
                        judge_attempts=judge_attempts,
                        search_failure_count=search_counts[
                            "search_query_failure_count"
                        ],
                    ),
                },
                "accepted_evidence": accepted,
                "rejected_evidence": rejected,
                "dedup_clusters": dedup_clusters,
                "audit": audit_descriptor,
                "cost_report": cost_report,
                "observed_variants": [],
                "recommendation_to_global_validator": aggregation[
                    "recommendation"
                ],
                "final_glossary_decision": None,
                "provenance": {
                    "run_spec_id": run_spec_id,
                    "attestation_execution_id": execution_id,
                    "frozen_candidate_sha256": frozen_sha,
                    "source_contract_ref": candidate["source_contract_ref"],
                    "attestation_policy_version": candidate["run_policy"][
                        "attestation_policy_version"
                    ],
                    "query_policy_version": candidate["run_policy"][
                        "query_policy_version"
                    ],
                    "source_policy_version": SOURCE_POLICY_VERSION,
                    "dedup_policy_version": DEDUP_POLICY_VERSION,
                    "judge_policy_version": candidate["run_policy"][
                        "judge_policy_version"
                    ],
                    "query_plan_id": plan.query_plan_id,
                    "execution_config_sha256": execution_config_sha,
                    "judge_prompt_sha256": prompt_sha256(),
                    "search_provider_ids": [
                        provider.provider_id for provider in self.search_providers
                    ],
                    "judge_route_order": list(self.judge_router.route_order),
                    "judge_attempts": judge_attempts,
                    "extractor_version": EXTRACTOR_VERSION,
                    "started_at": started_at,
                    "completed_at": completed_at,
                },
                "integrity": {},
            }
        )

    def _search(
        self, queries: Sequence[Any], *, audit: RunAuditStore
    ) -> tuple[list[SearchResult], dict[str, int]]:
        rows: list[SearchResult] = []
        attempt_rows: list[dict[str, Any]] = []
        for query in queries:
            for provider in self.search_providers:
                request_row = {
                    "provider_id": provider.provider_id,
                    "query_id": query.query_id,
                    "query_class": query.query_class,
                    "query_text": query.query_text,
                    "requested_count": self.config.retrieval.results_per_query,
                }
                try:
                    result_rows = tuple(
                        provider.search(
                            query,
                            count=self.config.retrieval.results_per_query,
                        )
                    )
                    rows.extend(result_rows)
                    raw_response_method = getattr(
                        provider, "raw_response", None
                    )
                    raw_response = (
                        raw_response_method(query.query_id)
                        if callable(raw_response_method)
                        else None
                    )
                    response_ref = audit.put_json(
                        "search/responses",
                        raw_response
                        if raw_response is not None
                        else {
                            "provider_id": provider.provider_id,
                            "query_id": query.query_id,
                            "normalized_results": [
                                _search_result_payload(item)
                                for item in result_rows
                            ],
                            "raw_response_unavailable": True,
                        },
                    )
                    attempt = {
                        **request_row,
                        "outcome": "SUCCEEDED",
                        "error_code": None,
                        "result_count": len(result_rows),
                        "response_ref": response_ref,
                    }
                    for result in result_rows:
                        audit.append(
                            "search_results", _search_result_payload(result)
                        )
                except SearchProviderError as exc:
                    attempt = {
                        **request_row,
                        "outcome": "FAILED",
                        "error_code": getattr(
                            exc, "code", "SEARCH_PROVIDER_FAILED"
                        ),
                        "result_count": 0,
                        "response_ref": None,
                    }
                attempt_rows.append(attempt)
                audit.append("search_attempts", attempt)
        return rows, {
            "search_query_attempt_count": len(attempt_rows),
            "search_query_success_count": sum(
                row["outcome"] == "SUCCEEDED" for row in attempt_rows
            ),
            "search_query_failure_count": sum(
                row["outcome"] == "FAILED" for row in attempt_rows
            ),
        }

    def _prepare_evidence(
        self,
        *,
        candidate: Mapping[str, Any],
        rows: Sequence[Mapping[str, Any]],
        query_count: int,
        raw_result_count: int,
        unique_url_count: int,
        audit: RunAuditStore,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        prepared: list[dict[str, Any]] = []
        terminal_rows: list[dict[str, Any]] = []
        candidate_occurrences = 0
        surfaces = [
            candidate["known_surfaces"]["canonical"],
            *candidate["known_surfaces"]["validated_variants"],
        ]
        for row in rows:
            try:
                fetched = self.document_fetcher.fetch(row["canonical_url"])
            except FetchError as exc:
                terminal = _url_terminal(
                    row,
                    status="FETCH_FAILED",
                    error_code=exc.code,
                )
                terminal_rows.append(terminal)
                audit.append("url_attempts", terminal)
                continue
            body_ref = audit.put_bytes("fetch/bodies", fetched.body)
            try:
                extracted = extract_document(fetched)
            except ExtractionError as exc:
                extraction = {
                    "canonical_url": row["canonical_url"],
                    "outcome": "FAILED",
                    "error_code": getattr(
                        exc, "code", "EXTRACTION_FAILED"
                    ),
                    "content_sha256": fetched.content_sha256,
                    "body_ref": body_ref,
                    "text_ref": None,
                }
                audit.append("extraction_attempts", extraction)
                terminal = _url_terminal(
                    row,
                    status="EXTRACTION_FAILED",
                    error_code=extraction["error_code"],
                    body_ref=body_ref,
                )
                terminal_rows.append(terminal)
                audit.append("url_attempts", terminal)
                continue
            text_ref = audit.put_bytes(
                "extraction/texts",
                extracted.text.encode("utf-8"),
                suffix=".txt",
            )
            audit.append(
                "extraction_attempts",
                {
                    "canonical_url": row["canonical_url"],
                    "outcome": "SUCCEEDED",
                    "error_code": None,
                    "content_sha256": fetched.content_sha256,
                    "body_ref": body_ref,
                    "text_ref": text_ref,
                    "extraction_method": extracted.extraction_method,
                },
            )
            language = detect_vietnamese(extracted.text)
            if not is_vietnamese_eligible(language):
                terminal = _url_terminal(
                    row,
                    status="LANGUAGE_MISMATCH",
                    error_code=language.label,
                    body_ref=body_ref,
                    text_ref=text_ref,
                )
                terminal_rows.append(terminal)
                audit.append("url_attempts", terminal)
                continue
            snippet = build_candidate_snippet(
                extracted.text,
                surfaces,
                config=self.config.snippets,
            )
            if snippet is None:
                occurrence_count = count_candidate_occurrences(
                    extracted.text, surfaces
                )
                status = (
                    "NO_CANDIDATE_SPAN"
                    if occurrence_count == 0
                    else "SNIPPET_TOO_SHORT"
                )
                terminal = _url_terminal(
                    row,
                    status=status,
                    error_code=status,
                    body_ref=body_ref,
                    text_ref=text_ref,
                )
                terminal_rows.append(terminal)
                audit.append("url_attempts", terminal)
                continue
            candidate_occurrences += snippet.occurrence_count
            source = profile_source(
                row["canonical_url"],
                content_kind=extracted.content_kind,
                overrides=self.source_overrides,
            )
            source_tier = source.source_tier
            source_tier_reasons = set(source.source_tier_reasons)
            if extracted.extraction_method == "FALLBACK_VISIBLE_TEXT":
                source_tier_reasons.add("FALLBACK_VISIBLE_TEXT_EXTRACTION")
            evidence_id = _evidence_id(
                candidate["integrity"]["frozen_candidate_sha256"],
                row["canonical_url"],
                fetched.content_sha256,
                snippet.span_start,
                snippet.span_end,
            )
            prepared.append(
                {
                    "evidence_id": evidence_id,
                    "canonical_url": row["canonical_url"],
                    "title": extracted.title or row["title"],
                    "publisher": source.publisher,
                    "organization": source.organization,
                    "source_type": source.source_type,
                    "source_tier": source_tier,
                    "source_tier_reasons": sorted(source_tier_reasons),
                    "source_policy_version": SOURCE_POLICY_VERSION,
                    "query_ids": sorted(set(row["query_ids"])),
                    "content_sha256": fetched.content_sha256,
                    "document_text": extracted.text,
                    "extraction": {
                        "method": extracted.extraction_method,
                        "author": extracted.author,
                        "published_at": extracted.published_at,
                        "section_titles": list(extracted.section_titles),
                    },
                    "language": {
                        "label": language.label,
                        "confidence": language.confidence,
                        "detector_version": language.detector_version,
                        "reason_codes": list(language.reason_codes),
                    },
                    "snippet": {
                        "original": snippet.original,
                        "masked": snippet.masked,
                        "span_start": snippet.span_start,
                        "span_end": snippet.span_end,
                        "matched_surface": snippet.matched_surface,
                        "occurrence_count": snippet.occurrence_count,
                    },
                    "search_provider_id": row["provider_id"],
                    "fetched_at": fetched.retrieved_at,
                    "fetch_from_cache": fetched.from_cache,
                    "fetch_http_status": fetched.http_status,
                    "fetch_policy_version": fetched.fetch_policy_version,
                    "robots_status": fetched.robots_status,
                    "redirect_chain": list(fetched.redirect_chain),
                }
            )
            span_record = {
                "evidence_id": evidence_id,
                "canonical_url": row["canonical_url"],
                "matched_surface": snippet.matched_surface,
                "occurrence_count": snippet.occurrence_count,
                "snippet_sha256": hashlib.sha256(
                    snippet.original.encode("utf-8")
                ).hexdigest(),
                "language": {
                    "label": language.label,
                    "confidence": language.confidence,
                    "detector_version": language.detector_version,
                },
            }
            audit.append("span_observations", span_record)
            terminal = _url_terminal(
                row,
                status="CANDIDATE_SPAN_READY",
                error_code=None,
                body_ref=body_ref,
                text_ref=text_ref,
                evidence_id=evidence_id,
            )
            terminal_rows.append(terminal)
            audit.append("url_attempts", terminal)
        fetch_success = sum(
            row["status"] != "FETCH_FAILED" for row in terminal_rows
        )
        extraction_success = sum(
            row["status"]
            not in {"FETCH_FAILED", "EXTRACTION_FAILED"}
            for row in terminal_rows
        )
        language_eligible = sum(
            row["status"]
            not in {
                "FETCH_FAILED",
                "EXTRACTION_FAILED",
                "LANGUAGE_MISMATCH",
            }
            for row in terminal_rows
        )
        return prepared, {
            "query_count": query_count,
            "raw_result_count": raw_result_count,
            "unique_url_count": unique_url_count,
            "fetch_attempt_count": len(rows),
            "fetch_success_count": fetch_success,
            "extraction_success_count": extraction_success,
            "language_eligible_count": language_eligible,
            "candidate_span_document_count": len(prepared),
            "candidate_occurrence_count": candidate_occurrences,
            "pre_dedup_snippet_count": len(prepared),
        }

    def _judge(
        self,
        *,
        candidate: Mapping[str, Any],
        rows: Sequence[Mapping[str, Any]],
        audit: RunAuditStore,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        judged: list[dict[str, Any]] = []
        all_attempts: list[dict[str, Any]] = []
        unavailable = 0
        for raw in rows:
            row = dict(raw)
            request = JudgeRequest(
                evidence_id=row["evidence_id"],
                definition_en=candidate["sense_contract"]["definition_en"],
                scope_id=candidate["scope_id"],
                candidate_vi=candidate["candidate_vi"],
                snippet_original=row["snippet"]["original"],
                snippet_masked=row["snippet"]["masked"],
                source_type=row["source_type"],
            )
            try:
                result, attempts = self.judge_router.judge(request)
                judge = dict(result.payload)
                route_id = result.route_id
                model_id = result.model_id
                response_sha = result.response_sha256
                response_ref = audit.put_json(
                    "judge/responses", result.raw_response
                )
            except AllJudgeRoutesFailed as exc:
                attempts = exc.attempts
                unavailable += 1
                judge = validate_judge_payload(
                    {
                        "schema_id": JUDGE_SCHEMA_ID,
                        "schema_version": JUDGE_SCHEMA_VERSION,
                        "judgeability": "INSUFFICIENT_SNIPPET",
                        "concept_relation": "UNCERTAIN",
                        "domain_match": False,
                        "candidate_role": "UNDETERMINED",
                        "machine_translation_suspected": False,
                        "evidence_span": "",
                        "reason": "All configured Judge routes failed.",
                    }
                )
                route_id = "unavailable"
                model_id = "unavailable"
                response_sha = _sha(judge)
                response_ref = audit.put_json("judge/responses", judge)
            for attempt in attempts:
                raw_response = attempt.get("raw_response")
                attempt_response_ref = (
                    audit.put_json("judge/responses", raw_response)
                    if raw_response is not None
                    else (
                        response_ref
                        if attempt["outcome"] == "ACCEPTED"
                        else None
                    )
                )
                public_attempt = {
                    key: value
                    for key, value in attempt.items()
                    if key != "raw_response"
                }
                audit.append(
                    "judge_attempts",
                    {
                        **public_attempt,
                        "response_ref": attempt_response_ref,
                    },
                )
                all_attempts.append(public_attempt)
            row["judge"] = judge
            row["judge_route_id"] = route_id
            row["judge_model_id"] = model_id
            row["judge_response_sha256"] = response_sha
            judged.append(row)
        return judged, all_attempts, unavailable


def _cluster_representatives(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_cluster: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_cluster.setdefault(str(row["duplicate_cluster_id"]), []).append(row)
    tier_order = {"A": 0, "B": 1, "C": 2, "D": 3, "X": 4}
    return [
        dict(
            sorted(
                members,
                key=lambda row: (
                    tier_order[str(row["source_tier"])],
                    str(row["canonical_url"]),
                ),
            )[0]
        )
        for _, members in sorted(by_cluster.items())
    ]


def _partition_evidence(
    rows: Sequence[Mapping[str, Any]],
    *,
    machine_translation_policy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw in rows:
        reasons = rejection_reasons(raw)
        if (
            machine_translation_policy == "EXCLUDE_FROM_STRONG_POSITIVE"
            and raw["judge"]["machine_translation_suspected"]
        ):
            reasons = sorted(
                set(reasons) | {"MACHINE_TRANSLATION_SUSPECTED"}
            )
        output = {
            key: raw[key]
            for key in (
                "evidence_id",
                "canonical_url",
                "title",
                "publisher",
                "organization",
                "source_type",
                "source_tier",
                "source_tier_reasons",
                "source_policy_version",
                "query_ids",
                "content_sha256",
                "independent_cluster_id",
                "duplicate_cluster_id",
                "publisher_id",
                "organization_id",
                "independence_group_id",
                "dedup_reasons",
                "extraction",
                "language",
                "snippet",
                "judge",
            )
        }
        output["rejection_reasons"] = reasons
        output["provenance"] = {
            "search_provider_id": raw["search_provider_id"],
            "fetched_at": raw["fetched_at"],
            "fetch_from_cache": raw["fetch_from_cache"],
            "fetch_http_status": raw["fetch_http_status"],
            "fetch_policy_version": raw["fetch_policy_version"],
            "robots_status": raw["robots_status"],
            "redirect_chain": raw["redirect_chain"],
            "judge_route_id": raw["judge_route_id"],
            "judge_model_id": raw["judge_model_id"],
            "judge_prompt_sha256": prompt_sha256(),
            "judge_response_sha256": raw["judge_response_sha256"],
        }
        (rejected if reasons else accepted).append(output)
    return accepted, rejected


def _package_flags(
    *,
    candidate: Mapping[str, Any],
    base_flags: Sequence[str],
    judge_attempts: Sequence[Mapping[str, Any]],
    search_failure_count: int,
) -> list[str]:
    flags = set(base_flags)
    if search_failure_count:
        flags.add("SEARCH_PROVIDER_FAILED")
    if candidate["sense_contract"]["definition_review_status"] == "UNVERIFIED":
        flags.add("DEFINITION_UNVERIFIED")
    accepted_route_by_evidence: dict[str, int] = {}
    route_index_by_evidence: dict[str, int] = {}
    for attempt in judge_attempts:
        evidence_id = str(attempt["evidence_id"])
        route_index_by_evidence[evidence_id] = (
            route_index_by_evidence.get(evidence_id, -1) + 1
        )
        if attempt["outcome"] == "ACCEPTED":
            accepted_route_by_evidence[evidence_id] = route_index_by_evidence[
                evidence_id
            ]
    if any(index > 0 for index in accepted_route_by_evidence.values()):
        flags.add("JUDGE_FALLBACK_USED")
    return sorted(flags)


def _run_spec_id(
    *,
    frozen_sha: str,
    query_plan_id: str,
    execution_config_sha256: str,
    run_policy: Mapping[str, Any],
) -> str:
    payload = {
        "frozen_candidate_sha256": frozen_sha,
        "query_plan_id": query_plan_id,
        "execution_config_sha256": execution_config_sha256,
        "run_policy": dict(run_policy),
    }
    return "attest_spec_" + _sha(payload)[:24]


def _execution_config_sha256(
    *,
    config: AttestationConfig,
    search_providers: Sequence[SearchProvider],
    document_fetcher: DocumentFetcher,
    source_overrides: Mapping[str, Mapping[str, Any]],
    judge_router: FallbackJudgeRouter,
) -> str:
    payload = {
        "config": config.identity_payload(),
        "search_providers": [
            _component_identity(provider) for provider in search_providers
        ],
        "document_fetcher": _component_identity(document_fetcher),
        "source_overrides": {
            host: dict(value)
            for host, value in sorted(source_overrides.items())
        },
        "judge_routes": [
            _component_identity(provider)
            for provider in judge_router.providers
        ],
        "extractor_version": EXTRACTOR_VERSION,
        "source_policy_version": SOURCE_POLICY_VERSION,
        "dedup_policy_version": DEDUP_POLICY_VERSION,
        "language_detector_version": LANGUAGE_DETECTOR_VERSION,
        "judge_prompt_sha256": prompt_sha256(),
    }
    return _sha(payload)


def _component_identity(component: Any) -> dict[str, Any]:
    method = getattr(component, "identity_payload", None)
    if callable(method):
        value = method()
        if not isinstance(value, Mapping):
            raise ValueError("component identity payload must be an object")
        return dict(value)
    payload: dict[str, Any] = {
        "component": type(component).__name__,
    }
    for name in ("provider_id", "route_id", "model_id"):
        if hasattr(component, name):
            payload[name] = str(getattr(component, name))
    return payload


def _evidence_id(
    frozen_sha: str,
    canonical_url: str,
    content_sha: str,
    start: int,
    end: int,
) -> str:
    raw = "\0".join(
        (frozen_sha, canonical_url, content_sha, str(start), str(end))
    )
    return "evidence_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _sha(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _search_result_payload(row: SearchResult) -> dict[str, Any]:
    return {
        "provider_id": row.provider_id,
        "query_id": row.query_id,
        "query_text": row.query_text,
        "rank": row.rank,
        "title": row.title,
        "url": row.url,
        "canonical_url": row.canonical_url,
        "description": row.description,
    }


def _url_terminal(
    row: Mapping[str, Any],
    *,
    status: str,
    error_code: str | None,
    body_ref: Mapping[str, Any] | None = None,
    text_ref: Mapping[str, Any] | None = None,
    evidence_id: str | None = None,
) -> dict[str, Any]:
    return {
        "canonical_url": str(row["canonical_url"]),
        "query_ids": sorted(str(item) for item in row["query_ids"]),
        "terminal": True,
        "status": status,
        "error_code": error_code,
        "body_ref": dict(body_ref) if body_ref is not None else None,
        "text_ref": dict(text_ref) if text_ref is not None else None,
        "evidence_id": evidence_id,
    }


def _new_execution_id(run_spec_id: str, started_at: str) -> str:
    del run_spec_id, started_at
    return "attest_exec_" + uuid4().hex


def _validate_policy_binding(run_policy: Mapping[str, Any]) -> None:
    expected = {
        "attestation_policy_version": ATTESTATION_POLICY_VERSION,
        "query_policy_version": "query-v1",
        "source_policy_version": SOURCE_POLICY_VERSION,
        "dedup_policy_version": DEDUP_POLICY_VERSION,
        "judge_policy_version": "attestation-judge-v1",
    }
    for key, value in expected.items():
        if run_policy[key] != value:
            raise ValueError(
                f"frozen candidate {key} does not match active policy"
            )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["AttestationEngine"]
