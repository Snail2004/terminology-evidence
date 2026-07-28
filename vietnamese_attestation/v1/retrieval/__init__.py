"""Query, search, fetch, and extraction primitives."""

from .fetch import (
    AllowAllRobotsPolicy,
    DiskFetchCache,
    FetchedDocument,
    HttpDocumentFetcher,
    StaticDocumentFetcher,
)
from .query import QueryPlan, build_query_plan
from .language import LanguageAssessment, detect_vietnamese
from .rate_limit import HostRateLimiter, NoopRateLimiter
from .search import BraveSearchProvider, SearchResult, StaticSearchProvider

__all__ = [
    "AllowAllRobotsPolicy",
    "BraveSearchProvider",
    "DiskFetchCache",
    "FetchedDocument",
    "HttpDocumentFetcher",
    "HostRateLimiter",
    "LanguageAssessment",
    "NoopRateLimiter",
    "QueryPlan",
    "SearchResult",
    "StaticDocumentFetcher",
    "StaticSearchProvider",
    "build_query_plan",
    "detect_vietnamese",
]
