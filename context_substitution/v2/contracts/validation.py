from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
ContractPath = tuple[str, ...]


class ContractValidationError(ValueError):
    """Raised when an internal Context Substitution contract is invalid."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


@dataclass(frozen=True)
class CanonicalPolicy:
    set_like_paths: frozenset[ContractPath]
    semantic_sequence_paths: frozenset[ContractPath]

    def __post_init__(self) -> None:
        overlap = self.set_like_paths & self.semantic_sequence_paths
        if overlap:
            rendered = ", ".join(sorted(_format_policy_path(path) for path in overlap))
            raise ValueError(f"Ordering paths are classified twice: {rendered}")
        for path in self.set_like_paths | self.semantic_sequence_paths:
            if not path or any(not isinstance(part, str) or not part for part in path):
                raise ValueError(f"Invalid ordering path: {path!r}")

    def list_kind(self, path: ContractPath) -> str:
        in_set = path in self.set_like_paths
        in_sequence = path in self.semantic_sequence_paths
        if in_set == in_sequence:
            raise ContractValidationError(
                "ordering_policy_unclassified" if not in_set else "ordering_policy_ambiguous",
                _format_policy_path(path),
                "every list path must have exactly one declared ordering class",
            )
        return "set" if in_set else "sequence"


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: JSONValue, *, policy: CanonicalPolicy) -> str:
    return _json_from_normalized(canonicalize(value, policy=policy))


def canonical_sha256(value: JSONValue, *, policy: CanonicalPolicy) -> str:
    return hashlib.sha256(canonical_json(value, policy=policy).encode("utf-8")).hexdigest()


def canonicalize(value: JSONValue, *, policy: CanonicalPolicy) -> JSONValue:
    return _canonicalize(value, policy=policy, policy_path=(), display_path="$")


def seal_payload(
    payload: Mapping[str, Any],
    *,
    policy: CanonicalPolicy,
    hash_path: ContractPath,
) -> dict[str, Any]:
    if not hash_path:
        raise ValueError("hash_path must not be empty")
    sealed = copy.deepcopy(dict(payload))
    _delete_nested_field(sealed, hash_path)
    _set_nested_field(sealed, hash_path, canonical_sha256(sealed, policy=policy))
    return sealed


def verify_payload_hash(
    payload: Mapping[str, Any],
    *,
    policy: CanonicalPolicy,
    hash_path: ContractPath,
) -> bool:
    recorded = _get_nested_field(payload, hash_path)
    if not isinstance(recorded, str) or _SHA256_RE.fullmatch(recorded) is None:
        return False
    unhashed = copy.deepcopy(dict(payload))
    _delete_nested_field(unhashed, hash_path)
    return canonical_sha256(unhashed, policy=policy) == recorded


def require_mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractValidationError("type", path, "expected an object")
    return value


def require_list(value: Any, *, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractValidationError("type", path, "expected an array")
    return value


def require_exact_keys(
    value: Mapping[str, Any],
    *,
    required: Iterable[str],
    optional: Iterable[str] = (),
    path: str,
) -> None:
    if any(not isinstance(key, str) for key in value):
        raise ContractValidationError("non_string_key", path, "JSON object keys must be strings")
    required_keys = frozenset(required)
    allowed = required_keys | frozenset(optional)
    actual = frozenset(value.keys())
    missing = sorted(required_keys - actual)
    unknown = sorted(actual - allowed)
    if missing:
        raise ContractValidationError(
            "missing_keys", path, f"missing required keys: {', '.join(missing)}"
        )
    if unknown:
        raise ContractValidationError(
            "unknown_keys", path, f"unknown keys: {', '.join(unknown)}"
        )


def require_string(
    value: Any,
    *,
    path: str,
    allow_empty: bool = False,
    maximum: int | None = None,
) -> str:
    if not isinstance(value, str):
        raise ContractValidationError("type", path, "expected a string")
    normalized = unicodedata.normalize("NFC", value)
    if not allow_empty and not normalized.strip():
        raise ContractValidationError("empty_string", path, "string must not be empty")
    if maximum is not None and len(normalized) > maximum:
        raise ContractValidationError(
            "string_too_long", path, f"string exceeds {maximum} characters"
        )
    return normalized


def require_nullable_string(
    value: Any,
    *,
    path: str,
    allow_empty: bool = False,
    maximum: int | None = None,
) -> str | None:
    if value is None:
        return None
    return require_string(value, path=path, allow_empty=allow_empty, maximum=maximum)


def require_enum(value: Any, allowed: Iterable[str], *, path: str) -> str:
    result = require_string(value, path=path)
    allowed_values = frozenset(allowed)
    if result not in allowed_values:
        raise ContractValidationError(
            "enum", path, f"expected one of: {', '.join(sorted(allowed_values))}"
        )
    return result


def require_int(value: Any, *, path: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractValidationError("type", path, "expected an integer")
    if minimum is not None and value < minimum:
        raise ContractValidationError("range", path, f"must be >= {minimum}")
    return value


def require_number(
    value: Any, *, path: str, minimum: float | None = None
) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractValidationError("type", path, "expected a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractValidationError("non_finite", path, "number must be finite")
    if minimum is not None and value < minimum:
        raise ContractValidationError("range", path, f"must be >= {minimum}")
    return value


def require_sha256(value: Any, *, path: str) -> str:
    result = require_string(value, path=path)
    if _SHA256_RE.fullmatch(result) is None:
        raise ContractValidationError(
            "sha256", path, "expected a lowercase 64-character SHA-256"
        )
    return result


def require_unique(values: Sequence[str], *, path: str) -> None:
    if len(values) != len(set(values)):
        raise ContractValidationError("duplicate", path, "values must be unique")


def _canonicalize(
    value: Any,
    *,
    policy: CanonicalPolicy,
    policy_path: ContractPath,
    display_path: str,
) -> JSONValue:
    if value is None or isinstance(value, (bool, int, str)):
        return unicodedata.normalize("NFC", value) if isinstance(value, str) else value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractValidationError(
                "non_finite", display_path, "JSON numbers must be finite"
            )
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, JSONValue] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ContractValidationError(
                    "non_string_key", display_path, "JSON object keys must be strings"
                )
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ContractValidationError(
                    "duplicate_key_after_normalization",
                    display_path,
                    f"duplicate normalized key: {normalized_key}",
                )
            normalized[normalized_key] = _canonicalize(
                child,
                policy=policy,
                policy_path=policy_path + (normalized_key,),
                display_path=f"{display_path}.{normalized_key}",
            )
        return normalized
    if isinstance(value, (list, tuple)):
        kind = policy.list_kind(policy_path)
        normalized_items = [
            _canonicalize(
                child,
                policy=policy,
                policy_path=policy_path + ("*",),
                display_path=f"{display_path}[{index}]",
            )
            for index, child in enumerate(value)
        ]
        if kind == "sequence":
            return normalized_items
        keyed = [(_json_from_normalized(item), item) for item in normalized_items]
        keyed.sort(key=lambda item: item[0])
        if any(keyed[index - 1][0] == keyed[index][0] for index in range(1, len(keyed))):
            raise ContractValidationError(
                "duplicate_set_item",
                display_path,
                "set-like arrays must not contain canonical duplicates",
            )
        return [item for _, item in keyed]
    raise ContractValidationError(
        "unsupported_json_type",
        display_path,
        f"unsupported value type: {type(value).__name__}",
    )


def _json_from_normalized(value: JSONValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _format_policy_path(path: ContractPath) -> str:
    rendered = "$"
    for part in path:
        rendered += "[*]" if part == "*" else f".{part}"
    return rendered


def _get_nested_field(value: Mapping[str, Any], path: ContractPath) -> Any:
    current: Any = value
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _delete_nested_field(value: dict[str, Any], path: ContractPath) -> None:
    current: Any = value
    for part in path[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(path[-1], None)


def _set_nested_field(value: dict[str, Any], path: ContractPath, field_value: Any) -> None:
    current: Any = value
    for part in path[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise ContractValidationError(
                "hash_path", _format_policy_path(path), "hash parent must already exist"
            )
        current = current[part]
    if not isinstance(current, dict):
        raise ContractValidationError(
            "hash_path", _format_policy_path(path), "hash parent must be an object"
        )
    current[path[-1]] = field_value
