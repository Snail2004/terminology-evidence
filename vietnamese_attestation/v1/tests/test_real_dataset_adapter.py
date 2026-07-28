from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

from vietnamese_attestation import v1
from vietnamese_attestation.v1.dataset import (
    ADAPTER_POLICY_ID,
    ADAPTER_SCHEMA_ID,
    ADAPTER_SCHEMA_VERSION,
    DatasetAdapterError,
    PILOT_MANIFEST_SHA256,
    PILOT_SCHEMA_ID,
    PILOT_ZIP_SHA256,
    V3_MANIFEST_SHA256,
    V3_SCHEMA_ID,
    V3_ZIP_SHA256,
    adapt_dataset_zip,
    load_supported_dataset_archive,
    validate_adapter_package,
    validate_zip_member_names,
)
from vietnamese_attestation.v1.cli.adapt_dataset import (
    main as adapter_cli_main,
)


DEFAULT_DATASET_ROOT = Path(__file__).resolve().parents[3] / "dataset"


def _dataset_root() -> Path:
    root = Path(os.environ.get("D2L_CE_DATASET_ROOT", DEFAULT_DATASET_ROOT))
    required = (
        root / "d2l_context_support_set_validation_ready_v3.zip",
        root / "pilot_dev_only_v1_1.zip",
    )
    if not all(path.is_file() for path in required):
        pytest.skip("exact shared C/E V3 and pilot V1.1 ZIPs are unavailable")
    return root


@lru_cache(maxsize=1)
def _v3_package() -> dict[str, object]:
    return adapt_dataset_zip(
        _dataset_root() / "d2l_context_support_set_validation_ready_v3.zip"
    )


@lru_cache(maxsize=1)
def _pilot_package() -> dict[str, object]:
    root = _dataset_root()
    return adapt_dataset_zip(
        root / "pilot_dev_only_v1_1.zip",
        parent_v3_zip=(
            root / "d2l_context_support_set_validation_ready_v3.zip"
        ),
    )


def test_public_facade_exposes_real_dataset_adapter() -> None:
    assert v1.ADAPTER_SCHEMA_ID == ADAPTER_SCHEMA_ID
    assert v1.ADAPTER_SCHEMA_VERSION == ADAPTER_SCHEMA_VERSION
    assert callable(v1.adapt_dataset_zip)
    assert callable(v1.validate_adapter_package)


def test_real_v3_maps_exact_candidate_and_sense_identities() -> None:
    root = _dataset_root()
    source_path = root / "d2l_context_support_set_validation_ready_v3.zip"
    before = _file_sha256(source_path)
    source = load_supported_dataset_archive(source_path)
    package = _v3_package()

    assert package["schema_id"] == ADAPTER_SCHEMA_ID
    assert package["policy_id"] == ADAPTER_POLICY_ID
    assert package["source"]["schema_id"] == V3_SCHEMA_ID
    assert package["source"]["zip_sha256"] == V3_ZIP_SHA256
    assert package["source"]["manifest_sha256"] == V3_MANIFEST_SHA256
    assert package["source"]["parent_dataset_manifest_sha256"] is None
    assert package["mode"] == "VALIDATION_READY_ZERO_API"
    assert package["receipt"]["term_sense_count"] == 150
    assert package["receipt"]["candidate_count"] == 450
    assert package["receipt"]["context_count"] == 1340
    assert len(package["candidates"]) == 450

    raw_by_id = {
        row["candidate_instance_id"]: row
        for row in source.candidate_instances
    }
    for normalized in package["candidates"]:
        raw = raw_by_id[normalized["candidate_id"]]
        assert normalized["candidate_id"] == raw["candidate_instance_id"]
        assert normalized["candidate_version"] == raw[
            "candidate_instance_sha256"
        ]
        assert normalized["candidate_vi"] == raw["candidate_target_vi"]
        assert normalized["formation"]["provenance"] == raw[
            "formation_provenance"
        ]
        assert normalized["final_glossary_decision"] is None
    assert before == _file_sha256(source_path) == V3_ZIP_SHA256


