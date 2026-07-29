from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

NAMESPACE = Path(__file__).resolve().parents[1]
REPO_ROOT = NAMESPACE.parents[1]
TOOLS = NAMESPACE / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from build_remaining100_stage_a import (  # type: ignore  # noqa: E402
    ARTIFACT_NAME,
    EXCLUDED_PARENT_IDS,
    build_remaining100_stage_a,
)
from validate_remaining100_stage_a import validate_artifact  # type: ignore  # noqa: E402


V3_ROOT = REPO_ROOT / "dataset" / "d2l_context_support_set_validation_ready_v3"
SELECTED50_ROOT = (
    REPO_ROOT
    / "dataset"
    / "d2l_dataset_50_senses_fast_track_stage_a_v1"
    / "release"
    / "d2l_dataset_50_senses_150_candidates_stage_b_review_v1"
)


class Remaining100StageATest(unittest.TestCase):
    def _build(self) -> Path:
        temp = Path(tempfile.mkdtemp(prefix="remaining100-test-"))
        output = temp / ARTIFACT_NAME
        result = build_remaining100_stage_a(
            v3_root=V3_ROOT,
            selected50_root=SELECTED50_ROOT,
            output_root=output,
            created_at="2026-07-30T12:00:00Z",
        )
        self.assertEqual(result["status"], "READY_FOR_STAGE_A_RISK_REVIEW")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        return output

    def test_build_has_exact_remaining_population(self) -> None:
        root = self._build()
        terms = [json.loads(line) for line in (root / "term_senses_100.jsonl").read_text(encoding="utf-8").splitlines()]
        candidates = [json.loads(line) for line in (root / "candidate_instances_300.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(terms), 100)
        self.assertEqual(len(candidates), 300)
        self.assertTrue(EXCLUDED_PARENT_IDS.isdisjoint({row["sense_id"] for row in terms}))
        self.assertFalse((root / ".handoff").exists())
        self.assertEqual(validate_artifact(root, v3_root=V3_ROOT), [])

    def test_risk_routing_and_batches_are_deterministic(self) -> None:
        root = self._build()
        index = json.loads((root / "batch_index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["batches"]), 10)
        self.assertEqual([row["sense_count"] for row in index["batches"]], [10] * 10)
        reviewer_1 = json.loads((root / "reviewer_1_full_input.json").read_text(encoding="utf-8"))
        reviewer_2 = json.loads((root / "reviewer_2_full_input.json").read_text(encoding="utf-8"))
        self.assertEqual(reviewer_1["case_count"], 100)
        self.assertEqual(reviewer_2["case_count"], 65)
        projected_contexts = [
            context
            for case in reviewer_1["cases"]
            for context in case["source_payload"]["evidence_contexts"]
        ]
        synthetic = [context for context in projected_contexts if context["synthetic"]]
        self.assertEqual(len(synthetic), 94)
        self.assertTrue(all(context["boundary_only"] for context in synthetic))
        self.assertTrue(all(context["sense_relation"] != "SAME_SENSE" for context in synthetic))
        self.assertTrue(all(case["review"] == {
            "definition_decision": "",
            "corrected_definition_en": "",
            "part_of_speech_decision": "",
            "corrected_part_of_speech": "",
            "scope_decision": "",
            "corrected_scope": "",
            "evidence_decision": "",
            "invalid_evidence_context_ids": [],
            "candidate_set_decision": "",
            "candidate_replacements": [],
            "sense_status": "",
            "proposed_split_labels": [],
            "review_notes": "",
            "review_status": "",
        } for case in reviewer_1["cases"] + reviewer_2["cases"]))

    def test_parent_tamper_fails_closed(self) -> None:
        root = self._build()
        path = root / "term_senses_100.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[0]["definition"] = "tampered"
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")
        errors = validate_artifact(root, v3_root=V3_ROOT)
        self.assertTrue(any("checksum inventory mismatch" in error for error in errors))
        self.assertTrue(any("not exact V3 subset" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
