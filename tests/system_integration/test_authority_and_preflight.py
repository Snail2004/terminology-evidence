from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from integration_harness.authority import SYNTHETIC_LOCAL_CONFORMANCE, resolve_authority
from integration_harness.errors import AuthorityError, PolicyError
from integration_harness.inventory import load_inventory
from integration_harness.join import validate_and_join
from integration_harness.preflight import validate_preflight
from integration_harness.jsonio import dump_json, load_json

from .helpers import make_fixture_repo


class AuthorityPreflightTests(unittest.TestCase):
    def test_authority_is_pinned_to_contract_and_action_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = make_fixture_repo(Path.cwd(), Path(directory), 1)
            authority = resolve_authority(
                fixture["authority"], fixture["contracts"], action_policy_path=fixture["action_policy"],
                action_policy_authority_path=fixture["action_policy_authority"],
                repository_root=Path.cwd(),
                authority_mode=SYNTHETIC_LOCAL_CONFORMANCE,
                expected={"authority_tag": "contracts-v1.1.0", "contract_version": "1.1.0"},
            )
            self.assertEqual(authority.authority_tag, "contracts-v1.1.0")
            receipt = load_json(fixture["authority"], require_object=True)
            receipt["authority_tag"] = "wrong"
            fixture["authority"].unlink()
            dump_json(fixture["authority"], receipt)
            with self.assertRaises(AuthorityError):
                resolve_authority(
                    fixture["authority"],
                    fixture["contracts"],
                    action_policy_path=fixture["action_policy"],
                    action_policy_authority_path=fixture["action_policy_authority"],
                    repository_root=Path.cwd(),
                    authority_mode=SYNTHETIC_LOCAL_CONFORMANCE,
                    expected={"authority_tag": "contracts-v1.1.0"},
                )

    def test_preflight_requires_supported_development_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = make_fixture_repo(Path.cwd(), Path(directory), 1)
            joined, _ = validate_and_join(load_inventory(fixture["manifest"]), schema_root=fixture["contracts"])
            authority = resolve_authority(
                fixture["authority"],
                fixture["contracts"],
                action_policy_path=fixture["action_policy"],
                action_policy_authority_path=fixture["action_policy_authority"],
                repository_root=Path.cwd(),
                authority_mode=SYNTHETIC_LOCAL_CONFORMANCE,
            )
            report = validate_preflight(
                joined, mode="FIXTURE_CONFORMANCE", authority=authority
            )
            self.assertEqual(report["development_invariants"]["auto_approved_count"], 0)
            with self.assertRaises(PolicyError):
                validate_preflight(
                    joined, mode="FROZEN_CALIBRATED", authority=authority
                )
