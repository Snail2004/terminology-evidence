from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from build_fast_track_stage_a import build_fast_track_stage_a  # noqa: E402
from common import sha256_file, strict_json_object, strict_jsonl  # noqa: E402
from spec import CREATED_AT_DEFAULT, SOURCE_DOCUMENT_SHA256  # noqa: E402
from validate_fast_track_stage_a import validate_artifact, validate_zip  # noqa: E402


SOURCE_DOCUMENT = Path(
    r"C:\work\agent-based-translation-d2l-direct-builder-v1\jobs"
    r"\src_d2l_full_book_local_b858af3a5252\source_package_snapshot\document.json"
)


def _source_roots() -> dict[str, Path]:
    dataset_root = REPOSITORY_ROOT / "dataset"
    return {
        "v3_root": dataset_root / "d2l_context_support_set_validation_ready_v3",
        "source_batch_root": dataset_root / "d2l_stage_a_review_batches_v1" / "release",
        "official_5_root": dataset_root
        / "d2l_stage_a_pilot_5_senses_official_v1"
        / "release"
        / "d2l_stage_a_pilot_5_senses_official_v1",
        "reviewed_15_root": dataset_root
        / "d2l_stage_a_pilot_15_senses_reviewed_v1"
        / "release"
        / "d2l_stage_a_pilot_15_senses_reviewed_v1",
        "repaired_5_root": dataset_root
        / "d2l_stage_a_targeted_repair_review_complete_5_senses_v1"
        / "release"
        / "d2l_stage_a_targeted_repair_review_complete_5_senses_v1",
    }


def _build(output_root: Path, source_document: Path = SOURCE_DOCUMENT) -> dict:
    return build_fast_track_stage_a(
        **_source_roots(),
        source_document=source_document,
        output_root=output_root,
        created_at=CREATED_AT_DEFAULT,
    )


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


class FastTrackStageATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.temporary.name)
        cls.artifact_root = cls.temp_root / "artifact"
        cls.result = _build(cls.artifact_root)
        cls.pool = strict_jsonl(cls.artifact_root / "master_pool_60.jsonl")
        cls.candidates = strict_jsonl(
            cls.artifact_root / "candidate_inventory_180.jsonl"
        )
        cls.contexts = strict_jsonl(cls.artifact_root / "contexts_selected.jsonl")
        cls.batch_index = _json(cls.artifact_root / "batch_index.json")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_release_validates_with_exact_phase_one_and_two_counts(self) -> None:
        self.assertEqual(validate_artifact(self.artifact_root), [])
        release_zip = Path(self.result["release_zip"])
        self.assertEqual(validate_zip(release_zip, self.artifact_root), [])
        self.assertEqual(
            self.result["counts"],
            {
                "sense_pool": 60,
                "candidate_pool": 180,
                "selected_context": 468,
                "stage_a_new_sense": 44,
                "stage_a_batch": 9,
            },
        )

    def test_pool_lanes_strata_and_new_risks_match_frozen_quotas(self) -> None:
        self.assertEqual(
            Counter(row["lane"] for row in self.pool),
            {
                "A_OFFICIAL": 5,
                "B_REVIEW_READY": 6,
                "C_REPAIRED": 5,
                "D_NEW": 44,
            },
        )
        self.assertEqual(
            Counter(row["stratum"] for row in self.pool),
            {"clear": 18, "ambiguous": 23, "collision_or_multi_target": 19},
        )
        self.assertEqual(
            Counter(
                row["risk_class"] for row in self.pool if row["lane"] == "D_NEW"
            ),
            {"R0_CLEAR": 13, "R3_AMBIGUOUS": 15, "R4_SPLIT_OR_POS_RISK": 16},
        )

    def test_every_sense_has_three_distinct_candidate_instances(self) -> None:
        grouped = defaultdict(list)
        for row in self.candidates:
            grouped[row["sense_id"]].append(row)
        self.assertEqual(set(grouped), {row["sense_id"] for row in self.pool})
        for sense_id, rows in grouped.items():
            self.assertEqual(len(rows), 3, sense_id)
            normalized = {
                row["candidate_target_vi"].strip().casefold() for row in rows
            }
            self.assertEqual(len(normalized), 3, sense_id)

    def test_positive_contexts_are_real_d2l_evidence(self) -> None:
        new_sense_ids = {
            row["sense_id"] for row in self.pool if row["lane"] == "D_NEW"
        }
        positive_by_sense = Counter()
        for row in self.contexts:
            if row["positive_evidence_eligible"]:
                self.assertFalse(row["synthetic"])
                self.assertEqual(row["source_artifact_sha256"], SOURCE_DOCUMENT_SHA256)
                if "PRIMARY" in row["evidence_roles"]:
                    positive_by_sense[row["pool_sense_id"]] += 1
            if row["synthetic"]:
                self.assertTrue(row["boundary_only"])
                self.assertFalse(row["positive_evidence_eligible"])
        for sense_id in new_sense_ids:
            self.assertEqual(positive_by_sense[sense_id], 5, sense_id)

    def test_nine_json_batches_cover_new_senses_once(self) -> None:
        self.assertEqual([row["sense_count"] for row in self.batch_index], [5] * 8 + [4])
        covered = []
        workload = Counter()
        for row in self.batch_index:
            manifest = strict_json_object(
                self.artifact_root / "batches" / row["batch_id"] / "batch_manifest.json"
            )
            covered.extend(manifest["sense_ids"])
            workload["reviewer_1"] += manifest["reviewer_1_case_count"]
            workload["reviewer_2"] += manifest["reviewer_2_case_count"]
            workload["mandatory"] += manifest["mandatory_adjudication_count"]
            workload["conditional"] += manifest["conditional_adjudication_count"]
            workload["blind"] += manifest["blind_audit_count"]
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(len(covered), 44)
        self.assertEqual(
            workload,
            {
                "reviewer_1": 44,
                "reviewer_2": 31,
                "mandatory": 16,
                "conditional": 15,
                "blind": 13,
            },
        )

    def test_reviewer_inputs_are_blank_blind_and_role_scoped(self) -> None:
        forbidden = {
            "intended_candidate_role",
            "final_gold_label",
            "stage_b_gold_label",
            "final_glossary_decision",
            "c_score",
            "e_evidence",
            "global_decision",
        }
        reviewer_counts = Counter()
        for index_row in self.batch_index:
            batch_id = index_row["batch_id"]
            for slot in ("reviewer_1", "reviewer_2"):
                payload = strict_json_object(
                    self.artifact_root / "batches" / batch_id / f"{slot}_input.json"
                )
                reviewer_counts[slot] += len(payload["cases"])
                for case in payload["cases"]:
                    self.assertFalse(forbidden & set(_walk_keys(case["source_payload"])))
                    for value in case["review"].values():
                        self.assertIn(value, ("", []))
                    risk = case["source_payload"]["risk_class"]
                    if slot == "reviewer_2":
                        self.assertIn(risk, {"R3_AMBIGUOUS", "R4_SPLIT_OR_POS_RISK"})
        self.assertEqual(reviewer_counts, {"reviewer_1": 44, "reviewer_2": 31})

    def test_batch_one_is_immediately_sendable(self) -> None:
        batch = self.artifact_root / "batches" / "batch_001"
        reviewer_1 = strict_json_object(batch / "reviewer_1_input.json")
        reviewer_2 = strict_json_object(batch / "reviewer_2_input.json")
        reviewer_1_terms = [
            case["source_payload"]["source_term"] for case in reviewer_1["cases"]
        ]
        reviewer_2_terms = [
            case["source_payload"]["source_term"] for case in reviewer_2["cases"]
        ]
        self.assertEqual(len(reviewer_1_terms), 5)
        self.assertEqual(len(reviewer_2_terms), 3)
        self.assertTrue(Path(self.result["batch_1_reviewer_1_zip"]).is_file())
        self.assertTrue(Path(self.result["batch_1_reviewer_2_zip"]).is_file())

    def test_source_document_drift_rejects_without_output(self) -> None:
        mutated = self.temp_root / "mutated_document.json"
        mutated.write_bytes(SOURCE_DOCUMENT.read_bytes() + b"\n")
        output = self.temp_root / "drift_output"
        with self.assertRaisesRegex(ValueError, "source document hash mismatch"):
            _build(output, mutated)
        self.assertFalse(output.exists())

    def test_release_is_deterministic(self) -> None:
        second_root = self.temp_root / "second" / "artifact"
        second_root.parent.mkdir()
        second = _build(second_root)
        self.assertEqual(
            sha256_file(self.artifact_root / "manifest.json"),
            sha256_file(second_root / "manifest.json"),
        )
        self.assertEqual(self.result["release_zip_sha256"], second["release_zip_sha256"])

    def test_packaged_reviewer_source_tamper_is_detected(self) -> None:
        tampered = self.temp_root / "tampered"
        shutil.copytree(self.artifact_root, tampered)
        path = tampered / "batches" / "batch_001" / "reviewer_1_input.json"
        payload = _json(path)
        payload["cases"][0]["source_payload"]["source_term"] += " tampered"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        errors = validate_artifact(tampered)
        self.assertTrue(
            any("reviewer source payload hash mismatch" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
