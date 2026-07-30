from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from integration_harness.adapter_v1.availability import (
    HISTORICAL_REPLAY_MODE,
    load_availability_manifest,
    write_missing_availability_manifest,
    write_present_availability_manifest,
)
from integration_harness.adapter_v1.dataset import OFFICIAL_MODE, SYNTHETIC_MODE, load_dataset_release
from integration_harness.adapter_v1.producer import (
    LEGACY_PACKAGE_SET_SCHEMA,
    LEGACY_SCHEMA_VERSION,
    NEW_INPUT_MODE,
    load_producer_set,
)
from integration_harness.errors import PolicyError
from integration_harness.hashing import self_sha256
from integration_harness.hashing import sha256_file
from integration_harness.jsonio import dump_json, load_json
from integration_harness.adapter_v1.trust import load_trusted_authority_profile

from .adapter_helpers import (
    make_accepted_producer_set,
    make_producer_set,
    make_synthetic_dataset_release,
)
from .trust_helpers import make_trusted_profile


class TrustedBatchAuthorityV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path.cwd()
        self.contracts = self.repo / "terminology_contracts_v1"

    def test_legacy_availability_is_explicit_historical_replay_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = make_synthetic_dataset_release(
                self.repo, root / "dataset", candidate_count=3
            )
            dataset = load_dataset_release(
                source["zip"], source["pin"], git_receipt_path=None,
                schema_root=self.contracts, mode=SYNTHETIC_MODE,
            )
            path = write_missing_availability_manifest(
                root / "availability", candidates=dataset.candidates,
                adapter_mode=SYNTHETIC_MODE, run_id="historical-run",
                phase_id="historical-phase", split_id="historical-split",
                observed_at="2026-07-30T00:00:00Z", reason_code="HISTORICAL_MISSING",
            )
            value = load_json(path, require_object=True)
            value["schema_id"] = "HarnessEvidenceAvailabilityIntakeV1"
            value["schema_version"] = "1.0.0"
            value["integrity"]["self_sha256"] = self_sha256(value)
            path.unlink()
            dump_json(path, value)
            with self.assertRaises(PolicyError):
                load_availability_manifest(
                    path, candidates=dataset.candidates,
                    schema_root=self.contracts, adapter_mode=SYNTHETIC_MODE,
                    intake_mode=NEW_INPUT_MODE,
                )
            loaded = load_availability_manifest(
                path, candidates=dataset.candidates,
                schema_root=self.contracts, adapter_mode=SYNTHETIC_MODE,
                intake_mode=HISTORICAL_REPLAY_MODE,
            )
            self.assertEqual(len(loaded.items), 6)

    def test_legacy_producer_set_is_explicit_historical_replay_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = make_synthetic_dataset_release(
                self.repo, root / "dataset", candidate_count=3
            )
            dataset = load_dataset_release(
                source["zip"], source["pin"], git_receipt_path=None,
                schema_root=self.contracts, mode=SYNTHETIC_MODE,
            )
            manifest_path = make_producer_set(
                self.repo, root / "producer", candidates=dataset.candidates,
                role="context_evidence",
            )
            value = load_json(manifest_path, require_object=True)
            value["schema_id"] = LEGACY_PACKAGE_SET_SCHEMA
            value["schema_version"] = LEGACY_SCHEMA_VERSION
            value["producer"].pop("tree")
            value["accepted_source_binding"] = value.pop("source_manifest")
            value["integrity"]["self_sha256"] = self_sha256(value)
            manifest_path.unlink()
            dump_json(manifest_path, value)
            with self.assertRaises(PolicyError):
                load_producer_set(
                    manifest_path, role="context_evidence",
                    candidates=dataset.candidates, schema_root=self.contracts,
                    adapter_mode=SYNTHETIC_MODE, intake_mode=NEW_INPUT_MODE,
                )
            loaded = load_producer_set(
                manifest_path, role="context_evidence",
                candidates=dataset.candidates, schema_root=self.contracts,
                adapter_mode=SYNTHETIC_MODE,
                intake_mode=HISTORICAL_REPLAY_MODE,
            )
            self.assertEqual(len(loaded.items), 3)

    def test_official_present_cannot_self_authorize_without_main_profile(self) -> None:
        official_root = (
            self.repo / "review_evidence" / "dataset"
            / "d2l-stage-a-official-5-sense-pilot-v1"
        )
        dataset = load_dataset_release(
            official_root / "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip",
            official_root / "official_dataset_input_pin_v1.json",
            git_receipt_path=official_root / "git_source_receipt.json",
            schema_root=self.contracts, mode=OFFICIAL_MODE,
            repository_root=self.repo,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = make_accepted_producer_set(
                self.repo, root / "context", candidates=dataset.candidates,
                role="context_evidence", run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            attestation = make_accepted_producer_set(
                self.repo, root / "attestation", candidates=dataset.candidates,
                role="attestation_evidence", run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            with self.assertRaises(PolicyError):
                write_present_availability_manifest(
                    root / "rejected", candidates=dataset.candidates,
                    adapter_mode=OFFICIAL_MODE,
                    context_set_manifest=context["manifest"],
                    attestation_set_manifest=attestation["manifest"],
                    context_acceptance_receipt=context["receipt"],
                    attestation_acceptance_receipt=attestation["receipt"],
                    schema_root=self.contracts, run_id="RUN-D0",
                    phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
                    observed_at="2026-07-30T00:00:00Z",
                )

    def test_profile_path_escape_and_main_stop_tamper_fail_closed(self) -> None:
        official_root = (
            self.repo / "review_evidence" / "dataset"
            / "d2l-stage-a-official-5-sense-pilot-v1"
        )
        dataset = load_dataset_release(
            official_root / "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip",
            official_root / "official_dataset_input_pin_v1.json",
            git_receipt_path=official_root / "git_source_receipt.json",
            schema_root=self.contracts, mode=OFFICIAL_MODE,
            repository_root=self.repo,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = make_accepted_producer_set(
                self.repo, root / "context", candidates=dataset.candidates,
                role="context_evidence", run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            attestation = make_accepted_producer_set(
                self.repo, root / "attestation", candidates=dataset.candidates,
                role="attestation_evidence", run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            producers = {
                "context_evidence": context["authority"],
                "attestation_evidence": attestation["authority"],
            }
            profile = make_trusted_profile(
                self.repo, root / "profile-a", candidates=dataset.candidates,
                producers=producers, run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            value = load_json(profile["path"], require_object=True)
            value["protocol"]["schemas"][0]["relative_path"] = "../outside.json"
            value["integrity"]["self_sha256"] = self_sha256(value)
            profile["path"].unlink()
            dump_json(profile["path"], value)
            with self.assertRaises(Exception):
                load_trusted_authority_profile(
                    profile["path"], expected_physical_sha256=sha256_file(profile["path"]),
                    expected_self_sha256=value["integrity"]["self_sha256"],
                    expected_issuer_id=profile["issuer_id"],
                    expected_authority_id=profile["authority_id"],
                )

            profile = make_trusted_profile(
                self.repo, root / "profile-b", candidates=dataset.candidates,
                producers=producers, run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            event = load_json(profile["stop_event"], require_object=True)
            event["stop_reason"] = "COHERENTLY_RESEALED_FOREIGN_STOP"
            profile["stop_event"].unlink()
            dump_json(profile["stop_event"], event)
            with self.assertRaises(Exception):
                load_trusted_authority_profile(
                    profile["path"], expected_physical_sha256=profile["physical_sha256"],
                    expected_self_sha256=profile["self_sha256"],
                    expected_issuer_id=profile["issuer_id"],
                    expected_authority_id=profile["authority_id"],
                )

    def test_expired_authorization_and_run_start_drift_reject(self) -> None:
        official_root = (
            self.repo / "review_evidence" / "dataset"
            / "d2l-stage-a-official-5-sense-pilot-v1"
        )
        dataset = load_dataset_release(
            official_root / "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip",
            official_root / "official_dataset_input_pin_v1.json",
            git_receipt_path=official_root / "git_source_receipt.json",
            schema_root=self.contracts, mode=OFFICIAL_MODE,
            repository_root=self.repo,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = make_accepted_producer_set(
                self.repo, root / "context", candidates=dataset.candidates,
                role="context_evidence", run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            attestation = make_accepted_producer_set(
                self.repo, root / "attestation", candidates=dataset.candidates,
                role="attestation_evidence", run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            producers = {
                "context_evidence": context["authority"],
                "attestation_evidence": attestation["authority"],
            }
            with self.assertRaises(PolicyError):
                make_trusted_profile(
                    self.repo, root / "expired", candidates=dataset.candidates,
                    producers=producers, run_id="RUN-D0",
                    phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
                    valid_until="2026-01-01T00:00:00Z",
                )
            profile = make_trusted_profile(
                self.repo, root / "start-drift", candidates=dataset.candidates,
                producers=producers, run_id="RUN-D0",
                phase_id="D0_ONE_CANDIDATE", split_id="official-five-sense",
            )
            start = load_json(profile["run_start"], require_object=True)
            start["phase_authorized_candidate_set_self_sha256"] = "f" * 64
            start["integrity"]["self_sha256"] = self_sha256(start)
            profile["run_start"].unlink()
            dump_json(profile["run_start"], start)
            with self.assertRaises(Exception):
                load_trusted_authority_profile(
                    profile["path"], expected_physical_sha256=profile["physical_sha256"],
                    expected_self_sha256=profile["self_sha256"],
                    expected_issuer_id=profile["issuer_id"],
                    expected_authority_id=profile["authority_id"],
                )


if __name__ == "__main__":
    unittest.main()
