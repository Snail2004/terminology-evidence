from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from build_stage_a_adjudication_result import build_adjudication_result  # noqa: E402
from common import sha256_file, strict_json_object, strict_jsonl  # noqa: E402
from spec import CREATED_AT_DEFAULT  # noqa: E402
from validate_stage_a_adjudication_result import (  # noqa: E402
    validate_result,
    validate_zip,
)


INTAKE_ROOT = PACKAGE_ROOT / "release" / "d2l_fast_track_stage_a_review_intake_v1"
REVIEWER_3_ROOT = INTAKE_ROOT / "handoff" / "result-reviewer3"


def _build(output: Path, reviewer_3_root: Path = REVIEWER_3_ROOT):
    return build_adjudication_result(
        intake_root=INTAKE_ROOT,
        reviewer_3_root=reviewer_3_root,
        output_root=output,
        created_at=CREATED_AT_DEFAULT,
    )


class StageAAdjudicationResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.temporary.name)
        cls.source_hashes = {
            path.resolve(): sha256_file(path) for path in REVIEWER_3_ROOT.glob("*.json")
        }
        cls.artifact_root = cls.temp_root / "adjudication"
        cls.result = _build(cls.artifact_root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_all_results_validate_and_release_zip_matches(self) -> None:
        self.assertEqual(validate_result(self.artifact_root, intake_root=INTAKE_ROOT), [])
        self.assertEqual(
            validate_zip(Path(self.result["release_zip"]), self.artifact_root), []
        )
        manifest = strict_json_object(self.artifact_root / "manifest.json")
        self.assertEqual(manifest["reviewer_3_result_file_count"], 9)
        self.assertEqual(manifest["adjudicated_case_count"], 24)

    def test_result_summary_preserves_boundaries_and_r0_queue(self) -> None:
        report = strict_json_object(self.artifact_root / "adjudication_report.json")
        summary = report["summary"]
        self.assertEqual(summary["ready_for_contract_construction_count"], 24)
        self.assertEqual(
            summary["decision_counts"]["candidate_set_decision"],
            {"ACCEPT": 6, "REVISE": 18},
        )
        self.assertEqual(summary["candidate_replacement_count"], 26)
        self.assertEqual(
            summary["stage_a_new_sense_funnel"],
            {
                "new_sense_count": 44,
                "r0_ready_without_adjudication": 9,
                "r3_ready_by_two_reviewer_agreement": 7,
                "ready_after_reviewer_3_adjudication": 24,
                "ready_for_contract_construction_total": 40,
                "r0_repair_and_reaudit_pending": 4,
            },
        )
        self.assertEqual(report["provider_call_count"], 0)
        self.assertEqual(report["stage_b_gold_autofill_count"], 0)
        self.assertIsNone(report["final_glossary_decision"])
        self.assertEqual(
            len(strict_jsonl(self.artifact_root / "pending" / "r0_repair_queue_4.jsonl")),
            4,
        )

    def test_raw_copies_are_identical_and_sources_untouched(self) -> None:
        inventory = strict_json_object(self.artifact_root / "input_inventory.json")
        self.assertEqual(inventory["result_file_count"], 9)
        self.assertEqual(inventory["case_count"], 24)
        for row in inventory["files"]:
            captured = self.artifact_root / row["captured_relative_path"]
            self.assertEqual(row["source_sha256"], row["captured_sha256"])
            self.assertEqual(sha256_file(captured), row["captured_sha256"])
        for path, digest in self.source_hashes.items():
            self.assertEqual(sha256_file(path), digest)

    def test_source_or_prior_review_tamper_rejects_without_output(self) -> None:
        tampered = self.temp_root / "tampered_source"
        shutil.copytree(REVIEWER_3_ROOT, tampered)
        path = tampered / "batch_001_reviewer_3_completed.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["source_payload"]["source_term"] += " tampered"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        output = self.temp_root / "tampered_source_output"
        with self.assertRaisesRegex(ValueError, "immutable case field changed"):
            _build(output, tampered)
        self.assertFalse(output.exists())

    def test_incomplete_adjudication_rejects_without_output(self) -> None:
        incomplete = self.temp_root / "incomplete"
        shutil.copytree(REVIEWER_3_ROOT, incomplete)
        path = incomplete / "batch_001_reviewer_3_completed.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["adjudication"]["adjudication_status"] = ""
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        output = self.temp_root / "incomplete_output"
        with self.assertRaisesRegex(ValueError, "adjudication_status must be COMPLETE"):
            _build(output, incomplete)
        self.assertFalse(output.exists())

    def test_unbound_candidate_replacement_rejects_without_output(self) -> None:
        invalid = self.temp_root / "invalid_replacement"
        shutil.copytree(REVIEWER_3_ROOT, invalid)
        path = invalid / "batch_003_reviewer_3_completed.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        replacement = payload["cases"][0]["adjudication"]["candidate_replacements"][0]
        replacement["candidate_id"] = "candidate_not_in_source"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        output = self.temp_root / "invalid_replacement_output"
        with self.assertRaisesRegex(ValueError, "replacement target is not a source candidate"):
            _build(output, invalid)
        self.assertFalse(output.exists())

    def test_duplicate_effective_candidate_targets_reject_without_output(self) -> None:
        invalid = self.temp_root / "duplicate_candidate"
        shutil.copytree(REVIEWER_3_ROOT, invalid)
        path = invalid / "batch_003_reviewer_3_completed.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        case = payload["cases"][0]
        replacement = case["adjudication"]["candidate_replacements"][0]
        untouched = next(
            row
            for row in case["source_payload"]["candidates"]
            if row["candidate_id"] != replacement["candidate_id"]
        )
        replacement["replacement_target_vi"] = untouched["candidate_target_vi"]
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        output = self.temp_root / "duplicate_candidate_output"
        with self.assertRaisesRegex(ValueError, "effective candidate targets must remain distinct"):
            _build(output, invalid)
        self.assertFalse(output.exists())

    def test_release_is_deterministic(self) -> None:
        second_root = self.temp_root / "second" / "adjudication"
        second_root.parent.mkdir()
        second = _build(second_root)
        self.assertEqual(
            sha256_file(self.artifact_root / "manifest.json"),
            sha256_file(second_root / "manifest.json"),
        )
        self.assertEqual(self.result["release_zip_sha256"], second["release_zip_sha256"])


if __name__ == "__main__":
    unittest.main()
