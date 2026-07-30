from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
    strict_jsonl,
    write_json,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_final_closure import (
    build_final_closure,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_final_closure import (
    validate_artifact,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = PACKAGE_ROOT / "release"
PROPOSAL_ROOT = RELEASE_ROOT / "d2l_remaining100_proposal_repair_v1"
PRIOR_CLOSURE_ROOT = (
    RELEASE_ROOT / "d2l_dataset_remaining_100_stage_a_followup_result_v1"
)
ARTIFACT_ROOT = RELEASE_ROOT / "d2l_remaining100_final_closure_v1"
ZIP_PATH = RELEASE_ROOT / "d2l_remaining100_final_closure_v1.zip"
REVIEWER_4 = (
    ARTIFACT_ROOT / "captures" / "reviewer_4" / "proposal_reaudit_reviewer_4.json"
)
REVIEWER_5 = (
    ARTIFACT_ROOT / "captures" / "reviewer_5" / "proposal_reaudit_reviewer_5.json"
)


class FinalClosureTests(unittest.TestCase):
    def _build(
        self,
        output_root: Path,
        zip_path: Path,
        reviewer_4: Path = REVIEWER_4,
        reviewer_5: Path = REVIEWER_5,
        after_inventory=None,
    ) -> None:
        build_final_closure(
            proposal_root=PROPOSAL_ROOT,
            prior_closure_root=PRIOR_CLOSURE_ROOT,
            reviewer_4_response=reviewer_4,
            reviewer_5_response=reviewer_5,
            output_root=output_root,
            zip_path=zip_path,
            after_inventory=after_inventory,
        )

    def test_release_validates(self) -> None:
        self.assertEqual(validate_artifact(ARTIFACT_ROOT), [])

    def test_exact_closure_and_child_counts(self) -> None:
        approvals = strict_jsonl(
            ARTIFACT_ROOT / "approved_repaired_split_proposals_4.jsonl"
        )
        children = strict_jsonl(
            ARTIFACT_ROOT / "approved_child_sense_projections_9.jsonl"
        )
        closure = strict_jsonl(ARTIFACT_ROOT / "closure_index_100.jsonl")
        self.assertEqual({row["source_term"] for row in approvals}, {
            "attention",
            "blocks",
            "inverse",
            "shape",
        })
        self.assertEqual(len(children), 9)
        self.assertEqual(len(closure), 100)
        self.assertEqual(
            sum(row["stage_a_status"] == "READY" for row in closure), 99
        )
        self.assertEqual(
            [row["source_term"] for row in closure if row["stage_a_status"] == "BLOCKED"],
            ["switch"],
        )

    def test_rebuild_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="final-closure-rebuild-") as name:
            output = Path(name) / "artifact"
            zip_path = Path(name) / "artifact.zip"
            self._build(output, zip_path)
            self.assertEqual(validate_artifact(output), [])
            self.assertEqual(sha256_file(zip_path), sha256_file(ZIP_PATH))

    def test_immutable_source_mutation_rejects_without_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="final-closure-mutation-") as name:
            temp = Path(name)
            reviewer_4 = temp / "reviewer_4.json"
            payload = strict_json_object(REVIEWER_4)
            payload["cases"][0]["source_term"] = "changed"
            write_json(reviewer_4, payload)
            output = temp / "artifact"
            with self.assertRaises(ValueError):
                self._build(output, temp / "artifact.zip", reviewer_4=reviewer_4)
            self.assertFalse(output.exists())

    def test_nonapproval_rejects_without_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="final-closure-block-") as name:
            temp = Path(name)
            reviewer_4 = temp / "reviewer_4.json"
            payload = strict_json_object(REVIEWER_4)
            payload["cases"][0]["audit"].update(
                {
                    "audit_decision": "BLOCK",
                    "audit_notes": "The repaired proposal remains blocked.",
                    "audit_status": "COMPLETE",
                    "invalid_child_sense_ids": [],
                }
            )
            write_json(reviewer_4, payload)
            output = temp / "artifact"
            with self.assertRaises(ValueError):
                self._build(output, temp / "artifact.zip", reviewer_4=reviewer_4)
            self.assertFalse(output.exists())

    def test_source_drift_rejects_without_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="final-closure-drift-") as name:
            temp = Path(name)
            reviewer_4 = temp / "reviewer_4.json"
            reviewer_5 = temp / "reviewer_5.json"
            reviewer_4.write_bytes(REVIEWER_4.read_bytes())
            reviewer_5.write_bytes(REVIEWER_5.read_bytes())

            def mutate_after_inventory() -> None:
                payload = json.loads(reviewer_4.read_text(encoding="utf-8"))
                payload["cases"][0]["audit"]["audit_notes"] += " changed"
                write_json(reviewer_4, payload)

            output = temp / "artifact"
            with self.assertRaises(ValueError):
                self._build(
                    output,
                    temp / "artifact.zip",
                    reviewer_4=reviewer_4,
                    reviewer_5=reviewer_5,
                    after_inventory=mutate_after_inventory,
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
