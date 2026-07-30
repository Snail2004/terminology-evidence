from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    sha256_file,
    strict_json_object,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.build_switch_replacement import (
    build_switch_replacement,
)
from dataset.d2l_dataset_remaining_100_stage_a_v1.tools.validate_switch_replacement import (
    validate_artifact,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = PACKAGE_ROOT / "release"
DATASET_ROOT = PACKAGE_ROOT.parent
V3_ROOT = DATASET_ROOT / "d2l_context_support_set_validation_ready_v3"
FINAL_CLOSURE_ROOT = RELEASE_ROOT / "d2l_remaining100_final_closure_v1"
ARTIFACT_ROOT = RELEASE_ROOT / "d2l_switch_replacement_hypothesis_testing_v1"
ZIP_PATH = RELEASE_ROOT / "d2l_switch_replacement_hypothesis_testing_v1.zip"
DIRECT_ARTIFACT_ROOT = Path(
    r"C:\work\agent-based-translation-d2l-direct-builder-v1\jobs\_work\d2l_campaign\src_d2l_full_book_local_b858af3a5252\run_8c7d39cf1ab2\component\artifacts"
)
GLOSSARY_JSON = DIRECT_ARTIFACT_ROOT / "glossary_seal" / "glossary.json"
B2_DECISIONS_JSON = (
    DIRECT_ARTIFACT_ROOT / "b2_admission_translation" / "decisions.json"
)


class SwitchReplacementTests(unittest.TestCase):
    def _build(
        self, output: Path, zip_path: Path, glossary_json: Path = GLOSSARY_JSON
    ) -> None:
        build_switch_replacement(
            v3_root=V3_ROOT,
            final_closure_root=FINAL_CLOSURE_ROOT,
            glossary_json=glossary_json,
            b2_decisions_json=B2_DECISIONS_JSON,
            output_root=output,
            zip_path=zip_path,
        )

    def test_release_validates(self) -> None:
        self.assertEqual(validate_artifact(ARTIFACT_ROOT), [])

    def test_exact_replacement_counts(self) -> None:
        source = strict_json_object(ARTIFACT_ROOT / "replacement_source.json")
        self.assertEqual(source["source_term"], "hypothesis testing")
        self.assertEqual(len(source["candidates"]), 3)
        self.assertEqual(len(source["evidence_contexts"]), 7)
        self.assertEqual(
            sum(row["context_role"] == "PRIMARY" for row in source["evidence_contexts"]),
            5,
        )
        self.assertTrue(
            all(
                row["synthetic"] is False
                and row["positive_evidence_eligible"] is True
                for row in source["evidence_contexts"]
            )
        )

    def test_reviewer_packs_are_distinct_and_blind(self) -> None:
        hashes: set[str] = set()
        for role in ("reviewer_1", "reviewer_2"):
            path = ARTIFACT_ROOT / "handoff" / f"switch_replacement_{role}.zip"
            hashes.add(sha256_file(path))
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                self.assertEqual(names, {"INSTRUCTIONS.md", "reviewer_input.json"})
                payload = json.loads(archive.read("reviewer_input.json"))
                self.assertEqual(payload["reviewer_slot"], role)
                self.assertNotIn(
                    "candidate_origin",
                    json.dumps(payload, ensure_ascii=False),
                )
        self.assertEqual(len(hashes), 2)

    def test_rebuild_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="switch-replacement-rebuild-") as name:
            output = Path(name) / "artifact"
            zip_path = Path(name) / "artifact.zip"
            self._build(output, zip_path)
            self.assertEqual(validate_artifact(output), [])
            self.assertEqual(sha256_file(zip_path), sha256_file(ZIP_PATH))

    def test_wrong_glossary_record_rejects_without_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="switch-replacement-source-") as name:
            temp = Path(name)
            glossary = temp / "glossary.json"
            shutil.copyfile(GLOSSARY_JSON, glossary)
            payload = strict_json_object(glossary)
            record = next(
                row
                for row in payload["records"]
                if row["record_id"] == "d2lce_bad32719ece6439b4716d093"
            )
            record["value"]["canonical_source"] = "changed"
            glossary.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            output = temp / "artifact"
            with self.assertRaises(ValueError):
                self._build(output, temp / "artifact.zip", glossary_json=glossary)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
