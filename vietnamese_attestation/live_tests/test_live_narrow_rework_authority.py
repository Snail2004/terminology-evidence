from __future__ import annotations

import copy
import json
import zipfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from vietnamese_attestation.v1.live.authority_adapter.adapter import (
    EXTERNAL_RECEIPT_ROLES,
    PROTOCOL_SCHEMA_ROLES,
    load_authority_bundle,
    make_external_authority_receipt,
    make_trusted_authority_profile,
)
from vietnamese_attestation.v1.live.common import (
    LiveSchemaError,
    canonical_bytes,
    canonical_sha256,
    file_sha256,
    load_object,
    seal,
)
from vietnamese_attestation.v1.live.fixtures import build_fixture_workspace
from vietnamese_attestation.v1.live.schema_tools import SCHEMA_CATALOG
from vietnamese_attestation.v1.live.snapshot import (
    build_snapshot,
    verify_snapshot,
    zip_snapshot,
)


def test_external_authority_adapter_binds_exact_bytes_and_trust(tmp_path: Path) -> None:
    fixture = _authority_fixture(tmp_path / "authority", production=True)
    bundle = load_authority_bundle(
        profile_path=fixture["profile_path"],
        receipt_paths=fixture["receipt_paths"],
        protocol_schema_paths=fixture["schema_paths"],
        execution_mode="PRODUCTION_AUTHORITY",
        expected_profile_physical_sha256=file_sha256(fixture["profile_path"]),
    )
    assert bundle["execution_mode"] == "PRODUCTION_AUTHORITY"
    assert set(bundle["receipt_bindings"]) == set(EXTERNAL_RECEIPT_ROLES)
    assert set(bundle["protocol_schema_bindings"]) == set(PROTOCOL_SCHEMA_ROLES)

    fixture["receipt_paths"]["POLICY_APPROVAL"].write_bytes(
        fixture["receipt_paths"]["POLICY_APPROVAL"].read_bytes() + b"\n"
    )
    with pytest.raises(LiveSchemaError, match="physical hash mismatch"):
        load_authority_bundle(
            profile_path=fixture["profile_path"],
            receipt_paths=fixture["receipt_paths"],
            protocol_schema_paths=fixture["schema_paths"],
            execution_mode="PRODUCTION_AUTHORITY",
            expected_profile_physical_sha256=file_sha256(fixture["profile_path"]),
        )


def test_draft_authority_cannot_be_promoted_to_production(tmp_path: Path) -> None:
    fixture = _authority_fixture(tmp_path / "authority", production=False)
    assert load_authority_bundle(
        profile_path=fixture["profile_path"],
        receipt_paths=fixture["receipt_paths"],
        protocol_schema_paths=fixture["schema_paths"],
        execution_mode="LOCAL_FIXTURE_ONLY",
    )["execution_mode"] == "LOCAL_FIXTURE_ONLY"
    with pytest.raises(LiveSchemaError, match="forbidden in production"):
        load_authority_bundle(
            profile_path=fixture["profile_path"],
            receipt_paths=fixture["receipt_paths"],
            protocol_schema_paths=fixture["schema_paths"],
            execution_mode="PRODUCTION_AUTHORITY",
            expected_profile_physical_sha256=file_sha256(fixture["profile_path"]),
        )


def test_snapshot_preserves_original_receipt_and_external_authority_bytes(
    tmp_path: Path,
) -> None:
    workspace = build_fixture_workspace(tmp_path / "base")
    fixture = _authority_fixture(tmp_path / "authority", production=False)
    bundle = load_authority_bundle(
        profile_path=fixture["profile_path"],
        receipt_paths=fixture["receipt_paths"],
        protocol_schema_paths=fixture["schema_paths"],
        execution_mode="LOCAL_FIXTURE_ONLY",
    )
    receipt = load_object(workspace["snapshot_root"] / "acquisition_receipt.json")
    original_path = tmp_path / "acquisition.pretty.json"
    original_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    snapshot_root = tmp_path / "snapshot-with-authority"
    manifest = build_snapshot(
        workspace["source_root"],
        snapshot_root,
        registry=workspace["registry"],
        retrieval_policy=workspace["policy_bundle"]["retrieval_policy"],
        acquisition_receipt=receipt,
        acquisition_receipt_source=original_path,
        authority_bundle=bundle,
        authority_receipt_paths=fixture["receipt_paths"],
        authority_profile_path=fixture["profile_path"],
    )
    assert (
        snapshot_root / "authority" / "acquisition_receipt.original.json"
    ).read_bytes() == original_path.read_bytes()
    for role, source in fixture["receipt_paths"].items():
        copied = snapshot_root / "authority" / "receipts" / f"{role.casefold()}.json"
        assert copied.read_bytes() == source.read_bytes()
    verified = verify_snapshot(snapshot_root)
    assert verified["integrity"]["self_sha256"] == manifest["integrity"]["self_sha256"]
    assert verified["authority_binding"]["mode"] == "LOCAL_FIXTURE_ONLY"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda manifest: manifest["documents"][0].__setitem__("extra", True),
        lambda manifest: manifest["documents"][0]["registry_admission"].__setitem__(
            "extra", True
        ),
        lambda manifest: manifest["producer"].__setitem__("extra", True),
    ],
)
def test_snapshot_nested_extra_fields_fail_after_reseal(
    tmp_path: Path, mutator
) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    manifest_path = workspace["snapshot_root"] / "snapshot_manifest.json"
    manifest = copy.deepcopy(load_object(manifest_path))
    mutator(manifest)
    manifest_path.write_bytes(canonical_bytes(seal(manifest)))
    with pytest.raises(LiveSchemaError, match="unsupported keys"):
        verify_snapshot(workspace["snapshot_root"])


