from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from pathlib import PurePosixPath

import pytest
from terminology_contracts.bindings import seal_frozen_candidate_contract

from vietnamese_attestation.v1.cli.replay import main as replay_main
from vietnamese_attestation.v1.cli.run import main as run_main
from vietnamese_attestation.v1.dataset import (
    OFFICIAL_DATASET_AUTHORITY_OWNER,
    OFFICIAL_DATASET_PRODUCER_COMPONENT_ID,
    OFFICIAL_PILOT_ARCHIVE_MEMBER_COUNT,
    OFFICIAL_PILOT_MANIFEST_SCHEMA_ID,
    OFFICIAL_PILOT_MANIFEST_SHA256,
    OFFICIAL_PILOT_MEMBER_COUNT,
    OFFICIAL_PILOT_PIN_SCHEMA_ID,
    OFFICIAL_PILOT_PIN_SHA256,
    OFFICIAL_PILOT_SENSE_COUNT,
    OFFICIAL_PILOT_ZIP_SHA256,
    OFFICIAL_SET_MANIFEST_SCHEMA_ID,
    OFFICIAL_SET_RECEIPT_SCHEMA_ID,
    OFFICIAL_SET_SCHEMA_VERSION,
    load_official_frozen_candidate_set,
    load_official_frozen_candidate_zip,
)
from vietnamese_attestation.v1.runtime.audit import FileRunAuditStore
from vietnamese_attestation.v1.runtime.replay import AuditReplayReader
from vietnamese_attestation.v1.strict_json import strict_json_loads

from ..conftest import judge_payload


REPO_ROOT = Path(__file__).resolve().parents[4]
SHARED_EXAMPLE = (
    REPO_ROOT
    / "terminology_contracts_v1"
    / "examples"
    / "valid"
    / "v1.1.0"
    / "frozen_candidate_contract.json"
)
OFFICIAL_AUTHORITY_RELATIVE = Path(
    "review_evidence/dataset/d2l-stage-a-official-5-sense-pilot-v1"
)
OFFICIAL_ZIP_NAME = "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip"
OFFICIAL_PIN_NAME = "official_dataset_input_pin_v1.json"


def test_official_dataset_set_binds_receipt_members_and_candidate_identity(
    tmp_path: Path,
) -> None:
    del tmp_path
    paths = _official_authority_paths()
    loaded = load_official_frozen_candidate_zip(
        paths["zip"],
        paths["pin"],
        expected_release_zip_sha256=OFFICIAL_PILOT_ZIP_SHA256,
        expected_manifest_sha256=OFFICIAL_PILOT_MANIFEST_SHA256,
        expected_pin_sha256=OFFICIAL_PILOT_PIN_SHA256,
    )
    assert len(loaded.candidates) == OFFICIAL_PILOT_MEMBER_COUNT
    assert loaded.manifest["schema_id"] == OFFICIAL_PILOT_MANIFEST_SCHEMA_ID
    assert loaded.receipt["schema_id"] == OFFICIAL_PILOT_PIN_SCHEMA_ID
    assert loaded.release_zip_physical_sha256 == OFFICIAL_PILOT_ZIP_SHA256
    assert loaded.archive_member_count == OFFICIAL_PILOT_ARCHIVE_MEMBER_COUNT
    assert len(
        {row["candidate_key"]["sense_id"] for row in loaded.candidates}
    ) == OFFICIAL_PILOT_SENSE_COUNT
    assert {
        row["input_provenance"]["component_id"] for row in loaded.candidates
    } == {OFFICIAL_DATASET_PRODUCER_COMPONENT_ID}
    assert loaded.candidates[0]["binding_status"] == "COMPLETE"


