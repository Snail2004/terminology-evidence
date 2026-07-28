from __future__ import annotations

import json

import pytest

from conftest import (
    MIGRATED_V11,
    MIGRATION_REPORTS,
    SCHEMAS,
    VALID_V10,
    load_json,
    validate_payload,
)
from terminology_contracts.integrity import canonical_sha256
from terminology_contracts.migration import MigrationError, migrate_v1_0_to_v1_1
from terminology_contracts.validation import validate_instance


def test_every_valid_v10_fixture_migrates_deterministically() -> None:
    for path in sorted(VALID_V10.glob("*.json")):
        source = load_json(path)
        first = migrate_v1_0_to_v1_1(source)
        second = migrate_v1_0_to_v1_1(source)
        assert first == second, path.name
        assert first.payload["schema_version"] == "1.1.0"
        assert first.report["source_sha256"] == canonical_sha256(source)
        assert first.report["target_sha256"] == canonical_sha256(first.payload)
        assert validate_payload(
            first.payload,
            calibration_path=None,
            allow_legacy_migration=True,
        ) == [], path.name
        if "candidate_key" in source:
            assert first.payload["candidate_key"] == source["candidate_key"]


def test_checked_in_migration_reports_bind_exact_outputs() -> None:
    for target in sorted(MIGRATED_V11.glob("*.json")):
        report = load_json(MIGRATION_REPORTS / f"{target.stem}.migration.json")
        assert report["target_sha256"] == canonical_sha256(load_json(target))


def test_second_migration_is_explicitly_rejected() -> None:
    migrated = migrate_v1_0_to_v1_1(
        load_json(VALID_V10 / "context_evidence_package.json")
    ).payload
    with pytest.raises(MigrationError, match="already V1.1"):
        migrate_v1_0_to_v1_1(migrated)


def test_migrated_calibration_preserves_model_but_is_not_frozen_eligible() -> None:
    source = load_json(VALID_V10 / "calibration_artifact.json")
    migrated = migrate_v1_0_to_v1_1(source).payload
    assert migrated["model"] == source["model"]
    assert migrated["verification_status"] == "UNVERIFIED_LEGACY"
    errors = validate_instance(migrated, SCHEMAS)
    assert any("not eligible" in error for error in errors)


def test_legacy_incomplete_certificate_is_not_natively_issuable() -> None:
    migrated = migrate_v1_0_to_v1_1(
        load_json(VALID_V10 / "terminology_certificate.json")
    ).payload
    errors = validate_instance(migrated, SCHEMAS)
    assert any("legacy-incomplete certificate cannot be issued" in error for error in errors)
