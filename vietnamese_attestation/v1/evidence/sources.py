from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any, Mapping


SOURCE_POLICY_VERSION = "source-tier-v2"


@dataclass(frozen=True)
class SourceProfile:
    publisher: str
    organization: str
    source_type: str
    source_tier: str
    source_tier_reasons: tuple[str, ...]


def profile_source(
    canonical_url: str,
    *,
    content_kind: str,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> SourceProfile:
    host = (urllib.parse.urlsplit(canonical_url).hostname or "").casefold()
    override = (overrides or {}).get(host)
    if override is not None:
        raw_reasons = override.get(
            "source_tier_reasons", ("VERIFIED_SOURCE_OVERRIDE",)
        )
        reasons = (
            (raw_reasons,)
            if isinstance(raw_reasons, str)
            else tuple(str(item) for item in raw_reasons)
        )
        if not reasons:
            raise ValueError("source override must include an authority reason")
        return SourceProfile(
            publisher=str(override["publisher"]),
            organization=str(override["organization"]),
            source_type=str(override["source_type"]),
            source_tier=_tier(str(override["source_tier"])),
            source_tier_reasons=tuple(
                sorted(reasons)
            ),
        )
    organization = _registrable_label(host)
    if host.endswith(".gov.vn") or host in {"chinhphu.vn", "moet.gov.vn"}:
        tier = "A"
        source_type = "government"
        reasons = ("VERIFIED_GOVERNMENT_DOMAIN",)
    elif host.endswith(".edu.vn") or host.endswith(".ac.vn"):
        tier = "B"
        source_type = "academic"
        reasons = ("VERIFIED_ACADEMIC_DOMAIN",)
    elif content_kind == "pdf":
        tier = "D"
        source_type = "unverified_pdf"
        reasons = ("UNVERIFIED_PDF_HOST",)
    elif host.endswith(".org.vn") or host.endswith(".org"):
        tier = "C"
        source_type = "unverified_organization"
        reasons = ("ORGANIZATION_TLD_ONLY",)
    else:
        tier = "D"
        source_type = "unverified_web_document"
        reasons = ("UNVERIFIED_WEB_SOURCE",)
    return SourceProfile(
        publisher=host,
        organization=organization,
        source_type=source_type,
        source_tier=tier,
        source_tier_reasons=reasons,
    )


def _registrable_label(host: str) -> str:
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    if parts[-2:] in (["com", "vn"], ["edu", "vn"], ["gov", "vn"], ["org", "vn"]):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _tier(value: str) -> str:
    normalized = value.upper()
    if normalized not in {"A", "B", "C", "D", "X"}:
        raise ValueError("source tier must be A, B, C, D, or X")
    return normalized


__all__ = ["SOURCE_POLICY_VERSION", "SourceProfile", "profile_source"]
