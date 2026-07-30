from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.build_stage_b_review_intake import (
    build_artifact,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.stage_b_review_result import (
    validate_completed_stage_b_review,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.validate_stage_b_review_intake import (
    validate_artifact,
)


NAMESPACE = Path(__file__).resolve().parents[1]
SOURCE = (
    NAMESPACE
    / "release"
    / "d2l_dataset_50_senses_150_candidates_stage_b_review_v1"
)


def _complete(
    slot: str, path: Path, *, disagreement_candidate: str | None = None
) -> None:
    payload = json.loads(
        (SOURCE / f"{slot}_full_input.json").read_text(encoding="utf-8")
    )
    for case in payload["cases"]:
        source = case["source_payload"]
        positives = [
            row["context_id"]
            for row in source["contexts"]
            if row["sense_relation"] == "SAME_SENSE"
            and not row["synthetic"]
            and not row["boundary_only"]
        ]
        label = (
            "CONDITIONAL"
            if source["candidate_id"] == disagreement_candidate
            else "ACCEPT"
        )
        case["review"] = {
            "candidate_gold_label": label,
            "allowed_scope": "d2l_selected_campaign_scope_v1",
            "validated_variants": [source["candidate_target_vi"]],
            "rejected_variants": [],
            "reason_codes": ["TEST_EVIDENCE"],
            "positive_context_refs": positives[:1],
            "vietnamese_evidence_refs": [],
            "review_notes": "Focused deterministic test review.",
            "review_status": "COMPLETE",
        }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class StageBReviewIntakeTests(unittest.TestCase):
    def test_completed_result_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer_1.json"
            _complete("reviewer_1", result)
            validated, errors = validate_completed_stage_b_review(
                SOURCE / "reviewer_1_full_input.json",
                result,
                expected_reviewer_slot="reviewer_1",
            )
            self.assertEqual(errors, [])
            self.assertEqual(len(validated.cases_by_candidate), 150)

    def test_source_tamper_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer_1.json"
            _complete("reviewer_1", result)
            payload = json.loads(result.read_text(encoding="utf-8"))
            payload["cases"][0]["source_payload"][
                "candidate_target_vi"
            ] = "tampered"
            result.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            _, errors = validate_completed_stage_b_review(
                SOURCE / "reviewer_1_full_input.json",
                result,
                expected_reviewer_slot="reviewer_1",
            )
            self.assertTrue(
                any("immutable case field changed" in error for error in errors)
            )

    def test_synthetic_positive_context_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer_1.json"
            _complete("reviewer_1", result)
            payload = json.loads(result.read_text(encoding="utf-8"))
            case = next(
                row
                for row in payload["cases"]
                if any(
                    context["synthetic"]
                    for context in row["source_payload"]["contexts"]
                )
            )
            context = next(
                row
                for row in case["source_payload"]["contexts"]
                if row["synthetic"]
            )
            case["review"]["positive_context_refs"] = [context["context_id"]]
            result.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            _, errors = validate_completed_stage_b_review(
                SOURCE / "reviewer_1_full_input.json",
                result,
                expected_reviewer_slot="reviewer_1",
            )
            self.assertTrue(
                any("not real same-sense evidence" in error for error in errors)
            )

    def test_incomplete_review_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer_1.json"
            _complete("reviewer_1", result)
            payload = json.loads(result.read_text(encoding="utf-8"))
            payload["cases"][0]["review"]["review_status"] = ""
            result.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            _, errors = validate_completed_stage_b_review(
                SOURCE / "reviewer_1_full_input.json",
                result,
                expected_reviewer_slot="reviewer_1",
            )
            self.assertTrue(
                any("review_status must be COMPLETE" in error for error in errors)
            )

    def test_same_result_path_rejects_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp) / "reviewer.json"
            _complete("reviewer_1", result)
            output = Path(temp) / "output"
            with self.assertRaisesRegex(ValueError, "distinct physical files"):
                build_artifact(
                    source_artifact_root=SOURCE,
                    reviewer_1_path=result,
                    reviewer_2_path=result,
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_build_routes_only_label_disagreement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_1 = root / "reviewer_1.json"
            result_2 = root / "reviewer_2.json"
            _complete("reviewer_1", result_1)
            first_candidate = json.loads(
                (SOURCE / "reviewer_2_full_input.json").read_text(encoding="utf-8")
            )["cases"][0]["source_payload"]["candidate_id"]
            _complete(
                "reviewer_2",
                result_2,
                disagreement_candidate=first_candidate,
            )
            output = root / "output"
            manifest = build_artifact(
                source_artifact_root=SOURCE,
                reviewer_1_path=result_1,
                reviewer_2_path=result_2,
                output_root=output,
            )
            self.assertEqual(manifest["agreement_count"], 149)
            self.assertEqual(manifest["disagreement_count"], 1)
            self.assertEqual(
                validate_artifact(output, source_artifact_root=SOURCE), []
            )


if __name__ == "__main__":
    unittest.main()
