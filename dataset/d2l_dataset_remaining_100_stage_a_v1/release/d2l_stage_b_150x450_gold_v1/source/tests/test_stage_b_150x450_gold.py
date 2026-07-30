from __future__ import annotations

import copy
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_jsonl,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_stage_b_150x450_gold import (
    ARTIFACT_NAME,
    _load_sources,
    _project_rows,
    build_artifact,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_stage_b_150x450_gold import (
    validate_artifact,
)


NAMESPACE = Path(__file__).resolve().parents[1]
STAGE_A = NAMESPACE / "release" / "d2l_dataset_150_stage_a_complete_v1"
BASELINE = (
    NAMESPACE.parents[0]
    / "d2l_dataset_50_senses_fast_track_stage_a_v1"
    / "release"
    / "d2l_dataset_50_senses_150_candidates_stage_b_gold_v1"
)
REMAINING = NAMESPACE / "release" / "d2l_stage_b_300_gold_v1"


class StageB150x450GoldTests(unittest.TestCase):
    def test_builds_and_validates_full_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / ARTIFACT_NAME
            manifest = build_artifact(
                stage_a_complete_root=STAGE_A,
                baseline_gold_root=BASELINE,
                remaining_gold_root=REMAINING,
                output_root=output,
            )
            self.assertEqual(manifest["source_slot_count"], 150)
            self.assertEqual(manifest["effective_sense_count"], 155)
            self.assertEqual(manifest["candidate_count"], 450)
            self.assertEqual(manifest["final_gold_label_count"], 450)
            self.assertEqual(manifest["adjudication_count"], 74)
            self.assertEqual(
                validate_artifact(
                    output,
                    stage_a_complete_root=STAGE_A,
                    baseline_gold_root=BASELINE,
                    remaining_gold_root=REMAINING,
                ),
                [],
            )

    def test_projection_has_exact_population_and_labels(self) -> None:
        sources = _load_sources(
            stage_a_complete_root=STAGE_A,
            baseline_gold_root=BASELINE,
            remaining_gold_root=REMAINING,
        )
        rows = _project_rows(sources)
        self.assertEqual(len(rows), 450)
        self.assertEqual(len({row["source_slot_sense_id"] for row in rows}), 150)
        self.assertEqual(len({row["effective_sense_id"] for row in rows}), 155)
        self.assertEqual(
            Counter(row["final_gold_label"] for row in rows),
            Counter(
                {
                    "ACCEPT": 328,
                    "CONDITIONAL": 100,
                    "REJECT": 16,
                    "SPLIT_REQUIRED": 6,
                }
            ),
        )

    def test_candidate_overlap_rejects(self) -> None:
        sources = _load_sources(
            stage_a_complete_root=STAGE_A,
            baseline_gold_root=BASELINE,
            remaining_gold_root=REMAINING,
        )
        tampered = copy.deepcopy(sources)
        tampered["remaining"][0]["candidate_id"] = tampered["baseline"][0][
            "candidate_id"
        ]
        with self.assertRaisesRegex(ValueError, "candidate population mismatch"):
            _project_rows(tampered)

    def test_projection_mutation_fails_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / ARTIFACT_NAME
            build_artifact(
                stage_a_complete_root=STAGE_A,
                baseline_gold_root=BASELINE,
                remaining_gold_root=REMAINING,
                output_root=output,
            )
            path = output / "stage_b_gold_450.jsonl"
            rows = strict_jsonl(path)
            rows[0]["final_gold_label"] = "REJECT"
            path.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(
                validate_artifact(
                    output,
                    stage_a_complete_root=STAGE_A,
                    baseline_gold_root=BASELINE,
                    remaining_gold_root=REMAINING,
                )
            )

    def test_partition_bytes_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / ARTIFACT_NAME
            build_artifact(
                stage_a_complete_root=STAGE_A,
                baseline_gold_root=BASELINE,
                remaining_gold_root=REMAINING,
                output_root=output,
            )
            self.assertEqual(
                sha256_file(BASELINE / "stage_b_gold_150.jsonl"),
                sha256_file(
                    output / "partitions" / "baseline_stage_b_gold_150.jsonl"
                ),
            )
            self.assertEqual(
                sha256_file(REMAINING / "stage_b_gold_300.jsonl"),
                sha256_file(
                    output / "partitions" / "remaining_stage_b_gold_300.jsonl"
                ),
            )

    def test_two_builds_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first" / ARTIFACT_NAME
            second = root / "second" / ARTIFACT_NAME
            build_artifact(
                stage_a_complete_root=STAGE_A,
                baseline_gold_root=BASELINE,
                remaining_gold_root=REMAINING,
                output_root=first,
            )
            build_artifact(
                stage_a_complete_root=STAGE_A,
                baseline_gold_root=BASELINE,
                remaining_gold_root=REMAINING,
                output_root=second,
            )
            self.assertEqual(
                sha256_file(first.parent / f"{ARTIFACT_NAME}.zip"),
                sha256_file(second.parent / f"{ARTIFACT_NAME}.zip"),
            )


if __name__ == "__main__":
    unittest.main()
