from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from terminology_contracts.integrity import sha256_file, verify_self_hash

from ..errors import GatePolicyError
from ..jsonio import assert_strict_json_file, load_json_object


ACTION_POLICY_AUTHORITY_SELF_SHA256 = (
    "1fca452c0604b7f41e9ffab72de0c134b108c52cafed279153bd7e98a0e8994a"
)
ACTION_POLICY_AUTHORITY_PHYSICAL_SHA256 = (
    "db51faa37b7f1186e62ca4c8d6776bd0a2a2b2b0ac3e78eab87328253f535761"
)
APPROVED_ACTION_POLICY_SHA256 = (
    "4220b15b7b5d5b740946b9b258a5e1f25469a8f8409ca6e1a0b399464285c9f5"
)
_AUTHORITY_PATH = (
    Path(__file__).resolve().parents[1]
    / "policies"
    / "gate_action_policy_authority_v1.0.0.json"
)


@dataclass(frozen=True)
class VerifiedActionPolicyAuthority:
    path: Path
    self_sha256: str
    approved_action_policy_sha256: str
    payload: dict[str, Any]


def verify_action_policy_authority() -> VerifiedActionPolicyAuthority:
    try:
        assert_strict_json_file(_AUTHORITY_PATH)
        payload = load_json_object(_AUTHORITY_PATH)
        verify_self_hash(payload, path=str(_AUTHORITY_PATH))
    except (OSError, UnicodeError, ValueError) as exc:
        raise GatePolicyError(f"invalid action-policy authority: {exc}") from exc

    if payload.get("schema_id") != "GlobalGateActionPolicyAuthorityV1":
        raise GatePolicyError("unsupported action-policy authority schema_id")
    if payload.get("schema_version") != "1.0.0":
        raise GatePolicyError("unsupported action-policy authority schema_version")
    if payload.get("status") != "REVIEWED":
        raise GatePolicyError("action-policy authority is not reviewed")
    declared = payload.get("integrity", {}).get("self_sha256")
    if declared != ACTION_POLICY_AUTHORITY_SELF_SHA256:
        raise GatePolicyError("action-policy authority self SHA-256 mismatch")
    if sha256_file(_AUTHORITY_PATH) != ACTION_POLICY_AUTHORITY_PHYSICAL_SHA256:
        raise GatePolicyError("action-policy authority physical SHA-256 mismatch")

    approved = payload.get("approved_action_policy")
    if not isinstance(approved, dict):
        raise GatePolicyError("action-policy authority approval is missing")
    if approved.get("self_sha256") != APPROVED_ACTION_POLICY_SHA256:
        raise GatePolicyError("action-policy authority approval SHA-256 mismatch")
    if approved.get("policy_id") != "global-gate-action-selection-v1":
        raise GatePolicyError("action-policy authority policy_id mismatch")
    if approved.get("policy_version") != "1.0.0":
        raise GatePolicyError("action-policy authority policy_version mismatch")

    contracts = payload.get("contracts_authority")
    if not isinstance(contracts, dict) or contracts != {
        "tag": "contracts-v1.1.0",
        "commit": "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed",
        "manifest_sha256": (
            "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
        ),
        "gate_policy_artifact_sha256": (
            "9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2"
        ),
    }:
        raise GatePolicyError("action-policy authority contracts binding mismatch")

    return VerifiedActionPolicyAuthority(
        path=_AUTHORITY_PATH,
        self_sha256=declared,
        approved_action_policy_sha256=APPROVED_ACTION_POLICY_SHA256,
        payload=payload,
    )
