from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
    strict_jsonl,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_review import (
    build_remaining_stage_b_review,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_remaining_stage_b_review import (
    FORBIDDEN_REVIEW_KEYS,
    validate_artifact,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = PACKAGE_ROOT.parent
V3_ROOT = DATASET_ROOT / "d2l_context_support_set_validation_ready_v3"
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
STAGE_A_COMPLETE_ROOT = (
    PACKAGE_ROOT / "release" / "d2l_dataset_150_stage_a_complete_v1"
)
ARTIFACT_ROOT = (
    PACKAGE_ROOT
    / "release"
    / "d2l_dataset_remaining_300_candidates_stage_b_review_v1"
)


class RemainingStageBReviewTests(unittest.TestCase):
    def _build(self, root: Path) -> tuple[Path, Path]:
        output = root / "artifact"
        zip_path = root / "artifact.zip"
        build_remaining_stage_b_review(
            v3_root=V3_ROOT,
            stage_b_50_root=STAGE_B_50_ROOT,
            remaining100_root=REMAINING100_ROOT,
            replacement_root=REPLACEMENT_ROOT,
            stage_a_complete_root=STAGE_A_COMPLETE_ROOT,
            output_root=output,
            zip_path=zip_path,
        )
        return output, zip_path

    def test_release_validates(self) -> None:
        self.assertEqual(validate_artifact(ARTIFACT_ROOT), [])

    def test_exact_counts_and_batches(self) -> None:
        senses = strict_jsonl(ARTIFACT_ROOT / "effective_senses_105.jsonl")
        candidates = strict_jsonl(ARTIFACT_ROOT / "candidate_instances_300.jsonl")
        batch_index = strict_json_object(ARTIFACT_ROOT / "batch_index.json")
        self.assertEqual(len(senses), 105)
        self.assertEqual(len(candidates), 300)
        self.assertEqual(len(batch_index["batches"]), 10)
        self.assertEqual(
            [row["candidate_count"] for row in batch_index["batches"]],
            [30] * 10,
        )

    def test_reviewer_inputs_are_blind_and_complete(self) -> None:
        payloads = [
            strict_json_object(ARTIFACT_ROOT / f"reviewer_{index}_full_input.json")
            for index in (1, 2)
        ]
        for payload in payloads:
            self.assertEqual(payload["case_count"], 300)
            self.assertEqual(len(payload["cases"]), 300)
            raw = json.dumps(payload, ensure_ascii=False)
            for forbidden in FORBIDDEN_REVIEW_KEYS:
                self.assertNotIn(f'"{forbidden}"', raw)
            self.assertNotIn('"candidate_gold_label": "ACCEPT"', raw)
            self.assertNotIn('"final_gold_label": "', raw)
        left = {
            case["source_payload"]["candidate_id"]: case["source_payload"]
            for case in payloads[0]["cases"]
        }
        right = {
            case["source_payload"]["candidate_id"]: case["source_payload"]
            for case in payloads[1]["cases"]
        }
        self.assertEqual(left, right)

    def test_split_candidate_partition_is_exact(self) -> None:
        candidates = strict_jsonl(ARTIFACT_ROOT / "candidate_instances_300.jsonl")
        split = [
            row
            for row in candidates
            if str(row["effective_sense_id"]).startswith("tmpchild_")
        ]
        self.assertEqual(len(split), 12)
        self.assertEqual(len({row["candidate_id"] for row in split}), 12)
        self.assertEqual(len({row["effective_sense_id"] for row in split}), 9)

    def test_rebuild_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first_name, tempfile.TemporaryDirectory() as second_name:
            first_root, first_zip = self._build(Path(first_name))
            second_root, second_zip = self._build(Path(second_name))
            self.assertEqual(sha256_file(first_zip), sha256_file(second_zip))
            self.assertEqual(
                strict_json_object(first_root / "manifest.json"),
                strict_json_object(second_root / "manifest.json"),
            )

    def test_parent_manifest_drift_rejects_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            copied = root / "stage_a_complete"
            import shutil

            shutil.copytree(STAGE_A_COMPLETE_ROOT, copied)
            manifest = strict_json_object(copied / "manifest.json")
            manifest["status"] = "TAMPERED"
            (copied / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "manifest self-hash mismatch"):
                build_remaining_stage_b_review(
                    v3_root=V3_ROOT,
                    stage_b_50_root=STAGE_B_50_ROOT,
                    remaining100_root=REMAINING100_ROOT,
                    replacement_root=REPLACEMENT_ROOT,
                    stage_a_complete_root=copied,
                    output_root=root / "artifact",
                    zip_path=root / "artifact.zip",
                )
            self.assertFalse((root / "artifact").exists())
            self.assertFalse((root / "artifact.zip").exists())


if __name__ == "__main__":
    unittest.main()
