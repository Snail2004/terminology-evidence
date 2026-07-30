"""Exact Main source-governance projection and pre-network path admission."""

from __future__ import annotations

import fnmatch
import hashlib
import io
import re
import unicodedata
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from ...strict_json import canonical_relative_ref, reject_link, strict_json_loads
from ..common import LiveSchemaError, verify_seal
from ..registry import validate_registry


SOURCE_GOVERNANCE_PACKAGE_SHA256 = (
    "fc6a64e59690c61e5184b2aacc03900929c9ddbbca7a95ff11de87c060074db6"
)
PROJECTION_CONTRACT_SELF_SHA256 = (
    "73fcb8575722d5dc30f3d9f98a2b53ae7d8cc5821741188cf93c02b946c7dff7"
)
PROJECTION_CONTRACT_PHYSICAL_SHA256 = (
    "ba0d8cbc71f5e3e95aa9d9624c093cc7fa357735fb710c6d5d70072d0544531c"
)
RUNTIME_REGISTRY_SELF_SHA256 = (
    "75ed11c83f458b2330051d1eedf935e532afa3eec4a77aeeae28a43e06e3a03a"
)
RUNTIME_REGISTRY_PHYSICAL_SHA256 = (
    "effe1ba49492a4df55ee48afcd1bd9bd2e1bd3772adada15ebd2302044ac841a"
)
PROJECTION_ANCHOR_SELF_SHA256 = (
    "2d190bbed4fc68f4f0799fed4b4c158610f179b6d0042e6972416e5646d1d37b"
)
PROJECTION_ANCHOR_PHYSICAL_SHA256 = (
    "ffbc2f48bec8a9e449167440f77761f626de6f3ada09ae96cc0054ea7b4917f9"
)
SOURCE_PROFILE_SELF_SHA256 = (
    "ed6922918429416eca1a799802cb7866bec2f88a907ad25de20c9ca0cbaa6141"
)
SOURCE_PROFILE_PHYSICAL_SHA256 = (
    "473e42f166e6393f4e3e7903d5a5469a8d2ea37a2cf466da87a30964f2555127"
)
RETRIEVAL_PROFILE_SELF_SHA256 = (
    "0ed727c713bb8e16dbbc70e74494956e28c9bd9b9cc5b37b8c0602eeb5babba0"
)
RETRIEVAL_PROFILE_PHYSICAL_SHA256 = (
    "1e65c7a64bb87b742dbb00eb45d959d01e3f40c3ee24c7788d6cbc16b9caac57"
)
PROJECTION_BASE_COMMIT = "0888bfd180fcd00b43848977a0576160ad471400"
PROJECTION_BASE_TREE = "345d1f837767f26d9154d4d287c3507c66aaa842"

_INVALID_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_MEMBERS = frozenset(
    {
        "CHECKSUMS.sha256",
        "controlled_vietnamese_source_registry_d0_canary_v1.json",
        "main_e_retrieval_policy_acceptance_profile_v1.json",
        "main_runtime_registry_projection_acceptance_anchor_v1.json",
        "main_runtime_registry_projection_contract_v1.json",
        "main_vi_source_registry_acceptance_profile_v1.json",
        "manifest.json",
        "verification.json",
    }
)


@dataclass(frozen=True)
class RuntimeRegistryProjection:
    package_path: Path
    registry: Mapping[str, Any]
    contract: Mapping[str, Any]
    anchor: Mapping[str, Any]
    allowed_schemes: frozenset[str]
    path_patterns: Mapping[str, tuple[str, ...]]


