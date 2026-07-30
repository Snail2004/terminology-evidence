from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from integration_harness.errors import IntegrityError, ValidationError
from integration_harness.hashing import self_sha256
from integration_harness.jsonio import dump_json, load_json
from integration_harness.review_package import (
    CHECKSUMS_NAME,
    RECEIPT_NAME,
    seal_review_package,
    verify_review_package,
)


class D0ReviewPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = (
            Path.cwd()
            / "docs/integration/system_integration_d0_review_receipt_v1.schema.json"
        )

    def _receipt(self) -> dict[str, object]:
        return {
            "schema_id": "SystemIntegrationD0ReviewReceiptV1",
            "schema_version": "1.0.0",
            "status": "EV02_BOUND_D0_COHORT_READY_FOR_INDEPENDENT_REVIEW",
            "live_status": "REVIEW_ONLY_DRAFT_INPUT",
            "base_commit": "1" * 40,
            "child_commit": "2" * 40,
            "child_tree": "3" * 40,
            "changed_paths": ["integration_harness/review_package.py"],
            "gates": {"focused": "PASS", "provider_calls": 0},
            "dataset_authority": {
                "status": "PRODUCER_SAFE_PAYLOAD_ACCEPTED_ZERO_PROVIDER",
                "zip_sha256": "8a39dce822dcb6aa228da25a5a10b7df07b6ac60ef68bca3e5466aba49449d73",
                "manifest_self_sha256": "194dd421ad7aef9272e90d1dff2ef96c5a8c8bf1ded7faba74283777e279ddc2",
                "candidate_identity_sha256": "ea80716a38d443afa954f110b3a8346f17073f7e76aa6ea6f2fce377490dd77b",
                "sense_identity_sha256": "db2e5298324981c96bb83c5318fc219e2bd0c341273e439a3bae3900fe9a5708",
                "context_identity_sha256": "eef660f3eff8dcec277ec607d0b56f16f66cdf55e708bb39cd6118167d7dd9fb",
                "candidate_count": 150,
                "sense_count": 50,
                "context_count": 386,
            },
            "evaluation_authority": {
                "child_commit": "7de0ecab74bc8439724e419743c18fee46cb885c",
                "child_tree": "7d2ebf8f65051e8e0326350eb32301954fb62dfc",
                "authority_zip_sha256": "86ca4e4453c6efc9c0fa11af1d37351c4e8640070c3ab7aa156006525c3bb63c",
                "cohort_physical_sha256": "df19e7e605f50190e389b374d5a08589858e1ce043b935c69646a3223daa8705",
                "cohort_self_sha256": "206f5770c7ea32d5a232f986240cfdf5655700b6a15b614a2251d6caba218fad",
                "candidate_set_sha256": "e72286e06201297864d3163311336515092d841181e484c01276faa9b989fa0b",
                "selection_authority_sha256": "0d52dd27e2657b9e9b0d353a5c66cc984b24dfbd6c8f6e79c98a99f69303745f",
                "canary_candidate_id": "candidate_479fdd8ff6d15304debec117",
                "candidate_count": 15,
                "sense_count": 5,
            },
            "main01_dependency": {
                "status": "REVIEW_ONLY_DRAFT_INPUT",
                "review_zip_sha256": "423c063e1533e5c1e044a21d1b17b196b523d2615c0fd250d9687e4406f319da",
                "profile_physical_sha256": "b9b56ce5d736a75c2084ff7f41e98f044f2d066b49e2f1e14ab3035087f8059a",
                "profile_self_sha256": "f25afa9aa1a28de431bc9e3c8422543b95820d6d31198da8fb9437d86e2da995",
                "run_spec_physical_sha256": "497ec63b9d4acdd88773b4f9dcc43b491efafe853af6b0750868694761ce4df7",
                "run_spec_self_sha256": "7a409a656e86f4597997b87b2e666a35c52ae1a647d08c430fcb7faef43f1aff",
                "activates_live_authority": False,
            },
            "invariants": {
                "provider_calls": 0,
                "network_calls": 0,
                "gold_access": 0,
                "auto_approved": 0,
                "certificates": 0,
                "official_live_authority": "HOLD",
            },
        }

    def _sealed(self, directory: str) -> Path:
        root = Path(directory) / "review"
        (root / "evidence").mkdir(parents=True)
        (root / "evidence/result.txt").write_text("PASS\n", encoding="ascii")
        result = seal_review_package(root, self._receipt(), schema_path=self.schema)
        self.assertEqual(result["member_count"], 2)
        checksums = (root / CHECKSUMS_NAME).read_text(encoding="ascii")
        self.assertIn(RECEIPT_NAME, checksums)
        return root

    def test_self_hashed_receipt_and_complete_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._sealed(directory)
            first = verify_review_package(root, schema_path=self.schema)
            second = verify_review_package(root, schema_path=self.schema)
            self.assertEqual(first, second)

    def test_receipt_and_member_tamper_fail_closed(self) -> None:
        for target in (RECEIPT_NAME, "evidence/result.txt"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                root = self._sealed(directory)
                path = root / target
                path.write_bytes(path.read_bytes() + b"x")
                with self.assertRaises(IntegrityError):
                    verify_review_package(root, schema_path=self.schema)

    def test_resealed_receipt_drift_still_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._sealed(directory)
            receipt_path = root / RECEIPT_NAME
            receipt = load_json(receipt_path, require_object=True)
            receipt["evaluation_authority"]["canary_candidate_id"] = "candidate_wrong"
            receipt["integrity"]["self_sha256"] = self_sha256(receipt)
            receipt_path.unlink()
            dump_json(receipt_path, receipt)
            with self.assertRaises((IntegrityError, ValidationError)) as caught:
                verify_review_package(root, schema_path=self.schema)
            self.assertIsNotNone(caught.exception)

    def test_omitted_receipt_and_extra_member_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._sealed(directory)
            lines = (root / CHECKSUMS_NAME).read_text(encoding="ascii").splitlines()
            (root / CHECKSUMS_NAME).write_text(
                "\n".join(line for line in lines if RECEIPT_NAME not in line) + "\n",
                encoding="ascii",
                newline="\n",
            )
            with self.assertRaises(IntegrityError):
                verify_review_package(root, schema_path=self.schema)
        with tempfile.TemporaryDirectory() as directory:
            root = self._sealed(directory)
            (root / "unexpected.txt").write_text("x", encoding="ascii")
            with self.assertRaises(IntegrityError):
                verify_review_package(root, schema_path=self.schema)


if __name__ == "__main__":
    unittest.main()
