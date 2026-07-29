from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


NAMESPACE = Path(__file__).resolve().parents[1]
REPO_ROOT = NAMESPACE.parents[1]
if str(NAMESPACE) not in sys.path:
    sys.path.insert(0, str(NAMESPACE))

from tools.build_complete_review import build_complete_review  # noqa: E402
from tools.common import read_csv, sha256_file, strict_json_object, strict_jsonl  # noqa: E402
from tools.spec import (  # noqa: E402
    ADJUDICATION_CSV_FIELDS,
    ADJUDICATION_INPUT_SHA256,
    EXPECTED_CASES,
    stable_id,
)
from tools.validate_complete_review import (  # noqa: E402
    ADAM_DEFINITION,
    STATISTICAL_POWER_REPLACEMENT,
    validate_artifact,
    validate_zip,
)


SOURCE_REVIEW_ROOT = (
    REPO_ROOT
    / "dataset"
    / "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
    / "release"
    / "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
)
SOURCE_RESULT_ROOT = (
    REPO_ROOT
    / "dataset"
    / "d2l_stage_a_targeted_repair_review_result_5_senses_v1"
    / "release"
    / "d2l_stage_a_targeted_repair_review_result_5_senses_v1"
)
ADJUDICATION = NAMESPACE / "inputs" / "adjudication_template_2_completed.csv"


class TargetedRepairReviewCompleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.output = (
            cls.base
            / "first"
            / "d2l_stage_a_targeted_repair_review_complete_5_senses_v1"
        )
        cls.result = build_complete_review(
            source_review_root=SOURCE_REVIEW_ROOT,
            source_result_root=SOURCE_RESULT_ROOT,
            adjudication_path=ADJUDICATION,
            output_root=cls.output,
            created_at="2026-07-29T13:00:00Z",
        )
        cls.zip_path = cls.output.parent / (
            "d2l_stage_a_targeted_repair_review_complete_5_senses_v1_"
            "reviewer_handoff.zip"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_release_validates_with_exact_counts(self) -> None:
        self.assertEqual(self.result["status"], "STAGE_A_REVIEW_COMPLETE")
        self.assertEqual(validate_artifact(self.output), [])
        self.assertEqual(validate_zip(self.zip_path, self.output), [])
        self.assertEqual(
            self.result["counts"],
            {
                "reviewed_sense": 5,
                "reviewed_candidate": 15,
                "review_context": 25,
                "consensus_3_of_3": 3,
                "adjudicated": 2,
                "candidate_replacement": 1,
            },
        )

    def test_five_reviewed_senses_are_complete(self) -> None:
        senses = strict_jsonl(self.output / "reviewed_senses_5.jsonl")
        self.assertEqual(
            {(row["source_term"], row["split_label"]) for row in senses},
            EXPECTED_CASES,
        )
        self.assertTrue(all(row["review_status"] == "COMPLETE" for row in senses))
        self.assertEqual(
            {row["resolution_method"] for row in senses},
            {"CONSENSUS_3_OF_3", "ADJUDICATED"},
        )

    def test_adam_definition_is_adjudicated(self) -> None:
        senses = strict_jsonl(self.output / "reviewed_senses_5.jsonl")
        adam = next(row for row in senses if row["source_term"] == "Adam")
        self.assertEqual(adam["definition_en"], ADAM_DEFINITION)
        self.assertEqual(adam["resolution_method"], "ADJUDICATED")

    def test_statistical_power_candidate_two_is_replaced_with_new_stable_id(self) -> None:
        rows = strict_jsonl(self.output / "reviewed_candidates_15.jsonl")
        replacement = next(
            row
            for row in rows
            if row["source_term"] == "statistical power"
            and row["candidate_slot"] == "CANDIDATE_2"
        )
        self.assertEqual(replacement["candidate_target_vi"], STATISTICAL_POWER_REPLACEMENT)
        self.assertEqual(replacement["candidate_resolution"], "REPLACED_BY_ADJUDICATION")
        self.assertEqual(
            replacement["candidate_id"],
            stable_id(
                "candidate_",
                replacement["output_sense_id"],
                STATISTICAL_POWER_REPLACEMENT,
                "v1",
            ),
        )
        self.assertNotEqual(replacement["candidate_id"], replacement["source_candidate_id"])

    def test_completed_adjudication_is_preserved_byte_identically(self) -> None:
        packaged = self.output / "adjudication_template_2_completed.csv"
        self.assertEqual(packaged.read_bytes(), ADJUDICATION.read_bytes())
        self.assertEqual(sha256_file(packaged), ADJUDICATION_INPUT_SHA256)

    def test_incomplete_adjudication_is_rejected_before_output(self) -> None:
        invalid = self.base / "incomplete.csv"
        rows = read_csv(ADJUDICATION)
        rows[0]["adjudication_status"] = ""
        with invalid.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ADJUDICATION_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        output = self.base / "incomplete-output"
        with self.assertRaisesRegex(ValueError, "input hash mismatch"):
            build_complete_review(
                source_review_root=SOURCE_REVIEW_ROOT,
                source_result_root=SOURCE_RESULT_ROOT,
                adjudication_path=invalid,
                output_root=output,
                created_at="2026-07-29T13:00:00Z",
            )
        self.assertFalse(output.exists())

    def test_source_field_tamper_is_rejected_before_output(self) -> None:
        invalid = self.base / "source-tamper.csv"
        rows = read_csv(ADJUDICATION)
        rows[0]["source_term"] = "changed source"
        with invalid.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ADJUDICATION_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        output = self.base / "source-tamper-output"
        with self.assertRaisesRegex(ValueError, "input hash mismatch"):
            build_complete_review(
                source_review_root=SOURCE_REVIEW_ROOT,
                source_result_root=SOURCE_RESULT_ROOT,
                adjudication_path=invalid,
                output_root=output,
                created_at="2026-07-29T13:00:00Z",
            )
        self.assertFalse(output.exists())

    def test_packaged_candidate_tamper_is_detected(self) -> None:
        tampered = self.base / "tampered-release"
        shutil.copytree(self.output, tampered)
        path = tampered / "reviewed_candidates_15.jsonl"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("độ mạnh của phép kiểm định", "mạnh", 1), encoding="utf-8")
        errors = validate_artifact(tampered)
        self.assertTrue(
            any("candidate" in error or "manifest file inventory" in error for error in errors)
        )

    def test_deterministic_rebuild(self) -> None:
        second = (
            self.base
            / "second"
            / "d2l_stage_a_targeted_repair_review_complete_5_senses_v1"
        )
        result = build_complete_review(
            source_review_root=SOURCE_REVIEW_ROOT,
            source_result_root=SOURCE_RESULT_ROOT,
            adjudication_path=ADJUDICATION,
            output_root=second,
            created_at="2026-07-29T13:00:00Z",
        )
        self.assertEqual(result["manifest_sha256"], self.result["manifest_sha256"])
        self.assertEqual(
            result["reviewer_handoff_zip_sha256"],
            self.result["reviewer_handoff_zip_sha256"],
        )

    def test_zero_provider_zero_contract_zero_gold_zero_final(self) -> None:
        manifest = strict_json_object(self.output / "manifest.json")
        summary = strict_json_object(self.output / "review_complete_summary.json")
        for payload in (manifest, summary):
            self.assertEqual(payload["provider_call_count"], 0)
            self.assertEqual(payload["official_contract_count"], 0)
            self.assertEqual(payload["stage_b_gold_autofill_count"], 0)
            self.assertIsNone(payload["final_glossary_decision"])


if __name__ == "__main__":
    unittest.main()
