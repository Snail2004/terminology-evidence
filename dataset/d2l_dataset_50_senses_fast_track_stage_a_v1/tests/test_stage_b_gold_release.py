from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.build_stage_b_gold_release import (
    build_artifact,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.stage_b_adjudication_result import (
    validate_completed_stage_b_adjudication,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.validate_stage_b_gold_release import (
    validate_artifact,
)


NAMESPACE = Path(__file__).resolve().parents[1]
RELEASE = NAMESPACE / "release"
DATASET_ARTIFACT = RELEASE / "d2l_dataset_50_senses_150_candidates_stage_b_review_v1"
REVIEW_INTAKE = RELEASE / "d2l_dataset_50_senses_stage_b_review_intake_v1"


def _complete(path: Path) -> None:
    payload = json.loads(
        (REVIEW_INTAKE / "adjudication_input.json").read_text(encoding="utf-8")
    )
    for case in payload["cases"]:
        case["adjudication"] = {
            "adjudicator_label": case["disagreement"]["reviewer_1_label"],
            "adjudication_reason": "Focused deterministic adjudication test.",
            "adjudication_status": "COMPLETE",
        }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class StageBGoldReleaseTests(unittest.TestCase):
    def test_completed_adjudication_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer_3.json"
            _complete(result)
            validated, errors = validate_completed_stage_b_adjudication(
                REVIEW_INTAKE / "adjudication_input.json", result
            )
            self.assertEqual(errors, [])
            self.assertEqual(len(validated.cases_by_candidate), 19)

    def test_source_tamper_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer_3.json"
            _complete(result)
            payload = json.loads(result.read_text(encoding="utf-8"))
            payload["cases"][0]["source_payload"]["candidate_target_vi"] = "tampered"
            result.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            _, errors = validate_completed_stage_b_adjudication(
                REVIEW_INTAKE / "adjudication_input.json", result
            )
            self.assertTrue(
                any("immutable case field changed" in error for error in errors)
            )

    def test_incomplete_adjudication_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer_3.json"
            _complete(result)
            payload = json.loads(result.read_text(encoding="utf-8"))
            payload["cases"][0]["adjudication"]["adjudication_status"] = ""
            result.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            _, errors = validate_completed_stage_b_adjudication(
                REVIEW_INTAKE / "adjudication_input.json", result
            )
            self.assertTrue(
                any("adjudication_status must be COMPLETE" in error for error in errors)
            )

    def test_builder_freezes_exact_150_gold_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "reviewer_3.json"
            _complete(result)
            output = root / "output"
            manifest = build_artifact(
                dataset_artifact_root=DATASET_ARTIFACT,
                review_intake_root=REVIEW_INTAKE,
                reviewer_3_path=result,
                output_root=output,
            )
            self.assertEqual(manifest["final_gold_label_count"], 150)
            self.assertEqual(manifest["adjudication_count"], 19)
            self.assertEqual(
                validate_artifact(
                    output,
                    dataset_artifact_root=DATASET_ARTIFACT,
                    review_intake_root=REVIEW_INTAKE,
                ),
                [],
            )

    def test_gold_release_keeps_global_decisions_null(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = root / "reviewer_3.json"
            _complete(result)
            output = root / "output"
            build_artifact(
                dataset_artifact_root=DATASET_ARTIFACT,
                review_intake_root=REVIEW_INTAKE,
                reviewer_3_path=result,
                output_root=output,
            )
            rows = [
                json.loads(line)
                for line in (output / "stage_b_gold_150.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(len(rows), 150)
            self.assertTrue(all(row["final_gold_label"] for row in rows))
            self.assertTrue(
                all(row["final_glossary_decision"] is None for row in rows)
            )
            self.assertTrue(all(row["provider_call_count"] == 0 for row in rows))


if __name__ == "__main__":
    unittest.main()
