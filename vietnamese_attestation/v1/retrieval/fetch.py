from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Protocol

from .rate_limit import HostRateLimiter, RateLimiter


@dataclass(frozen=True)
class HttpFetchResponse:
    body: bytes
    content_type: str
    http_status: int
    response_headers: tuple[tuple[str, str], ...]
    final_url: str


BytesGet = Callable[
    [str, Mapping[str, str], float, int],
    tuple[bytes, str] | HttpFetchResponse,
]
FETCH_POLICY_VERSION = "attestation-fetch-v2"
CACHE_SCHEMA_VERSION = "attestation-fetch-cache-v2"


class FetchError(RuntimeError):
    def __init__(self, message: str, *, code: str = "FETCH_FAILED") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class FetchedDocument:
    canonical_url: str
    content_type: str
    body: bytes
    content_sha256: str
    from_cache: bool
    retrieved_at: str
    http_status: int
    response_headers: tuple[tuple[str, str], ...]
    fetch_policy_version: str
    robots_status: str
    redirect_chain: tuple[str, ...]


class DocumentFetcher(Protocol):
    def fetch(self, canonical_url: str) -> FetchedDocument: ...


class RobotsPolicy(Protocol):
    def allowed(self, url: str, *, user_agent: str) -> bool: ...


class StandardRobotsPolicy:
    def __init__(self, *, timeout_seconds: float = 10) -> None:
        self._timeout_seconds = timeout_seconds
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def allowed(self, url: str, *, user_agent: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        origin = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, "", "", "")
        )
        parser = self._parsers.get(origin)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(origin + "/robots.txt")
            try:
                parser.read()
            except Exception:
                return False
            self._parsers[origin] = parser
        return parser.can_fetch(user_agent, url)

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": type(self).__name__,
            "timeout_seconds": self._timeout_seconds,
            "deny_on_retrieval_failure": True,
        }


class AllowAllRobotsPolicy:
    def allowed(self, url: str, *, user_agent: str) -> bool:
        del url, user_agent
        return True

    def identity_payload(self) -> dict[str, object]:
        return {"component": type(self).__name__, "allow_all": True}


class DiskFetchCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": type(self).__name__,
            "schema_version": CACHE_SCHEMA_VERSION,
            "root_sha256": hashlib.sha256(
                str(self.root.resolve()).casefold().encode("utf-8")
            ).hexdigest(),
        }

    def load(self, canonical_url: str) -> FetchedDocument | None:
        key = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        path = self.root / f"{key}.json"
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != CACHE_SCHEMA_VERSION:
            raise FetchError(
                "cached document schema is unsupported",
                code="CACHE_SCHEMA_MISMATCH",
            )
        body = base64.b64decode(payload["body_base64"], validate=True)
        digest = hashlib.sha256(body).hexdigest()
        if digest != payload["content_sha256"]:
            raise FetchError(
                "cached document hash mismatch", code="CACHE_HASH_MISMATCH"
            )
        if payload["canonical_url"] != canonical_url:
            raise FetchError(
                "cached document URL binding mismatch",
                code="CACHE_URL_MISMATCH",
            )
        return FetchedDocument(
            canonical_url=canonical_url,
            content_type=str(payload["content_type"]),
            body=body,
            content_sha256=digest,
            from_cache=True,
            retrieved_at=str(payload["retrieved_at"]),
            http_status=int(payload["http_status"]),
            response_headers=tuple(
                (str(key), str(value))
                for key, value in payload["response_headers"]
            ),
            fetch_policy_version=str(payload["fetch_policy_version"]),
            robots_status=str(payload["robots_status"]),
            redirect_chain=tuple(
                str(item) for item in payload["redirect_chain"]
            ),
        )

    def store(self, document: FetchedDocument) -> None:
        key = hashlib.sha256(
            document.canonical_url.encode("utf-8")
        ).hexdigest()
        path = self.root / f"{key}.json"
        tmp = self.root / f"{key}.json.tmp"
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "canonical_url": document.canonical_url,
            "content_type": document.content_type,
            "content_sha256": document.content_sha256,
            "body_base64": base64.b64encode(document.body).decode("ascii"),
            "retrieved_at": document.retrieved_at,
            "http_status": document.http_status,
            "response_headers": [list(item) for item in document.response_headers],
            "fetch_policy_version": document.fetch_policy_version,
            "robots_status": document.robots_status,
            "redirect_chain": list(document.redirect_chain),
        }
        tmp.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)


