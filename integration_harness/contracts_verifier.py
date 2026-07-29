"""Public subprocess boundary for the reviewed Contracts R2 verifier."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import AuthorityError
from .hashing import self_sha256, sha256_bytes
from .jsonio import load_json, loads_strict


REPORT_SCHEMA_ID = "TerminologyContractsAuthorityVerificationReportV1"
REPORT_SELF_SHA256 = "8d11809faf9236f834e3238a3e38b02f2b1a6377b148648e7d0e53ee669218cc"
REPORT_PHYSICAL_SHA256 = "fae5375ebc5dc0af9269ec01692c707c05e9664bdf02347ff0d8a7a25b0922b3"
RECEIPT_SELF_SHA256 = "a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618"
RECEIPT_PHYSICAL_SHA256 = "acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79"
FINAL_ZIP_SHA256 = "2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471"
MANIFEST_SHA256 = "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
GATE_POLICY_SELF_SHA256 = "9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2"
FEATURE_REGISTRY_CANONICAL_SHA256 = "057f47d68097286f04f0870d2e78944e59c07b0cb4e9db7f9d8675c9f2c8b182"


@dataclass(frozen=True)
class ContractVerifierEvidence:
    payload: dict[str, Any]
    raw: bytes = field(repr=False)
    self_sha256: str = ""
    physical_sha256: str = ""


@dataclass
class PublicContractR2Verifier:
    repository_root: Path
    contracts_root: Path
    command_prefix: tuple[str, ...] = field(default_factory=tuple)
    python_executable: str = sys.executable

    def __post_init__(self) -> None:
        self.repository_root = self.repository_root.resolve()
        self.contracts_root = self.contracts_root.resolve()

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
        )