def load_runtime_registry_projection(
    package_path: str | Path,
) -> RuntimeRegistryProjection:
    """Load only Main's exact reviewed runtime-registry projection ZIP."""

    package_file, package_raw = _read_regular(package_path)
    if hashlib.sha256(package_raw).hexdigest() != SOURCE_GOVERNANCE_PACKAGE_SHA256:
        raise LiveSchemaError("source-governance package physical SHA-256 mismatch")
    members = _zip_members(package_raw)

    registry = _pinned_object(
        members,
        "controlled_vietnamese_source_registry_d0_canary_v1.json",
        RUNTIME_REGISTRY_PHYSICAL_SHA256,
        RUNTIME_REGISTRY_SELF_SHA256,
    )
    contract = _pinned_object(
        members,
        "main_runtime_registry_projection_contract_v1.json",
        PROJECTION_CONTRACT_PHYSICAL_SHA256,
        PROJECTION_CONTRACT_SELF_SHA256,
    )
    anchor = _pinned_object(
        members,
        "main_runtime_registry_projection_acceptance_anchor_v1.json",
        PROJECTION_ANCHOR_PHYSICAL_SHA256,
        PROJECTION_ANCHOR_SELF_SHA256,
    )
    source_profile = _pinned_object(
        members,
        "main_vi_source_registry_acceptance_profile_v1.json",
        SOURCE_PROFILE_PHYSICAL_SHA256,
        SOURCE_PROFILE_SELF_SHA256,
    )
    retrieval_profile = _pinned_object(
        members,
        "main_e_retrieval_policy_acceptance_profile_v1.json",
        RETRIEVAL_PROFILE_PHYSICAL_SHA256,
        RETRIEVAL_PROFILE_SELF_SHA256,
    )
    registry = validate_registry(registry)
    path_patterns = _path_bindings(contract, anchor, registry)
    if source_profile.get("integrity", {}).get("self_sha256") != SOURCE_PROFILE_SELF_SHA256:
        raise LiveSchemaError("source profile binding mismatch")
    if retrieval_profile.get("allowed_schemes") != ["https"]:
        raise LiveSchemaError("retrieval profile allowed schemes mismatch")
    return RuntimeRegistryProjection(
        package_path=package_file,
        registry=registry,
        contract=contract,
        anchor=anchor,
        allowed_schemes=frozenset(retrieval_profile["allowed_schemes"]),
        path_patterns=path_patterns,
    )


def admit_url_before_network(
    projection: RuntimeRegistryProjection,
    registry: Mapping[str, Any],
    url: str,
) -> dict[str, Any]:
    """Resolve one reviewed source and path before a fetch may start."""

    checked = validate_registry(registry)
    if checked["integrity"]["self_sha256"] != RUNTIME_REGISTRY_SELF_SHA256:
        raise LiveSchemaError("runtime registry does not match source-governance projection")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in projection.allowed_schemes:
        raise LiveSchemaError("source URL scheme is outside reviewed retrieval policy")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise LiveSchemaError("source URL contains forbidden authority or fragment fields")
    try:
        port = parsed.port
    except ValueError as exc:
        raise LiveSchemaError("source URL port is invalid") from exc
    if port not in {None, 443}:
        raise LiveSchemaError("source URL port is outside reviewed retrieval policy")
    host = (parsed.hostname or "").casefold().strip(".")
    path = _canonical_url_path(parsed.path)
    matches = [
        record
        for record in checked["records"]
        if record["allowed"]
        and _host_matches(record["host_pattern"], host)
        and any(
            fnmatch.fnmatchcase(path, pattern)
            for pattern in projection.path_patterns.get(record["source_id"], ())
        )
    ]
    if not matches:
        raise LiveSchemaError("source URL is outside reviewed host/path projection")
    if len(matches) != 1:
        raise LiveSchemaError("source URL has ambiguous reviewed source projection")
    return {
        "source_id": matches[0]["source_id"],
        "host": host,
        "path": path,
        "contract_self_sha256": PROJECTION_CONTRACT_SELF_SHA256,
        "anchor_self_sha256": PROJECTION_ANCHOR_SELF_SHA256,
        "registry_self_sha256": RUNTIME_REGISTRY_SELF_SHA256,
    }


