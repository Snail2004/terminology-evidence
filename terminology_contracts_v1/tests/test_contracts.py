from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from terminology_contracts.manifest import verify_manifest
from terminology_contracts.validation import validate_file


class ContractTests(unittest.TestCase):
    def test_all_valid_examples(self):
        for path in sorted((ROOT / "examples" / "valid").glob("*.json")):
            with self.subTest(path=path.name):
                self.assertEqual(validate_file(path, ROOT / "schemas"), [])

    def test_all_invalid_examples(self):
        for path in sorted((ROOT / "examples" / "invalid").glob("*.json")):
            with self.subTest(path=path.name):
                self.assertTrue(validate_file(path, ROOT / "schemas"))

    def test_manifest(self):
        self.assertEqual(verify_manifest(ROOT), [])

    def test_global_join_mismatch_detected(self):
        path = ROOT / "examples" / "invalid" / "global_input_mismatched_candidate.json"
        errors = validate_file(path, ROOT / "schemas")
        self.assertTrue(any("candidate_key mismatch" in e for e in errors))

    def test_dev_auto_approval_detected(self):
        path = ROOT / "examples" / "invalid" / "dev_policy_auto_approved.json"
        errors = validate_file(path, ROOT / "schemas")
        self.assertTrue(any("cannot emit AUTO_APPROVED" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
