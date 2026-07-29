from __future__ import annotations

import tempfile
import unittest
import sys
import shutil
from pathlib import Path

from integration_harness.assembler import GlobalCliAdapter
from integration_harness.authority import (
    CONTRACTS_R1_HISTORICAL_REPLAY,
    CONTRACTS_R2_CURRENT,
    R1_RECEIPT_PHYSICAL_SHA256,
    R1_RECEIPT_SELF_SHA256,
)
from integration_harness.errors import ReplayError
from integration_harness.faults import inject_fault
from integration_harness.hashing import sha256_file
from integration_harness.jsonio import dump_json, load_json
from integration_harness.pipeline import execute_run
from integration_harness.replay import replay_run

from .helpers import make_fixture_repo, reseal_test_run


class PipelineReplayTests(unittest.TestCase):
    def _global_adapter(self, root: Path, fixture: dict[str, Path]) -> GlobalCliAdapter:
        return GlobalCliAdapter(
            repository_root=root,
            authority_receipt=fixture["authority"],
            contracts_root=fixture["contracts"],
            action_policy=fixture["action_policy"],
            command_prefix=(
                sys.executable,
                "-B",
                str(root / "tests" / "system_integration" / "fixtures" / "public_global_cli.py"),
            ),
        )

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
                command_prefix=(sys.executable, "-B", str(root / "tests" / "system_integration" / "fixtures" / "public_global_cli.py")),
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

    def test_exact_r2_run_seals_ar1_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            work = Path(directory)
            fixture = make_fixture_repo(root, work / "fixture", 1)
            adapter = self._global_adapter(root, fixture)
            adapter.authority_receipt = fixture["r2_receipt"]
            run_dir = execute_run(
                manifest_path=fixture["manifest"],
                authority_receipt=fixture["r2_receipt"],
                contracts_root=fixture["contracts"],
                action_policy=fixture["action_policy"],
                action_policy_authority=fixture["action_policy_authority"],
                approval_root=fixture["approval_root"],
                authority_mode=CONTRACTS_R2_CURRENT,
                output_dir=work / "r2-run",
                run_id="integration-r2-001",
                mode="REAL_DEVELOPMENT_ZERO_NETWORK",
                adapter=adapter,
                repository_root=root,
            )
            self.assertTrue((run_dir / "input" / "authority" / "approval" / "approval_binding_v1.json").is_file())
            self.assertTrue((run_dir / "input" / "authority" / "contracts_r2_verifier_report.json").is_file())
            self.assertEqual(
                (run_dir / "input" / "authority" / "authority_receipt.json.sha256").read_text(
                    encoding="ascii"
                ),
                f"{sha256_file(fixture['r2_receipt'])}  authority_receipt.json\n",
            )
            replay = replay_run(
                run_dir,
                adapter=adapter,
                repository_root=root,
                contracts_root=fixture["contracts"],
            )
            self.assertEqual(replay["authority_mode"], CONTRACTS_R2_CURRENT)
            self.assertEqual(replay["semantic_replay"], "PUBLIC_CLI_REPLAY_PASS")
            for fault in (
                "r2_receipt_drift",
                "approval_binding_missing",
                "approval_binding_swap",
                "approval_artifact_drift",
                "action_policy_drift",
                "r1_automatic_fallback",
            ):
                with self.subTest(fault=fault):
                    mutated = work / f"r2-fault-{fault}"
                    inject_fault(run_dir, mutated, fault)
                    with self.assertRaises(ReplayError):
                        replay_run(
                            mutated,
                            repository_root=root,
                            contracts_root=fixture["contracts"],
                        )

    def test_r1_replay_requires_explicit_sealed_historical_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            work = Path(directory)
            fixture = make_fixture_repo(root, work / "fixture", 1)
            adapter = self._global_adapter(root, fixture)
            run_dir = execute_run(
                manifest_path=fixture["manifest"],
                authority_receipt=fixture["authority"],
                contracts_root=fixture["contracts"],
                action_policy=fixture["action_policy"],
                output_dir=work / "source-run",
                run_id="integration-historical-r1",
                mode="FIXTURE_CONFORMANCE",
                adapter=adapter,
                repository_root=root,
            )
            r1 = root / "terminology_contracts_v1" / "release" / "v1.1.0-final" / "history" / "contracts_v1_1_0_authority_receipt_r1_resealed.json"
            shutil.copyfile(r1, run_dir / "input" / "authority" / "authority_receipt.json")
            spec_path = run_dir / "run_spec.json"
            spec = load_json(spec_path, require_object=True)
            spec["authority_mode"] = CONTRACTS_R1_HISTORICAL_REPLAY
            spec["compatibility_mode"] = CONTRACTS_R1_HISTORICAL_REPLAY
            spec["authority"] = {
                "authority_mode": CONTRACTS_R1_HISTORICAL_REPLAY,
                "compatibility_mode": CONTRACTS_R1_HISTORICAL_REPLAY,
                "receipt_self_sha256": R1_RECEIPT_SELF_SHA256,
                "receipt_physical_sha256": R1_RECEIPT_PHYSICAL_SHA256,
            }
            spec_path.unlink()
            dump_json(spec_path, spec)
            reseal_test_run(run_dir)
            replay = replay_run(run_dir)
            self.assertEqual(replay["semantic_replay"], "HISTORICAL_R1_SEALED_REPLAY_PASS")

            blocked = work / "r1-without-mode"
            shutil.copytree(run_dir, blocked)
            blocked_spec_path = blocked / "run_spec.json"
            blocked_spec = load_json(blocked_spec_path, require_object=True)
            blocked_spec.pop("authority_mode")
            blocked_spec.pop("compatibility_mode")
            blocked_spec["authority"].pop("authority_mode")
            blocked_spec["authority"].pop("compatibility_mode")
            blocked_spec_path.unlink()
            dump_json(blocked_spec_path, blocked_spec)
            reseal_test_run(blocked)
            with self.assertRaises(ReplayError):
                replay_run(blocked)

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
                command_prefix=(sys.executable, "-B", str(root / "tests" / "system_integration" / "fixtures" / "public_global_cli.py")),
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
