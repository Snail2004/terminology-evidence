from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
    strict_jsonl,
    write_json,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_switch_replacement_closure import (
    build_switch_replacement_closure,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_switch_replacement_closure import (
    validate_artifact,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = PACKAGE_ROOT.parent
STAGE_B_50_ROOT = (
    DATASET_ROOT
    / "d2l_dataset_50_senses_fast_track_stage_a_v1"
    / "release"
    / "d2l_dataset_50_senses_150_candidates_stage_b_gold_v1"
)
REMAINING100_ROOT = PACKAGE_ROOT / "release" / "d2l_remaining100_final_closure_v1"
REPLACEMENT_ROOT = (
    PACKAGE_ROOT / "release" / "d2l_switch_replacement_hypothesis_testing_v1"
)
ARTIFACT_ROOT = PACKAGE_ROOT / "release" / "d2l_dataset_150_stage_a_complete_v1"
REVIEWER_1 = ARTIFACT_ROOT / "captured_reviews" / "reviewer_1.json"
REVIEWER_2 = ARTIFACT_ROOT / "captured_reviews" / "reviewer_2.json"


class SwitchReplacementClosureTests(unittest.TestCase):
    def _build(
        self,
        root: Path,
        reviewer_1: Path = REVIEWER_1,
        reviewer_2: Path = REVIEWER_2,
    ) -> tuple[Path, Path]:
        output = root / "artifact"
        zip_path = root / "artifact.zip"
        build_switch_replacement_closure(
            stage_b_50_root=STAGE_B_50_ROOT,
            remaining100_root=REMAINING100_ROOT,
            replacement_root=REPLACEMENT_ROOT,
            reviewer_1_response=reviewer_1,
            reviewer_2_response=reviewer_2,
            output_root=output,
            zip_path=zip_path,
        )
        return output, zip_path

    def test_release_validates(self) -> None:
        self.assertEqual(validate_artifact(ARTIFACT_ROOT), [])

    def test_exact_completion_counts(self) -> None:
        summary = strict_json_object(ARTIFACT_ROOT / "completion_summary.json")
        self.assertEqual(summary["stage_a_ready_source_slot_count"], 150)
        self.assertEqual(summary["stage_a_blocked_source_slot_count"], 0)
        self.assertEqual(summary["effective_sense_count"], 155)
        self.assertEqual(summary["candidate_instance_count"], 450)
        slots = strict_jsonl(ARTIFACT_ROOT / "stage_a_source_slot_index_150.jsonl")
        self.assertEqual(len(slots), 150)
        replacement = [row for row in slots if row["is_replacement"]]
        self.assertEqual(len(replacement), 1)
        self.assertEqual(replacement[0]["effective_source_term"], "hypothesis testing")

    def test_rebuild_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first_name, tempfile.TemporaryDirectory() as second_name:
            first_root, first_zip = self._build(Path(first_name))
            second_root, second_zip = self._build(Path(second_name))
            self.assertEqual(sha256_file(first_zip), sha256_file(second_zip))
            self.assertEqual(
                strict_json_object(first_root / "manifest.json"),
                strict_json_object(second_root / "manifest.json"),
            )

    def test_same_review_path_rejects_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with self.assertRaisesRegex(ValueError, "two distinct paths"):
                self._build(root, REVIEWER_1, REVIEWER_1)
            self.assertFalse((root / "artifact").exists())
            self.assertFalse((root / "artifact.zip").exists())

    def test_source_mutation_rejects_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            tampered = root / "reviewer_1.json"
            payload = json.loads(REVIEWER_1.read_text(encoding="utf-8"))
            payload["cases"][0]["source_payload"]["source_term"] = "tampered"
            write_json(tampered, payload)
            with self.assertRaisesRegex(ValueError, "immutable source payload changed"):
                self._build(root, tampered, REVIEWER_2)
            self.assertFalse((root / "artifact").exists())
            self.assertFalse((root / "artifact.zip").exists())

    def test_nonaccept_rejects_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            rejected = root / "reviewer_2.json"
            payload = json.loads(REVIEWER_2.read_text(encoding="utf-8"))
            payload["cases"][0]["review"]["evidence_decision"] = "UNJUDGEABLE"
            write_json(rejected, payload)
            with self.assertRaisesRegex(ValueError, "evidence_decision is not ACCEPT"):
                self._build(root, REVIEWER_1, rejected)
            self.assertFalse((root / "artifact").exists())
            self.assertFalse((root / "artifact.zip").exists())


if __name__ == "__main__":
    unittest.main()
