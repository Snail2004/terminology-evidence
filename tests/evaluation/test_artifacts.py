import unittest

from evaluation.v1.artifacts.eligibility import EligibilityError, apply_exclusions
from evaluation.v1.artifacts.join import JoinError, exact_join, validate_split_leakage
from evaluation.v1.fixtures.synthetic import build_synthetic_rows


def _key(index):
    return {"source_term": "term", "sense_id": f"sense_{index}", "scope_id": "global", "candidate_vi": f"vi_{index}"}


class ArtifactTests(unittest.TestCase):
    def test_exact_join_rejects_duplicate_gold_and_extras(self):
        base = [{"candidate_key": _key(1), "split": "development"}]
        gold = [{"candidate_key": _key(1), "gold_label": "ACCEPT"}, {"candidate_key": _key(1), "gold_label": "ACCEPT"}]
        with self.assertRaises(JoinError):
            exact_join(base, gold_rows=gold)
        with self.assertRaises(JoinError):
            exact_join(base, gold_rows=[{"candidate_key": _key(2), "gold_label": "ACCEPT"}])

    def test_split_leakage_rejected(self):
        rows = [{"candidate_key": _key(1), "split": "development", "source_block_cluster": "cluster"}, {"candidate_key": _key(1), "split": "test", "source_block_cluster": "cluster"}]
        with self.assertRaises(JoinError):
            validate_split_leakage(rows)

    def test_valid_join_and_exclusions(self):
        base = [{"candidate_key": _key(1), "split": "development"}]
        joined = exact_join(base, gold_rows=[{"candidate_key": _key(1), "gold_label": "ACCEPT"}])
        self.assertEqual(joined[0]["gold"]["gold_label"], "ACCEPT")
        eligible, excluded = apply_exclusions(joined, [{"candidate_key": _key(1), "reason": "HUMAN_UNJUDGEABLE", "artifact_ref": "a", "timestamp": "t", "reviewer_approval": "r"}])
        self.assertEqual(eligible, [])
        self.assertEqual(len(excluded), 1)

    def test_forbidden_exclusion_rejected(self):
        rows = build_synthetic_rows()[:1]
        with self.assertRaises(EligibilityError):
            apply_exclusions(rows, [{"candidate_key": rows[0]["candidate_key"], "reason": "LOW_SCORE", "artifact_ref": "a", "timestamp": "t", "reviewer_approval": "r"}])
