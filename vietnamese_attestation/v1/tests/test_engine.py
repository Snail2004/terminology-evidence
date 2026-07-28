from __future__ import annotations

import copy

import pytest

from .conftest import judge_payload

from vietnamese_attestation.v1.contracts.base import ContractValidationError
from vietnamese_attestation.v1.config import (
    AttestationConfig,
    RetrievalConfig,
)
from vietnamese_attestation.v1.contracts.output import (
    validate_attestation_package,
)
from vietnamese_attestation.v1.judging import (
    FallbackJudgeRouter,
    JudgeTransportError,
    StaticJudgeProvider,
)
from vietnamese_attestation.v1.retrieval import (
    StaticDocumentFetcher,
    StaticSearchProvider,
)
from vietnamese_attestation.v1.retrieval.search import (
    SearchProviderError,
)
from vietnamese_attestation.v1.retrieval.urls import (
    canonicalize_url,
)
from vietnamese_attestation.v1.runtime.engine import (
    AttestationEngine,
)


def test_strong_attestation_collapses_duplicate_echo(
    frozen_candidate: dict[str, object],
) -> None:
    urls = [
        "https://hoclieu.gov.vn/ml/inference",
        "https://mirror.example.com/copied-inference",
        "https://lab.edu.vn/guide/inference",
    ]
    search = _search_provider(urls)
    shared = (
        "<html><title>Cẩm nang</title><body>Trong học máy, suy luận là "
        "quá trình mô hình đã huấn luyện tạo dự đoán cho dữ liệu mới. "
        "Nội dung này trình bày kỹ thuật triển khai mô hình.</body></html>"
    )
    independent = (
        "<html><title>Giáo trình</title><body>Một mô hình học máy thực hiện "
        "suy luận để sinh đầu ra trên mẫu chưa từng thấy. Tài liệu mô tả "
        "quá trình dự đoán trong triển khai.</body></html>"
    )
    fetcher = StaticDocumentFetcher(
        {
            canonicalize_url(urls[0]): ("text/html", shared),
            canonicalize_url(urls[1]): ("text/html", shared),
            canonicalize_url(urls[2]): ("text/html", independent),
        }
    )
    judge = StaticJudgeProvider(
        route_id="fixture_judge",
        model_id="fixture-model",
        payloads_by_evidence_id={"*": judge_payload()},
    )
    package = _engine(search, fetcher, [judge]).run(frozen_candidate)
    assert package["attestation_evidence"]["status"] == "ATTESTED"
    assert package["attestation_evidence"]["counts"][
        "independent_cluster_count"
    ] == 2
    assert package["attestation_evidence"]["counts"][
        "unique_url_count"
    ] == 3
    assert len(package["accepted_evidence"]) == 2
    assert sorted(
        len(cluster["member_evidence_ids"])
        for cluster in package["dedup_clusters"]
    ) == [1, 2]
    assert any(
        "EXACT_CONTENT_HASH" in cluster["dedup_reasons"]
        for cluster in package["dedup_clusters"]
    )
    assert "DUPLICATE_ECHO_COLLAPSED" in package["attestation_evidence"]["flags"]
    assert package["final_glossary_decision"] is None
    validate_attestation_package(package)


def test_wrong_sense_is_not_retried_or_accepted(
    frozen_candidate: dict[str, object],
) -> None:
    url = "https://journal.edu.vn/logic"
    search = _search_provider([url])
    fetcher = StaticDocumentFetcher(
        {
            canonicalize_url(url): (
                "text/html",
                "<p>Trong logic hình thức, suy luận là phép dẫn xuất mệnh đề "
                "từ các tiên đề và quy tắc chứng minh.</p>",
            )
        }
    )
    first = StaticJudgeProvider(
        route_id="fixture_judge",
        model_id="fixture-model",
        payloads_by_evidence_id={"*": judge_payload("DIFFERENT")},
    )
    second = StaticJudgeProvider(
        route_id="unused_fallback",
        model_id="fixture-model-2",
        payloads_by_evidence_id={"*": judge_payload()},
    )
    package = _engine(search, fetcher, [first, second]).run(frozen_candidate)
    assert package["attestation_evidence"]["status"] == "NOT_ATTESTED"
    assert len(package["accepted_evidence"]) == 0
    assert package["rejected_evidence"][0]["rejection_reasons"] == [
        "CONCEPT_DIFFERENT"
    ]
    assert second.calls == []


def test_related_concept_is_supporting_but_not_accepted(
    frozen_candidate: dict[str, object],
) -> None:
    url = "https://lab.edu.vn/related"
    package = _engine(
        _search_provider([url]),
        StaticDocumentFetcher(
            {
                canonicalize_url(url): (
                    "text/html",
                    "<p>Suy luận là một thao tác liên quan trong học máy và "
                    "được dùng khi mô hình xử lý dữ liệu mới trong hệ thống "
                    "dự đoán có nhiều bước kỹ thuật cần được giải thích.</p>",
                )
            }
        ),
        [
            StaticJudgeProvider(
                route_id="fixture_judge",
                model_id="fixture-model",
                payloads_by_evidence_id={"*": judge_payload("RELATED")},
            )
        ],
    ).run(frozen_candidate)
    assert package["accepted_evidence"] == []
    assert package["rejected_evidence"][0]["rejection_reasons"] == [
        "CONCEPT_RELATED"
    ]
    assert package["attestation_evidence"]["status"] == "WEAKLY_ATTESTED"


