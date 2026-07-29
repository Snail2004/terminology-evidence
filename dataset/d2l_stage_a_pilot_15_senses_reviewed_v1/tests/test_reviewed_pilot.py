from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

NAMESPACE = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(NAMESPACE))

from tools.common import read_jsonl
from tools.review_contract import check_receipt_hashes
from tools.validate_reviewed_pilot import validate_artifact


REPO_RELEASE = NAMESPACE / "release" / "d2l_stage_a_pilot_15_senses_reviewed_v1"
ARTIFACT = REPO_RELEASE if REPO_RELEASE.is_dir() else NAMESPACE.parent
DEFAULT_HANDOFF = ARTIFACT.parent / "d2l_stage_a_pilot_15_senses_reviewed_v1_reviewer_handoff.zip"
HANDOFF = Path(os.environ.get("D2L_REVIEWED_PILOT_ZIP", DEFAULT_HANDOFF))


class ReviewedPilotArtifactTests(unittest.TestCase):
    def test_release_gate_passes(self) -> None:
        report = validate_artifact(ARTIFACT, HANDOFF if HANDOFF.is_file() else None)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["selected_sense_count"], 15)
        self.assertEqual(report["ready_resolution_count"], 11)
        self.assertEqual(report["pending_resolution_count"], 4)

    def test_decisions_are_sealed_and_final_decision_is_null(self) -> None:
        rows = read_jsonl(ARTIFACT / "merged_review_decisions_15.jsonl")
        self.assertEqual(len(rows), 15)
        self.assertTrue(all(row["final_glossary_decision"] is None for row in rows))
        self.assertEqual(
            {row["resolution_status"] for row in rows},
            {"READY_FOR_CONTRACT_CONSTRUCTION", "REVISION_REQUIRED", "SPLIT_REQUIRED", "UNRESOLVED"},
        )

    def test_stage_b_has_no_automatic_gold(self) -> None:
        text = (ARTIFACT / "stage_b_annotation_template_45.csv").read_text(encoding="utf-8-sig")
        rows = list(__import__("csv").DictReader(text.splitlines()))
        self.assertEqual(len(rows), 45)
        for row in rows:
            self.assertEqual(row["candidate_gold_label"], "")
            self.assertEqual(row["vietnamese_evidence_refs"], "")

    def test_tampered_decision_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp) / ARTIFACT.name
            shutil.copytree(ARTIFACT, copied)
            path = copied / "merged_review_decisions_15.jsonl"
            rows = path.read_text(encoding="utf-8").splitlines()
            first = json.loads(rows[0])
            first["final_decision"] = "REVISE"
            rows[0] = json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
            report = validate_artifact(copied)
            self.assertEqual(report["status"], "FAIL")

    def test_three_human_identities_are_retained(self) -> None:
        provenance = read_jsonl(ARTIFACT / "review_provenance_15_senses.jsonl")
        adjudication = read_jsonl(ARTIFACT / "stage_a_adjudication_15_senses.jsonl")
        ids = {row["reviewer_id"] for row in provenance} | {row["adjudicator_id"] for row in adjudication}
        self.assertEqual(ids, {"diemphuong", "reviewer_2", "snail"})

    def test_review_input_hash_drift_is_rejected(self) -> None:
        inputs = ARTIFACT / "review_inputs"
        with tempfile.TemporaryDirectory() as temp:
            mutated = Path(temp) / "reviewer_1.csv"
            shutil.copyfile(inputs / "reviewer_1.csv", mutated)
            mutated.write_bytes(mutated.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                check_receipt_hashes(
                    {
                        "reviewer_1": mutated,
                        "reviewer_2": inputs / "reviewer_2.csv",
                        "blind_audit": inputs / "reviewer_2_blind_audit.csv",
                        "adjudicator": inputs / "adjudicator.csv",
                    },
                    inputs / "INTAKE_RECEIPT.txt",
                )


if __name__ == "__main__":
    unittest.main()
