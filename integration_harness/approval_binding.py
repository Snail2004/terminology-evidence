"""Verification of the detached AR-1 approval evidence publication."""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import AuthorityError
from .hashing import self_sha256, sha256_bytes, sha256_file
from .jsonio import canonical_bytes, load_json
from .paths import safe_relative_path


APPROVAL_BINDING_SELF_SHA256 = "ab7acbccfbdf64b74071133d4e049a06cbafc66c989f9b9f7ce52a08caa720b2"
APPROVAL_BINDING_PHYSICAL_SHA256 = "3ad39870e4e95c51ac88ee6a3d451504d41ba26d3bf5dc6569d25a585a7147a5"
APPROVAL_CHECKSUMS_PHYSICAL_SHA256 = "fe0268bc6be8209a2cc90b81833443e4c4f081a4c4e465edf2652e1a228bed43"
APPROVAL_ARTIFACT_SELF_SHA256 = "8ccb232602d73c13b20e6954f7a4982371e5c57f1e25f7caec3898c2ce4bcb78"
APPROVAL_ARTIFACT_PHYSICAL_SHA256 = "7d232474a7b1beb277d6f50fcf09680a8861dab79a25becdd3ea9029795b0cd8"

_BINDING_NAME = "approval_binding_v1.json"
_CHECKSUMS_NAME = "CHECKSUMS.sha256"
_EVIDENCE_NAMES = (
    "Hau_Review_Contract_Steward_R2_Authority_Promotion.md",
    "Independent_Review_Contract_Steward_Authority_Maintenance_V1_2_R2.md",
    "contracts_v1_1_0_authority_receipt_r2_independent_approval.json",
    "contracts_v1_1_authority_maintenance_v1_2_r2_independent_audit.json",
)
_MEMBER_NAMES = frozenset((_BINDING_NAME, _CHECKSUMS_NAME, *_EVIDENCE_NAMES))
_BINDING_FIELDS = frozenset(
    {
        "schema_id",
        "binding_version",
        "approval_status",
        "issued_at",
        "publisher_role",
        "authority_tag",
        "authority_commit",
        "authority_module_tree_git_oid",
        "receipt_revision",
        "receipt_canonical_self_sha256",
        "receipt_physical_sha256",
        "final_contracts_zip_sha256",
        "approval_artifact_canonical_self_sha256",
        "approval_artifact_physical_sha256",
        "review_report_physical_sha256",
        "independent_audit_physical_sha256",
        "promotion_notes_physical_sha256",
        "evidence_inventory",
        "previous_binding_sha256",
        "integrity",
    }
)


@dataclass(frozen=True)
class ApprovalEvidenceFile:
    path: Path
    relative_path: str
    physical_sha256: str
    size_bytes: int


@dataclass(frozen=True)
class VerifiedApprovalBinding:
    root: Path
    binding_path: Path
    checksums_path: Path
    payload: dict[str, Any]
    binding_self_sha256: str
    binding_physical_sha256: str
    checksums_physical_sha256: str
    approval_artifact_self_sha256: str
    approval_artifact_physical_sha256: str
    evidence_inventory_sha256: str
    files: tuple[ApprovalEvidenceFile, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_status": self.payload["approval_status"],
            "binding_self_sha256": self.binding_self_sha256,
            "binding_physical_sha256": self.binding_physical_sha256,
            "checksums_physical_sha256": self.checksums_physical_sha256,
            "approval_artifact_self_sha256": self.approval_artifact_self_sha256,
            "approval_artifact_physical_sha256": self.approval_artifact_physical_sha256,
            "evidence_inventory_sha256": self.evidence_inventory_sha256,
            "evidence_count": len(self.payload["evidence_inventory"]),
        }


def _reject_reparse(path: Path) -> None:
    try:
        details = os.lstat(path)
    except OSError as exc:
        raise AuthorityError(f"cannot stat approval evidence: {path}") from exc
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(details.st_mode) or attributes & reparse_flag:
        raise AuthorityError(f"reparse path is forbidden in approval evidence: {path}")


def _parse_checksums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise AuthorityError("cannot read AR-1 CHECKSUMS") from exc
    if len(lines) != 5:
        raise AuthorityError("AR-1 CHECKSUMS must contain exactly five entries")
    result: dict[str, str] = {}
    ordered_paths: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", line)
        if match is None:
            raise AuthorityError("malformed AR-1 CHECKSUMS entry")
        digest, value = match.groups()
        safe = safe_relative_path(value)
        if len(safe.parts) != 1 or value in result:
            raise AuthorityError("AR-1 CHECKSUMS path is duplicate or noncanonical")
        result[value] = digest
        ordered_paths.append(value)
    if ordered_paths != sorted(ordered_paths):
        raise AuthorityError("AR-1 CHECKSUMS entries are not path-sorted")
    return result


