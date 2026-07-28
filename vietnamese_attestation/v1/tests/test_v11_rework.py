from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any, Mapping

import pytest

from .conftest import judge_payload

from vietnamese_attestation.v1.config import (
    AttestationConfig,
    RetrievalConfig,
    SnippetConfig,
    StatusConfig,
)
from vietnamese_attestation.v1.contracts.base import ContractValidationError
from vietnamese_attestation.v1.contracts.output import (
    seal_attestation_package,
)
from vietnamese_attestation.v1.evidence.sources import (
    profile_source,
)
from vietnamese_attestation.v1.evidence.spans import (
    build_candidate_snippet,
)
from vietnamese_attestation.v1.judging import (
    FallbackJudgeRouter,
    StaticJudgeProvider,
)
from vietnamese_attestation.v1.retrieval import (
    AllowAllRobotsPolicy,
    DiskFetchCache,
    HttpDocumentFetcher,
    NoopRateLimiter,
    StaticDocumentFetcher,
    StaticSearchProvider,
)
from vietnamese_attestation.v1.retrieval.extraction import (
    extract_document,
)
from vietnamese_attestation.v1.retrieval.urls import (
    canonicalize_url,
)
from vietnamese_attestation.v1.runtime.engine import (
    AttestationEngine,
)
from vietnamese_attestation.v1.runtime.replay import (
    AuditReplayReader,
)


def test_general_word_cannot_be_attested(
    frozen_candidate: dict[str, Any],
) -> None:
    surface = str(frozen_candidate["candidate_vi"])
    urls = [
        "https://one.gov.vn/guide",
        "https://two.edu.vn/guide",
    ]
    payload = judge_payload()
    payload["candidate_role"] = "GENERAL_WORD"
    package = _engine(
        urls=urls,
        documents={url: _technical_document(surface, index) for index, url in enumerate(urls)},
        judge_value=payload,
    ).run(frozen_candidate)
    assert package["attestation_evidence"]["status"] != "ATTESTED"
    assert package["accepted_evidence"] == []
    assert all(
        "NON_TECHNICAL_ROLE" in row["rejection_reasons"]
        for row in package["rejected_evidence"]
    )


def test_attested_without_accepted_evidence_is_rejected(
    frozen_candidate: dict[str, Any],
) -> None:
    package = _engine(
        urls=[], documents={}, judge_value=judge_payload()
    ).run(frozen_candidate)
    forged = copy.deepcopy(package)
    forged["attestation_evidence"]["status"] = "ATTESTED"
    with pytest.raises(ContractValidationError, match="ATTESTED requires"):
        seal_attestation_package(forged)


def test_machine_translation_exclusion_policy_is_explicit(
    frozen_candidate: dict[str, Any],
) -> None:
    surface = str(frozen_candidate["candidate_vi"])
    urls = ["https://one.gov.vn/a", "https://two.edu.vn/b"]
    payload = judge_payload()
    payload["machine_translation_suspected"] = True
    package = _engine(
        urls=urls,
        documents={url: _technical_document(surface, index) for index, url in enumerate(urls)},
        judge_value=payload,
        status=StatusConfig(
            machine_translation_suspicion_policy=(
                "EXCLUDE_FROM_STRONG_POSITIVE"
            )
        ),
    ).run(frozen_candidate)
    assert package["accepted_evidence"] == []
    assert package["attestation_evidence"]["status"] != "ATTESTED"


def test_span_yield_prevents_full_coverage(
    frozen_candidate: dict[str, Any],
) -> None:
    surface = str(frozen_candidate["candidate_vi"])
    urls = [f"https://source-{index}.edu.vn/doc" for index in range(20)]
    documents = {
        url: (
            _technical_document(surface, index)
            if index < 2
            else _vietnamese_document_without_candidate(index)
        )
        for index, url in enumerate(urls)
    }
    package = _engine(
        urls=urls,
        documents=documents,
        judge_value=judge_payload(),
    ).run(frozen_candidate)
    coverage = package["attestation_evidence"]["coverage_breakdown"]
    assert package["attestation_evidence"]["counts"][
        "candidate_span_document_count"
    ] == 2
    assert coverage["span_yield"] == 0.1
    assert package["attestation_evidence"]["features"]["E_coverage"] == 0.1


