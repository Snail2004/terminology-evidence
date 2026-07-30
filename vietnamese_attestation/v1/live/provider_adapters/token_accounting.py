"""Exact Main token-accounting package loader for Gemini E-05."""

from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ...strict_json import canonical_relative_ref, reject_link, strict_json_loads
from ..common import (
    LiveSchemaError,
    require_exact_keys,
    require_sha256,
    require_string,
    seal,
    verify_seal,
)


TOKEN_ONLY_COST_UNAVAILABLE = "TOKEN_ONLY_COST_UNAVAILABLE"
MAIN_TOKEN_PACKAGE_SHA256 = (
    "2901b042edd0dd3a4ae7e3b822b7066ccd5e6e5a3c046ff0b7b3320e0b8dacda"
)
MAIN_TOKEN_PACKAGE_MANIFEST_SELF_SHA256 = (
    "74ff02f7aca5412a880724d4e0bda5ee3a5b39867502b5ca1aafcaa0fd9474bb"
)
MAIN_TOKEN_AUTHORITY_SELF_SHA256 = (
    "467eaad13fe23b08be15ee86bc1777e66faae9eb06c407f596e3c9b273155e80"
)
MAIN_TOKEN_AUTHORITY_PHYSICAL_SHA256 = (
    "b9b8186aa1bb92f1226fa187e016e9455dc055450e6299d49b50195da6a55e73"
)
MAIN_TOKEN_ANCHOR_SELF_SHA256 = (
    "1c0ba8d193ff15d4a61094855dd8e266ea63793b43ceea13433c693774eb7a0c"
)
MAIN_TOKEN_ANCHOR_PHYSICAL_SHA256 = (
    "e96a7bebd19a23c3d5e0aec0494038cca02e3787f70b5ed3c6cedd169607c805"
)
MAIN_GENERATION_CONTRACT_SELF_SHA256 = (
    "f9b1506dcc960c5eb3673c8c44c5956cd3cd5c283a53204e056cb0c115c1b873"
)
MAIN_GENERATION_CONTRACT_PHYSICAL_SHA256 = (
    "2c1e05497a4fafdd57798661469d19cb7c1805e933941f0e3c3385c7702bfc6b"
)
MAIN_TOKEN_USER_DECISION_SELF_SHA256 = (
    "083cd4713cde369cfceb8616c28e06e40953a3423f5bc8eabe397b9e63c7d97b"
)
E05_PROVIDER_PLAN_SELF_SHA256 = (
    "5320bfc4abd73c299113338c10ebd686516a130e62a4b8a6e5ebcd1115b811cf"
)
E05_PROVIDER_PLAN_PHYSICAL_SHA256 = (
    "fb70908ba9826fff4518c9e0f5c380648d610dd04dd2e1b06e266aafd911f7e3"
)

_AUTHORITY_SCHEMA_ID = "MainTokenAccountingAuthorityV1"
_ANCHOR_SCHEMA_ID = "MainTokenAccountingAcceptanceAnchorV1"
_GENERATION_SCHEMA_ID = "MainGeminiGenerationContractV1"
_PROVIDER = "gemini_official"
_MODEL = "gemini-3.5-flash"
_TOKEN_FIELDS = ["input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"]
_FIELD_MAP = {
    "input_tokens": "promptTokenCount",
    "output_tokens": "candidatesTokenCount",
    "reasoning_tokens": "thoughtsTokenCount",
    "total_tokens": "totalTokenCount",
}
_OPERATIONAL_METRICS = [
    "physical_request_count",
    "network_request_count",
    "retry_index",
    "latency_ms",
]
_SHA256_ROW = re.compile(r"([0-9a-f]{64})  (.+)")
_MEMBERS = frozenset(
    {
        "CHECKSUMS.sha256",
        "evidence/C01_D0_Cohort_Preflight_Independent_Acceptance_Receipt_V1.json",
        "evidence/E05_Authority_Lifecycle_Recorded_Adapter_Verification_Receipt_V1.json",
        "evidence/SI_Main_Profile_Alignment_Independent_Acceptance_Receipt_V1.json",
        "main_gemini_generation_contract_v1.json",
        "main_gemini_secret_readiness_v1.json",
        "main_token_accounting_acceptance_anchor_v1.json",
        "main_token_accounting_authority_v1.json",
        "main_token_accounting_user_decision_v1.json",
        "manifest.json",
        "reviewer_handoff.md",
        "source/build_main_token_accounting.py",
        "source/verify_main_token_accounting.py",
        "verification_report.json",
    }
)


