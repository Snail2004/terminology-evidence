import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.analysis_plan.access import (
    GENESIS_SHA256,
    GOLD_ACCESS_SCHEMA_ID,
    GOLD_ACCESS_SCHEMA_VERSION,
    GoldAccessError,
    seal_gold_access_event,
    verify_gold_access_ledger,
)
from evaluation.v1.analysis_plan.builder import (
    ACCESS_TEMPLATES_FILE,
    CONTENT_DIRECTORY,
    PLAN_FILE,
    TABLES_FILE,
    build_analysis_plan_content,
)
from evaluation.v1.analysis_plan.publication import (
    FREEZE_RECEIPT_FILE,
    FREEZE_STATUS,
    PUBLICATION_CHECKSUMS_FILE,
    PUBLICATION_MANIFEST_FILE,
    AnalysisPlanPublicationError,
    build_analysis_plan_publication,
    verify_analysis_plan_publication,
)
from evaluation.v1.analysis_plan.verifier import AnalysisPlanError, verify_analysis_plan_content
from evaluation.v1.jsonio import read_json, sha256_value, write_json
from evaluation.v1.d0_preparation.builder import build_d0_content
from evaluation.v1.d0_preparation.publication import verify_d0_publication
from evaluation.v1.d0_preparation.verifier import verify_d0_content
from tests.evaluation.git_context import resolve_test_git_context


class AnalysisPlanFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, cls.source_commit = resolve_test_git_context(Path(__file__).resolve().parents[2])
        cls.content = cls.repo / CONTENT_DIRECTORY

    def test_frozen_content_matches_registry_and_has_no_access(self):
        report = verify_analysis_plan_content(self.repo)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["actual_gold_access_receipt_count"], 0)
        self.assertEqual(report["gold_access_ledger_head"], GENESIS_SHA256)
        publication = verify_analysis_plan_publication(self.repo)
        self.assertEqual(publication["status"], FREEZE_STATUS)
        self.assertEqual(publication["actual_gold_access_receipt_count"], 0)
        self.assertEqual(publication["network_calls"], 0)
        self.assertEqual(publication["provider_calls"], 0)

        plan = read_json(self.content / PLAN_FILE)
        self.assertEqual(plan["label_mapping"]["primary_binary"]["positive"], ["ACCEPT"])
        self.assertEqual(plan["label_mapping"]["primary_binary"]["negative"], ["REJECT", "SPLIT_REQUIRED"])
        self.assertEqual(
            plan["e_status_reporting_mapping"]["ATTESTED_LIMITED"],
            ["WEAKLY_ATTESTED"],
        )
        self.assertEqual(plan["missing_data_policy"]["imputation"], "NONE")
        self.assertEqual(plan["confidence_interval_policy"]["proportions"], "wilson")
        self.assertEqual([row["stage"] for row in plan["access_order"]], ["D0", "D1", "V1", "T1"])

        with TemporaryDirectory() as temp:
            content = Path(temp) / "d0-content"
            result = build_d0_content(self.repo, content)
            verified = verify_d0_content(self.repo, content)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(verified["status"], "PASS")
            self.assertEqual(verified["sense_count"], 5)
            self.assertEqual(verified["candidate_count"], 15)
            self.assertFalse(verified["gold_access"])
            self.assertEqual(verified["provider_calls"], 0)
            self.assertEqual(verified["network_calls"], 0)

        publication = self.repo / "evaluation" / "v1" / "authority" / "d0_preparation_v1"
        if (publication / "manifest.json").is_file():
            report = verify_d0_publication(self.repo, publication)
            self.assertEqual(report["status"], "PASS")
            self.assertFalse(report["gold_access"])

    def test_planned_tables_and_builder_are_result_free_and_deterministic(self):
        plan = read_json(self.content / PLAN_FILE)
        tables = read_json(self.content / TABLES_FILE)
        access = read_json(self.content / ACCESS_TEMPLATES_FILE)
        self.assertEqual(plan["scope"]["sense_count"], 50)
        self.assertEqual(plan["scope"]["candidate_count"], 150)
        self.assertEqual(tables["result_cells_present"], 0)
        self.assertEqual([table["id"] for table in tables["tables"]], [f"T{index:02d}" for index in range(1, 13)])
        self.assertEqual(access["actual_access_receipts"], [])

        with TemporaryDirectory() as temp:
            output = Path(temp) / "content"
            build_analysis_plan_content(
                self.repo,
                source_parent_commit=plan["source_parent_commit"],
                output_directory=output,
            )
            for filename in (PLAN_FILE, TABLES_FILE, ACCESS_TEMPLATES_FILE):
                self.assertEqual((output / filename).read_bytes(), (self.content / filename).read_bytes())

            d0_one = Path(temp) / "d0-one"
            d0_two = Path(temp) / "d0-two"
            build_d0_content(self.repo, d0_one)
            build_d0_content(self.repo, d0_two)
            for path in sorted(d0_one.iterdir()):
                self.assertEqual(path.read_bytes(), (d0_two / path.name).read_bytes())

        receipt = read_json(self.content / FREEZE_RECEIPT_FILE)
        with TemporaryDirectory() as temp:
            publication = Path(temp) / "publication"
            build_analysis_plan_publication(
                repo=self.repo,
                content_commit=receipt["content_commit"],
                output=publication,
            )
            for filename in (FREEZE_RECEIPT_FILE, PUBLICATION_MANIFEST_FILE, PUBLICATION_CHECKSUMS_FILE):
                self.assertEqual((publication / filename).read_bytes(), (self.content / filename).read_bytes())

    def test_content_tamper_rejects(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            shutil.copytree(self.content, root / CONTENT_DIRECTORY)
            shutil.copytree(
                self.repo / "evaluation" / "v1" / "registries",
                root / "evaluation" / "v1" / "registries",
            )
            expected = self.repo / "evaluation" / "v1" / "authority" / "expected_test_manifest_v1.json"
            target = root / "evaluation" / "v1" / "authority" / "expected_test_manifest_v1.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(expected, target)
            docs = root / "docs" / "evaluation"
            docs.mkdir(parents=True)
            for name in (
                "ANALYSIS_PLAN_50_150_V1.md",
                "Yeu_cau_Agent_Evaluation_Freeze_Analysis_Plan_50_150_V1.md",
            ):
                shutil.copyfile(self.repo / "docs" / "evaluation" / name, docs / name)

            plan_path = root / CONTENT_DIRECTORY / PLAN_FILE
            plan = read_json(plan_path)
            plan["scope"]["candidate_count"] = 149
            write_json(plan_path, plan)
            with self.assertRaises(AnalysisPlanError):
                verify_analysis_plan_content(root)

        with TemporaryDirectory() as temp:
            publication = Path(temp) / "publication"
            publication.mkdir()
            for filename in (FREEZE_RECEIPT_FILE, PUBLICATION_MANIFEST_FILE, PUBLICATION_CHECKSUMS_FILE):
                shutil.copyfile(self.content / filename, publication / filename)
            receipt_path = publication / FREEZE_RECEIPT_FILE
            receipt = read_json(receipt_path)
            receipt["scope"]["candidate_count"] = 149
            receipt["integrity"]["self_sha256"] = ""
            unsigned = dict(receipt)
            unsigned["integrity"] = {}
            receipt["integrity"]["self_sha256"] = sha256_value(unsigned)
            write_json(receipt_path, receipt)
            with self.assertRaises(AnalysisPlanPublicationError):
                verify_analysis_plan_publication(self.repo, bundle_root=publication)

        with TemporaryDirectory() as temp:
            content = Path(temp) / "d0-content"
            build_d0_content(self.repo, content)
            cohort_path = content / "d0_blind_cohort_authority_v1.json"
            cohort = read_json(cohort_path)
            cohort["candidate_ids"] = list(reversed(cohort["candidate_ids"]))
            cohort["integrity"]["self_sha256"] = ""
            cohort["integrity"]["self_sha256"] = sha256_value({**cohort, "integrity": {}})
            write_json(cohort_path, cohort)
            with self.assertRaises(ValueError):
                verify_d0_content(self.repo, content)

    def test_gold_access_receipts_enforce_order_hashes_and_time(self):
        freeze_sha = "a" * 64

        def event(stage, sequence, previous, issued_at):
            return seal_gold_access_event(
                {
                    "schema_id": GOLD_ACCESS_SCHEMA_ID,
                    "schema_version": GOLD_ACCESS_SCHEMA_VERSION,
                    "sequence_number": sequence,
                    "stage": stage,
                    "issued_at": issued_at,
                    "actor": "evaluation-maintainer",
                    "purpose": f"authorized {stage} gold access",
                    "previous_event_sha256": previous,
                    "analysis_plan_freeze_receipt_sha256": freeze_sha,
                    "dataset_split_manifest_sha256": "b" * 64,
                    "producer_bundle_manifest_sha256": "c" * 64,
                    "gold_bundle_manifest_sha256": "d" * 64,
                    "authorized_scope_sha256": "e" * 64,
                    "authorization": {
                        "approved": True,
                        "approved_by": "reviewer",
                        "approved_at": issued_at,
                        "approval_receipt_sha256": "f" * 64,
                    },
                    "event_sha256": "",
                }
            )

        d0 = event("D0", 0, GENESIS_SHA256, "2026-07-30T01:00:00+07:00")
        d1 = event("D1", 1, d0["event_sha256"], "2026-07-30T02:00:00+07:00")
        self.assertEqual(verify_gold_access_ledger([d0, d1], analysis_plan_freeze_receipt_sha256=freeze_sha), d1["event_sha256"])

        wrong_stage = event("V1", 1, d0["event_sha256"], "2026-07-30T02:00:00+07:00")
        with self.assertRaises(GoldAccessError):
            verify_gold_access_ledger([d0, wrong_stage], analysis_plan_freeze_receipt_sha256=freeze_sha)
        backward = event("D1", 1, d0["event_sha256"], "2026-07-30T00:59:59+07:00")
        with self.assertRaises(GoldAccessError):
            verify_gold_access_ledger([d0, backward], analysis_plan_freeze_receipt_sha256=freeze_sha)
        tampered = dict(d1)
        tampered["purpose"] = "changed after sealing"
        with self.assertRaises(GoldAccessError):
            verify_gold_access_ledger([d0, tampered], analysis_plan_freeze_receipt_sha256=freeze_sha)

        with TemporaryDirectory() as temp:
            content = Path(temp) / "d0-content"
            build_d0_content(self.repo, content)
            ledger = (content / "pre_d0_amendment_ledger_v1.jsonl").read_text(encoding="utf-8")
            self.assertEqual(ledger.count("PRE_D0_AMENDMENT"), 1)
            self.assertEqual(ledger.count("PRE_D0_REFREEZE"), 1)
            cohort = read_json(content / "d0_blind_cohort_authority_v1.json")
            self.assertFalse(cohort["gold_access_authorized"])
