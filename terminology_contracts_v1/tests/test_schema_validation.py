from __future__ import annotations

import json

from conftest import INVALID_V11, ROOT, SCHEMAS, VALID_V10, VALID_V11
from terminology_contracts.manifest import build_manifest, verify_manifest, write_manifest
from terminology_contracts.registries import SCHEMA_FILES
from terminology_contracts.validation import validate_file
from terminology_contracts.validation import validate_instance

ACTIVE_SCHEMA_DIR = SCHEMAS / "v1.1.0"


def test_all_native_v11_examples_validate() -> None:
    for path in sorted(VALID_V11.glob("*.json")):
        assert validate_file(path, SCHEMAS) == [], path.name


def test_all_legacy_v10_examples_remain_byte_compatible() -> None:
    for path in sorted(VALID_V10.glob("*.json")):
        assert validate_file(path, SCHEMAS, allow_legacy_migration=True) == [], path.name


def test_legacy_decision_does_not_require_v11_feature_registry() -> None:
    payload = json.loads(
        (VALID_V10 / "global_decision_package.json").read_text(encoding="utf-8")
    )
    errors = validate_instance(
        payload,
        SCHEMAS,
        calibration_path=VALID_V10 / "calibration_artifact.json",
        feature_registry_path=None,
        allow_legacy_migration=True,
    )
    assert errors == []


def test_all_invalid_v11_examples_reject() -> None:
    for path in sorted(INVALID_V11.glob("*.json")):
        assert validate_file(path, SCHEMAS), path.name


def test_current_schema_alias_is_byte_identical() -> None:
    for filename in SCHEMA_FILES.values():
        assert (SCHEMAS / "current" / filename).read_bytes() == (
            ACTIVE_SCHEMA_DIR / filename
        ).read_bytes()


def test_canonical_serialized_names_are_locked() -> None:
    calibration = json.loads(
        (ACTIVE_SCHEMA_DIR / "calibration_artifact.schema.json").read_text(
            encoding="utf-8"
        )
    )
    certificate = json.loads(
        (ACTIVE_SCHEMA_DIR / "terminology_certificate.schema.json").read_text(
            encoding="utf-8"
        )
    )
    gate = json.loads(
        (ACTIVE_SCHEMA_DIR / "gate_result_set.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert "feature_contract_version" in calibration["properties"]
    assert "feature_registry_version" not in calibration["properties"]
    assert "validity_context_refs" in certificate["properties"]
    assert "attestation_evidence_refs" in certificate["properties"]
    assert "support_context_refs" not in certificate["properties"]
    observation = gate["properties"]["observations"]["items"]
    assert "action" in observation["properties"]
    assert "severity" not in observation["properties"]


def test_package_manifest_is_complete() -> None:
    assert verify_manifest(ROOT) == []


def test_package_manifest_excludes_tool_caches(tmp_path) -> None:
    (tmp_path / "payload.txt").write_text("contract\n", encoding="utf-8")
    for cache_name in (".pytest_cache", ".mypy_cache", ".ruff_cache"):
        cache_file = tmp_path / cache_name / "state.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text("{}\n", encoding="utf-8")

    manifest = build_manifest(tmp_path)
    write_manifest(tmp_path, manifest)

    paths = {record["path"] for record in manifest["files"]}
    assert paths == {"payload.txt"}
    assert verify_manifest(tmp_path) == []