@dataclass(frozen=True)
class VerifiedTokenAccountingAuthority:
    package_path: Path
    package_sha256: str
    authority: Mapping[str, Any]
    anchor: Mapping[str, Any]
    generation_contract: Mapping[str, Any]
    user_decision: Mapping[str, Any]
    manifest: Mapping[str, Any]

    @property
    def value(self) -> Mapping[str, Any]:
        """Compatibility alias for callers that need the authority object."""

        return self.authority


def load_main_token_accounting_authority(
    package_path: str | Path,
    *,
    now: datetime | None = None,
) -> VerifiedTokenAccountingAuthority:
    """Load only Main's exact independently accepted ZIP package."""

    package_file, package_raw = _read_regular(package_path, "token-accounting package")
    package_sha = hashlib.sha256(package_raw).hexdigest()
    if package_sha != MAIN_TOKEN_PACKAGE_SHA256:
        raise LiveSchemaError("Main token-accounting package physical SHA-256 mismatch")
    members = _zip_members(package_raw)
    if set(members) != set(_MEMBERS):
        raise LiveSchemaError("Main token-accounting package member set mismatch")
    _verify_checksums(members)

    manifest = _json_object(members["manifest.json"], "token-accounting manifest")
    _require_seal(
        manifest,
        MAIN_TOKEN_PACKAGE_MANIFEST_SELF_SHA256,
        "token-accounting manifest",
    )
    _verify_manifest(manifest, members)

    authority_raw = members["main_token_accounting_authority_v1.json"]
    anchor_raw = members["main_token_accounting_acceptance_anchor_v1.json"]
    generation_raw = members["main_gemini_generation_contract_v1.json"]
    decision_raw = members["main_token_accounting_user_decision_v1.json"]
    _require_physical(
        authority_raw, MAIN_TOKEN_AUTHORITY_PHYSICAL_SHA256, "token authority"
    )
    _require_physical(anchor_raw, MAIN_TOKEN_ANCHOR_PHYSICAL_SHA256, "token anchor")
    _require_physical(
        generation_raw,
        MAIN_GENERATION_CONTRACT_PHYSICAL_SHA256,
        "Gemini generation contract",
    )

    authority = _validate_authority(
        _json_object(authority_raw, "token authority"), now=now
    )
    anchor = _validate_anchor(
        _json_object(anchor_raw, "token anchor"),
        authority=authority,
        members=members,
    )
    generation = _validate_generation_contract(
        _json_object(generation_raw, "Gemini generation contract"),
        authority=authority,
    )
    decision = _validate_user_decision(
        _json_object(decision_raw, "token-accounting user decision")
    )
    if authority["bindings"]["user_decision_self_sha256"] != decision["integrity"][
        "self_sha256"
    ]:
        raise LiveSchemaError("token authority user-decision binding mismatch")
    return VerifiedTokenAccountingAuthority(
        package_path=package_file,
        package_sha256=package_sha,
        authority=authority,
        anchor=anchor,
        generation_contract=generation,
        user_decision=decision,
        manifest=manifest,
    )


def make_recorded_token_accounting_authority() -> dict[str, Any]:
    """Create an explicit test-only field-map contract for recorded transport."""

    return seal(
        {
            "schema_id": "RecordedGeminiTokenAccountingAuthorityV1",
            "schema_version": "1.0.0",
            "status": "TEST_ONLY_RECORDED",
            "provider_id": _PROVIDER,
            "model_id": _MODEL,
            "model_version": "recorded-official-shape-fixture-v1",
            "provider_usage_source": "usageMetadata",
            "token_fields": list(_TOKEN_FIELDS),
            "provider_usage_field_map": dict(_FIELD_MAP),
            "operational_metrics": list(_OPERATIONAL_METRICS),
            "reasoning_policy": "minimal",
            "thinking_level": "minimal",
            "cost_reporting": TOKEN_ONLY_COST_UNAVAILABLE,
            "generation_contract_self_sha256": canonical_generation_contract_sha256(),
            "final_glossary_decision": None,
            "run_authorized": False,
            "integrity": {},
        }
    )