def verify_approval_binding(root: Path) -> VerifiedApprovalBinding:
    root = root.absolute()
    _reject_reparse(root)
    root = root.resolve()
    if not root.is_dir():
        raise AuthorityError("detached AR-1 approval root is unavailable")
    members = list(root.iterdir())
    names = [member.name for member in members]
    if len(members) != 6 or set(names) != _MEMBER_NAMES:
        raise AuthorityError("detached AR-1 approval root must contain exactly six members")
    if len({name.casefold() for name in names}) != len(names):
        raise AuthorityError("case-confusable AR-1 approval member")
    for member in members:
        _reject_reparse(member)
        if not member.is_file():
            raise AuthorityError("AR-1 approval member is not a regular file")

    binding_path = root / _BINDING_NAME
    checksums_path = root / _CHECKSUMS_NAME
    if sha256_file(binding_path) != APPROVAL_BINDING_PHYSICAL_SHA256:
        raise AuthorityError("AR-1 approval binding physical hash mismatch")
    if sha256_file(checksums_path) != APPROVAL_CHECKSUMS_PHYSICAL_SHA256:
        raise AuthorityError("AR-1 CHECKSUMS physical hash mismatch")
    checksums = _parse_checksums(checksums_path)
    if set(checksums) != _MEMBER_NAMES - {_CHECKSUMS_NAME}:
        raise AuthorityError("AR-1 CHECKSUMS inventory mismatch")
    for name, digest in checksums.items():
        if sha256_file(root / name) != digest:
            raise AuthorityError(f"AR-1 approval evidence hash mismatch: {name}")

    binding = load_json(binding_path, require_object=True)
    if set(binding) != _BINDING_FIELDS:
        raise AuthorityError("AR-1 approval binding field set mismatch")
    expected = {
        "schema_id": "TerminologyContractsApprovalBindingV1",
        "binding_version": "1.0.0",
        "approval_status": "ACCEPTED_FOR_AUTHORITY_PROMOTION",
        "publisher_role": "MAIN_MAINTAINER_REVIEW_GOVERNANCE",
        "authority_tag": "contracts-v1.1.0",
        "authority_commit": "282409c470049760904fa16de4c67d711b5fcd00",
        "authority_module_tree_git_oid": "938bca1f9c60596ef9403a43f0355476ad42afef",
        "receipt_revision": 2,
        "receipt_canonical_self_sha256": "a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618",
        "receipt_physical_sha256": "acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79",
        "final_contracts_zip_sha256": "2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471",
        "approval_artifact_canonical_self_sha256": APPROVAL_ARTIFACT_SELF_SHA256,
        "approval_artifact_physical_sha256": APPROVAL_ARTIFACT_PHYSICAL_SHA256,
        "review_report_physical_sha256": "1865493ff297b10a3af188865398a02d02f580f16b3fa6bc4f5ba8fb26179dfe",
        "independent_audit_physical_sha256": "254e7752dc07a0d56d330f055349e12a0ffefb90ce0bdfa8129136552a0fef8f",
        "promotion_notes_physical_sha256": "859bf5fe6e1e1c7aba521ea1360eb03ae079c31977716e02e5f7e3ce4a1c3249",
        "previous_binding_sha256": None,
    }
    for key, value in expected.items():
        if binding.get(key) != value:
            raise AuthorityError(f"AR-1 approval binding mismatch: {key}")
    declared_self = binding.get("integrity", {}).get("self_sha256")
    if declared_self != APPROVAL_BINDING_SELF_SHA256 or self_sha256(binding) != declared_self:
        raise AuthorityError("AR-1 approval binding self hash mismatch")

    inventory = binding.get("evidence_inventory")
    if not isinstance(inventory, list) or len(inventory) != 4:
        raise AuthorityError("AR-1 evidence inventory must contain four records")
    inventory_paths = [row.get("path") for row in inventory if isinstance(row, dict)]
    if inventory_paths != list(_EVIDENCE_NAMES):
        raise AuthorityError("AR-1 evidence inventory ordering/path mismatch")
    files: list[ApprovalEvidenceFile] = []
    for row in inventory:
        path = root / row["path"]
        digest = sha256_file(path)
        size = path.stat().st_size
        if row.get("physical_sha256") != digest or row.get("size_bytes") != size:
            raise AuthorityError(f"AR-1 evidence inventory drift: {row['path']}")
        if "canonical_self_sha256" in row:
            value = load_json(path, require_object=True)
            if row["canonical_self_sha256"] != self_sha256(value):
                raise AuthorityError("AR-1 approval artifact self hash mismatch")
        files.append(ApprovalEvidenceFile(path, row["path"], digest, size))
    approval_value = load_json(root / _EVIDENCE_NAMES[2], require_object=True)
    if self_sha256(approval_value) != APPROVAL_ARTIFACT_SELF_SHA256:
        raise AuthorityError("AR-1 approval artifact canonical hash mismatch")
    all_files = (
        ApprovalEvidenceFile(binding_path, _BINDING_NAME, sha256_file(binding_path), binding_path.stat().st_size),
        ApprovalEvidenceFile(checksums_path, _CHECKSUMS_NAME, sha256_file(checksums_path), checksums_path.stat().st_size),
        *files,
    )
    return VerifiedApprovalBinding(
        root=root,
        binding_path=binding_path,
        checksums_path=checksums_path,
        payload=binding,
        binding_self_sha256=declared_self,
        binding_physical_sha256=sha256_file(binding_path),
        checksums_physical_sha256=sha256_file(checksums_path),
        approval_artifact_self_sha256=APPROVAL_ARTIFACT_SELF_SHA256,
        approval_artifact_physical_sha256=APPROVAL_ARTIFACT_PHYSICAL_SHA256,
        evidence_inventory_sha256=sha256_bytes(canonical_bytes(inventory)),
        files=tuple(all_files),
    )
