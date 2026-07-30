from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.build_r0_reaudit_result import build_r0_reaudit_result
from tools.r0_result import load_canonical_input, validate_completed_r0_result
from tools.validate_r0_reaudit_result import validate_artifact, validate_zip


class R0ReauditResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.namespace = Path(__file__).resolve().parents[1]
        cls.repair_zip = (
            cls.namespace
            / "release"
            / "d2l_fast_track_stage_a_r0_repair_reaudit_v1_release.zip"
        )
        cls.temporary = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temporary.name)
        extracted = cls.work / "repair"
        extracted.mkdir()
        with zipfile.ZipFile(cls.repair_zip) as archive:
            archive.extractall(extracted)
        cls.canonical = load_canonical_input(extracted)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _completed(self) -> dict:
        payload = copy.deepcopy(self.canonical)
        for case in payload["cases"]:
            case["review"] = {
                "definition_decision": "ACCEPT",
                "corrected_definition_en": "",
                "part_of_speech_decision": "ACCEPT",
                "corrected_part_of_speech": "",
                "scope_decision": "ACCEPT",
                "corrected_scope": "",
                "evidence_decision": "ACCEPT",
                "invalid_evidence_context_ids": [],
                "candidate_set_decision": "ACCEPT",
                "candidate_replacements": [],
                "sense_status": "READY_FOR_CONTRACT_CONSTRUCTION",
                "proposed_split_labels": [],
                "review_notes": "The repaired source, evidence, and candidate set are accepted.",
                "review_status": "COMPLETE",
            }
        return payload

    def _write(self, name: str, payload: dict) -> Path:
        path = self.work / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_completed_four_case_result_passes(self) -> None:
        result, errors = validate_completed_r0_result(
            self.canonical, self._write("completed.json", self._completed())
        )
        self.assertEqual(errors, [])
        self.assertIsNotNone(result)
        self.assertEqual(len(result.records), 4)

    def test_source_tamper_is_rejected(self) -> None:
        payload = self._completed()
        payload["cases"][0]["source_payload"]["source_term"] = "tampered"
        result, errors = validate_completed_r0_result(
            self.canonical, self._write("tampered.json", payload)
        )
        self.assertIsNone(result)
        self.assertTrue(any("immutable case field changed" in error for error in errors))

    def test_incomplete_or_revised_result_does_not_unlock(self) -> None:
        payload = self._completed()
        payload["cases"][0]["review"]["candidate_set_decision"] = "REVISE"
        result, errors = validate_completed_r0_result(
            self.canonical, self._write("revised.json", payload)
        )
        self.assertIsNone(result)
        self.assertTrue(any("must be ACCEPT" in error for error in errors))

    def test_builder_emits_valid_sealed_artifact(self) -> None:
        completed = self._write("builder_completed.json", self._completed())
        output = self.work / "built_result"
        result = build_r0_reaudit_result(
            repair_release_zip=self.repair_zip,
            completed_review=completed,
            output_root=output,
            created_at="2026-07-29T16:00:00Z",
        )
        self.assertEqual(result["status"], "R0_REAUDIT_COMPLETE_EXACT_50_UNLOCKED")
        self.assertEqual(validate_artifact(output), [])
        self.assertEqual(validate_zip(Path(result["release_zip"]), output), [])


if __name__ == "__main__":
    unittest.main()