def validate_recorded_token_accounting_authority(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "status",
            "provider_id",
            "model_id",
            "model_version",
            "provider_usage_source",
            "token_fields",
            "provider_usage_field_map",
            "operational_metrics",
            "reasoning_policy",
            "thinking_level",
            "cost_reporting",
            "generation_contract_self_sha256",
            "final_glossary_decision",
            "run_authorized",
            "integrity",
        },
        path="$.recorded_token_accounting_authority",
    )
    if (
        value["schema_id"] != "RecordedGeminiTokenAccountingAuthorityV1"
        or value["schema_version"] != "1.0.0"
        or value["status"] != "TEST_ONLY_RECORDED"
        or value["provider_id"] != _PROVIDER
        or value["model_id"] != _MODEL
        or value["provider_usage_source"] != "usageMetadata"
        or value["token_fields"] != _TOKEN_FIELDS
        or value["provider_usage_field_map"] != _FIELD_MAP
        or value["operational_metrics"] != _OPERATIONAL_METRICS
        or value["reasoning_policy"] != "minimal"
        or value["thinking_level"] != "minimal"
        or value["cost_reporting"] != TOKEN_ONLY_COST_UNAVAILABLE
        or value["generation_contract_self_sha256"]
        != canonical_generation_contract_sha256()
        or value["final_glossary_decision"] is not None
        or value["run_authorized"] is not False
        or not verify_seal(value)
    ):
        raise LiveSchemaError("recorded token-accounting authority mismatch")
    require_string(value["model_version"], path="$.model_version")
    return dict(value)


def canonical_generation_config() -> dict[str, str]:
    return {"reasoning": "minimal", "thinking_level": "minimal"}


def canonical_generation_contract_sha256() -> str:
    return hashlib.sha256(
        b'{"reasoning":"minimal","thinking_level":"minimal"}'
    ).hexdigest()


def _validate_authority(
    value: Mapping[str, Any], *, now: datetime | None
) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "authority_id",
            "bindings",
            "cost_reporting",
            "effective_from",
            "effective_until",
            "final_glossary_decision",
            "integrity",
            "issuer_id",
            "model_id",
            "model_version",
            "official_source_locator",
            "operational_metrics",
            "provider_id",
            "provider_usage_field_map",
            "provider_usage_source",
            "reasoning_policy",
            "run_authorized",
            "schema_id",
            "schema_version",
            "source_retrieved_at",
            "status",
            "thinking_level",
            "token_fields",
            "unknown_cost_representation",
        },
        path="$.token_accounting_authority",
    )
    if (
        value["schema_id"] != _AUTHORITY_SCHEMA_ID
        or value["schema_version"] != "1.0.0"
        or value["status"] != "MAIN_PINNED_TOKEN_ACCOUNTING_ONLY"
        or value["provider_id"] != _PROVIDER
        or value["model_id"] != _MODEL
        or value["model_version"] != _MODEL
        or value["provider_usage_source"] != "usageMetadata"
        or value["token_fields"] != _TOKEN_FIELDS
        or value["provider_usage_field_map"] != _FIELD_MAP
        or value["operational_metrics"] != _OPERATIONAL_METRICS
        or value["reasoning_policy"] != "minimal"
        or value["thinking_level"] != "minimal"
        or value["cost_reporting"] != TOKEN_ONLY_COST_UNAVAILABLE
        or value["unknown_cost_representation"]
        != {
            "cost": None,
            "cost_status": TOKEN_ONLY_COST_UNAVAILABLE,
            "currency": None,
        }
        or value["final_glossary_decision"] is not None
        or value["run_authorized"] is not False
    ):
        raise LiveSchemaError("Main token-accounting authority semantics mismatch")
    for key in (
        "authority_id",
        "issuer_id",
        "official_source_locator",
        "effective_from",
        "source_retrieved_at",
    ):
        require_string(value[key], path=f"$.token_accounting_authority.{key}")
    bindings = value["bindings"]
    require_exact_keys(
        bindings,
        {
            "canary_candidate_id",
            "candidate_set_sha256",
            "draft4_base_commit",
            "draft4_portability_commit",
            "e_base_commit",
            "generation_contract_self_sha256",
            "main_commit",
            "provider_plan_physical_sha256",
            "provider_plan_self_sha256",
            "si_commit",
            "user_decision_self_sha256",
        },
        path="$.token_accounting_authority.bindings",
    )
    for key in (
        "candidate_set_sha256",
        "generation_contract_self_sha256",
        "provider_plan_physical_sha256",
        "provider_plan_self_sha256",
        "user_decision_self_sha256",
    ):
        require_sha256(bindings[key], path=f"$.token_accounting_authority.bindings.{key}")
    if (
        bindings["e_base_commit"]
        != "894bd1cc9f11e00322aeb9e7fc0120f440ca2a37"
        or bindings["generation_contract_self_sha256"]
        != MAIN_GENERATION_CONTRACT_SELF_SHA256
        or bindings["provider_plan_physical_sha256"]
        != E05_PROVIDER_PLAN_PHYSICAL_SHA256
        or bindings["provider_plan_self_sha256"] != E05_PROVIDER_PLAN_SELF_SHA256
        or bindings["user_decision_self_sha256"]
        != MAIN_TOKEN_USER_DECISION_SELF_SHA256
    ):
        raise LiveSchemaError("Main token-accounting authority binding mismatch")
    effective_from = _timestamp(value["effective_from"], "effective_from")
    _timestamp(value["source_retrieved_at"], "source_retrieved_at")
    if value["effective_until"] is not None:
        require_string(value["effective_until"], path="$.effective_until")
        effective_until = _timestamp(value["effective_until"], "effective_until")
    else:
        effective_until = None
    if now is not None:
        current = now if now.tzinfo is not None else now.replace(tzinfo=effective_from.tzinfo)
        if current < effective_from or (
            effective_until is not None and current > effective_until
        ):
            raise LiveSchemaError("Main token-accounting authority is outside validity")
    _require_seal(value, MAIN_TOKEN_AUTHORITY_SELF_SHA256, "token authority")
    return dict(value)


