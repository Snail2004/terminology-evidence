import subprocess
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.constants import MODE_REAL_AUTHORITY, MODE_SYNTHETIC
from evaluation.v1.jsonio import read_json, write_json
from evaluation.v1.preregistration.freeze import (
    AccessLog,
    DurablePreregistrationStore,
    FreezeError,
    FreezeState,
)
from evaluation.v1.preregistration.ledger import LedgerError
from evaluation.v1.preregistration.receipt import build_receipt
from evaluation.v1.preregistration.recovery import RecoveryError, recover_projection, verify_recovery_receipt


class DurableStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[2]
        cls.registries = cls.repo / "evaluation" / "v1" / "registries"
        cls.commit = subprocess.run(
            ["git", "-C", str(cls.repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        artifacts = {
            "contracts_receipt": cls.repo / "terminology_contracts_v1" / "release" / "v1.1.0-final" / "contracts_v1_1_0_authority_receipt_r2.json",
            "contracts_approval_binding": cls.repo / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2" / "approval_binding_v1.json",
            "contracts_checksums": cls.repo / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2" / "CHECKSUMS.sha256",
            "global_authority_report": cls.repo / "global_validator" / "v1" / "release" / "authority_verification_report.json",
            "global_action_policy": cls.repo / "global_validator" / "v1" / "release" / "gate_policy_report.json",
            "dataset_manifest": cls.repo / "dataset" / "d2l_context_support_set_validation_ready_v3" / "manifest.json",
            "dataset_split_assignments": cls.repo / "dataset" / "d2l_context_support_set_validation_ready_v3" / "split_assignments.jsonl",
        }
        cls.real_receipt = build_receipt(
            mode=MODE_REAL_AUTHORITY,
            base_commit=cls.commit,
            repo_root_path=cls.repo,
            registry_root_path=cls.registries,
            authority_artifact_paths=artifacts,
            artifact_hashes={"evaluation_plan": "a" * 64},
            created_at="2026-07-29T15:00:00+07:00",
        )

    @staticmethod
    def _store(root: Path, *, timeout: float = 2.0) -> DurablePreregistrationStore:
        return DurablePreregistrationStore(root / "events.jsonl", root / "state.json", lock_timeout_seconds=timeout)

    def test_restart_preserves_one_time_access(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            store.freeze(self.real_receipt, actor="maintainer", issued_at="2026-07-29T15:01:00+07:00")
            store.open_validation(actor="maintainer", purpose="validation", issued_at="2026-07-29T15:02:00+07:00")
            store.freeze_calibration(actor="maintainer", calibration_artifact_sha256="c" * 64, issued_at="2026-07-29T15:03:00+07:00")
            store.open_hidden_test(actor="maintainer", purpose="hidden evaluation", issued_at="2026-07-29T15:04:00+07:00")
            reloaded = self._store(root)
            state = reloaded.load()
            self.assertEqual(state["status"], "HIDDEN_TEST_ACCESSED")
            self.assertEqual(FreezeState.from_projection(state).hidden_test_opened_at, "2026-07-29T15:04:00+07:00")
            self.assertEqual(len(AccessLog.from_ledger(reloaded.ledger).entries), 2)
            with self.assertRaises(FreezeError):
                reloaded.open_hidden_test(actor="maintainer", purpose="again")
            self.assertEqual(reloaded.load()["event_count"], 4)

    def test_synthetic_receipt_cannot_freeze(self):
        synthetic = build_receipt(
            mode=MODE_SYNTHETIC,
            base_commit=self.commit,
            repo_root_path=self.repo,
            registry_root_path=self.registries,
            synthetic_reason="fixture",
        )
        with TemporaryDirectory() as temp:
            with self.assertRaises(FreezeError):
                self._store(Path(temp)).freeze(synthetic, actor="test")

    def test_concurrent_hidden_test_open_is_exactly_once(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            store.freeze(self.real_receipt, actor="maintainer")
            store.open_validation(actor="maintainer", purpose="validation")
            store.freeze_calibration(actor="maintainer", calibration_artifact_sha256="d" * 64)
            outcomes = []
            guard = threading.Lock()

            def open_once():
                try:
                    store.open_hidden_test(actor="worker", purpose="hidden")
                    result = "opened"
                except (FreezeError, LedgerError):
                    result = "rejected"
                with guard:
                    outcomes.append(result)

            threads = [threading.Thread(target=open_once) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(sorted(outcomes), ["opened", "rejected"])
            self.assertEqual(store.load()["event_count"], 4)

    def test_projection_divergence_requires_explicit_recovery(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            store.freeze(self.real_receipt, actor="maintainer")
            store.open_validation(actor="maintainer", purpose="validation")
            projection = read_json(root / "state.json")
            projection["status"] = "TAMPERED"
            write_json(root / "state.json", projection)
            with self.assertRaises(FreezeError):
                store.load()
            result = recover_projection(
                store,
                root / "recovery.json",
                reason="projection byte drift",
                operator="maintainer",
                recovery_tool="evaluation-recovery",
                recovery_tool_version="1.0.0",
                issued_at="2026-07-29T15:05:00+07:00",
            )
            self.assertEqual(result["projection"]["status"], "VALIDATION_ACCESSED")
            self.assertEqual(result["projection"]["recovery_count"], 1)
            verify_recovery_receipt(result["receipt"])
            tampered_receipt = dict(result["receipt"])
            tampered_receipt["reason"] = "rewritten"
            with self.assertRaises(RecoveryError):
                verify_recovery_receipt(tampered_receipt)
            self.assertEqual(store.load(), result["projection"])
            with self.assertRaises(RecoveryError):
                recover_projection(
                    store,
                    root / "another.json",
                    reason="not needed",
                    operator="maintainer",
                    recovery_tool="evaluation-recovery",
                    recovery_tool_version="1.0.0",
                )

    def test_ledger_tamper_cannot_be_recovered(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            store.freeze(self.real_receipt, actor="maintainer")
            path = root / "events.jsonl"
            path.write_text(path.read_text(encoding="utf-8").replace("maintainer", "attacker"), encoding="utf-8")
            with self.assertRaises(LedgerError):
                store.load()
            with self.assertRaises(LedgerError):
                recover_projection(
                    store,
                    root / "recovery.json",
                    reason="ledger drift",
                    operator="maintainer",
                    recovery_tool="evaluation-recovery",
                    recovery_tool_version="1.0.0",
                )

    def test_busy_writer_fails_closed(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root, timeout=0.05)
            store.freeze(self.real_receipt, actor="maintainer")
            with store.ledger.writer(), self.assertRaises(LedgerError):
                store.open_validation(actor="maintainer", purpose="validation")
