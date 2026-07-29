import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.fixtures.synthetic import build_synthetic_rows, write_synthetic_release
from evaluation.v1.jsonio import write_json
from evaluation.v1.reports.builder import build_evaluation_report


class ReportAndCliTests(unittest.TestCase):
    def test_report_is_reproducible(self):
        with TemporaryDirectory() as temp:
            first = Path(temp) / "one"
            second = Path(temp) / "two"
            report_one = build_evaluation_report(build_synthetic_rows(), first, split="development", bootstrap_seed=17, bootstrap_replicates=20)
            report_two = build_evaluation_report(build_synthetic_rows(), second, split="development", bootstrap_seed=17, bootstrap_replicates=20)
            self.assertEqual(report_one["semantic_sha256"], report_two["semantic_sha256"])
            self.assertEqual((first / "primary_metrics.json").read_bytes(), (second / "primary_metrics.json").read_bytes())
            self.assertTrue((first / "candidate_results.csv").is_file())

    def test_cli_synthetic_and_evaluate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture"
            output = root / "report"
            write_synthetic_release(fixture)
            command = [sys.executable, "-B", "-m", "evaluation.v1.cli", "evaluate", str(fixture / "rows.json"), str(output), "--replicates", "10"]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / "evaluation_report.json").is_file())
