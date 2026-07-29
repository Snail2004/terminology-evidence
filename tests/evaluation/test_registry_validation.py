import json
import tempfile
import unittest
from pathlib import Path

from evaluation.v1.jsonio import StrictJSONError, loads_strict
from evaluation.v1.registries.loader import RegistryError, load_registries, registry_counts, registry_root


class RegistryValidationTests(unittest.TestCase):
    def test_frozen_registries_load_and_counts(self):
        registries = load_registries()
        self.assertEqual(registry_counts(registries), {"research_questions": 8, "metrics": 16, "experiments": 10, "ablations": 6})

    def test_duplicate_and_nonfinite_json_rejected(self):
        with self.assertRaises(StrictJSONError):
            loads_strict('{"a": 1, "a": 2}')
        with self.assertRaises(StrictJSONError):
            loads_strict('{"a": NaN}')
        with self.assertRaises(StrictJSONError):
            loads_strict('[1, 2]')

    def test_metric_primary_order_is_frozen(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in registry_root().glob("*.json"):
                (root / path.name).write_bytes(path.read_bytes())
            path = root / "metric_registry_v1.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["primary_metrics"] = list(reversed(value["primary_metrics"]))
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(RegistryError):
                load_registries(root)
