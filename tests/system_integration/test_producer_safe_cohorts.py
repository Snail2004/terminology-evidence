from __future__ import annotations

import copy
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from integration_harness.adapter_v1.producer_safe import (
    EVALUATION_EV02_ACCEPTANCE_RECEIPT_SELF_SHA256,
    EVALUATION_EV02_CANDIDATE_SET_SHA256,
    EVALUATION_EV02_CANARY_CANDIDATE_ID,
    EVALUATION_EV02_CHILD,
    EVALUATION_EV02_COHORT_SELF_SHA256,
    EVALUATION_EV02_PRODUCER_HANDOFF_ZIP_SHA256,
    EVALUATION_EV02_TREE,
    PROHIBITED_FULL_EVALUATION_AUTHORITY_ZIP_SHA256,
    PRODUCER_SAFE_CANDIDATE_IDENTITY_SHA256,
    PRODUCER_SAFE_CONTEXT_IDENTITY_SHA256,
    PRODUCER_SAFE_MANIFEST_PHYSICAL_SHA256,
    PRODUCER_SAFE_MANIFEST_SELF_SHA256,
    PRODUCER_SAFE_PUBLICATION_RECEIPT_PHYSICAL_SHA256,
    PRODUCER_SAFE_PUBLICATION_RECEIPT_SELF_SHA256,
    PRODUCER_SAFE_SENSE_IDENTITY_SHA256,
    PRODUCER_SAFE_ZIP_SHA256,
    SUPPORTED_COHORT_SIZES,
    load_evaluation_d0_producer_handoff,
    validate_evaluation_producer_input_sha256,
    load_producer_safe_parent,
    verify_producer_safe_cohort_release,
    write_producer_safe_cohort_release,
)
from integration_harness.errors import IntegrityError, PolicyError
from integration_harness.hashing import self_sha256, sha256_file
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
        self.evaluation_zip = Path(
            os.environ.get(
                "HARNESS_EVALUATION_EV02_PRODUCER_HANDOFF_ZIP",
                str(
                    Path.cwd()
                    / "docs/integration/EV02_D0_BLIND_COHORT_PRODUCER_HANDOFF_7de0eca_V1.zip"
                ),
            )
        )
        if (
            not self.zip_path.is_file()
            or not self.publication_path.is_file()
            or not self.evaluation_zip.is_file()
        ):
            self.skipTest("exact reviewed producer-safe release is not available")
        self.schema_root = Path.cwd() / "docs" / "integration"

    def _build(self, output: Path) -> dict[str, object]:
        return write_producer_safe_cohort_release(
            self.zip_path,
            self.evaluation_zip,
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
                self.assertIn(EVALUATION_EV02_CANARY_CANDIDATE_ID, observed)
                previous = observed
            canary = next(
                item for item in parent.candidates
                if item.candidate_id == EVALUATION_EV02_CANARY_CANDIDATE_ID
            )
            context_by_id = {item.context_id: item for item in parent.contexts}
            self.assertTrue(any(context_by_id[item].context_class == "CONTRASTIVE" for item in canary.context_ids))
            d0 = load_json(root / "a" / "cohorts/cohort_015.json", require_object=True)
            self.assertEqual(d0["sense_count"], 5)
            self.assertEqual(d0["candidate_count"], 15)
            self.assertEqual(
                d0["evaluation_candidate_set_sha256"],
                EVALUATION_EV02_CANDIDATE_SET_SHA256,
            )
            self.assertEqual(
                d0["evaluation_phase_membership"]["CANARY"],
                [EVALUATION_EV02_CANARY_CANDIDATE_ID],
            )
            self.assertIn(EVALUATION_EV02_CANARY_CANDIDATE_ID, d0["candidate_ids"])
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
                    evaluation_producer_handoff_zip_path=self.evaluation_zip,
                    publication_receipt_path=self.publication_path,
                    schema_root=self.schema_root,
                )

    def test_exact_evaluation_handoff_and_phase_projection(self) -> None:
        parent = load_producer_safe_parent(
            self.zip_path, publication_receipt_path=self.publication_path
        )
        evaluation = load_evaluation_d0_producer_handoff(
            self.evaluation_zip, parent=parent
        )
        self.assertEqual(
            sha256_file(self.evaluation_zip),
            EVALUATION_EV02_PRODUCER_HANDOFF_ZIP_SHA256,
        )
        self.assertEqual(evaluation.cohort["integrity"]["self_sha256"], EVALUATION_EV02_COHORT_SELF_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            release = Path(directory) / "release"
            self._build(release)
            manifest = load_json(release / "manifest.json", require_object=True)
            self.assertEqual(manifest["evaluation_producer_handoff"]["child_commit"], EVALUATION_EV02_CHILD)
            self.assertEqual(manifest["evaluation_producer_handoff"]["child_tree"], EVALUATION_EV02_TREE)
            self.assertEqual(
                manifest["evaluation_producer_handoff"]["acceptance_receipt_self_sha256"],
                EVALUATION_EV02_ACCEPTANCE_RECEIPT_SELF_SHA256,
            )
            one = load_json(release / "cohorts/cohort_001.json", require_object=True)
            fifteen = load_json(release / "cohorts/cohort_015.json", require_object=True)
            self.assertEqual(one["candidate_ids"], [EVALUATION_EV02_CANARY_CANDIDATE_ID])
            self.assertEqual(one["evaluation_phase_membership"], {"CANARY": [EVALUATION_EV02_CANARY_CANDIDATE_ID], "REMAINDER": []})
            self.assertEqual(fifteen["candidate_ids"], list(evaluation.candidate_ids))
            self.assertEqual(fifteen["evaluation_phase_membership"], evaluation.cohort["phase_membership"])

        with self.assertRaises(PolicyError):
            validate_evaluation_producer_input_sha256(
                PROHIBITED_FULL_EVALUATION_AUTHORITY_ZIP_SHA256
            )
        for prohibited_name in (
            "aggregate_label_distribution.json",
            "split_statistics.json",
            "evaluation_only_member.json",
        ):
            with self.subTest(prohibited_name=prohibited_name), tempfile.TemporaryDirectory() as directory:
                altered = Path(directory) / "altered.zip"
                with zipfile.ZipFile(self.evaluation_zip) as source, zipfile.ZipFile(altered, "w") as target:
                    for info in source.infolist():
                        target.writestr(info, source.read(info))
                    target.writestr(prohibited_name, b'{"forbidden":true}\n')
                with self.assertRaises(IntegrityError):
                    load_evaluation_d0_producer_handoff(altered, parent=parent)

    def test_resealed_ev_authority_and_phase_drifts_fail_closed(self) -> None:
        mutations = (
            self._alternate_canary,
            self._alternate_phase,
            self._alternate_candidate_set,
            self._cross_authority,
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate.__name__), tempfile.TemporaryDirectory() as directory:
                release = Path(directory) / "release"
                self._build(release)
                mutate(release)
                self._reseal_release(release)
                with self.assertRaises(IntegrityError):
                    verify_producer_safe_cohort_release(
                        release,
                        zip_path=self.zip_path,
                        evaluation_producer_handoff_zip_path=self.evaluation_zip,
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

    @staticmethod
    def _alternate_canary(root: Path) -> None:
        cohort_path = root / "cohorts/cohort_001.json"
        cohort = load_json(cohort_path, require_object=True)
        replacement = load_json(root / "cohorts/cohort_015.json", require_object=True)["candidate_ids"][1]
        cohort["candidate_ids"] = [replacement]
        cohort["canary_candidate_id"] = replacement
        cohort["evaluation_phase_membership"] = {"CANARY": [replacement], "REMAINDER": []}
        ProducerSafeCohortAuthorityTests._seal_json(cohort_path, cohort)

    @staticmethod
    def _alternate_phase(root: Path) -> None:
        cohort_path = root / "cohorts/cohort_015.json"
        cohort = load_json(cohort_path, require_object=True)
        canary = cohort["evaluation_phase_membership"]["CANARY"][0]
        replacement = cohort["evaluation_phase_membership"]["REMAINDER"][0]
        cohort["evaluation_phase_membership"]["CANARY"] = [replacement]
        cohort["evaluation_phase_membership"]["REMAINDER"] = sorted(
            [item for item in cohort["candidate_ids"] if item != replacement]
        )
        self_hash_payload = copy.deepcopy(cohort["evaluation_phase_membership"])
        from integration_harness.jsonio import canonical_bytes
        from integration_harness.hashing import sha256_bytes
        cohort["evaluation_phase_membership_sha256"] = sha256_bytes(canonical_bytes(self_hash_payload))
        cohort["canary_candidate_id"] = canary
        ProducerSafeCohortAuthorityTests._seal_json(cohort_path, cohort)

    @staticmethod
    def _alternate_candidate_set(root: Path) -> None:
        cohort_path = root / "cohorts/cohort_015.json"
        cohort = load_json(cohort_path, require_object=True)
        cohort["evaluation_candidate_set_sha256"] = "1" * 64
        ProducerSafeCohortAuthorityTests._seal_json(cohort_path, cohort)

    @staticmethod
    def _cross_authority(root: Path) -> None:
        manifest_path = root / "manifest.json"
        manifest = load_json(manifest_path, require_object=True)
        manifest["evaluation_producer_handoff"]["child_commit"] = "2" * 40
        ProducerSafeCohortAuthorityTests._seal_json(manifest_path, manifest)

    @staticmethod
    def _seal_json(path: Path, value: dict[str, object]) -> None:
        value["integrity"] = {"self_sha256": "0" * 64}
        value["integrity"]["self_sha256"] = self_sha256(value)
        path.unlink()
        dump_json(path, value)

    @staticmethod
    def _reseal_release(root: Path) -> None:
        manifest_path = root / "manifest.json"
        manifest = load_json(manifest_path, require_object=True)
        for binding in manifest["cohorts"]:
            cohort_path = root / binding["relative_path"]
            binding["physical_sha256"] = sha256_file(cohort_path)
            cohort = load_json(cohort_path, require_object=True)
            binding["self_sha256"] = cohort["integrity"]["self_sha256"]
            binding["candidate_set_sha256"] = cohort["candidate_set_sha256"]
        ProducerSafeCohortAuthorityTests._seal_json(manifest_path, manifest)
        lines = [
            f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != "CHECKSUMS.sha256"
        ]
        (root / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


if __name__ == "__main__":
    unittest.main()
