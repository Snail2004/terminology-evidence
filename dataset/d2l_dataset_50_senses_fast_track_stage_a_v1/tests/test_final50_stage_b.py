from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from tools.build_final50_stage_b import build_final50_stage_b
from tools.final50 import assign_splits, select_exact_50
from tools.validate_final50_stage_b import validate_artifact, validate_zip


class Final50StageBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.namespace = Path(__file__).resolve().parents[1]
        cls.repo_root = cls.namespace.parents[1]
        cls.release = cls.namespace / "release"
        cls.temporary = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temporary.name)
        cls.base_root = cls.work / "base"
        cls.base_root.mkdir()
        with zipfile.ZipFile(cls.release / "d2l_dataset_50_senses_fast_track_stage_a_v1_release.zip") as archive:
            archive.extractall(cls.base_root)
        cls.pool = [
            json.loads(line)
            for line in (cls.base_root / "master_pool_60.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        cls.contexts = [
            json.loads(line)
            for line in (cls.base_root / "contexts_selected.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        cls.output = cls.work / "final50"
        cls.result = build_final50_stage_b(
            repo_root=cls.repo_root,
            base_release_zip=cls.release / "d2l_dataset_50_senses_fast_track_stage_a_v1_release.zip",
            intake_release_zip=cls.release / "d2l_fast_track_stage_a_review_intake_v1_release.zip",
            adjudication_release_zip=cls.release / "d2l_fast_track_stage_a_adjudication_result_v1_release.zip",
            r0_result_release_zip=cls.release / "d2l_fast_track_stage_a_r0_reaudit_result_v1_release.zip",
            output_root=cls.output,
            created_at="2026-07-29T17:00:00Z",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_selection_freezes_exact_lane_and_stratum_quotas(self) -> None:
        selected, excluded, swaps = select_exact_50(self.pool, self.contexts)
        self.assertEqual(len(selected), 50)
        self.assertEqual(len(excluded), 10)
        self.assertEqual(
            Counter(row["lane"] for row in selected),
            Counter({"A_OFFICIAL": 5, "B_REVIEW_READY": 6, "C_REPAIRED": 4, "D_NEW": 35}),
        )
        self.assertEqual(
            Counter(row["stratum"] for row in selected),
            Counter({"clear": 15, "ambiguous": 20, "collision_or_multi_target": 15}),
        )
        self.assertGreaterEqual(len(swaps), 1)

    def test_split_is_exact_and_leakage_safe(self) -> None:
        selected, _, _ = select_exact_50(self.pool, self.contexts)
        assignments, components = assign_splits(selected, self.contexts)
        self.assertEqual(Counter(assignments.values()), Counter({"development": 30, "validation": 10, "test": 10}))
        self.assertTrue(all(len({row["split"]}) == 1 for row in components))

    def test_full_builder_contract_and_reviewer_gate_passes(self) -> None:
        self.assertEqual(self.result["status"], "READY_FOR_STAGE_B_DUAL_REVIEW")
        self.assertEqual(validate_artifact(self.output, contracts_root=self.repo_root / "terminology_contracts_v1"), [])
        self.assertEqual(validate_zip(Path(self.result["reviewer_handoff_zip"]), self.output), [])
        self.assertEqual(self.result["counts"]["term_sense"], 50)
        self.assertEqual(self.result["counts"]["candidate"], 150)

    def test_reviewer_inputs_are_blank_and_independent(self) -> None:
        payloads = [
            json.loads((self.output / f"reviewer_{slot}_full_input.json").read_text(encoding="utf-8"))
            for slot in (1, 2)
        ]
        self.assertTrue(all(payload["case_count"] == 150 for payload in payloads))
        self.assertTrue(all(case["review"]["review_status"] == "" for payload in payloads for case in payload["cases"]))
        order_1 = [case["source_payload"]["candidate_id"] for case in payloads[0]["cases"]]
        order_2 = [case["source_payload"]["candidate_id"] for case in payloads[1]["cases"]]
        self.assertNotEqual(order_1, order_2)

    def test_official_candidate_id_text_and_hash_are_preserved(self) -> None:
        source = [
            json.loads(line)
            for line in (self.base_root / "candidate_inventory_180.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        official = {row["candidate_id"]: row for row in source if row["lane"] == "A_OFFICIAL"}
        final = [
            json.loads(line)
            for line in (self.output / "candidate_instances_150.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        projected = {row["candidate_instance_id"]: row for row in final if row["candidate_instance_id"] in official}
        self.assertEqual(set(projected), set(official))
        for candidate_id, source_row in official.items():
            self.assertEqual(projected[candidate_id]["candidate_target_vi"], source_row["candidate_target_vi"])
            self.assertEqual(projected[candidate_id]["candidate_instance_sha256"], source_row["source_candidate_sha256"])

    def test_no_gold_or_final_decision_is_autofilled(self) -> None:
        candidates = [
            json.loads(line)
            for line in (self.output / "candidate_instances_150.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(all(row["final_gold_label"] is None for row in candidates))
        self.assertTrue(all(row["final_glossary_decision"] is None for row in candidates))


if __name__ == "__main__":
    unittest.main()
