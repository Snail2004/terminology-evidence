from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from integration_harness.errors import DiscoveryError, JoinError
from integration_harness.hashing import self_sha256, sha256_file
from integration_harness.inventory import load_inventory
from integration_harness.join import validate_and_join
from integration_harness.jsonio import dump_json, load_json

from .helpers import make_fixture_repo


class InventoryJoinTests(unittest.TestCase):
    def test_fifteen_candidates_join_by_complete_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            fixture = make_fixture_repo(root, Path(directory), 15)
            inventory = load_inventory(fixture["manifest"])
            joined, report = validate_and_join(inventory, schema_root=fixture["contracts"])
            self.assertEqual(len(inventory.records), 76)
            self.assertEqual(len(joined), 15)
            self.assertEqual(report["joined_count"], 15)

    def test_missing_role_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            fixture = make_fixture_repo(root, Path(directory), 1)
            manifest = load_json(fixture["manifest"], require_object=True)
            manifest["artifacts"] = [item for item in manifest["artifacts"] if item["role"] != "context_evidence"]
            manifest["integrity"]["self_sha256"] = self_sha256(manifest)
            fixture["manifest"].unlink()
            dump_json(fixture["manifest"], manifest)
            inventory = load_inventory(fixture["manifest"])
            with self.assertRaises(JoinError):
                validate_and_join(inventory, schema_root=fixture["contracts"])

    def test_identity_mismatch_fails_after_physical_reseal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            fixture = make_fixture_repo(root, Path(directory), 1)
            manifest = load_json(fixture["manifest"], require_object=True)
            frozen = next(item for item in manifest["artifacts"] if item["role"] == "frozen_candidate")
            path = fixture["manifest"].parent / frozen["relative_path"]
            value = load_json(path, require_object=True)
            value["candidate_key"]["candidate_id"] = "foreign-candidate"
            value["integrity"]["self_sha256"] = self_sha256(value)
            path.unlink()
            dump_json(path, value)
            frozen["physical_sha256"] = sha256_file(path)
            frozen["declared_self_sha256"] = value["integrity"]["self_sha256"]
            manifest["integrity"]["self_sha256"] = self_sha256(manifest)
            fixture["manifest"].unlink()
            dump_json(fixture["manifest"], manifest)
            inventory = load_inventory(fixture["manifest"])
            with self.assertRaises(JoinError):
                validate_and_join(inventory, schema_root=fixture["contracts"])

    def test_duplicate_physical_path_is_rejected_by_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path.cwd()
            fixture = make_fixture_repo(root, Path(directory), 1)
            manifest = load_json(fixture["manifest"], require_object=True)
            manifest["artifacts"].append(copy.deepcopy(manifest["artifacts"][0]))
            manifest["integrity"]["self_sha256"] = self_sha256(manifest)
            fixture["manifest"].unlink()
            dump_json(fixture["manifest"], manifest)
            with self.assertRaises(DiscoveryError):
                load_inventory(fixture["manifest"])