def test_official_cli_rejects_loose_complete_input_and_accepts_release_set(
    tmp_path: Path,
) -> None:
    paths = _official_authority_paths()
    official = load_official_frozen_candidate_zip(
        paths["zip"],
        paths["pin"],
        expected_release_zip_sha256=OFFICIAL_PILOT_ZIP_SHA256,
        expected_manifest_sha256=OFFICIAL_PILOT_MANIFEST_SHA256,
    )
    candidate_id = official.candidates[0]["candidate_key"]["candidate_id"]
    candidate = json.loads(SHARED_EXAMPLE.read_text(encoding="utf-8"))
    loose = tmp_path / "loose.json"
    loose.write_text(json.dumps(candidate), encoding="utf-8")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(_offline_fixture()), encoding="utf-8")
    with pytest.raises(SystemExit):
        run_main(
            [
                "--candidate",
                str(loose),
                "--offline-fixture",
                str(fixture),
                "--output",
                str(tmp_path / "loose-out.json"),
            ]
        )

    output = tmp_path / "official-out.json"
    assert (
        run_main(
            [
                "--dataset-release-zip",
                str(paths["zip"]),
                "--dataset-input-pin",
                str(paths["pin"]),
                "--expected-dataset-release-zip-sha256",
                OFFICIAL_PILOT_ZIP_SHA256,
                "--expected-dataset-manifest-sha256",
                OFFICIAL_PILOT_MANIFEST_SHA256,
                "--official-candidate-id",
                candidate_id,
                "--offline-fixture",
                str(fixture),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["candidate_key"][
        "candidate_id"
    ] == candidate_id


def test_cli_json_loader_rejects_duplicate_keys(tmp_path: Path) -> None:
    candidate = tmp_path / "duplicate.json"
    candidate.write_text('{"candidate_id":"one","candidate_id":"two"}', encoding="utf-8")
    with pytest.raises(ValueError, match="strict"):
        run_main(
            [
                "--candidate",
                str(candidate),
                "--offline-fixture",
                str(tmp_path / "unused.json"),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )


def test_official_loader_rejects_receipt_tamper_and_producer_drift(
    tmp_path: Path,
) -> None:
    authority = _official_authority_paths()
    tampered_zip = tmp_path / "tampered.zip"
    tampered_zip.write_bytes(authority["zip"].read_bytes() + b"\x00")
    with pytest.raises(ValueError, match="ZIP physical"):
        load_official_frozen_candidate_zip(
            tampered_zip,
            authority["pin"],
            expected_release_zip_sha256=OFFICIAL_PILOT_ZIP_SHA256,
            expected_manifest_sha256=OFFICIAL_PILOT_MANIFEST_SHA256,
        )

    tampered_pin = tmp_path / "tampered-pin.json"
    pin = json.loads(authority["pin"].read_text(encoding="utf-8"))
    pin["artifact"]["physical_sha256"] = "0" * 64
    tampered_pin.write_text(json.dumps(pin), encoding="utf-8")
    with pytest.raises(ValueError, match="self-hash|accepted ZIP"):
        load_official_frozen_candidate_zip(
            authority["zip"],
            tampered_pin,
            expected_release_zip_sha256=OFFICIAL_PILOT_ZIP_SHA256,
            expected_manifest_sha256=OFFICIAL_PILOT_MANIFEST_SHA256,
        )

    for name, field in (("zip-parent-link", "zip"), ("pin-parent-link", "pin")):
        link = tmp_path / name
        os.symlink(authority[field].parent, link, target_is_directory=True)
        supplied = link / authority[field].name
        with pytest.raises(ValueError, match="symlink|reparse|junction"):
            load_official_frozen_candidate_zip(
                supplied if field == "zip" else authority["zip"],
                supplied if field == "pin" else authority["pin"],
                expected_release_zip_sha256=OFFICIAL_PILOT_ZIP_SHA256,
                expected_manifest_sha256=OFFICIAL_PILOT_MANIFEST_SHA256,
            )

    paths = _make_official_set(tmp_path / "path-chain")
    for name, field in (
        ("manifest-link", "manifest"),
        ("receipt-link", "receipt"),
        ("candidate-link", "root"),
    ):
        link = tmp_path / name
        os.symlink(paths[field].parent, link, target_is_directory=True)
        supplied = link / paths[field].name
        arguments = {
            "manifest": paths["manifest"],
            "receipt": paths["receipt"],
            "root": paths["root"],
        }
        arguments[field] = supplied
        with pytest.raises(ValueError, match="symlink|reparse|junction"):
            load_official_frozen_candidate_set(
                arguments["manifest"],
                arguments["receipt"],
                arguments["root"],
                expected_receipt_sha256=paths["receipt_sha256"],
            )

    if os.name == "nt":
        junction = tmp_path / "candidate-junction"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(paths["root"])],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        with pytest.raises(ValueError, match="reparse|junction"):
            load_official_frozen_candidate_set(
                paths["manifest"],
                paths["receipt"],
                junction,
                expected_receipt_sha256=paths["receipt_sha256"],
            )

    with pytest.raises(ValueError, match="authority pin"):
        load_official_frozen_candidate_zip(
            authority["zip"],
            authority["pin"],
            expected_release_zip_sha256="0" * 64,
            expected_manifest_sha256=OFFICIAL_PILOT_MANIFEST_SHA256,
        )

    with pytest.raises(ValueError, match="manifest authority"):
        load_official_frozen_candidate_zip(
            authority["zip"],
            authority["pin"],
            expected_release_zip_sha256=OFFICIAL_PILOT_ZIP_SHA256,
            expected_manifest_sha256="0" * 64,
        )

    producer_drift = _make_official_set(tmp_path / "producer-drift")
    manifest = json.loads(producer_drift["manifest"].read_text(encoding="utf-8"))
    manifest["producer"]["component_id"] = "vietnamese-attestation"
    _write_sealed(producer_drift["manifest"], manifest)
    receipt = json.loads(producer_drift["receipt"].read_text(encoding="utf-8"))
    receipt["manifest_physical_sha256"] = _sha256_file(
        producer_drift["manifest"]
    )
    receipt["manifest_self_sha256"] = manifest["integrity"]["self_sha256"]
    receipt["producer"] = copy.deepcopy(manifest["producer"])
    _write_sealed(producer_drift["receipt"], receipt)
    with pytest.raises(ValueError, match="producer.component_id"):
        load_official_frozen_candidate_set(
            producer_drift["manifest"],
            producer_drift["receipt"],
            producer_drift["root"],
            expected_receipt_sha256=_sha256_file(producer_drift["receipt"]),
        )


def test_direct_replay_requires_external_manifest_anchor_and_strict_rows(
    tmp_path: Path,
) -> None:
    manifest_path = _make_audit(tmp_path)
    manifest_sha = _sha256_file(manifest_path)
    output = tmp_path / "replay.json"
    with pytest.raises(SystemExit):
        replay_main(
            [
                "--manifest",
                str(manifest_path),
                "--mode",
                "REPLAY_FROM_SEARCH",
                "--output",
                str(output),
            ]
        )
    assert (
        replay_main(
            [
                "--manifest",
                str(manifest_path),
                "--expected-manifest-sha256",
                manifest_sha,
                "--mode",
                "REPLAY_FROM_SEARCH",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["manifest_sha256"] == manifest_sha

    manifest_parent_link = tmp_path / "replay-manifest-parent-link"
    os.symlink(manifest_path.parent, manifest_parent_link, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink|reparse|junction"):
        AuditReplayReader(
            manifest_parent_link / manifest_path.name,
            expected_manifest_sha256=manifest_sha,
        )

    stream = manifest_path.parent / "search" / "requests.jsonl"
    stream.write_bytes(b'{"x":1,"x":2}\n')
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["streams"]["search_attempts"]["artifact_sha256"] = _sha256_file(stream)
    manifest["streams"]["search_attempts"]["row_count"] = 1
    _write_canonical(manifest_path, manifest)
    with pytest.raises(ValueError, match="strict audit stream"):
        AuditReplayReader(
            manifest_path,
            expected_manifest_sha256=_sha256_file(manifest_path),
        ).verify_all_content()

    manifest_raw = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        manifest_raw.replace(
            '{"attestation_execution_id":',
            '{"schema_id":"forged","attestation_execution_id":',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="strict audit manifest"):
        AuditReplayReader(
            manifest_path,
            expected_manifest_sha256=_sha256_file(manifest_path),
        )


def _make_official_set(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "candidates"
    root.mkdir(parents=True)
    dataset_sha = "d" * 64
    release_id = "dataset-release-001"
    producer = {
        "authority_owner": OFFICIAL_DATASET_AUTHORITY_OWNER,
        "component_id": OFFICIAL_DATASET_PRODUCER_COMPONENT_ID,
        "component_version": "1.1.0",
        "release_id": release_id,
    }
    members = []
    for index in range(OFFICIAL_PILOT_MEMBER_COUNT):
        candidate = json.loads(SHARED_EXAMPLE.read_text(encoding="utf-8"))
        key = candidate["candidate_key"]
        key.update(
            {
                "candidate_id": f"cand-{index:03d}",
                "candidate_version": f"version-{index:03d}",
                "sense_id": f"sense-{index:03d}",
                "scope_id": "scope-pilot",
                "dataset_manifest_sha256": dataset_sha,
                "effective_sense_contract_sha256": _sha256_text(
                    f"sense-{index}"
                ),
            }
        )
        key["candidate_vi"] = f"ứng viên {index}"
        candidate["surfaces"]["canonical_vi"] = key["candidate_vi"]
        provenance = candidate["input_provenance"]
        provenance["component_id"] = producer["component_id"]
        provenance["component_version"] = producer["component_version"]
        provenance["run_id"] = producer["release_id"]
        provenance["source_artifact_hashes"]["dataset"] = dataset_sha
        candidate = seal_frozen_candidate_contract(candidate)
        key = candidate["candidate_key"]
        ref = f"candidates/candidate-{index:03d}.json"
        path = root.joinpath(*PurePosixPath(ref).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = _canonical_bytes(candidate)
        path.write_bytes(raw)
        members.append(
            {
                "artifact_ref": ref,
                "physical_sha256": hashlib.sha256(raw).hexdigest(),
                "candidate_id": key["candidate_id"],
                "candidate_version": key["candidate_version"],
                "sense_id": key["sense_id"],
                "scope_id": key["scope_id"],
                "dataset_manifest_sha256": dataset_sha,
                "effective_sense_contract_sha256": key[
                    "effective_sense_contract_sha256"
                ],
                "input_contract_sha256": candidate["input_contract_sha256"],
                "candidate_self_sha256": candidate["integrity"]["self_sha256"],
            }
        )
    manifest = {
        "schema_id": OFFICIAL_SET_MANIFEST_SCHEMA_ID,
        "schema_version": OFFICIAL_SET_SCHEMA_VERSION,
        "producer": producer,
        "dataset_manifest_sha256": dataset_sha,
        "expected_member_count": OFFICIAL_PILOT_MEMBER_COUNT,
        "members": members,
        "integrity": {"self_sha256": "0" * 64},
    }
    manifest_path = tmp_path / "dataset_release_manifest.json"
    _write_sealed(manifest_path, manifest)
    manifest_raw = manifest_path.read_bytes()
    receipt = {
        "schema_id": OFFICIAL_SET_RECEIPT_SCHEMA_ID,
        "schema_version": OFFICIAL_SET_SCHEMA_VERSION,
        "producer": producer,
        "manifest_physical_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "manifest_self_sha256": manifest["integrity"]["self_sha256"],
        "dataset_manifest_sha256": dataset_sha,
        "expected_member_count": OFFICIAL_PILOT_MEMBER_COUNT,
        "integrity": {"self_sha256": "0" * 64},
    }
    receipt_path = tmp_path / "dataset_release_receipt.json"
    _write_sealed(receipt_path, receipt)
    return {
        "root": root,
        "manifest": manifest_path,
        "receipt": receipt_path,
        "receipt_sha256": _sha256_file(receipt_path),
    }


def _make_audit(tmp_path: Path) -> Path:
    store = FileRunAuditStore(tmp_path / "runs", "execution-001")
    store.append("search_attempts", {"request": "one"})
    store.finalize(
        run_spec_id="spec-001",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )
    return tmp_path / "runs" / "runs" / "execution-001" / "run_manifest.json"


def _offline_fixture() -> dict[str, object]:
    return {
        "search_provider_id": "fixture_search",
        "search_results_by_query_class": {
            "EXACT_CANDIDATE": [],
            "CANDIDATE_DOMAIN": [],
            "CANDIDATE_SOURCE_TERM": [],
        },
        "documents": {},
        "judge_routes": [
            {
                "route_id": "fixture_judge",
                "model_id": "fixture-model",
                "payloads_by_evidence_id": {"*": judge_payload()},
            }
        ],
        "timestamps": [
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:01Z",
        ],
    }


def _write_sealed(path: Path, value: dict[str, object]) -> None:
    value["integrity"] = {"self_sha256": "0" * 64}
    value["integrity"]["self_sha256"] = _self_sha256(value)
    _write_canonical(path, value)


def _write_canonical(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _self_sha256(value: dict[str, object]) -> str:
    copy_value = copy.deepcopy(value)
    copy_value["integrity"].pop("self_sha256", None)
    return hashlib.sha256(_canonical_bytes(copy_value).rstrip(b"\n")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _official_authority_paths() -> dict[str, Path]:
    supplied = os.environ.get("D2L_OFFICIAL_DATASET_AUTHORITY_ROOT")
    root = Path(supplied) if supplied else REPO_ROOT / OFFICIAL_AUTHORITY_RELATIVE
    zip_path = root / OFFICIAL_ZIP_NAME
    pin_path = root / OFFICIAL_PIN_NAME
    if not zip_path.is_file() or not pin_path.is_file():
        raise AssertionError(
            "exact official Dataset authority is unavailable; set "
            "D2L_OFFICIAL_DATASET_AUTHORITY_ROOT"
        )
    return {"zip": zip_path, "pin": pin_path}