def fetch_after_path_admission(
    projection: RuntimeRegistryProjection,
    registry: Mapping[str, Any],
    fetch: Callable[..., Any],
    url: str,
    *,
    retry_index: int,
) -> tuple[dict[str, Any], Any]:
    """Guard the exact URL before invoking the physical fetch boundary."""

    admission = admit_url_before_network(projection, registry, url)
    return admission, fetch(url, retry_index=retry_index)


def _path_bindings(
    contract: Mapping[str, Any],
    anchor: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> dict[str, tuple[str, ...]]:
    if (
        contract.get("schema_id") != "MainRuntimeRegistryProjectionContractV1"
        or contract.get("status") != "ACCEPTED_FOR_ZERO_PROVIDER_CANARY_PREPARATION"
        or any(
            contract.get(field) is not False
            for field in (
                "corpus_acquisition_authorized",
                "network_calls_authorized",
                "provider_calls_authorized",
                "run_authorized",
            )
        )
        or contract.get("final_glossary_decision") is not None
    ):
        raise LiveSchemaError("source-governance projection contract mismatch")
    expected_bindings = {
        "e_commit": PROJECTION_BASE_COMMIT,
        "e_tree": PROJECTION_BASE_TREE,
        "retrieval_profile_physical_sha256": RETRIEVAL_PROFILE_PHYSICAL_SHA256,
        "retrieval_profile_self_sha256": RETRIEVAL_PROFILE_SELF_SHA256,
        "source_profile_physical_sha256": SOURCE_PROFILE_PHYSICAL_SHA256,
        "source_profile_self_sha256": SOURCE_PROFILE_SELF_SHA256,
    }
    if any(contract.get("bindings", {}).get(key) != value for key, value in expected_bindings.items()):
        raise LiveSchemaError("source-governance projection binding mismatch")
    if contract.get("path_admission") != {
        "enforcement_owner": "E_LIVE_ACQUISITION_ADAPTER",
        "failure_mode": "REJECT_BEFORE_NETWORK",
        "mode": "EXACT_GLOB_PATTERNS_FROM_REVIEWED_SOURCE_REGISTRY",
        "required": True,
    }:
        raise LiveSchemaError("source-governance path-admission contract mismatch")

    expected_anchor_target = {
        "contract_physical_sha256": PROJECTION_CONTRACT_PHYSICAL_SHA256,
        "contract_self_sha256": PROJECTION_CONTRACT_SELF_SHA256,
        "e_commit": PROJECTION_BASE_COMMIT,
        "e_tree": PROJECTION_BASE_TREE,
        "runtime_registry_physical_sha256": RUNTIME_REGISTRY_PHYSICAL_SHA256,
        "runtime_registry_self_sha256": RUNTIME_REGISTRY_SELF_SHA256,
        "source_profile_physical_sha256": SOURCE_PROFILE_PHYSICAL_SHA256,
        "source_profile_self_sha256": SOURCE_PROFILE_SELF_SHA256,
    }
    if (
        anchor.get("schema_id") != "MainRuntimeRegistryProjectionAcceptanceAnchorV1"
        or anchor.get("status") != "ACCEPTED_FOR_ZERO_PROVIDER_CANARY_PREPARATION"
        or anchor.get("target") != expected_anchor_target
        or set(anchor.get("authority_boundary", {}).values()) != {False}
    ):
        raise LiveSchemaError("source-governance projection anchor mismatch")

    records = {row["source_id"]: row for row in registry["records"]}
    patterns_by_source: dict[str, tuple[str, ...]] = {}
    for source in contract.get("sources", []):
        source_id = source.get("source_id")
        if source_id not in records or source.get("runtime_record") != records[source_id]:
            raise LiveSchemaError("source-governance runtime record mismatch")
        profile = source.get("source_profile", {})
        if profile.get("domain", "").casefold() != records[source_id]["host_pattern"]:
            raise LiveSchemaError("source-governance source domain mismatch")
        raw_patterns = profile.get("path_patterns")
        if not isinstance(raw_patterns, list) or not raw_patterns:
            raise LiveSchemaError("source-governance path patterns are missing")
        patterns = tuple(_canonical_path_pattern(value) for value in raw_patterns)
        if len(patterns) != len(set(patterns)):
            raise LiveSchemaError("source-governance path patterns contain duplicates")
        patterns_by_source[source_id] = patterns
    if set(patterns_by_source) != set(records):
        raise LiveSchemaError("source-governance path inventory mismatch")
    return patterns_by_source


def _canonical_path_pattern(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or "\\" in value
        or any(char in value for char in "?#[]")
        or unicodedata.normalize("NFC", value) != value
        or unicodedata.normalize("NFKC", value) != value
    ):
        raise LiveSchemaError("source-governance path pattern is not canonical")
    if any(part in {"", ".", ".."} for part in value.split("/")[1:]):
        raise LiveSchemaError("source-governance path pattern contains unsafe segments")
    return value


def _canonical_url_path(raw_path: str) -> str:
    if _INVALID_PERCENT.search(raw_path):
        raise LiveSchemaError("source URL path contains invalid percent encoding")
    try:
        path = urllib.parse.unquote_to_bytes(raw_path or "/").decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LiveSchemaError("source URL path is not UTF-8") from exc
    if (
        not path.startswith("/")
        or "\\" in path
        or any(ord(char) < 0x20 for char in path)
        or unicodedata.normalize("NFC", path) != path
        or unicodedata.normalize("NFKC", path) != path
    ):
        raise LiveSchemaError("source URL path is not canonical")
    parts = path.split("/")[1:]
    if parts and parts[-1] == "":
        parts.pop()
    if any(part in {"", ".", ".."} for part in parts):
        raise LiveSchemaError("source URL path contains unsafe segments")
    return path


def _host_matches(pattern: str, host: str) -> bool:
    pattern = pattern.casefold().strip(".")
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return host.endswith(suffix) and host != suffix[1:]
    return host == pattern


def _read_regular(path: str | Path) -> tuple[Path, bytes]:
    supplied = Path(path).absolute()
    try:
        reject_link(supplied)
        resolved = supplied.resolve(strict=True)
        reject_link(resolved)
        raw = resolved.read_bytes()
    except (OSError, ValueError) as exc:
        raise LiveSchemaError(f"cannot read source-governance package: {path}") from exc
    if not resolved.is_file():
        raise LiveSchemaError("source-governance package is not a regular file")
    return resolved, raw


def _zip_members(raw: bytes) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise LiveSchemaError("source-governance package is not a valid ZIP") from exc
    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        case_keys = [canonical_relative_ref(name)[1] for name in names]
        if (
            names != sorted(names)
            or set(names) != set(_MEMBERS)
            or len(case_keys) != len(set(case_keys))
            or any(info.is_dir() or info.flag_bits & 0x1 for info in infos)
        ):
            raise LiveSchemaError("source-governance ZIP inventory is not canonical")
        return {info.filename: archive.read(info) for info in infos}


def _pinned_object(
    members: Mapping[str, bytes],
    name: str,
    physical_sha256: str,
    self_sha256: str,
) -> dict[str, Any]:
    raw = members[name]
    if hashlib.sha256(raw).hexdigest() != physical_sha256:
        raise LiveSchemaError(f"source-governance member physical hash mismatch: {name}")
    try:
        value = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise LiveSchemaError(f"source-governance member is not strict JSON: {name}") from exc
    if (
        not isinstance(value, dict)
        or value.get("integrity", {}).get("self_sha256") != self_sha256
        or not verify_seal(value)
    ):
        raise LiveSchemaError(f"source-governance member self hash mismatch: {name}")
    return value


__all__ = [
    "PROJECTION_ANCHOR_SELF_SHA256",
    "PROJECTION_CONTRACT_SELF_SHA256",
    "RUNTIME_REGISTRY_SELF_SHA256",
    "RuntimeRegistryProjection",
    "SOURCE_GOVERNANCE_PACKAGE_SHA256",
    "admit_url_before_network",
    "fetch_after_path_admission",
    "load_runtime_registry_projection",
]
