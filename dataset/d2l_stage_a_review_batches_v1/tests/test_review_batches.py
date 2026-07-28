from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from build_batches import build_release  # noqa: E402
from common import read_csv, read_json, read_jsonl  # noqa: E402
from review_workflow import merge_reviews, resolve_decisions, validate_review  # noqa: E402
from validate_batches import validate_release  # noqa: E402


class ReviewBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.source_root = (
            REPOSITORY_ROOT / "dataset" / "d2l_context_support_set_validation_ready_v3"
        )
        cls.release_root = Path(cls.temporary.name) / "release"
        build_release(cls.source_root, cls.release_root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_release_covers_all_senses_in_split_safe_batches(self) -> None:
        report = validate_release(self.source_root, self.release_root)
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(report["sense_count"], 150)
        self.assertEqual(report["batch_count"], 16)
        self.assertEqual(
            report["split_counts"],
            {"development": 100, "validation": 25, "test": 25},
        )
        manifest = read_json(self.release_root / "manifest.json")
        self.assertEqual(manifest["missing_optional_evidence_reference_count"], 2)

    def test_existing_five_case_pilot_hashes_remain_compatible(self) -> None:
        pilot_path = (
            REPOSITORY_ROOT
            / "dataset"
            / "d2l_stage_a_parallel_review_pack_v1_2"
            / "sense_review_cases.jsonl"
        )
        pilot = {row["sense_id"]: row for row in read_jsonl(pilot_path)}
        generated = {}
        for path in (self.release_root / "batches").glob("*/sense_review_cases.jsonl"):
            generated.update({row["sense_id"]: row for row in read_jsonl(path)})
        for sense_id, source_case in pilot.items():
            self.assertEqual(
                generated[sense_id]["source_payload_sha256"],
                source_case["source_payload_sha256"],
            )
            self.assertEqual(generated[sense_id]["case_sha256"], source_case["case_sha256"])

    def test_blank_template_passes_partial_and_fails_complete(self) -> None:
        batch_root = self.release_root / "batches" / "development_001"
        review_path = batch_root / "ai_1.csv"
        self.assertEqual(validate_review(batch_root, review_path)["status"], "PASS")
        self.assertEqual(
            validate_review(batch_root, review_path, True)["status"], "FAIL"
        )

    def test_source_field_tamper_is_rejected(self) -> None:
        batch_root = self.release_root / "batches" / "development_001"
        source_path = batch_root / "ai_1.csv"
        mutated_path = Path(self.temporary.name) / "tampered.csv"
        rows = read_csv(source_path)
        rows[0]["case_sha256"] = "0" * 64
        with mutated_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        report = validate_review(batch_root, mutated_path)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("immutable field" in error for error in report["errors"]))

    def test_core_decision_consensus_ignores_scope_note_wording(self) -> None:
        decisions = [
            {
                "definition_status": "ACCEPTED",
                "effective_definition_en": "same",
                "part_of_speech_status": "ACCEPTED",
                "effective_part_of_speech": "noun",
                "scope_note": note,
            }
            for note in ("one", "two", "three")
        ]
        resolution, effective = resolve_decisions(decisions)
        self.assertEqual(resolution, "AGREEMENT_3_OF_3")
        self.assertEqual(effective["effective_definition_en"], "same")

    def test_three_completed_csv_files_validate_and_merge(self) -> None:
        batch_root = self.release_root / "batches" / "development_001"
        cases = read_jsonl(batch_root / "sense_review_cases.jsonl")
        case_by_id = {case["sense_id"]: case for case in cases}
        review_paths = []
        for slot in (1, 2, 3):
            rows = read_csv(batch_root / f"ai_{slot}.csv")
            for row in rows:
                case = case_by_id[row["sense_id"]]
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
                        "scope_note": f"reviewer {slot} wording",
                        "evidence_context_ids": evidence,
                        "confidence": "0.95",
                        "rationale": "Supported by the cited corpus context.",
                        "risk_flags": "",
                    }
                )
            review_path = Path(self.temporary.name) / f"complete_{slot}.csv"
            with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            review_paths.append(review_path)
            report = validate_review(batch_root, review_path, True)
            self.assertEqual(report["status"], "PASS", report["errors"])
        output_dir = Path(self.temporary.name) / "merged"
        summary = merge_reviews(batch_root, review_paths, output_dir)
        self.assertEqual(summary["sense_count"], 10)
        self.assertEqual(summary["resolution_counts"], {"AGREEMENT_3_OF_3": 10})
        self.assertEqual(summary["adjudication_required"], 0)


if __name__ == "__main__":
    unittest.main()