class HttpDocumentFetcher:
    def __init__(
        self,
        *,
        cache: DiskFetchCache,
        robots: RobotsPolicy | None = None,
        timeout_seconds: float = 20,
        max_response_bytes: int = 15_000_000,
        user_agent: str = "TerminologyEvidenceBot/1.0",
        rate_limiter: RateLimiter | None = None,
        max_attempts: int = 2,
        retry_delay_seconds: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
        bytes_get: BytesGet | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must not be negative")
        self._cache = cache
        self._robots = robots or StandardRobotsPolicy()
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._user_agent = user_agent
        self._rate_limiter = rate_limiter or HostRateLimiter()
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._sleeper = sleeper
        self._bytes_get = bytes_get or _default_bytes_get
        self._clock = clock or _utc_now

    def fetch(self, canonical_url: str) -> FetchedDocument:
        cached = self._cache.load(canonical_url)
        if cached is not None:
            return cached
        if not self._robots.allowed(
            canonical_url, user_agent=self._user_agent
        ):
            raise FetchError(
                "robots policy denied the URL", code="ROBOTS_BLOCKED"
            )
        response = self._fetch_with_retry(canonical_url)
        body = response.body
        content_type = response.content_type
        if not body:
            raise FetchError("document body is empty", code="EMPTY_BODY")
        digest = hashlib.sha256(body).hexdigest()
        document = FetchedDocument(
            canonical_url=canonical_url,
            content_type=content_type,
            body=body,
            content_sha256=digest,
            from_cache=False,
            retrieved_at=self._clock(),
            http_status=response.http_status,
            response_headers=response.response_headers,
            fetch_policy_version=FETCH_POLICY_VERSION,
            robots_status="ALLOWED",
            redirect_chain=tuple(
                dict.fromkeys((canonical_url, response.final_url))
            ),
        )
        self._cache.store(document)
        return document

    def _fetch_with_retry(self, canonical_url: str) -> HttpFetchResponse:
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            self._rate_limiter.wait(canonical_url)
            try:
                value = self._bytes_get(
                    canonical_url,
                    {"User-Agent": self._user_agent},
                    self._timeout_seconds,
                    self._max_response_bytes,
                )
                if isinstance(value, HttpFetchResponse):
                    return value
                body, content_type = value
                return HttpFetchResponse(
                    body=body,
                    content_type=content_type,
                    http_status=200,
                    response_headers=(("content-type", content_type),),
                    final_url=canonical_url,
                )
            except FetchError:
                raise
            except Exception as exc:
                last_error = exc
                if (
                    attempt + 1 >= self._max_attempts
                    or not _is_retryable_fetch_error(exc)
                ):
                    break
                self._sleeper(self._retry_delay_seconds * (attempt + 1))
        code = _fetch_error_code(last_error)
        raise FetchError("document fetch failed", code=code) from last_error

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": "HttpDocumentFetcher",
            "fetch_policy_version": FETCH_POLICY_VERSION,
            "timeout_seconds": self._timeout_seconds,
            "max_response_bytes": self._max_response_bytes,
            "user_agent": self._user_agent,
            "max_attempts": self._max_attempts,
            "retry_delay_seconds": self._retry_delay_seconds,
            "robots_policy": type(self._robots).__name__,
            "robots_identity": _identity(self._robots),
            "cache_identity": self._cache.identity_payload(),
        }


class StaticDocumentFetcher:
    def __init__(
        self,
        documents: Mapping[str, tuple[str, str | bytes]],
        *,
        retrieved_at: str = "2026-01-01T00:00:00Z",
    ) -> None:
        self._documents = dict(documents)
        self.calls: list[str] = []
        self._retrieved_at = retrieved_at

    def fetch(self, canonical_url: str) -> FetchedDocument:
        self.calls.append(canonical_url)
        try:
            content_type, raw = self._documents[canonical_url]
        except KeyError as exc:
            raise FetchError(
                "static document is missing", code="FIXTURE_DOCUMENT_MISSING"
            ) from exc
        body = raw if isinstance(raw, bytes) else raw.encode("utf-8")
        return FetchedDocument(
            canonical_url=canonical_url,
            content_type=content_type,
            body=body,
            content_sha256=hashlib.sha256(body).hexdigest(),
            from_cache=False,
            retrieved_at=self._retrieved_at,
            http_status=200,
            response_headers=(("content-type", content_type),),
            fetch_policy_version="static-fetch-v1",
            robots_status="FIXTURE_ALLOWED",
            redirect_chain=(canonical_url,),
        )

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": "StaticDocumentFetcher",
            "fetch_policy_version": "static-fetch-v1",
            "document_count": len(self._documents),
        }


def _default_bytes_get(
    url: str,
    headers: Mapping[str, str],
    timeout: float,
    max_bytes: int,
) -> HttpFetchResponse:
    request = urllib.request.Request(url=url, headers=dict(headers), method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise FetchError(
                "document exceeds max_response_bytes",
                code="CONTENT_TOO_LARGE",
            )
        content_type = response.headers.get_content_type()
        headers_out = tuple(
            sorted(
                (str(key).casefold(), str(value))
                for key, value in response.headers.items()
            )
        )
        status = int(getattr(response, "status", 200))
        final_url = str(response.geturl())
    return HttpFetchResponse(
        body=body,
        content_type=content_type,
        http_status=status,
        response_headers=headers_out,
        final_url=final_url,
    )


def _is_retryable_fetch_error(error: Exception) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code == 429 or 500 <= error.code < 600
    return isinstance(error, (TimeoutError, urllib.error.URLError))


def _fetch_error_code(error: Exception | None) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP_{error.code}"
    if isinstance(error, TimeoutError):
        return "FETCH_TIMEOUT"
    if isinstance(error, urllib.error.URLError):
        return "FETCH_URL_ERROR"
    return "FETCH_FAILED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _identity(component: object) -> dict[str, object]:
    method = getattr(component, "identity_payload", None)
    if callable(method):
        return dict(method())
    return {"component": type(component).__name__}


__all__ = [
    "AllowAllRobotsPolicy",
    "DiskFetchCache",
    "CACHE_SCHEMA_VERSION",
    "DocumentFetcher",
    "FetchError",
    "FetchedDocument",
    "FETCH_POLICY_VERSION",
    "HttpDocumentFetcher",
    "HttpFetchResponse",
    "RobotsPolicy",
    "StandardRobotsPolicy",
    "StaticDocumentFetcher",
]
