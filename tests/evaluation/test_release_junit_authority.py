import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.jsonio import sha256_bytes, sha256_value, write_json
from evaluation.v1.release_tools.junit import (
    JUnitAuthorityError,
    normalized_junit_bytes,
    load_expected_test_manifest,
    identity_set_sha256,
    verify_junit,
)


class ReleaseJUnitAuthorityTests(unittest.TestCase):
    @staticmethod
    def _manifest(path: Path, identities):
        value = {
            "schema_id": "EvaluationExpectedTestManifestV1",
            "schema_version": "1.0.0",
            "manifest_id": "evaluation-ar2-test-authority-v1",
            "runner": "pytest",
            "identity_format": "JUNIT_CLASSNAME_DOT_NAME",
            "test_count": len(identities),
            "testcase_identities": sorted(identities),
            "testcase_identity_sha256": identity_set_sha256(identities),
            "integrity": {"self_sha256": ""},
        }
        unsigned = dict(value)
        unsigned["integrity"] = {}
        value["integrity"]["self_sha256"] = sha256_value(unsigned)
        write_json(path, value)

    @staticmethod
    def _junit(path: Path, identities, *, failures=0, errors=0, skipped=0):
        suite = ET.Element("testsuite", {"tests": str(len(identities)), "failures": str(failures), "errors": str(errors), "skipped": str(skipped)})
        for index, identifier in enumerate(identities):
            classname, _, name = identifier.rpartition(".")
            case = ET.SubElement(suite, "testcase", {"classname": classname, "name": name})
            if index == 0 and failures:
                ET.SubElement(case, "failure")
            if index == 0 and errors:
                ET.SubElement(case, "error")
            if index == 0 and skipped:
                ET.SubElement(case, "skipped")
        path.write_bytes(ET.tostring(suite, encoding="utf-8"))

    def test_exact_green_junit_passes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            identities = ["test_module.Case.test_a", "test_module.Case.test_b"]
            self._manifest(root / "manifest.json", identities)
            self._junit(root / "junit.xml", identities)
            report = verify_junit(root / "junit.xml", expected_manifest_path=root / "manifest.json")
            self.assertEqual(report["tests"], 2)
            second = root / "junit-with-timing.xml"
            self._junit(second, identities)
            tree = ET.parse(second)
            tree.getroot().set("time", "9.999")
            tree.write(second, encoding="utf-8")
            timed = verify_junit(second, expected_manifest_path=root / "manifest.json")
            self.assertNotEqual(report["physical_sha256"], timed["physical_sha256"])
            self.assertEqual(
                sha256_bytes(normalized_junit_bytes(report)),
                sha256_bytes(normalized_junit_bytes(timed)),
            )

    def test_red_skipped_empty_and_unrelated_junit_reject(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            identities = ["test_module.Case.test_a"]
            self._manifest(root / "manifest.json", identities)
            for name, kwargs in (
                ("failure", {"failures": 1}),
                ("error", {"errors": 1}),
                ("skip", {"skipped": 1}),
            ):
                path = root / f"{name}.xml"
                self._junit(path, identities, **kwargs)
                with self.assertRaises(JUnitAuthorityError):
                    verify_junit(path, expected_manifest_path=root / "manifest.json")
            empty = root / "empty.xml"
            self._junit(empty, [])
            with self.assertRaises(JUnitAuthorityError):
                verify_junit(empty, expected_manifest_path=root / "manifest.json")
            unrelated = root / "unrelated.xml"
            self._junit(unrelated, ["other.Case.test_x"])
            with self.assertRaises(JUnitAuthorityError):
                verify_junit(unrelated, expected_manifest_path=root / "manifest.json")

    def test_manifest_tamper_rejects(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            self._manifest(path, ["test_module.Case.test_a"])
            value = __import__("json").loads(path.read_text(encoding="utf-8"))
            value["test_count"] = 2
            write_json(path, value)
            with self.assertRaises(JUnitAuthorityError):
                load_expected_test_manifest(path)
