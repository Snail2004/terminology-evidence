import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.constants import STATUS_CONFORMANCE_ONLY
from evaluation.v1.jsonio import sha256_file, sha256_value, write_json
from evaluation.v1.release_tools.builder import (
    RELEASE_SCHEMA_ID,
    RELEASE_SCHEMA_VERSION,
    ReleaseBuildError,
    _file_inventory,
    _write_checksums,
    verify_release,
)
from evaluation.v1.release_tools.junit import identity_set_sha256, normalized_junit_bytes


class ReleaseVerificationTests(unittest.TestCase):
    @staticmethod
    def _write_release(root: Path) -> None:
        identities = ["tests.evaluation.test_example.ExampleTests.test_green"]
        expected_tests = {
            "schema_id": "EvaluationExpectedTestManifestV1",
            "schema_version": "1.0.0",
            "manifest_id": "evaluation-ar2-test-authority-v1",
            "runner": "pytest",
            "identity_format": "JUNIT_CLASSNAME_DOT_NAME",
            "test_count": 1,
            "testcase_identities": identities,
            "testcase_identity_sha256": identity_set_sha256(identities),
            "integrity": {"self_sha256": ""},
        }
        unsigned_tests = dict(expected_tests)
        unsigned_tests["integrity"] = {}
        expected_tests["integrity"]["self_sha256"] = sha256_value(unsigned_tests)
        write_json(root / "expected_test_manifest_v1.json", expected_tests)
        junit_report = {
            "tests": 1,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "testcase_identities": identities,
            "testcase_identity_sha256": identity_set_sha256(identities),
            "physical_sha256": "0" * 64,
        }
        (root / "junit.xml").write_bytes(normalized_junit_bytes(junit_report))
        (root / "payload.txt").write_text("sealed\n", encoding="ascii", newline="\n")
        files = _file_inventory(root)
        manifest = {
            "schema_id": RELEASE_SCHEMA_ID,
            "schema_version": RELEASE_SCHEMA_VERSION,
            "status": STATUS_CONFORMANCE_ONLY,
            "source_commit": "1" * 40,
            "source_tree_git_oid": "2" * 40,
            "source_tree_sha256": "3" * 64,
            "source_file_count": 1,
            "release_mode": "DETACHED_OBJECT",
            "junit": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            "external_junit": None,
            "expected_test_manifest_sha256": sha256_file(root / "expected_test_manifest_v1.json"),
            "registry_counts": {"metrics": 1},
            "network_calls": 0,
            "provider_calls": 0,
            "files": files,
            "integrity": {"self_sha256": ""},
        }
        unsigned_manifest = dict(manifest)
        unsigned_manifest["integrity"] = {}
        manifest["integrity"]["self_sha256"] = sha256_value(unsigned_manifest)
        write_json(root / "release_manifest.json", manifest)
        _write_checksums(root)

    @staticmethod
    def _reseal_manifest(root: Path, mutate) -> None:
        import json

        path = root / "release_manifest.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        mutate(value)
        value["integrity"]["self_sha256"] = ""
        unsigned = dict(value)
        unsigned["integrity"] = {}
        value["integrity"]["self_sha256"] = sha256_value(unsigned)
        write_json(path, value)

    def test_exact_release_passes_and_extra_file_rejects(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self._write_release(root)
            self.assertEqual(verify_release(root)["status"], STATUS_CONFORMANCE_ONLY)
            (root / "unsealed.txt").write_text("extra", encoding="ascii")
            with self.assertRaises(ReleaseBuildError):
                verify_release(root)

    def test_noncanonical_and_case_confusable_inventory_paths_reject(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self._write_release(root)
            self._reseal_manifest(root, lambda value: value["files"][0].update(path="folder\\alias.json"))
            with self.assertRaises(ReleaseBuildError):
                verify_release(root)

        with TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self._write_release(root)

            def duplicate_casefold(value):
                duplicate = dict(value["files"][0])
                duplicate["path"] = duplicate["path"].upper()
                value["files"].append(duplicate)

            self._reseal_manifest(root, duplicate_casefold)
            with self.assertRaises(ReleaseBuildError):
                verify_release(root)
