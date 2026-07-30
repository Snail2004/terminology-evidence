from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .common import canonical_json_bytes, sha256_bytes


MATCH_STATUSES = {
    "GLOSSARY_EXACT",
    "GLOSSARY_QUALIFIED",
    "GLOSSARY_VARIANT",
    "GLOSSARY_MISSING",
    "AMBIGUOUS_MULTI_SENSE",
}


@dataclass(frozen=True)
class GlossaryEntry:
    english: str
    vietnamese: str
    discussion: str
    line_number: int
    qualifier: str | None

    @property
    def base_english(self) -> str:
        if not self.qualifier:
            return self.english
        return self.english[: self.english.rfind("(")].strip()

    @property
    def entry_sha256(self) -> str:
        return sha256_bytes(
            canonical_json_bytes(
                {
                    "discussion": self.discussion,
                    "english": self.english,
                    "line_number": self.line_number,
                    "qualifier": self.qualifier,
                    "vietnamese": self.vietnamese,
                }
            )
        )


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("–", "-").replace("—", "-")
    return re.sub(r"[^0-9a-z]+", " ", normalized).strip()


def _singularize(value: str) -> str:
    words = value.split()
    if not words:
        return value
    last = words[-1]
    if len(last) > 4 and last.endswith("ies"):
        words[-1] = last[:-3] + "y"
    elif len(last) > 4 and last.endswith("s") and not last.endswith("ss"):
        words[-1] = last[:-1]
    return " ".join(words)


def variant_keys(value: str) -> set[str]:
    normalized = normalize_text(value)
    keys = {normalized, _singularize(normalized)}
    keys.add(normalized.replace(" ", ""))
    keys.add(_singularize(normalized).replace(" ", ""))
    return {key for key in keys if key}


def parse_glossary(path: Path) -> list[GlossaryEntry]:
    entries: list[GlossaryEntry] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        body = line[1:-1] if line.endswith("|") else line[1:]
        cells = [cell.strip() for cell in body.split("|")]
        if len(cells) < 2:
            continue
        english, vietnamese = cells[:2]
        discussion = cells[2] if len(cells) >= 3 else ""
        if english.casefold() == "english" or set(english) <= {"-", ":"}:
            continue
        if not english or not vietnamese:
            continue
        qualifier_match = re.search(r"\(([^()]*)\)\s*$", english)
        entries.append(
            GlossaryEntry(
                english=english,
                vietnamese=vietnamese,
                discussion=discussion,
                line_number=line_number,
                qualifier=qualifier_match.group(1).strip() if qualifier_match else None,
            )
        )
    if not entries:
        raise ValueError(f"no glossary entries parsed from {path}")
    return entries


def _result(status: str, entries: Iterable[GlossaryEntry]) -> dict[str, object]:
    matched = sorted(entries, key=lambda item: (item.line_number, item.english, item.vietnamese))
    if status not in MATCH_STATUSES:
        raise ValueError(status)
    primary = matched[0] if len(matched) == 1 else None
    return {
        "glossary_match_status": status,
        "matched_entry_count": len(matched),
        "matched_entries": [
            {
                "discussion": item.discussion,
                "english": item.english,
                "entry_sha256": item.entry_sha256,
                "line_number": item.line_number,
                "qualifier": item.qualifier,
                "vietnamese": item.vietnamese,
            }
            for item in matched
        ],
        "glossary_source_entry": primary.english if primary else None,
        "glossary_candidate_vi": primary.vietnamese if primary else None,
        "glossary_qualifier": primary.qualifier if primary else None,
        "glossary_entry_sha256": primary.entry_sha256 if primary else None,
    }


def match_glossary(source_term: str, entries: list[GlossaryEntry]) -> dict[str, object]:
    normalized = normalize_text(source_term)
    exact = [entry for entry in entries if normalize_text(entry.english) == normalized]
    if len(exact) == 1:
        return _result("GLOSSARY_EXACT", exact)
    if len(exact) > 1:
        return _result("AMBIGUOUS_MULTI_SENSE", exact)

    qualified = [
        entry
        for entry in entries
        if entry.qualifier and normalize_text(entry.base_english) == normalized
    ]
    if len(qualified) == 1:
        return _result("GLOSSARY_QUALIFIED", qualified)
    if len(qualified) > 1:
        return _result("AMBIGUOUS_MULTI_SENSE", qualified)

    source_keys = variant_keys(source_term)
    variants = [
        entry
        for entry in entries
        if source_keys.intersection(variant_keys(entry.base_english))
    ]
    if len(variants) == 1:
        return _result("GLOSSARY_VARIANT", variants)
    if len(variants) > 1:
        return _result("AMBIGUOUS_MULTI_SENSE", variants)
    return _result("GLOSSARY_MISSING", [])
