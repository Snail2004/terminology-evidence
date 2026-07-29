import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.authority import AuthorityProfileError, load_allowed_authority_profile, verify_external_authorities
from evaluation.v1.constants import MODE_LEGACY_READ_ONLY, MODE_REAL_AUTHORITY, MODE_SYNTHETIC
from evaluation.v1.jsonio import sha256_file, sha256_value, write_json
from evaluation.v1.preregistration.legacy import verify_legacy_receipt
from evaluation.v1.preregistration.receipt import ReceiptError, build_receipt, verify_receipt, verify_receipt_object, write_receipt
from tests.evaluation.git_context import resolve_test_git_context


class AuthorityAndReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[2]
        cls.git_repo, cls.commit = resolve_test_git_context(cls.repo)
        cls.registries = cls.repo / "evaluation" / "v1" / "registries"
        cls.artifacts = {
            "contracts_receipt": cls.repo / "terminology_contracts_v1" / "release" / "v1.1.0-final" / "contracts_v1_1_0_authority_receipt_r2.json",
            "contracts_approval_binding": cls.repo / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2" / "approval_binding_v1.json",
            "contracts_checksums": cls.repo / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2" / "CHECKSUMS.sha256",
            "global_authority_report": cls.repo / "global_validator" / "v1" / "release" / "authority_verification_report.json",
            "global_action_policy": cls.repo / "global_validator" / "v1" / "release" / "gate_policy_report.json",
            "dataset_manifest": cls.repo / "dataset" / "d2l_context_support_set_validation_ready_v3" / "manifest.json",
            "dataset_split_assignments": cls.repo / "dataset" / "d2l_context_support_set_validation_ready_v3" / "split_assignments.jsonl",
        }

    def test_profile_and_external_authorities_are_exact(self):
        profile = load_allowed_authority_profile()
        self.assertEqual(profile["integrity"]["self_sha256"], "415d0a32291221f8bbd2c36c8b4a44301f471781d4598d8db647eeb3e74fb33f")
        evidence = verify_external_authorities(self.artifacts, registry_root=self.registries)
        self.assertEqual(evidence["status"], "PASS")
        self.assertEqual(evidence["contracts"]["receipt_revision"], 2)

    def test_real_receipt_round_trip_binds_external_authority(self):
        receipt = build_receipt(
            mode=MODE_REAL_AUTHORITY,
            base_commit=self.commit,
            repo_root_path=self.git_repo,
            registry_root_path=self.registries,
            authority_artifact_paths=self.artifacts,
            artifact_hashes={"evaluation_plan": "a" * 64},
            created_at="2026-07-29T15:00:00+07:00",
        )
        self.assertTrue(receipt["frozen_before_validation"])
        self.assertEqual(receipt["authority_evidence"]["status"], "PASS")
        with TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            write_receipt(path, receipt)
            verified = verify_receipt(
                path,
                registry_root_path=self.registries,
                repo_root_path=self.git_repo,
                authority_artifact_paths=self.artifacts,
            )
            self.assertEqual(verified, receipt)

    def test_synthetic_mode_is_conformance_only_and_legacy_cannot_build(self):
        synthetic = build_receipt(
            mode=MODE_SYNTHETIC,
            base_commit=self.commit,
            repo_root_path=self.git_repo,
            registry_root_path=self.registries,
            artifact_hashes={"fixture": "b" * 64},
            synthetic_reason="schema plumbing only",
            created_at="2026-07-29T15:00:00+07:00",
        )
        self.assertEqual(synthetic["status"], "CONFORMANCE_ONLY")
        self.assertFalse(synthetic["frozen_before_validation"])
        self.assertIsNone(synthetic["authority_evidence"])
        with self.assertRaises(ReceiptError):
            build_receipt(
                mode=MODE_LEGACY_READ_ONLY,
                base_commit=self.commit,
                repo_root_path=self.git_repo,
            )

    def test_unknown_or_tampered_receipt_rejects(self):
        receipt = build_receipt(
            mode=MODE_SYNTHETIC,
            base_commit=self.commit,
            repo_root_path=self.git_repo,
            registry_root_path=self.registries,
            synthetic_reason="fixture",
            created_at="2026-07-29T15:00:00+07:00",
        )
        receipt["unknown"] = True
        with self.assertRaises(ReceiptError):
            verify_receipt_object(receipt)
        receipt.pop("unknown")
        receipt["status"] = "FROZEN_BEFORE_VALIDATION"
        with self.assertRaises(ReceiptError):
            verify_receipt_object(receipt)

    def test_authority_tamper_fails_before_receipt(self):
        with TemporaryDirectory() as temp:
            copied = dict(self.artifacts)
            tampered = Path(temp) / "binding.json"
            tampered.write_bytes(self.artifacts["contracts_approval_binding"].read_bytes() + b"\n")
            copied["contracts_approval_binding"] = tampered
            with self.assertRaises(AuthorityProfileError):
                build_receipt(
                    mode=MODE_REAL_AUTHORITY,
                    base_commit=self.commit,
                    repo_root_path=self.git_repo,
                    registry_root_path=self.registries,
                    authority_artifact_paths=copied,
                    artifact_hashes={"plan": "c" * 64},
                )

    def test_legacy_receipt_is_read_only_projection(self):
        registries = {
            path.stem.removesuffix("_v1"): sha256_file(path)
            for path in self.registries.glob("*_v1.json")
        }
        legacy = {
            "schema_id": "EvaluationPreregistrationReceiptV1",
            "schema_version": "1.0.0",
            "status": "FROZEN_BEFORE_VALIDATION",
            "frozen_before_validation": True,
            "created_at": "2026-07-29T00:00:00Z",
            "base_commit": self.commit,
            "dataset_manifest_sha256": "d" * 64,
            "registries": registries,
            "contracts_authority": {"legacy": True},
            "global_action_policy": {"legacy": True},
            "artifact_hashes": {},
            "integrity": {"self_sha256": ""},
        }
        unsigned = dict(legacy)
        unsigned["integrity"] = {}
        legacy["integrity"]["self_sha256"] = sha256_value(unsigned)
        with TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.json"
            write_json(path, legacy)
            projection = verify_legacy_receipt(path, registry_root_path=self.registries)
            self.assertEqual(projection["mode"], MODE_LEGACY_READ_ONLY)
            self.assertFalse(projection["can_freeze"])
