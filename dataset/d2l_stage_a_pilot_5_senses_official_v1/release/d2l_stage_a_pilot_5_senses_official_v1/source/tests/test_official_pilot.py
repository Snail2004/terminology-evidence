from __future__ import annotations

import copy
import csv
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


NAMESPACE = Path(__file__).resolve().parents[1]
REPO_ROOT = NAMESPACE.parents[1]
if str(NAMESPACE) not in sys.path:
    sys.path.insert(0, str(NAMESPACE))

from tools.build_official_pilot import (  # noqa: E402
    _build_blind_records,
    _load_inputs,
    build_official_pilot,
)
from tools.common import (  # noqa: E402
    strict_json_loads,
    strict_json_object,
    strict_jsonl,
)
from tools.validate_official_pilot import validate_artifact, validate_zip  # noqa: E402


REVIEWED_ROOT = (
    REPO_ROOT
    / "dataset"
    / "d2l_stage_a_pilot_15_senses_reviewed_v1"
    / "release"
    / "d2l_stage_a_pilot_15_senses_reviewed_v1"
)
V3_ROOT = REPO_ROOT / "dataset" / "d2l_context_support_set_validation_ready_v3"
CONTRACTS_ROOT = REPO_ROOT / "terminology_contracts_v1"


class OfficialPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.output = cls.base / "first" / "d2l_stage_a_pilot_5_senses_official_v1"
        cls.output.parent.mkdir()
        cls.result = build_official_pilot(
            repo_root=REPO_ROOT,
            reviewed_root=REVIEWED_ROOT,
            v3_root=V3_ROOT,
            contracts_root=CONTRACTS_ROOT,
            output_root=cls.output,
            created_at="2026-07-29T08:00:00Z",
        )
        cls.zip_path = cls.output.parent / (
            "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_release_gate_and_counts(self) -> None:
        self.assertEqual(self.result["status"], "READY_FOR_REAL_PILOT_REVIEW")
        self.assertEqual(validate_artifact(self.output, CONTRACTS_ROOT), [])
        self.assertEqual(validate_zip(self.zip_path, self.output), [])
        manifest = strict_json_object(self.output / "manifest.json")
        self.assertEqual(manifest["counts"]["effective_sense_contract"], 5)
        self.assertEqual(manifest["counts"]["frozen_candidate_contract"], 15)
        self.assertEqual(manifest["counts"]["constraint_evidence_package"], 15)

    def test_stage_b_is_33_eligible_12_blocked_with_zero_gold(self) -> None:
        with (self.output / "stage_b_template_45.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(
            Counter(row["stage_b_eligibility"] for row in rows),
            Counter({"ELIGIBLE": 33, "BLOCKED_BY_STAGE_A": 12}),
        )
        self.assertTrue(all(row["candidate_gold_label"] == "" for row in rows))

    def test_exact_five_selection_and_role_specific_evidence(self) -> None:
        selection = strict_json_object(
            self.output / "integration_pilot_5_sense_selection_receipt.json"
        )
        self.assertEqual(
            {row["source_term"] for row in selection["records"]},
            {
                "null hypothesis",
                "output gate",
                "Jupyter notebook",
                "learning rate",
                "contexts",
            },
        )
        bindings = [
            strict_json_object(path)
            for path in (self.output / "review_bindings_5").glob("*.json")
        ]
        self.assertEqual(len(bindings), 5)
        for binding in bindings:
            self.assertTrue(binding["positive_definition_evidence_ids"])
            self.assertTrue(binding["positive_pos_evidence_ids"])
            self.assertTrue(binding["boundary_context_ids"])
            self.assertTrue(binding["review_provenance_refs"])

    def test_blind_audit_is_case_bound(self) -> None:
        blind = {
            row["sense_id"]: row
            for row in strict_jsonl(self.output / "blind_audit_records_3.jsonl")
        }
        companion = strict_jsonl(
            self.output / "updated_reviewed_stage_a_companion_15.jsonl"
        )
        r0 = [row for row in companion if row["risk_class"] == "R0_CLEAR"]
        self.assertEqual(len(r0), 3)
        for row in r0:
            self.assertEqual(
                row["blind_audit_ref"]["blind_audit_record_sha256"],
                blind[row["sense_id"]]["blind_audit_record_sha256"],
            )

    def test_builder_rejects_blind_semantic_conflict(self) -> None:
        data = _load_inputs(REVIEWED_ROOT, V3_ROOT, CONTRACTS_ROOT)
        tampered = copy.deepcopy(data)
        tampered["blind_rows"][0]["consensus_split_decision"] = "SPLIT_REQUIRED"
        with self.assertRaisesRegex(ValueError, "NO_SPLIT"):
            _build_blind_records(tampered)

    def test_strict_json_rejects_unsafe_inputs(self) -> None:
        invalid = (
            '{"a":1,"a":2}',
            '{"value":NaN}',
            '{"value":Infinity}',
            '{"value":1e9999}',
            '{"a":1} trailing',
        )
        for text in invalid:
            with self.subTest(text=text), self.assertRaises((ValueError, json.JSONDecodeError)):
                strict_json_loads(text)

    def test_reference_only_parent_layout(self) -> None:
        self.assertFalse((self.output / "source_dataset").exists())
        refs = list((self.output / "lineage").glob("*.json"))
        self.assertEqual(len(refs), 3)
        for path in refs:
            record = strict_json_object(path)
            self.assertTrue(record["reference_only"])
            self.assertFalse(record["materialized_package"])
            self.assertFalse(record["original_checksums_file_copied"])

    def test_deterministic_rebuild(self) -> None:
        second = self.base / "second" / "d2l_stage_a_pilot_5_senses_official_v1"
        second.parent.mkdir()
        result = build_official_pilot(
            repo_root=REPO_ROOT,
            reviewed_root=REVIEWED_ROOT,
            v3_root=V3_ROOT,
            contracts_root=CONTRACTS_ROOT,
            output_root=second,
            created_at="2026-07-29T08:00:00Z",
        )
        self.assertEqual(result["manifest_sha256"], self.result["manifest_sha256"])
        self.assertEqual(
            result["reviewer_handoff_zip_sha256"],
            self.result["reviewer_handoff_zip_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
