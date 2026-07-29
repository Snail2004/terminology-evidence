from __future__ import annotations

import copy
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from integration_harness.approval_binding import verify_approval_binding
from integration_harness.authority import (
    CONTRACTS_R1_HISTORICAL_REPLAY,
    CONTRACTS_R2_CURRENT,
    resolve_authority,
)
from integration_harness.contracts_verifier import (
    NON_PRODUCTION_CONFORMANCE,
    PublicContractR2Verifier,
)
from integration_harness.errors import AuthorityError
from integration_harness.hashing import self_sha256
from integration_harness.jsonio import dump_json, load_json

from .helpers import fake_contract_verifier, make_fixture_repo


class R2CommonBindingTests(unittest.TestCase):
    def _fixture(self, root: Path):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        return make_fixture_repo(root, directory, 1)

    def _resolve(
        self,
        root: Path,
        *,
        receipt: Path | None = None,
        approval_root: Path | None = None,
        action_policy: Path | None = None,
        action_policy_authority: Path | None = None,
        authority_mode: str = CONTRACTS_R2_CURRENT,
    ):
        fixture = self._fixture(root)
        return resolve_authority(
            receipt or fixture["r2_receipt"],
            fixture["contracts"],
            repository_root=root,
            approval_root=approval_root or fixture["approval_root"],
            action_policy_path=action_policy or fixture["action_policy"],
            action_policy_authority_path=(
                action_policy_authority or fixture["action_policy_authority"]
            ),
            authority_mode=authority_mode,
        )

    def test_exact_r2_and_detached_approval_pass(self) -> None:
        root = Path.cwd()
        fixture = self._fixture(root)
        authority = resolve_authority(
            fixture["r2_receipt"],
            fixture["contracts"],
            repository_root=root,
            approval_root=fixture["approval_root"],
            action_policy_path=fixture["action_policy"],
            action_policy_authority_path=fixture["action_policy_authority"],
            authority_mode=CONTRACTS_R2_CURRENT,
        )
        self.assertEqual(authority.receipt_revision, 2)
        self.assertEqual(authority.r2_module_file_count, 227)
        self.assertEqual(authority.approval.payload["approval_status"], "ACCEPTED_FOR_AUTHORITY_PROMOTION")
        self.assertEqual(authority.compatibility_mode, "NONE")

    def test_nonproduction_exact_report_cannot_authorize_current_r2(self) -> None:
        root = Path.cwd()
        fixture = self._fixture(root)
        verifier = fake_contract_verifier(root)
        evidence = verifier.verify(fixture["r2_receipt"])
        self.assertEqual(evidence.execution_boundary, NON_PRODUCTION_CONFORMANCE)
        with self.assertRaisesRegex(AuthorityError, "canonical production"):
            resolve_authority(
                fixture["r2_receipt"],
                fixture["contracts"],
                repository_root=root,
                approval_root=fixture["approval_root"],
                action_policy_path=fixture["action_policy"],
                action_policy_authority_path=fixture["action_policy_authority"],
                authority_mode=CONTRACTS_R2_CURRENT,
                contract_verifier=verifier,
            )

    def test_external_drifted_contracts_root_with_fake_wrapper_rejects(self) -> None:
        root = Path.cwd()
        fixture = self._fixture(root)
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory) / "terminology_contracts_v1"
            shutil.copytree(fixture["contracts"], external)
            schema = external / "schemas" / "current" / "attestation_evidence_package.schema.json"
            schema.write_bytes(schema.read_bytes() + b"\n")
            fake_wrapper = (
                root
                / "tests"
                / "system_integration"
                / "fixtures"
                / "public_contract_verifier.py"
            )
            shutil.copyfile(
                fake_wrapper,
                external
                / "release"
                / "authority_maintenance_v1"
                / "tools"
                / "verify_authority_receipt.py",
            )
            from integration_harness import contracts_verifier as verifier_module

            with self.assertRaisesRegex(AuthorityError, "reviewed Git blob"):
                verifier_module._verify_active_contracts_files(root, external)
            with self.assertRaisesRegex(AuthorityError, "canonical repository subtree"):
                resolve_authority(
                    fixture["r2_receipt"],
                    external,
                    repository_root=root,
                    approval_root=fixture["approval_root"],
                    action_policy_path=fixture["action_policy"],
                    action_policy_authority_path=fixture["action_policy_authority"],
                    authority_mode=CONTRACTS_R2_CURRENT,
                )

    def test_active_contracts_git_drift_rejects(self) -> None:
        root = Path.cwd()
        verifier = PublicContractR2Verifier(root, root / "terminology_contracts_v1")
        from integration_harness import contracts_verifier as verifier_module

        original_git = verifier_module._git

        def drifted_git(repository_root, args, *, allow_nonzero=False):
            result = original_git(
                repository_root, args, allow_nonzero=allow_nonzero
            )
            if args and args[0] == "status":
                return SimpleNamespace(
                    returncode=0,
                    stdout=" M terminology_contracts_v1/schemas/current/attestation_evidence_package.schema.json\n",
                    stderr="",
                )
            return result

        with patch(
            "integration_harness.contracts_verifier._git",
            side_effect=drifted_git,
        ), self.assertRaisesRegex(AuthorityError, "worktree differs"):
            verifier.verify_production_checkout()

    def test_contracts_parent_and_root_reparse_reject(self) -> None:
        root = Path.cwd()
        contracts_root = root / "terminology_contracts_v1"
        original = os.lstat

        for target in (root, contracts_root):
            verifier = PublicContractR2Verifier(root, contracts_root)

            def fake_lstat(path):
                value = original(path)
                if Path(path) == target:
                    return SimpleNamespace(
                        st_mode=value.st_mode,
                        st_file_attributes=getattr(value, "st_file_attributes", 0)
                        | 0x400,
                    )
                return value

            with self.subTest(target=target), patch(
                "integration_harness.contracts_verifier.os.lstat",
                side_effect=fake_lstat,
            ), self.assertRaisesRegex(AuthorityError, "reparse path"):
                verifier.verify_production_checkout()

    def test_all_six_resealed_r2_drifts_reject(self) -> None:
        root = Path.cwd()
        source = root / "terminology_contracts_v1" / "release" / "v1.1.0-final" / "contracts_v1_1_0_authority_receipt_r2.json"
        probes = {
            "gate_policy_self_sha256": "0" * 64,
            "feature_registry_file_sha256": "0" * 64,
            "receipt_revision": 1,
            "contract_tree_git_oid": "0" * 40,
            "authority_status": "UNSEALED",
            "final_release_zip_sha256": "0" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            for field, value in probes.items():
                with self.subTest(field=field):
                    receipt = copy.deepcopy(load_json(source, require_object=True))
                    receipt[field] = value
                    receipt["integrity"]["self_sha256"] = self_sha256(receipt)
                    path = Path(directory) / f"{field}.json"
                    dump_json(path, receipt)
                    with self.assertRaises(AuthorityError):
                        self._resolve(root, receipt=path)

    def test_detached_binding_missing_swapped_tampered_and_case_reject(self) -> None:
        root = Path.cwd()
        source = root / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2"
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for fault in ("missing", "swapped", "tampered", "case"):
                target = work / fault
                shutil.copytree(source, target)
                if fault == "missing":
                    (target / "Hau_Review_Contract_Steward_R2_Authority_Promotion.md").unlink()
                elif fault == "swapped":
                    left = target / "Independent_Review_Contract_Steward_Authority_Maintenance_V1_2_R2.md"
                    right = target / "Hau_Review_Contract_Steward_R2_Authority_Promotion.md"
                    left.write_bytes(right.read_bytes())
                elif fault == "tampered":
                    path = target / "approval_binding_v1.json"
                    value = load_json(path, require_object=True)
                    value["approval_status"] = "REJECTED"
                    value["integrity"]["self_sha256"] = self_sha256(value)
                    path.unlink()
                    dump_json(path, value)
                else:
                    path = target / "approval_binding_v1.json"
                    interim = target / "binding.tmp"
                    path.rename(interim)
                    interim.rename(target / "Approval_Binding_V1.json")
                with self.subTest(fault=fault), self.assertRaises(AuthorityError):
                    verify_approval_binding(target)

    def test_reparse_member_rejects(self) -> None:
        root = Path.cwd() / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2"
        original = os.lstat

        for target in (root, root / "approval_binding_v1.json"):
            def fake_lstat(path):
                value = original(path)
                if Path(path) == target:
                    return SimpleNamespace(
                        st_mode=value.st_mode,
                        st_file_attributes=getattr(value, "st_file_attributes", 0) | 0x400,
                    )
                return value

            with self.subTest(target=target), patch(
                "integration_harness.approval_binding.os.lstat",
                side_effect=fake_lstat,
            ), self.assertRaises(AuthorityError):
                verify_approval_binding(root)

    def test_action_policy_and_authority_sidecar_drift_reject(self) -> None:
        root = Path.cwd()
        fixture = self._fixture(root)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for key, source in (
                ("policy", fixture["action_policy"]),
                ("sidecar", fixture["action_policy_authority"]),
            ):
                target = work / f"{key}.json"
                value = load_json(source, require_object=True)
                value["integrity"]["self_sha256"] = "0" * 64
                dump_json(target, value)
                kwargs = {"action_policy": target} if key == "policy" else {"action_policy_authority": target}
                with self.subTest(key=key), self.assertRaises(AuthorityError):
                    self._resolve(root, **kwargs)

    def test_r1_cannot_start_or_replace_r2(self) -> None:
        root = Path.cwd()
        r1 = root / "terminology_contracts_v1" / "release" / "v1.1.0-final" / "history" / "contracts_v1_1_0_authority_receipt_r1_resealed.json"
        with self.assertRaises(AuthorityError):
            self._resolve(root, receipt=r1, authority_mode=CONTRACTS_R1_HISTORICAL_REPLAY)
        with self.assertRaises(AuthorityError):
            self._resolve(root, receipt=r1, authority_mode=CONTRACTS_R2_CURRENT)
