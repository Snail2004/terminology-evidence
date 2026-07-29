"""Public subprocess boundary for the reviewed Contracts R2 verifier."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .errors import AuthorityError
from .hashing import self_sha256, sha256_bytes
from .jsonio import load_json, loads_strict
from .paths import safe_relative_path


REPORT_SCHEMA_ID = "TerminologyContractsAuthorityVerificationReportV1"
REPORT_SELF_SHA256 = "8d11809faf9236f834e3238a3e38b02f2b1a6377b148648e7d0e53ee669218cc"
REPORT_PHYSICAL_SHA256 = "fae5375ebc5dc0af9269ec01692c707c05e9664bdf02347ff0d8a7a25b0922b3"
RECEIPT_SELF_SHA256 = "a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618"
RECEIPT_PHYSICAL_SHA256 = "acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79"
FINAL_ZIP_SHA256 = "2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471"
MANIFEST_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
GATE_POLICY_SELF_SHA256 = "9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2"
FEATURE_REGISTRY_CANONICAL_SHA256 = "057f47d68097286f04f0870d2e78944e59c07b0cb4e9db7f9d8675c9f2c8b182"
R2_PUBLICATION_COMMIT = "282409c470049760904fa16de4c67d711b5fcd00"
R2_MODULE_TREE_GIT_OID = "938bca1f9c60596ef9403a43f0355476ad42afef"
R2_MODULE_FILE_COUNT = 227
CONTRACTS_RELATIVE_ROOT = "terminology_contracts_v1"

PRODUCTION_CANONICAL = "PRODUCTION_CANONICAL"
NON_PRODUCTION_CONFORMANCE = "NON_PRODUCTION_CONFORMANCE"


@dataclass(frozen=True)
class ContractsCheckoutEvidence:
    repository_head_commit: str
    contracts_tree_git_oid: str
    reviewed_file_count: int
    contracts_relative_root: str = CONTRACTS_RELATIVE_ROOT


@dataclass(frozen=True)
class ContractVerifierEvidence:
    payload: dict[str, Any]
    raw: bytes = field(repr=False)
    self_sha256: str = ""
    physical_sha256: str = ""
    execution_boundary: str = ""
    repository_head_commit: str | None = None
    contracts_tree_git_oid: str | None = None
    reviewed_file_count: int | None = None


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.fspath(_absolute(left))) == os.path.normcase(
        os.fspath(_absolute(right))
    )


def _reject_reparse(path: Path, *, label: str) -> None:
    try:
        details = os.lstat(path)
    except OSError as exc:
        raise AuthorityError(f"cannot stat {label}: {path}") from exc
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(details.st_mode) or attributes & reparse_flag:
        raise AuthorityError(f"reparse path is forbidden for {label}: {path}")


def _reject_contract_tree_reparse(contracts_root: Path) -> None:
    for directory, child_dirs, child_files in os.walk(
        contracts_root, topdown=True, followlinks=False
    ):
        current = Path(directory)
        _reject_reparse(current, label="Contracts directory")
        for name in (*child_dirs, *child_files):
            _reject_reparse(current / name, label="Contracts tree member")


def _git(
    repository_root: Path,
    args: Sequence[str],
    *,
    allow_nonzero: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        cwd=repository_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    if completed.returncode != 0 and not allow_nonzero:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise AuthorityError(f"cannot verify Contracts Git checkout: {detail}")
    return completed


def _reviewed_file_entries(repository_root: Path) -> dict[str, str]:
    output = _git(
        repository_root,
        [
            "ls-tree",
            "-r",
            "-z",
            f"{R2_PUBLICATION_COMMIT}:{CONTRACTS_RELATIVE_ROOT}",
        ],
    ).stdout
    entries: dict[str, str] = {}
    for row in output.split("\0"):
        if not row:
            continue
        try:
            metadata, relative = row.split("\t", 1)
            mode, object_type, object_id = metadata.split(" ", 2)
            safe = safe_relative_path(relative)
        except Exception as exc:
            raise AuthorityError("malformed reviewed Contracts Git tree") from exc
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise AuthorityError("unsupported member type in reviewed Contracts Git tree")
        canonical = safe.as_posix()
        if canonical in entries:
            raise AuthorityError("duplicate path in reviewed Contracts Git tree")
        entries[canonical] = object_id
    if len(entries) != R2_MODULE_FILE_COUNT:
        raise AuthorityError("reviewed Contracts Git tree file-count mismatch")
    return entries


def _git_blob_oid(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def _verify_active_contracts_files(
    repository_root: Path, contracts_root: Path
) -> int:
    reviewed = _reviewed_file_entries(repository_root)
    _reject_contract_tree_reparse(contracts_root)
    active: dict[str, Path] = {}
    for directory, _child_dirs, child_files in os.walk(
        contracts_root, topdown=True, followlinks=False
    ):
        current = Path(directory)
        for name in child_files:
            path = current / name
            relative = path.relative_to(contracts_root).as_posix()
            if relative in active:
                raise AuthorityError("duplicate active Contracts path")
            active[relative] = path
    if set(active) != set(reviewed):
        raise AuthorityError("active Contracts file inventory differs from reviewed Git tree")
    for relative, expected_oid in reviewed.items():
        path = active[relative]
        details = os.lstat(path)
        if not stat.S_ISREG(details.st_mode):
            raise AuthorityError(f"active Contracts member is not a regular file: {relative}")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise AuthorityError(f"cannot read active Contracts member: {relative}") from exc
        if _git_blob_oid(raw) != expected_oid:
            raise AuthorityError(f"active Contracts file differs from reviewed Git blob: {relative}")
    return len(reviewed)


def _verify_reviewed_contracts_checkout(
    repository_root: Path,
    contracts_root: Path,
    *,
    trusted_repository_root: Path,
) -> ContractsCheckoutEvidence:
    repository_root = _absolute(repository_root)
    contracts_root = _absolute(contracts_root)
    trusted_repository_root = _absolute(trusted_repository_root)

    _reject_reparse(repository_root, label="repository root")
    _reject_reparse(contracts_root, label="Contracts root")
    if not _same_path(repository_root, trusted_repository_root):
        raise AuthorityError("production R2 repository root is not the trusted Harness checkout")
    expected_contracts_root = repository_root / CONTRACTS_RELATIVE_ROOT
    if not _same_path(contracts_root, expected_contracts_root):
        raise AuthorityError("production R2 Contracts root is not the canonical repository subtree")
    if not contracts_root.is_dir():
        raise AuthorityError("production R2 Contracts root is unavailable")
    reviewed_file_count = _verify_active_contracts_files(
        repository_root, contracts_root
    )

    top_level = _git(repository_root, ["rev-parse", "--show-toplevel"]).stdout.strip()
    if not _same_path(Path(top_level), repository_root):
        raise AuthorityError("production R2 repository root is not the active Git worktree root")
    ancestry = _git(
        repository_root,
        ["merge-base", "--is-ancestor", R2_PUBLICATION_COMMIT, "HEAD"],
        allow_nonzero=True,
    )
    if ancestry.returncode != 0:
        raise AuthorityError("reviewed R2 publication is not an ancestor of the active checkout")
    reviewed_tree = _git(
        repository_root,
        ["rev-parse", f"{R2_PUBLICATION_COMMIT}:{CONTRACTS_RELATIVE_ROOT}"],
    ).stdout.strip()
    if reviewed_tree != R2_MODULE_TREE_GIT_OID:
        raise AuthorityError("reviewed R2 publication Contracts tree pin mismatch")
    active_tree = _git(
        repository_root,
        ["rev-parse", f"HEAD:{CONTRACTS_RELATIVE_ROOT}"],
    ).stdout.strip()
    if active_tree != reviewed_tree:
        raise AuthorityError("active Contracts Git tree differs from the reviewed R2 tree")
    worktree_status = _git(
        repository_root,
        [
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            CONTRACTS_RELATIVE_ROOT,
        ],
    ).stdout
    if worktree_status.strip():
        raise AuthorityError("active Contracts worktree differs from its reviewed Git tree")
    head_commit = _git(repository_root, ["rev-parse", "HEAD"]).stdout.strip()
    return ContractsCheckoutEvidence(
        repository_head_commit=head_commit,
        contracts_tree_git_oid=active_tree,
        reviewed_file_count=reviewed_file_count,
    )


@dataclass
class PublicContractR2Verifier:
    repository_root: Path
    contracts_root: Path
    command_prefix: tuple[str, ...] = field(default_factory=tuple)
    python_executable: str = sys.executable
    execution_boundary: str = PRODUCTION_CANONICAL

    def __post_init__(self) -> None:
        self.repository_root = _absolute(self.repository_root)
        self.contracts_root = _absolute(self.contracts_root)
        if self.execution_boundary not in {
            PRODUCTION_CANONICAL,
            NON_PRODUCTION_CONFORMANCE,
        }:
            raise AuthorityError("unsupported Contract verifier execution boundary")
        if self.command_prefix and self.execution_boundary != NON_PRODUCTION_CONFORMANCE:
            raise AuthorityError("custom Contract verifier commands are conformance-only")

    def is_production_for(self, repository_root: Path, contracts_root: Path) -> bool:
        executable_matches = _same_path(
            Path(self.python_executable), Path(sys.executable)
        )
        return (
            self.execution_boundary == PRODUCTION_CANONICAL
            and not self.command_prefix
            and executable_matches
            and _same_path(self.repository_root, repository_root)
            and _same_path(self.contracts_root, contracts_root)
        )

    def verify_production_checkout(self) -> ContractsCheckoutEvidence:
        if self.execution_boundary != PRODUCTION_CANONICAL or self.command_prefix:
            raise AuthorityError("non-production Contract verifier cannot verify an R2 checkout")
        trusted_root = _absolute(Path(__file__).parent.parent)
        return _verify_reviewed_contracts_checkout(
            self.repository_root,
            self.contracts_root,
            trusted_repository_root=trusted_root,
        )

    def _command(self) -> list[str]:
        if self.command_prefix:
            return list(self.command_prefix)
        script = (
            self.contracts_root
            / "release"
            / "authority_maintenance_v1"
            / "tools"
            / "verify_authority_receipt.py"
        )
        if not script.is_file():
            raise AuthorityError(f"public Contract R2 verifier is missing: {script}")
        return [self.python_executable, "-B", str(script)]

    def verify(self, receipt_path: Path) -> ContractVerifierEvidence:
        checkout = (
            self.verify_production_checkout()
            if self.execution_boundary == PRODUCTION_CANONICAL
            else None
        )
        receipt_path = receipt_path.resolve()
        with tempfile.TemporaryDirectory(prefix="integration-contract-r2-") as directory:
            report_path = Path(directory) / "authority_verification_report.json"
            command = self._command() + [
                "--repo-root",
                str(self.repository_root),
                "--distribution-root",
                str(self.repository_root),
                "--receipt",
                str(receipt_path),
                "--report",
                str(report_path),
            ]
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["SYSTEM_INTEGRATION_NETWORK_POLICY"] = "FORBIDDEN"
            env["NO_PROXY"] = "*"
            completed = subprocess.run(
                command,
                cwd=self.repository_root,
                env=env,
                capture_output=True,
                check=False,
                timeout=180,
            )
            if completed.returncode != 0:
                stderr = completed.stderr.decode("utf-8", errors="replace").strip()
                raise AuthorityError(f"public Contract R2 verifier failed: {stderr}")
            stdout = loads_strict(completed.stdout, require_object=True)
            if not report_path.is_file():
                raise AuthorityError("public Contract R2 verifier emitted no report")
            raw = report_path.read_bytes()
            payload = load_json(report_path, require_object=True)
            if stdout != payload:
                raise AuthorityError("public Contract R2 verifier stdout/report mismatch")

        if checkout is not None and self.verify_production_checkout() != checkout:
            raise AuthorityError("Contracts checkout drifted during public R2 verification")

        expected = {
            "schema_id": REPORT_SCHEMA_ID,
            "result": "PASS",
            "authority_tag": "contracts-v1.1.0",
            "authority_commit": "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed",
            "manifest_sha256": MANIFEST_SHA256,
            "gate_policy_self_sha256": GATE_POLICY_SELF_SHA256,
            "feature_registry_canonical_sha256": FEATURE_REGISTRY_CANONICAL_SHA256,
            "receipt_self_sha256": RECEIPT_SELF_SHA256,
            "receipt_physical_sha256": RECEIPT_PHYSICAL_SHA256,
            "release_zip_sha256": FINAL_ZIP_SHA256,
            "integrity_mode": "CANONICAL_SELF_HASH_AND_PHYSICAL_DISTRIBUTION_PIN",
            "warnings": [],
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise AuthorityError(f"public Contract R2 verifier report mismatch: {key}")
        declared_self = payload.get("integrity", {}).get("self_sha256")
        if declared_self != REPORT_SELF_SHA256 or self_sha256(payload) != declared_self:
            raise AuthorityError("public Contract R2 verifier report self hash mismatch")
        physical = sha256_bytes(raw)
        if physical != REPORT_PHYSICAL_SHA256:
            raise AuthorityError("public Contract R2 verifier report physical hash mismatch")
        return ContractVerifierEvidence(
            payload=payload,
            raw=raw,
            self_sha256=declared_self,
            physical_sha256=physical,
            execution_boundary=self.execution_boundary,
            repository_head_commit=(
                checkout.repository_head_commit if checkout is not None else None
            ),
            contracts_tree_git_oid=(
                checkout.contracts_tree_git_oid if checkout is not None else None
            ),
            reviewed_file_count=(
                checkout.reviewed_file_count if checkout is not None else None
            ),
        )