def _validate_anchor(
    value: Mapping[str, Any],
    *,
    authority: Mapping[str, Any],
    members: Mapping[str, bytes],
) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "accepted_token_field_map",
            "cost_authorized",
            "does_not_grant",
            "evidence",
            "grants",
            "integrity",
            "issued_at",
            "model_id",
            "model_version",
            "provider_id",
            "reviewer_authority_id",
            "reviewer_status",
            "run_authorized",
            "schema_id",
            "schema_version",
            "status",
            "target_authority",
            "verification",
        },
        path="$.token_accounting_anchor",
    )
    if (
        value["schema_id"] != _ANCHOR_SCHEMA_ID
        or value["schema_version"] != "1.0.0"
        or value["status"]
        != "TOKEN_ACCOUNTING_AUTHORITY_ACCEPTED_FOR_CANARY_PREPARATION"
        or value["provider_id"] != _PROVIDER
        or value["model_id"] != _MODEL
        or value["model_version"] != _MODEL
        or value["accepted_token_field_map"] != _FIELD_MAP
        or value["grants"] != ["TOKEN_ACCOUNTING_CONSUMPTION"]
        or value["cost_authorized"] is not False
        or value["run_authorized"] is not False
    ):
        raise LiveSchemaError("Main token-accounting anchor semantics mismatch")
    target = value["target_authority"]
    require_exact_keys(
        target,
        {"path", "physical_sha256", "self_sha256"},
        path="$.token_accounting_anchor.target_authority",
    )
    if target != {
        "path": "main_token_accounting_authority_v1.json",
        "physical_sha256": MAIN_TOKEN_AUTHORITY_PHYSICAL_SHA256,
        "self_sha256": authority["integrity"]["self_sha256"],
    }:
        raise LiveSchemaError("Main token-accounting anchor target mismatch")
    evidence = value["evidence"]
    if not isinstance(evidence, list) or len(evidence) != 3:
        raise LiveSchemaError("Main token-accounting anchor evidence set mismatch")
    seen: set[str] = set()
    for index, row in enumerate(evidence):
        if not isinstance(row, Mapping):
            raise LiveSchemaError("Main token-accounting anchor evidence row invalid")
        require_exact_keys(
            row,
            {"byte_count", "path", "physical_sha256"},
            path=f"$.token_accounting_anchor.evidence[{index}]",
        )
        ref, case_key = canonical_relative_ref(row["path"])
        if case_key in seen or ref not in members:
            raise LiveSchemaError("Main token-accounting anchor evidence ref mismatch")
        seen.add(case_key)
        raw = members[ref]
        if (
            row["byte_count"] != len(raw)
            or row["physical_sha256"] != hashlib.sha256(raw).hexdigest()
        ):
            raise LiveSchemaError("Main token-accounting anchor evidence hash mismatch")
    _require_seal(value, MAIN_TOKEN_ANCHOR_SELF_SHA256, "token anchor")
    return dict(value)


