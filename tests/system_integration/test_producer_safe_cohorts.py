from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path

from integration_harness.adapter_v1.producer_safe import (
    PRODUCER_SAFE_CANDIDATE_IDENTITY_SHA256,
    PRODUCER_SAFE_CONTEXT_IDENTITY_SHA256,
    PRODUCER_SAFE_MANIFEST_PHYSICAL_SHA256,
    PRODUCER_SAFE_MANIFEST_SELF_SHA256,
    PRODUCER_SAFE_PUBLICATION_RECEIPT_PHYSICAL_SHA256,
    PRODUCER_SAFE_PUBLICATION_RECEIPT_SELF_SHA256,
    PRODUCER_SAFE_SENSE_IDENTITY_SHA256,
    PRODUCER_SAFE_ZIP_SHA256,
    SUPPORTED_COHORT_SIZES,
    load_producer_safe_parent,
    verify_producer_safe_cohort_release,
    write_producer_safe_cohort_release,
)
from integration_harness.errors import IntegrityError
from integration_harness.hashing import sha256_file
from integration_harness.jsonio import dump_json, load_json


class ProducerSafeCohortAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        release = Path(
            os.environ.get(
                "HARNESS_PRODUCER_SAFE_RELEASE_ROOT",
                r"C:\work\terminology_evidence-worktrees\dataset-v1\dataset\pipeline_input_50_150_producer_safe_v1\release",
            )
        )
        self.zip_path = release / "pipeline_input_50_150_producer_safe_v1.zip"
        self.publication_path = release / "pipeline_input_50_150_producer_safe_v1_publication_receipt.json"
        if not self.zip_path.is_file() or not self.publication_path.is_file():
            self.skipTest("exact reviewed producer-safe release is not available")
        self.schema_root = Path.cwd() / "docs" / "integration"

    def _build(self, output: Path) -> dict[str, object]:
        return write_producer_safe_cohort_release(
            self.zip_path,
            output,
            publication_receipt_path=self.publication_path,
            schema_root=self.schema_root,
            issuer_id="system-integration-maintainer",
            authority_id="producer-safe-cohort-authority-v1",
            run_id="RUN-D0",
            phase_id="D0_ONE_CANDIDATE",
            split_id="producer-safe-parent-150",
        )

    def test_exact_parent_and_nested_d0_1_15(self) -> None:
        parent = load_producer_safe_parent(
            self.zip_path, publication_receipt_path=self.publication_path
        )
        self.assertEqual(len(parent.candidates), 150)
        self.assertEqual(len(parent.contexts), 386)
        self.assertEqual(sha256_file(self.zip_path), PRODUCER_SAFE_ZIP_SHA256)
        self.assertEqual(parent.manifest["manifest_sha256"], PRODUCER_SAFE_MANIFEST_SELF_SHA256)
        self.assertEqual(parent.manifest["sense_identity_sha256"], PRODUCER_SAFE_SENSE_IDENTITY_SHA256)
        self.assertEqual(parent.manifest["candidate_identity_sha256"], PRODUCER_SAFE_CANDIDATE_IDENTITY_SHA256)
        self.assertEqual(parent.manifest["context_identity_sha256"], PRODUCER_SAFE_CONTEXT_IDENTITY_SHA256)
        self.assertEqual(parent.publication_receipt["receipt_sha256"], PRODUCER_SAFE_PUBLICATION_RECEIPT_SELF_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self._build(root / "a")
            self._build(root / "b")
            self.assertEqual(result["cohort_counts"], list(SUPPORTED_COHORT_SIZES))
            previous: set[str] = set()
            for count in SUPPORTED_COHORT_SIZES:
                cohort = load_json(root / "a" / f"cohorts/cohort_{count:03d}.json", require_object=True)
                observed = set(cohort["candidate_ids"])
                self.assertEqual(len(observed), count)
                self.assertTrue(previous.issubset(observed))
                self.assertIn(parent.canary_candidate_id, observed)
                previous = observed
            canary = next(item for item in parent.candidates if item.candidate_id == parent.canary_candidate_id)
            context_by_id = {item.context_id: item for item in parent.contexts}
            self.assertTrue(any(context_by_id[item].context_class == "CONTRASTIVE" for item in canary.context_ids))
            d0 = load_json(root / "a" / "cohorts/cohort_015.json", require_object=True)
            self.assertEqual(d0["sense_count"], 5)
            self.assertEqual(d0["candidate_count"], 15)
            self.assertIn(parent.canary_candidate_id, d0["candidate_ids"])
            for sense_id in d0["sense_ids"]:
                context_ids = {
                    item["context_id"]
                    for item in d0["context_bindings"]
                    if item["sense_id"] == sense_id
                }
                self.assertTrue(
                    any(context_by_id[item].context_class == "CONTRASTIVE" for item in context_ids)
                )
            a_hashes = {
                path.relative_to(root / "a").as_posix(): sha256_file(path)
                for path in (root / "a").rglob("*") if path.is_file()
            }
            b_hashes = {
                path.relative_to(root / "b").as_posix(): sha256_file(path)
                for path in (root / "b").rglob("*") if path.is_file()
            }
            self.assertEqual(a_hashes, b_hashes)

    def test_publication_or_parent_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publication = load_json(self.publication_path, require_object=True)
            publication["candidate_count"] = 149
            tampered_publication = root / "publication.json"
            dump_json(tampered_publication, publication)
            with self.assertRaises(IntegrityError):
                load_producer_safe_parent(
                    self.zip_path, publication_receipt_path=tampered_publication
                )
            self._build(root / "release")
            cohort_path = root / "release" / "cohorts" / "cohort_015.json"
            cohort = load_json(cohort_path, require_object=True)
            changed = copy.deepcopy(cohort)
            changed["candidate_ids"] = list(reversed(changed["candidate_ids"]))
            cohort_path.unlink()
            dump_json(cohort_path, changed)
            with self.assertRaises(IntegrityError):
                verify_producer_safe_cohort_release(
                    root / "release",
                    zip_path=self.zip_path,
                    publication_receipt_path=self.publication_path,
                    schema_root=self.schema_root,
                )

    def test_exact_physical_authority_constants(self) -> None:
        parent = load_producer_safe_parent(
            self.zip_path, publication_receipt_path=self.publication_path
        )
        self.assertEqual(sha256_file(self.publication_path), PRODUCER_SAFE_PUBLICATION_RECEIPT_PHYSICAL_SHA256)
        self.assertEqual(
            sha256_file(
                self.zip_path.parent
                / "pipeline_input_50_150_producer_safe_v1"
                / "pipeline_input_50_150_manifest.json"
            ),
            PRODUCER_SAFE_MANIFEST_PHYSICAL_SHA256,
        )
        self.assertEqual(parent.publication_receipt["network_call_count"], 0)
        self.assertEqual(parent.publication_receipt["provider_call_count"], 0)


if __name__ == "__main__":
    unittest.main()
