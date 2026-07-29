from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

from integration_harness.assembler import GlobalCliAdapter
from integration_harness.errors import ReplayError
from integration_harness.faults import inject_fault
from integration_harness.pipeline import execute_run
from integration_harness.replay import replay_run

from .helpers import make_fixture_repo


class PipelineReplayTests(unittest.TestCase):
    def test_fifteen_candidate_run_seals_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            work = Path(directory)
            fixture = make_fixture_repo(root, work, 15)
            adapter = GlobalCliAdapter(
                repository_root=root,
                authority_receipt=fixture["authority"],
                contracts_root=fixture["contracts"],
                action_policy=fixture["action_policy"],
                command_prefix=(sys.executable, str(root / "tests" / "system_integration" / "fixtures" / "public_global_cli.py")),
            )
            run_dir = execute_run(
                manifest_path=fixture["manifest"], authority_receipt=fixture["authority"], contracts_root=fixture["contracts"],
                action_policy=fixture["action_policy"], output_dir=work / "run", run_id="integration-dev-001",
                mode="FIXTURE_CONFORMANCE", adapter=adapter,
            )
            replay = replay_run(run_dir, adapter=adapter)
            self.assertEqual(replay["candidate_count"], 15)
            self.assertEqual(replay["semantic_replay"], "PUBLIC_CLI_REPLAY_PASS")
            self.assertTrue((run_dir / "CHECKSUMS.sha256").is_file())
            self.assertEqual(len(list((run_dir / "input" / "global_inputs").glob("*.json"))), 15)

    def test_faults_fail_before_consumption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            work = Path(directory)
            fixture = make_fixture_repo(root, work, 1)
            adapter = GlobalCliAdapter(
                repository_root=root,
                authority_receipt=fixture["authority"],
                contracts_root=fixture["contracts"],
                action_policy=fixture["action_policy"],
                command_prefix=(sys.executable, str(root / "tests" / "system_integration" / "fixtures" / "public_global_cli.py")),
            )
            run_dir = execute_run(
                manifest_path=fixture["manifest"], authority_receipt=fixture["authority"], contracts_root=fixture["contracts"],
                action_policy=fixture["action_policy"], output_dir=work / "run", run_id="integration-dev-002",
                mode="FIXTURE_CONFORMANCE", adapter=adapter,
            )
            for fault in ("missing_package", "duplicate_json_key", "nan", "checksum_drift", "path_traversal"):
                with self.subTest(fault=fault):
                    mutated = work / f"fault-{fault}"
                    inject_fault(run_dir, mutated, fault)
                    with self.assertRaises(ReplayError):
                        replay_run(mutated)
