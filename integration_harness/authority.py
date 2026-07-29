"""Resolution and persistence of versioned external authority artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .approval_binding import VerifiedApprovalBinding, verify_approval_binding
from .contracts_verifier import (
    ContractVerifierEvidence,
    PublicContractR2Verifier,
    RECEIPT_PHYSICAL_SHA256,
    RECEIPT_SELF_SHA256,
)
from .errors import AuthorityError
from .hashing import self_sha256, sha256_bytes, sha256_file
from .jsonio import canonical_bytes, load_json


SYNTHETIC_LOCAL_CONFORMANCE = "SYNTHETIC_LOCAL_CONFORMANCE"
CONTRACTS_R2_CURRENT = "CONTRACTS_R2_CURRENT"
CONTRACTS_R1_HISTORICAL_REPLAY = "CONTRACTS_R1_HISTORICAL_REPLAY"

R1_RECEIPT_SELF_SHA256 = "c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4"
R1_RECEIPT_PHYSICAL_SHA256 = "3497460f16ca478dada7b25425775882f10d1cb2b5d3638c36cba4ec5fb2791b"
AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
AUTHORITY_TAG_OBJECT_OID = "1a8c00d12f100145a276cd8304440ff0a7e8d2a1"
TAGGED_CONTRACT_TREE_OID = "d6386c4c4d19ba2aad982a519b9b59ecfd2213c9"
R2_PUBLICATION_COMMIT = "282409c470049760904fa16de4c67d711b5fcd00"
R2_MODULE_TREE_OID = "938bca1f9c60596ef9403a43f0355476ad42afef"
CONTRACT_VERSION = "1.1.0"
MANIFEST_SELF_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
MANIFEST_PHYSICAL_SHA256 = "383884e28e9b9203b0ce346d8ad08572dea235a2d53c40c07bf1de22403f73fc"
GATE_POLICY_SELF_SHA256 = "9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2"
GATE_POLICY_PHYSICAL_SHA256 = "3d9fe31a96eecb0ae5f84823f87c7bb4739bd8139942e7b04ac279cc8c39dc85"
FEATURE_REGISTRY_SELF_SHA256 = "057f47d68097286f04f0870d2e78944e59c07b0cb4e9db7f9d8675c9f2c8b182"
FEATURE_REGISTRY_PHYSICAL_SHA256 = "78a0cc6e969c88173a2203c76e41411e836a326616da452f38148c9f0c960244"
RELEASE_MANIFEST_SELF_SHA256 = "d64b82abb2b74bf7477a1c9f740c8d6a3bc0155dae8d3476b484fee239ad7522"
RELEASE_MANIFEST_PHYSICAL_SHA256 = "bd9d4c10908bdb951eaebb8c139afe7a09b198bd6422ef7626dc728c6ea9ccb7"
RELEASE_CHECKSUMS_PHYSICAL_SHA256 = "295a93ea167c0cbb590e6d4cf5894f18e48782aa942dbe424855c19cb0c52196"
FINAL_AUDIT_SELF_SHA256 = "e8cec2de12224f816ca7eb6c8b38d75f2b07f6d99f44c019caae44f45c961202"
FINAL_AUDIT_PHYSICAL_SHA256 = "21a36752d0e244449c650221a0a89c73376526efd88a3b56f62d0e0c68eedfd3"
FINAL_ZIP_SHA256 = "2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471"
ACTION_POLICY_SELF_SHA256 = "4220b15b7b5d5b740946b9b258a5e1f25469a8f8409ca6e1a0b399464285c9f5"
ACTION_POLICY_PHYSICAL_SHA256 = "33d48fadc91ede7cfd90860b12f1786299eabb76d1d95a57b048c7d1a333fd9e"
ACTION_POLICY_AUTHORITY_SELF_SHA256 = "1fca452c0604b7f41e9ffab72de0c134b108c52cafed279153bd7e98a0e8994a"
ACTION_POLICY_AUTHORITY_PHYSICAL_SHA256 = "db51faa37b7f1186e62ca4c8d6776bd0a2a2b2b0ac3e78eab87328253f535761"


@dataclass(frozen=True)
class AuthoritySet:
    receipt_path: Path
    contracts_root: Path
    action_policy_path: Path
    action_policy_authority_path: Path
    authority_mode: str
    compatibility_mode: str
    authority_tag: str
    authority_tag_object_oid: str | None
    authority_commit: str
    contract_tree_git_oid: str | None
    r2_publication_commit: str | None
    r2_module_tree_git_oid: str | None
    contract_version: str
    receipt_revision: int | None
    contracts_manifest_sha256: str
    contracts_manifest_file_sha256: str
    gate_policy_sha256: str
    gate_policy_file_sha256: str
    feature_registry_canonical_sha256: str | None
    feature_registry_sha256: str
    release_manifest_self_sha256: str | None
    release_manifest_physical_sha256: str | None
    release_checksums_physical_sha256: str | None
    final_audit_self_sha256: str | None
    final_audit_physical_sha256: str | None
    final_zip_sha256: str | None
    receipt_physical_sha256: str
    receipt_self_sha256: str | None
    action_policy_sha256: str
    action_policy_file_sha256: str
    action_policy_authority_self_sha256: str
    action_policy_authority_physical_sha256: str
    contract_verifier_report_self_sha256: str | None
    contract_verifier_report_physical_sha256: str | None
    approval: VerifiedApprovalBinding | None = field(repr=False, default=None)
    verifier_report: ContractVerifierEvidence | None = field(repr=False, default=None)

    def as_dict(self) -> dict[str, Any]:
        approval = self.approval.as_dict() if self.approval is not None else None
        return {
            "authority_mode": self.authority_mode,
            "compatibility_mode": self.compatibility_mode,
            "authority_tag": self.authority_tag,
            "authority_tag_object_oid": self.authority_tag_object_oid,
            "authority_commit": self.authority_commit,
            "contract_tree_git_oid": self.contract_tree_git_oid,
            "r2_publication_commit": self.r2_publication_commit,
            "r2_module_tree_git_oid": self.r2_module_tree_git_oid,
            "contract_version": self.contract_version,
            "receipt_revision": self.receipt_revision,
            "contracts_manifest_sha256": self.contracts_manifest_sha256,
            "contracts_manifest_file_sha256": self.contracts_manifest_file_sha256,
            "gate_policy_sha256": self.gate_policy_sha256,
            "gate_policy_file_sha256": self.gate_policy_file_sha256,
            "feature_registry_canonical_sha256": self.feature_registry_canonical_sha256,
            "feature_registry_sha256": self.feature_registry_sha256,
            "release_manifest_self_sha256": self.release_manifest_self_sha256,
            "release_manifest_physical_sha256": self.release_manifest_physical_sha256,
            "release_checksums_physical_sha256": self.release_checksums_physical_sha256,
            "final_audit_self_sha256": self.final_audit_self_sha256,
            "final_audit_physical_sha256": self.final_audit_physical_sha256,
            "final_zip_sha256": self.final_zip_sha256,
            "receipt_physical_sha256": self.receipt_physical_sha256,
            "receipt_self_sha256": self.receipt_self_sha256,
            "action_policy_sha256": self.action_policy_sha256,
            "action_policy_file_sha256": self.action_policy_file_sha256,
            "action_policy_authority_self_sha256": self.action_policy_authority_self_sha256,
            "action_policy_authority_physical_sha256": self.action_policy_authority_physical_sha256,
            "contract_verifier_report_self_sha256": self.contract_verifier_report_self_sha256,
            "contract_verifier_report_physical_sha256": self.contract_verifier_report_physical_sha256,
            "approval_binding": approval,
        }


def _require_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise AuthorityError(f"authority receipt missing {key}")
    return result


def _verify_self(value: Mapping[str, Any], label: str) -> str:
    declared = value.get("integrity", {}).get("self_sha256")
    if not isinstance(declared, str) or self_sha256(value) != declared:
        raise AuthorityError(f"{label} self hash mismatch")
    return declared


def _verify_action_policy(
    action_policy: Path, action_policy_authority: Path
) -> tuple[str, str, str, str]:
    policy = load_json(action_policy, require_object=True)
    policy_self = _verify_self(policy, "Global action policy")
    policy_physical = sha256_file(action_policy)
    if policy_self != ACTION_POLICY_SELF_SHA256 or policy_physical != ACTION_POLICY_PHYSICAL_SHA256:
        raise AuthorityError("Global action policy pin mismatch")

    sidecar = load_json(action_policy_authority, require_object=True)
    sidecar_self = _verify_self(sidecar, "Global action-policy authority")
    sidecar_physical = sha256_file(action_policy_authority)
    if sidecar_self != ACTION_POLICY_AUTHORITY_SELF_SHA256 or sidecar_physical != ACTION_POLICY_AUTHORITY_PHYSICAL_SHA256:
        raise AuthorityError("Global action-policy authority pin mismatch")
    if sidecar.get("schema_id") != "GlobalGateActionPolicyAuthorityV1" or sidecar.get("status") != "REVIEWED":
        raise AuthorityError("Global action-policy authority is not reviewed")
    if sidecar.get("approved_action_policy", {}).get("self_sha256") != policy_self:
        raise AuthorityError("Global action-policy authority approval mismatch")
    if sidecar.get("contracts_authority") != {
        "tag": AUTHORITY_TAG,
        "commit": AUTHORITY_COMMIT,
        "manifest_sha256": MANIFEST_SELF_SHA256,
        "gate_policy_artifact_sha256": GATE_POLICY_SELF_SHA256,
    }:
        raise AuthorityError("Global action-policy authority Contracts binding mismatch")
    return policy_self, policy_physical, sidecar_self, sidecar_physical


def _verify_common_contract_files(contracts_root: Path) -> dict[str, Any]:
    manifest_path = contracts_root / "manifest.json"
    gate_policy_path = contracts_root / "policies" / "gate_policy_v1.0.0.json"
    registry_path = contracts_root / "registries" / "feature_contract_v1.1.0.json"
    for path in (manifest_path, gate_policy_path, registry_path):
        if not path.is_file():
            raise AuthorityError(f"required authority artifact is missing: {path}")
    manifest = load_json(manifest_path, require_object=True)
    manifest_self = manifest.get("integrity", {}).get("manifest_sha256")
    gate = load_json(gate_policy_path, require_object=True)
    gate_self = _verify_self(gate, "GatePolicy")
    registry = load_json(registry_path, require_object=True)
    registry_self = sha256_bytes(canonical_bytes(registry))
    return {
        "manifest_self": manifest_self,
        "manifest_physical": sha256_file(manifest_path),
        "gate_self": gate_self,
        "gate_physical": sha256_file(gate_policy_path),
        "registry_self": registry_self,
        "registry_physical": sha256_file(registry_path),
    }


def _verify_expected(authority: AuthoritySet, expected: Mapping[str, Any] | None) -> None:
    if not expected:
        return
    actual = authority.as_dict()
    for key, value in expected.items():
        if key not in actual or actual[key] != value:
            raise AuthorityError(f"persisted authority mismatch: {key}")


def resolve_authority(
    receipt_path: Path,
    contracts_root: Path,
    *,
    action_policy_path: Path | None = None,
    action_policy_authority_path: Path | None = None,
    approval_root: Path | None = None,
    repository_root: Path | None = None,
    authority_mode: str = SYNTHETIC_LOCAL_CONFORMANCE,
    expected: Mapping[str, Any] | None = None,
    contract_verifier: PublicContractR2Verifier | None = None,
) -> AuthoritySet:
    receipt_path = receipt_path.resolve()
    contracts_root = contracts_root.resolve()
    repository_root = (repository_root or contracts_root.parent).resolve()
    if not receipt_path.is_file() or not contracts_root.is_dir():
        raise AuthorityError("authority receipt/contracts root is unavailable")
    action_policy = (
        action_policy_path.resolve()
        if action_policy_path is not None
        else repository_root / "global_validator" / "v1" / "policies" / "gate_action_selection_v1.0.0.json"
    )
    action_authority = (
        action_policy_authority_path.resolve()
        if action_policy_authority_path is not None
        else repository_root / "global_validator" / "v1" / "policies" / "gate_action_policy_authority_v1.0.0.json"
    )
    if not action_policy.is_file() or not action_authority.is_file():
        raise AuthorityError("Global action policy or authority sidecar is unavailable")
    policy_self, policy_file, sidecar_self, sidecar_file = _verify_action_policy(action_policy, action_authority)
    contract_files = _verify_common_contract_files(contracts_root)
    receipt = load_json(receipt_path, require_object=True)
    receipt_self = _verify_self(receipt, "authority receipt")
    receipt_physical = sha256_file(receipt_path)

    if authority_mode == CONTRACTS_R1_HISTORICAL_REPLAY:
        raise AuthorityError("R1 authority cannot be resolved for a new run")
    if authority_mode == CONTRACTS_R2_CURRENT:
        if approval_root is None:
            raise AuthorityError("current R2 authority requires detached AR-1 approval")
        verifier = contract_verifier or PublicContractR2Verifier(repository_root, contracts_root)
        verifier_evidence = verifier.verify(receipt_path)
        approval = verify_approval_binding(approval_root)
        expected_receipt = {
            "schema_id": "TerminologyContractsAuthorityReceiptV1",
            "schema_version": "1.0.0",
            "receipt_revision": 2,
            "authority_status": "SEALED",
            "publication_status": "PENDING_INDEPENDENT_REVIEW",
            "authority_tag": AUTHORITY_TAG,
            "authority_tag_object_oid": AUTHORITY_TAG_OBJECT_OID,
            "authority_commit": AUTHORITY_COMMIT,
            "contract_tree_git_oid": TAGGED_CONTRACT_TREE_OID,
            "contract_version": CONTRACT_VERSION,
            "manifest_sha256": MANIFEST_SELF_SHA256,
            "manifest_file_sha256": MANIFEST_PHYSICAL_SHA256,
            "gate_policy_self_sha256": GATE_POLICY_SELF_SHA256,
            "gate_policy_file_sha256": GATE_POLICY_PHYSICAL_SHA256,
            "feature_registry_canonical_sha256": FEATURE_REGISTRY_SELF_SHA256,
            "feature_registry_file_sha256": FEATURE_REGISTRY_PHYSICAL_SHA256,
            "final_release_zip_sha256": FINAL_ZIP_SHA256,
        }
        for key, value in expected_receipt.items():
            if receipt.get(key) != value:
                raise AuthorityError(f"R2 authority receipt mismatch: {key}")
        if receipt_self != RECEIPT_SELF_SHA256 or receipt_physical != RECEIPT_PHYSICAL_SHA256:
            raise AuthorityError("R2 authority receipt exact hash mismatch")
        if approval.payload["receipt_canonical_self_sha256"] != receipt_self or approval.payload["receipt_physical_sha256"] != receipt_physical:
            raise AuthorityError("AR-1 approval does not bind the active R2 receipt")
        if approval.payload["authority_commit"] != R2_PUBLICATION_COMMIT or approval.payload["authority_module_tree_git_oid"] != R2_MODULE_TREE_OID:
            raise AuthorityError("AR-1 approval R2 publication binding mismatch")
        release_root = contracts_root / "release" / "v1.1.0-final"
        release_manifest = load_json(release_root / "release_manifest.json", require_object=True)
        final_audit = load_json(release_root / "final_release_audit.json", require_object=True)
        release_values = {
            "release_manifest_self": _verify_self(release_manifest, "R2 release manifest"),
            "release_manifest_physical": sha256_file(release_root / "release_manifest.json"),
            "release_checksums_physical": sha256_file(release_root / "CHECKSUMS.sha256"),
            "final_audit_self": _verify_self(final_audit, "R2 final audit"),
            "final_audit_physical": sha256_file(release_root / "final_release_audit.json"),
            "final_zip": sha256_file(release_root / "terminology_contracts_v1_1_0_final.zip"),
        }
        if release_values != {
            "release_manifest_self": RELEASE_MANIFEST_SELF_SHA256,
            "release_manifest_physical": RELEASE_MANIFEST_PHYSICAL_SHA256,
            "release_checksums_physical": RELEASE_CHECKSUMS_PHYSICAL_SHA256,
            "final_audit_self": FINAL_AUDIT_SELF_SHA256,
            "final_audit_physical": FINAL_AUDIT_PHYSICAL_SHA256,
            "final_zip": FINAL_ZIP_SHA256,
        }:
            raise AuthorityError("R2 release publication binding mismatch")
        authority = AuthoritySet(
            receipt_path=receipt_path,
            contracts_root=contracts_root,
            action_policy_path=action_policy,
            action_policy_authority_path=action_authority,
            authority_mode=CONTRACTS_R2_CURRENT,
            compatibility_mode="NONE",
            authority_tag=AUTHORITY_TAG,
            authority_tag_object_oid=AUTHORITY_TAG_OBJECT_OID,
            authority_commit=AUTHORITY_COMMIT,
            contract_tree_git_oid=TAGGED_CONTRACT_TREE_OID,
            r2_publication_commit=R2_PUBLICATION_COMMIT,
            r2_module_tree_git_oid=R2_MODULE_TREE_OID,
            contract_version=CONTRACT_VERSION,
            receipt_revision=2,
            contracts_manifest_sha256=contract_files["manifest_self"],
            contracts_manifest_file_sha256=contract_files["manifest_physical"],
            gate_policy_sha256=contract_files["gate_self"],
            gate_policy_file_sha256=contract_files["gate_physical"],
            feature_registry_canonical_sha256=contract_files["registry_self"],
            feature_registry_sha256=contract_files["registry_physical"],
            release_manifest_self_sha256=release_values["release_manifest_self"],
            release_manifest_physical_sha256=release_values["release_manifest_physical"],
            release_checksums_physical_sha256=release_values["release_checksums_physical"],
            final_audit_self_sha256=release_values["final_audit_self"],
            final_audit_physical_sha256=release_values["final_audit_physical"],
            final_zip_sha256=release_values["final_zip"],
            receipt_physical_sha256=receipt_physical,
            receipt_self_sha256=receipt_self,
            action_policy_sha256=policy_self,
            action_policy_file_sha256=policy_file,
            action_policy_authority_self_sha256=sidecar_self,
            action_policy_authority_physical_sha256=sidecar_file,
            contract_verifier_report_self_sha256=verifier_evidence.self_sha256,
            contract_verifier_report_physical_sha256=verifier_evidence.physical_sha256,
            approval=approval,
            verifier_report=verifier_evidence,
        )
    elif authority_mode == SYNTHETIC_LOCAL_CONFORMANCE:
        authority_tag = _require_string(receipt, "authority_tag")
        authority_commit = _require_string(receipt, "authority_commit")
        contract_version = _require_string(receipt, "contract_version")
        declared_manifest = receipt.get("manifest_sha256", receipt.get("contracts_manifest_sha256"))
        if declared_manifest not in (None, contract_files["manifest_self"]):
            raise AuthorityError("synthetic receipt Contracts manifest mismatch")
        declared_action = receipt.get("action_policy_sha256", receipt.get("global_action_policy_sha256"))
        if declared_action not in (None, policy_self):
            raise AuthorityError("synthetic receipt action policy mismatch")
        authority = AuthoritySet(
            receipt_path=receipt_path,
            contracts_root=contracts_root,
            action_policy_path=action_policy,
            action_policy_authority_path=action_authority,
            authority_mode=SYNTHETIC_LOCAL_CONFORMANCE,
            compatibility_mode=SYNTHETIC_LOCAL_CONFORMANCE,
            authority_tag=authority_tag,
            authority_tag_object_oid=None,
            authority_commit=authority_commit,
            contract_tree_git_oid=None,
            r2_publication_commit=None,
            r2_module_tree_git_oid=None,
            contract_version=contract_version,
            receipt_revision=None,
            contracts_manifest_sha256=contract_files["manifest_self"],
            contracts_manifest_file_sha256=contract_files["manifest_physical"],
            gate_policy_sha256=contract_files["gate_self"],
            gate_policy_file_sha256=contract_files["gate_physical"],
            feature_registry_canonical_sha256=contract_files["registry_self"],
            feature_registry_sha256=contract_files["registry_physical"],
            release_manifest_self_sha256=None,
            release_manifest_physical_sha256=None,
            release_checksums_physical_sha256=None,
            final_audit_self_sha256=None,
            final_audit_physical_sha256=None,
            final_zip_sha256=None,
            receipt_physical_sha256=receipt_physical,
            receipt_self_sha256=receipt_self,
            action_policy_sha256=policy_self,
            action_policy_file_sha256=policy_file,
            action_policy_authority_self_sha256=sidecar_self,
            action_policy_authority_physical_sha256=sidecar_file,
            contract_verifier_report_self_sha256=None,
            contract_verifier_report_physical_sha256=None,
        )
    else:
        raise AuthorityError(f"unsupported authority mode: {authority_mode}")
    _verify_expected(authority, expected)
    return authority


def verify_historical_r1_binding(receipt_path: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    if expected.get("authority_mode") != CONTRACTS_R1_HISTORICAL_REPLAY or expected.get("compatibility_mode") != CONTRACTS_R1_HISTORICAL_REPLAY:
        raise AuthorityError("historical R1 replay mode is not explicitly sealed")
    receipt_path = receipt_path.resolve()
    if sha256_file(receipt_path) != R1_RECEIPT_PHYSICAL_SHA256:
        raise AuthorityError("historical R1 receipt physical hash mismatch")
    receipt = load_json(receipt_path, require_object=True)
    if _verify_self(receipt, "historical R1 receipt") != R1_RECEIPT_SELF_SHA256:
        raise AuthorityError("historical R1 receipt self hash mismatch")
    required = {
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_version": CONTRACT_VERSION,
        "manifest_sha256": MANIFEST_SELF_SHA256,
        "manifest_file_sha256": MANIFEST_PHYSICAL_SHA256,
        "gate_policy_artifact_sha256": GATE_POLICY_SELF_SHA256,
        "gate_policy_file_sha256": GATE_POLICY_PHYSICAL_SHA256,
        "feature_contract_file_sha256": FEATURE_REGISTRY_PHYSICAL_SHA256,
        "release_zip_sha256": FINAL_ZIP_SHA256,
    }
    for key, value in required.items():
        if receipt.get(key) != value:
            raise AuthorityError(f"historical R1 receipt mismatch: {key}")
    if expected.get("receipt_self_sha256") != R1_RECEIPT_SELF_SHA256 or expected.get("receipt_physical_sha256") != R1_RECEIPT_PHYSICAL_SHA256:
        raise AuthorityError("historical R1 run-spec receipt pin mismatch")
    return {
        "authority_mode": CONTRACTS_R1_HISTORICAL_REPLAY,
        "compatibility_mode": CONTRACTS_R1_HISTORICAL_REPLAY,
        "receipt_self_sha256": R1_RECEIPT_SELF_SHA256,
        "receipt_physical_sha256": R1_RECEIPT_PHYSICAL_SHA256,
    }
