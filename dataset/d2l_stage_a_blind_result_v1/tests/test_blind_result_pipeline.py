from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
DATASET_ROOT = PACKAGE_ROOT.parent
REPAIR_RELEASE = DATASET_ROOT / "d2l_stage_a_review_repair_v1_2" / "release"
PACK_ROOT = REPAIR_RELEASE / "blind_audit_pack_development_v1"
sys.path.insert(0, str(TOOLS_ROOT))

from artifact import build_artifact, validate_artifact  # noqa: E402
from common import read_csv, read_json, read_jsonl, write_csv  # noqa: E402
from intake import BLIND_OUTPUT_FIELDS, validate_and_normalize_reviews  # noqa: E402


class BlindResultPipelineTests(unittest.TestCase):
    def _review_rows(self, slot: int) -> list[dict[str, str]]:
        templates = read_csv(PACK_ROOT / "blind_reviewer_1.csv")
        cases = {row["blind_case_id"]: row for row in read_csv(PACK_ROOT / "blind_cases.csv")}
        contexts: dict[str, list[str]] = {}
        for row in read_csv(PACK_ROOT / "blind_contexts.csv"):
            contexts.setdefault(row["blind_case_id"], []).append(row["context_id"])
        rows: list[dict[str, str]] = []
        for template in templates:
            row = dict(template)
            case = cases[row["blind_case_id"]]
            term = case["source_term"]
            delimiter = " | " if slot == 3 else ";"
            evidence = contexts[row["blind_case_id"]]
            row.update(
                {
                    "blind_definition_en": f"Independent definition for {term}, reviewer {slot}.",
                    "blind_part_of_speech": "noun",
                    "positive_definition_evidence_ids": delimiter.join(evidence[:2]),
                    "positive_pos_evidence_ids": delimiter.join(evidence[:1]),
                    "split_recommendation": "NO_SPLIT",
                    "confidence": "0.90",
                    "rationale": "The cited corpus contexts support this decision.",
                    "risk_flags": "NONE",
                }
            )
            if term == "in place":
                row["split_recommendation"] = "SPLIT"
                row["blind_part_of_speech"] = (
                    "adverb"
                    if slot == 1
                    else "adverb_phrase_or_adjective"
                    if slot == 2
                    else "adverb or adjective"
                )
            if term == "contexts" and slot == 3:
                row["split_recommendation"] = "SPLIT"
            rows.append(row)
        return rows

    def _write_reviews(self, root: Path) -> list[Path]:
        paths = []
        for slot in (1, 2, 3):
            path = root / f"reviewer_{slot}.csv"
            write_csv(path, BLIND_OUTPUT_FIELDS, self._review_rows(slot))
            paths.append(path)
        return paths

    def test_semicolon_and_pipe_inputs_build_a_fail_closed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviews = self._write_reviews(root)
            output = root / "artifact"
            summary = build_artifact(
                pack_root=PACK_ROOT,
                review_paths=reviews,
                anchor_reference_path=REPAIR_RELEASE / "blind_audit_anchor_reference.jsonl",
                anchored_consensus_path=REPAIR_RELEASE / "recomputed_consensus_records_v2.jsonl",
                output_root=output,
            )
            self.assertEqual(summary["blind_case_count"], 13)
            self.assertEqual(summary["normalized_review_record_count"], 39)
            self.assertEqual(summary["split_unanimous_count"], 12)
            self.assertEqual(summary["adjudication_case_count"], 3)
            self.assertEqual(
                summary["adjudication_terms"],
                ["contexts", "fully-connected layers", "in place"],
            )
            self.assertIsNone(summary["final_glossary_decision"])
            report = validate_artifact(output)
            self.assertEqual(report["status"], "PASS", report["errors"])
            normalized_three = read_jsonl(output / "normalized_reviews" / "reviewer_3.jsonl")
            self.assertTrue(
                all(isinstance(row["positive_definition_evidence_ids"], list) for row in normalized_three)
            )
            self.assertEqual(
                read_json(output / "provenance" / "reviewer_1.json")["status"],
                "PENDING_OWNER_ATTESTATION",
            )

    def test_exactly_three_distinct_physical_paths_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviews = self._write_reviews(root)
            with self.assertRaisesRegex(ValueError, "Exactly three"):
                validate_and_normalize_reviews(pack_root=PACK_ROOT, review_paths=reviews[:2])
            with self.assertRaisesRegex(ValueError, "distinct physical"):
                validate_and_normalize_reviews(
                    pack_root=PACK_ROOT,
                    review_paths=[reviews[0], reviews[0], reviews[0]],
                )

    def test_distinct_files_with_identical_bytes_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "one.csv"
            write_csv(first, BLIND_OUTPUT_FIELDS, self._review_rows(1))
            paths = [first]
            for name in ("two.csv", "three.csv"):
                path = root / name
                path.write_bytes(first.read_bytes())
                paths.append(path)
            report = validate_and_normalize_reviews(pack_root=PACK_ROOT, review_paths=paths)
            self.assertEqual(len(report["normalized_by_slot"]), 3)
            self.assertEqual(len({row["sha256"] for row in report["input_bindings"]}), 1)

    def test_foreign_evidence_rejects_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviews = self._write_reviews(root)
            rows = read_csv(reviews[1])
            rows[0]["positive_definition_evidence_ids"] = "ctx_not_in_case"
            write_csv(reviews[1], BLIND_OUTPUT_FIELDS, rows)
            output = root / "artifact"
            with self.assertRaisesRegex(ValueError, "foreign context"):
                build_artifact(
                    pack_root=PACK_ROOT,
                    review_paths=reviews,
                    anchor_reference_path=REPAIR_RELEASE / "blind_audit_anchor_reference.jsonl",
                    anchored_consensus_path=REPAIR_RELEASE / "recomputed_consensus_records_v2.jsonl",
                    output_root=output,
                )
            self.assertFalse(output.exists())

    def test_case_identity_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviews = self._write_reviews(root)
            rows = read_csv(reviews[2])
            rows[0]["sense_id"] = "forged_sense"
            write_csv(reviews[2], BLIND_OUTPUT_FIELDS, rows)
            with self.assertRaisesRegex(ValueError, "sense_id drift"):
                validate_and_normalize_reviews(pack_root=PACK_ROOT, review_paths=reviews)

    def test_artifact_validator_rejects_unbound_extra_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviews = self._write_reviews(root)
            output = root / "artifact"
            build_artifact(
                pack_root=PACK_ROOT,
                review_paths=reviews,
                anchor_reference_path=REPAIR_RELEASE / "blind_audit_anchor_reference.jsonl",
                anchored_consensus_path=REPAIR_RELEASE / "recomputed_consensus_records_v2.jsonl",
                output_root=output,
            )
            (output / "unexpected.txt").write_text("not bound\n", encoding="utf-8")
            report = validate_artifact(output)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("artifact file set or file bindings drifted", report["errors"])


if __name__ == "__main__":
    unittest.main()
