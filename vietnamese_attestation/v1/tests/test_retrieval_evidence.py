from __future__ import annotations

from vietnamese_attestation.v1.config import (
    SnippetConfig,
)
from vietnamese_attestation.v1.evidence.dedup import (
    cluster_evidence_documents,
)
from vietnamese_attestation.v1.evidence.spans import (
    build_candidate_snippet,
)
from vietnamese_attestation.v1.retrieval import (
    AllowAllRobotsPolicy,
    BraveSearchProvider,
    DiskFetchCache,
    HostRateLimiter,
    HttpDocumentFetcher,
    NoopRateLimiter,
)
from vietnamese_attestation.v1.retrieval.query import (
    QuerySpec,
)
from vietnamese_attestation.v1.retrieval.urls import (
    canonicalize_url,
)


def test_url_canonicalization_removes_tracking_only() -> None:
    assert canonicalize_url(
        "HTTPS://Example.COM:443/a/../b?q=2&utm_source=x&q=1#fragment"
    ) == "https://example.com/b?q=1&q=2"


def test_candidate_span_builds_exact_mask() -> None:
    text = (
        "Trong học máy, quá trình suy luận cho phép mô hình tạo dự đoán "
        "cho dữ liệu mới."
    )
    snippet = build_candidate_snippet(
        text,
        ["suy luận", "quá trình suy luận"],
        config=SnippetConfig(
            words_before=3, words_after=6, min_words=5, max_words=20
        ),
    )
    assert snippet is not None
    assert snippet.matched_surface == "quá trình suy luận"
    assert snippet.masked == (
        snippet.original[: snippet.span_start]
        + "[TERM]"
        + snippet.original[snippet.span_end :]
    )


def test_duplicate_echo_collapses_but_same_organization_does_not() -> None:
    rows = [
        {
            "canonical_url": "https://a.edu.vn/one",
            "organization": "a.edu.vn",
            "document_text": "Suy luận tạo dự đoán từ mô hình đã huấn luyện.",
        },
        {
            "canonical_url": "https://mirror.vn/copy",
            "organization": "mirror.vn",
            "document_text": "Suy luận tạo dự đoán từ mô hình đã huấn luyện.",
        },
        {
            "canonical_url": "https://a.edu.vn/two",
            "organization": "a.edu.vn",
            "document_text": "Một tài liệu khác của cùng tổ chức.",
        },
        {
            "canonical_url": "https://b.gov.vn/unique",
            "organization": "b.gov.vn",
            "document_text": "Dữ liệu độc lập mô tả suy luận trên đầu vào mới.",
        },
    ]
    clustered = cluster_evidence_documents(rows)
    ids = [row["independent_cluster_id"] for row in clustered]
    assert ids[0] == ids[1]
    assert ids[2] != ids[0]
    assert ids[3] != ids[0]


def test_http_fetch_retries_timeout_and_caches_success(tmp_path) -> None:
    calls = 0

    def bytes_get(url, headers, timeout, max_bytes):
        nonlocal calls
        del url, headers, timeout, max_bytes
        calls += 1
        if calls == 1:
            raise TimeoutError("transient timeout")
        return b"retrieved text", "text/plain"

    fetcher = HttpDocumentFetcher(
        cache=DiskFetchCache(tmp_path / "cache"),
        robots=AllowAllRobotsPolicy(),
        rate_limiter=NoopRateLimiter(),
        retry_delay_seconds=0,
        bytes_get=bytes_get,
    )
    first = fetcher.fetch("https://example.edu.vn/document")
    second = fetcher.fetch("https://example.edu.vn/document")
    assert first.body == b"retrieved text"
    assert not first.from_cache
    assert second.from_cache
    assert calls == 2


def test_host_rate_limiter_waits_only_for_same_host() -> None:
    now = [10.0]
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    limiter = HostRateLimiter(
        min_interval_seconds=0.5,
        clock=lambda: now[0],
        sleeper=sleep,
    )
    limiter.wait("https://one.example/a")
    limiter.wait("https://two.example/a")
    limiter.wait("https://one.example/b")
    assert sleeps == [0.5]


def test_search_retries_transient_timeout() -> None:
    calls = 0

    def json_get(url, headers, timeout):
        nonlocal calls
        del url, headers, timeout
        calls += 1
        if calls == 1:
            raise TimeoutError("transient")
        return {"web": {"results": []}}

    provider = BraveSearchProvider(
        "fixture-key",
        json_get=json_get,
        max_attempts=2,
        retry_delay_seconds=0,
        rate_limiter=NoopRateLimiter(),
    )
    rows = provider.search(
        QuerySpec("query_001", "EXACT_CANDIDATE", '"suy luan"'),
        count=10,
    )
    assert rows == ()
    assert calls == 2
