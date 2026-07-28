"""Deterministic pre-Judge Vietnamese language diagnostics."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


LANGUAGE_DETECTOR_VERSION = "vi-rule-detector-v1"
_VI_DIACRITICS = frozenset(
    "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợ"
    "úùủũụứừửữựýỳỷỹỵ"
)
_VI_STOPWORDS = frozenset(
    {
        "các",
        "cách",
        "cho",
        "của",
        "dữ",
        "được",
        "hệ",
        "hình",
        "học",
        "không",
        "là",
        "liệu",
        "máy",
        "mô",
        "một",
        "này",
        "những",
        "quá",
        "suy",
        "thống",
        "trình",
        "trong",
        "và",
        "với",
        # Unaccented forms retained for deterministic fixture support.
        "cac",
        "cach",
        "cho",
        "cua",
        "du",
        "duoc",
        "he",
        "hinh",
        "hoc",
        "khong",
        "la",
        "lieu",
        "may",
        "mo",
        "mot",
        "nay",
        "nhung",
        "qua",
        "suy",
        "thong",
        "trinh",
        "trong",
        "va",
        "voi",
    }
)
_EN_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "data",
        "for",
        "from",
        "in",
        "is",
        "model",
        "of",
        "the",
        "this",
        "to",
        "with",
    }
)


@dataclass(frozen=True)
class LanguageAssessment:
    label: str
    confidence: float
    detector_version: str
    reason_codes: tuple[str, ...]


def detect_vietnamese(text: str) -> LanguageAssessment:
    normalized = unicodedata.normalize("NFC", text).casefold()
    tokens = re.findall(r"[^\W\d_]+", normalized, flags=re.UNICODE)
    if not tokens:
        return LanguageAssessment(
            label="UNCERTAIN",
            confidence=0.0,
            detector_version=LANGUAGE_DETECTOR_VERSION,
            reason_codes=("NO_LEXICAL_TOKENS",),
        )
    vi_hits = sum(token in _VI_STOPWORDS for token in tokens)
    en_hits = sum(token in _EN_STOPWORDS for token in tokens)
    diacritic_hits = sum(
        any(character in _VI_DIACRITICS for character in token)
        for token in tokens
    )
    vi_signal = vi_hits + (2 * diacritic_hits)
    if en_hits >= max(4, vi_signal * 2):
        label = "NON_VIETNAMESE"
        confidence = min(1.0, en_hits / max(5, len(tokens) * 0.25))
        reasons = ("EN_SIGNAL_DOMINATES",)
    elif vi_signal >= 3 and en_hits >= 3:
        label = "MIXED_VI_EN"
        confidence = min(1.0, (vi_signal + en_hits) / max(8, len(tokens)))
        reasons = ("VI_SIGNAL_PRESENT", "EN_SIGNAL_PRESENT")
    elif vi_signal >= 3:
        label = "VIETNAMESE"
        confidence = min(1.0, vi_signal / max(5, len(tokens) * 0.25))
        reasons = ("VI_SIGNAL_PRESENT",)
    elif en_hits >= 3 and vi_signal == 0:
        label = "NON_VIETNAMESE"
        confidence = min(1.0, en_hits / max(5, len(tokens) * 0.25))
        reasons = ("EN_SIGNAL_WITHOUT_VI",)
    else:
        label = "UNCERTAIN"
        confidence = min(0.49, vi_signal / max(1, len(tokens)))
        reasons = ("INSUFFICIENT_LANGUAGE_SIGNAL",)
    return LanguageAssessment(
        label=label,
        confidence=round(float(confidence), 6),
        detector_version=LANGUAGE_DETECTOR_VERSION,
        reason_codes=reasons,
    )


def is_vietnamese_eligible(assessment: LanguageAssessment) -> bool:
    return assessment.label in {"VIETNAMESE", "MIXED_VI_EN"}


__all__ = [
    "LANGUAGE_DETECTOR_VERSION",
    "LanguageAssessment",
    "detect_vietnamese",
    "is_vietnamese_eligible",
]
