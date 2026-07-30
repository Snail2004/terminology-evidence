"""Fail-closed loading of externally pinned production authority bytes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..common import LiveSchemaError, canonical_sha256, file_sha256, load_object, require_exact_keys, require_sha256, require_string, verify_seal
from .adapter import load_authority_bundle, validate_protocol_instance


EXECUTION_BINDING_KEYS = {
    "cohort_id", "candidate_ids", "run_id", "phase_id", "run_spec_id",
    "registry_self_sha256", "snapshot_manifest_sha256", "policy_hashes",
    "e_commit", "e_tree", "provider_role_plan_sha256", "budget_sha256",
    "authority_bundle_self_sha256",
}


def load_production_authority(inputs: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Load every production authority from a pinned regular file, never RAM-only data."""
    require_exact_keys(inputs, {
        "profile_path", "expected_profile_physical_sha256", "receipt_paths",
        "protocol_schema_paths", "authorization_receipt_path",
        "expected_authorization_receipt_physical_sha256", "expected_e_commit", "expected_e_tree",
    })
    bundle = load_authority_bundle(
        profile_path=inputs["profile_path"], receipt_paths=inputs["receipt_paths"],
        protocol_schema_paths=inputs["protocol_schema_paths"], execution_mode="PRODUCTION_AUTHORITY",
        expected_profile_physical_sha256=inputs["expected_profile_physical_sha256"],
    )
    schema_path = Path(inputs["protocol_schema_paths"]["LIVE_AUTHORIZATION_RECEIPT"])
    schema_binding = bundle["protocol_schema_bindings"]["LIVE_AUTHORIZATION_RECEIPT"]
    if file_sha256(schema_path) != schema_binding["artifact_physical_sha256"]:
        raise LiveSchemaError("authorization schema bytes are not Main-bound")
    schema = load_object(schema_path)
    if canonical_sha256(schema) != schema_binding["artifact_self_sha256"]:
        raise LiveSchemaError("authorization schema canonical hash is not Main-bound")

    receipt_path = Path(inputs["authorization_receipt_path"])
    expected_physical = require_sha256(inputs["expected_authorization_receipt_physical_sha256"], path="$.expected_authorization_receipt_physical_sha256")
    if file_sha256(receipt_path) != expected_physical:
        raise LiveSchemaError("authorization receipt physical hash mismatch")
    receipt = validate_protocol_instance(load_object(receipt_path), role="LIVE_AUTHORIZATION_RECEIPT", schema_path=schema_path)
    if not verify_seal(receipt):
        raise LiveSchemaError("authorization receipt canonical self hash mismatch")
    if receipt.get("authorization_status") != "RUN_AUTHORIZED" or receipt.get("test_only") is not False:
        raise LiveSchemaError("production receipt is not RUN_AUTHORIZED")
    trusted_pairs = {(row["issuer_id"], row["authority_id"]) for row in bundle["receipt_bindings"].values()}
    if (receipt.get("issuer_id"), receipt.get("authority_id")) not in trusted_pairs:
        raise LiveSchemaError("authorization receipt issuer/authority is not Main-trusted")
    current = now or datetime.now(timezone.utc)
    if not _timestamp(receipt.get("valid_from"), "valid_from") <= current <= _timestamp(receipt.get("valid_until"), "valid_until"):
        raise LiveSchemaError("authorization receipt is outside its validity interval")

    binding = receipt.get("e_execution_binding")
    if not isinstance(binding, Mapping):
        raise LiveSchemaError("authorization receipt lacks E execution binding")
    require_exact_keys(binding, EXECUTION_BINDING_KEYS, path="$.e_execution_binding")
    for key in ("registry_self_sha256", "snapshot_manifest_sha256", "provider_role_plan_sha256", "budget_sha256", "authority_bundle_self_sha256"):
        require_sha256(binding[key], path=f"$.e_execution_binding.{key}")
    for key in ("cohort_id", "run_id", "phase_id", "run_spec_id"):
        require_string(binding[key], path=f"$.e_execution_binding.{key}")
    candidates = binding["candidate_ids"]
    if not isinstance(candidates, list) or not candidates or candidates != sorted(set(candidates)):
        raise LiveSchemaError("authorization candidate_ids must be sorted unique and nonempty")
    policies = binding["policy_hashes"]
    require_exact_keys(policies, {"retrieval_policy", "query_template_set", "provider_role_plan", "aggregation_policy"}, path="$.e_execution_binding.policy_hashes")
    for key, value in policies.items():
        require_sha256(value, path=f"$.e_execution_binding.policy_hashes.{key}")
    for key in ("e_commit", "e_tree"):
        require_string(binding[key], path=f"$.e_execution_binding.{key}")
    if binding["e_commit"] != inputs["expected_e_commit"] or binding["e_tree"] != inputs["expected_e_tree"]:
        raise LiveSchemaError("authorization receipt E commit/tree mismatch")
    if binding["authority_bundle_self_sha256"] != bundle["integrity"]["self_sha256"]:
        raise LiveSchemaError("authorization receipt authority bundle mismatch")
    return {"bundle": bundle, "receipt": dict(receipt), "receipt_physical_sha256": expected_physical,
            "schema_physical_sha256": schema_binding["artifact_physical_sha256"], "schema_canonical_sha256": schema_binding["artifact_self_sha256"],
            "execution_binding": dict(binding)}


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise LiveSchemaError(f"authorization {field} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiveSchemaError(f"authorization {field} is invalid") from exc
    if parsed.tzinfo is None:
        raise LiveSchemaError(f"authorization {field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


__all__ = ["load_production_authority"]
