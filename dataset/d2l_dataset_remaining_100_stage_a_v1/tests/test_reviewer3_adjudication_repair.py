from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.adjudication_result import (
    validate_completed_adjudication,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
    write_json,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.reviewer3_adjudication_repair import (
    apply_repair_response,
    build_repair_package,
    validate_repair_response,
)


ROOT = Path(__file__).resolve().parents[1]
INTAKE_ROOT = ROOT / "release" / "d2l_dataset_remaining_100_stage_a_review_intake_v1"


def _canonical_payload(batch_id: str) -> dict:
    path = INTAKE_ROOT / "handoff" / f"{batch_id}_reviewer_3_adjudication.zip"
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("reviewer_3_input.json").decode("utf-8"))


def _complete_adjudication(payload: dict) -> dict:
    for case in payload["cases"]:
        adjudication = case["adjudication"]
        adjudication.update(
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
                "review_notes": "Synthetic unit-test adjudication.",
                "review_status": "COMPLETE",
                "scope_decision": "ACCEPT",
                "sense_status": "READY_FOR_CONTRACT_CONSTRUCTION",
                "adjudication_rationale": "Synthetic unit-test resolution.",
                "adjudication_status": "COMPLETE",
            }
        )
    return payload


def _make_result_root(root: Path, *, target_count: int = 8) -> Path:
    reviewer_root = root / "reviewer3"
    marked = 0
    for batch_index in range(1, 11):
        batch_id = f"batch_{batch_index:03d}"
        payload = _complete_adjudication(_canonical_payload(batch_id))
        for case in payload["cases"]:
            if marked >= target_count:
                break
            case["adjudication"]["evidence_decision"] = "REVISE"
            marked += 1
        write_json(reviewer_root / batch_id / "reviewer_3_input.json", payload)
    if marked != target_count:
        raise AssertionError("fixture did not create every targeted repair")
    return reviewer_root


class Reviewer3AdjudicationRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name)
        self.reviewer_root = _make_result_root(self.temp_root)
        self.source_hashes = {
            path.relative_to(self.reviewer_root).as_posix(): sha256_file(path)
            for path in self.reviewer_root.rglob("*.json")
        }
        self.artifact_root = self.temp_root / "repair"
        self.zip_path = self.temp_root / "repair.zip"
        self.result = build_repair_package(
            intake_root=INTAKE_ROOT,
            reviewer_3_root=self.reviewer_root,
            output_root=self.artifact_root,
            zip_path=self.zip_path,
        )

    def test_detects_only_eight_targeted_cases(self) -> None:
        payload = strict_json_object(self.artifact_root / "reviewer_3_repair_input.json")
        self.assertEqual(payload["case_count"], 8)
        self.assertEqual(self.result["source_case_count"], 45)
        self.assertEqual(self.result["valid_case_count"], 37)

    def test_source_results_remain_byte_identical(self) -> None:
        after = {
            path.relative_to(self.reviewer_root).as_posix(): sha256_file(path)
            for path in self.reviewer_root.rglob("*.json")
        }
        self.assertEqual(after, self.source_hashes)

    def test_accept_response_validates_and_applies_to_copy(self) -> None:
        input_path = self.artifact_root / "reviewer_3_repair_input.json"
        response = strict_json_object(input_path)
        for case in response["cases"]:
            case["repair"]["evidence_decision"] = "ACCEPT"
        response_path = self.temp_root / "response.json"
        write_json(response_path, response)
        _, errors = validate_repair_response(input_path, response_path)
        self.assertEqual(errors, [])
        corrected_root = self.temp_root / "corrected"
        result = apply_repair_response(
            intake_root=INTAKE_ROOT,
            reviewer_3_root=self.reviewer_root,
            repair_input_path=input_path,
            response_path=response_path,
            output_root=corrected_root,
        )
        self.assertEqual(result["corrected_case_count"], 8)
        self.assertEqual(result["corrected_file_count"], 10)
        for batch_index in range(1, 11):
            batch_id = f"batch_{batch_index:03d}"
            corrected = corrected_root / batch_id / "reviewer_3_input.json"
            canonical = _canonical_payload(batch_id)
            _, validation_errors, _ = validate_completed_adjudication(
                canonical,
                corrected,
                expected_batch_id=batch_id,
            )
            self.assertEqual(validation_errors, [])

    def test_revise_requires_source_bound_context_ids(self) -> None:
        input_path = self.artifact_root / "reviewer_3_repair_input.json"
        response = strict_json_object(input_path)
        for case in response["cases"]:
            case["repair"]["evidence_decision"] = "REVISE"
            case["repair"]["invalid_evidence_context_ids"] = ["not-source-bound"]
        response_path = self.temp_root / "invalid.json"
        write_json(response_path, response)
        _, errors = validate_repair_response(input_path, response_path)
        self.assertTrue(any("not source-bound" in error for error in errors))

    def test_immutable_field_change_rejects(self) -> None:
        input_path = self.artifact_root / "reviewer_3_repair_input.json"
        response = strict_json_object(input_path)
        for case in response["cases"]:
            case["repair"]["evidence_decision"] = "ACCEPT"
        response["cases"][0]["source_term"] += " changed"
        response_path = self.temp_root / "tampered.json"
        write_json(response_path, response)
        _, errors = validate_repair_response(input_path, response_path)
        self.assertTrue(any("immutable field changed" in error for error in errors))

    def test_unexpected_review_error_fails_closed(self) -> None:
        bad_root = _make_result_root(self.temp_root / "bad")
        first = bad_root / "batch_001" / "reviewer_3_input.json"
        payload = strict_json_object(first)
        payload["cases"][0]["adjudication"]["review_notes"] = ""
        write_json(first, payload)
        output = self.temp_root / "must_not_exist"
        with self.assertRaisesRegex(ValueError, "review_notes must be nonblank"):
            build_repair_package(
                intake_root=INTAKE_ROOT,
                reviewer_3_root=bad_root,
                output_root=output,
                zip_path=self.temp_root / "must_not_exist.zip",
            )
        self.assertFalse(output.exists())

    def test_deterministic_package(self) -> None:
        second_root = self.temp_root / "repair_second"
        second_zip = self.temp_root / "repair_second.zip"
        second = build_repair_package(
            intake_root=INTAKE_ROOT,
            reviewer_3_root=self.reviewer_root,
            output_root=second_root,
            zip_path=second_zip,
        )
        self.assertEqual(self.result["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(self.result["zip_sha256"], second["zip_sha256"])


if __name__ == "__main__":
    unittest.main()