def test_unknown_pdf_is_not_promoted_to_tier_b() -> None:
    profile = profile_source(
        "https://spam-example.com/file.pdf", content_kind="pdf"
    )
    assert profile.source_tier == "D"
    assert profile.source_tier_reasons == ("UNVERIFIED_PDF_HOST",)


def test_cache_preserves_original_retrieved_at(tmp_path: Path) -> None:
    cache = DiskFetchCache(tmp_path / "cache")

    def bytes_get(url, headers, timeout, max_bytes):
        del url, headers, timeout, max_bytes
        return b"du lieu van ban", "text/plain"

    first_fetcher = HttpDocumentFetcher(
        cache=cache,
        robots=AllowAllRobotsPolicy(),
        rate_limiter=NoopRateLimiter(),
        bytes_get=bytes_get,
        clock=lambda: "2026-01-01T00:00:00Z",
    )
    first = first_fetcher.fetch("https://example.edu.vn/document")
    second_fetcher = HttpDocumentFetcher(
        cache=cache,
        robots=AllowAllRobotsPolicy(),
        rate_limiter=NoopRateLimiter(),
        bytes_get=lambda *args: (_ for _ in ()).throw(AssertionError("network")),
        clock=lambda: "2026-02-01T00:00:00Z",
    )
    second = second_fetcher.fetch("https://example.edu.vn/document")
    assert first.retrieved_at == "2026-01-01T00:00:00Z"
    assert second.retrieved_at == first.retrieved_at
    assert second.from_cache


def test_each_execution_has_unique_id_but_stable_spec(
    frozen_candidate: dict[str, Any],
) -> None:
    surface = str(frozen_candidate["candidate_vi"])
    url = "https://one.edu.vn/guide"
    first = _engine(
        urls=[url],
        documents={url: _technical_document(surface, 1)},
        judge_value=judge_payload(),
    ).run(frozen_candidate)
    second = _engine(
        urls=[url],
        documents={url: _technical_document(surface, 1)},
        judge_value=judge_payload(),
    ).run(frozen_candidate)
    assert first["provenance"]["run_spec_id"] == second["provenance"][
        "run_spec_id"
    ]
    assert first["provenance"]["attestation_execution_id"] != second[
        "provenance"
    ]["attestation_execution_id"]


def test_file_audit_store_keeps_terminal_urls_and_invalid_judge_raw(
    tmp_path: Path,
    frozen_candidate: dict[str, Any],
) -> None:
    surface = str(frozen_candidate["candidate_vi"])
    urls = ["https://one.edu.vn/a", "https://two.edu.vn/b"]
    engine = _engine(
        urls=urls,
        documents={
            urls[0]: _technical_document(surface, 1),
            urls[1]: _vietnamese_document_without_candidate(2),
        },
        judge_value={"raw_marker": "BROKEN_RAW"},
        audit_store_root=tmp_path,
        execution_id_factory=lambda spec, started: "attest_exec_fixed_001",
    )
    package = engine.run(frozen_candidate)
    run_root = tmp_path / "runs" / "attest_exec_fixed_001"
    terminal_rows = _jsonl(run_root / "fetch" / "attempts.jsonl")
    assert len(terminal_rows) == 2
    assert all(row["terminal"] is True for row in terminal_rows)
    assert {row["status"] for row in terminal_rows} == {
        "CANDIDATE_SPAN_READY",
        "NO_CANDIDATE_SPAN",
    }
    raw_responses = list((run_root / "judge" / "responses").glob("*.json"))
    assert any("BROKEN_RAW" in path.read_text(encoding="utf-8") for path in raw_responses)
    assert set(package["audit"]["replay_modes"]) == {
        "REPLAY_FROM_SEARCH",
        "REPLAY_FROM_FETCH",
        "REPLAY_FROM_EXTRACTION",
        "REPLAY_FROM_SNIPPETS",
        "REPLAY_FROM_JUDGE",
    }
    assert package["audit"]["store_mode"] == "FILE"
    assert package["cost_report"]["price_status"] == "UNKNOWN"
    assert package["cost_report"]["estimated_total_cost"] is None
    assert package["cost_report"]["search_requests"] == 3
    reader = AuditReplayReader(run_root / "run_manifest.json")
    reader.verify_all_content()
    replay = reader.replay("REPLAY_FROM_JUDGE")
    assert len(replay["streams"]["url_attempts"]) == 2


