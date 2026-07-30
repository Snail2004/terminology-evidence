from __future__ import annotations

import copy
import json
import os
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
from vietnamese_attestation.v1.live.authority_adapter.source_governance import (
    RUNTIME_REGISTRY_SELF_SHA256,
    fetch_after_path_admission,
    load_runtime_registry_projection,
)
from vietnamese_attestation.v1.live.authority_adapter.final_canary import (
    load_final_canary_authority_inputs,
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
from vietnamese_attestation.v1.live.policies import validate_policy_bundle
from vietnamese_attestation.v1.live.schema_tools import SCHEMA_CATALOG
from vietnamese_attestation.v1.live.service import (
    ELiveService,
    compute_run_spec_id,
    make_run_request,
)
from vietnamese_attestation.v1.live.snapshot import (
    build_snapshot,
    verify_snapshot,
    zip_snapshot,
)


SOURCE_GOVERNANCE_PACKAGE = Path(
    os.environ.get(
        "E_SOURCE_GOVERNANCE_PACKAGE",
        r"C:\work\terminology-evidence-artifacts\D0_API_Execution_Plan_Operations_V1\runtime-registry-projection-v1\release\build-a.zip",
    )
)
CORPUS_AUTHORITY_PACKAGE = Path(
    os.environ.get(
        "E_CORPUS_AUTHORITY_PACKAGE",
        r"C:\work\terminology-evidence-artifacts\D0_API_Execution_Plan_Operations_V1\corpus-acquisition-runtime-v1\release\build-a.zip",
    )
)
DRAFT4_FINAL_AUTHORITY_PACKAGE = Path(
    os.environ.get(
        "E_DRAFT4_FINAL_AUTHORITY_PACKAGE",
        r"C:\work\terminology-evidence-artifacts\D0_API_Execution_Plan_Operations_V1\draft4-final-authority\release\build-a.zip",
    )
)
E05_DELIVERY = Path(
    os.environ.get(
        "E05_EXACT_INPUT_DELIVERY",
        r"C:\work\terminology-evidence-artifacts\e05-exact-integration-input-v1\delivery.zip",
    )
)
FROZEN_CANDIDATE_CONTRACT = Path(
    os.environ.get(
        "E_FROZEN_CANDIDATE_CONTRACT",
        r"C:\work\terminology-evidence-artifacts\D0_API_Execution_Plan_Operations_V1\canary-global-contracts-v2\release\build-a\contracts\frozen_candidate.json",
    )
)


def test_source_governance_path_admission_precedes_fetch() -> None:
    projection = load_runtime_registry_projection(SOURCE_GOVERNANCE_PACKAGE)
    calls: list[str] = []

    def fetch(url: str, *, retry_index: int) -> dict[str, int]:
        calls.append(url)
        return {"retry_index": retry_index}

    with pytest.raises(LiveSchemaError, match="outside reviewed host/path projection"):
        fetch_after_path_admission(
            projection,
            projection.registry,
            fetch,
            "https://users.soict.hust.edu.vn/private/unreviewed.pdf",
            retry_index=0,
        )
    assert calls == []

    admission, result = fetch_after_path_admission(
        projection,
        projection.registry,
        fetch,
        "https://users.soict.hust.edu.vn/huonglt/AI/lecture.pdf",
        retry_index=0,
    )
    assert admission["source_id"] == "HUST_SOICT_LECTURES"
    assert admission["registry_self_sha256"] == RUNTIME_REGISTRY_SELF_SHA256
    assert result == {"retry_index": 0}
    assert calls == ["https://users.soict.hust.edu.vn/huonglt/AI/lecture.pdf"]


def test_live_snapshot_preserves_exact_authorities_and_run_hold(
    tmp_path: Path,
) -> None:
    projection = load_runtime_registry_projection(SOURCE_GOVERNANCE_PACKAGE)
    authorities = load_final_canary_authority_inputs(
        CORPUS_AUTHORITY_PACKAGE, DRAFT4_FINAL_AUTHORITY_PACKAGE
    )
    source_root = tmp_path / "acquired"
    source_root.mkdir()
    (source_root / "lecture.html").write_bytes(
        b"<html><body>Underflow is called tran duoi.</body></html>"
    )
    receipt = seal(
        {
            "schema_id": "EControlledAcquisitionReceiptV1",
            "schema_version": "1.0.0",
            "mode": "LIVE_AUTHORIZED",
            "rows": [
                {
                    "file_ref": "lecture.html",
                    "source_id": "HUST_SOICT_LECTURES",
                    "canonical_url": "https://users.soict.hust.edu.vn/huonglt/AI/lecture.html",
                    "final_url": "https://users.soict.hust.edu.vn/huonglt/AI/lecture.html",
                    "content_type": "text/html",
                    "redirect_chain": [],
                    "retrieved_at_utc": "2026-07-30T13:00:00Z",
                    "http_status": 200,
                }
            ],
            "integrity": {},
        }
    )
    receipt_path = tmp_path / "acquisition_receipt.json"
    receipt_path.write_bytes(canonical_bytes(receipt) + b"\n")
    retrieval_policy = seal(
        {
            "schema_id": "ERetrievalPolicyV1",
            "schema_version": "1.0.0",
            "policy_id": "focused-live-snapshot-v1",
            "network_mode": "LIVE_AUTHORIZED",
            "integrity": {},
        }
    )
    snapshot_root = tmp_path / "snapshot"
    manifest = build_snapshot(
        source_root,
        snapshot_root,
        registry=projection.registry,
        retrieval_policy=retrieval_policy,
        acquisition_receipt=receipt,
        acquisition_receipt_source=receipt_path,
        corpus_authority_package_path=CORPUS_AUTHORITY_PACKAGE,
        draft4_final_authority_package_path=DRAFT4_FINAL_AUTHORITY_PACKAGE,
        source_governance_package_path=SOURCE_GOVERNANCE_PACKAGE,
    )
    assert manifest["mode"] == "LIVE_AUTHORIZED"
    assert verify_snapshot(snapshot_root)["mode"] == "LIVE_AUTHORIZED"
    assert (
        snapshot_root / "authority" / "acquisition_receipt.original.json"
    ).read_bytes() == receipt_path.read_bytes()
    assert (
        snapshot_root
        / "authority"
        / "main_corpus_acquisition_authorization.original.json"
    ).read_bytes() == authorities.corpus_authorization_bytes
    assert (
        snapshot_root
        / "authority"
        / "draft4_final_authority_receipt.original.json"
    ).read_bytes() == authorities.draft4_authority_bytes
    assert authorities.live_execution_authorized is False


def test_production_preflight_joins_official_frozen_candidate_contract(
    tmp_path: Path,
) -> None:
    workspace = build_fixture_workspace(tmp_path / "workspace")
    frozen = load_object(FROZEN_CANDIDATE_CONTRACT)
    candidate_key = frozen["candidate_key"]
    assert frozen["input_contract_sha256"] != canonical_sha256(candidate_key)
    policy_hashes = validate_policy_bundle(workspace["policy_bundle"])
    request = make_run_request(
        run_id="run_frozen_candidate_join_v1",
        phase_id="E_CONTROLLED_CORPUS_CANARY",
        sense_id=candidate_key["sense_id"],
        candidate_id=candidate_key["candidate_id"],
        term_en=candidate_key["source_term"],
        candidate_vi=candidate_key["candidate_vi"],
        sense_definition=frozen["effective_definition_en"],
        domain={
            "scope_id": candidate_key["scope_id"],
            "anchors": [candidate_key["source_term"]],
        },
        candidate_variants=[],
        authority_refs={
            "cohort_id": "fixture-cohort-v1",
            "registry_self_sha256": workspace["registry"]["integrity"][
                "self_sha256"
            ],
            "snapshot_manifest_sha256": workspace["service"].snapshot[
                "integrity"
            ]["self_sha256"],
            "candidate_key": candidate_key,
            "input_contract_sha256": frozen["input_contract_sha256"],
        },
        budget=workspace["request"]["budget"],
        policy_hashes=policy_hashes,
    )
    service = ELiveService(
        root=tmp_path / "runs",
        registry=workspace["registry"],
        snapshot_root=workspace["snapshot_root"],
        policy_bundle=workspace["policy_bundle"],
        authorization_receipt={},
        authorized_cohort_id="fixture-cohort-v1",
        authorized_candidate_ids=[candidate_key["candidate_id"]],
        execution_mode="PRODUCTION_AUTHORITY",
        e05_delivery_path=E05_DELIVERY,
        frozen_candidate_contract_path=FROZEN_CANDIDATE_CONTRACT,
    )

    accepted = service.preflight(request)
    assert "REQUEST_INPUT_CONTRACT_SHA256_MISMATCH" not in accepted["blockers"]
    assert "FROZEN_CANDIDATE_KEY_MISMATCH" not in accepted["blockers"]

    key_drift = copy.deepcopy(request)
    key_drift["authority_refs"]["candidate_key"]["candidate_version"] = "f" * 64
    key_drift["run_spec_id"] = compute_run_spec_id(key_drift)
    assert "FROZEN_CANDIDATE_KEY_MISMATCH" in service.preflight(key_drift)[
        "blockers"
    ]

    hash_drift = copy.deepcopy(request)
    hash_drift["authority_refs"]["input_contract_sha256"] = "0" * 64
    hash_drift["run_spec_id"] = compute_run_spec_id(hash_drift)
    assert "REQUEST_INPUT_CONTRACT_SHA256_MISMATCH" in service.preflight(
        hash_drift
    )["blockers"]


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
