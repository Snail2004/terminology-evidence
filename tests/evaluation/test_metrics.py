import unittest

from evaluation.v1.fixtures.synthetic import build_synthetic_rows
from evaluation.v1.metrics.bootstrap import decision_flip_rate, grouped_bootstrap
from evaluation.v1.metrics.core import summarize_global
from evaluation.v1.metrics.intervals import wilson_interval
from evaluation.v1.metrics.paired import mcnemar_exact


class MetricTests(unittest.TestCase):
    def test_wilson_known_boundaries(self):
        self.assertEqual(wilson_interval(0, 0), (0.0, 0.0))
        low, high = wilson_interval(5, 10)
        self.assertAlmostEqual(low, 0.236593090512564, places=12)
        self.assertAlmostEqual(high, 0.763406909487436, places=12)

    def test_global_primary_metrics(self):
        rows = build_synthetic_rows()
        summary = summarize_global(rows)
        self.assertEqual(summary["eligible_n"], 9)
        self.assertEqual(summary["false_approval_count"], 1)
        self.assertEqual(summary["auto_approved_precision"]["total"], 3)

    def test_grouped_bootstrap_is_seed_deterministic(self):
        rows = build_synthetic_rows()
        stat = lambda sample: summarize_global(sample)["auto_approved_precision"]["estimate"]
        first = grouped_bootstrap(rows, stat, seed=7, replicates=30)
        second = grouped_bootstrap(rows, stat, seed=7, replicates=30)
        self.assertEqual(first, second)
        self.assertEqual(first["group_count"], 5)

    def test_flip_rate_and_mcnemar(self):
        self.assertAlmostEqual(decision_flip_rate([0.2, 0.9, 0.8], 0.5), 1 / 3)
        result = mcnemar_exact([
            {"left": True, "right": False},
            {"left": False, "right": True},
            {"left": True, "right": True},
        ])
        self.assertEqual(result["discordant_left_only"], 1)
        self.assertEqual(result["discordant_right_only"], 1)
        self.assertEqual(result["p_value"], 1.0)
