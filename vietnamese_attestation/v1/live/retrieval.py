"""Local-fixture discovery/fetch adapters and corpus-first evidence extraction."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..config import SnippetConfig
from ..evidence.dedup import cluster_evidence_documents
from ..evidence.spans import build_candidate_snippet
from ..retrieval.extraction import extract_document
from ..retrieval.fetch import FetchedDocument
from ..strict_json import resolve_artifact_file
from .common import LiveSchemaError, canonical_sha256, utc_now
from .registry import admit_source
from .snapshot import verify_snapshot


class UnknownPhysicalOutcome(LiveSchemaError):
    """A fixture deliberately models a request whose physical outcome is unknown."""


class FixtureTransientFetchError(LiveSchemaError):
    """A deterministic transient fixture failure eligible for bounded retry."""


class FixtureDiscovery:
    """Discovery creates leads only; it never treats a lead as evidence."""

    def __init__(self, leads: Mapping[str, Sequence[str]], *, provider_id: str = "fixture-discovery-v1") -> None:
        self.leads = {str(key): tuple(str(item) for item in value) for key, value in leads.items()}
        self.provider_id = provider_id
        self.query_count = 0

    def query(self, query_text: str, *, candidate_id: str, max_queries: int) -> list[dict[str, Any]]:
        if self.query_count >= max_queries:
            raise LiveSchemaError("discovery query budget exceeded")
        self.query_count += 1
        urls = list(self.leads.get(candidate_id, ()))
        return [{"url": url, "title": "fixture lead", "description": "lead only", "candidate_id": candidate_id, "query_text": query_text} for url in urls]


class FixtureFetcher:
    """Fetch exact bytes supplied by a local fixture map, with no HTTP fallback."""

    def __init__(self, documents: Mapping[str, Mapping[str, Any]], *, clock=utc_now) -> None:
        self.documents = {str(key): dict(value) for key, value in documents.items()}
        self.clock = clock
        self.request_count = 0
        self.attempts_by_url: dict[str, int] = {}

    def fetch(self, url: str, *, retry_index: int = 0) -> FetchedDocument:
        self.request_count += 1
        self.attempts_by_url[url] = self.attempts_by_url.get(url, 0) + 1
        if url not in self.documents:
            raise LiveSchemaError("fixture has no bytes for requested URL")
        row = self.documents[url]
        if row.get("physical_outcome") == "UNKNOWN":
            raise UnknownPhysicalOutcome("fixture physical outcome is unknown")
        failures_before_success = int(row.get("failures_before_success", 0))
        if self.attempts_by_url[url] <= failures_before_success:
            raise FixtureTransientFetchError("deterministic transient fixture failure")
        body = row.get("body")
        if not isinstance(body, (bytes, bytearray)) or not body:
            raise LiveSchemaError("fixture document body is empty or unavailable")
        body = bytes(body)
        content_type = str(row.get("content_type", "text/html"))
        final_url = str(row.get("final_url", url))
        redirect_chain = tuple(str(item) for item in row.get("redirect_chain", ()))
        return FetchedDocument(
            canonical_url=url,
            content_type=content_type,
            body=body,
            content_sha256=hashlib.sha256(body).hexdigest(),
            from_cache=False,
            retrieved_at=str(row.get("retrieved_at_utc", self.clock())),
            http_status=int(row.get("http_status", 200)),
            response_headers=tuple((str(k), str(v)) for k, v in row.get("response_headers", ())),
            fetch_policy_version="EControlledFixtureFetcherV1",
            robots_status="NOT_APPLICABLE_LOCAL_FIXTURE",
            redirect_chain=redirect_chain,
        )

    def metadata(self, url: str) -> dict[str, Any]:
        if url not in self.documents:
            raise LiveSchemaError("fixture has no metadata for requested URL")
        return dict(self.documents[url])


def extract_snapshot_evidence(
    snapshot_root: str | Path,
    *,
    candidate_id: str,
    sense_id: str,
    term_en: str,
    candidate_vi: str,
    candidate_variants: Sequence[str] = (),
    snippet_config: SnippetConfig | None = None,
) -> list[dict[str, Any]]:
    """Extract candidate snippets from frozen snapshot bytes before discovery."""
    root = Path(snapshot_root).absolute()
    manifest = verify_snapshot(root)
    config = snippet_config or SnippetConfig(words_before=35, words_after=65, min_words=8, max_words=180)
    surfaces = [candidate_vi, *candidate_variants]
    rows: list[dict[str, Any]] = []
    for document in manifest["documents"]:
        extraction_path = resolve_artifact_file(root, document["extraction_ref"])
        text = extraction_path.read_text(encoding="utf-8")
        snippet = build_candidate_snippet(text, surfaces, config=config)
        if snippet is None:
            continue
        evidence_id = "evidence_" + hashlib.sha256((candidate_id + "\0" + document["document_id"] + "\0" + str(snippet.span_start)).encode("utf-8")).hexdigest()[:32]
        rows.append(
            {
                "evidence_id": evidence_id,
                "candidate_id": candidate_id,
                "sense_id": sense_id,
                "term_en": term_en,
                "candidate_vi": candidate_vi,
                "document_id": document["document_id"],
                "document_text": text,
                "source_id": document["source_id"],
                "source_tier": document["registry_admission"]["source_tier"],
                "source_type": document["registry_admission"]["source_type"],
                "canonical_url": document["canonical_url"],
                "final_url": document["final_url"],
                "content_sha256": document["content_physical_sha256"],
                "snippet_original": snippet.original,
                "snippet_masked": snippet.masked.replace("[TERM]", "[CANDIDATE]"),
                "evidence_span": snippet.matched_surface,
                "span_start": snippet.span_start,
                "span_end": snippet.span_end,
                "occurrence_count": snippet.occurrence_count,
                "publisher": document["source_id"],
                "organization": document["source_id"],
                "document_ref": document["document_ref"],
                "snapshot_manifest_sha256": manifest["integrity"]["self_sha256"],
            }
        )
    for row in rows:
        row["evidence_sha256"] = canonical_sha256(
            {key: row[key] for key in ("evidence_id", "document_id", "snippet_original", "content_sha256")}
        )
    return rows


def extract_fetched_evidence(
    document: FetchedDocument,
    *,
    source_id: str,
    source_tier: str,
    source_type: str,
    candidate_id: str,
    sense_id: str,
    term_en: str,
    candidate_vi: str,
    candidate_variants: Sequence[str] = (),
) -> list[dict[str, Any]]:
    extracted = extract_document(document)
    snippet = build_candidate_snippet(
        extracted.text,
        [candidate_vi, *candidate_variants],
        config=SnippetConfig(words_before=35, words_after=65, min_words=8, max_words=180),
    )
    if snippet is None:
        return []
    document_id = "doc_" + hashlib.sha256((source_id + "\0" + document.canonical_url + "\0" + document.content_sha256).encode("utf-8")).hexdigest()[:32]
    evidence_id = "evidence_" + hashlib.sha256((candidate_id + "\0" + document_id + "\0" + str(snippet.span_start)).encode("utf-8")).hexdigest()[:32]
    rows = [
        {
                "evidence_id": evidence_id,
                "candidate_id": candidate_id,
                "sense_id": sense_id,
                "term_en": term_en,
                "candidate_vi": candidate_vi,
                "document_id": document_id,
                "document_text": extracted.text,
                "source_id": source_id,
                "source_tier": source_tier,
                "source_type": source_type,
                "canonical_url": document.canonical_url,
                "final_url": document.canonical_url,
                "content_sha256": document.content_sha256,
                "snippet_original": snippet.original,
                "snippet_masked": snippet.masked.replace("[TERM]", "[CANDIDATE]"),
                "evidence_span": snippet.matched_surface,
                "span_start": snippet.span_start,
                "span_end": snippet.span_end,
                "occurrence_count": snippet.occurrence_count,
                "publisher": source_id,
                "organization": source_id,
                "document_ref": "fixture-fetch://" + document_id,
                "snapshot_manifest_sha256": "0" * 64,
        }
    ]
    rows[0]["evidence_sha256"] = canonical_sha256({"evidence_id": evidence_id, "content_sha256": document.content_sha256, "snippet_original": snippet.original})
    return rows


def cluster_global_evidence(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Cluster the combined snapshot+fetch set and select one Judge row per cluster."""
    clustered = cluster_evidence_documents(rows)
    clustered.sort(key=lambda row: str(row["evidence_id"]))
    representatives: dict[str, dict[str, Any]] = {}
    tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    for row in clustered:
        cluster_id = str(row["duplicate_cluster_id"])
        current = representatives.get(cluster_id)
        row_key = (
            tier_order.get(str(row.get("source_tier", "D")), 9),
            str(row.get("canonical_url", "")),
            str(row["evidence_id"]),
        )
        if current is None:
            representatives[cluster_id] = row
            continue
        current_key = (
            tier_order.get(str(current.get("source_tier", "D")), 9),
            str(current.get("canonical_url", "")),
            str(current["evidence_id"]),
        )
        if row_key < current_key:
            representatives[cluster_id] = row
    selected = [representatives[key] for key in sorted(representatives)]
    return clustered, selected


__all__ = [
    "FixtureDiscovery",
    "FixtureFetcher",
    "FixtureTransientFetchError",
    "UnknownPhysicalOutcome",
    "cluster_global_evidence",
    "extract_fetched_evidence",
    "extract_snapshot_evidence",
]
