from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_jsonl,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_gold import (
    ARTIFACT_NAME,
    build_artifact,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.remaining_stage_b_adjudication_result import (
    validate_completed_adjudication,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_remaining_stage_b_gold import (
    validate_artifact,
)


NAMESPACE = Path(__file__).resolve().parents[1]
DATASET = (
    NAMESPACE
    / "release"
    / "d2l_dataset_remaining_300_candidates_stage_b_review_v1"
)
INTAKE = NAMESPACE / "release" / "d2l_stage_b_r1_repair_v1"


def _complete_adjudication(path: Path) -> None:
    payload = json.loads(
        (INTAKE / "reviewer_3_adjudication_input.json").read_text(encoding="utf-8")
    )
    for case in payload["cases"]:
        case["adjudication"] = {
            "adjudicator_label": case["disagreement"]["reviewer_1_label"],
            "adjudication_reason": "Focused test selects Reviewer 1 after evidence review.",
            "adjudication_status": "COMPLETE",
        }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class RemainingStageBGoldTests(unittest.TestCase):
    def test_completed_adjudication_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer_3.json"
            _complete_adjudication(result)
            validated, errors = validate_completed_adjudication(
                INTAKE / "reviewer_3_adjudication_input.json", result
            )
            self.assertEqual(errors, [])
            self.assertEqual(len(validated.cases_by_candidate), 55)

    def test_builds_complete_300_candidate_gold(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "reviewer_3.json"
            _complete_adjudication(result)
            output = root / ARTIFACT_NAME
            manifest = build_artifact(
                dataset_artifact_root=DATASET,
                review_intake_root=INTAKE,
                reviewer_3_path=result,
                output_root=output,
            )
            self.assertEqual(manifest["source_slot_count"], 100)
            self.assertEqual(manifest["effective_sense_count"], 105)
            self.assertEqual(manifest["candidate_count"], 300)
            self.assertEqual(manifest["final_gold_label_count"], 300)
            self.assertEqual(manifest["adjudication_count"], 55)
            self.assertEqual(
                validate_artifact(
                    output,
                    dataset_artifact_root=DATASET,
                    review_intake_root=INTAKE,
                ),
                [],
            )
            gold = strict_jsonl(output / "stage_b_gold_300.jsonl")
            self.assertEqual(
                {row["review_resolution"] for row in gold},
                {"DUAL_REVIEW_CONSENSUS", "REVIEWER_3_ADJUDICATED"},
            )

    def test_adjudication_source_tamper_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "reviewer_3.json"
            _complete_adjudication(result)
            payload = json.loads(result.read_text(encoding="utf-8"))
            payload["cases"][0]["candidate_id"] = "candidate_tampered"
            result.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            output = root / ARTIFACT_NAME
            with self.assertRaises(ValueError):
                build_artifact(
                    dataset_artifact_root=DATASET,
                    review_intake_root=INTAKE,
                    reviewer_3_path=result,
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_incomplete_adjudication_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "reviewer_3.json"
            _complete_adjudication(result)
            payload = json.loads(result.read_text(encoding="utf-8"))
            payload["cases"][0]["adjudication"]["adjudication_status"] = ""
            result.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            output = root / ARTIFACT_NAME
            with self.assertRaisesRegex(ValueError, "adjudication_status"):
                build_artifact(
                    dataset_artifact_root=DATASET,
                    review_intake_root=INTAKE,
                    reviewer_3_path=result,
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_gold_mutation_fails_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "reviewer_3.json"
            _complete_adjudication(result)
            output = root / ARTIFACT_NAME
            build_artifact(
                dataset_artifact_root=DATASET,
                review_intake_root=INTAKE,
                reviewer_3_path=result,
                output_root=output,
            )
            path = output / "stage_b_gold_300.jsonl"
            rows = strict_jsonl(path)
            rows[0]["final_gold_label"] = "REJECT"
            path.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )
            errors = validate_artifact(
                output,
                dataset_artifact_root=DATASET,
                review_intake_root=INTAKE,
            )
            self.assertTrue(errors)

    def test_two_builds_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "reviewer_3.json"
            _complete_adjudication(result)
            first = root / "first" / ARTIFACT_NAME
            second = root / "second" / ARTIFACT_NAME
            build_artifact(
                dataset_artifact_root=DATASET,
                review_intake_root=INTAKE,
                reviewer_3_path=result,
                output_root=first,
            )
            build_artifact(
                dataset_artifact_root=DATASET,
                review_intake_root=INTAKE,
                reviewer_3_path=result,
                output_root=second,
            )
            self.assertEqual(
                sha256_file(first.parent / f"{ARTIFACT_NAME}.zip"),
                sha256_file(second.parent / f"{ARTIFACT_NAME}.zip"),
            )


if __name__ == "__main__":
    unittest.main()
