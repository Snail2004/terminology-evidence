from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from build_r0_repair_reaudit import build_r0_repair_reaudit  # noqa: E402
from common import sha256_file, strict_json_object, strict_jsonl  # noqa: E402
from r0_repair import apply_r0_repair, blank_review  # noqa: E402
from spec import CREATED_AT_DEFAULT  # noqa: E402
from validate_r0_repair_reaudit import validate_repair_reaudit, validate_zip  # noqa: E402


ADJUDICATION_ROOT = (
    PACKAGE_ROOT / "release" / "d2l_fast_track_stage_a_adjudication_result_v1"
)


def _build(output: Path):
    return build_r0_repair_reaudit(
        adjudication_root=ADJUDICATION_ROOT,
        output_root=output,
        created_at=CREATED_AT_DEFAULT,
    )


class R0RepairReauditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.temporary.name)
        cls.artifact_root = cls.temp_root / "r0_reaudit"
        cls.result = _build(cls.artifact_root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_release_validates_and_zip_matches(self) -> None:
        self.assertEqual(
            validate_repair_reaudit(
                self.artifact_root, adjudication_root=ADJUDICATION_ROOT
            ),
            [],
        )
        self.assertEqual(
            validate_zip(Path(self.result["release_zip"]), self.artifact_root), []
        )
        manifest = strict_json_object(self.artifact_root / "manifest.json")
        self.assertEqual(manifest["repair_case_count"], 4)
        self.assertEqual(manifest["definition_repair_count"], 1)
        self.assertEqual(manifest["candidate_target_repair_count"], 4)

    def test_repairs_are_narrow_and_keep_ids_contexts(self) -> None:
        source = {
            row["sense_id"]: row
            for row in strict_jsonl(
                ADJUDICATION_ROOT / "pending" / "r0_repair_queue_4.jsonl"
            )
        }
        repaired = strict_jsonl(self.artifact_root / "repaired_r0_cases_4.jsonl")
        self.assertEqual(len(repaired), 4)
        operation_counts = {"REPLACE_DEFINITION": 0, "REPLACE_CANDIDATE_TARGET": 0}
        for row in repaired:
            original = source[row["sense_id"]]["source_payload"]
            result = row["repaired_source_payload"]
            self.assertEqual(
                [item["candidate_id"] for item in original["candidates"]],
                [item["candidate_id"] for item in result["candidates"]],
            )
            self.assertEqual(
                [item["candidate_slot"] for item in original["candidates"]],
                [item["candidate_slot"] for item in result["candidates"]],
            )
            self.assertEqual(original["evidence_contexts"], result["evidence_contexts"])
            for operation in row["repair_operations"]:
                operation_counts[operation["operation"]] += 1
            targets = [
                item["candidate_target_vi"].strip().casefold()
                for item in result["candidates"]
            ]
            self.assertEqual(len(targets), len(set(targets)))
        self.assertEqual(
            operation_counts,
            {"REPLACE_DEFINITION": 1, "REPLACE_CANDIDATE_TARGET": 4},
        )

    def test_handoff_is_blind_blank_and_has_no_final_labels(self) -> None:
        payload = strict_json_object(
            self.artifact_root / "handoff" / "reviewer_input.json"
        )
        self.assertEqual(payload["case_count"], 4)
        self.assertEqual(payload["reviewer_slot"], "r0_blind_reauditor")
        for case in payload["cases"]:
            self.assertNotIn("reviewer_1", case)
            self.assertNotIn("repair_operations", case)
            self.assertEqual(case["review"], blank_review())
            self.assertEqual(case["provider_call_count"], 0)
            self.assertIsNone(case["stage_b_gold_label"])
            self.assertIsNone(case["final_glossary_decision"])
        with zipfile.ZipFile(self.result["handoff_zip"]) as archive:
            self.assertEqual(
                json.loads(archive.read("reviewer_input.json")), payload
            )

    def test_synthetic_contexts_remain_boundary_only(self) -> None:
        repaired = strict_jsonl(self.artifact_root / "repaired_r0_cases_4.jsonl")
        for row in repaired:
            synthetic = [
                context
                for context in row["repaired_source_payload"]["evidence_contexts"]
                if context["synthetic"]
            ]
            self.assertEqual(len(synthetic), 1)
            self.assertTrue(synthetic[0]["boundary_only"])
            self.assertFalse(synthetic[0]["positive_evidence_eligible"])

    def test_queue_tamper_is_rejected(self) -> None:
        queue = strict_jsonl(
            ADJUDICATION_ROOT / "pending" / "r0_repair_queue_4.jsonl"
        )
        tampered = copy.deepcopy(queue[0])
        tampered["source_payload"]["source_term"] += " tampered"
        with self.assertRaisesRegex(ValueError, "queue record hash mismatch"):
            apply_r0_repair(tampered, "test-policy")

    def test_release_is_deterministic(self) -> None:
        second_root = self.temp_root / "second" / "r0_reaudit"
        second_root.parent.mkdir()
        second = _build(second_root)
        self.assertEqual(
            sha256_file(self.artifact_root / "manifest.json"),
            sha256_file(second_root / "manifest.json"),
        )
        self.assertEqual(self.result["release_zip_sha256"], second["release_zip_sha256"])


if __name__ == "__main__":
    unittest.main()
