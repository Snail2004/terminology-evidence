from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from integration_harness.errors import IntegrityError
from integration_harness.jsonio import loads_strict
from integration_harness.paths import safe_relative_path


class StrictIntegrityTests(unittest.TestCase):
    def test_duplicate_keys_at_nested_depth_are_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            loads_strict('{"outer":{"x":1,"x":2}}', require_object=True)

    def test_nonfinite_and_trailing_data_are_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            loads_strict('{"x":NaN}', require_object=True)
        with self.assertRaises(IntegrityError):
            loads_strict('{"x":1} trailing', require_object=True)
        with self.assertRaises(IntegrityError):
            loads_strict(b"\xff", require_object=True)

    def test_path_traversal_and_backslash_are_rejected(self) -> None:
        for value in ("../escape", "a/../../escape", "C:/escape", "/absolute", "a\\b", "a/./b"):
            with self.subTest(value=value), self.assertRaises(IntegrityError):
                safe_relative_path(value)
