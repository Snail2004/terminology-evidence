import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.constants import AMENDMENT_SCHEMA_ID, MODE_REAL_AUTHORITY, SCHEMA_VERSION
from evaluation.v1.preregistration.amendments import AmendmentError, append_amendment, validate_amendment
from evaluation.v1.preregistration.freeze import DurablePreregistrationStore, FreezeError
from evaluation.v1.preregistration.receipt import build_receipt
from tests.evaluation.git_context import resolve_test_git_context


class AmendmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[2]
        git_repo, commit = resolve_test_git_context(cls.repo)
        registries = cls.repo / "evaluation" / "v1" / "registries"
        artifacts = {
            "contracts_receipt": cls.repo / "terminology_contracts_v1" / "release" / "v1.1.0-final" / "contracts_v1_1_0_authority_receipt_r2.json",
            "contracts_approval_binding": cls.repo / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2" / "approval_binding_v1.json",
            "contracts_checksums": cls.repo / "review_evidence" / "contracts" / "contracts-v1.1.0" / "authority-r2" / "CHECKSUMS.sha256",
            "global_authority_report": cls.repo / "global_validator" / "v1" / "release" / "authority_verification_report.json",
            "global_action_policy": cls.repo / "global_validator" / "v1" / "release" / "gate_policy_report.json",
            "dataset_manifest": cls.repo / "dataset" / "d2l_context_support_set_validation_ready_v3" / "manifest.json",
            "dataset_split_assignments": cls.repo / "dataset" / "d2l_context_support_set_validation_ready_v3" / "split_assignments.jsonl",
        }
        cls.receipt = build_receipt(
            mode=MODE_REAL_AUTHORITY,
            base_commit=commit,
            repo_root_path=git_repo,
            registry_root_path=registries,
            authority_artifact_paths=artifacts,
            artifact_hashes={"evaluation_plan": "a" * 64},
        )

    @staticmethod
    def _amendment(*, primary=True, version="v2", namespace=None):
        return {
            "schema_id": AMENDMENT_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "amendment_id": "amendment-001",
            "reason": "clarify preregistered analysis",
            "affected_artifacts": ["evaluation/v1/registries/metric_registry_v1.json"],
            "before_hashes": {"evaluation/v1/registries/metric_registry_v1.json": "b" * 64},
            "after_hashes": {"evaluation/v1/registries/metric_registry_v1.json": "c" * 64},
            "changes_primary_analysis": primary,
            "impact_on_claims": "requires a new freeze",
            "new_preregistration_version": version,
            "analysis_namespace": namespace,
        }

    @staticmethod
    def _store(root):
        return DurablePreregistrationStore(root / "events.jsonl", root / "state.json")

    def test_prevalidation_amendment_requires_new_freeze(self):
        with TemporaryDirectory() as temp:
            store = self._store(Path(temp))
            store.freeze(self.receipt, actor="maintainer")
            state = append_amendment(store, self._amendment(), actor="maintainer")
            self.assertEqual(state["status"], "REFREEZE_REQUIRED")
            with self.assertRaises(FreezeError):
                store.open_validation(actor="maintainer", purpose="validation")
            self.assertEqual(store.load()["event_count"], 2)

    def test_postvalidation_amendment_invalidates_primary_path(self):
        with TemporaryDirectory() as temp:
            store = self._store(Path(temp))
            store.freeze(self.receipt, actor="maintainer")
            store.open_validation(actor="maintainer", purpose="validation")
            state = append_amendment(store, self._amendment(), actor="maintainer")
            self.assertEqual(state["status"], "REFREEZE_REQUIRED")
            self.assertEqual(state["amendment_count"], 1)

    def test_post_hidden_primary_rejects_but_exploratory_isolated(self):
        with TemporaryDirectory() as temp:
            store = self._store(Path(temp))
            store.freeze(self.receipt, actor="maintainer")
            store.open_validation(actor="maintainer", purpose="validation")
            store.freeze_calibration(actor="maintainer", calibration_artifact_sha256="d" * 64)
            store.open_hidden_test(actor="maintainer", purpose="hidden")
            with self.assertRaises(AmendmentError):
                append_amendment(store, self._amendment(), actor="maintainer")
            exploratory = self._amendment(primary=False, version=None, namespace="exploratory/post-test")
            state = append_amendment(store, exploratory, actor="maintainer")
            self.assertEqual(state["status"], "HIDDEN_TEST_ACCESSED")
            self.assertEqual(state["exploratory_count"], 1)

    def test_amendment_path_and_hash_shape_fail_closed(self):
        bad = self._amendment()
        bad["affected_artifacts"] = ["../metric.json"]
        with self.assertRaises((AmendmentError, ValueError)):
            validate_amendment(bad)
        bad = self._amendment()
        bad["before_hashes"]["evaluation/v1/registries/metric_registry_v1.json"] = "not-a-hash"
        with self.assertRaises(AmendmentError):
            validate_amendment(bad)