def _validate_generation_contract(
    value: Mapping[str, Any], *, authority: Mapping[str, Any]
) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "api_method",
            "generation_config",
            "integrity",
            "model_id",
            "provider_id",
            "provider_plan_physical_sha256",
            "provider_plan_self_sha256",
            "reasoning_policy",
            "run_authorized",
            "schema_id",
            "schema_version",
            "status",
            "usage_contract",
        },
        path="$.generation_contract",
    )
    generation = value["generation_config"]
    require_exact_keys(
        generation,
        {"response_mime_type", "sampling_parameters_omitted", "thinking_level"},
        path="$.generation_contract.generation_config",
    )
    usage = value["usage_contract"]
    require_exact_keys(
        usage,
        {"accept_nonzero_reasoning_tokens", "required_token_fields"},
        path="$.generation_contract.usage_contract",
    )
    if (
        value["schema_id"] != _GENERATION_SCHEMA_ID
        or value["schema_version"] != "1.0.0"
        or value["status"] != "ACCEPTED_FOR_ZERO_PROVIDER_CANARY_PREPARATION"
        or value["provider_id"] != _PROVIDER
        or value["model_id"] != _MODEL
        or value["api_method"] != "generateContent"
        or value["reasoning_policy"] != "minimal"
        or value["run_authorized"] is not False
        or value["provider_plan_self_sha256"] != E05_PROVIDER_PLAN_SELF_SHA256
        or value["provider_plan_physical_sha256"]
        != E05_PROVIDER_PLAN_PHYSICAL_SHA256
        or generation
        != {
            "response_mime_type": "application/json",
            "sampling_parameters_omitted": [
                "temperature",
                "top_p",
                "top_k",
                "thinking_budget",
            ],
            "thinking_level": "minimal",
        }
        or usage
        != {
            "accept_nonzero_reasoning_tokens": True,
            "required_token_fields": _TOKEN_FIELDS,
        }
        or authority["bindings"]["generation_contract_self_sha256"]
        != value["integrity"]["self_sha256"]
    ):
        raise LiveSchemaError("Main Gemini generation contract mismatch")
    _require_seal(
        value, MAIN_GENERATION_CONTRACT_SELF_SHA256, "Gemini generation contract"
    )
    return dict(value)


def _validate_user_decision(value: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "decision",
            "decision_source",
            "integrity",
            "issued_at",
            "run_authorized",
            "schema_id",
            "schema_version",
            "status",
        },
        path="$.token_accounting_user_decision",
    )
    if (
        value["schema_id"] != "MainTokenAccountingUserDecisionV1"
        or value["schema_version"] != "1.0.0"
        or value["status"] != "TOKEN_ONLY_ACCOUNTING_APPROVED"
        or value["run_authorized"] is not False
        or value["decision"]
        != {
            "estimate_or_fabricate_usd_cost": False,
            "record_tokens": True,
            "record_usd_cost_only_when_provider_returns_billed_usd": True,
            "unknown_cost_representation": {
                "cost": None,
                "cost_status": TOKEN_ONLY_COST_UNAVAILABLE,
                "currency": None,
            },
        }
    ):
        raise LiveSchemaError("Main token-accounting user decision mismatch")
    _require_seal(
        value, MAIN_TOKEN_USER_DECISION_SELF_SHA256, "token-accounting user decision"
    )
    return dict(value)


def _verify_manifest(value: Mapping[str, Any], members: Mapping[str, bytes]) -> None:
    require_exact_keys(
        value,
        {"files", "integrity", "schema_id", "schema_version", "status"},
        path="$.token_accounting_manifest",
    )
    if (
        value["schema_id"] != "MainTokenAccountingPackageManifestV1"
        or value["schema_version"] != "1.0.0"
        or value["status"] != "PASS"
    ):
        raise LiveSchemaError("Main token-accounting manifest identity mismatch")
    expected = set(members) - {"CHECKSUMS.sha256", "manifest.json"}
    rows = value["files"]
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise LiveSchemaError("Main token-accounting manifest inventory mismatch")
    refs: list[str] = []
    cases: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise LiveSchemaError("Main token-accounting manifest row invalid")
        require_exact_keys(
            row,
            {"byte_count", "path", "physical_sha256"},
            path=f"$.token_accounting_manifest.files[{index}]",
        )
        ref, case_key = canonical_relative_ref(row["path"])
        if case_key in cases:
            raise LiveSchemaError("Main token-accounting manifest case collision")
        cases.add(case_key)
        refs.append(ref)
        raw = members.get(ref)
        if raw is None or row["byte_count"] != len(raw):
            raise LiveSchemaError("Main token-accounting manifest file mismatch")
        if row["physical_sha256"] != hashlib.sha256(raw).hexdigest():
            raise LiveSchemaError("Main token-accounting manifest hash mismatch")
    if refs != sorted(refs) or set(refs) != expected:
        raise LiveSchemaError("Main token-accounting manifest ordering/inventory mismatch")


