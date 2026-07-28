from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from build_artifact import build_artifact  # noqa: E402
from hardening_common import read_csv, read_json, read_jsonl, sha256_file  # noqa: E402
from validate_artifact import validate_artifact  # noqa: E402


SOURCE_DOCUMENT = Path(
    "C:/work/agent-based-translation-d2l-direct-builder-v1/jobs/"
    "src_d2l_full_book_local_b858af3a5252/source_package_snapshot/document.json"
)


class HardeningArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not SOURCE_DOCUMENT.is_file():
            raise unittest.SkipTest("Bound D2L source document is not available")
        cls.temporary = tempfile.TemporaryDirectory()
        cls.parent_root = (
            REPOSITORY_ROOT / "dataset" / "d2l_context_support_set_validation_ready_v3"
        )
        cls.output_root = Path(cls.temporary.name) / "release"
        cls.archive_path = (
            Path(cls.temporary.name) / "dataset_methodology_hardening_v1.zip"
        )
        cls.parent_manifest_before = sha256_file(cls.parent_root / "manifest.json")
        cls.summary = build_artifact(
            cls.parent_root,
            SOURCE_DOCUMENT,
            cls.output_root,
            cls.archive_path,
            PACKAGE_ROOT / "methodology_protocol.md",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_structural_validation_passes_with_explicit_blockers(self) -> None:
        report = validate_artifact(
            self.parent_root, self.output_root, self.archive_path
        )
        self.assertEqual(report["status"], "PASS_WITH_BLOCKERS", report["errors"])
        self.assertEqual(report["structural_integrity"], "PASS")
        self.assertEqual(
            report["audit_status_counts"],
            {"FAIL_SYNTHETIC": 140, "PASS_CORPUS_EXTRACTED": 1200},
        )
        self.assertEqual(report["statistical_unit_count"], 3474)
        self.assertEqual(report["source_block_split_leakage_count"], 45)
        self.assertEqual(report["downstream_block_count"], 22)
        self.assertEqual(report["controlled_vietnamese_source_count"], 0)

    def test_synthetic_contexts_never_enter_c_or_statistical_units(self) -> None:
        audit = read_csv(self.output_root / "corpus_origin_audit.csv")
        synthetic_ids = {
            row["context_id"]
            for row in audit
            if row["origin"] == "SYNTHETIC_CONTROLLED"
        }
        self.assertEqual(len(synthetic_ids), 140)
        self.assertTrue(
            all(
                row["eligible_for_c_primary_support"].casefold() == "false"
                and row["eligible_for_c_support"].casefold() == "false"
                for row in audit
                if row["context_id"] in synthetic_ids
            )
        )
        statistical = read_jsonl(self.output_root / "statistical_units.jsonl")
        self.assertTrue(
            all(row["context_id"] not in synthetic_ids for row in statistical)
        )

    def test_build_is_deterministic_and_parent_is_immutable(self) -> None:
        second_root = Path(self.temporary.name) / "release_second"
        second_archive = Path(self.temporary.name) / "hardening_second.zip"
        second = build_artifact(
            self.parent_root,
            SOURCE_DOCUMENT,
            second_root,
            second_archive,
            PACKAGE_ROOT / "methodology_protocol.md",
        )
        self.assertEqual(
            second["artifact_manifest_sha256"],
            self.summary["artifact_manifest_sha256"],
        )
        self.assertEqual(second["archive_sha256"], self.summary["archive_sha256"])
        self.assertEqual(
            sha256_file(self.parent_root / "manifest.json"),
            self.parent_manifest_before,
        )

    def test_tampered_artifact_fails_validation(self) -> None:
        tampered = Path(self.temporary.name) / "tampered"
        shutil.copytree(self.output_root, tampered)
        path = tampered / "source_block_registry.jsonl"
        rows = read_jsonl(path)
        rows[0]["source_text"] += " tampered"
        path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )
        report = validate_artifact(self.parent_root, tampered)
        self.assertEqual(report["status"], "FAIL")
        self.assertGreater(report["error_count"], 0)

    def test_external_and_independent_inputs_are_not_fabricated(self) -> None:
        validation = read_json(self.output_root / "validation_report.json")
        blocker_codes = {row["code"] for row in validation["blockers"]}
        self.assertIn("CONTROLLED_VIETNAMESE_REGISTRY_EMPTY", blocker_codes)
        self.assertIn("BLIND_ADVERSARIAL_SUBSET_PENDING", blocker_codes)
        self.assertIn("TAC_DRIFT_CASES_PENDING", blocker_codes)
        adversarial = read_json(self.output_root / "adversarial_manifest.json")
        tac = read_json(self.output_root / "tac_drift_manifest.json")
        self.assertEqual(adversarial["cases"], [])
        self.assertEqual(tac["cases"], [])


if __name__ == "__main__":
    unittest.main()
