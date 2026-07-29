from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


NAMESPACE = Path(__file__).resolve().parents[1]
REPO_ROOT = NAMESPACE.parents[1]
if str(NAMESPACE) not in sys.path:
    sys.path.insert(0, str(NAMESPACE))

from tools.build_review_pack import build_review_pack  # noqa: E402
from tools.common import read_csv, strict_json_object, strict_jsonl  # noqa: E402
from tools.spec import (  # noqa: E402
    EXPECTED_BLOCK_IDS,
    EXPECTED_OUTPUT_SENSE_IDS,
    EXPECTED_PARENT_IDS,
    REVIEW_CSV_FIELDS,
    REVIEW_HUMAN_FIELDS,
    REVIEWER_SLOTS,
)
from tools.validate_review_pack import (  # noqa: E402
    _load_records,
    _validate_reviews,
    validate_artifact,
    validate_zip,
)


V3_ROOT = REPO_ROOT / "dataset" / "d2l_context_support_set_validation_ready_v3"
REVIEWED_ROOT = (
    REPO_ROOT
    / "dataset"
    / "d2l_stage_a_pilot_15_senses_reviewed_v1"
    / "release"
    / "d2l_stage_a_pilot_15_senses_reviewed_v1"
)
OFFICIAL_11_ROOT = (
    REPO_ROOT
    / "dataset"
    / "d2l_stage_a_pilot_11_senses_official_v1"
    / "release"
    / "d2l_stage_a_pilot_11_senses_official_v1"
)
SOURCE_DOCUMENT = (
    REPO_ROOT.parents[1]
    / "agent-based-translation-d2l-direct-builder-v1"
    / "jobs"
    / "src_d2l_full_book_local_b858af3a5252"
    / "source_package_snapshot"
    / "document.json"
)


class TargetedRepairReviewPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.output = cls.base / "first" / "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
        cls.output.parent.mkdir()
        cls.result = build_review_pack(
            repo_root=REPO_ROOT,
            v3_root=V3_ROOT,
            reviewed_root=REVIEWED_ROOT,
            official_11_root=OFFICIAL_11_ROOT,
            source_document=SOURCE_DOCUMENT,
            output_root=cls.output,
            created_at="2026-07-29T10:00:00Z",
        )
        cls.zip_path = cls.output.parent / (
            "d2l_stage_a_targeted_repair_review_pack_5_senses_v1_reviewer_handoff.zip"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_release_validates_and_has_exact_counts(self) -> None:
        self.assertEqual(self.result["status"], "READY_FOR_TARGETED_HUMAN_REVIEW")
        self.assertEqual(validate_artifact(self.output, SOURCE_DOCUMENT), [])
        self.assertEqual(validate_zip(self.zip_path, self.output), [])
        self.assertEqual(
            self.result["counts"],
            {
                "parent": 4,
                "output_sense": 5,
                "candidate": 15,
                "review_context": 25,
                "rejected_parent_evidence": 2,
                "reviewer_template": 3,
            },
        )

    def test_exact_five_cases_use_twenty_five_corpus_blocks(self) -> None:
        proposals = strict_jsonl(self.output / "repair_sense_proposals_5.jsonl")
        evidence = strict_jsonl(self.output / "evidence_contexts_25.jsonl")
        self.assertEqual({row["output_sense_id"] for row in proposals}, EXPECTED_OUTPUT_SENSE_IDS)
        self.assertEqual({row["parent_sense_id"] for row in proposals}, EXPECTED_PARENT_IDS)
        self.assertEqual({row["block_id"] for row in evidence}, EXPECTED_BLOCK_IDS)
        self.assertEqual(
            Counter(row["output_sense_id"] for row in evidence),
            Counter({sense_id: 5 for sense_id in EXPECTED_OUTPUT_SENSE_IDS}),
        )
        self.assertTrue(all(row["synthetic"] is False for row in evidence))

    def test_candidates_are_three_distinct_values_per_sense(self) -> None:
        rows = strict_jsonl(self.output / "candidate_proposals_15.jsonl")
        self.assertEqual(len({row["candidate_id"] for row in rows}), 15)
        for sense_id in EXPECTED_OUTPUT_SENSE_IDS:
            selected = [row for row in rows if row["output_sense_id"] == sense_id]
            self.assertEqual(len(selected), 3)
            self.assertEqual(
                len({row["candidate_target_vi"].casefold() for row in selected}), 3
            )
        self.assertEqual(
            Counter(row["formation_method"] for row in rows),
            Counter({"REUSE_V3_CANDIDATE": 9, "DATASET_TARGETED_REPAIR_PROPOSAL": 6}),
        )

    def test_three_templates_are_blank_and_source_identical(self) -> None:
        source_rows = None
        for slot in REVIEWER_SLOTS:
            path = self.output / "reviewer_templates" / f"{slot}.csv"
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, list(REVIEW_CSV_FIELDS))
                rows = list(reader)
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row["reviewer_slot"] == slot for row in rows))
            self.assertTrue(
                all(row[field] == "" for row in rows for field in REVIEW_HUMAN_FIELDS)
            )
            current = [
                {key: value for key, value in row.items() if key != "reviewer_slot"}
                for row in rows
            ]
            if source_rows is None:
                source_rows = current
            else:
                self.assertEqual(current, source_rows)

    def test_source_field_tamper_is_rejected(self) -> None:
        tampered = self.base / "tampered-source"
        shutil.copytree(self.output, tampered)
        path = tampered / "reviewer_templates" / "reviewer_1.csv"
        rows = read_csv(path)
        rows[0]["source_term"] = "changed source"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        errors: list[str] = []
        records = _load_records(tampered, errors)
        _validate_reviews(tampered, records, errors)
        self.assertTrue(any("review source payload mismatch" in row for row in errors))

    def test_prefilled_human_field_is_rejected(self) -> None:
        tampered = self.base / "tampered-human"
        shutil.copytree(self.output, tampered)
        path = tampered / "reviewer_templates" / "reviewer_2.csv"
        rows = read_csv(path)
        rows[0]["definition_decision"] = "ACCEPT"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        errors: list[str] = []
        records = _load_records(tampered, errors)
        _validate_reviews(tampered, records, errors)
        self.assertTrue(any("review template is prefilled" in row for row in errors))

    def test_wrong_source_document_is_rejected_before_output(self) -> None:
        invalid_document = self.base / "wrong-document.json"
        invalid_document.write_text("{}\n", encoding="utf-8")
        output = self.base / "wrong-source-output"
        with self.assertRaisesRegex(ValueError, "source document physical hash mismatch"):
            build_review_pack(
                repo_root=REPO_ROOT,
                v3_root=V3_ROOT,
                reviewed_root=REVIEWED_ROOT,
                official_11_root=OFFICIAL_11_ROOT,
                source_document=invalid_document,
                output_root=output,
                created_at="2026-07-29T10:00:00Z",
            )
        self.assertFalse(output.exists())

    def test_rejected_parent_evidence_is_not_positive_support(self) -> None:
        rejected = strict_jsonl(self.output / "rejected_parent_evidence_2.jsonl")
        evidence = strict_jsonl(self.output / "evidence_contexts_25.jsonl")
        self.assertEqual(
            {row["rejection_reason"] for row in rejected},
            {
                "WRONG_SENSE_EXPRESSIVE_POWER",
                "SYNTHETIC_BOUNDARY_NOT_POSITIVE_EVIDENCE",
            },
        )
        self.assertTrue(all(row["excluded_from_positive_evidence"] for row in rejected))
        self.assertTrue(
            {row["source_context_id"] for row in rejected}.isdisjoint(
                {row["context_id"] for row in evidence}
            )
        )

    def test_deterministic_rebuild(self) -> None:
        second = self.base / "second" / "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
        second.parent.mkdir()
        result = build_review_pack(
            repo_root=REPO_ROOT,
            v3_root=V3_ROOT,
            reviewed_root=REVIEWED_ROOT,
            official_11_root=OFFICIAL_11_ROOT,
            source_document=SOURCE_DOCUMENT,
            output_root=second,
            created_at="2026-07-29T10:00:00Z",
        )
        self.assertEqual(result["manifest_sha256"], self.result["manifest_sha256"])
        self.assertEqual(
            result["reviewer_handoff_zip_sha256"],
            self.result["reviewer_handoff_zip_sha256"],
        )

    def test_zero_provider_zero_gold_zero_final(self) -> None:
        acceptance = strict_json_object(self.output / "acceptance_gate_report.json")
        manifest = strict_json_object(self.output / "manifest.json")
        for payload in (acceptance, manifest):
            self.assertEqual(payload["provider_call_count"], 0)
            self.assertEqual(payload["stage_b_gold_autofill_count"], 0)
            self.assertIsNone(payload["final_glossary_decision"])


if __name__ == "__main__":
    unittest.main()