def _verify_checksums(members: Mapping[str, bytes]) -> None:
    try:
        text = members["CHECKSUMS.sha256"].decode("ascii", errors="strict")
    except UnicodeError as exc:
        raise LiveSchemaError("Main token-accounting CHECKSUMS is not ASCII") from exc
    rows: dict[str, str] = {}
    case_keys: set[str] = set()
    for line in text.splitlines():
        match = _SHA256_ROW.fullmatch(line)
        if match is None:
            raise LiveSchemaError("Main token-accounting CHECKSUMS row invalid")
        digest, raw_ref = match.groups()
        ref, case_key = canonical_relative_ref(raw_ref)
        if ref in rows or case_key in case_keys:
            raise LiveSchemaError("Main token-accounting CHECKSUMS duplicate")
        rows[ref] = digest
        case_keys.add(case_key)
    expected = set(members) - {"CHECKSUMS.sha256"}
    if set(rows) != expected:
        raise LiveSchemaError("Main token-accounting CHECKSUMS inventory mismatch")
    for ref, digest in rows.items():
        if hashlib.sha256(members[ref]).hexdigest() != digest:
            raise LiveSchemaError("Main token-accounting CHECKSUMS hash mismatch")


def _zip_members(raw: bytes) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise LiveSchemaError("Main token-accounting package is not a valid ZIP") from exc
    result: dict[str, bytes] = {}
    case_keys: set[str] = set()
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                raise LiveSchemaError("Main token-accounting ZIP contains a directory entry")
            ref, case_key = canonical_relative_ref(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and stat.S_ISLNK(mode):
                raise LiveSchemaError("Main token-accounting ZIP contains a symlink")
            if ref in result or case_key in case_keys:
                raise LiveSchemaError("Main token-accounting ZIP member collision")
            try:
                result[ref] = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise LiveSchemaError("cannot read Main token-accounting ZIP") from exc
            case_keys.add(case_key)
    return result


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as exc:
        raise LiveSchemaError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise LiveSchemaError(f"{label} must be a JSON object")
    return value


def _require_physical(raw: bytes, expected: str, label: str) -> None:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise LiveSchemaError(f"{label} physical SHA-256 mismatch")


def _require_seal(value: Mapping[str, Any], expected: str, label: str) -> None:
    if not verify_seal(value) or value.get("integrity", {}).get("self_sha256") != expected:
        raise LiveSchemaError(f"{label} canonical self SHA-256 mismatch")


def _read_regular(path: str | Path, label: str) -> tuple[Path, bytes]:
    supplied = Path(path).absolute()
    try:
        reject_link(supplied)
        resolved = supplied.resolve(strict=True)
        reject_link(resolved)
    except (OSError, ValueError) as exc:
        raise LiveSchemaError(f"cannot resolve {label}") from exc
    if not resolved.is_file():
        raise LiveSchemaError(f"{label} is not a regular file")
    return resolved, resolved.read_bytes()


def _timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiveSchemaError(f"token-accounting {label} is invalid") from exc
    if parsed.tzinfo is None:
        raise LiveSchemaError(f"token-accounting {label} lacks timezone")
    return parsed


__all__ = [
    "E05_PROVIDER_PLAN_PHYSICAL_SHA256",
    "E05_PROVIDER_PLAN_SELF_SHA256",
    "MAIN_GENERATION_CONTRACT_SELF_SHA256",
    "MAIN_TOKEN_ANCHOR_PHYSICAL_SHA256",
    "MAIN_TOKEN_ANCHOR_SELF_SHA256",
    "MAIN_TOKEN_AUTHORITY_PHYSICAL_SHA256",
    "MAIN_TOKEN_AUTHORITY_SELF_SHA256",
    "MAIN_TOKEN_PACKAGE_SHA256",
    "TOKEN_ONLY_COST_UNAVAILABLE",
    "VerifiedTokenAccountingAuthority",
    "canonical_generation_config",
    "canonical_generation_contract_sha256",
    "load_main_token_accounting_authority",
    "make_recorded_token_accounting_authority",
    "validate_recorded_token_accounting_authority",
]
