import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.constants import STATUS_CONFORMANCE_ONLY
from evaluation.v1.jsonio import read_json, sha256_file, sha256_value, write_json
from evaluation.v1.registries.loader import REGISTRY_FILES, load_registries, registry_counts
from evaluation.v1.release_tools.builder import (
    RELEASE_CHECKSUM_FILE,
    RELEASE_SCHEMA_ID,
    RELEASE_SCHEMA_VERSION,
    ReleaseBuildError,
    _file_inventory,
    _write_checksums,
    verify_release,
)
from evaluation.v1.release_tools.junit import identity_set_sha256, normalized_junit_bytes
from evaluation.v1.release_tools.git_source import SOURCE_ROOTS, read_source_zip, source_tree_sha256, write_source_zip


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
        entries = [
            ("docs/evaluation/README.md", b"# Evaluation\n"),
            ("evaluation/v1/authority/expected_test_manifest_v1.json", (root / "expected_test_manifest_v1.json").read_bytes()),
            ("evaluation/v1/module.py", b"VALUE = 1\n"),
            ("tests/evaluation/test_module.py", b"def test_value():\n    assert 1 == 1\n"),
        ]
        registry_root = Path(__file__).parents[2] / "evaluation" / "v1" / "registries"
        entries.extend(
            (f"evaluation/v1/registries/{name}", (registry_root / name).read_bytes())
            for name in REGISTRY_FILES
        )
        entries.sort()
        write_source_zip(entries, root / "evaluation_preregistration_source.zip")
        source_hash = source_tree_sha256(entries)
        write_json(
            root / "git_source_receipt.json",
            {
                "schema_id": "EvaluationGitSourceReceiptV1",
                "schema_version": "1.0.0",
                "source_commit": "1" * 40,
                "source_tree_git_oid": "2" * 40,
                "source_tree_sha256": source_hash,
                "source_file_count": len(entries),
                "release_mode": "DETACHED_OBJECT",
            },
        )
        write_json(
            root / "ownership_scan.json",
            {"status": "PASS", "allowed_roots": list(SOURCE_ROOTS), "source_files": len(entries)},
        )
        write_json(root / "static_scan.json", {"status": "PASS", "forbidden_imports": []})
        write_json(root / "credential_scan.json", {"status": "PASS", "credential_literals": []})
        write_json(
            root / "commands.json",
            {"test": "python -B -m pytest -q tests/evaluation", "release": "python -B -m evaluation.v1.tools.build_release", "network_calls": 0},
        )
        write_json(
            root / "environment.json",
            {"python": "3.test", "platform": "test", "source_commit": "1" * 40, "network_calls": 0, "provider_calls": 0},
        )
        (root / "payload.txt").write_text("sealed\n", encoding="ascii", newline="\n")
        report = root / "synthetic" / "report"
        report.mkdir(parents=True)
        (report / "EVALUATION_REPORT.md").write_text("# Report\n", encoding="ascii", newline="\n")
        (report / "bootstrap_summary.json").write_text("{}\n", encoding="ascii", newline="\n")
        files = _file_inventory(root)
        manifest = {
            "schema_id": RELEASE_SCHEMA_ID,
            "schema_version": RELEASE_SCHEMA_VERSION,
            "status": STATUS_CONFORMANCE_ONLY,
            "source_commit": "1" * 40,
            "source_tree_git_oid": "2" * 40,
            "source_tree_sha256": source_hash,
            "source_file_count": len(entries),
            "release_mode": "DETACHED_OBJECT",
            "junit": {
                "tests": 1,
                "failures": 0,
                "errors": 0,
                "skipped": 0,
                "testcase_identity_sha256": identity_set_sha256(identities),
                "physical_sha256": sha256_file(root / "junit.xml"),
            },
            "external_junit": None,
            "expected_test_manifest_sha256": sha256_file(root / "expected_test_manifest_v1.json"),
            "registry_counts": registry_counts(load_registries(registry_root)),
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
    def _reseal_release(root: Path, mutate=None) -> None:
        path = root / "release_manifest.json"
        value = read_json(path)
        value["files"] = _file_inventory(root)
        if mutate is not None:
            mutate(value)
        value["integrity"]["self_sha256"] = ""
        unsigned = dict(value)
        unsigned["integrity"] = {}
        value["integrity"]["self_sha256"] = sha256_value(unsigned)
        write_json(path, value)
        _write_checksums(root)

    def test_exact_release_passes_and_extra_file_rejects(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self._write_release(root)
            self.assertEqual(verify_release(root)["status"], STATUS_CONFORMANCE_ONLY)
            (root / "unsealed.txt").write_text("extra", encoding="ascii")
            with self.assertRaises(ReleaseBuildError):
                verify_release(root)

        manifest_mutations = [
            lambda value: value.update(schema_id="ForgedReleaseManifest"),
            lambda value: value.update(schema_version="9.9.9"),
            lambda value: value.update(status="PASS"),
            lambda value: value.update(source_commit="3" * 40),
            lambda value: value.update(source_tree_git_oid="4" * 40),
            lambda value: value.update(source_tree_sha256="5" * 64),
            lambda value: value.update(source_file_count=value["source_file_count"] + 1),
            lambda value: value.update(release_mode="UNREVIEWED"),
            lambda value: value["junit"].update(tests=value["junit"]["tests"] + 1),
            lambda value: value["junit"].update(failures=1),
            lambda value: value["junit"].update(errors=1),
            lambda value: value["junit"].update(skipped=1),
            lambda value: value["junit"].update(testcase_identity_sha256="6" * 64),
            lambda value: value["junit"].update(physical_sha256="7" * 64),
            lambda value: value.update(external_junit=dict(value["junit"])),
            lambda value: value.update(expected_test_manifest_sha256="8" * 64),
            lambda value: value["registry_counts"].update(metrics=value["registry_counts"]["metrics"] + 1),
            lambda value: value.update(network_calls=1),
            lambda value: value.update(provider_calls=1),
        ]
        for mutation in manifest_mutations:
            with TemporaryDirectory() as temp:
                root = Path(temp) / "release"
                root.mkdir()
                self._write_release(root)
                self._reseal_release(root, mutation)
                with self.assertRaises(ReleaseBuildError):
                    verify_release(root)

        with TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self._write_release(root)
            git_receipt = read_json(root / "git_source_receipt.json")
            git_receipt["source_commit"] = "9" * 40
            write_json(root / "git_source_receipt.json", git_receipt)
            self._reseal_release(root)
            with self.assertRaises(ReleaseBuildError):
                verify_release(root)

        with TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self._write_release(root)
            entries = read_source_zip(root / "evaluation_preregistration_source.zip")
            first_path, first_data = entries[0]
            entries[0] = (first_path, first_data + b"drift")
            write_source_zip(entries, root / "evaluation_preregistration_source.zip")
            self._reseal_release(root)
            with self.assertRaises(ReleaseBuildError):
                verify_release(root)

        with TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self._write_release(root)
            (root / "expected_test_manifest_v1.json").write_bytes(
                (root / "expected_test_manifest_v1.json").read_bytes() + b"\n"
            )
            self._reseal_release(
                root,
                lambda value: value.update(
                    expected_test_manifest_sha256=sha256_file(root / "expected_test_manifest_v1.json")
                ),
            )
            with self.assertRaises(ReleaseBuildError):
                verify_release(root)

        evidence_mutations = {
            "ownership_scan.json": lambda value: value.update(source_files=value["source_files"] + 1),
            "static_scan.json": lambda value: value.update(forbidden_imports=["evaluation/v1/module.py"]),
            "credential_scan.json": lambda value: value.update(credential_literals=["evaluation/v1/module.py"]),
            "commands.json": lambda value: value.update(network_calls=1),
            "environment.json": lambda value: value.update(provider_calls=1),
        }
        for relative, mutation in evidence_mutations.items():
            with TemporaryDirectory() as temp:
                root = Path(temp) / "release"
                root.mkdir()
                self._write_release(root)
                evidence = read_json(root / relative)
                mutation(evidence)
                write_json(root / relative, evidence)
                self._reseal_release(root)
                with self.assertRaises(ReleaseBuildError):
                    verify_release(root)

    def test_noncanonical_and_case_confusable_inventory_paths_reject(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "release"
            root.mkdir()
            self._write_release(root)
            self._reseal_release(root, lambda value: value["files"][0].update(path="folder\\alias.json"))
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

            self._reseal_release(root, duplicate_casefold)
            with self.assertRaises(ReleaseBuildError):
                verify_release(root)
