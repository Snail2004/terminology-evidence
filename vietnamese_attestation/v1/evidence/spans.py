from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence

from ..config import SnippetConfig


@dataclass(frozen=True)
class CandidateSnippet:
    original: str
    masked: str
    span_start: int
    span_end: int
    matched_surface: str
    occurrence_count: int


def build_candidate_snippet(
    text: str,
    surfaces: Sequence[str],
    *,
    config: SnippetConfig,
) -> CandidateSnippet | None:
    normalized_text = unicodedata.normalize("NFC", text)
    match = _first_surface_match(normalized_text, surfaces)
    if match is None:
        return None
    start, end = match.span()
    words = list(re.finditer(r"\S+", normalized_text))
    if not words:
        return None
    containing = [
        index
        for index, word in enumerate(words)
        if word.start() <= start < word.end()
        or word.start() < end <= word.end()
        or (start <= word.start() and word.end() <= end)
    ]
    if not containing:
        return None
    first_word = min(containing)
    last_word = max(containing)
    snippet_first = max(0, first_word - config.words_before)
    snippet_last = min(len(words) - 1, last_word + config.words_after)
    if snippet_last - snippet_first + 1 > config.max_words:
        excess = snippet_last - snippet_first + 1 - config.max_words
        trim_left = excess // 2
        trim_right = excess - trim_left
        snippet_first += trim_left
        snippet_last -= trim_right
    snippet_start = words[snippet_first].start()
    snippet_end = words[snippet_last].end()
    original = normalized_text[snippet_start:snippet_end]
    if len(re.findall(r"\S+", original)) < config.min_words:
        return None
    local_start = start - snippet_start
    local_end = end - snippet_start
    matched_surface = original[local_start:local_end]
    masked = original[:local_start] + "[TERM]" + original[local_end:]
    return CandidateSnippet(
        original=original,
        masked=masked,
        span_start=local_start,
        span_end=local_end,
        matched_surface=matched_surface,
        occurrence_count=count_candidate_occurrences(
            normalized_text, surfaces
        ),
    )


def count_candidate_occurrences(text: str, surfaces: Sequence[str]) -> int:
    normalized_text = unicodedata.normalize("NFC", text)
    spans: set[tuple[int, int]] = set()
    for surface in _normalized_surfaces(surfaces):
        pattern = re.compile(
            rf"(?<!\w){re.escape(surface)}(?!\w)",
            flags=re.IGNORECASE | re.UNICODE,
        )
        spans.update(match.span() for match in pattern.finditer(normalized_text))
    return len(spans)


def _first_surface_match(
    text: str, surfaces: Sequence[str]
) -> re.Match[str] | None:
    normalized = _normalized_surfaces(surfaces)
    best: re.Match[str] | None = None
    for surface in normalized:
        pattern = re.compile(
            rf"(?<!\w){re.escape(surface)}(?!\w)",
            flags=re.IGNORECASE | re.UNICODE,
        )
        match = pattern.search(text)
        if match is not None and (
            best is None
            or match.start() < best.start()
            or (
                match.start() == best.start()
                and match.end() - match.start() > best.end() - best.start()
            )
        ):
            best = match
    return best


def _normalized_surfaces(surfaces: Sequence[str]) -> list[str]:
    return sorted(
        {
            unicodedata.normalize("NFC", surface).strip()
            for surface in surfaces
            if surface.strip()
        },
        key=lambda item: (-len(item), item.casefold()),
    )


__all__ = [
    "CandidateSnippet",
    "build_candidate_snippet",
    "count_candidate_occurrences",
]
