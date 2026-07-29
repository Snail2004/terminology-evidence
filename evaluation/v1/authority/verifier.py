"""Verification of AR-2 external authority artifacts against a frozen profile."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from ..constants import AUTHORITY_PROFILE_SCHEMA_ID, AUTHORITY_PROFILE_SCHEMA_VERSION
from ..jsonio import read_json, sha256_file, sha256_value


class AuthorityProfileError(ValueError):
    """Raised when an authority profile or supplied authority artifact drifts."""


PROFILE_FILE = "allowed_authority_profile_v1.json"
VERIFIED_BUNDLE_SCHEMA_ID = "EvaluationVerifiedAuthorityBundleV1"
VERIFIED_BUNDLE_SCHEMA_VERSION = "1.0.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID = re.compile(r"^[0-9a-f]{40}$")
_ARTIFACT_KEYS = {
    "contracts_receipt",
    "contracts_approval_binding",
    "contracts_checksums",
    "global_authority_report",
    "global_action_policy",
    "dataset_manifest",
    "dataset_split_assignments",
}


def profile_path() -> Path:
    return Path(__file__).with_name(PROFILE_FILE)


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    integrity = dict(result.get("integrity", {}))
    integrity.pop("self_sha256", None)
    result["integrity"] = integrity
    return result


def _require_keys(value: Any, expected: set[str], field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        actual = sorted(value) if isinstance(value, Mapping) else type(value).__name__
        raise AuthorityProfileError(f"{field} keys mismatch: {actual}")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise AuthorityProfileError(f"{field} is not a lowercase SHA256")
    return value


def _require_oid(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _GIT_OID.fullmatch(value):
        raise AuthorityProfileError(f"{field} is not a full lowercase Git OID")
    return value


def _verify_self_hash(value: Mapping[str, Any], field: str) -> str:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {"self_sha256"}:
        raise AuthorityProfileError(f"{field} integrity is invalid")
    declared = _require_sha256(integrity.get("self_sha256"), f"{field}.integrity.self_sha256")
    actual = sha256_value(_without_self_hash(value))
    if declared != actual:
        raise AuthorityProfileError(f"{field} self hash mismatch")
    return actual


def load_allowed_authority_profile(path: Path | None = None) -> dict[str, Any]:
    value = read_json(path or profile_path())
    _require_keys(
        value,
        {"schema_id", "schema_version", "profile_id", "status", "contracts", "global", "dataset", "evaluation_registries", "integrity"},
        "profile",
    )
    if value["schema_id"] != AUTHORITY_PROFILE_SCHEMA_ID or value["schema_version"] != AUTHORITY_PROFILE_SCHEMA_VERSION:
        raise AuthorityProfileError("unsupported authority profile schema")
    if value["profile_id"] != "evaluation-ar2-authority-profile-v1" or value["status"] != "ACTIVE":
        raise AuthorityProfileError("authority profile is not the active AR-2 profile")
    contracts = _require_keys(
        value["contracts"],
        {"authority_tag", "authority_publication_commit", "authority_module_tree_git_oid", "contract_tree_git_oid", "receipt", "detached_approval"},
        "profile.contracts",
    )
    _require_oid(contracts["authority_publication_commit"], "profile.contracts.authority_publication_commit")
    _require_oid(contracts["authority_module_tree_git_oid"], "profile.contracts.authority_module_tree_git_oid")
    _require_oid(contracts["contract_tree_git_oid"], "profile.contracts.contract_tree_git_oid")
    receipt = _require_keys(contracts["receipt"], {"schema_id", "receipt_revision", "canonical_self_sha256", "physical_sha256"}, "profile.contracts.receipt")
    _require_sha256(receipt["canonical_self_sha256"], "profile.contracts.receipt.canonical_self_sha256")
    _require_sha256(receipt["physical_sha256"], "profile.contracts.receipt.physical_sha256")
    approval = _require_keys(
        contracts["detached_approval"],
        {"schema_id", "binding_version", "approval_status", "canonical_self_sha256", "physical_sha256", "checksums_physical_sha256"},
        "profile.contracts.detached_approval",
    )
    for key in ("canonical_self_sha256", "physical_sha256", "checksums_physical_sha256"):
        _require_sha256(approval[key], f"profile.contracts.detached_approval.{key}")
    global_profile = _require_keys(value["global"], {"authority_report", "action_policy"}, "profile.global")
    authority_report = _require_keys(
        global_profile["authority_report"],
        {"schema_id", "schema_version", "status", "source_commit", "canonical_self_sha256", "physical_sha256", "global_test_identity_sha256", "contracts_test_identity_sha256"},
        "profile.global.authority_report",
    )
    _require_oid(authority_report["source_commit"], "profile.global.authority_report.source_commit")
    for key in ("canonical_self_sha256", "physical_sha256", "global_test_identity_sha256", "contracts_test_identity_sha256"):
        _require_sha256(authority_report[key], f"profile.global.authority_report.{key}")
    action_policy = _require_keys(
        global_profile["action_policy"],
        {"schema_id", "schema_version", "status", "action_policy_authority_id", "action_policy_authority_sha256", "action_policy_id", "action_policy_version", "action_policy_sha256", "gate_policy_artifact_sha256", "canonical_self_sha256", "physical_sha256"},
        "profile.global.action_policy",
    )
    for key in ("action_policy_authority_sha256", "action_policy_sha256", "gate_policy_artifact_sha256", "canonical_self_sha256", "physical_sha256"):
        _require_sha256(action_policy[key], f"profile.global.action_policy.{key}")
    dataset = _require_keys(
        value["dataset"],
        {"manifest_schema_id", "manifest_schema_version", "manifest_status", "manifest_declared_sha256", "manifest_physical_sha256", "split_assignment_schema_id", "split_assignment_schema_version", "split_policy_id", "split_assignments_physical_sha256", "target_counts"},
        "profile.dataset",
    )
    for key in ("manifest_declared_sha256", "manifest_physical_sha256", "split_assignments_physical_sha256"):
        _require_sha256(dataset[key], f"profile.dataset.{key}")
    _require_keys(dataset["target_counts"], {"development", "validation", "test"}, "profile.dataset.target_counts")
    registries = value["evaluation_registries"]
    if not isinstance(registries, Mapping) or not registries:
        raise AuthorityProfileError("profile evaluation_registries is empty")
    for name, digest in registries.items():
        if not isinstance(name, str) or not name.endswith("_v1.json"):
            raise AuthorityProfileError("profile registry name is invalid")
        _require_sha256(digest, f"profile.evaluation_registries.{name}")
    _verify_self_hash(value, "profile")
    return dict(value)


def _verify_physical(path: Path, expected: str, field: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise AuthorityProfileError(f"{field} is missing or symlinked")
    if sha256_file(path) != expected:
        raise AuthorityProfileError(f"{field} physical hash mismatch")


def _match_fields(actual: Mapping[str, Any], expected: Mapping[str, Any], fields: tuple[str, ...], field: str) -> None:
    for name in fields:
        if actual.get(name) != expected.get(name):
            raise AuthorityProfileError(f"{field}.{name} mismatch")


def verify_external_authorities(
    artifact_paths: Mapping[str, Path],
    *,
    registry_root: Path,
    allowed_profile_path: Path | None = None,
) -> dict[str, Any]:
    """Verify exact external authority bytes without opening validation/test rows."""
    if set(artifact_paths) != _ARTIFACT_KEYS:
        raise AuthorityProfileError(f"authority artifact set mismatch: {sorted(artifact_paths)}")
    profile = load_allowed_authority_profile(allowed_profile_path)
    contracts = profile["contracts"]
    receipt_profile = contracts["receipt"]
    approval_profile = contracts["detached_approval"]
    global_profile = profile["global"]
    dataset_profile = profile["dataset"]

    _verify_physical(artifact_paths["contracts_receipt"], receipt_profile["physical_sha256"], "contracts_receipt")
    receipt = read_json(artifact_paths["contracts_receipt"])
    _verify_self_hash(receipt, "contracts_receipt")
    _match_fields(receipt, {"schema_id": receipt_profile["schema_id"], "receipt_revision": receipt_profile["receipt_revision"], "authority_tag": contracts["authority_tag"], "contract_tree_git_oid": contracts["contract_tree_git_oid"]}, ("schema_id", "receipt_revision", "authority_tag", "contract_tree_git_oid"), "contracts_receipt")
    if receipt["integrity"]["self_sha256"] != receipt_profile["canonical_self_sha256"]:
        raise AuthorityProfileError("contracts receipt canonical hash mismatch")

    _verify_physical(artifact_paths["contracts_approval_binding"], approval_profile["physical_sha256"], "contracts_approval_binding")
    approval = read_json(artifact_paths["contracts_approval_binding"])
    _verify_self_hash(approval, "contracts_approval_binding")
    _match_fields(approval, {"schema_id": approval_profile["schema_id"], "binding_version": approval_profile["binding_version"], "approval_status": approval_profile["approval_status"], "authority_tag": contracts["authority_tag"], "authority_commit": contracts["authority_publication_commit"], "authority_module_tree_git_oid": contracts["authority_module_tree_git_oid"], "receipt_revision": receipt_profile["receipt_revision"], "receipt_canonical_self_sha256": receipt_profile["canonical_self_sha256"], "receipt_physical_sha256": receipt_profile["physical_sha256"]}, ("schema_id", "binding_version", "approval_status", "authority_tag", "authority_commit", "authority_module_tree_git_oid", "receipt_revision", "receipt_canonical_self_sha256", "receipt_physical_sha256"), "contracts_approval_binding")
    if approval["integrity"]["self_sha256"] != approval_profile["canonical_self_sha256"]:
        raise AuthorityProfileError("detached approval canonical hash mismatch")
    _verify_physical(artifact_paths["contracts_checksums"], approval_profile["checksums_physical_sha256"], "contracts_checksums")

    report_profile = global_profile["authority_report"]
    _verify_physical(artifact_paths["global_authority_report"], report_profile["physical_sha256"], "global_authority_report")
    global_report = read_json(artifact_paths["global_authority_report"])
    _verify_self_hash(global_report, "global_authority_report")
    _match_fields(global_report, report_profile, ("schema_id", "schema_version", "status", "source_commit"), "global_authority_report")
    if global_report["integrity"]["self_sha256"] != report_profile["canonical_self_sha256"] or global_report.get("warnings") != []:
        raise AuthorityProfileError("Global authority report is not exact green authority")
    test_evidence = global_report.get("test_evidence", {})
    if test_evidence.get("global", {}).get("identity_sha256") != report_profile["global_test_identity_sha256"] or test_evidence.get("contracts", {}).get("identity_sha256") != report_profile["contracts_test_identity_sha256"]:
        raise AuthorityProfileError("Global release test identity mismatch")

    policy_profile = global_profile["action_policy"]
    _verify_physical(artifact_paths["global_action_policy"], policy_profile["physical_sha256"], "global_action_policy")
    action_policy = read_json(artifact_paths["global_action_policy"])
    _verify_self_hash(action_policy, "global_action_policy")
    _match_fields(action_policy, policy_profile, ("schema_id", "schema_version", "status", "action_policy_authority_id", "action_policy_authority_sha256", "action_policy_id", "action_policy_version", "action_policy_sha256", "gate_policy_artifact_sha256"), "global_action_policy")
    if action_policy["integrity"]["self_sha256"] != policy_profile["canonical_self_sha256"]:
        raise AuthorityProfileError("Global action policy canonical hash mismatch")

    _verify_physical(artifact_paths["dataset_manifest"], dataset_profile["manifest_physical_sha256"], "dataset_manifest")
    dataset_manifest = read_json(artifact_paths["dataset_manifest"])
    _match_fields(dataset_manifest, {"schema_id": dataset_profile["manifest_schema_id"], "schema_version": dataset_profile["manifest_schema_version"], "status": dataset_profile["manifest_status"], "manifest_sha256": dataset_profile["manifest_declared_sha256"]}, ("schema_id", "schema_version", "status", "manifest_sha256"), "dataset_manifest")
    split_file = dataset_manifest.get("files", {}).get("split_assignments.jsonl", {})
    if split_file.get("sha256") != dataset_profile["split_assignments_physical_sha256"] or dataset_manifest.get("split_policy", {}).get("policy_id") != dataset_profile["split_policy_id"] or dataset_manifest.get("split_policy", {}).get("target_counts") != dataset_profile["target_counts"]:
        raise AuthorityProfileError("Dataset split-manifest binding mismatch")
    _verify_physical(artifact_paths["dataset_split_assignments"], dataset_profile["split_assignments_physical_sha256"], "dataset_split_assignments")

    registry_hashes: dict[str, str] = {}
    for name, expected in profile["evaluation_registries"].items():
        path = registry_root / name
        _verify_physical(path, expected, f"evaluation_registry.{name}")
        registry_hashes[name] = expected

    evidence: dict[str, Any] = {
        "schema_id": VERIFIED_BUNDLE_SCHEMA_ID,
        "schema_version": VERIFIED_BUNDLE_SCHEMA_VERSION,
        "status": "PASS",
        "profile_id": profile["profile_id"],
        "profile_self_sha256": profile["integrity"]["self_sha256"],
        "contracts": {
            "authority_tag": contracts["authority_tag"],
            "authority_module_tree_git_oid": contracts["authority_module_tree_git_oid"],
            "receipt_revision": receipt_profile["receipt_revision"],
            "receipt_canonical_self_sha256": receipt_profile["canonical_self_sha256"],
            "receipt_physical_sha256": receipt_profile["physical_sha256"],
            "approval_binding_self_sha256": approval_profile["canonical_self_sha256"],
            "approval_binding_physical_sha256": approval_profile["physical_sha256"],
        },
        "global": {
            "source_commit": report_profile["source_commit"],
            "authority_report_self_sha256": report_profile["canonical_self_sha256"],
            "action_policy_authority_sha256": policy_profile["action_policy_authority_sha256"],
            "action_policy_sha256": policy_profile["action_policy_sha256"],
        },
        "dataset": {
            "manifest_schema_id": dataset_profile["manifest_schema_id"],
            "manifest_declared_sha256": dataset_profile["manifest_declared_sha256"],
            "manifest_physical_sha256": dataset_profile["manifest_physical_sha256"],
            "split_policy_id": dataset_profile["split_policy_id"],
            "split_assignments_physical_sha256": dataset_profile["split_assignments_physical_sha256"],
        },
        "evaluation_registries": dict(sorted(registry_hashes.items())),
        "integrity": {"self_sha256": ""},
    }
    evidence["integrity"]["self_sha256"] = sha256_value(_without_self_hash(evidence))
    return evidence


def verify_authority_evidence_object(value: Mapping[str, Any]) -> str:
    expected_keys = {"schema_id", "schema_version", "status", "profile_id", "profile_self_sha256", "contracts", "global", "dataset", "evaluation_registries", "integrity"}
    _require_keys(value, expected_keys, "verified authority evidence")
    if value.get("schema_id") != VERIFIED_BUNDLE_SCHEMA_ID or value.get("schema_version") != VERIFIED_BUNDLE_SCHEMA_VERSION or value.get("status") != "PASS":
        raise AuthorityProfileError("verified authority evidence is not PASS V1")
    profile = load_allowed_authority_profile()
    if value.get("profile_id") != profile["profile_id"] or value.get("profile_self_sha256") != profile["integrity"]["self_sha256"]:
        raise AuthorityProfileError("verified authority evidence profile mismatch")
    expected = {
        "contracts": {
            "authority_tag": profile["contracts"]["authority_tag"],
            "authority_module_tree_git_oid": profile["contracts"]["authority_module_tree_git_oid"],
            "receipt_revision": profile["contracts"]["receipt"]["receipt_revision"],
            "receipt_canonical_self_sha256": profile["contracts"]["receipt"]["canonical_self_sha256"],
            "receipt_physical_sha256": profile["contracts"]["receipt"]["physical_sha256"],
            "approval_binding_self_sha256": profile["contracts"]["detached_approval"]["canonical_self_sha256"],
            "approval_binding_physical_sha256": profile["contracts"]["detached_approval"]["physical_sha256"],
        },
        "global": {
            "source_commit": profile["global"]["authority_report"]["source_commit"],
            "authority_report_self_sha256": profile["global"]["authority_report"]["canonical_self_sha256"],
            "action_policy_authority_sha256": profile["global"]["action_policy"]["action_policy_authority_sha256"],
            "action_policy_sha256": profile["global"]["action_policy"]["action_policy_sha256"],
        },
        "dataset": {
            "manifest_schema_id": profile["dataset"]["manifest_schema_id"],
            "manifest_declared_sha256": profile["dataset"]["manifest_declared_sha256"],
            "manifest_physical_sha256": profile["dataset"]["manifest_physical_sha256"],
            "split_policy_id": profile["dataset"]["split_policy_id"],
            "split_assignments_physical_sha256": profile["dataset"]["split_assignments_physical_sha256"],
        },
        "evaluation_registries": dict(sorted(profile["evaluation_registries"].items())),
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise AuthorityProfileError(f"verified authority evidence {key} mismatch")
    return _verify_self_hash(value, "verified authority evidence")
