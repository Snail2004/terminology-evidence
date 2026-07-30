from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
    write_json,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.reviewer3_adjudication_finalize import (
    build_corrected_release,
    validate_release,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.reviewer3_adjudication_repair import (
    build_repair_package,
)


ROOT = Path(__file__).resolve().parents[1]
INTAKE_ROOT = ROOT / "release" / "d2l_dataset_remaining_100_stage_a_review_intake_v1"


def _canonical_payload(batch_id: str) -> dict:
    path = INTAKE_ROOT / "handoff" / f"{batch_id}_reviewer_3_adjudication.zip"
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("reviewer_3_input.json").decode("utf-8"))


def _complete_adjudication(payload: dict) -> dict:
    for case in payload["cases"]:
        case["adjudication"].update(
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


def _make_reviewer_root(root: Path) -> Path:
    reviewer_root = root / "reviewer3"
    marked = 0
    for batch_index in range(1, 11):
        batch_id = f"batch_{batch_index:03d}"
        payload = _complete_adjudication(_canonical_payload(batch_id))
        for case in payload["cases"]:
            if marked >= 8:
                break
            case["adjudication"]["evidence_decision"] = "REVISE"
            marked += 1
        write_json(reviewer_root / batch_id / "reviewer_3_input.json", payload)
    if marked != 8:
        raise AssertionError("fixture did not create every targeted repair")
    return reviewer_root


class Reviewer3AdjudicationFinalizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name)
        self.reviewer_root = _make_reviewer_root(self.temp_root)
        self.source_hashes = {
            path.relative_to(self.reviewer_root).as_posix(): sha256_file(path)
            for path in self.reviewer_root.rglob("*.json")
        }
        self.repair_root = self.temp_root / "repair"
        build_repair_package(
            intake_root=INTAKE_ROOT,
            reviewer_3_root=self.reviewer_root,
            output_root=self.repair_root,
            zip_path=self.temp_root / "repair.zip",
        )
        response = strict_json_object(
            self.repair_root / "reviewer_3_repair_input.json"
        )
        for case in response["cases"]:
            case["repair"]["evidence_decision"] = "ACCEPT"
        self.response_path = self.temp_root / "response.json"
        write_json(self.response_path, response)

    def _build(self, name: str) -> dict:
        return build_corrected_release(
            intake_root=INTAKE_ROOT,
            reviewer_3_root=self.reviewer_root,
            repair_source_root=self.repair_root,
            response_path=self.response_path,
            output_root=self.temp_root / name,
            zip_path=self.temp_root / f"{name}.zip",
        )

    def test_builds_valid_corrected_release(self) -> None:
        result = self._build("corrected")
        self.assertEqual(result["validated_batch_count"], 10)
        self.assertEqual(result["validated_case_count"], 45)
        self.assertEqual(result["corrected_case_count"], 8)
        self.assertEqual(
            validate_release(
                self.temp_root / "corrected",
                intake_root=INTAKE_ROOT,
                reviewer_3_root=self.reviewer_root,
            ),
            [],
        )
        after = {
            path.relative_to(self.reviewer_root).as_posix(): sha256_file(path)
            for path in self.reviewer_root.rglob("*.json")
        }
        self.assertEqual(after, self.source_hashes)

    def test_release_is_deterministic(self) -> None:
        first = self._build("first")
        second = self._build("second")
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(first["zip_sha256"], second["zip_sha256"])

    def test_tampered_response_rejects_without_output(self) -> None:
        response = strict_json_object(self.response_path)
        response["cases"][0]["source_term"] += " changed"
        tampered = self.temp_root / "tampered.json"
        write_json(tampered, response)
        output = self.temp_root / "must_not_exist"
        with self.assertRaisesRegex(ValueError, "immutable field changed"):
            build_corrected_release(
                intake_root=INTAKE_ROOT,
                reviewer_3_root=self.reviewer_root,
                repair_source_root=self.repair_root,
                response_path=tampered,
                output_root=output,
                zip_path=self.temp_root / "must_not_exist.zip",
            )
        self.assertFalse(output.exists())

    def test_source_drift_rejects_without_output(self) -> None:
        source = self.reviewer_root / "batch_001" / "reviewer_3_input.json"
        payload = strict_json_object(source)
        payload["cases"][0]["adjudication"]["review_notes"] += " changed"
        write_json(source, payload)
        output = self.temp_root / "drift_output"
        with self.assertRaisesRegex(ValueError, "source drifted after preflight"):
            build_corrected_release(
                intake_root=INTAKE_ROOT,
                reviewer_3_root=self.reviewer_root,
                repair_source_root=self.repair_root,
                response_path=self.response_path,
                output_root=output,
                zip_path=self.temp_root / "drift_output.zip",
            )
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
