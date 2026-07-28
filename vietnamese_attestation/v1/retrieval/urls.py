from __future__ import annotations

import posixpath
import urllib.parse


_TRACKING_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "source",
    }
)


def canonicalize_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise ValueError("evidence URL must use HTTP or HTTPS")
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if not hostname:
        raise ValueError("evidence URL lacks a hostname")
    port = parsed.port
    if port is not None and not (
        (parsed.scheme.casefold() == "http" and port == 80)
        or (parsed.scheme.casefold() == "https" and port == 443)
    ):
        authority = f"{hostname}:{port}"
    else:
        authority = hostname
    path = urllib.parse.unquote(parsed.path or "/")
    normalized_path = posixpath.normpath(path)
    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path
    query = [
        (key, item)
        for key, item in urllib.parse.parse_qsl(
            parsed.query, keep_blank_values=True
        )
        if not key.casefold().startswith("utm_")
        and key.casefold() not in _TRACKING_KEYS
    ]
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.casefold(),
            authority,
            urllib.parse.quote(normalized_path, safe="/:@"),
            urllib.parse.urlencode(sorted(query)),
            "",
        )
    )


__all__ = ["canonicalize_url"]
