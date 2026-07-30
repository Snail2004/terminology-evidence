from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from integration_harness.adapter_v1.build import build_adapter_bundle
from integration_harness.adapter_v1.availability import (
    write_missing_availability_manifest,
    write_present_availability_manifest,
)
from integration_harness.adapter_v1.dataset import (
    OFFICIAL_MODE,
    SYNTHETIC_MODE,
    load_dataset_release,
)
from integration_harness.adapter_v1.replay import replay_adapter_bundle
from integration_harness.errors import IntegrityError, PolicyError, ReplayError, ValidationError
from integration_harness.hashing import self_sha256, sha256_file
from integration_harness.inventory import load_inventory
from integration_harness.join import validate_and_join
from integration_harness.jsonio import dump_json, load_json
from integration_harness.pipeline import execute_run
from integration_harness.replay import replay_run

from .adapter_helpers import (
    make_external_hold_authority,
    make_producer_set,
    make_synthetic_dataset_release,
)
from .helpers import FakePublicGlobalAdapter, make_fixture_repo


class Adapter50150Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path.cwd()
        self.contracts = self.repo / "terminology_contracts_v1"
        self.schema = self.repo / "docs" / "integration" / "artifact_inventory_50_150_schema.json"
        self.official_root = (
            self.repo
            / "review_evidence"
            / "dataset"
            / "d2l-stage-a-official-5-sense-pilot-v1"
        )

    def _official_dataset(self):
        return load_dataset_release(
            self.official_root
            / "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip",
            self.official_root / "official_dataset_input_pin_v1.json",
            git_receipt_path=self.official_root / "git_source_receipt.json",
            schema_root=self.contracts,
            mode=OFFICIAL_MODE,
            repository_root=self.repo,
        )

    def test_official_fifteen_candidate_missing_preflight_replays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            dataset = self._official_dataset()
            availability = write_missing_availability_manifest(
                work / "availability",
                candidates=dataset.candidates,
                adapter_mode=OFFICIAL_MODE,
                run_id="official-adapter-preflight",
                phase_id="zero-provider-preflight",
                split_id="official-five-sense",
                observed_at="2026-07-30T00:00:00Z",
                reason_code="PRODUCER_PACKAGE_SET_NOT_MAIN_ACCEPTED",
            )
            result = build_adapter_bundle(
                dataset_zip=dataset.zip_path,
                dataset_pin=dataset.pin_path,
                dataset_git_receipt=dataset.git_receipt_path,
                availability_manifest=availability,
                contracts_root=self.contracts,
                repository_root=self.repo,
                output_root=work / "bundle",
                adapter_mode=OFFICIAL_MODE,
                inventory_schema_path=self.schema,
            )
            self.assertEqual(result["candidate_count"], 15)
            self.assertEqual(result["sense_count"], 5)
            self.assertEqual(result["ready_candidate_count"], 0)
            self.assertEqual(result["not_submitted_count"], 15)
            self.assertEqual(result["availability_counts"]["MISSING"], 30)
            self.assertEqual(
                result["global_execution_status"], "HOLD_EVIDENCE_AVAILABILITY"
            )
            replay = replay_adapter_bundle(
                work / "bundle",
                contracts_root=self.contracts,
                repository_root=self.repo,
            )
            self.assertEqual(
                replay["semantic_replay"],
                "SEALED_ADAPTER_AVAILABILITY_HOLD_REPLAY_PASS",
            )
            self.assertEqual(replay["joined_count"], 0)
            self.assertEqual(replay["not_submitted_count"], 15)
            inventory = load_inventory(work / "bundle" / "artifact_inventory.json")
            with self.assertRaises(PolicyError):
                execute_run(
                    manifest_path=inventory.manifest_path,
                    authority_receipt=work / "missing-authority.json",
                    contracts_root=self.contracts,
                    output_dir=work / "forbidden-run",
                    run_id="forbidden-hold-run",
                    mode="FIXTURE_CONFORMANCE",
                )

    def test_external_hold_without_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            dataset = self._official_dataset()
            availability = write_missing_availability_manifest(
                work / "availability",
                candidates=dataset.candidates,
                adapter_mode=OFFICIAL_MODE,
                run_id="official-adapter-preflight",
                phase_id="zero-provider-preflight",
                split_id="official-five-sense",
                observed_at="2026-07-30T00:00:00Z",
                reason_code="PRODUCER_PACKAGE_SET_NOT_MAIN_ACCEPTED",
            )
            manifest = load_json(availability, require_object=True)
            manifest["rows"][0]["status"] = "EXTERNAL_HOLD"
            manifest["counts"]["MISSING"] -= 1
            manifest["counts"]["EXTERNAL_HOLD"] += 1
            manifest["integrity"]["self_sha256"] = self_sha256(manifest)
            availability.unlink()
            dump_json(availability, manifest)
            with self.assertRaises(ValidationError):
                build_adapter_bundle(
                    dataset_zip=dataset.zip_path,
                    dataset_pin=dataset.pin_path,
                    dataset_git_receipt=dataset.git_receipt_path,
                    availability_manifest=availability,
                    contracts_root=self.contracts,
                    repository_root=self.repo,
                    output_root=work / "blocked",
                    adapter_mode=OFFICIAL_MODE,
                    inventory_schema_path=self.schema,
                )
            self.assertFalse((work / "blocked").exists())

    def test_external_hold_and_invalid_are_sealed_but_never_joined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            dataset = self._official_dataset()
            availability = write_missing_availability_manifest(
                work / "availability",
                candidates=dataset.candidates,
                adapter_mode=OFFICIAL_MODE,
                run_id="official-adapter-preflight",
                phase_id="zero-provider-preflight",
                split_id="official-five-sense",
                observed_at="2026-07-30T00:00:00Z",
                reason_code="PRODUCER_PACKAGE_SET_NOT_MAIN_ACCEPTED",
            )
            manifest = load_json(availability, require_object=True)
            hold_row = manifest["rows"][0]
            hold_row["status"] = "EXTERNAL_HOLD"
            hold_row["reason_code"] = "EXTERNAL_ACQUISITION_STOP_RECEIPT"
            hold_row["external_hold_receipt"] = make_external_hold_authority(
                availability,
                candidate_key=hold_row["candidate_key"],
                role=hold_row["role"],
                run_id=manifest["run_id"],
                phase_id=manifest["phase_id"],
                split_id=manifest["split_id"],
                reason_code=hold_row["reason_code"],
                observed_at=hold_row["observed_at"],
            )
            invalid_row = manifest["rows"][3]
            invalid_row["status"] = "INVALID"
            invalid_row["reason_code"] = "REJECTED_EXISTING_ARTIFACT"
            invalid_row["validation_error_code"] = "IDENTITY_CANDIDATE_VERSION_MISMATCH"
            manifest["counts"]["MISSING"] -= 2
            manifest["counts"]["EXTERNAL_HOLD"] += 1
            manifest["counts"]["INVALID"] += 1
            manifest["integrity"]["self_sha256"] = self_sha256(manifest)
            availability.unlink()
            dump_json(availability, manifest)

            result = build_adapter_bundle(
                dataset_zip=dataset.zip_path,
                dataset_pin=dataset.pin_path,
                dataset_git_receipt=dataset.git_receipt_path,
                availability_manifest=availability,
                contracts_root=self.contracts,
                repository_root=self.repo,
                output_root=work / "bundle",
                adapter_mode=OFFICIAL_MODE,
                inventory_schema_path=self.schema,
            )
            self.assertEqual(result["ready_candidate_count"], 0)
            self.assertEqual(result["availability_counts"]["EXTERNAL_HOLD"], 1)
            self.assertEqual(result["availability_counts"]["INVALID"], 1)
            readiness = load_json(
                work / "bundle" / "sidecars" / "global_batch_readiness_report_v2.json",
                require_object=True,
            )
            self.assertEqual(readiness["counts"]["identity_rejected"], 1)
            self.assertEqual(readiness["counts"]["not_submitted"], 15)
            self.assertFalse((work / "bundle" / "packages").exists())
            replay = replay_adapter_bundle(
                work / "bundle",
                contracts_root=self.contracts,
                repository_root=self.repo,
            )
            self.assertEqual(replay["joined_count"], 0)
            self.assertEqual(
                replay["semantic_replay"],
                "SEALED_ADAPTER_AVAILABILITY_HOLD_REPLAY_PASS",
            )

    def test_synthetic_fifty_sense_inventory_joins_150_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source = make_synthetic_dataset_release(self.repo, work / "dataset")
            dataset = load_dataset_release(
                source["zip"],
                source["pin"],
                git_receipt_path=None,
                schema_root=self.contracts,
                mode=SYNTHETIC_MODE,
            )
            context = make_producer_set(
                self.repo,
                work / "context",
                candidates=dataset.candidates,
                role="context_evidence",
            )
            attestation = make_producer_set(
                self.repo,
                work / "attestation",
                candidates=dataset.candidates,
                role="attestation_evidence",
            )
            status_ids = [
                dataset.candidates[0].identity.candidate_id,
                dataset.candidates[1].identity.candidate_id,
            ]
            self._set_attestation_status(attestation, status_ids[0], "NOT_ATTESTED")
            self._set_attestation_status(
                attestation,
                status_ids[1],
                "ATTESTATION_UNJUDGEABLE",
            )
            availability = write_present_availability_manifest(
                work / "availability",
                candidates=dataset.candidates,
                adapter_mode=SYNTHETIC_MODE,
                context_set_manifest=context,
                attestation_set_manifest=attestation,
                schema_root=self.contracts,
                run_id="synthetic-50-150",
                phase_id="conformance",
                split_id="synthetic",
                observed_at="2026-07-30T00:00:00Z",
            )
            for name in ("bundle-a", "bundle-b"):
                build_adapter_bundle(
                    dataset_zip=source["zip"],
                    dataset_pin=source["pin"],
                    dataset_git_receipt=None,
                    availability_manifest=availability,
                    contracts_root=self.contracts,
                    repository_root=self.repo,
                    output_root=work / name,
                    adapter_mode=SYNTHETIC_MODE,
                    inventory_schema_path=self.schema,
                )
            inventory = load_inventory(work / "bundle-a" / "artifact_inventory.json")
            joined, report = validate_and_join(inventory, schema_root=self.contracts)
            self.assertEqual(len(joined), 150)
            self.assertEqual(report["joined_count"], 150)
            effective = [row for row in inventory.records if row.role == "effective_sense"]
            self.assertEqual(len(effective), 150)
            self.assertEqual(len({row.path for row in effective}), 50)
            self.assertEqual(self._tree_hashes(work / "bundle-a"), self._tree_hashes(work / "bundle-b"))
            replay = replay_adapter_bundle(work / "bundle-a", contracts_root=self.contracts)
            self.assertEqual(replay["semantic_replay"], "SEALED_ADAPTER_COMPLETE_REPLAY_PASS")
            self.assertEqual(replay["joined_count"], 150)
            availability_sidecar = load_json(
                work / "bundle-a" / "sidecars" / "evidence_availability_manifest_v2.json",
                require_object=True,
            )
            for candidate_id, expected_status in zip(
                status_ids,
                ("NOT_ATTESTED", "ATTESTATION_UNJUDGEABLE"),
                strict=True,
            ):
                row = next(
                    item
                    for item in availability_sidecar["rows"]
                    if item["candidate_key"]["candidate_id"] == candidate_id
                    and item["role"] == "attestation_evidence"
                )
                self.assertEqual(row["status"], "PRESENT")
                package = load_json(work / "bundle-a" / row["package"]["relative_path"], require_object=True)
                self.assertEqual(package["local_status"], expected_status)

    def test_missing_extra_and_inventory_drift_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source = make_synthetic_dataset_release(self.repo, work / "dataset")
            dataset = load_dataset_release(
                source["zip"], source["pin"], git_receipt_path=None,
                schema_root=self.contracts, mode=SYNTHETIC_MODE,
            )
            context = make_producer_set(
                self.repo, work / "context", candidates=dataset.candidates,
                role="context_evidence",
            )
            attestation = make_producer_set(
                self.repo, work / "attestation", candidates=dataset.candidates,
                role="attestation_evidence",
            )
            value = load_json(context, require_object=True)
            value["entries"] = value["entries"][:-1]
            value["entry_count"] -= 1
            value["package_count"] -= 1
            value["integrity"]["self_sha256"] = self_sha256(value)
            context.unlink()
            dump_json(context, value)
            with self.assertRaises(Exception):
                write_present_availability_manifest(
                    work / "missing",
                    candidates=dataset.candidates,
                    adapter_mode=SYNTHETIC_MODE,
                    context_set_manifest=context,
                    attestation_set_manifest=attestation,
                    schema_root=self.contracts,
                    run_id="missing-package",
                    phase_id="conformance",
                    split_id="synthetic",
                    observed_at="2026-07-30T00:00:00Z",
                )
            self.assertFalse((work / "missing").exists())

            hold = make_producer_set(
                self.repo,
                work / "fake-hold",
                candidates=dataset.candidates,
                role="context_evidence",
            )
            value = load_json(hold, require_object=True)
            value["entries"][0]["kind"] = "HOLD"
            value["package_count"] -= 1
            value["hold_count"] = 1
            value["integrity"]["self_sha256"] = self_sha256(value)
            hold.unlink()
            dump_json(hold, value)
            with self.assertRaises(ValidationError):
                write_present_availability_manifest(
                    work / "fake-hold-availability",
                    candidates=dataset.candidates,
                    adapter_mode=SYNTHETIC_MODE,
                    context_set_manifest=hold,
                    attestation_set_manifest=attestation,
                    schema_root=self.contracts,
                    run_id="fake-hold",
                    phase_id="conformance",
                    split_id="synthetic",
                    observed_at="2026-07-30T00:00:00Z",
                )

    def test_shared_sense_path_drift_and_inventory_reorder_reject(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            bundle = self._synthetic_bundle(work)
            manifest_path = bundle / "artifact_inventory.json"
            manifest = load_json(manifest_path, require_object=True)
            target = next(row for row in manifest["artifacts"] if row["role"] == "effective_sense")
            source = bundle / target["relative_path"]
            duplicate = source.with_name(source.stem + "-duplicate.json")
            duplicate.write_bytes(source.read_bytes())
            target["relative_path"] = duplicate.relative_to(bundle).as_posix()
            target["physical_sha256"] = sha256_file(duplicate)
            manifest["integrity"]["self_sha256"] = self_sha256(manifest)
            manifest_path.unlink()
            dump_json(manifest_path, manifest)
            self._reseal_checksums(bundle)
            with self.assertRaises(ReplayError):
                replay_adapter_bundle(bundle, contracts_root=self.contracts)

            bundle = self._synthetic_bundle(work, name="reorder")
            manifest_path = bundle / "artifact_inventory.json"
            manifest = load_json(manifest_path, require_object=True)
            manifest["artifacts"] = list(reversed(manifest["artifacts"]))
            manifest_path.unlink()
            dump_json(manifest_path, manifest)
            self._reseal_checksums(bundle)
            with self.assertRaises(IntegrityError):
                replay_adapter_bundle(bundle, contracts_root=self.contracts)

    def test_partial_ready_batch_excludes_missing_candidate_from_global_join(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source = make_synthetic_dataset_release(self.repo, work / "dataset")
            dataset = load_dataset_release(
                source["zip"],
                source["pin"],
                git_receipt_path=None,
                schema_root=self.contracts,
                mode=SYNTHETIC_MODE,
            )
            context = make_producer_set(
                self.repo,
                work / "context",
                candidates=dataset.candidates,
                role="context_evidence",
            )
            attestation = make_producer_set(
                self.repo,
                work / "attestation",
                candidates=dataset.candidates,
                role="attestation_evidence",
            )
            availability = write_present_availability_manifest(
                work / "availability",
                candidates=dataset.candidates,
                adapter_mode=SYNTHETIC_MODE,
                context_set_manifest=context,
                attestation_set_manifest=attestation,
                schema_root=self.contracts,
                run_id="synthetic-partial",
                phase_id="conformance",
                split_id="synthetic",
                observed_at="2026-07-30T00:00:00Z",
            )
            excluded_id = dataset.candidates[0].identity.candidate_id
            self._mark_candidate_missing(availability, excluded_id)
            result = build_adapter_bundle(
                dataset_zip=source["zip"],
                dataset_pin=source["pin"],
                dataset_git_receipt=None,
                availability_manifest=availability,
                contracts_root=self.contracts,
                repository_root=self.repo,
                output_root=work / "bundle",
                adapter_mode=SYNTHETIC_MODE,
                inventory_schema_path=self.schema,
            )
            self.assertEqual(result["ready_candidate_count"], 149)
            self.assertEqual(result["not_submitted_count"], 1)
            self.assertEqual(result["global_execution_status"], "READY_FOR_PUBLIC_GLOBAL_CLI")
            inventory = load_inventory(work / "bundle" / "artifact_inventory.json")
            self.assertNotIn(
                excluded_id,
                {
                    record.candidate_key["candidate_id"]
                    for record in inventory.records
                    if record.candidate_key is not None
                },
            )
            joined, report = validate_and_join(inventory, schema_root=self.contracts)
            self.assertEqual(len(joined), 149)
            self.assertEqual(report["joined_count"], 149)
            readiness = load_json(
                work / "bundle" / "sidecars" / "global_batch_readiness_report_v2.json",
                require_object=True,
            )
            self.assertEqual(readiness["not_submitted"][0]["candidate_id"], excluded_id)
            replay = replay_adapter_bundle(work / "bundle", contracts_root=self.contracts)
            self.assertEqual(replay["joined_count"], 149)
            self.assertEqual(
                replay["semantic_replay"],
                "SEALED_ADAPTER_AVAILABILITY_HOLD_REPLAY_PASS",
            )

    def test_reparse_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            bundle = self._synthetic_bundle(work)
            original = __import__("os").path.isjunction

            def fake_isjunction(path):
                return Path(path).name == "packages" or original(path)

            with mock.patch("integration_harness.paths.os.path.isjunction", side_effect=fake_isjunction):
                with self.assertRaises(IntegrityError):
                    load_inventory(bundle / "artifact_inventory.json")

    def test_coherently_resealed_sidecar_semantic_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            dataset = self._official_dataset()
            availability = write_missing_availability_manifest(
                work / "availability",
                candidates=dataset.candidates,
                adapter_mode=OFFICIAL_MODE,
                run_id="official-adapter-preflight",
                phase_id="zero-provider-preflight",
                split_id="official-five-sense",
                observed_at="2026-07-30T00:00:00Z",
                reason_code="PRODUCER_PACKAGE_SET_NOT_MAIN_ACCEPTED",
            )
            build_adapter_bundle(
                dataset_zip=dataset.zip_path,
                dataset_pin=dataset.pin_path,
                dataset_git_receipt=dataset.git_receipt_path,
                availability_manifest=availability,
                contracts_root=self.contracts,
                repository_root=self.repo,
                output_root=work / "bundle",
                adapter_mode=OFFICIAL_MODE,
                inventory_schema_path=self.schema,
            )
            authority_path = work / "bundle" / "sidecars" / "global_batch_authority_v2.json"
            authority = load_json(authority_path, require_object=True)
            authority["expected_sense_count"] = 50
            authority["integrity"]["self_sha256"] = self_sha256(authority)
            authority_path.unlink()
            dump_json(authority_path, authority)
            readiness_path = work / "bundle" / "sidecars" / "global_batch_readiness_report_v2.json"
            readiness = load_json(readiness_path, require_object=True)
            readiness["batch_authority"] = {
                "physical_sha256": sha256_file(authority_path),
                "self_sha256": authority["integrity"]["self_sha256"],
            }
            readiness["integrity"]["self_sha256"] = self_sha256(readiness)
            readiness_path.unlink()
            dump_json(readiness_path, readiness)
            inventory_path = work / "bundle" / "artifact_inventory.json"
            inventory = load_json(inventory_path, require_object=True)
            source = next(
                item
                for item in inventory["source_authority"]
                if item["role"] == "global_batch_authority"
            )
            source["physical_sha256"] = sha256_file(authority_path)
            source["declared_self_sha256"] = authority["integrity"]["self_sha256"]
            inventory["sidecar_bindings"]["global_batch_authority"]["physical_sha256"] = sha256_file(authority_path)
            inventory["sidecar_bindings"]["global_batch_authority"]["self_sha256"] = authority["integrity"]["self_sha256"]
            readiness_source = next(
                item
                for item in inventory["source_authority"]
                if item["role"] == "global_batch_readiness_report"
            )
            readiness_source["physical_sha256"] = sha256_file(readiness_path)
            readiness_source["declared_self_sha256"] = readiness["integrity"]["self_sha256"]
            inventory["sidecar_bindings"]["global_batch_readiness_report"]["physical_sha256"] = sha256_file(readiness_path)
            inventory["sidecar_bindings"]["global_batch_readiness_report"]["self_sha256"] = readiness["integrity"]["self_sha256"]
            inventory["integrity"]["self_sha256"] = self_sha256(inventory)
            inventory_path.unlink()
            dump_json(inventory_path, inventory)
            self._reseal_checksums(work / "bundle")
            with self.assertRaises(ReplayError):
                replay_adapter_bundle(
                    work / "bundle",
                    contracts_root=self.contracts,
                    repository_root=self.repo,
                )

    def test_synthetic_150_core_seal_and_replay_preserve_adapter_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            bundle = self._synthetic_bundle(work)
            authority = make_fixture_repo(self.repo, work / "authority", 1)
            adapter = FakePublicGlobalAdapter(self.repo, work / "authority")
            run_dir = execute_run(
                manifest_path=bundle / "artifact_inventory.json",
                authority_receipt=authority["authority"],
                contracts_root=self.contracts,
                action_policy=authority["action_policy"],
                output_dir=work / "run",
                run_id="synthetic-50-150-run",
                mode="FIXTURE_CONFORMANCE",
                adapter=adapter,
                repository_root=self.repo,
            )
            self.assertEqual(
                len(list((run_dir / "input" / "shared" / "effective_sense").glob("*.json"))),
                50,
            )
            replay = replay_run(
                run_dir,
                adapter=adapter,
                repository_root=self.repo,
                contracts_root=self.contracts,
            )
            self.assertEqual(replay["candidate_count"], 150)
            self.assertEqual(replay["semantic_replay"], "PUBLIC_CLI_REPLAY_PASS")

    def _synthetic_bundle(self, work: Path, *, name: str = "bundle") -> Path:
        source_root = work / f"dataset-{name}"
        source = make_synthetic_dataset_release(self.repo, source_root)
        dataset = load_dataset_release(
            source["zip"], source["pin"], git_receipt_path=None,
            schema_root=self.contracts, mode=SYNTHETIC_MODE,
        )
        context = make_producer_set(
            self.repo, work / f"context-{name}", candidates=dataset.candidates,
            role="context_evidence",
        )
        attestation = make_producer_set(
            self.repo, work / f"attestation-{name}", candidates=dataset.candidates,
            role="attestation_evidence",
        )
        availability = write_present_availability_manifest(
            work / f"availability-{name}",
            candidates=dataset.candidates,
            adapter_mode=SYNTHETIC_MODE,
            context_set_manifest=context,
            attestation_set_manifest=attestation,
            schema_root=self.contracts,
            run_id=f"synthetic-{name}",
            phase_id="conformance",
            split_id="synthetic",
            observed_at="2026-07-30T00:00:00Z",
        )
        bundle = work / name
        build_adapter_bundle(
            dataset_zip=source["zip"], dataset_pin=source["pin"],
            dataset_git_receipt=None, availability_manifest=availability,
            contracts_root=self.contracts,
            repository_root=self.repo, output_root=bundle,
            adapter_mode=SYNTHETIC_MODE, inventory_schema_path=self.schema,
        )
        return bundle

    @staticmethod
    def _set_attestation_status(
        manifest_path: Path,
        candidate_id: str,
        status: str,
    ) -> None:
        manifest = load_json(manifest_path, require_object=True)
        entry = next(item for item in manifest["entries"] if item["candidate_id"] == candidate_id)
        package_path = manifest_path.parent / entry["relative_path"]
        package = load_json(package_path, require_object=True)
        package["local_status"] = status
        package["integrity"]["self_sha256"] = self_sha256(package)
        package_path.unlink()
        dump_json(package_path, package)
        entry["physical_sha256"] = sha256_file(package_path)
        entry["self_sha256"] = package["integrity"]["self_sha256"]
        manifest["integrity"]["self_sha256"] = self_sha256(manifest)
        manifest_path.unlink()
        dump_json(manifest_path, manifest)

    @staticmethod
    def _mark_candidate_missing(manifest_path: Path, candidate_id: str) -> None:
        manifest = load_json(manifest_path, require_object=True)
        for binding in manifest["producer_sets"]:
            producer_path = manifest_path.parent / binding["relative_path"]
            producer = load_json(producer_path, require_object=True)
            entry = next(
                item for item in producer["entries"] if item["candidate_id"] == candidate_id
            )
            package_path = producer_path.parent / entry["relative_path"]
            package_path.unlink()
            producer["entries"] = [
                item for item in producer["entries"] if item["candidate_id"] != candidate_id
            ]
            producer["entry_count"] -= 1
            producer["package_count"] -= 1
            producer["integrity"]["self_sha256"] = self_sha256(producer)
            producer_path.unlink()
            dump_json(producer_path, producer)
            binding["physical_sha256"] = sha256_file(producer_path)
            binding["self_sha256"] = producer["integrity"]["self_sha256"]
        for row in manifest["rows"]:
            if row["candidate_key"]["candidate_id"] != candidate_id:
                continue
            row["status"] = "MISSING"
            row["reason_code"] = "PRODUCER_PACKAGE_NOT_AVAILABLE"
            row["validation_error_code"] = None
            row["external_hold_receipt"] = None
        manifest["counts"]["PRESENT"] -= 2
        manifest["counts"]["MISSING"] += 2
        manifest["integrity"]["self_sha256"] = self_sha256(manifest)
        manifest_path.unlink()
        dump_json(manifest_path, manifest)

    @staticmethod
    def _tree_hashes(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in root.rglob("*")
            if path.is_file()
        }

    @staticmethod
    def _reseal_checksums(root: Path) -> None:
        checksum = root / "CHECKSUMS.sha256"
        if checksum.exists():
            checksum.unlink()
        lines = [
            f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]
        checksum.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    unittest.main()