def test_main_content_excludes_navigation_only_candidate(
    frozen_candidate: dict[str, Any],
) -> None:
    surface = str(frozen_candidate["candidate_vi"])
    url = "https://example.edu.vn/navigation"
    fetched = StaticDocumentFetcher(
        {
            canonicalize_url(url): (
                "text/html",
                f"<nav>{surface}</nav><main>Trong hoc may, tai lieu nay mo ta "
                "mo hinh va du lieu dau vao bang nhieu noi dung ky thuat "
                "nhung khong lap lai cum tu trong thanh dieu huong.</main>",
            )
        }
    ).fetch(canonicalize_url(url))
    extracted = extract_document(fetched)
    assert extracted.extraction_method == "MAIN_CONTENT_EXTRACTED"
    assert build_candidate_snippet(
        extracted.text,
        [surface],
        config=SnippetConfig(min_words=5),
    ) is None


def test_non_vietnamese_page_is_not_sent_to_judge(
    frozen_candidate: dict[str, Any],
    tmp_path: Path,
) -> None:
    surface = str(frozen_candidate["candidate_vi"])
    url = "https://example.edu.vn/english"
    engine = _engine(
        urls=[url],
        documents={
            url: (
                "<main>The model uses "
                + surface
                + " in this English document and the system is designed "
                "for data from the model with the output of the process "
                "and the input to the machine learning service.</main>"
            )
        },
        judge_value=judge_payload(),
        audit_store_root=tmp_path,
        execution_id_factory=lambda spec, started: "attest_exec_language_001",
    )
    package = engine.run(frozen_candidate)
    assert package["attestation_evidence"]["counts"][
        "language_eligible_count"
    ] == 0
    assert package["attestation_evidence"]["counts"][
        "judged_cluster_count"
    ] == 0
    terminal = _jsonl(
        tmp_path
        / "runs"
        / "attest_exec_language_001"
        / "fetch"
        / "attempts.jsonl"
    )
    assert terminal[0]["status"] == "LANGUAGE_MISMATCH"


def test_min_words_is_enforced() -> None:
    assert build_candidate_snippet(
        "Day la suy luan.",
        ["suy luan"],
        config=SnippetConfig(min_words=20),
    ) is None


def _engine(
    *,
    urls: list[str],
    documents: Mapping[str, str],
    judge_value: Mapping[str, Any],
    audit_store_root: Path | None = None,
    execution_id_factory=None,
    status: StatusConfig | None = None,
) -> AttestationEngine:
    rows = [{"url": url, "title": f"Document {index}"} for index, url in enumerate(urls)]
    search = StaticSearchProvider(
        "fixture_search",
        {
            "EXACT_CANDIDATE": rows,
            "CANDIDATE_DOMAIN": rows,
            "CANDIDATE_SOURCE_TERM": rows,
        },
    )
    fetcher = StaticDocumentFetcher(
        {
            canonicalize_url(url): ("text/html", text)
            for url, text in documents.items()
        }
    )
    judge = StaticJudgeProvider(
        route_id="fixture_judge",
        model_id="fixture-model",
        payloads_by_evidence_id={"*": judge_value},
    )
    timestamps = iter(["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"])
    return AttestationEngine(
        search_providers=[search],
        document_fetcher=fetcher,
        judge_router=FallbackJudgeRouter([judge]),
        config=AttestationConfig(
            retrieval=RetrievalConfig(
                results_per_query=max(10, len(urls)),
                max_unique_urls=max(20, len(urls)),
                max_fetches=max(20, len(urls)),
            ),
            status=status or StatusConfig(),
            search_provider_ids=("fixture_search",),
            judge_route_order=("fixture_judge",),
        ),
        clock=lambda: next(timestamps),
        audit_store_root=audit_store_root,
        execution_id_factory=execution_id_factory,
    )


def _technical_document(surface: str, index: int) -> str:
    return (
        "<main>Trong hoc may, "
        + surface
        + " la qua trinh mo hinh da huan luyen tao du doan cho du lieu moi. "
        + f"Tai lieu ky thuat so {index} mo ta dau vao, tham so, he thong va "
        "cach trien khai mo hinh trong moi truong tinh toan thuc te.</main>"
    )


def _vietnamese_document_without_candidate(index: int) -> str:
    return (
        "<main>Trong hoc may, tai lieu ky thuat so "
        + str(index)
        + " mo ta mo hinh, du lieu, tham so va cach he thong tao du doan "
        "cho dau vao moi bang mot quy trinh tinh toan co nhieu buoc.</main>"
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
