from __future__ import annotations

import unittest

from tools.build_pilot import (
    INTEGRATION_TERMS,
    SELECTION_SPECS,
    _review_requirement,
    _review_slots,
)


class SelectionContractTests(unittest.TestCase):
    def test_selection_is_five_five_five(self) -> None:
        counts = {}
        for spec in SELECTION_SPECS.values():
            counts[spec["group"]] = counts.get(spec["group"], 0) + 1
        self.assertEqual(counts, {
            "CLEAR_LOW_RISK": 5,
            "AMBIGUOUS_POLYSEMOUS": 5,
            "GATE_ADJUDICATION_RISK": 5,
        })

    def test_selection_has_required_gate_signals(self) -> None:
        tags = {tag for spec in SELECTION_SPECS.values() for tag in spec["tags"]}
        self.assertIn("WRONG_SENSE_CANDIDATE", tags)
        self.assertIn("TARGET_COLLISION", tags)
        self.assertIn("INSUFFICIENT_POSITIVE_EVIDENCE", tags)
        self.assertIn("E_UNJUDGEABLE_SCENARIO", tags)
        self.assertIn("MANDATORY_ADJUDICATION", tags)

    def test_all_selected_terms_are_development_policy_inputs(self) -> None:
        self.assertEqual(len(SELECTION_SPECS), 15)
        self.assertEqual(len(set(SELECTION_SPECS)), 15)


class ReviewContractTests(unittest.TestCase):
    def test_risk_review_slots(self) -> None:
        self.assertEqual(len(_review_slots("R0_CLEAR", ["BLIND_AUDIT"])), 1)
        self.assertEqual(len(_review_slots("R1_QUALIFIED", [])), 1)
        self.assertEqual(len(_review_slots("R2_MISSING", [])), 1)
        self.assertEqual(len(_review_slots("R3_AMBIGUOUS", [])), 2)
        self.assertEqual(len(_review_slots("R4_SPLIT_OR_POS_RISK", [])), 3)
        self.assertEqual(len(_review_slots("R3_AMBIGUOUS", ["E_UNJUDGEABLE_SCENARIO"])), 3)

    def test_review_requirements_are_explicit(self) -> None:
        self.assertEqual(_review_requirement("R0_CLEAR"), "SOURCE_GROUND_PLUS_BLIND_AUDIT")
        self.assertEqual(_review_requirement("R3_AMBIGUOUS"), "TWO_DISTINCT_BLIND_HUMAN_REVIEWERS")
        self.assertIn("ADJUDICATION", _review_requirement("R4_SPLIT_OR_POS_RISK"))

    def test_integration_subset_has_two_clear_two_ambiguous_one_gate(self) -> None:
        self.assertEqual(INTEGRATION_TERMS, ["momentum", "underflow", "Adam", "word embedding", "in place"])
        groups = [SELECTION_SPECS[term]["group"] for term in INTEGRATION_TERMS]
        self.assertEqual(groups.count("CLEAR_LOW_RISK"), 2)
        self.assertEqual(groups.count("AMBIGUOUS_POLYSEMOUS"), 2)
        self.assertEqual(groups.count("GATE_ADJUDICATION_RISK"), 1)


if __name__ == "__main__":
    unittest.main()
