from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


NAMESPACE = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(NAMESPACE))

from tools.candidates import normalize_candidates
from tools.common import canonical_json_bytes, seal_record, sha256_bytes, verify_record
from tools.glossary import GlossaryEntry, match_glossary, normalize_text, parse_glossary
from tools.grounding import active_positive_ids, classify_risk, real_positive_context


class GlossaryTests(unittest.TestCase):
    def test_parse_and_exact_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "glossary.md"
            path.write_text(
                "| English | Tiếng Việt | Thảo luận tại |\n"
                "|---|---|---|\n"
                "| model | mô hình | |\n",
                encoding="utf-8",
            )
            entries = parse_glossary(path)
            result = match_glossary("Model", entries)
        self.assertEqual(result["glossary_match_status"], "GLOSSARY_EXACT")
        self.assertEqual(result["glossary_candidate_vi"], "mô hình")

    def test_qualified_and_variant_match(self) -> None:
        entries = [GlossaryEntry("argument (in programming)", "đối số", "", 10, "in programming")]
        self.assertEqual(match_glossary("argument", entries)["glossary_match_status"], "GLOSSARY_QUALIFIED")
        plural = [GlossaryEntry("activation function", "hàm kích hoạt", "", 11, None)]
        self.assertEqual(match_glossary("activation functions", plural)["glossary_match_status"], "GLOSSARY_VARIANT")

    def test_ambiguous_match(self) -> None:
        entries = [
            GlossaryEntry("model (statistics)", "mô hình", "", 1, "statistics"),
            GlossaryEntry("model (person)", "người mẫu", "", 2, "person"),
        ]
        self.assertEqual(match_glossary("model", entries)["glossary_match_status"], "AMBIGUOUS_MULTI_SENSE")


class GroundingTests(unittest.TestCase):
    def test_positive_context_filter_and_quarantine(self) -> None:
        context = {
            "context_id": "ctx_1",
            "sense_relation": "SAME_SENSE",
            "context_role": "PRIMARY",
            "source_text": "model",
            "provenance": {"block_id": "block_1"},
        }
        self.assertTrue(real_positive_context(context))
        sense = {"primary_context_ids": ["ctx_1"], "backup_context_ids": []}
        self.assertEqual(active_positive_ids(sense, {"ctx_1": context}, set()), ["ctx_1"])
        self.assertEqual(active_positive_ids(sense, {"ctx_1": context}, {"block_1"}), [])

    def test_risk_precedence(self) -> None:
        sense = {"source_term": "in place", "stratum": "clear"}
        risk, _ = classify_risk(sense, {"glossary_match_status": "GLOSSARY_EXACT"}, 5)
        self.assertEqual(risk, "R4_SPLIT_OR_POS_RISK")
        sense = {"source_term": "ordinary term", "stratum": "clear"}
        risk, _ = classify_risk(sense, {"glossary_match_status": "GLOSSARY_MISSING"}, 5)
        self.assertEqual(risk, "R2_MISSING")


class CandidateTests(unittest.TestCase):
    def test_glossary_match_is_role_a_and_labels_remain_blank(self) -> None:
        candidates = []
        slots = []
        for number, (candidate_id, value, method) in enumerate(
            [
                ("c1", "biểu diễn", "RECORDED_PIPELINE_OUTPUT"),
                ("c2", "mô hình", "MODEL_GENERATED_SUPPORT_SET_V2"),
                ("c3", "người mẫu", "MODEL_GENERATED_SUPPORT_SET_V2"),
            ],
            start=1,
        ):
            candidates.append(
                {
                    "candidate_instance_id": candidate_id,
                    "candidate_instance_sha256": "a" * 64,
                    "candidate_target_vi": value,
                    "created_at": "2026-01-01T00:00:00Z",
                    "formation_method": method,
                    "formation_provenance": [],
                    "sense_id": "sense_1",
                    "term_id": "term_1",
                }
            )
            slots.append(
                {
                    "candidate_instance_id": candidate_id,
                    "candidate_slot_sha256": "b" * 64,
                    "slot_number": number,
                }
            )
        output = normalize_candidates(candidates, slots, {"sense_1": {"glossary_candidate_vi": "mô hình"}})
        role_a = next(row for row in output if row["candidate_role"] == "A")
        self.assertEqual(role_a["candidate_id"], "c2")
        self.assertIsNone(role_a["candidate_gold_label"])


class IntegrityTests(unittest.TestCase):
    def test_record_self_hash(self) -> None:
        record = seal_record({"schema_id": "Example", "value": "đúng"})
        self.assertTrue(verify_record(record))
        record["value"] = "sai"
        self.assertFalse(verify_record(record))

    def test_canonical_json_is_stable(self) -> None:
        left = canonical_json_bytes({"b": 2, "a": 1})
        right = canonical_json_bytes({"a": 1, "b": 2})
        self.assertEqual(left, right)
        self.assertEqual(sha256_bytes(left), sha256_bytes(right))


if __name__ == "__main__":
    unittest.main()
