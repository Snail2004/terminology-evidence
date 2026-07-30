from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_file_inventory,
    canonical_json_bytes,
    seal_record,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    write_checksums,
    write_json,
    write_jsonl,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_followup_result import (
    build_followup_result,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_followup_result import (
    validate_artifact,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_ROOT = PROJECT_ROOT / "dataset" / "d2l_dataset_remaining_100_stage_a_v1"
RELEASE_ROOT = DATASET_ROOT / "release"
FOLLOWUP_ROOT = RELEASE_ROOT / "d2l_dataset_remaining_100_stage_a_followup_intake_v1"
INITIAL_ROOT = RELEASE_ROOT / "d2l_dataset_remaining_100_stage_a_review_intake_v1"
REVIEWER_3_ROOT = RELEASE_ROOT / "d2l_dataset_remaining_100_stage_a_reviewer3_corrected_v1"
ARTIFACT_ROOT = RELEASE_ROOT / "d2l_dataset_remaining_100_stage_a_followup_result_v1"
ZIP_PATH = RELEASE_ROOT / "d2l_dataset_remaining_100_stage_a_followup_result_v1.zip"


def captured_responses(root: Path = ARTIFACT_ROOT) -> tuple[list[Path], list[Path]]:
    reviewer_4 = sorted((root / "captures").glob("*/reviewer_4/*.json"))
    reviewer_5 = sorted((root / "captures").glob("*/reviewer_5/*.json"))
    return reviewer_4, reviewer_5


class FollowupResultTests(unittest.TestCase):
    def test_release_validates(self) -> None:
        self.assertEqual(validate_artifact(ARTIFACT_ROOT), [])

    def test_closure_and_repair_routing(self) -> None:
        closure = strict_jsonl(ARTIFACT_ROOT / "closure_index_100.jsonl")
        self.assertEqual(len(closure), 100)
        self.assertEqual(
            sum(row["stage_a_status"] == "READY" for row in closure), 95
        )
        revisions = strict_jsonl(
            ARTIFACT_ROOT / "routing" / "high_risk_revision_required_4.jsonl"
        )
        self.assertEqual(
            {row["source_term"] for row in revisions},
            {"attention", "blocks", "inverse", "shape"},
        )
        reviewer_2 = strict_json_object(
            ARTIFACT_ROOT
            / "repair_batches"
            / "high_risk_proposal_repair_reviewer_2"
            / "repair_input.json"
        )
        reviewer_3 = strict_json_object(
            ARTIFACT_ROOT
            / "repair_batches"
            / "high_risk_proposal_repair_reviewer_3"
            / "repair_input.json"
        )
        self.assertEqual(reviewer_2["case_count"], 3)
        self.assertEqual(reviewer_3["case_count"], 1)

    def test_rebuild_is_byte_deterministic(self) -> None:
        reviewer_4, reviewer_5 = captured_responses()
        with tempfile.TemporaryDirectory(prefix="followup-result-rebuild-") as name:
            root = Path(name)
            output = root / "artifact"
            zip_path = root / "artifact.zip"
            build_followup_result(
                followup_root=FOLLOWUP_ROOT,
                initial_intake_root=INITIAL_ROOT,
                reviewer_3_corrected_root=REVIEWER_3_ROOT,
                reviewer_4_responses=reviewer_4,
                reviewer_5_responses=reviewer_5,
                output_root=output,
                zip_path=zip_path,
            )
            self.assertEqual(sha256_file(zip_path), sha256_file(ZIP_PATH))
            self.assertEqual(validate_artifact(output), [])

    def test_source_mutation_rejects_without_output(self) -> None:
        reviewer_4, reviewer_5 = captured_responses()
        with tempfile.TemporaryDirectory(prefix="followup-result-tamper-") as name:
            root = Path(name)
            tampered = root / "tampered.json"
            payload = copy.deepcopy(strict_json_object(reviewer_4[0]))
            payload["cases"][0]["source_payload"]["source_term"] = "changed"
            write_json(tampered, payload)
            responses = [tampered, *reviewer_4[1:]]
            output = root / "artifact"
            with self.assertRaises(ValueError):
                build_followup_result(
                    followup_root=FOLLOWUP_ROOT,
                    initial_intake_root=INITIAL_ROOT,
                    reviewer_3_corrected_root=REVIEWER_3_ROOT,
                    reviewer_4_responses=responses,
                    reviewer_5_responses=reviewer_5,
                    output_root=output,
                    zip_path=root / "artifact.zip",
                )
            self.assertFalse(output.exists())

    def test_resealed_closure_authority_drift_rejects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="followup-result-authority-") as name:
            copied = Path(name) / "artifact"
            shutil.copytree(ARTIFACT_ROOT, copied)
            closure = strict_jsonl(copied / "closure_index_100.jsonl")
            closure[0]["authority_record_sha256"] = "0" * 64
            closure[0] = seal_record(closure[0])
            write_jsonl(copied / "closure_index_100.jsonl", closure)
            manifest = strict_json_object(copied / "manifest.json")
            manifest["files"] = build_file_inventory(
                copied, {"CHECKSUMS.sha256", "manifest.json"}
            )
            manifest["file_count"] = len(manifest["files"])
            manifest.pop("manifest_sha256", None)
            manifest["manifest_sha256"] = sha256_bytes(
                canonical_json_bytes(manifest)
            )
            write_json(copied / "manifest.json", manifest)
            write_checksums(copied, copied / "CHECKSUMS.sha256")
            errors = validate_artifact(copied)
            self.assertTrue(
                any("closure authority binding mismatch" in error for error in errors)
            )


if __name__ == "__main__":
    unittest.main()
