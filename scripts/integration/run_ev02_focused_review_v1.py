"""Run the EV-02 focused gate from self-contained reviewer dependencies."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from integration_harness.adapter_v1.producer_safe import (
    EVALUATION_EV02_PRODUCER_HANDOFF_ZIP_SHA256,
    PRODUCER_SAFE_MANIFEST_PHYSICAL_SHA256,
    PRODUCER_SAFE_PUBLICATION_RECEIPT_PHYSICAL_SHA256,
    PRODUCER_SAFE_ZIP_SHA256,
)
from integration_harness.errors import IntegrityError, ValidationError
from integration_harness.hashing import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-package-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    package_root = args.review_package_root.resolve()
    repo_root = args.repo_root.resolve()

    release_root = package_root / "dependencies/dataset/release"
    dataset_zip = release_root / "pipeline_input_50_150_producer_safe_v1.zip"
    publication = release_root / "pipeline_input_50_150_producer_safe_v1_publication_receipt.json"
    manifest = (
        release_root
        / "pipeline_input_50_150_producer_safe_v1/pipeline_input_50_150_manifest.json"
    )
    handoff = (
        package_root
        / "dependencies/evaluation/EV02_D0_BLIND_COHORT_PRODUCER_HANDOFF_7de0eca_V1.zip"
    )
    expected = {
        dataset_zip: PRODUCER_SAFE_ZIP_SHA256,
        publication: PRODUCER_SAFE_PUBLICATION_RECEIPT_PHYSICAL_SHA256,
        manifest: PRODUCER_SAFE_MANIFEST_PHYSICAL_SHA256,
        handoff: EVALUATION_EV02_PRODUCER_HANDOFF_ZIP_SHA256,
    }
    for path, digest in expected.items():
        if not path.is_file() or sha256_file(path) != digest:
            raise IntegrityError(f"focused review dependency mismatch: {path}")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repo_root)
    environment["HARNESS_PRODUCER_SAFE_RELEASE_ROOT"] = str(release_root)
    environment["HARNESS_EVALUATION_EV02_PRODUCER_HANDOFF_ZIP"] = str(handoff)
    with tempfile.TemporaryDirectory() as directory:
        junit = Path(directory) / "focused.junit.xml"
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "tests/system_integration/test_producer_safe_cohorts.py",
            "tests/system_integration/test_d0_review_package.py",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit}",
        ]
        result = subprocess.run(
            command,
            cwd=repo_root,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode != 0:
            return result.returncode
        suite = ET.parse(junit).getroot().find("testsuite")
        if suite is None:
            raise ValidationError("focused review JUnit has no testsuite")
        observed = {
            field: int(suite.attrib.get(field, "0"))
            for field in ("tests", "failures", "errors", "skipped")
        }
        if observed != {"tests": 18, "failures": 0, "errors": 0, "skipped": 0}:
            raise ValidationError(f"focused review JUnit identity drift: {observed}")
    print("FOCUSED_REVIEW=9_TESTS_9_SUBTESTS_0_SKIPS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
