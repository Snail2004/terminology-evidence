from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Mapping


JsonPost = Callable[
    [str, Mapping[str, str], Mapping[str, Any], float],
    Mapping[str, Any],
]


def default_json_post(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> Mapping[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
        headers={"Content-Type": "application/json", **dict(headers)},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, Mapping):
        raise ValueError("provider response must be an object")
    return result


__all__ = ["JsonPost", "default_json_post"]
