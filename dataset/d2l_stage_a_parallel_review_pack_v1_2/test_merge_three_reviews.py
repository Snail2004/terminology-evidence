import unittest

from merge_three_reviews import resolve_decisions


def decision(definition, *, status="ACCEPTED", pos="noun", pos_status="ACCEPTED", note=""):
    return {
        "definition_status": status,
        "effective_definition_en": definition,
        "part_of_speech_status": pos_status,
        "effective_part_of_speech": pos,
        "scope_note": note,
    }


class MergePolicyTests(unittest.TestCase):
    def test_scope_note_wording_does_not_block_core_unanimity(self):
        decisions = [
            decision("same", note="A boundary."),
            decision("same", note="B boundary."),
            decision("same", note="C boundary."),
        ]
        resolution, effective, variants, winning_variants = resolve_decisions(decisions)
        self.assertEqual(resolution, "AGREEMENT_3_OF_3")
        self.assertEqual(effective["effective_definition_en"], "same")
        self.assertEqual(effective["scope_note_resolution"], "NON_BLOCKING_TEXT_VARIANTS")
        self.assertEqual(variants, ["A boundary.", "B boundary.", "C boundary."])
        self.assertEqual(winning_variants, variants)

    def test_core_majority_remains_majority(self):
        decisions = [
            decision("same", note="A"),
            decision("same", note="B"),
            decision("different", note="0 minority note"),
        ]
        resolution, effective, variants, winning_variants = resolve_decisions(decisions)
        self.assertEqual(resolution, "MAJORITY_2_OF_3")
        self.assertEqual(effective["effective_definition_en"], "same")
        self.assertEqual(effective["scope_note"], "A")
        self.assertEqual(variants, ["0 minority note", "A", "B"])
        self.assertEqual(winning_variants, ["A", "B"])

    def test_distinct_core_decisions_still_require_adjudication(self):
        decisions = [
            decision("one", note="A"),
            decision("two", note="B"),
            decision("three", note="C"),
        ]
        resolution, effective, _, winning_variants = resolve_decisions(decisions)
        self.assertEqual(resolution, "ADJUDICATION_REQUIRED")
        self.assertIsNone(effective)
        self.assertEqual(winning_variants, ["A"])


if __name__ == "__main__":
    unittest.main()
