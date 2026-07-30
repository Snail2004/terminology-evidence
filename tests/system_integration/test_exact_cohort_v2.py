from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from integration_harness.adapter_v1.availability import (
    load_availability_manifest,
    write_missing_availability_manifest,
)
from integration_harness.adapter_v1.build import build_adapter_bundle
from integration_harness.adapter_v1.dataset import SYNTHETIC_MODE, load_dataset_release
from integration_harness.adapter_v1.replay import replay_adapter_bundle
from integration_harness.adapter_v1.sidecars import (
    SidecarSet,
    build_sidecars,
    verify_sidecars,
)
from integration_harness.hashing import self_sha256, sha256_bytes
from integration_harness.jsonio import canonical_bytes, load_json

from .adapter_helpers import make_synthetic_dataset_release


class ExactCohortV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path.cwd()
        self.contracts = self.repo / "terminology_contracts_v1"
        self.schema = self.repo / "docs/integration/artifact_inventory_exact_cohort_v2.schema.json"

    def test_exact_cohort_cardinalities_build_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for candidate_count in (1, 3, 15, 30, 90, 150):
                with self.subTest(candidate_count=candidate_count):
                    source = make_synthetic_dataset_release(
                        self.repo,
                        root / f"dataset-{candidate_count}",
                        candidate_count=candidate_count,
                    )
                    dataset = load_dataset_release(
                        source["zip"],
                        source["pin"],
                        git_receipt_path=None,
                        schema_root=self.contracts,
                        mode=SYNTHETIC_MODE,
                    )
                    availability = write_missing_availability_manifest(
                        root / f"availability-{candidate_count}",
                        candidates=dataset.candidates,
                        adapter_mode=SYNTHETIC_MODE,
                        run_id=f"cohort-{candidate_count}",
                        phase_id="exact-cohort-conformance",
                        split_id=f"candidates-{candidate_count}",
                        observed_at="2026-07-30T00:00:00Z",
                        reason_code="ZERO_PROVIDER_INPUT_NOT_SUBMITTED",
                    )
                    output = root / f"bundle-{candidate_count}"
                    result = build_adapter_bundle(
                        dataset_zip=source["zip"],
                        dataset_pin=source["pin"],
                        dataset_git_receipt=None,
                        availability_manifest=availability,
                        contracts_root=self.contracts,
                        repository_root=self.repo,
                        output_root=output,
                        adapter_mode=SYNTHETIC_MODE,
                        inventory_schema_path=self.schema,
                    )
                    self.assertEqual(result["candidate_count"], candidate_count)
                    self.assertEqual(result["not_submitted_count"], candidate_count)
                    inventory = load_json(output / "artifact_inventory.json", require_object=True)
                    self.assertEqual(inventory["schema_id"], "ArtifactInventoryExactCohortV2")
                    cohort = load_json(
                        output / "sidecars/harness_cohort_inventory_v2.json",
                        require_object=True,
                    )
                    self.assertEqual(cohort["schema_id"], "HarnessCohortInventoryV2")
                    self.assertEqual(cohort["candidate_count"], len(cohort["candidates"]))
                    replay = replay_adapter_bundle(output, contracts_root=self.contracts)
                    self.assertEqual(replay["candidate_count"], candidate_count)
                    self.assertEqual(replay["not_submitted_count"], candidate_count)

    def test_v1_sidecar_family_retains_historical_replay_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = make_synthetic_dataset_release(
                self.repo, root / "dataset", candidate_count=15
            )
            dataset = load_dataset_release(
                source["zip"], source["pin"], git_receipt_path=None,
                schema_root=self.contracts, mode=SYNTHETIC_MODE,
            )
            availability_path = write_missing_availability_manifest(
                root / "availability",
                candidates=dataset.candidates,
                adapter_mode=SYNTHETIC_MODE,
                run_id="legacy-sidecar-replay",
                phase_id="historical",
                split_id="fifteen",
                observed_at="2026-07-30T00:00:00Z",
                reason_code="HISTORICAL_NOT_SUBMITTED",
            )
            availability_input = load_availability_manifest(
                availability_path,
                candidates=dataset.candidates,
                schema_root=self.contracts,
                adapter_mode=SYNTHETIC_MODE,
            )
            active = build_sidecars(
                dataset, availability_input, package_refs={}, receipt_refs={}
            )
            legacy = SidecarSet(
                cohort=copy.deepcopy(active.cohort),
                authority=copy.deepcopy(active.authority),
                availability=copy.deepcopy(active.availability),
                readiness=copy.deepcopy(active.readiness),
            )
            legacy.cohort["schema_id"] = "HarnessCohortInventoryV1"
            legacy.cohort["schema_version"] = "1.0.0"
            legacy.cohort["integrity"]["self_sha256"] = self_sha256(legacy.cohort)
            cohort_physical = sha256_bytes(canonical_bytes(legacy.cohort) + b"\n")
            legacy.authority["schema_id"] = "GlobalBatchAuthorityV1"
            legacy.authority["schema_version"] = "1.0.0"
            legacy.authority["cohort_inventory"] = {
                "self_sha256": legacy.cohort["integrity"]["self_sha256"],
                "physical_sha256": cohort_physical,
            }
            legacy.authority["integrity"]["self_sha256"] = self_sha256(legacy.authority)
            authority_physical = sha256_bytes(canonical_bytes(legacy.authority) + b"\n")
            legacy.availability["schema_id"] = "EvidenceAvailabilityManifestV1"
            legacy.availability["schema_version"] = "1.0.0"
            legacy.availability["integrity"]["self_sha256"] = self_sha256(legacy.availability)
            availability_physical = sha256_bytes(canonical_bytes(legacy.availability) + b"\n")
            legacy.readiness["schema_id"] = "GlobalBatchReadinessReportV1"
            legacy.readiness["schema_version"] = "1.0.0"
            legacy.readiness["batch_authority"] = {
                "self_sha256": legacy.authority["integrity"]["self_sha256"],
                "physical_sha256": authority_physical,
            }
            legacy.readiness["availability_manifest"] = {
                "self_sha256": legacy.availability["integrity"]["self_sha256"],
                "physical_sha256": availability_physical,
            }
            legacy.readiness["integrity"]["self_sha256"] = self_sha256(legacy.readiness)
            stats = verify_sidecars(
                legacy,
                dataset=dataset,
                physical_hashes={
                    "cohort": cohort_physical,
                    "authority": authority_physical,
                    "availability": availability_physical,
                    "readiness": sha256_bytes(canonical_bytes(legacy.readiness) + b"\n"),
                },
            )
            self.assertEqual(stats["candidate_count"], 15)
            self.assertEqual(stats["not_submitted_count"], 15)
