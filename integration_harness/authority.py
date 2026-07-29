"""Resolution and pinning of external authority artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import AuthorityError
from .hashing import self_sha256, sha256_file
from .jsonio import load_json


@dataclass(frozen=True)
class AuthoritySet:
    receipt_path: Path
    contracts_root: Path
    authority_tag: str
    authority_commit: str
    contract_version: str
    contracts_manifest_sha256: str
    contracts_manifest_file_sha256: str
    gate_policy_path: Path
    gate_policy_sha256: str
    gate_policy_file_sha256: str
    feature_registry_path: Path
    feature_registry_sha256: str
    action_policy_path: Path
    action_policy_sha256: str
    action_policy_file_sha256: str
    receipt_physical_sha256: str
    receipt_self_sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "authority_tag": self.authority_tag,
            "authority_commit": self.authority_commit,
            "contract_version": self.contract_version,
            "contracts_manifest_sha256": self.contracts_manifest_sha256,
            "contracts_manifest_file_sha256": self.contracts_manifest_file_sha256,
            "gate_policy_sha256": self.gate_policy_sha256,
            "gate_policy_file_sha256": self.gate_policy_file_sha256,
            "feature_registry_sha256": self.feature_registry_sha256,
            "action_policy_sha256": self.action_policy_sha256,
            "action_policy_file_sha256": self.action_policy_file_sha256,
            "receipt_physical_sha256": self.receipt_physical_sha256,
            "receipt_self_sha256": self.receipt_self_sha256,
        }


def _require_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise AuthorityError(f"authority receipt missing {key}")
    return result


def resolve_authority(
    receipt_path: Path,
    contracts_root: Path,
    *,
    action_policy_path: Path | None = None,
    expected: Mapping[str, Any] | None = None,
) -> AuthoritySet:
    receipt_path = receipt_path.resolve()
    contracts_root = contracts_root.resolve()
    if not receipt_path.is_file() or not contracts_root.is_dir():
        raise AuthorityError("authority receipt/contracts root is unavailable")
    receipt = load_json(receipt_path, require_object=True)
    authority_tag = _require_string(receipt, "authority_tag")
    authority_commit = _require_string(receipt, "authority_commit")
    contract_version = _require_string(receipt, "contract_version")
    manifest_path = contracts_root / "manifest.json"
    gate_policy = contracts_root / "policies" / "gate_policy_v1.0.0.json"
    feature_registry = contracts_root / "registries" / "feature_contract_v1.1.0.json"
    action_policy = (
        action_policy_path.resolve()
        if action_policy_path is not None
        else contracts_root.parent / "global_validator" / "v1" / "policies" / "gate_action_selection_v1.0.0.json"
    )
    for path in (manifest_path, gate_policy, feature_registry, action_policy):
        if not path.is_file():
            raise AuthorityError(f"required authority artifact is missing: {path}")
    expected = expected or {}
    for key, actual in {
        "authority_tag": authority_tag,
        "authority_commit": authority_commit,
        "contract_version": contract_version,
    }.items():
        if key in expected and expected[key] != actual:
            raise AuthorityError(f"authority mismatch for {key}: expected {expected[key]}, got {actual}")
    manifest_file_sha = sha256_file(manifest_path)
    manifest_value = load_json(manifest_path, require_object=True)
    manifest_integrity = manifest_value.get("integrity")
    manifest_sha = manifest_integrity.get("manifest_sha256") if isinstance(manifest_integrity, dict) else None
    if not isinstance(manifest_sha, str) or len(manifest_sha) != 64:
        raise AuthorityError("Contracts manifest has no canonical manifest SHA")
    declared_manifest_sha = receipt.get("manifest_sha256", receipt.get("contracts_manifest_sha256"))
    if declared_manifest_sha is not None and declared_manifest_sha != manifest_sha:
        raise AuthorityError("authority receipt Contracts manifest SHA mismatch")
    declared_manifest_file_sha = receipt.get("manifest_file_sha256")
    if declared_manifest_file_sha is not None and declared_manifest_file_sha != manifest_file_sha:
        raise AuthorityError("authority receipt Contracts manifest file SHA mismatch")
    expected_manifest = expected.get("contracts_manifest_sha256", expected.get("manifest_sha256"))
    if expected_manifest not in (None, manifest_sha):
        raise AuthorityError("Contracts manifest SHA mismatch")
    expected_manifest_file = expected.get("contracts_manifest_file_sha256", expected.get("manifest_file_sha256"))
    if expected_manifest_file not in (None, manifest_file_sha):
        raise AuthorityError("Contracts manifest file SHA mismatch")
    gate_file_sha = sha256_file(gate_policy)
    gate_value = load_json(gate_policy, require_object=True)
    gate_sha = gate_value.get("integrity", {}).get("self_sha256")
    if not isinstance(gate_sha, str):
        raise AuthorityError("Gate policy has no canonical self hash")
    feature_sha = sha256_file(feature_registry)
    action_file_sha = sha256_file(action_policy)
    action_value = load_json(action_policy, require_object=True)
    action_sha = action_value.get("integrity", {}).get("self_sha256")
    if not isinstance(action_sha, str):
        raise AuthorityError("Global action policy has no canonical self hash")
    declared_action_sha = receipt.get("action_policy_sha256", receipt.get("global_action_policy_sha256"))
    if declared_action_sha is not None and declared_action_sha != action_sha:
        raise AuthorityError("authority receipt action policy SHA mismatch")
    declared_gate_sha = receipt.get("gate_policy_artifact_sha256", receipt.get("gate_policy_sha256"))
    if declared_gate_sha is not None and declared_gate_sha != gate_sha:
        raise AuthorityError("authority receipt Gate policy SHA mismatch")
    declared_gate_file_sha = receipt.get("gate_policy_file_sha256")
    if declared_gate_file_sha is not None and declared_gate_file_sha != gate_file_sha:
        raise AuthorityError("authority receipt Gate policy file SHA mismatch")
    declared_feature_sha = receipt.get("feature_contract_file_sha256")
    if declared_feature_sha is not None and declared_feature_sha != feature_sha:
        raise AuthorityError("authority receipt feature registry SHA mismatch")
    expected_gate = expected.get("gate_policy_sha256", expected.get("gate_policy_artifact_sha256"))
    if expected_gate not in (None, gate_sha):
        raise AuthorityError("Gate policy SHA mismatch")
    expected_action = expected.get("action_policy_sha256", expected.get("global_action_policy_sha256"))
    if expected_action not in (None, action_sha):
        raise AuthorityError("Global action policy SHA mismatch")
    if expected.get("feature_registry_sha256") not in (None, feature_sha):
        raise AuthorityError("Feature registry SHA mismatch")
    receipt_integrity = receipt.get("integrity")
    receipt_self = None
    if isinstance(receipt_integrity, dict) and receipt_integrity.get("self_sha256"):
        receipt_self = receipt_integrity["self_sha256"]
        if receipt_self != self_sha256(receipt):
            raise AuthorityError("authority receipt self hash mismatch")
    receipt_physical = sha256_file(receipt_path)
    if expected.get("receipt_physical_sha256") not in (None, receipt_physical):
        raise AuthorityError("authority receipt physical SHA mismatch")
    if expected.get("receipt_self_sha256") not in (None, receipt_self):
        raise AuthorityError("authority receipt self SHA mismatch")
    return AuthoritySet(
        receipt_path=receipt_path,
        contracts_root=contracts_root,
        authority_tag=authority_tag,
        authority_commit=authority_commit,
        contract_version=contract_version,
        contracts_manifest_sha256=manifest_sha,
        contracts_manifest_file_sha256=manifest_file_sha,
        gate_policy_path=gate_policy,
        gate_policy_sha256=gate_sha,
        gate_policy_file_sha256=gate_file_sha,
        feature_registry_path=feature_registry,
        feature_registry_sha256=feature_sha,
        action_policy_path=action_policy,
        action_policy_sha256=action_sha,
        action_policy_file_sha256=action_file_sha,
        receipt_physical_sha256=receipt_physical,
        receipt_self_sha256=receipt_self,
    )
