from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from common import read_csv, read_json, read_jsonl, sha256_object  # noqa: E402
from review_intake import finalize_reviews, inventory_reviews  # noqa: E402


class ReviewIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.release_root = PACKAGE_ROOT / "release"
        cls.completed_root = Path(cls.temporary.name) / "completed"
        cls._write_completed_reviews(cls.completed_root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @classmethod
    def _write_completed_reviews(cls, root: Path) -> None:
        for batch_root in sorted((cls.release_root / "batches").iterdir()):
            if not batch_root.is_dir():
                continue
            cases = {
                row["sense_id"]: row
                for row in read_jsonl(batch_root / "sense_review_cases.jsonl")
            }
            rows = read_csv(batch_root / "ai_1.csv")
            for row in rows:
                case = cases[row["sense_id"]]
                evidence = next(
                    context["context_id"]
                    for group in case["evidence_contexts"].values()
                    for context in group
                )
                row.update(
                    {
                        "definition_status": "ACCEPTED",
                        "effective_definition_en": case["model_definition_en"],
                        "part_of_speech_status": "ACCEPTED",
                        "effective_part_of_speech": case["model_part_of_speech"],
                        "scope_note": "Independent review conclusion.",
                        "evidence_context_ids": evidence,
                        "confidence": "0.95",
                        "rationale": "Supported by the cited corpus context.",
                        "risk_flags": "",
                    }
                )
            target = root / batch_root.name
            target.mkdir(parents=True)
            first = target / "ai_1.csv"
            with first.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            shutil.copyfile(first, target / "ai_2.csv")
            shutil.copyfile(first, target / "ai_3.csv")

    def test_empty_intake_reports_all_48_missing(self) -> None:
        empty = Path(self.temporary.name) / "empty"
        report = inventory_reviews(self.release_root, empty)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["expected_review_file_count"], 48)
        self.assertEqual(report["missing_review_file_count"], 48)

    def test_complete_intake_finalizes_all_150_senses(self) -> None:
        report = inventory_reviews(self.release_root, self.completed_root)
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["valid_review_file_count"], 48)
        output = Path(self.temporary.name) / "finalized"
        summary = finalize_reviews(self.release_root, self.completed_root, output)
        self.assertEqual(summary["sense_count"], 150)
        self.assertEqual(
            summary["split_counts"],
            {"development": 100, "test": 25, "validation": 25},
        )
        self.assertEqual(summary["resolution_counts"], {"AGREEMENT_3_OF_3": 150})
        merged = read_jsonl(output / "merged_all_batches.jsonl")
        self.assertEqual(len(merged), 150)
        for row in merged:
            identity = dict(row)
            claimed = identity.pop("record_sha256")
            self.assertEqual(claimed, sha256_object(identity))
            self.assertEqual(row["schema_id"], "D2LCSTGlobalMergedReviewRecordV1")
            self.assertTrue(row["parent_batch_record_sha256"])
        self.assertEqual(len(read_jsonl(output / "adjudication_queue.jsonl")), 0)
        self.assertEqual(read_json(output / "manifest.json")["status"], "PASS")

    def test_mutation_after_inventory_rejects_without_final_output(self) -> None:
        drifting = Path(self.temporary.name) / "drifting"
        shutil.copytree(self.completed_root, drifting)
        output = Path(self.temporary.name) / "drift_output"
        original_inventory = inventory_reviews

        def inventory_then_mutate(release_root: Path, intake_root: Path):
            report = original_inventory(release_root, intake_root)
            path = intake_root / "development_001" / "ai_1.csv"
            path.write_bytes(path.read_bytes() + b"\n")
            return report

        with patch("review_intake.inventory_reviews", side_effect=inventory_then_mutate):
            with self.assertRaisesRegex(ValueError, "Review input drift detected"):
                finalize_reviews(self.release_root, drifting, output)
        self.assertFalse(output.exists())

    def test_tampered_review_rejects_without_final_output(self) -> None:
        tampered = Path(self.temporary.name) / "tampered"
        shutil.copytree(self.completed_root, tampered)
        path = tampered / "development_001" / "ai_2.csv"
        rows = read_csv(path)
        rows[0]["case_sha256"] = "0" * 64
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        output = Path(self.temporary.name) / "tampered_output"
        with self.assertRaises(ValueError):
            finalize_reviews(self.release_root, tampered, output)
        self.assertFalse(output.exists())

    def test_unexpected_csv_fails_inventory(self) -> None:
        unexpected = Path(self.temporary.name) / "unexpected"
        shutil.copytree(self.completed_root, unexpected)
        shutil.copyfile(
            unexpected / "development_001" / "ai_1.csv",
            unexpected / "extra.csv",
        )
        report = inventory_reviews(self.release_root, unexpected)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["unexpected_review_files"], ["extra.csv"])


if __name__ == "__main__":
    unittest.main()
