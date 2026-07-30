from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_review_preflight import (
    ARTIFACT_NAME,
    build_artifact,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.remaining_stage_b_review_result import (
    MISSING_ALLOWED_SCOPE,
    validate_completed_review,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_remaining_stage_b_review_preflight import (
    validate_artifact,
)


NAMESPACE = Path(__file__).resolve().parents[1]
SOURCE = (
    NAMESPACE
    / "release"
    / "d2l_dataset_remaining_300_candidates_stage_b_review_v1"
)
_REFERENCE_CASES = json.loads(
    (SOURCE / "reviewer_1_full_input.json").read_text(encoding="utf-8")
)["cases"]
REPAIR_CANDIDATE_ID = _REFERENCE_CASES[0]["source_payload"]["candidate_id"]
DISAGREEMENT_CANDIDATE_ID = _REFERENCE_CASES[1]["source_payload"]["candidate_id"]


def _complete(
    slot: str,
    path: Path,
    *,
    disagreement: bool = True,
    extra_error: bool = False,
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
        if source["candidate_id"] == REPAIR_CANDIDATE_ID:
            label = "SPLIT_REQUIRED"
            allowed_scope = "" if slot == "reviewer_1" else "d2l_scope_v1"
            validated: list[str] = []
            positive_refs: list[str] = []
        else:
            label = (
                "CONDITIONAL"
                if slot == "reviewer_2"
                and disagreement
                and source["candidate_id"] == DISAGREEMENT_CANDIDATE_ID
                else "ACCEPT"
            )
            allowed_scope = "d2l_scope_v1"
            validated = [source["candidate_target_vi"]]
            positive_refs = positives[:1]
        case["review"] = {
            "candidate_gold_label": label,
            "allowed_scope": allowed_scope,
            "validated_variants": validated,
            "rejected_variants": [],
            "reason_codes": ["FOCUSED_TEST_EVIDENCE"],
            "positive_context_refs": positive_refs,
            "vietnamese_evidence_refs": [],
            "review_notes": "Focused deterministic test review.",
            "review_status": "COMPLETE",
        }
    if extra_error:
        case = next(
            row
            for row in payload["cases"]
            if row["source_payload"]["candidate_id"]
            not in {REPAIR_CANDIDATE_ID, DISAGREEMENT_CANDIDATE_ID}
        )
        case["review"]["review_notes"] = ""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class RemainingStageBReviewPreflightTests(unittest.TestCase):
    def test_completed_reviews_identify_only_expected_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviewer_1 = root / "reviewer_1.json"
            reviewer_2 = root / "reviewer_2.json"
            _complete("reviewer_1", reviewer_1)
            _complete("reviewer_2", reviewer_2)
            result_1, issues_1 = validate_completed_review(
                SOURCE / "reviewer_1_full_input.json",
                reviewer_1,
                expected_reviewer_slot="reviewer_1",
            )
            result_2, issues_2 = validate_completed_review(
                SOURCE / "reviewer_2_full_input.json",
                reviewer_2,
                expected_reviewer_slot="reviewer_2",
            )
            self.assertIsNotNone(result_1)
            self.assertIsNotNone(result_2)
            self.assertEqual([issue.code for issue in issues_1], [MISSING_ALLOWED_SCOPE])
            self.assertEqual(issues_2, [])

    def test_build_routes_repair_and_label_disagreement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviewer_1 = root / "reviewer_1.json"
            reviewer_2 = root / "reviewer_2.json"
            _complete("reviewer_1", reviewer_1)
            _complete("reviewer_2", reviewer_2)
            output = root / ARTIFACT_NAME
            manifest = build_artifact(
                source_artifact_root=SOURCE,
                reviewer_1_path=reviewer_1,
                reviewer_2_path=reviewer_2,
                output_root=output,
            )
            self.assertEqual(manifest["reviewer_1_repair_case_count"], 1)
            self.assertEqual(manifest["agreement_count"], 299)
            self.assertEqual(manifest["disagreement_count"], 1)
            self.assertEqual(validate_artifact(output, source_artifact_root=SOURCE), [])
            adjudication = strict_json_object(
                output / "reviewer_3_adjudication_input.json"
            )
            self.assertEqual(adjudication["case_count"], 1)
            self.assertIsNone(adjudication["cases"][0]["final_gold_label"])

    def test_nonrepair_validation_error_rejects_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviewer_1 = root / "reviewer_1.json"
            reviewer_2 = root / "reviewer_2.json"
            _complete("reviewer_1", reviewer_1, extra_error=True)
            _complete("reviewer_2", reviewer_2)
            output = root / ARTIFACT_NAME
            with self.assertRaisesRegex(ValueError, "exactly one repairable"):
                build_artifact(
                    source_artifact_root=SOURCE,
                    reviewer_1_path=reviewer_1,
                    reviewer_2_path=reviewer_2,
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_source_tamper_rejects_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviewer_1 = root / "reviewer_1.json"
            reviewer_2 = root / "reviewer_2.json"
            _complete("reviewer_1", reviewer_1)
            _complete("reviewer_2", reviewer_2)
            payload = json.loads(reviewer_1.read_text(encoding="utf-8"))
            payload["cases"][0]["source_payload"]["candidate_target_vi"] = "tampered"
            reviewer_1.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            output = root / ARTIFACT_NAME
            with self.assertRaises(ValueError):
                build_artifact(
                    source_artifact_root=SOURCE,
                    reviewer_1_path=reviewer_1,
                    reviewer_2_path=reviewer_2,
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_same_result_path_rejects_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviewer = root / "reviewer.json"
            _complete("reviewer_1", reviewer)
            output = root / ARTIFACT_NAME
            with self.assertRaisesRegex(ValueError, "distinct physical files"):
                build_artifact(
                    source_artifact_root=SOURCE,
                    reviewer_1_path=reviewer,
                    reviewer_2_path=reviewer,
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_two_builds_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviewer_1 = root / "reviewer_1.json"
            reviewer_2 = root / "reviewer_2.json"
            _complete("reviewer_1", reviewer_1)
            _complete("reviewer_2", reviewer_2)
            first = root / "first" / ARTIFACT_NAME
            second = root / "second" / ARTIFACT_NAME
            build_artifact(
                source_artifact_root=SOURCE,
                reviewer_1_path=reviewer_1,
                reviewer_2_path=reviewer_2,
                output_root=first,
            )
            build_artifact(
                source_artifact_root=SOURCE,
                reviewer_1_path=reviewer_1,
                reviewer_2_path=reviewer_2,
                output_root=second,
            )
            self.assertEqual(
                sha256_file(first.parent / f"{ARTIFACT_NAME}.zip"),
                sha256_file(second.parent / f"{ARTIFACT_NAME}.zip"),
            )


if __name__ == "__main__":
    unittest.main()
