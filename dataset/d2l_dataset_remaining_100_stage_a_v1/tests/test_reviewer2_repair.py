from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
    write_json,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.reviewer2_repair import (
    apply_repair_response,
    build_repair_package,
    validate_repair_response,
)


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = ROOT / "release" / "d2l_dataset_remaining_100_stage_a_v1"


def _complete_review(payload: dict, *, make_invalid: bool) -> dict:
    for case in payload["cases"]:
        review = case["review"]
        review.update(
            {
                "candidate_replacements": [],
                "candidate_set_decision": "ACCEPT",
                "corrected_definition_en": "",
                "corrected_part_of_speech": "",
                "corrected_scope": "",
                "definition_decision": "ACCEPT",
                "evidence_decision": "ACCEPT",
                "invalid_evidence_context_ids": [],
                "part_of_speech_decision": "ACCEPT",
                "proposed_split_labels": [],
                "review_notes": "Synthetic unit-test review.",
                "review_status": "COMPLETE",
                "scope_decision": "ACCEPT",
                "sense_status": "READY_FOR_CONTRACT_CONSTRUCTION",
            }
        )
    if make_invalid:
        case = payload["cases"][0]
        case["review"]["candidate_set_decision"] = "REVISE"
        case["review"]["sense_status"] = "SPLIT_REQUIRED"
        case["review"]["proposed_split_labels"] = ["sense one", "sense two"]
    return payload


def _make_result_roots(temp_root: Path) -> tuple[Path, Path]:
    reviewer_1_root = temp_root / "reviewer1"
    reviewer_2_root = temp_root / "reviewer2"
    reviewer_1_root.mkdir()
    reviewer_2_root.mkdir()
    invalid_batches = set()
    for source_path in sorted((CANONICAL_ROOT / "batches").glob("batch_*")):
        batch_id = source_path.name
        r1 = strict_json_object(source_path / "reviewer_1_input.json")
        write_json(
            reviewer_1_root / f"{batch_id}_reviewer_1_completed.json",
            _complete_review(r1, make_invalid=False),
        )
        r2 = strict_json_object(source_path / "reviewer_2_input.json")
        should_fail = len(invalid_batches) < 6 and bool(r2["cases"])
        if should_fail:
            invalid_batches.add(batch_id)
        write_json(
            reviewer_2_root / f"{batch_id}_reviewer_2_completed.json",
            _complete_review(r2, make_invalid=should_fail),
        )
    return reviewer_1_root, reviewer_2_root


class Reviewer2RepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name)
        self.reviewer_1_root, self.reviewer_2_root = _make_result_roots(
            self.temp_root
        )
        self.artifact_root = self.temp_root / "repair"
        self.zip_path = self.temp_root / "repair.zip"
        self.before = {
            path.name: sha256_file(path)
            for path in sorted(self.reviewer_2_root.glob("*.json"))
        }
        self.result = build_repair_package(
            canonical_root=CANONICAL_ROOT,
            reviewer_1_root=self.reviewer_1_root,
            reviewer_2_root=self.reviewer_2_root,
            output_root=self.artifact_root,
            zip_path=self.zip_path,
        )

    def test_detects_only_six_targeted_cases(self) -> None:
        payload = strict_json_object(self.artifact_root / "reviewer_2_repair_input.json")
        self.assertEqual(payload["case_count"], 6)
        self.assertEqual(len({row["batch_id"] for row in payload["cases"]}), 6)

    def test_source_review_files_remain_byte_identical(self) -> None:
        after = {
            path.name: sha256_file(path)
            for path in sorted(self.reviewer_2_root.glob("*.json"))
        }
        self.assertEqual(after, self.before)

    def test_accept_partition_response_validates_and_applies_to_copy(self) -> None:
        input_path = self.artifact_root / "reviewer_2_repair_input.json"
        response = strict_json_object(input_path)
        for case in response["cases"]:
            case["repair"]["candidate_set_decision"] = "ACCEPT"
        response_path = self.temp_root / "response.json"
        write_json(response_path, response)
        _, errors = validate_repair_response(input_path, response_path)
        self.assertEqual(errors, [])
        corrected_root = self.temp_root / "corrected"
        result = apply_repair_response(
            canonical_root=CANONICAL_ROOT,
            reviewer_2_root=self.reviewer_2_root,
            repair_input_path=input_path,
            response_path=response_path,
            output_root=corrected_root,
        )
        self.assertEqual(result["corrected_case_count"], 6)
        self.assertEqual(len(list(corrected_root.glob("batch_*_completed.json"))), 10)

    def test_blank_or_unbound_repair_rejects(self) -> None:
        input_path = self.artifact_root / "reviewer_2_repair_input.json"
        response = strict_json_object(input_path)
        response_path = self.temp_root / "blank.json"
        write_json(response_path, response)
        _, errors = validate_repair_response(input_path, response_path)
        self.assertTrue(errors)

        response = strict_json_object(input_path)
        for case in response["cases"]:
            case["repair"] = {
                "candidate_set_decision": "REVISE",
                "candidate_replacements": [
                    {
                        "candidate_id": "not-a-source-candidate",
                        "candidate_slot": 99,
                        "replacement_target_vi": "mục thay thế",
                    }
                ],
            }
        write_json(response_path, response)
        _, errors = validate_repair_response(input_path, response_path)
        self.assertTrue(any("not source-bound" in error for error in errors))

    def test_immutable_repair_case_fields_reject(self) -> None:
        input_path = self.artifact_root / "reviewer_2_repair_input.json"
        response = strict_json_object(input_path)
        for case in response["cases"]:
            case["repair"]["candidate_set_decision"] = "ACCEPT"
        response["cases"][0]["source_term"] += " changed"
        response_path = self.temp_root / "tampered.json"
        write_json(response_path, response)
        _, errors = validate_repair_response(input_path, response_path)
        self.assertTrue(any("immutable field changed" in error for error in errors))

    def test_deterministic_package(self) -> None:
        second_root = self.temp_root / "repair_second"
        second_zip = self.temp_root / "repair_second.zip"
        second = build_repair_package(
            canonical_root=CANONICAL_ROOT,
            reviewer_1_root=self.reviewer_1_root,
            reviewer_2_root=self.reviewer_2_root,
            output_root=second_root,
            zip_path=second_zip,
        )
        self.assertEqual(self.result["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(self.result["zip_sha256"], second["zip_sha256"])


if __name__ == "__main__":
    unittest.main()
