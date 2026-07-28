"""Real-pilot, deterministic, zero-network Evidence E execution."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
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
from ..contracts.output import validate_attestation_package
from ..dataset.adapter import adapt_dataset_zip
from ..dataset.contracts import validate_adapter_candidate
from ..judging.base import (
    JudgeRequest,
    JudgeRouteResult,
    JudgeTransportError,
)
from ..judging.router import FallbackJudgeRouter
from ..retrieval.fetch import StaticDocumentFetcher
from ..retrieval.search import (
    SearchProviderError,
    StaticSearchProvider,
)
from ..retrieval.urls import canonicalize_url
from ..runtime.engine import AttestationEngine
from ..runtime.replay import AuditReplayReader
from .controlled_registry import inspect_controlled_registry


ZERO_API_SUMMARY_SCHEMA_ID = "VietnameseAttestationZeroApiPilotSummaryV1"
ZERO_API_SUMMARY_SCHEMA_VERSION = "1.0.0"
ZERO_API_POLICY_ID = "vietnamese_attestation_zero_api_pilot_v1"
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


def run_zero_api_pilot(
    *,
    source_zip: str | Path,
    parent_v3_zip: str | Path,
    output_root: str | Path,
    controlled_registry: str | Path | None = None,
) -> dict[str, Any]:
    """Run all 15 development candidates without network/provider access."""

    root = Path(output_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("zero-API output root must be absent or empty")
    root.mkdir(parents=True, exist_ok=True)
    adapter = adapt_dataset_zip(
        source_zip,
        parent_v3_zip=parent_v3_zip,
    )
    if adapter["mode"] != "DEVELOPMENT_ZERO_API":
        raise ValueError("zero-API pilot requires DEVELOPMENT_ZERO_API input")
    candidates = adapter["candidates"]
    if len(candidates) != len(SCENARIOS):
        raise ValueError("zero-API pilot requires exactly 15 candidates")
    _write_json(root / "adapter-package.json", adapter)

    result_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    for index, (raw_candidate, scenario) in enumerate(
        zip(candidates, SCENARIOS, strict=True)
    ):
        candidate = _internal_candidate(raw_candidate)
        engine = _scenario_engine(
            candidate=candidate,
            scenario=scenario,
            index=index,
            audit_root=root,
        )
        package = validate_attestation_package(engine.run(candidate))
        if package["final_glossary_decision"] is not None:
            raise RuntimeError("zero-API package emitted a final decision")
        candidate_id = package["candidate_id"]
        package_path = root / "packages" / f"{candidate_id}.json"
        _write_json(package_path, package)
        execution_id = package["provenance"]["attestation_execution_id"]
        run_root = root / "runs" / execution_id
        _write_json(run_root / "package.json", package)
        replay = _verify_replay(run_root / "run_manifest.json")
        replay_rows.append(replay)
        result_rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_version": package["candidate_version"],
                "sense_id": package["sense_id"],
                "scope_id": package["scope_id"],
                "scenario": scenario,
                "local_status": package["attestation_evidence"]["status"],
                "flags": package["attestation_evidence"]["flags"],
                "accepted_evidence_count": len(package["accepted_evidence"]),
                "rejected_evidence_count": len(package["rejected_evidence"]),
                "execution_id": execution_id,
                "started_at": package["provenance"]["started_at"],
                "completed_at": package["provenance"]["completed_at"],
                "package_ref": package_path.relative_to(root).as_posix(),
                "package_sha256": _file_sha256(package_path),
                "audit_manifest_sha256": package["audit"]["manifest_sha256"],
                "replay_status": replay["status"],
                "final_glossary_decision": None,
            }
        )

    attempts = _aggregate_attempts(root, result_rows)
    _write_jsonl(root / "provider_attempts.jsonl", attempts)
    raw_response_count = _collect_raw_responses(root, result_rows)
    replay_report = {
        "schema_id": "VietnameseAttestationZeroApiReplayReportV1",
        "schema_version": "1.0.0",
        "run_count": len(replay_rows),
        "all_content_verified": all(
            row["status"] == "PASS" for row in replay_rows
        ),
        "runs": replay_rows,
        "provider_call_count": 0,
    }
    _write_json(root / "replay_report.json", replay_report)

    controlled_report = (
        inspect_controlled_registry(controlled_registry)
        if controlled_registry is not None
        else {
            "schema_id": "ControlledVietnameseRegistryInspectionV1",
            "schema_version": "1.0.0",
            "status": "NOT_SUPPLIED",
            "row_count": 0,
            "blockers": ["CONTROLLED_REGISTRY_NOT_SUPPLIED"],
            "retrieval_provider_created": False,
            "provider_call_count": 0,
        }
    )
    _write_json(root / "controlled_corpus_adapter_report.json", controlled_report)
    projection_report = _projection_report(adapter)
    _write_json(root / "contract_projection_report.json", projection_report)
    provider_report = {
        "schema_id": "VietnameseAttestationProviderCanaryReportV1",
        "schema_version": "1.0.0",
        "status": "HOLD_NOT_RUN_ZERO_API_PHASE",
        "routes": ["brave", "shopai", "ckey", "gemini_official"],
        "external_provider_call_count": 0,
    }
    _write_json(root / "provider_canary_report.json", provider_report)

    status_counts: dict[str, int] = {}
    for row in result_rows:
        status = row["local_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "schema_id": ZERO_API_SUMMARY_SCHEMA_ID,
        "schema_version": ZERO_API_SUMMARY_SCHEMA_VERSION,
        "policy_id": ZERO_API_POLICY_ID,
        "mode": adapter["mode"],
        "source_manifest_sha256": adapter["source"]["manifest_sha256"],
        "parent_dataset_manifest_sha256": adapter["source"][
            "parent_dataset_manifest_sha256"
        ],
        "candidate_count": len(result_rows),
        "scenario_count": len(SCENARIOS),
        "scenario_coverage": list(SCENARIOS),
        "status_counts": dict(sorted(status_counts.items())),
        "run_results": result_rows,
        "audit_manifest_count": len(result_rows),
        "replay_pass_count": sum(
            row["status"] == "PASS" for row in replay_rows
        ),
        "fixture_provider_attempt_count": len(attempts),
        "raw_response_count": raw_response_count,
        "external_provider_call_count": 0,
        "contract_projection_status": projection_report["status"],
        "controlled_corpus_status": controlled_report["status"],
        "final_glossary_decision": None,
        "integrity": {"self_sha256": "0" * 64},
    }
    summary["integrity"]["self_sha256"] = _self_sha256(summary)
    _write_json(root / "pilot_zero_api_summary.json", summary)
    _write_json(
        root / "zero_api_artifact_manifest.json",
        _artifact_manifest(root),
    )
    return summary


def _internal_candidate(raw: Mapping[str, Any]) -> dict[str, Any]:
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


def _scenario_engine(
    *,
    candidate: Mapping[str, Any],
    scenario: str,
    index: int,
    audit_root: Path,
) -> AttestationEngine:
    rows, documents, overrides = _scenario_documents(candidate, scenario)
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
        source_overrides=overrides,
        clock=lambda: next(timestamps),
        audit_store_root=audit_root,
        execution_id_factory=lambda run_spec_id, timestamp: execution_id,
    )


def _scenario_documents(
    candidate: Mapping[str, Any], scenario: str
) -> tuple[
    list[dict[str, str]],
    dict[str, tuple[str, str | bytes]],
    dict[str, dict[str, Any]],
]:
    urls = [
        "https://one.edu.vn/evidence/a",
        "https://two.gov.vn/evidence/b",
    ]
    documents: dict[str, tuple[str, str | bytes]] = {}
    overrides: dict[str, dict[str, Any]] = {}
    if scenario == "SEARCH_FAILURE":
        return [], documents, overrides
    if scenario == "FETCH_TIMEOUT":
        return [_search_row(urls[0], "Fetch timeout")], documents, overrides
    if scenario == "EXTRACTION_FAILURE":
        documents[canonicalize_url(urls[0])] = (
            "application/octet-stream",
            b"unsupported fixture content",
        )
        return [_search_row(urls[0], "Extraction failure")], documents, overrides
    if scenario == "UNKNOWN_PDF":
        documents[canonicalize_url(urls[0])] = (
            "application/pdf",
            b"not-a-valid-pdf",
        )
        return [_search_row(urls[0], "Unknown PDF")], documents, overrides
    if scenario == "NON_VIETNAMESE":
        documents[canonicalize_url(urls[0])] = (
            "text/html",
            _document("an unrelated English expression", "SCENARIO_SAME", english=True),
        )
        return [_search_row(urls[0], "Non Vietnamese")], documents, overrides
    if scenario == "CANDIDATE_SPAN_ABSENT":
        documents[canonicalize_url(urls[0])] = (
            "text/html",
            _document("một biểu thức hoàn toàn khác", "SCENARIO_SAME"),
        )
        return [_search_row(urls[0], "Missing span")], documents, overrides

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
    return [_search_row(url, scenario) for url in urls], documents, overrides


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
            request_sha256=_canonical_sha256(request_payload),
            response_sha256=_canonical_sha256(payload),
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


def _verify_replay(manifest_path: Path) -> dict[str, Any]:
    reader = AuditReplayReader(manifest_path)
    reader.verify_all_content()
    modes: dict[str, dict[str, int]] = {}
    for mode in reader.manifest["replay_modes"]:
        replay = reader.replay(mode)
        modes[mode] = {
            name: len(rows) for name, rows in replay["streams"].items()
        }
    return {
        "execution_id": reader.manifest["attestation_execution_id"],
        "run_spec_id": reader.manifest["run_spec_id"],
        "status": "PASS",
        "modes": modes,
    }


def _aggregate_attempts(
    root: Path, result_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for result in result_rows:
        run_root = root / "runs" / str(result["execution_id"])
        for kind, relative in (
            ("SEARCH", "search/requests.jsonl"),
            ("JUDGE", "judge/attempts.jsonl"),
        ):
            path = run_root / relative
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                audit_attempt = json.loads(line)
                query_text = audit_attempt.get("query_text")
                request_sha256 = audit_attempt.get("request_sha256")
                if request_sha256 is None:
                    request_sha256 = _canonical_sha256(
                        {
                            key: audit_attempt.get(key)
                            for key in (
                                "provider_id",
                                "query_id",
                                "query_class",
                                "query_text",
                                "requested_count",
                            )
                        }
                    )
                response_sha256 = audit_attempt.get("response_sha256")
                response_ref = audit_attempt.get("response_ref")
                if response_sha256 is None and isinstance(
                    response_ref, Mapping
                ):
                    response_sha256 = response_ref.get("artifact_sha256")
                input_tokens = int(audit_attempt.get("input_tokens") or 0)
                output_tokens = int(audit_attempt.get("output_tokens") or 0)
                attempts.append(
                    {
                        "run_id": result["execution_id"],
                        "candidate_id": result["candidate_id"],
                        "execution_id": result["execution_id"],
                        "attempt_kind": kind,
                        "provider_id": audit_attempt.get("provider_id")
                        or audit_attempt.get("route_id"),
                        "model_id": audit_attempt.get("model_id"),
                        "query_hash": (
                            _canonical_sha256(query_text)
                            if isinstance(query_text, str)
                            else None
                        ),
                        "request_hash": request_sha256,
                        "response_hash": response_sha256,
                        "status": audit_attempt.get("outcome"),
                        "retry_index": 0,
                        "failure_reason": audit_attempt.get("error_code"),
                        "started_at": result["started_at"],
                        "completed_at": result["completed_at"],
                        "token_usage": {
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens,
                        },
                        "latency_ms": 0,
                        "external_api": False,
                        "audit_attempt": audit_attempt,
                    }
                )
    return attempts


def _collect_raw_responses(
    root: Path, result_rows: Sequence[Mapping[str, Any]]
) -> int:
    destination = root / "raw_responses"
    count = 0
    for result in result_rows:
        execution_id = str(result["execution_id"])
        run_root = root / "runs" / execution_id
        for namespace in ("search/responses", "judge/responses"):
            source = run_root / namespace
            if not source.is_dir():
                continue
            target = destination / execution_id / namespace
            target.mkdir(parents=True, exist_ok=True)
            for path in sorted(source.iterdir()):
                if not path.is_file() or path.name.endswith(".tmp"):
                    continue
                copied = target / path.name
                shutil.copyfile(path, copied)
                if _file_sha256(copied) != path.name.split(".", 1)[0]:
                    raise RuntimeError("raw response hash drift during copy")
                count += 1
    return count


def _projection_report(adapter: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "candidate_id": row["candidate_id"],
            "status": "BLOCKED_DEVELOPMENT_IDENTITY",
            "reason_codes": [
                "EFFECTIVE_SENSE_CONTRACT_SHA256_UNAVAILABLE",
                "KNOWN_VIETNAMESE_SURFACES_UNAVAILABLE",
                "DOMAIN_ANCHORS_UNAVAILABLE",
            ],
        }
        for row in adapter["candidates"]
    ]
    return {
        "schema_id": "VietnameseAttestationContractProjectionReportV1",
        "schema_version": "1.0.0",
        "authority_schema_id": "AttestationEvidencePackageV1",
        "authority_schema_version": "1.1.0",
        "status": "BLOCKED_DEVELOPMENT_IDENTITY",
        "projected_package_count": 0,
        "blocked_candidate_count": len(rows),
        "candidates": rows,
        "final_glossary_decision": None,
    }


def _artifact_manifest(root: Path) -> dict[str, Any]:
    manifest_name = "zero_api_artifact_manifest.json"
    files = [
        {
            "artifact_ref": path.relative_to(root).as_posix(),
            "artifact_sha256": _file_sha256(path),
            "byte_count": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name != manifest_name
        and not path.name.endswith(".tmp")
    ]
    manifest = {
        "schema_id": "VietnameseAttestationZeroApiArtifactManifestV1",
        "schema_version": "1.0.0",
        "file_count": len(files),
        "files": files,
        "external_provider_call_count": 0,
        "final_glossary_decision": None,
        "integrity": {"self_sha256": "0" * 64},
    }
    manifest["integrity"]["self_sha256"] = _self_sha256(manifest)
    return manifest


def _write_json(path: Path, value: Any) -> None:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    raw = "".join(
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
        for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


def _self_sha256(value: Mapping[str, Any]) -> str:
    payload = json.loads(json.dumps(value, ensure_ascii=False))
    payload["integrity"]["self_sha256"] = "0" * 64
    return _canonical_sha256(payload)


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "SCENARIOS",
    "ZERO_API_POLICY_ID",
    "ZERO_API_SUMMARY_SCHEMA_ID",
    "ZERO_API_SUMMARY_SCHEMA_VERSION",
    "run_zero_api_pilot",
]
