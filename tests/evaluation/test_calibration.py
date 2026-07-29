import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.calibration.logistic import brier_score, choose_threshold, fit_logistic, log_loss
from evaluation.v1.calibration.feature_registry import FeatureRegistryError


class CalibrationTests(unittest.TestCase):
    def test_logistic_fit_is_deterministic_and_predicts(self):
        rows = [([0.0], 0), ([1.0], 1), ([2.0], 1)]
        model = fit_logistic(rows, feature_names=["x"], iterations=100)
        self.assertGreater(model.predict_probability([2.0]), model.predict_probability([0.0]))
        self.assertEqual(model.to_dict()["model"], "logistic_regression")

    def test_threshold_and_calibration_metrics(self):
        selected = choose_threshold([0.1, 0.8, 0.9], [0, 1, 1], precision_target=0.9)
        self.assertEqual(selected["threshold"], 0.8)
        self.assertAlmostEqual(brier_score([0.1, 0.8, 0.9], [0, 1, 1]), 0.02)
        self.assertGreater(log_loss([0.1, 0.8, 0.9], [0, 1, 1]), 0.0)

    def test_feature_registry_is_enforced(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "features.json"
            path.write_text('{"core_features":["C_mean"],"producer_context_features":[],"producer_attestation_features":[],"optional_probe_features":[]}', encoding="utf-8")
            fit_logistic([([0.1], 0), ([0.9], 1)], feature_names=["C_mean"], feature_registry_path=path)
            with self.assertRaises(FeatureRegistryError):
                fit_logistic([([0.1], 0), ([0.9], 1)], feature_names=["unknown"], feature_registry_path=path)
