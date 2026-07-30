from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    canonical_json_bytes,
    sha256_bytes,
    write_json,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.spec import (
    REVIEW_FIELDS,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.followup_handoffs import (
    blank_proposal_audit,
    blank_standard_review,
    build_high_risk_audit_handoffs,
    build_reaudit_handoffs,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.followup_validation import (
    ReviewFileSpec,
    apply_resolution,
    capture_review_files,
    sanitize_for_blind_review,
    source_payload_sha256,
    validate_blind_result,
    validate_high_risk_repair,
    validate_r0_repair,
)


def source_payload(sense_id: str = "sense_1") -> dict[str, object]:
    return {
        "candidates": [
            {
                "candidate_id": f"candidate_{index}",
                "candidate_instance_sha256": str(index) * 64,
                "candidate_slot": f"slot_{index}",
                "candidate_target_vi": f"target {index}",
            }
            for index in range(1, 4)
        ],
        "dataset_version": "test",
        "evidence_contexts": [
            {
                "context_id": "ctx_1",
                "source_text": "first context",
                "synthetic": False,
            },
            {
                "context_id": "ctx_2",
                "positive_evidence_eligible": False,
                "source_text": "synthetic boundary",
                "synthetic": True,
            },
        ],
        "parent_binding": {"manifest_sha256": "a" * 64},
        "policy_id": "test",
        "proposed_definition_en": "definition",
        "proposed_part_of_speech": "noun",
        "proposed_scope": "scope",
        "provider_call_count": 0,
        "review_requirement": "SOURCE_GROUND_PLUS_BLIND_AUDIT",
        "risk_class": "R0_CLEAR",
        "schema_id": "TestSource",
        "schema_version": "1.0",
        "sense_id": sense_id,
        "source_review_status": "REVISION_REQUIRED",
        "source_term": "term",
        "stratum": "clear",
        "term_id": sense_id,
    }


def blank_r0_repair() -> dict[str, object]:
    return {
        "candidate_replacements": [],
        "corrected_definition_en": "",
        "corrected_part_of_speech": "",
        "corrected_scope": "",
        "invalid_evidence_context_ids": [],
        "proposed_split_labels": [],
        "repair_rationale": "",
        "repair_status": "",
    }


def blank_high_risk_repair() -> dict[str, object]:
    return {
        "candidate_replacements": [],
        "child_sense_repairs": [],
        "corrected_definition_en": "",
        "corrected_part_of_speech": "",
        "corrected_scope": "",
        "invalid_evidence_context_ids": [],
        "repair_rationale": "",
        "repair_status": "",
        "resolution_status": "",
    }


def r0_payload(batch_id: str = "repair_batch_001") -> dict[str, object]:
    source = source_payload()
    return {
        "batch_id": batch_id,
        "case_count": 1,
        "cases": [
            {
                "batch_id": batch_id,
                "case_id": "case_1",
                "repair": blank_r0_repair(),
                "required_repairs": ["candidate_replacements"],
                "sense_id": "sense_1",
                "source_payload": source,
                "source_payload_sha256": source_payload_sha256(source),
            }
        ],
        "policy_id": "test",
        "status": "test",
    }


def high_risk_payload(batch_id: str = "highrisk_batch_001") -> dict[str, object]:
    source = source_payload()
    return {
        "batch_id": batch_id,
        "case_count": 1,
        "cases": [
            {
                "batch_id": batch_id,
                "case_id": "case_1",
                "repair": blank_high_risk_repair(),
                "repair_mode": "SPLIT_REQUIRED",
                "required_repairs": ["split"],
                "sense_id": "sense_1",
                "source_payload": source,
                "source_payload_sha256": source_payload_sha256(source),
                "split_targets": [
                    {"temporary_child_sense_id": "child_1"},
                    {"temporary_child_sense_id": "child_2"},
                ],
            }
        ],
        "policy_id": "test",
        "status": "test",
    }


def blind_payload(batch_id: str = "blind_batch_001") -> dict[str, object]:
    source = source_payload()
    return {
        "batch_id": batch_id,
        "case_count": 1,
        "cases": [
            {
                "batch_id": batch_id,
                "case_id": "case_1",
                "review": blank_standard_review(),
                "reviewer_slot": "r0_blind_reviewer",
                "sense_id": "sense_1",
                "source_payload": source,
                "source_payload_sha256": source_payload_sha256(source),
            }
        ],
        "reviewer_slot": "r0_blind_reviewer",
        "status": "test",
    }


class FollowupValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="followup-intake-test-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_pair(
        self, name: str, source: dict[str, object], response: dict[str, object]
    ) -> tuple[Path, Path]:
        input_path = self.root / f"{name}_input.json"
        response_path = self.root / f"{name}_response.json"
        write_json(input_path, source)
        write_json(response_path, response)
        return input_path, response_path

    def test_r0_repair_accepts_bound_candidate_change(self) -> None:
        source = r0_payload()
        response = copy.deepcopy(source)
        repair = response["cases"][0]["repair"]
        repair.update(
            {
                "candidate_replacements": [
                    {
                        "candidate_id": "candidate_1",
                        "candidate_slot": "slot_1",
                        "replacement_target_vi": "new target",
                    }
                ],
                "repair_rationale": "Evidence-bound candidate repair.",
                "repair_status": "COMPLETE",
            }
        )
        input_path, response_path = self._write_pair("r0", source, response)
        self.assertEqual(validate_r0_repair(input_path, response_path), [])

    def test_r0_repair_rejects_immutable_source_change(self) -> None:
        source = r0_payload()
        response = copy.deepcopy(source)
        response["cases"][0]["source_payload"]["source_term"] = "changed"
        input_path, response_path = self._write_pair("r0_tamper", source, response)
        errors = validate_r0_repair(input_path, response_path)
        self.assertTrue(any("immutable field changed" in error for error in errors))

    def test_high_risk_split_requires_exact_partition(self) -> None:
        source = high_risk_payload()
        response = copy.deepcopy(source)
        repair = response["cases"][0]["repair"]
        repair.update(
            {
                "child_sense_repairs": [
                    {
                        "candidate_assignments": [
                            {
                                "candidate_id": "candidate_1",
                                "candidate_slot": "slot_1",
                                "target_vi": "target 1",
                            }
                        ],
                        "context_ids": ["ctx_1"],
                        "definition_en": "first",
                        "part_of_speech": "noun",
                        "scope": "scope",
                        "temporary_child_sense_id": "child_1",
                    },
                    {
                        "candidate_assignments": [
                            {
                                "candidate_id": "candidate_2",
                                "candidate_slot": "slot_2",
                                "target_vi": "target 2",
                            },
                            {
                                "candidate_id": "candidate_3",
                                "candidate_slot": "slot_3",
                                "target_vi": "target 3",
                            },
                        ],
                        "context_ids": ["ctx_2"],
                        "definition_en": "second",
                        "part_of_speech": "noun",
                        "scope": "scope",
                        "temporary_child_sense_id": "child_2",
                    },
                ],
                "repair_rationale": "Exact partition.",
                "repair_status": "COMPLETE",
                "resolution_status": "SPLIT_PROPOSED",
            }
        )
        input_path, response_path = self._write_pair("high", source, response)
        self.assertEqual(validate_high_risk_repair(input_path, response_path), [])
        response["cases"][0]["repair"]["child_sense_repairs"][1][
            "context_ids"
        ] = ["ctx_1", "ctx_2"]
        write_json(response_path, response)
        errors = validate_high_risk_repair(input_path, response_path)
        self.assertTrue(any("contexts must be assigned exactly once" in e for e in errors))

    def test_blind_result_accepts_complete_standard_review(self) -> None:
        source = blind_payload()
        response = copy.deepcopy(source)
        review = response["cases"][0]["review"]
        for field in REVIEW_FIELDS:
            if field.endswith("_decision"):
                review[field] = "ACCEPT"
        review["sense_status"] = "READY_FOR_CONTRACT_CONSTRUCTION"
        review["review_notes"] = "All supplied eligible evidence supports the sense."
        review["review_status"] = "COMPLETE"
        input_path, response_path = self._write_pair("blind", source, response)
        self.assertEqual(validate_blind_result(input_path, response_path), [])

    def test_capture_rejects_source_drift_before_output_is_accepted(self) -> None:
        source = r0_payload()
        response = copy.deepcopy(source)
        repair = response["cases"][0]["repair"]
        repair.update(
            {
                "candidate_replacements": [
                    {
                        "candidate_id": "candidate_1",
                        "candidate_slot": "slot_1",
                        "replacement_target_vi": "new target",
                    }
                ],
                "repair_rationale": "Evidence-bound candidate repair.",
                "repair_status": "COMPLETE",
            }
        )
        input_path, response_path = self._write_pair("capture", source, response)
        spec = ReviewFileSpec(
            kind="r0_repair",
            reviewer_role="reviewer_1",
            batch_id="repair_batch_001",
            input_path=input_path,
            response_path=response_path,
        )

        def mutate() -> None:
            response_path.write_text("{}\n", encoding="utf-8")

        capture_root = self.root / "captures"
        with self.assertRaisesRegex(ValueError, "source review drift"):
            capture_review_files([spec], capture_root, after_inventory=mutate)

    def test_apply_resolution_is_id_bound_and_removes_invalid_context(self) -> None:
        source = source_payload()
        effective, operations = apply_resolution(
            source,
            {
                "candidate_replacements": [
                    {
                        "candidate_id": "candidate_1",
                        "candidate_slot": "slot_1",
                        "replacement_target_vi": "replacement",
                    }
                ],
                "corrected_definition_en": "corrected definition",
                "corrected_part_of_speech": "",
                "corrected_scope": "",
                "invalid_evidence_context_ids": ["ctx_1"],
            },
        )
        self.assertEqual(effective["proposed_definition_en"], "corrected definition")
        self.assertEqual(effective["candidates"][0]["candidate_target_vi"], "replacement")
        self.assertEqual(
            [row["context_id"] for row in effective["evidence_contexts"]], ["ctx_2"]
        )
        self.assertEqual(len(operations), 3)
        self.assertEqual(source["proposed_definition_en"], "definition")

    def test_blind_sanitizer_removes_routing_fields(self) -> None:
        sanitized = sanitize_for_blind_review(source_payload())
        self.assertNotIn("risk_class", sanitized)
        self.assertNotIn("review_requirement", sanitized)
        self.assertNotIn("source_review_status", sanitized)
        self.assertIn("parent_binding", sanitized)

    def test_handoffs_are_blank_and_deterministic(self) -> None:
        source = sanitize_for_blind_review(source_payload())
        source_sha = sha256_bytes(canonical_json_bytes(source))
        repair_records = [
            {
                "blind_source_payload": source,
                "blind_source_payload_sha256": source_sha,
                "reaudit_case_id": f"reaudit_{index}",
                "record_sha256": str(index) * 64,
                "sense_id": f"sense_{index}",
            }
            for index in range(1, 13)
        ]
        high_risk_records = [
            {
                "audit_case_id": f"audit_{index}",
                "blind_source_payload": source,
                "blind_source_payload_sha256": source_sha,
                "proposal": {"proposal_type": "REPAIRED_SOURCE"},
                "record_sha256": str(index) * 64,
                "sense_id": f"high_{index}",
                "source_term": f"term {index}",
            }
            for index in range(1, 11)
        ]
        handoff_root = self.root / "handoff"
        handoff_root.mkdir()
        reaudit = build_reaudit_handoffs(repair_records, handoff_root)
        high_risk = build_high_risk_audit_handoffs(high_risk_records, handoff_root)
        self.assertEqual([row["case_count"] for row in reaudit], [5, 5, 2])
        self.assertEqual([row["case_count"] for row in high_risk], [4, 4, 2])
        reaudit_input = json.loads(
            (self.root / "review_batches/followup_reaudit_batch_001/reviewer_input.json")
            .read_text(encoding="utf-8")
        )
        audit_input = json.loads(
            (self.root / "review_batches/high_risk_audit_batch_001/auditor_input.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(reaudit_input["cases"][0]["review"], blank_standard_review())
        self.assertEqual(audit_input["cases"][0]["audit"], blank_proposal_audit())


if __name__ == "__main__":
    unittest.main()
