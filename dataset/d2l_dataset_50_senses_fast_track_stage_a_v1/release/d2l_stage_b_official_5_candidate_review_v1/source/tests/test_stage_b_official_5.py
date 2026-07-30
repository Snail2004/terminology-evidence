from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from build_stage_b_official_5 import build_stage_b_official_5  # noqa: E402
from common import sha256_file, strict_json_object  # noqa: E402
from spec import CREATED_AT_DEFAULT  # noqa: E402
from validate_stage_b_official_5 import validate_artifact, validate_zip  # noqa: E402


OFFICIAL_ROOT = (
    PACKAGE_ROOT.parent
    / "d2l_stage_a_pilot_5_senses_official_v1"
    / "release"
    / "d2l_stage_a_pilot_5_senses_official_v1"
)


def _build(output: Path):
    return build_stage_b_official_5(
        official_root=OFFICIAL_ROOT,
        output_root=output,
        created_at=CREATED_AT_DEFAULT,
    )


class StageBOfficial5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name) / "artifact"
        cls.result = _build(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_release_has_two_blind_15_case_inputs(self) -> None:
        self.assertEqual(validate_artifact(self.root), [])
        self.assertEqual(validate_zip(Path(self.result["release_zip"]), self.root), [])
        for slot in ("reviewer_1", "reviewer_2"):
            payload = strict_json_object(self.root / f"{slot}_input.json")
            self.assertEqual(payload["case_count"], 15)
            self.assertEqual(len(payload["cases"]), 15)

    def test_no_candidate_role_or_evaluation_output_is_exposed(self) -> None:
        forbidden = {
            "candidate_role",
            "intended_candidate_role",
            "final_gold_label",
            "c_score",
            "e_evidence",
            "global_decision",
        }
        for slot in ("reviewer_1", "reviewer_2"):
            payload = strict_json_object(self.root / f"{slot}_input.json")
            for case in payload["cases"]:
                keys = set(case["source_payload"])
                self.assertFalse(forbidden & keys)
                self.assertEqual(case["review"]["candidate_gold_label"], "")

    def test_reviewer_source_sets_are_equal_but_order_is_independent(self) -> None:
        first = strict_json_object(self.root / "reviewer_1_input.json")
        second = strict_json_object(self.root / "reviewer_2_input.json")
        first_ids = {case["source_payload"]["candidate_id"] for case in first["cases"]}
        second_ids = {case["source_payload"]["candidate_id"] for case in second["cases"]}
        self.assertEqual(first_ids, second_ids)
        self.assertNotEqual(
            [case["source_payload"]["candidate_id"] for case in first["cases"]],
            [case["source_payload"]["candidate_id"] for case in second["cases"]],
        )

    def test_synthetic_contexts_are_boundary_only(self) -> None:
        for slot in ("reviewer_1", "reviewer_2"):
            payload = strict_json_object(self.root / f"{slot}_input.json")
            for case in payload["cases"]:
                for context in case["source_payload"]["contexts"]:
                    if context["synthetic"]:
                        self.assertTrue(context["boundary_only"])

    def test_source_authority_drift_rejects_without_output(self) -> None:
        official_copy = self.root.parent / "official_copy"
        shutil.copytree(OFFICIAL_ROOT, official_copy)
        manifest = official_copy / "manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["manifest_sha256"] = "0" * 64
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        output = self.root.parent / "drift_output"
        with self.assertRaisesRegex(ValueError, "authority hash mismatch"):
            build_stage_b_official_5(
                official_root=official_copy,
                output_root=output,
                created_at=CREATED_AT_DEFAULT,
            )
        self.assertFalse(output.exists())

    def test_release_is_deterministic(self) -> None:
        second = self.root.parent / "second" / "artifact"
        second.parent.mkdir()
        result = _build(second)
        self.assertEqual(
            sha256_file(self.root / "manifest.json"),
            sha256_file(second / "manifest.json"),
        )
        self.assertEqual(self.result["release_zip_sha256"], result["release_zip_sha256"])


if __name__ == "__main__":
    unittest.main()
