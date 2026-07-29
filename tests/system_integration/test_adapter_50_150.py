from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from integration_harness.adapter_v1.build import build_adapter_bundle
from integration_harness.adapter_v1.dataset import (
    OFFICIAL_MODE,
    SYNTHETIC_MODE,
    load_dataset_release,
)
from integration_harness.adapter_v1.replay import replay_adapter_bundle
from integration_harness.errors import IntegrityError, PolicyError, ReplayError
from integration_harness.hashing import self_sha256, sha256_file
from integration_harness.inventory import load_inventory
from integration_harness.join import validate_and_join
from integration_harness.jsonio import dump_json, load_json
from integration_harness.pipeline import execute_run
from integration_harness.replay import replay_run

from .adapter_helpers import make_producer_set, make_synthetic_dataset_release
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

    def test_official_fifteen_candidate_hold_preflight_replays(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            dataset = self._official_dataset()
            context = make_producer_set(
                self.repo,
                work / "context",
                candidates=dataset.candidates,
                role="context_evidence",
                hold=True,
            )
            attestation = make_producer_set(
                self.repo,
                work / "attestation",
                candidates=dataset.candidates,
                role="attestation_evidence",
                hold=True,
            )
            result = build_adapter_bundle(
                dataset_zip=dataset.zip_path,
                dataset_pin=dataset.pin_path,
                dataset_git_receipt=dataset.git_receipt_path,
                context_set_manifest=context,
                attestation_set_manifest=attestation,
                contracts_root=self.contracts,
                repository_root=self.repo,
                output_root=work / "bundle",
                adapter_mode=OFFICIAL_MODE,
                allowed_hold_roles=frozenset(
                    {"context_evidence", "attestation_evidence"}
                ),
                inventory_schema_path=self.schema,
            )
            self.assertEqual(result["candidate_count"], 15)
            self.assertEqual(result["sense_count"], 5)
            self.assertEqual(result["hold_count"], 30)
            self.assertEqual(
                result["global_execution_status"], "HOLD_EXPLICIT_PRODUCER_PACKAGE"
            )
            replay = replay_adapter_bundle(
                work / "bundle",
                contracts_root=self.contracts,
                repository_root=self.repo,
            )
            self.assertEqual(replay["semantic_replay"], "SEALED_ADAPTER_HOLD_REPLAY_PASS")
            self.assertEqual(replay["joined_count"], 15)
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

    def test_explicit_attestation_hold_requires_role_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            dataset = self._official_dataset()
            context = make_producer_set(
                self.repo,
                work / "context",
                candidates=dataset.candidates,
                role="context_evidence",
                hold=True,
            )
            attestation = make_producer_set(
                self.repo,
                work / "attestation",
                candidates=dataset.candidates,
                role="attestation_evidence",
                hold=True,
            )
            with self.assertRaises(PolicyError):
                build_adapter_bundle(
                    dataset_zip=dataset.zip_path,
                    dataset_pin=dataset.pin_path,
                    dataset_git_receipt=dataset.git_receipt_path,
                    context_set_manifest=context,
                    attestation_set_manifest=attestation,
                    contracts_root=self.contracts,
                    repository_root=self.repo,
                    output_root=work / "blocked",
                    adapter_mode=OFFICIAL_MODE,
                    allowed_hold_roles=frozenset({"context_evidence"}),
                    inventory_schema_path=self.schema,
                )
            self.assertFalse((work / "blocked").exists())

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
                hold=False,
            )
            attestation = make_producer_set(
                self.repo,
                work / "attestation",
                candidates=dataset.candidates,
                role="attestation_evidence",
                hold=False,
            )
            for name in ("bundle-a", "bundle-b"):
                build_adapter_bundle(
                    dataset_zip=source["zip"],
                    dataset_pin=source["pin"],
                    dataset_git_receipt=None,
                    context_set_manifest=context,
                    attestation_set_manifest=attestation,
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
                role="context_evidence", hold=False,
            )
            attestation = make_producer_set(
                self.repo, work / "attestation", candidates=dataset.candidates,
                role="attestation_evidence", hold=False,
            )
            value = load_json(context, require_object=True)
            value["entries"] = value["entries"][:-1]
            value["entry_count"] -= 1
            value["package_count"] -= 1
            value["integrity"]["self_sha256"] = self_sha256(value)
            context.unlink()
            dump_json(context, value)
            with self.assertRaises(Exception):
                build_adapter_bundle(
                    dataset_zip=source["zip"], dataset_pin=source["pin"],
                    dataset_git_receipt=None, context_set_manifest=context,
                    attestation_set_manifest=attestation, contracts_root=self.contracts,
                    repository_root=self.repo, output_root=work / "missing",
                    adapter_mode=SYNTHETIC_MODE, inventory_schema_path=self.schema,
                )
            self.assertFalse((work / "missing").exists())

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
            role="context_evidence", hold=False,
        )
        attestation = make_producer_set(
            self.repo, work / f"attestation-{name}", candidates=dataset.candidates,
            role="attestation_evidence", hold=False,
        )
        bundle = work / name
        build_adapter_bundle(
            dataset_zip=source["zip"], dataset_pin=source["pin"],
            dataset_git_receipt=None, context_set_manifest=context,
            attestation_set_manifest=attestation, contracts_root=self.contracts,
            repository_root=self.repo, output_root=bundle,
            adapter_mode=SYNTHETIC_MODE, inventory_schema_path=self.schema,
        )
        return bundle

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
