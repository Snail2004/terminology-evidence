from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from integration_harness.adapter_v1.availability import (
    write_missing_availability_manifest,
    write_present_availability_manifest,
)
from integration_harness.adapter_v1.build import build_adapter_bundle
from integration_harness.adapter_v1.dataset import OFFICIAL_MODE, load_dataset_release
from integration_harness.adapter_v1.replay import replay_adapter_bundle
from integration_harness.errors import IntegrityError, ValidationError
from integration_harness.hashing import self_sha256, sha256_file
from integration_harness.jsonio import dump_json, load_json

from .adapter_helpers import make_accepted_producer_set, make_external_hold_authority


class BatchAuthorityHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path.cwd()
        self.contracts = self.repo / "terminology_contracts_v1"
        root = self.repo / "review_evidence" / "dataset" / "d2l-stage-a-official-5-sense-pilot-v1"
        self.dataset = load_dataset_release(
            root / "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip",
            root / "official_dataset_input_pin_v1.json",
            git_receipt_path=root / "git_source_receipt.json",
            schema_root=self.contracts,
            mode=OFFICIAL_MODE,
            repository_root=self.repo,
        )

    def _accepted_input(self, work: Path):
        context = make_accepted_producer_set(
            self.repo,
            work / "context",
            candidates=self.dataset.candidates,
            role="context_evidence",
            run_id="official-run",
            phase_id="official-phase",
            split_id="official-split",
        )
        attestation = make_accepted_producer_set(
            self.repo,
            work / "attestation",
            candidates=self.dataset.candidates,
            role="attestation_evidence",
            run_id="official-run",
            phase_id="official-phase",
            split_id="official-split",
        )
        availability = write_present_availability_manifest(
            work / "availability",
            candidates=self.dataset.candidates,
            adapter_mode=OFFICIAL_MODE,
            context_set_manifest=context["manifest"],
            attestation_set_manifest=attestation["manifest"],
            context_acceptance_receipt=context["receipt"],
            attestation_acceptance_receipt=attestation["receipt"],
            schema_root=self.contracts,
            run_id="official-run",
            phase_id="official-phase",
            split_id="official-split",
            observed_at="2026-07-30T00:00:00Z",
        )
        return context, attestation, availability

    def test_typed_official_acceptance_reaches_present_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            _, _, availability = self._accepted_input(work)
            result = build_adapter_bundle(
                dataset_zip=self.dataset.zip_path,
                dataset_pin=self.dataset.pin_path,
                dataset_git_receipt=self.dataset.git_receipt_path,
                availability_manifest=availability,
                contracts_root=self.contracts,
                repository_root=self.repo,
                output_root=work / "bundle",
                adapter_mode=OFFICIAL_MODE,
                inventory_schema_path=self.repo / "docs/integration/artifact_inventory_exact_cohort_v2.schema.json",
            )
            self.assertEqual(result["ready_candidate_count"], 15)
            self.assertEqual(result["availability_counts"]["PRESENT"], 30)
            replay = replay_adapter_bundle(work / "bundle", contracts_root=self.contracts, repository_root=self.repo)
            self.assertEqual(replay["joined_count"], 15)
            self.assertEqual(replay["semantic_replay"], "SEALED_ADAPTER_COMPLETE_REPLAY_PASS")

    def test_arbitrary_self_hashed_acceptance_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            context, attestation, _ = self._accepted_input(work)
            fake = {"schema_id": "AnythingSelfHashedV1", "status": "NOT_ACCEPTED", "integrity": {}}
            fake["integrity"]["self_sha256"] = self_sha256(fake)
            context["receipt"].unlink()
            dump_json(context["receipt"], fake)
            with self.assertRaises(ValidationError):
                write_present_availability_manifest(
                    work / "rejected",
                    candidates=self.dataset.candidates,
                    adapter_mode=OFFICIAL_MODE,
                    context_set_manifest=context["manifest"],
                    attestation_set_manifest=attestation["manifest"],
                    context_acceptance_receipt=context["receipt"],
                    attestation_acceptance_receipt=attestation["receipt"],
                    schema_root=self.contracts,
                    run_id="official-run",
                    phase_id="official-phase",
                    split_id="official-split",
                    observed_at="2026-07-30T00:00:00Z",
                )
            self.assertFalse((work / "rejected").exists())

    def test_acceptance_manifest_drift_is_rejected_before_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            context, attestation, _ = self._accepted_input(work)
            manifest = load_json(context["manifest"], require_object=True)
            manifest["producer"]["tree"] = "9" * 40
            manifest["integrity"]["self_sha256"] = self_sha256(manifest)
            context["manifest"].unlink()
            dump_json(context["manifest"], manifest)
            with self.assertRaises(Exception):
                write_present_availability_manifest(
                    work / "rejected",
                    candidates=self.dataset.candidates,
                    adapter_mode=OFFICIAL_MODE,
                    context_set_manifest=context["manifest"],
                    attestation_set_manifest=attestation["manifest"],
                    context_acceptance_receipt=context["receipt"],
                    attestation_acceptance_receipt=attestation["receipt"],
                    schema_root=self.contracts,
                    run_id="official-run",
                    phase_id="official-phase",
                    split_id="official-split",
                    observed_at="2026-07-30T00:00:00Z",
                )

    def test_acceptance_status_role_run_and_cohort_drift_fail_closed(self) -> None:
        mutations = {
            "status": lambda value: value.__setitem__("status", "NOT_ACCEPTED"),
            "role": lambda value: value.__setitem__("producer_role", "attestation_evidence"),
            "run": lambda value: value.__setitem__("run_id", "foreign-run"),
            "candidate_count": lambda value: value.__setitem__("candidate_count", 14),
            "candidate_set": lambda value: value.__setitem__("candidate_set_sha256", "0" * 64),
            "manifest_hash": lambda value: value["package_set_manifest"].__setitem__(
                "physical_sha256", "0" * 64
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            context, attestation, _ = self._accepted_input(work)
            original = load_json(context["receipt"], require_object=True)
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    changed = copy.deepcopy(original)
                    mutate(changed)
                    changed["integrity"]["self_sha256"] = self_sha256(changed)
                    context["receipt"].unlink()
                    dump_json(context["receipt"], changed)
                    with self.assertRaises(Exception):
                        write_present_availability_manifest(
                            work / f"rejected-{name}",
                            candidates=self.dataset.candidates,
                            adapter_mode=OFFICIAL_MODE,
                            context_set_manifest=context["manifest"],
                            attestation_set_manifest=attestation["manifest"],
                            context_acceptance_receipt=context["receipt"],
                            attestation_acceptance_receipt=attestation["receipt"],
                            schema_root=self.contracts,
                            run_id="official-run",
                            phase_id="official-phase",
                            split_id="official-split",
                            observed_at="2026-07-30T00:00:00Z",
                        )
                    context["receipt"].unlink()
                    dump_json(context["receipt"], original)

    def test_external_hold_requires_authoritative_stop_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            availability = write_missing_availability_manifest(
                work / "availability",
                candidates=self.dataset.candidates,
                adapter_mode=OFFICIAL_MODE,
                run_id="hold-run",
                phase_id="hold-phase",
                split_id="hold-split",
                observed_at="2026-07-30T00:00:00Z",
                reason_code="EXTERNAL_ACQUISITION_STOP_RECEIPT",
            )
            manifest = load_json(availability, require_object=True)
            row = manifest["rows"][0]
            held_candidate_id = row["candidate_key"]["candidate_id"]
            held_role = row["role"]
            row["status"] = "EXTERNAL_HOLD"
            row["reason_code"] = "EXTERNAL_ACQUISITION_STOP_RECEIPT"
            row["external_hold_receipt"] = make_external_hold_authority(
                availability,
                candidate_key=row["candidate_key"],
                role=row["role"],
                run_id=manifest["run_id"],
                phase_id=manifest["phase_id"],
                split_id=manifest["split_id"],
                reason_code=row["reason_code"],
                observed_at=row["observed_at"],
            )
            manifest["counts"]["MISSING"] -= 1
            manifest["counts"]["EXTERNAL_HOLD"] += 1
            manifest["integrity"]["self_sha256"] = self_sha256(manifest)
            availability.unlink()
            dump_json(availability, manifest)
            result = build_adapter_bundle(
                dataset_zip=self.dataset.zip_path,
                dataset_pin=self.dataset.pin_path,
                dataset_git_receipt=self.dataset.git_receipt_path,
                availability_manifest=availability,
                contracts_root=self.contracts,
                repository_root=self.repo,
                output_root=work / "bundle",
                adapter_mode=OFFICIAL_MODE,
                inventory_schema_path=self.repo / "docs/integration/artifact_inventory_exact_cohort_v2.schema.json",
            )
            self.assertEqual(result["availability_counts"]["EXTERNAL_HOLD"], 1)
            self.assertEqual(replay_adapter_bundle(work / "bundle", contracts_root=self.contracts, repository_root=self.repo)["joined_count"], 0)

            stop = work / "bundle" / "source_authority" / "availability_receipts" / held_role / held_candidate_id / "stop_event.json"
            value = load_json(stop, require_object=True)
            value["reason_code"] = "TAMPERED_STOP"
            value["integrity"]["self_sha256"] = self_sha256(value)
            stop.unlink()
            dump_json(stop, value)
            with self.assertRaises(Exception):
                replay_adapter_bundle(work / "bundle", contracts_root=self.contracts, repository_root=self.repo)

    def test_external_hold_rejects_coherently_resealed_non_stop_and_revoked_authority(self) -> None:
        for drift in ("stop_status", "authorization_status"):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                availability = write_missing_availability_manifest(
                    work / "availability",
                    candidates=self.dataset.candidates,
                    adapter_mode=OFFICIAL_MODE,
                    run_id="hold-run",
                    phase_id="hold-phase",
                    split_id="hold-split",
                    observed_at="2026-07-30T00:00:00Z",
                    reason_code="EXTERNAL_ACQUISITION_STOP_RECEIPT",
                )
                manifest = load_json(availability, require_object=True)
                row = manifest["rows"][0]
                row["status"] = "EXTERNAL_HOLD"
                row["reason_code"] = "EXTERNAL_ACQUISITION_STOP_RECEIPT"
                row["external_hold_receipt"] = make_external_hold_authority(
                    availability,
                    candidate_key=row["candidate_key"],
                    role=row["role"],
                    run_id=manifest["run_id"],
                    phase_id=manifest["phase_id"],
                    split_id=manifest["split_id"],
                    reason_code=row["reason_code"],
                    observed_at=row["observed_at"],
                )
                root = availability.parent / "external_stop"
                authorization_path = root / "authorization.json"
                stop_path = root / "stop_event.json"
                receipt_path = root / "hold_receipt.json"
                authorization = load_json(authorization_path, require_object=True)
                stop = load_json(stop_path, require_object=True)
                receipt = load_json(receipt_path, require_object=True)
                if drift == "stop_status":
                    stop["status"] = "RUNNING"
                else:
                    authorization["status"] = "REVOKED"
                    authorization["integrity"]["self_sha256"] = self_sha256(authorization)
                    authorization_path.unlink()
                    dump_json(authorization_path, authorization)
                    binding = {
                        "relative_path": "authorization.json",
                        "physical_sha256": sha256_file(authorization_path),
                        "self_sha256": authorization["integrity"]["self_sha256"],
                    }
                    stop["authorization_receipt"] = binding
                    receipt["authorization_receipt"] = binding
                stop["integrity"]["self_sha256"] = self_sha256(stop)
                stop_path.unlink()
                dump_json(stop_path, stop)
                receipt["stop_event"] = {
                    "relative_path": "stop_event.json",
                    "physical_sha256": sha256_file(stop_path),
                    "self_sha256": stop["integrity"]["self_sha256"],
                }
                receipt["integrity"]["self_sha256"] = self_sha256(receipt)
                receipt_path.unlink()
                dump_json(receipt_path, receipt)
                row["external_hold_receipt"] = {
                    "relative_path": "external_stop/hold_receipt.json",
                    "physical_sha256": sha256_file(receipt_path),
                    "self_sha256": receipt["integrity"]["self_sha256"],
                }
                manifest["counts"]["MISSING"] -= 1
                manifest["counts"]["EXTERNAL_HOLD"] += 1
                manifest["integrity"]["self_sha256"] = self_sha256(manifest)
                availability.unlink()
                dump_json(availability, manifest)
                with self.assertRaises(ValidationError):
                    build_adapter_bundle(
                        dataset_zip=self.dataset.zip_path,
                        dataset_pin=self.dataset.pin_path,
                        dataset_git_receipt=self.dataset.git_receipt_path,
                        availability_manifest=availability,
                        contracts_root=self.contracts,
                        repository_root=self.repo,
                        output_root=work / "rejected",
                        adapter_mode=OFFICIAL_MODE,
                        inventory_schema_path=self.repo / "docs/integration/artifact_inventory_exact_cohort_v2.schema.json",
                    )