def test_exhausted_judge_routes_is_unjudgeable_not_negative(
    frozen_candidate: dict[str, object],
) -> None:
    url = "https://lab.edu.vn/inference"
    search = _search_provider([url])
    fetcher = StaticDocumentFetcher(
        {
            canonicalize_url(url): (
                "text/html",
                "<p>Suy luận giúp mô hình đã huấn luyện tạo đầu ra cho dữ "
                "liệu mới trong hệ thống học máy.</p>",
            )
        }
    )
    failed = StaticJudgeProvider(
        route_id="fixture_judge",
        model_id="fixture-model",
        payloads_by_evidence_id={
            "*": JudgeTransportError("timeout", "provider timeout")
        },
    )
    package = _engine(search, fetcher, [failed]).run(frozen_candidate)
    assert (
        package["attestation_evidence"]["status"]
        == "ATTESTATION_UNJUDGEABLE"
    )
    assert (
        package["recommendation_to_global_validator"]
        == "EVIDENCE_UNJUDGEABLE"
    )
    assert package["final_glossary_decision"] is None


def test_package_hash_rejects_tampering(
    frozen_candidate: dict[str, object],
) -> None:
    url = "https://lab.edu.vn/inference"
    package = _engine(
        _search_provider([url]),
        StaticDocumentFetcher(
            {
                canonicalize_url(url): (
                    "text/html",
                    "<p>Suy luận giúp mô hình tạo dự đoán cho dữ liệu mới "
                    "trong hệ thống học máy, đồng thời mô tả cách đầu ra được "
                    "tính từ tham số đã huấn luyện và mẫu đầu vào cụ thể.</p>",
                )
            }
        ),
        [
            StaticJudgeProvider(
                route_id="fixture_judge",
                model_id="fixture-model",
                payloads_by_evidence_id={"*": judge_payload()},
            )
        ],
    ).run(frozen_candidate)
    tampered = copy.deepcopy(package)
    tampered["attestation_evidence"]["features"]["E_concept"] = 0
    with pytest.raises(ContractValidationError, match="self-hash mismatch"):
        validate_attestation_package(tampered)


def test_search_failure_is_reported_without_fabricating_evidence(
    frozen_candidate: dict[str, object],
) -> None:
    class FailedSearch:
        provider_id = "failed_search"

        def search(self, query, *, count):
            del query, count
            raise SearchProviderError("offline search failure")

    judge = StaticJudgeProvider(
        route_id="fixture_judge",
        model_id="fixture-model",
        payloads_by_evidence_id={"*": judge_payload()},
    )
    timestamps = iter(
        ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"]
    )
    package = AttestationEngine(
        search_providers=[FailedSearch()],
        document_fetcher=StaticDocumentFetcher({}),
        judge_router=FallbackJudgeRouter([judge]),
        config=AttestationConfig(
            search_provider_ids=("failed_search",),
            judge_route_order=("fixture_judge",),
        ),
        clock=lambda: next(timestamps),
    ).run(frozen_candidate)
    assert package["accepted_evidence"] == []
    assert package["rejected_evidence"] == []
    assert "SEARCH_PROVIDER_FAILED" in package["attestation_evidence"]["flags"]
    assert package["final_glossary_decision"] is None


def test_unexpected_extraction_failure_is_not_silenced(
    frozen_candidate: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://lab.edu.vn/inference"
    engine = _engine(
        _search_provider([url]),
        StaticDocumentFetcher(
            {
                canonicalize_url(url): (
                    "text/html",
                    "<p>Suy luan cho du lieu moi trong hoc may.</p>",
                )
            }
        ),
        [
            StaticJudgeProvider(
                route_id="fixture_judge",
                model_id="fixture-model",
                payloads_by_evidence_id={"*": judge_payload()},
            )
        ],
    )
    monkeypatch.setattr(
        "vietnamese_attestation.v1.runtime.engine.extract_document",
        lambda document: (_ for _ in ()).throw(AssertionError("bug")),
    )
    with pytest.raises(AssertionError, match="bug"):
        engine.run(frozen_candidate)


def _search_provider(urls: list[str]) -> StaticSearchProvider:
    rows = [{"url": url, "title": f"Document {index}"} for index, url in enumerate(urls)]
    return StaticSearchProvider(
        "fixture_search",
        {
            "EXACT_CANDIDATE": rows,
            "CANDIDATE_DOMAIN": rows,
            "CANDIDATE_SOURCE_TERM": rows,
        },
    )


def _engine(
    search: StaticSearchProvider,
    fetcher: StaticDocumentFetcher,
    judges: list[StaticJudgeProvider],
) -> AttestationEngine:
    timestamps = iter(
        ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"]
    )
    return AttestationEngine(
        search_providers=[search],
        document_fetcher=fetcher,
        judge_router=FallbackJudgeRouter(judges),
        config=AttestationConfig(
            retrieval=RetrievalConfig(min_fetch_coverage=0.5),
            search_provider_ids=("fixture_search",),
            judge_route_order=tuple(judge.route_id for judge in judges),
        ),
        clock=lambda: next(timestamps),
    )
