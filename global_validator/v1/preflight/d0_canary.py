"""Fail-closed compatibility contract for the D0 one-candidate canary.

This module does not assemble a Global input or execute the decision engine.
It only verifies the accepted C, SI, E, and Draft4 preparation surfaces before
Main independently accepts the zero-provider development preflight.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from terminology_contracts.integrity import verify_self_hash

from ..errors import InputValidationError, IntegrityValidationError
from ..jsonio import load_json_object


SCHEMA_ID = "GlobalD0OneCandidateProvisionalPreflightV1"
SCHEMA_VERSION = "1.0.0"
PROVISIONAL_PREFLIGHT_STATUS = (
    "GLOBAL_D0_ONE_CANDIDATE_ZERO_PROVIDER_PREFLIGHT_READY_FOR_MAIN_ACCEPTANCE"
)
CANARY_CANDIDATE_ID = "candidate_479fdd8ff6d15304debec117"

C01_COMMIT = "a9965c93782834fd8d913df370f437a26059d267"
SI_COMMIT = "2d4aac1341561057e45e61f691cb2062413ede9c"
E05_SURFACE_COMMIT = "894bd1cc9f11e00322aeb9e7fc0120f440ca2a37"
E_FINAL_CHILD = "0888bfd180fcd00b43848977a0576160ad471400"
E_FINAL_PARENT = E05_SURFACE_COMMIT
E_FINAL_TREE = "345d1f837767f26d9154d4d287c3507c66aaa842"
E_FINAL_REVIEW_PACKAGE_SHA256 = (
    "b8c5a02323ff04c2f0a8bdf22b60495c9cd22deeb23428f8dcbbb309c0b64836"
)
E_FINAL_COMPLETE_BUNDLE_SHA256 = (
    "3ad42c58ec8f57b77425d111a63197d53200d49b0c2566b6e24d61a25f85df19"
)
DRAFT4_TOKEN_COMMIT = "0acb5a82106dbcefa13fcb998590f7ce04af852f"
DRAFT4_TOKEN_TREE = "f315548679756e671a227436d705487ce53f4408"
TOKEN_AUTHORITY_SELF_SHA256 = (
    "467eaad13fe23b08be15ee86bc1777e66faae9eb06c407f596e3c9b273155e80"
)

_EXPECTED_SURFACES = {
    "c01": {
        "status": "ACCEPTED_OUTPUT_SURFACE",
        "commit": C01_COMMIT,
        "provider_role_plan_self_sha256": (
            "155261fc2c80e54b6e22e266104fa6a5a2040fa6faf4b8d7865bb970a763e815"
        ),
        "output_schema_id": "ContextEvidencePackageV1",
        "final_decision_owner": "GLOBAL_TERMINOLOGY_VALIDATOR",
        "final_glossary_decision": None,
    },
    "si": {
        "status": "SI_EV02_OWNER_BINDING_ACCEPTED",
        "commit": SI_COMMIT,
        "release_schema_id": "HarnessProducerSafeCohortAuthorityReleaseV1",
        "canary_candidate_id": CANARY_CANDIDATE_ID,
        "candidate_set_sha256": (
            "e72286e06201297864d3163311336515092d841181e484c01276faa9b989fa0b"
        ),
        "supported_candidate_counts": [1, 15],
        "provider_calls": 0,
        "network_calls": 0,
        "gold_access": 0,
        "final_glossary_decision": None,
    },
    "e05": {
        "status": (
            "E_TOKEN_ONLY_PROVIDER_INTEGRATION_ACCEPTED_FOR_ZERO_PROVIDER_"
            "CANARY_PREPARATION"
        ),
        "surface_commit": E05_SURFACE_COMMIT,
        "final_e_narrow_child": E_FINAL_CHILD,
        "final_e_narrow_parent": E_FINAL_PARENT,
        "final_e_narrow_tree": E_FINAL_TREE,
        "final_e_review_package_sha256": E_FINAL_REVIEW_PACKAGE_SHA256,
        "final_e_complete_bundle_sha256": E_FINAL_COMPLETE_BUNDLE_SHA256,
        "e05_authority_adapter_blob_oid": (
            "5d272300c21be990c51b2129f67eba9fab129173"
        ),
        "token_accounting_adapter_blob_oid": (
            "2cf692a3f1def051aa9807b604d0adee1567cfce"
        ),
        "ledger_schema_id": "ELiveLedgerEventV1",
        "draft4_schema_version": "1.1.0-draft.4",
        "draft4_token_accounting_binding_status": (
            "TOKEN_ACCOUNTING_AUTHORITY_ACCEPTED_FOR_CANARY_PREPARATION"
        ),
        "draft4_token_accounting_commit": DRAFT4_TOKEN_COMMIT,
        "draft4_token_accounting_tree": DRAFT4_TOKEN_TREE,
        "token_accounting_authority_self_sha256": TOKEN_AUTHORITY_SELF_SHA256,
        "token_accounting_authority_physical_sha256": (
            "b9b8186aa1bb92f1226fa187e016e9455dc055450e6299d49b50195da6a55e73"
        ),
        "token_accounting_acceptance_anchor_self_sha256": (
            "1c0ba8d193ff15d4a61094855dd8e266ea63793b43ceea13433c693774eb7a0c"
        ),
        "usage_snapshot_schema_physical_sha256": (
            "f5a7fd6690adc48e6459fa60a503b91bfda1704de46bc79afacb8e0fae1157e7"
        ),
        "live_ledger_schema_physical_sha256": (
            "2e1417285e6a428c83e7e27a4b8a42b032b362791ec7af927d43c4d67566f489"
        ),
        "network_request_count_durable": True,
        "price_table_interpretation": None,
        "live_execution_authorized": False,
        "token_only_provider_integration_accepted_for_zero_provider_canary_preparation": True,
    },
}

_EXPECTED_INVARIANTS = {
    "approval_score": None,
    "auto_approved_count": 0,
    "certificate_count": 0,
    "gold_access": 0,
    "provider_calls": 0,
    "network_calls": 0,
    "corpus_access": 0,
}

_EXPECTED_CLAIMS = {
    "e_token_only_provider_integration_accepted_for_zero_provider_canary_preparation": True,
    "e_live_runtime_authority_active": False,
    "global_d0_development_preflight_pass": False,
    "run_authorized": False,
}


def load_d0_canary_preflight(path: Path) -> dict[str, Any]:
    """Load and validate one provisional, zero-provider preflight artifact."""

    try:
        value = load_json_object(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise InputValidationError(f"cannot load D0 canary preflight: {exc}") from exc
    return validate_d0_canary_preflight(value)


def validate_d0_canary_preflight(value: Mapping[str, Any]) -> dict[str, Any]:
    """Verify the preparation artifact without granting final authority."""

    if not isinstance(value, Mapping):
        raise InputValidationError("D0 canary preflight must be an object")
    _require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "status",
            "candidate_id",
            "candidate_count",
            "mode",
            "surfaces",
            "token_accounting",
            "invariants",
            "claims",
            "integrity",
        },
        path="$",
    )
    if value["schema_id"] != SCHEMA_ID or value["schema_version"] != SCHEMA_VERSION:
        raise InputValidationError("D0 canary preflight schema mismatch")
    if value["status"] != PROVISIONAL_PREFLIGHT_STATUS:
        raise InputValidationError("D0 canary preflight status mismatch")
    if value["candidate_id"] != CANARY_CANDIDATE_ID or value["candidate_count"] != 1:
        raise InputValidationError("D0 canary preflight candidate binding mismatch")
    if value["mode"] != "DEVELOPMENT_HEURISTIC":
        raise InputValidationError("D0 canary preflight must remain development-only")

    surfaces = _mapping(value["surfaces"], "$.surfaces")
    _require_exact_keys(surfaces, set(_EXPECTED_SURFACES), path="$.surfaces")
    for role, expected in _EXPECTED_SURFACES.items():
        observed = _mapping(surfaces[role], f"$.surfaces.{role}")
        if observed != expected:
            raise InputValidationError(f"$.surfaces.{role} differs from preparation pin")

    _validate_token_accounting(value["token_accounting"])
    if _mapping(value["invariants"], "$.invariants") != _EXPECTED_INVARIANTS:
        raise InputValidationError("development invariants differ from the zero-provider lock")
    if _mapping(value["claims"], "$.claims") != _EXPECTED_CLAIMS:
        raise InputValidationError("provisional preflight contains an unauthorized claim")

    try:
        verify_self_hash(dict(value), path="D0 canary provisional preflight")
    except ValueError as exc:
        raise IntegrityValidationError(str(exc)) from exc
    return dict(value)


def _validate_token_accounting(value: Any) -> None:
    usage = _mapping(value, "$.token_accounting")
    _require_exact_keys(
        usage,
        {
            "status",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
            "network_request_count",
            "cost",
            "currency",
        },
        path="$.token_accounting",
    )
    if usage["status"] != "TOKEN_ONLY_COST_UNAVAILABLE":
        raise InputValidationError("token accounting status is not token-only")
    tokens = []
    for field in (
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    ):
        observed = usage[field]
        if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
            raise InputValidationError(f"$.token_accounting.{field} must be nonnegative")
        tokens.append(observed)
    if tokens[3] != tokens[0] + tokens[1] + tokens[2]:
        raise InputValidationError("token accounting total does not equal its components")
    network_requests = usage["network_request_count"]
    if (
        isinstance(network_requests, bool)
        or not isinstance(network_requests, int)
        or network_requests != 0
    ):
        raise InputValidationError(
            "provisional zero-provider network_request_count must be zero"
        )
    if usage["cost"] is not None or usage["currency"] is not None:
        raise InputValidationError("token-only accounting must not invent cost or currency")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise InputValidationError(f"{path} must be an object")
    return dict(value)


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], *, path: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise InputValidationError(
            f"{path} fields differ; missing={missing}, extra={extra}"
        )