def test_snapshot_zip_has_canonical_order_and_fixed_metadata(tmp_path: Path) -> None:
    first = build_fixture_workspace(tmp_path / "first")
    second = build_fixture_workspace(tmp_path / "second")
    first_zip = zip_snapshot(first["snapshot_root"], tmp_path / "first.zip")
    second_zip = zip_snapshot(second["snapshot_root"], tmp_path / "second.zip")
    assert first_zip.read_bytes() == second_zip.read_bytes()
    with zipfile.ZipFile(first_zip) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        for info in archive.infolist():
            assert info.create_system == 0
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.extra == b""
            assert info.comment == b""

    reversed_zip = tmp_path / "reversed.zip"
    with zipfile.ZipFile(first_zip) as source, zipfile.ZipFile(
        reversed_zip, "w", compression=zipfile.ZIP_STORED
    ) as target:
        for source_info in reversed(source.infolist()):
            info = zipfile.ZipInfo(source_info.filename, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            target.writestr(info, source.read(source_info))
    with pytest.raises(LiveSchemaError, match="canonical POSIX order"):
        verify_snapshot(reversed_zip)


def test_all_exported_schemas_are_draft_2020_12_valid() -> None:
    for schema in SCHEMA_CATALOG.values():
        Draft202012Validator.check_schema(schema)


def _authority_fixture(root: Path, *, production: bool) -> dict[str, object]:
    root.mkdir(parents=True)
    receipt_status = "MAIN_PINNED_APPROVED" if production else "DRAFT_FIXTURE_ONLY"
    profile_status = (
        "MAIN_PINNED_RUNTIME_AUTHORITY" if production else "DRAFT_FIXTURE_ONLY"
    )
    issuer = "main-maintainer"
    authority = "terminology-evidence-main"
    receipt_paths: dict[str, Path] = {}
    receipt_bindings = []
    for role in sorted(EXTERNAL_RECEIPT_ROLES):
        receipt = make_external_authority_receipt(
            receipt_id=f"receipt-{role.casefold()}",
            role=role,
            issuer_id=issuer,
            authority_id=authority,
            subject_self_sha256=canonical_sha256({"role": role, "kind": "self"}),
            subject_physical_sha256=canonical_sha256(
                {"role": role, "kind": "physical"}
            ),
            status=receipt_status,
        )
        path = root / f"{role.casefold()}.json"
        path.write_bytes(canonical_bytes(receipt))
        receipt_paths[role] = path
        receipt_bindings.append(
            {
                "role": role,
                "artifact_ref": path.name,
                "artifact_physical_sha256": file_sha256(path),
                "artifact_self_sha256": receipt["integrity"]["self_sha256"],
            }
        )

    schema_paths: dict[str, Path] = {}
    protocol_bindings = []
    for role in sorted(PROTOCOL_SCHEMA_ROLES):
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://example.invalid/e/{role.casefold()}.schema.json",
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_id"],
            "properties": {"schema_id": {"type": "string"}},
        }
        path = root / f"{role.casefold()}.schema.json"
        path.write_bytes(canonical_bytes(schema))
        schema_paths[role] = path
        protocol_bindings.append(
            {
                "role": role,
                "artifact_ref": schema["$id"],
                "artifact_physical_sha256": file_sha256(path),
                "artifact_self_sha256": canonical_sha256(schema),
            }
        )
    profile = make_trusted_authority_profile(
        trusted_issuers=[issuer],
        trusted_authorities=[authority],
        receipt_bindings=receipt_bindings,
        protocol_schema_bindings=protocol_bindings,
        status=profile_status,
    )
    profile_path = root / "trusted_authority_profile.json"
    profile_path.write_bytes(canonical_bytes(profile))
    return {
        "profile_path": profile_path,
        "receipt_paths": receipt_paths,
        "schema_paths": schema_paths,
    }
