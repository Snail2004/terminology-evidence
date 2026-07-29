from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


class CliReleaseTests(unittest.TestCase):
    def test_cli_help_exposes_v1_commands(self) -> None:
        completed = subprocess.run([sys.executable, "-m", "integration_harness", "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0)
        for command in ("authority-verify", "inventory", "validate-packages", "join", "run", "replay", "verify-run", "inject-fault", "build-release"):
            self.assertIn(command, completed.stdout)

    def test_source_has_no_cache_or_pycs_in_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            output = Path(directory) / "release"
            completed = subprocess.run([sys.executable, "-m", "integration_harness", "build-release", "--repository-root", str(root), "--output-dir", str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            archive = output / "system_integration_harness_v1_rc1.zip"
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
            self.assertTrue(names)
            self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))
