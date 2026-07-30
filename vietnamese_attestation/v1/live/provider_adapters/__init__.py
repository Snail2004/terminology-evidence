"""Concrete provider adapters for the authority-gated E Live runtime."""

from __future__ import annotations

from typing import Any


_GEMINI_EXPORTS = {
    "GeminiOfficialAdapter",
    "GeminiTransport",
    "GeminiUnknownPhysicalOutcome",
    "UrllibGeminiTransport",
}


def __getattr__(name: str) -> Any:
    # Avoid an import cycle while the E-05 authority adapter loads the exact
    # token-accounting submodule.
    if name in _GEMINI_EXPORTS:
        from . import gemini_official

        return getattr(gemini_official, name)
    raise AttributeError(name)


__all__ = sorted(_GEMINI_EXPORTS)
