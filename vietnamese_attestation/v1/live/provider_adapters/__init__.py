"""Concrete provider adapters for the authority-gated E Live runtime."""

from .gemini_official import (
    GeminiOfficialAdapter,
    GeminiTransport,
    GeminiUnknownPhysicalOutcome,
    UrllibGeminiTransport,
    make_recorded_pricing_authority,
)

__all__ = [
    "GeminiOfficialAdapter",
    "GeminiTransport",
    "GeminiUnknownPhysicalOutcome",
    "UrllibGeminiTransport",
    "make_recorded_pricing_authority",
]