def test_real_pilot_binds_v3_parent_and_keeps_authority_unavailable() -> None:
    root = _dataset_root()
    source_path = root / "pilot_dev_only_v1_1.zip"
    parent_path = root / "d2l_context_support_set_validation_ready_v3.zip"
    before = (_file_sha256(source_path), _file_sha256(parent_path))
    package = _pilot_package()

    assert package["source"]["schema_id"] == PILOT_SCHEMA_ID
    assert package["source"]["zip_sha256"] == PILOT_ZIP_SHA256
    assert package["source"]["manifest_sha256"] == PILOT_MANIFEST_SHA256
    assert package["source"]["parent_dataset_manifest_sha256"] == (
        V3_MANIFEST_SHA256
    )
    assert package["mode"] == "DEVELOPMENT_ZERO_API"
    assert package["receipt"]["term_sense_count"] == 5
    assert package["receipt"]["candidate_count"] == 15
    assert package["receipt"]["context_count"] == 38
    assert package["receipt"]["provider_call_count"] == 0
    assert package["final_glossary_decision"] is None
    assert package["authority"] == {
        "official": False,
        "calibrated": False,
        "human_review_complete": False,
        "candidate_is_human_gold": False,
        "final_decision_authority": "GLOBAL_TERMINOLOGY_VALIDATOR_ONLY",
    }
    for row in package["candidates"]:
        assert row["known_vietnamese_surfaces"] == {
            "status": "UNAVAILABLE_NOT_PROVIDED",
            "canonical": None,
            "validated_variants": None,
            "rejected_variants": None,
            "source_term_surfaces_usage": "ENGLISH_SOURCE_ONLY_NOT_MAPPED",
        }
        assert row["domain_anchors"] == {
            "status": "UNAVAILABLE_SCOPE_ID_ONLY",
            "domain_profile_id": None,
            "vi_anchors": None,
            "en_anchors": None,
        }
        assert row["sense_contract"]["review_status"] == (
            "PENDING_HUMAN_REVIEW"
        )
        assert row["identity_binding"][
            "effective_sense_contract_sha256"
        ] is None
    assert before == (_file_sha256(source_path), _file_sha256(parent_path))


def test_pilot_rejects_missing_parent_v3() -> None:
    with pytest.raises(DatasetAdapterError, match="parent_v3_required"):
        adapt_dataset_zip(_dataset_root() / "pilot_dev_only_v1_1.zip")


def test_modified_source_zip_rejects_before_normalization(tmp_path: Path) -> None:
    source = _dataset_root() / "pilot_dev_only_v1_1.zip"
    modified = tmp_path / "pilot.zip"
    shutil.copyfile(source, modified)
    with modified.open("ab") as handle:
        handle.write(b"not-authoritative")
    with pytest.raises(DatasetAdapterError, match="unsupported_zip_sha256"):
        adapt_dataset_zip(
            modified,
            parent_v3_zip=(
                _dataset_root()
                / "d2l_context_support_set_validation_ready_v3.zip"
            ),
        )


@pytest.mark.parametrize(
    "names, code",
    [
        (["../escape.json"], "unsafe_zip_name"),
        (["/absolute.json"], "unsafe_zip_name"),
        (["C:/drive.json"], "unsafe_zip_name"),
        ([r"folder\file.json"], "unsafe_zip_name"),
        (["File.json", "file.json"], "case_confusable_zip_name"),
    ],
)
def test_zip_member_paths_fail_closed(names: list[str], code: str) -> None:
    infos = [
        SimpleNamespace(
            filename=name,
            is_dir=lambda: name.endswith("/"),
            flag_bits=0,
            external_attr=0,
            file_size=1,
        )
        for name in names
    ]
    with pytest.raises(DatasetAdapterError, match=code):
        validate_zip_member_names(infos)


def test_adapter_package_hash_rejects_identity_tampering() -> None:
    package = copy.deepcopy(_pilot_package())
    package["candidates"][0]["candidate_version"] = "f" * 64
    with pytest.raises(DatasetAdapterError):
        validate_adapter_package(package)


def test_zero_api_cli_writes_pilot_package_and_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _dataset_root()
    output = tmp_path / "adapter.json"
    receipt = tmp_path / "receipt.json"
    assert adapter_cli_main(
        [
            "--source-zip",
            str(root / "pilot_dev_only_v1_1.zip"),
            "--parent-v3-zip",
            str(root / "d2l_context_support_set_validation_ready_v3.zip"),
            "--output",
            str(output),
            "--receipt-output",
            str(receipt),
        ]
    ) == 0
    package = json.loads(output.read_text(encoding="utf-8"))
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert validate_adapter_package(package) == package
    assert receipt_payload == package["receipt"]
    assert receipt_payload["candidate_count"] == 15
    assert receipt_payload["provider_call_count"] == 0
    assert json.loads(capsys.readouterr().out)["candidate_count"] == 15


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
