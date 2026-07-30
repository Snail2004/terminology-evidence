from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_remaining_stage_b_reviewer1_repair_intake import (
    ARTIFACT_NAME,
    build_artifact,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_remaining_stage_b_reviewer1_repair_intake import (
    validate_artifact,
)


NAMESPACE = Path(__file__).resolve().parents[1]
SOURCE = (
    NAMESPACE
    / "release"
    / "d2l_dataset_remaining_300_candidates_stage_b_review_v1"
)
PARENT = (
    NAMESPACE
    / "release"
    / "d2l_dataset_remaining_300_candidates_stage_b_review_preflight_v1"
)


def _complete_repair(path: Path) -> None:
    payload = json.loads(
        (PARENT / "reviewer_1_repair_input.json").read_text(encoding="utf-8")
    )
    payload["cases"][0]["repair"] = {
        "allowed_scope": "D2L_HARDWARE_OR_OBJECT_DETECTION_SEPARATE_SCOPES",
        "repair_notes": "Keep the two acronym expansions in separate senses.",
        "repair_status": "COMPLETE",
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class RemainingStageBReviewer1RepairIntakeTests(unittest.TestCase):
    def test_valid_repair_builds_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            response = root / "reviewer_1_repair.json"
            _complete_repair(response)
            output = root / ARTIFACT_NAME
            manifest = build_artifact(
                parent_artifact_root=PARENT,
                source_artifact_root=SOURCE,
                repair_response_path=response,
                output_root=output,
            )
            self.assertEqual(manifest["agreement_count"], 245)
            self.assertEqual(manifest["disagreement_count"], 55)
            self.assertEqual(
                validate_artifact(
                    output,
                    parent_artifact_root=PARENT,
                    source_artifact_root=SOURCE,
                ),
                [],
            )

    def test_only_allowed_scope_changes_in_repaired_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            response = root / "reviewer_1_repair.json"
            _complete_repair(response)
            output = root / ARTIFACT_NAME
            build_artifact(
                parent_artifact_root=PARENT,
                source_artifact_root=SOURCE,
                repair_response_path=response,
                output_root=output,
            )
            original = strict_json_object(PARENT / "raw_reviews" / "reviewer_1.json")
            repaired = strict_json_object(
                output / "repaired_reviews" / "reviewer_1.json"
            )
            changed = []
            for before, after in zip(original["cases"], repaired["cases"]):
                if before != after:
                    changed.append((before, after))
            self.assertEqual(len(changed), 1)
            before, after = changed[0]
            expected_review = dict(before["review"])
            expected_review["allowed_scope"] = (
                "D2L_HARDWARE_OR_OBJECT_DETECTION_SEPARATE_SCOPES"
            )
            self.assertEqual(after["review"], expected_review)
            expected_case = dict(before)
            expected_case["review"] = expected_review
            self.assertEqual(after, expected_case)

    def test_immutable_repair_tamper_rejects_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            response = root / "reviewer_1_repair.json"
            _complete_repair(response)
            payload = json.loads(response.read_text(encoding="utf-8"))
            payload["cases"][0]["original_review"]["candidate_gold_label"] = "ACCEPT"
            response.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            output = root / ARTIFACT_NAME
            with self.assertRaisesRegex(ValueError, "immutable case field changed"):
                build_artifact(
                    parent_artifact_root=PARENT,
                    source_artifact_root=SOURCE,
                    repair_response_path=response,
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_blank_scope_rejects_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            response = root / "reviewer_1_repair.json"
            _complete_repair(response)
            payload = json.loads(response.read_text(encoding="utf-8"))
            payload["cases"][0]["repair"]["allowed_scope"] = ""
            response.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            output = root / ARTIFACT_NAME
            with self.assertRaisesRegex(ValueError, "allowed_scope must be nonblank"):
                build_artifact(
                    parent_artifact_root=PARENT,
                    source_artifact_root=SOURCE,
                    repair_response_path=response,
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_reviewer_3_handoff_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            response = root / "reviewer_1_repair.json"
            _complete_repair(response)
            output = root / ARTIFACT_NAME
            build_artifact(
                parent_artifact_root=PARENT,
                source_artifact_root=SOURCE,
                repair_response_path=response,
                output_root=output,
            )
            self.assertEqual(
                sha256_file(PARENT / "handoff" / "reviewer_3.zip"),
                sha256_file(output / "handoff" / "reviewer_3.zip"),
            )
            self.assertEqual(
                sha256_file(PARENT / "reviewer_3_adjudication_input.json"),
                sha256_file(output / "reviewer_3_adjudication_input.json"),
            )

    def test_two_builds_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            response = root / "reviewer_1_repair.json"
            _complete_repair(response)
            first = root / "first" / ARTIFACT_NAME
            second = root / "second" / ARTIFACT_NAME
            build_artifact(
                parent_artifact_root=PARENT,
                source_artifact_root=SOURCE,
                repair_response_path=response,
                output_root=first,
            )
            build_artifact(
                parent_artifact_root=PARENT,
                source_artifact_root=SOURCE,
                repair_response_path=response,
                output_root=second,
            )
            self.assertEqual(
                sha256_file(first.parent / f"{ARTIFACT_NAME}.zip"),
                sha256_file(second.parent / f"{ARTIFACT_NAME}.zip"),
            )


if __name__ == "__main__":
    unittest.main()
