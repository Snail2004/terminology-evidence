from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.review_intake import (
    build_review_intake,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_review_intake import (
    validate_intake,
)


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
CANONICAL_ROOT = RELEASE / "d2l_dataset_remaining_100_stage_a_v1"
ARTIFACT_ROOT = RELEASE / "d2l_dataset_remaining_100_stage_a_review_intake_v1"
ZIP_PATH = RELEASE / "d2l_dataset_remaining_100_stage_a_review_intake_v1_reviewer_handoff.zip"


class Remaining100ReviewIntakeTests(unittest.TestCase):
    def test_release_validates(self) -> None:
        self.assertEqual(
            validate_intake(ARTIFACT_ROOT, canonical_root=CANONICAL_ROOT), []
        )

    def test_rebuild_is_deterministic_from_packaged_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "intake"
            result = build_review_intake(
                canonical_root=CANONICAL_ROOT,
                reviewer_1_root=ARTIFACT_ROOT / "raw_reviews" / "reviewer_1",
                reviewer_2_root=ARTIFACT_ROOT / "raw_reviews" / "reviewer_2",
                repair_source_root=ARTIFACT_ROOT / "repair",
                repair_response_path=ARTIFACT_ROOT
                / "repair"
                / "reviewer_2_repair_response.json",
                output_root=output,
                created_at="2026-07-30T00:00:00Z",
            )
            expected_manifest = strict_json_object(ARTIFACT_ROOT / "manifest.json")
            self.assertEqual(
                result["manifest_sha256"], expected_manifest["manifest_sha256"]
            )
            self.assertEqual(result["release_zip_sha256"], sha256_file(ZIP_PATH))

    def test_route_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            copied = Path(temp_dir) / "intake"
            shutil.copytree(ARTIFACT_ROOT, copied)
            path = copied / "route_index_100.jsonl"
            lines = path.read_text(encoding="utf-8").splitlines()
            row = json.loads(lines[0])
            row["route"] = "R3_DUAL_AGREEMENT"
            lines[0] = json.dumps(row, ensure_ascii=False, sort_keys=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            errors = validate_intake(copied, canonical_root=CANONICAL_ROOT)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
