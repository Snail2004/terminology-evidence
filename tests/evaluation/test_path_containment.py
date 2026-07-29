import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.v1.artifacts.authority import (
    AuthorityError,
    canonical_manifest_path,
    secure_existing_file,
    verify_manifest,
)
from evaluation.v1.jsonio import sha256_file, write_json


class PathContainmentTests(unittest.TestCase):
    def test_noncanonical_paths_reject(self):
        bad = [
            "a\\b.json",
            "C:/a.json",
            "//server/share.json",
            "/absolute.json",
            "a/../b.json",
            "a/./b.json",
            "a//b.json",
            "a:/b.json",
            "a/",
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(AuthorityError):
                canonical_manifest_path(value)

    def test_valid_manifest_and_casefold_duplicate(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            root.mkdir()
            target = root / "Artifact.json"
            target.write_text("value", encoding="utf-8")
            valid = Path(temp) / "valid.json"
            write_json(valid, {"files": [{"path": "Artifact.json", "sha256": sha256_file(target)}]})
            self.assertEqual(verify_manifest(root, valid)["files"][0]["path"], "Artifact.json")
            duplicate = Path(temp) / "duplicate.json"
            write_json(duplicate, {"files": [
                {"path": "Artifact.json", "sha256": sha256_file(target)},
                {"path": "artifact.json", "sha256": sha256_file(target)},
            ]})
            with self.assertRaises(AuthorityError):
                verify_manifest(root, duplicate)

    def test_intermediate_symlink_rejects(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            target = outside / "value.json"
            target.write_text("value", encoding="utf-8")
            link = root / "linked"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            manifest = base / "manifest.json"
            write_json(manifest, {"files": [{"path": "linked/value.json", "sha256": sha256_file(target)}]})
            with self.assertRaises(AuthorityError):
                verify_manifest(root, manifest)
            with self.assertRaises(AuthorityError):
                secure_existing_file(link / "value.json", trusted_root=root, field="linked authority")

            if os.name == "nt":
                junction = root / "junction"
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if created.returncode == 0:
                    try:
                        with self.assertRaises(AuthorityError):
                            secure_existing_file(junction / "value.json", trusted_root=root, field="junction authority")
                    finally:
                        os.rmdir(junction)
