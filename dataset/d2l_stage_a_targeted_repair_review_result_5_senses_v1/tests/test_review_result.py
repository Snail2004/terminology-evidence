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

from tools.build_review_result import build_review_result  # noqa: E402
from tools.common import read_csv, sha256_file, strict_json_object, strict_jsonl  # noqa: E402
from tools.spec import (  # noqa: E402
    ADJUDICATION_CASES,
    ADJUDICATION_CSV_FIELDS,
    ADJUDICATION_OUTPUT_FIELDS,
    CONSENSUS_CASES,
    REVIEW_CSV_FIELDS,
    REVIEW_INPUT_SHA256,
    REVIEWER_SLOTS,
)
from tools.validate_review_result import validate_artifact, validate_zip  # noqa: E402


SOURCE_REVIEW_ROOT = (
    REPO_ROOT
    / "dataset"
    / "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
    / "release"
    / "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
)
INPUTS = {slot: NAMESPACE / "inputs" / f"{slot}.csv" for slot in REVIEWER_SLOTS}


class TargetedRepairReviewResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.output = (
            cls.base
            / "first"
            / "d2l_stage_a_targeted_repair_review_result_5_senses_v1"
        )
        cls.result = build_review_result(
            source_review_root=SOURCE_REVIEW_ROOT,
            review_paths=INPUTS,
            output_root=cls.output,
            created_at="2026-07-29T12:00:00Z",
        )
        cls.zip_path = cls.output.parent / (
            "d2l_stage_a_targeted_repair_review_result_5_senses_v1_"
            "adjudication_handoff.zip"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_release_validates_with_exact_counts(self) -> None:
        self.assertEqual(self.result["status"], "ADJUDICATION_REQUIRED")
        self.assertEqual(validate_artifact(self.output), [])
        self.assertEqual(validate_zip(self.zip_path, self.output), [])
        self.assertEqual(
            self.result["counts"],
            {
                "review_case": 5,
                "review_input": 3,
                "consensus_3_of_3": 3,
                "adjudication_required": 2,
            },
        )

    def test_result_classifies_three_consensus_and_two_adjudication_cases(self) -> None:
        consensus = strict_jsonl(self.output / "consensus_3_of_3_3.jsonl")
        adjudication = strict_jsonl(self.output / "adjudication_required_2.jsonl")
        self.assertEqual(
            {(row["source_term"], row["split_label"]) for row in consensus},
            CONSENSUS_CASES,
        )
        self.assertEqual(
            {
                (row["source_term"], row["split_label"]): row["issue_type"]
                for row in adjudication
            },
            ADJUDICATION_CASES,
        )
        self.assertTrue(
            all(row["consensus_status"] == "AGREEMENT_3_OF_3" for row in consensus)
        )

    def test_review_inputs_are_preserved_byte_identically(self) -> None:
        for slot in REVIEWER_SLOTS:
            source = INPUTS[slot]
            packaged = self.output / "review_inputs" / f"{slot}.csv"
            self.assertEqual(source.read_bytes(), packaged.read_bytes())
            self.assertEqual(sha256_file(packaged), REVIEW_INPUT_SHA256[slot])

    def test_adjudication_template_has_two_blank_output_rows(self) -> None:
        path = self.output / "adjudication_template_2.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, list(ADJUDICATION_CSV_FIELDS))
            rows = list(reader)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["source_term"] for row in rows}, {"Adam", "statistical power"})
        self.assertTrue(
            all(row[field] == "" for row in rows for field in ADJUDICATION_OUTPUT_FIELDS)
        )

    def test_same_physical_input_in_three_slots_is_rejected_before_output(self) -> None:
        output = self.base / "same-path-output"
        shared = INPUTS["reviewer_1"]
        with self.assertRaisesRegex(ValueError, "three distinct physical paths"):
            build_review_result(
                source_review_root=SOURCE_REVIEW_ROOT,
                review_paths={slot: shared for slot in REVIEWER_SLOTS},
                output_root=output,
                created_at="2026-07-29T12:00:00Z",
            )
        self.assertFalse(output.exists())

    def test_wrong_reviewer_cardinality_is_rejected_before_output(self) -> None:
        output = self.base / "wrong-cardinality-output"
        with self.assertRaisesRegex(ValueError, "three named reviewer slots"):
            build_review_result(
                source_review_root=SOURCE_REVIEW_ROOT,
                review_paths={
                    "reviewer_1": INPUTS["reviewer_1"],
                    "reviewer_2": INPUTS["reviewer_2"],
                },
                output_root=output,
                created_at="2026-07-29T12:00:00Z",
            )
        self.assertFalse(output.exists())

    def test_input_tamper_is_rejected_before_output(self) -> None:
        tampered = self.base / "tampered-reviewer-1.csv"
        rows = read_csv(INPUTS["reviewer_1"])
        rows[0]["source_term"] = "changed source"
        with tampered.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        output = self.base / "tampered-output"
        paths = dict(INPUTS)
        paths["reviewer_1"] = tampered
        with self.assertRaisesRegex(ValueError, "review input hash mismatch"):
            build_review_result(
                source_review_root=SOURCE_REVIEW_ROOT,
                review_paths=paths,
                output_root=output,
                created_at="2026-07-29T12:00:00Z",
            )
        self.assertFalse(output.exists())

    def test_packaged_result_tamper_is_detected(self) -> None:
        tampered = self.base / "tampered-release"
        shutil.copytree(self.output, tampered)
        path = tampered / "adjudication_template_2.csv"
        rows = read_csv(path)
        rows[0]["adjudicated_definition_en"] = "prefilled"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ADJUDICATION_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        errors = validate_artifact(tampered)
        self.assertTrue(any("prefilled" in error for error in errors))

    def test_deterministic_rebuild(self) -> None:
        second = (
            self.base
            / "second"
            / "d2l_stage_a_targeted_repair_review_result_5_senses_v1"
        )
        result = build_review_result(
            source_review_root=SOURCE_REVIEW_ROOT,
            review_paths=INPUTS,
            output_root=second,
            created_at="2026-07-29T12:00:00Z",
        )
        self.assertEqual(result["manifest_sha256"], self.result["manifest_sha256"])
        self.assertEqual(
            result["adjudication_handoff_zip_sha256"],
            self.result["adjudication_handoff_zip_sha256"],
        )

    def test_zero_provider_zero_contract_zero_final(self) -> None:
        manifest = strict_json_object(self.output / "manifest.json")
        summary = strict_json_object(self.output / "review_summary.json")
        for payload in (manifest, summary):
            self.assertEqual(payload["provider_call_count"], 0)
            self.assertEqual(payload["official_contract_count"], 0)
            self.assertIsNone(payload["final_glossary_decision"])


if __name__ == "__main__":
    unittest.main()
