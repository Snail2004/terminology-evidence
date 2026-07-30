from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
    strict_jsonl,
    write_json,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_proposal_repair_intake import (
    build_proposal_repair_intake,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.proposal_repair_validation import (
    validate_proposal_repair,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_proposal_repair_intake import (
    validate_artifact,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_ROOT = PROJECT_ROOT / "dataset" / "d2l_dataset_remaining_100_stage_a_v1"
RELEASE_ROOT = DATASET_ROOT / "release"
SOURCE_ROOT = RELEASE_ROOT / "d2l_dataset_remaining_100_stage_a_followup_result_v1"
ARTIFACT_ROOT = (
    RELEASE_ROOT / "d2l_remaining100_proposal_repair_v1"
)
ZIP_PATH = (
    RELEASE_ROOT / "d2l_remaining100_proposal_repair_v1.zip"
)


def captured_responses(root: Path = ARTIFACT_ROOT) -> tuple[list[Path], list[Path]]:
    return (
        sorted((root / "captures" / "reviewer_2").glob("*.json")),
        sorted((root / "captures" / "reviewer_3").glob("*.json")),
    )


class ProposalRepairIntakeTests(unittest.TestCase):
    def test_release_validates(self) -> None:
        self.assertEqual(validate_artifact(ARTIFACT_ROOT), [])

    def test_repair_records_route_to_distinct_reauditors(self) -> None:
        records = strict_jsonl(
            ARTIFACT_ROOT / "proposal_repairs_pending_reaudit_4.jsonl"
        )
        self.assertEqual(len(records), 4)
        self.assertEqual(
            {row["source_term"] for row in records},
            {"attention", "blocks", "inverse", "shape"},
        )
        self.assertTrue(
            all(
                row["repair_result_role"] != row["reaudit_reviewer_role"]
                for row in records
            )
        )

    def test_rebuild_is_byte_deterministic(self) -> None:
        reviewer_2, reviewer_3 = captured_responses()
        with tempfile.TemporaryDirectory(prefix="proposal-repair-rebuild-") as name:
            root = Path(name)
            output = root / "artifact"
            zip_path = root / "artifact.zip"
            build_proposal_repair_intake(
                source_root=SOURCE_ROOT,
                reviewer_2_responses=reviewer_2,
                reviewer_3_responses=reviewer_3,
                output_root=output,
                zip_path=zip_path,
            )
            self.assertEqual(sha256_file(zip_path), sha256_file(ZIP_PATH))
            self.assertEqual(validate_artifact(output), [])

    def test_unflagged_child_change_rejects(self) -> None:
        reviewer_2, _ = captured_responses()
        source_path = (
            SOURCE_ROOT
            / "repair_batches"
            / "high_risk_proposal_repair_reviewer_2"
            / "repair_input.json"
        )
        response = copy.deepcopy(strict_json_object(reviewer_2[0]))
        case = response["cases"][0]
        invalid_ids = set(case["audit"]["invalid_child_sense_ids"])
        child = next(
            row
            for row in case["repair"]["revised_proposal"]["child_sense_repairs"]
            if row["temporary_child_sense_id"] not in invalid_ids
        )
        child["definition_en"] += " changed"
        with tempfile.TemporaryDirectory(prefix="proposal-repair-invalid-") as name:
            response_path = Path(name) / "response.json"
            write_json(response_path, response)
            errors = validate_proposal_repair(source_path, response_path)
        self.assertTrue(any("changed children" in error for error in errors))

    def test_source_mutation_rejects_without_output(self) -> None:
        reviewer_2, reviewer_3 = captured_responses()
        with tempfile.TemporaryDirectory(prefix="proposal-repair-tamper-") as name:
            root = Path(name)
            response = copy.deepcopy(strict_json_object(reviewer_2[0]))
            response["cases"][0]["source_term"] = "changed"
            tampered = root / "tampered.json"
            write_json(tampered, response)
            output = root / "artifact"
            with self.assertRaises(ValueError):
                build_proposal_repair_intake(
                    source_root=SOURCE_ROOT,
                    reviewer_2_responses=[tampered],
                    reviewer_3_responses=reviewer_3,
                    output_root=output,
                    zip_path=root / "artifact.zip",
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
