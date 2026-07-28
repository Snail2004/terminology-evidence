from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from .query import QuerySpec
from .urls import canonicalize_url
from .rate_limit import HostRateLimiter, RateLimiter


JsonGet = Callable[[str, Mapping[str, str], float], Mapping[str, Any]]


class SearchProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "SEARCH_FAILED") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class SearchResult:
    provider_id: str
    query_id: str
    query_text: str
    rank: int
    title: str
    url: str
    canonical_url: str
    description: str


class SearchProvider(Protocol):
    provider_id: str

    def search(
        self, query: QuerySpec, *, count: int
    ) -> Sequence[SearchResult]: ...


class BraveSearchProvider:
    provider_id = "brave"

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = "https://api.search.brave.com/res/v1/web/search",
        timeout_seconds: float = 20,
        json_get: JsonGet | None = None,
        max_attempts: int = 2,
        retry_delay_seconds: float = 0.5,
        rate_limiter: RateLimiter | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Brave API key is empty")
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("?")
        self._timeout_seconds = timeout_seconds
        self._json_get = json_get or _default_json_get
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._rate_limiter = rate_limiter or HostRateLimiter()
        self._sleeper = sleeper
        self._raw_responses: dict[str, Mapping[str, Any]] = {}
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")

    def search(
        self, query: QuerySpec, *, count: int
    ) -> Sequence[SearchResult]:
        url = self._endpoint + "?" + urllib.parse.urlencode(
            {
                "q": query.query_text,
                "count": max(1, min(int(count), 20)),
                "country": "vn",
                "search_lang": "vi",
            }
        )
        payload = self._request_with_retry(url)
        self._raw_responses[query.query_id] = payload
        web = payload.get("web", {})
        raw_results = web.get("results", []) if isinstance(web, Mapping) else []
        if not isinstance(raw_results, list):
            raise SearchProviderError("Brave search result schema is invalid")
        return tuple(
            _search_result(
                provider_id=self.provider_id,
                query=query,
                rank=index + 1,
                raw=row,
            )
            for index, row in enumerate(raw_results[:count])
            if isinstance(row, Mapping) and isinstance(row.get("url"), str)
        )

    def raw_response(self, query_id: str) -> Mapping[str, Any] | None:
        return self._raw_responses.get(query_id)

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": type(self).__name__,
            "provider_id": self.provider_id,
            "endpoint": self._endpoint,
            "timeout_seconds": self._timeout_seconds,
            "max_attempts": self._max_attempts,
            "retry_delay_seconds": self._retry_delay_seconds,
            "country": "vn",
            "search_lang": "vi",
        }

    def _request_with_retry(self, url: str) -> Mapping[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            self._rate_limiter.wait(self._endpoint)
            try:
                return self._json_get(
                    url,
                    {
                        "Accept": "application/json",
                        "X-Subscription-Token": self._api_key,
                    },
                    self._timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= self._max_attempts or not _retryable(exc):
                    break
                self._sleeper(
                    _retry_delay(
                        exc,
                        fallback=self._retry_delay_seconds * (attempt + 1),
                    )
                )
        raise SearchProviderError(
            "Brave search request failed", code=_search_error_code(last_error)
        ) from last_error


class StaticSearchProvider:
    def __init__(
        self,
        provider_id: str,
        rows_by_query_class: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> None:
        self.provider_id = provider_id
        self._rows = {
            str(key): tuple(dict(row) for row in rows)
            for key, rows in rows_by_query_class.items()
        }
        self._raw_responses: dict[str, Mapping[str, Any]] = {}

    def search(
        self, query: QuerySpec, *, count: int
    ) -> Sequence[SearchResult]:
        raw_rows = self._rows.get(query.query_class, ())[:count]
        self._raw_responses[query.query_id] = {
            "fixture_query_class": query.query_class,
            "results": [dict(row) for row in raw_rows],
        }
        return tuple(
            _search_result(
                provider_id=self.provider_id,
                query=query,
                rank=index + 1,
                raw=row,
            )
            for index, row in enumerate(
                raw_rows
            )
        )

    def raw_response(self, query_id: str) -> Mapping[str, Any] | None:
        return self._raw_responses.get(query_id)

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": type(self).__name__,
            "provider_id": self.provider_id,
            "query_class_count": len(self._rows),
        }


def merge_search_results(
    rows: Sequence[SearchResult],
    *,
    max_unique_urls: int,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        existing = merged.get(row.canonical_url)
        if existing is None:
            merged[row.canonical_url] = {
                "canonical_url": row.canonical_url,
                "url": row.url,
                "title": row.title,
                "description": row.description,
                "provider_id": row.provider_id,
                "query_ids": [row.query_id],
                "best_rank": row.rank,
            }
        else:
            existing["query_ids"].append(row.query_id)
            existing["query_ids"] = sorted(set(existing["query_ids"]))
            existing["best_rank"] = min(existing["best_rank"], row.rank)
    return sorted(
        merged.values(),
        key=lambda item: (item["best_rank"], item["canonical_url"]),
    )[:max_unique_urls]


def _search_result(
    *,
    provider_id: str,
    query: QuerySpec,
    rank: int,
    raw: Mapping[str, Any],
) -> SearchResult:
    url = str(raw["url"]).strip()
    return SearchResult(
        provider_id=provider_id,
        query_id=query.query_id,
        query_text=query.query_text,
        rank=rank,
        title=str(raw.get("title", "")).strip(),
        url=url,
        canonical_url=canonicalize_url(url),
        description=str(raw.get("description", "")).strip(),
    )


def _default_json_get(
    url: str, headers: Mapping[str, str], timeout: float
) -> Mapping[str, Any]:
    request = urllib.request.Request(url=url, headers=dict(headers), method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise SearchProviderError("search response must be an object")
    return payload


def _retryable(error: Exception) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code == 429 or 500 <= error.code < 600
    return isinstance(error, (TimeoutError, urllib.error.URLError))


def _search_error_code(error: Exception | None) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return f"SEARCH_HTTP_{error.code}"
    if isinstance(error, TimeoutError):
        return "SEARCH_TIMEOUT"
    if isinstance(error, urllib.error.URLError):
        return "SEARCH_URL_ERROR"
    return "SEARCH_FAILED"


def _retry_delay(error: Exception, *, fallback: float) -> float:
    if isinstance(error, urllib.error.HTTPError):
        raw = error.headers.get("Retry-After") if error.headers else None
        if raw is not None:
            try:
                return max(0.0, float(raw))
            except ValueError:
                pass
    return fallback


__all__ = [
    "BraveSearchProvider",
    "SearchProvider",
    "SearchProviderError",
    "SearchResult",
    "StaticSearchProvider",
    "merge_search_results",
]
