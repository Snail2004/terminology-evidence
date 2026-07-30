from __future__ import annotations

import io
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from .fetch import FetchedDocument


EXTRACTOR_VERSION = "vietnamese_attestation_extractor_v2"


class ExtractionError(RuntimeError):
    def __init__(self, message: str, *, code: str = "EXTRACTION_FAILED") -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ExtractedDocument:
    canonical_url: str
    content_sha256: str
    title: str
    text: str
    content_kind: str
    extraction_method: str
    author: str
    published_at: str
    section_titles: tuple[str, ...]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self._excluded_depth = 0
        self._main_depth = 0
        self._title_depth = 0
        self.parts: list[str] = []
        self.main_parts: list[str] = []
        self.title_parts: list[str] = []
        self.section_titles: list[str] = []
        self._heading_depth = 0
        self.author = ""
        self.published_at = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript", "svg"}:
            self._hidden_depth += 1
        if lowered in {"nav", "header", "footer", "aside", "form"}:
            self._excluded_depth += 1
        if lowered in {"main", "article"}:
            self._main_depth += 1
        if lowered == "title":
            self._title_depth += 1
        if lowered in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_depth += 1
        attributes = {key.casefold(): value or "" for key, value in attrs}
        if lowered == "meta":
            name = (
                attributes.get("name")
                or attributes.get("property")
                or ""
            ).casefold()
            content = attributes.get("content", "").strip()
            if name in {"author", "article:author"} and content:
                self.author = content
            if name in {
                "article:published_time",
                "date",
                "datepublished",
            } and content:
                self.published_at = content

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "noscript", "svg"} and self._hidden_depth:
            self._hidden_depth -= 1
        if lowered in {"nav", "header", "footer", "aside", "form"} and self._excluded_depth:
            self._excluded_depth -= 1
        if lowered in {"main", "article"} and self._main_depth:
            self._main_depth -= 1
        if lowered == "title" and self._title_depth:
            self._title_depth -= 1
        if lowered in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading_depth:
            self._heading_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._hidden_depth or self._excluded_depth:
            return
        if self._title_depth:
            self.title_parts.append(data)
        self.parts.append(data)
        if self._main_depth:
            self.main_parts.append(data)
        if self._heading_depth and data.strip():
            self.section_titles.append(data)


def extract_document(document: FetchedDocument) -> ExtractedDocument:
    content_type = document.content_type.split(";", 1)[0].strip().casefold()
    if content_type in {"text/html", "application/xhtml+xml"}:
        return _extract_html(document)
    if content_type == "application/pdf":
        return _extract_pdf(document)
    if content_type.startswith("text/") or content_type in {
        "application/json",
        "application/xml",
    }:
        text = _normalize_text(document.body.decode("utf-8", errors="replace"))
        if not text:
            raise ExtractionError(
                "text extraction produced an empty document",
                code="EMPTY_EXTRACTED_TEXT",
            )
        return ExtractedDocument(
            canonical_url=document.canonical_url,
            content_sha256=document.content_sha256,
            title="",
            text=text,
            content_kind="text",
            extraction_method="PLAIN_TEXT",
            author="",
            published_at="",
            section_titles=(),
        )
    raise ExtractionError(
        f"unsupported content type: {content_type}",
        code="UNSUPPORTED_CONTENT_TYPE",
    )


def _extract_html(document: FetchedDocument) -> ExtractedDocument:
    parser = _VisibleTextParser()
    parser.feed(document.body.decode("utf-8", errors="replace"))
    main_text = _normalize_text("\n".join(parser.main_parts))
    fallback_text = _normalize_text("\n".join(parser.parts))
    text = main_text or fallback_text
    if not text:
        raise ExtractionError(
            "HTML extraction produced an empty document",
            code="EMPTY_HTML_CONTENT",
        )
    return ExtractedDocument(
        canonical_url=document.canonical_url,
        content_sha256=document.content_sha256,
        title=_normalize_text(" ".join(parser.title_parts)),
        text=text,
        content_kind="html",
        extraction_method=(
            "MAIN_CONTENT_EXTRACTED"
            if main_text
            else "FALLBACK_VISIBLE_TEXT"
        ),
        author=_normalize_text(parser.author),
        published_at=_normalize_text(parser.published_at),
        section_titles=tuple(
            dict.fromkeys(
                _normalize_text(value)
                for value in parser.section_titles
                if _normalize_text(value)
            )
        ),
    )


def _extract_pdf(document: FetchedDocument) -> ExtractedDocument:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ExtractionError(
            "pypdf is required for text PDF extraction",
            code="PDF_EXTRACTOR_UNAVAILABLE",
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(document.body))
        text = _normalize_text(
            " ".join((page.extract_text() or "") for page in reader.pages)
        )
    except Exception as exc:
        raise ExtractionError(
            "PDF extraction failed", code="PDF_EXTRACTION_FAILED"
        ) from exc
    if not text:
        raise ExtractionError(
            "PDF has no extractable text",
            code="UNSUPPORTED_SCANNED_PDF",
        )
    title = ""
    if reader.metadata is not None:
        title = _normalize_text(str(reader.metadata.title or ""))
    return ExtractedDocument(
        canonical_url=document.canonical_url,
        content_sha256=document.content_sha256,
        title=title,
        text=text,
        content_kind="pdf",
        extraction_method="PDF_TEXT_EXTRACTED",
        author=(
            _normalize_text(str(reader.metadata.author or ""))
            if reader.metadata is not None
            else ""
        ),
        published_at="",
        section_titles=(),
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


__all__ = [
    "EXTRACTOR_VERSION",
    "ExtractedDocument",
    "ExtractionError",
    "extract_document",
]
