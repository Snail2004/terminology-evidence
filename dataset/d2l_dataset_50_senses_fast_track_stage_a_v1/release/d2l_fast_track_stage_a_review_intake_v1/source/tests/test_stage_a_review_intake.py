from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from build_stage_a_review_intake import build_review_intake  # noqa: E402
from common import sha256_file, strict_json_object, strict_jsonl  # noqa: E402
from spec import CREATED_AT_DEFAULT  # noqa: E402
from validate_stage_a_review_intake import validate_intake, validate_zip  # noqa: E402


CANONICAL_ROOT = (
    PACKAGE_ROOT / "release" / "d2l_dataset_50_senses_fast_track_stage_a_v1"
)
REVIEWER_1_ROOT = CANONICAL_ROOT / "handoff" / "result-reviewer1"
REVIEWER_2_ROOT = CANONICAL_ROOT / "handoff" / "result-reviewer2"


def _build(output: Path, reviewer_1: Path = REVIEWER_1_ROOT, reviewer_2: Path = REVIEWER_2_ROOT):
    return build_review_intake(
        canonical_root=CANONICAL_ROOT,
        reviewer_1_root=reviewer_1,
        reviewer_2_root=reviewer_2,
        output_root=output,
        created_at=CREATED_AT_DEFAULT,
    )


class StageAReviewIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.temporary.name)
        cls.source_hashes = {
            path.resolve(): sha256_file(path)
            for root in (REVIEWER_1_ROOT, REVIEWER_2_ROOT)
            for path in root.glob("*.json")
        }
        cls.artifact_root = cls.temp_root / "intake"
        cls.result = _build(cls.artifact_root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_all_reviews_validate_and_release_zip_matches(self) -> None:
        self.assertEqual(
            validate_intake(self.artifact_root, canonical_root=CANONICAL_ROOT), []
        )
        self.assertEqual(
            validate_zip(Path(self.result["release_zip"]), self.artifact_root), []
        )
        manifest = strict_json_object(self.artifact_root / "manifest.json")
        self.assertEqual(manifest["review_result_file_count"], 18)
        self.assertEqual(manifest["completed_review_decision_count"], 75)

    def test_raw_review_copies_are_byte_identical_and_sources_untouched(self) -> None:
        inventory = strict_json_object(self.artifact_root / "input_inventory.json")
        self.assertEqual(inventory["review_counts"], {"reviewer_1": 44, "reviewer_2": 31})
        for row in inventory["files"]:
            captured = self.artifact_root / row["captured_relative_path"]
            self.assertEqual(row["source_sha256"], row["captured_sha256"])
            self.assertEqual(sha256_file(captured), row["captured_sha256"])
        for path, digest in self.source_hashes.items():
            self.assertEqual(sha256_file(path), digest)

    def test_routes_match_risk_adaptive_policy(self) -> None:
        report = strict_json_object(self.artifact_root / "comparison_report.json")
        self.assertEqual(
            report["comparison"],
            {
                "r0_ready": 9,
                "r0_repair_required": 4,
                "r3_agreement": 7,
                "r3_disagreement": 8,
                "r4_mandatory": 16,
                "r4_with_agreement": 5,
                "r4_with_disagreement": 11,
                "reviewer_3_adjudication_cases": 24,
            },
        )
        adjudication = strict_jsonl(self.artifact_root / "adjudication_cases_24.jsonl")
        repair = strict_jsonl(self.artifact_root / "r0_repair_queue_4.jsonl")
        self.assertEqual(len(adjudication), 24)
        self.assertEqual(len(repair), 4)

    def test_reviewer_3_inputs_are_blank_and_contain_no_final_label(self) -> None:
        report = strict_json_object(self.artifact_root / "comparison_report.json")
        total = 0
        for handoff in report["reviewer_3_handoffs"]:
            total += handoff["case_count"]
            with zipfile.ZipFile(self.artifact_root / handoff["zip_path"]) as archive:
                payload = json.loads(archive.read("reviewer_3_input.json"))
                instructions = archive.read("REVIEW_INSTRUCTIONS.md").decode("utf-8")
                self.assertIn("candidate_id", instructions)
                for case in payload["cases"]:
                    self.assertIsNone(case["stage_b_gold_label"])
                    self.assertIsNone(case["final_glossary_decision"])
                    for field, value in case["adjudication"].items():
                        self.assertEqual(
                            value,
                            []
                            if field
                            in {
                                "invalid_evidence_context_ids",
                                "candidate_replacements",
                                "proposed_split_labels",
                            }
                            else "",
                        )
        self.assertEqual(total, 24)

    def test_source_payload_tamper_rejects_without_output(self) -> None:
        reviewer_1 = self.temp_root / "tampered_r1"
        shutil.copytree(REVIEWER_1_ROOT, reviewer_1)
        path = reviewer_1 / "batch_001_reviewer_1_completed.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["source_payload"]["source_term"] += " tampered"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        output = self.temp_root / "tampered_output"
        with self.assertRaisesRegex(ValueError, "source_payload changed"):
            _build(output, reviewer_1=reviewer_1)
        self.assertFalse(output.exists())

    def test_incomplete_review_rejects_without_output(self) -> None:
        reviewer_2 = self.temp_root / "incomplete_r2"
        shutil.copytree(REVIEWER_2_ROOT, reviewer_2)
        path = reviewer_2 / "batch_001_reviewer_2_completed.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["review"]["review_status"] = ""
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        output = self.temp_root / "incomplete_output"
        with self.assertRaisesRegex(ValueError, "review_status must be COMPLETE"):
            _build(output, reviewer_2=reviewer_2)
        self.assertFalse(output.exists())

    def test_release_is_deterministic(self) -> None:
        second_root = self.temp_root / "second" / "intake"
        second_root.parent.mkdir()
        second = _build(second_root)
        self.assertEqual(
            sha256_file(self.artifact_root / "manifest.json"),
            sha256_file(second_root / "manifest.json"),
        )
        self.assertEqual(self.result["release_zip_sha256"], second["release_zip_sha256"])


if __name__ == "__main__":
    unittest.main()
