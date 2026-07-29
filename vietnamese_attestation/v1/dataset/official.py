"""Fail-closed consumer for Dataset-owned Frozen Candidate release sets."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..contracts.shared import validate_shared_frozen_candidate
from ..strict_json import (
    canonical_relative_ref,
    regular_files,
    reject_link,
    resolve_artifact_file,
    resolve_artifact_root,
    strict_json_loads,
)


OFFICIAL_SET_MANIFEST_SCHEMA_ID = "DatasetFrozenCandidateSetManifestV1"
OFFICIAL_SET_RECEIPT_SCHEMA_ID = "DatasetFrozenCandidateSetReleaseReceiptV1"
OFFICIAL_SET_SCHEMA_VERSION = "1.0.0"
OFFICIAL_DATASET_AUTHORITY_OWNER = "DATASET_AGENT"
OFFICIAL_DATASET_PRODUCER_COMPONENT_ID = (
    "d2l-dataset-frozen-candidate-projector"
)
OFFICIAL_PILOT_MEMBER_COUNT = 15
OFFICIAL_PILOT_SENSE_COUNT = 5
OFFICIAL_PILOT_ZIP_SHA256 = (
    "9b6a9ee1272b6403054b61f5399d4391328d1d2d8a964b1102af0a2656bc2738"
)
OFFICIAL_PILOT_MANIFEST_SCHEMA_ID = "D2LOfficial5SensePilotManifestV1"
OFFICIAL_PILOT_MANIFEST_SHA256 = (
    "16bd2b9c7a974bdccfb977384fa1a35381e6e810c110f489f31d1606398ce2f5"
)
OFFICIAL_PILOT_PIN_SCHEMA_ID = "D2LOfficialDatasetInputPinV1"
OFFICIAL_PILOT_PIN_SHA256 = (
    "7ae7c94176e32b419cfac4bb36704d633c550068e34d00b80389ebb20f035b05"
)
OFFICIAL_PILOT_PIN_MAIN_COMMIT = (
    "7fd046cc6a9b8f78fd122549feaefa4b2ab83821"
)
OFFICIAL_PILOT_AUTHORITY_ROOT_REF = (
    "review_evidence/dataset/d2l-stage-a-official-5-sense-pilot-v1"
)
OFFICIAL_PILOT_ZIP_REF = (
    OFFICIAL_PILOT_AUTHORITY_ROOT_REF
    + "/d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip"
)
OFFICIAL_PILOT_PIN_REF = (
    OFFICIAL_PILOT_AUTHORITY_ROOT_REF + "/official_dataset_input_pin_v1.json"
)
OFFICIAL_PILOT_PRODUCER_COMPONENT_VERSION = "1.0.0"
OFFICIAL_PILOT_PRODUCER_RUN_ID = (
    "d2l-stage-a-p0b-official-5-sense-release"
)
OFFICIAL_PILOT_PRODUCER_RUN_SPEC_ID = (
    "d2l-stage-a-p0b-official-5-sense-spec-v1"
)
OFFICIAL_PILOT_ARCHIVE_MEMBER_COUNT = 70
OFFICIAL_PILOT_STATUS = "READY_FOR_REAL_PILOT_REVIEW"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHECKSUM_ROW = re.compile(r"([0-9a-f]{64}) \*([^\r\n]+)")
_CANDIDATE_REF = re.compile(
    r"frozen_candidate_contracts_15/(candidate_[0-9a-f]{24})\.json"
)


@dataclass(frozen=True)
class OfficialFrozenCandidateSet:
    manifest: dict[str, Any]
    receipt: dict[str, Any]
    candidates: tuple[dict[str, Any], ...]
    manifest_physical_sha256: str
    receipt_physical_sha256: str
    release_zip_physical_sha256: str | None = None
    archive_member_count: int | None = None


def load_official_frozen_candidate_zip(
    dataset_release_zip: str | Path,
    dataset_input_pin: str | Path,
    *,
    expected_release_zip_sha256: str,
    expected_manifest_sha256: str,
    expected_pin_sha256: str = OFFICIAL_PILOT_PIN_SHA256,
) -> OfficialFrozenCandidateSet:
    """Load the exact Main-pinned five-sense Dataset release without extraction."""

    if _sha256(
        expected_release_zip_sha256, "expected_release_zip_sha256"
    ) != OFFICIAL_PILOT_ZIP_SHA256:
        raise ValueError("Dataset release ZIP authority pin mismatch")
    if _sha256(
        expected_manifest_sha256, "expected_manifest_sha256"
    ) != OFFICIAL_PILOT_MANIFEST_SHA256:
        raise ValueError("Dataset manifest authority pin mismatch")
    if _sha256(expected_pin_sha256, "expected_pin_sha256") != (
        OFFICIAL_PILOT_PIN_SHA256
    ):
        raise ValueError("Dataset input pin authority mismatch")

    pin_path, pin_raw, pin = _strict_object_file(
        dataset_input_pin, "Dataset input pin"
    )
    del pin_path
    _validate_official_pin(pin)

    zip_path = _strict_regular_file(dataset_release_zip, "Dataset release ZIP")
    zip_sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    if zip_sha256 != OFFICIAL_PILOT_ZIP_SHA256:
        raise ValueError("Dataset release ZIP physical SHA-256 mismatch")
    if zip_path.stat().st_size != pin["artifact"]["size_bytes"]:
        raise ValueError("Dataset release ZIP size differs from Main pin")

    members = _strict_zip_members(zip_path)
    if len(members) != OFFICIAL_PILOT_ARCHIVE_MEMBER_COUNT:
        raise ValueError("Dataset release ZIP member count mismatch")
    if len(members) != pin["artifact"]["entry_count"]:
        raise ValueError("Dataset release ZIP inventory differs from Main pin")

    manifest_raw, manifest = _strict_zip_object(
        members, "manifest.json", "Dataset release manifest"
    )
    manifest_physical_sha256 = hashlib.sha256(manifest_raw).hexdigest()
    _validate_official_manifest(manifest)
    if manifest_physical_sha256 != pin["manifest"]["physical_sha256"]:
        raise ValueError("Dataset manifest physical hash differs from Main pin")

    checksums = _parse_checksums(members["CHECKSUMS.sha256"])
    _verify_official_inventory(members, manifest, checksums)
    candidates = _official_candidates(members, manifest)

    return OfficialFrozenCandidateSet(
        manifest=copy.deepcopy(manifest),
        receipt=copy.deepcopy(pin),
        candidates=tuple(candidates),
        manifest_physical_sha256=manifest_physical_sha256,
        receipt_physical_sha256=hashlib.sha256(pin_raw).hexdigest(),
        release_zip_physical_sha256=zip_sha256,
        archive_member_count=len(members),
    )


def _validate_official_pin(pin: Mapping[str, Any]) -> None:
    _equal(pin, "schema_id", OFFICIAL_PILOT_PIN_SCHEMA_ID, "Dataset input pin")
    _equal(
        pin,
        "status",
        "CANONICAL_MAIN_PIN_ACCEPTED_FOR_REAL_ZERO_NETWORK_PILOT",
        "Dataset input pin",
    )
    _validate_self_hash(pin, "Dataset input pin")
    if pin["integrity"]["self_sha256"] != OFFICIAL_PILOT_PIN_SHA256:
        raise ValueError("Dataset input pin self-hash mismatch")

    artifact = _mapping(pin.get("artifact"), "Dataset input pin artifact")
    if artifact.get("physical_sha256") != OFFICIAL_PILOT_ZIP_SHA256:
        raise ValueError("Dataset input pin does not bind the accepted ZIP")
    if artifact.get("entry_count") != OFFICIAL_PILOT_ARCHIVE_MEMBER_COUNT:
        raise ValueError("Dataset input pin archive count mismatch")
    if artifact.get("size_bytes") != 135292:
        raise ValueError("Dataset input pin archive size mismatch")
    if artifact.get("do_not_alter_or_rebuild") is not True:
        raise ValueError("Dataset input pin immutability flag is missing")

    manifest = _mapping(pin.get("manifest"), "Dataset input pin manifest")
    if manifest.get("self_sha256") != OFFICIAL_PILOT_MANIFEST_SHA256:
        raise ValueError("Dataset input pin manifest self-hash mismatch")
    _sha256(
        manifest.get("physical_sha256"),
        "Dataset input pin manifest physical_sha256",
    )

    counts = _mapping(pin.get("counts"), "Dataset input pin counts")
    expected_counts = {
        "frozen_candidate_contracts": OFFICIAL_PILOT_MEMBER_COUNT,
        "constraint_evidence_packages": OFFICIAL_PILOT_MEMBER_COUNT,
        "effective_sense_contracts": OFFICIAL_PILOT_SENSE_COUNT,
    }
    for field, expected in expected_counts.items():
        if counts.get(field) != expected:
            raise ValueError(f"Dataset input pin {field} count mismatch")

    boundaries = _mapping(pin.get("boundaries"), "Dataset input pin boundaries")
    if boundaries.get("network_calls") != 0 or boundaries.get(
        "provider_calls"
    ) != 0:
        raise ValueError("Dataset input pin is not zero-network")
    if boundaries.get("final_glossary_decision") is not None:
        raise ValueError("Dataset input pin contains a final glossary decision")
    if boundaries.get("production") != "NOT_AUTHORIZED":
        raise ValueError("Dataset input pin production boundary mismatch")

    downstream = _mapping(
        pin.get("downstream"), "Dataset input pin downstream"
    )
    attestation = _mapping(
        downstream.get("vietnamese_attestation"),
        "Dataset input pin Vietnamese Attestation downstream",
    )
    if attestation.get("expected_official_packages_or_holds") != (
        OFFICIAL_PILOT_MEMBER_COUNT
    ):
        raise ValueError("Dataset input pin E package count mismatch")
    if attestation.get("registry_policy") != (
        "APPROVED_CONTROLLED_VIETNAMESE_REGISTRY_ONLY"
    ):
        raise ValueError("Dataset input pin E registry policy mismatch")
    if attestation.get("status") != (
        "AUTHORIZED_TO_PRODUCE_EVIDENCE_OR_EXPLICIT_PER_CANDIDATE_HOLD"
    ):
        raise ValueError("Dataset input pin E authorization mismatch")

    producer_git = _mapping(
        pin.get("producer_git"), "Dataset input pin producer Git"
    )
    if producer_git.get("reviewed_commit") != (
        "c585308abbdcd64af7d9c428509e441e56090bee"
    ):
        raise ValueError("Dataset input pin reviewed producer commit mismatch")
    if producer_git.get("unreviewed_later_commit_excluded") != (
        "b03093dd700f6b5ef87b43d97f4cc1852bea7c4c"
    ):
        raise ValueError("Dataset input pin excluded producer commit mismatch")


def _validate_official_manifest(manifest: Mapping[str, Any]) -> None:
    _exact_keys(
        manifest,
        {
            "artifact_name",
            "contract_authority",
            "counts",
            "created_at",
            "files",
            "final_glossary_decision",
            "manifest_sha256",
            "policy_id",
            "provider_call_count",
            "schema_id",
            "schema_version",
            "source_bindings",
            "status",
        },
        "official Dataset manifest",
    )
    _equal(
        manifest,
        "schema_id",
        OFFICIAL_PILOT_MANIFEST_SCHEMA_ID,
        "official Dataset manifest",
    )
    _equal(manifest, "schema_version", "1.0.0", "official Dataset manifest")
    _equal(
        manifest,
        "status",
        OFFICIAL_PILOT_STATUS,
        "official Dataset manifest",
    )
    if manifest.get("provider_call_count") != 0:
        raise ValueError("official Dataset manifest is not zero-provider")
    if manifest.get("final_glossary_decision") is not None:
        raise ValueError("official Dataset manifest contains a final decision")
    if manifest.get("manifest_sha256") != OFFICIAL_PILOT_MANIFEST_SHA256:
        raise ValueError("official Dataset manifest authority hash mismatch")
    payload = copy.deepcopy(dict(manifest))
    payload.pop("manifest_sha256", None)
    if hashlib.sha256(_canonical_bytes(payload)).hexdigest() != (
        OFFICIAL_PILOT_MANIFEST_SHA256
    ):
        raise ValueError("official Dataset manifest self-hash mismatch")

    counts = _mapping(manifest.get("counts"), "official Dataset counts")
    expected_counts = {
        "candidate": OFFICIAL_PILOT_MEMBER_COUNT,
        "constraint_evidence_package": OFFICIAL_PILOT_MEMBER_COUNT,
        "effective_sense_contract": OFFICIAL_PILOT_SENSE_COUNT,
        "frozen_candidate_contract": OFFICIAL_PILOT_MEMBER_COUNT,
        "selected_sense": OFFICIAL_PILOT_SENSE_COUNT,
    }
    for field, expected in expected_counts.items():
        if counts.get(field) != expected:
            raise ValueError(f"official Dataset manifest {field} count mismatch")

    authority = _mapping(
        manifest.get("contract_authority"), "official Dataset contract authority"
    )
    if authority != {
        "commit": "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed",
        "manifest_sha256": (
            "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
        ),
        "tag": "contracts-v1.1.0",
    }:
        raise ValueError("official Dataset outer Contracts R1 binding mismatch")

    bindings = _mapping(
        manifest.get("source_bindings"), "official Dataset source bindings"
    )
    for field in (
        "dataset_v3_manifest_sha256",
        "parent_p0_manifest_sha256",
        "reviewed_15_manifest_sha256",
    ):
        _sha256(bindings.get(field), f"official Dataset {field}")

    files = _mapping(manifest.get("files"), "official Dataset file inventory")
    refs = list(files)
    if refs != sorted(refs) or len(refs) != len(set(refs)):
        raise ValueError("official Dataset manifest refs are not sorted and unique")
    case_refs: set[str] = set()
    for ref, record in files.items():
        canonical_ref, case_ref = canonical_relative_ref(ref)
        if canonical_ref != ref or case_ref in case_refs:
            raise ValueError("official Dataset manifest has confusable file refs")
        case_refs.add(case_ref)
        row = _mapping(record, f"official Dataset file record: {ref}")
        _exact_keys(row, {"sha256", "size_bytes"}, f"file record: {ref}")
        _sha256(row["sha256"], f"file record SHA-256: {ref}")
        if type(row["size_bytes"]) is not int or row["size_bytes"] < 0:
            raise ValueError(f"file record size is invalid: {ref}")


def _strict_zip_members(path: Path) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("invalid Dataset release ZIP") from exc
    members: dict[str, bytes] = {}
    case_refs: set[str] = set()
    try:
        for info in archive.infolist():
            if info.is_dir():
                raise ValueError("Dataset release ZIP contains a directory entry")
            ref, case_ref = canonical_relative_ref(info.filename)
            if ref in members or case_ref in case_refs:
                raise ValueError("Dataset release ZIP has duplicate member refs")
            case_refs.add(case_ref)
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            dos_attributes = info.external_attr & 0xFFFF
            if stat.S_ISLNK(unix_mode) or (dos_attributes & 0x400):
                raise ValueError("Dataset release ZIP contains a link or reparse entry")
            if info.flag_bits & 0x1:
                raise ValueError("Dataset release ZIP contains an encrypted member")
            try:
                raw = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise ValueError(f"cannot read Dataset ZIP member: {ref}") from exc
            if len(raw) != info.file_size:
                raise ValueError(f"Dataset ZIP member size mismatch: {ref}")
            members[ref] = raw
    finally:
        archive.close()
    return members


def _strict_zip_object(
    members: Mapping[str, bytes], ref: str, label: str
) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = members[ref]
    except KeyError as exc:
        raise ValueError(f"missing {label}") from exc
    try:
        value = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"invalid strict JSON for {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return raw, value


def _parse_checksums(raw: bytes) -> dict[str, str]:
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeError as exc:
        raise ValueError("Dataset CHECKSUMS is not strict ASCII") from exc
    if not text.endswith("\n"):
        raise ValueError("Dataset CHECKSUMS must end with one newline")
    rows = text.splitlines()
    checksums: dict[str, str] = {}
    case_refs: set[str] = set()
    for index, row in enumerate(rows):
        match = _CHECKSUM_ROW.fullmatch(row)
        if match is None:
            raise ValueError(f"invalid Dataset CHECKSUMS row: {index}")
        digest, supplied_ref = match.groups()
        ref, case_ref = canonical_relative_ref(supplied_ref)
        if ref in checksums or case_ref in case_refs:
            raise ValueError("Dataset CHECKSUMS contains duplicate refs")
        case_refs.add(case_ref)
        checksums[ref] = digest
    if list(checksums) != sorted(checksums):
        raise ValueError("Dataset CHECKSUMS refs are not sorted")
    return checksums


def _verify_official_inventory(
    members: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    checksums: Mapping[str, str],
) -> None:
    expected_checksum_refs = set(members) - {"CHECKSUMS.sha256"}
    if set(checksums) != expected_checksum_refs:
        raise ValueError("Dataset CHECKSUMS does not cover the full ZIP inventory")
    expected_manifest_refs = set(manifest["files"])
    if set(checksums) != expected_manifest_refs | {"manifest.json"}:
        raise ValueError("Dataset manifest and CHECKSUMS inventory differ")
    for ref, expected in checksums.items():
        if hashlib.sha256(members[ref]).hexdigest() != expected:
            raise ValueError(f"Dataset CHECKSUMS hash mismatch: {ref}")
    for ref, record in manifest["files"].items():
        raw = members[ref]
        if len(raw) != record["size_bytes"]:
            raise ValueError(f"Dataset manifest size mismatch: {ref}")
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError(f"Dataset manifest file hash mismatch: {ref}")


def _official_candidates(
    members: Mapping[str, bytes], manifest: Mapping[str, Any]
) -> list[dict[str, Any]]:
    candidate_refs = sorted(ref for ref in members if _CANDIDATE_REF.fullmatch(ref))
    if len(candidate_refs) != OFFICIAL_PILOT_MEMBER_COUNT:
        raise ValueError("official Dataset candidate member set is not exact 15")
    effective_refs = sorted(
        ref
        for ref in members
        if ref.startswith("effective_sense_contracts_5/") and ref.endswith(".json")
    )
    if len(effective_refs) != OFFICIAL_PILOT_SENSE_COUNT:
        raise ValueError("official Dataset effective-sense member set is not exact 5")

    effective_by_hash: dict[str, Mapping[str, Any]] = {}
    for ref in effective_refs:
        _, effective = _strict_zip_object(
            members, ref, "official effective-sense contract"
        )
        _validate_self_hash(effective, "official effective-sense contract")
        digest = effective["integrity"]["self_sha256"]
        if digest in effective_by_hash:
            raise ValueError("official Dataset effective-sense hashes are not unique")
        effective_by_hash[digest] = effective

    candidates: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    candidate_versions: set[str] = set()
    sense_ids: set[str] = set()
    for ref in candidate_refs:
        _, value = _strict_zip_object(members, ref, "official frozen candidate")
        candidate = validate_shared_frozen_candidate(value)
        match = _CANDIDATE_REF.fullmatch(ref)
        assert match is not None
        key = candidate["candidate_key"]
        if key["candidate_id"] != match.group(1):
            raise ValueError("official candidate ID differs from its member ref")
        if key["candidate_id"] in candidate_ids:
            raise ValueError("official candidate IDs are not unique")
        if key["candidate_version"] in candidate_versions:
            raise ValueError("official candidate versions are not unique")
        candidate_ids.add(key["candidate_id"])
        candidate_versions.add(key["candidate_version"])
        sense_ids.add(key["sense_id"])
        _validate_official_candidate(candidate, manifest, effective_by_hash)
        candidates.append(candidate)
    if len(sense_ids) != OFFICIAL_PILOT_SENSE_COUNT:
        raise ValueError("official candidate set does not bind exact five senses")
    return candidates


def _validate_official_candidate(
    candidate: Mapping[str, Any],
    manifest: Mapping[str, Any],
    effective_by_hash: Mapping[str, Mapping[str, Any]],
) -> None:
    if candidate.get("binding_status") != "COMPLETE":
        raise ValueError("official Dataset candidate binding is not COMPLETE")
    key = _mapping(candidate.get("candidate_key"), "official candidate key")
    bindings = manifest["source_bindings"]
    if key.get("dataset_manifest_sha256") != bindings[
        "dataset_v3_manifest_sha256"
    ]:
        raise ValueError("official candidate Dataset V3 binding mismatch")
    effective_hash = key.get("effective_sense_contract_sha256")
    effective = effective_by_hash.get(effective_hash)
    if effective is None:
        raise ValueError("official candidate effective-sense binding is absent")
    for field in ("sense_id", "scope_id"):
        if key.get(field) != effective.get(field):
            raise ValueError(f"official candidate {field} binding mismatch")
    if effective.get("parent_dataset_manifest_sha256") != bindings[
        "dataset_v3_manifest_sha256"
    ]:
        raise ValueError("official effective-sense Dataset V3 binding mismatch")

    provenance = _mapping(
        candidate.get("input_provenance"), "official candidate provenance"
    )
    expected_producer = {
        "component_id": OFFICIAL_DATASET_PRODUCER_COMPONENT_ID,
        "component_version": OFFICIAL_PILOT_PRODUCER_COMPONENT_VERSION,
        "run_id": OFFICIAL_PILOT_PRODUCER_RUN_ID,
        "run_spec_id": OFFICIAL_PILOT_PRODUCER_RUN_SPEC_ID,
    }
    for field, expected in expected_producer.items():
        if provenance.get(field) != expected:
            raise ValueError(f"official candidate producer {field} mismatch")
    source_hashes = _mapping(
        provenance.get("source_artifact_hashes"),
        "official candidate source artifact hashes",
    )
    if source_hashes.get("dataset_manifest") != bindings[
        "dataset_v3_manifest_sha256"
    ]:
        raise ValueError("official candidate provenance Dataset binding mismatch")
    if source_hashes.get("candidate_instance") != key["candidate_version"]:
        raise ValueError("official candidate instance/version binding mismatch")


def _strict_regular_file(path: str | Path, label: str) -> Path:
    supplied = Path(path).absolute()
    reject_link(supplied)
    try:
        resolved = supplied.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"cannot resolve {label}") from exc
    reject_link(resolved)
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file")
    return resolved


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def load_official_frozen_candidate_set(
    dataset_release_manifest: str | Path,
    dataset_release_receipt: str | Path,
    candidate_root: str | Path,
    *,
    expected_receipt_sha256: str,
) -> OfficialFrozenCandidateSet:
    """Load one exact Dataset release after verifying its external receipt pin."""

    expected_receipt_sha256 = _sha256(
        expected_receipt_sha256, "expected_receipt_sha256"
    )
    receipt_path, receipt_raw, receipt = _strict_object_file(
        dataset_release_receipt, "Dataset release receipt"
    )
    receipt_physical_sha256 = hashlib.sha256(receipt_raw).hexdigest()
    if receipt_physical_sha256 != expected_receipt_sha256:
        raise ValueError("Dataset release receipt physical SHA-256 mismatch")
    _validate_receipt(receipt)

    manifest_path, manifest_raw, manifest = _strict_object_file(
        dataset_release_manifest, "Dataset release manifest"
    )
    manifest_physical_sha256 = hashlib.sha256(manifest_raw).hexdigest()
    _validate_manifest(manifest)
    if receipt["manifest_physical_sha256"] != manifest_physical_sha256:
        raise ValueError("Dataset receipt does not bind the manifest bytes")
    if receipt["manifest_self_sha256"] != manifest["integrity"]["self_sha256"]:
        raise ValueError("Dataset receipt does not bind the manifest self-hash")
    if receipt["producer"] != manifest["producer"]:
        raise ValueError("Dataset manifest and receipt producer differ")
    for field in ("dataset_manifest_sha256", "expected_member_count"):
        if receipt[field] != manifest[field]:
            raise ValueError(f"Dataset manifest and receipt {field} differ")

    root = resolve_artifact_root(candidate_root)
    members = manifest["members"]
    expected_refs = {member["artifact_ref"] for member in members}
    if regular_files(root) != expected_refs:
        raise ValueError("Dataset candidate root and manifest member set differ")

    candidates: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    candidate_versions: set[str] = set()
    for index, member in enumerate(members):
        path = resolve_artifact_file(root, member["artifact_ref"])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != member["physical_sha256"]:
            raise ValueError(f"Dataset candidate physical hash mismatch: {index}")
        try:
            value = strict_json_loads(raw.decode("utf-8", errors="strict"))
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f"invalid strict Dataset candidate JSON: {index}") from exc
        if not isinstance(value, Mapping):
            raise ValueError(f"Dataset candidate is not an object: {index}")
        candidate = validate_shared_frozen_candidate(value)
        _validate_candidate_binding(candidate, member, manifest)
        candidate_id = candidate["candidate_key"]["candidate_id"]
        candidate_version = candidate["candidate_key"]["candidate_version"]
        if candidate_id in candidate_ids:
            raise ValueError("Dataset candidate IDs are not unique")
        if candidate_version in candidate_versions:
            raise ValueError("Dataset candidate versions are not unique")
        candidate_ids.add(candidate_id)
        candidate_versions.add(candidate_version)
        candidates.append(candidate)

    del receipt_path, manifest_path
    return OfficialFrozenCandidateSet(
        manifest=copy.deepcopy(manifest),
        receipt=copy.deepcopy(receipt),
        candidates=tuple(candidates),
        manifest_physical_sha256=manifest_physical_sha256,
        receipt_physical_sha256=receipt_physical_sha256,
    )


def _validate_receipt(receipt: Mapping[str, Any]) -> None:
    _exact_keys(
        receipt,
        {
            "schema_id",
            "schema_version",
            "producer",
            "manifest_physical_sha256",
            "manifest_self_sha256",
            "dataset_manifest_sha256",
            "expected_member_count",
            "integrity",
        },
        "Dataset release receipt",
    )
    _equal(receipt, "schema_id", OFFICIAL_SET_RECEIPT_SCHEMA_ID, "receipt")
    _equal(receipt, "schema_version", OFFICIAL_SET_SCHEMA_VERSION, "receipt")
    _validate_producer(receipt["producer"])
    for field in (
        "manifest_physical_sha256",
        "manifest_self_sha256",
        "dataset_manifest_sha256",
    ):
        _sha256(receipt[field], f"receipt.{field}")
    _member_count(receipt["expected_member_count"], "receipt")
    _validate_self_hash(receipt, "Dataset release receipt")


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    _exact_keys(
        manifest,
        {
            "schema_id",
            "schema_version",
            "producer",
            "dataset_manifest_sha256",
            "expected_member_count",
            "members",
            "integrity",
        },
        "Dataset release manifest",
    )
    _equal(manifest, "schema_id", OFFICIAL_SET_MANIFEST_SCHEMA_ID, "manifest")
    _equal(manifest, "schema_version", OFFICIAL_SET_SCHEMA_VERSION, "manifest")
    _validate_producer(manifest["producer"])
    _sha256(manifest["dataset_manifest_sha256"], "manifest.dataset_manifest_sha256")
    expected_count = _member_count(manifest["expected_member_count"], "manifest")
    members = manifest["members"]
    if not isinstance(members, list) or len(members) != expected_count:
        raise ValueError("Dataset manifest member count mismatch")

    refs: list[str] = []
    case_refs: set[str] = set()
    for index, value in enumerate(members):
        if not isinstance(value, Mapping):
            raise ValueError(f"Dataset manifest member is not an object: {index}")
        _exact_keys(
            value,
            {
                "artifact_ref",
                "physical_sha256",
                "candidate_id",
                "candidate_version",
                "sense_id",
                "scope_id",
                "dataset_manifest_sha256",
                "effective_sense_contract_sha256",
                "input_contract_sha256",
                "candidate_self_sha256",
            },
            f"Dataset manifest member {index}",
        )
        artifact_ref, case_ref = canonical_relative_ref(value["artifact_ref"])
        if case_ref in case_refs:
            raise ValueError("Dataset manifest has case-confusable member refs")
        case_refs.add(case_ref)
        refs.append(artifact_ref)
        for field in (
            "physical_sha256",
            "dataset_manifest_sha256",
            "effective_sense_contract_sha256",
            "input_contract_sha256",
            "candidate_self_sha256",
        ):
            _sha256(value[field], f"members[{index}].{field}")
        for field in ("candidate_id", "candidate_version", "sense_id", "scope_id"):
            _nonempty(value[field], f"members[{index}].{field}")
        if value["dataset_manifest_sha256"] != manifest["dataset_manifest_sha256"]:
            raise ValueError("Dataset member manifest binding mismatch")
    if refs != sorted(refs) or len(refs) != len(set(refs)):
        raise ValueError("Dataset manifest member refs must be sorted and unique")
    _validate_self_hash(manifest, "Dataset release manifest")


def _validate_producer(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("Dataset producer must be an object")
    _exact_keys(
        value,
        {"authority_owner", "component_id", "component_version", "release_id"},
        "Dataset producer",
    )
    _equal(value, "authority_owner", OFFICIAL_DATASET_AUTHORITY_OWNER, "producer")
    _equal(
        value,
        "component_id",
        OFFICIAL_DATASET_PRODUCER_COMPONENT_ID,
        "producer",
    )
    _nonempty(value["component_version"], "producer.component_version")
    _nonempty(value["release_id"], "producer.release_id")


def _validate_candidate_binding(
    candidate: Mapping[str, Any],
    member: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    if candidate["binding_status"] != "COMPLETE":
        raise ValueError("official Dataset candidate binding is not COMPLETE")
    key = candidate["candidate_key"]
    expected = {
        "candidate_id": key["candidate_id"],
        "candidate_version": key["candidate_version"],
        "sense_id": key["sense_id"],
        "scope_id": key["scope_id"],
        "dataset_manifest_sha256": key["dataset_manifest_sha256"],
        "effective_sense_contract_sha256": key[
            "effective_sense_contract_sha256"
        ],
        "input_contract_sha256": candidate["input_contract_sha256"],
        "candidate_self_sha256": candidate["integrity"]["self_sha256"],
    }
    for field, value in expected.items():
        if member[field] != value:
            raise ValueError(f"Dataset candidate/member {field} binding mismatch")
    if key["dataset_manifest_sha256"] != manifest["dataset_manifest_sha256"]:
        raise ValueError("Dataset candidate manifest identity mismatch")
    provenance = candidate["input_provenance"]
    producer = manifest["producer"]
    if provenance["component_id"] != producer["component_id"]:
        raise ValueError("Dataset candidate producer component mismatch")
    if provenance["component_version"] != producer["component_version"]:
        raise ValueError("Dataset candidate producer version mismatch")
    if provenance["run_id"] != producer["release_id"]:
        raise ValueError("Dataset candidate producer release mismatch")
    if provenance["source_artifact_hashes"].get("dataset") != manifest[
        "dataset_manifest_sha256"
    ]:
        raise ValueError("Dataset candidate provenance manifest mismatch")


def _strict_object_file(
    path: str | Path, label: str
) -> tuple[Path, bytes, dict[str, Any]]:
    supplied = Path(path).absolute()
    reject_link(supplied)
    resolved = supplied.resolve(strict=True)
    reject_link(resolved)
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file")
    raw = resolved.read_bytes()
    try:
        value = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"invalid strict JSON for {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return resolved, raw, value


def _validate_self_hash(value: Mapping[str, Any], label: str) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {"self_sha256"}:
        raise ValueError(f"{label} integrity is invalid")
    expected = _sha256(integrity["self_sha256"], f"{label}.integrity.self_sha256")
    payload = copy.deepcopy(dict(value))
    payload["integrity"].pop("self_sha256", None)
    actual = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if actual != expected:
        raise ValueError(f"{label} self-hash mismatch")


def _member_count(value: Any, label: str) -> int:
    if type(value) is not int or value != OFFICIAL_PILOT_MEMBER_COUNT:
        raise ValueError(
            f"{label} expected_member_count must be {OFFICIAL_PILOT_MEMBER_COUNT}"
        )
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} keys mismatch")


def _equal(
    value: Mapping[str, Any], field: str, expected: str, label: str
) -> None:
    if value.get(field) != expected:
        raise ValueError(f"{label}.{field} mismatch")


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


__all__ = [
    "OFFICIAL_DATASET_AUTHORITY_OWNER",
    "OFFICIAL_DATASET_PRODUCER_COMPONENT_ID",
    "OFFICIAL_PILOT_ARCHIVE_MEMBER_COUNT",
    "OFFICIAL_PILOT_AUTHORITY_ROOT_REF",
    "OFFICIAL_PILOT_MANIFEST_SCHEMA_ID",
    "OFFICIAL_PILOT_MANIFEST_SHA256",
    "OFFICIAL_PILOT_MEMBER_COUNT",
    "OFFICIAL_PILOT_PIN_MAIN_COMMIT",
    "OFFICIAL_PILOT_PIN_REF",
    "OFFICIAL_PILOT_PIN_SCHEMA_ID",
    "OFFICIAL_PILOT_PIN_SHA256",
    "OFFICIAL_PILOT_PRODUCER_COMPONENT_VERSION",
    "OFFICIAL_PILOT_PRODUCER_RUN_ID",
    "OFFICIAL_PILOT_PRODUCER_RUN_SPEC_ID",
    "OFFICIAL_PILOT_SENSE_COUNT",
    "OFFICIAL_PILOT_STATUS",
    "OFFICIAL_PILOT_ZIP_SHA256",
    "OFFICIAL_PILOT_ZIP_REF",
    "OFFICIAL_SET_MANIFEST_SCHEMA_ID",
    "OFFICIAL_SET_RECEIPT_SCHEMA_ID",
    "OFFICIAL_SET_SCHEMA_VERSION",
    "OfficialFrozenCandidateSet",
    "load_official_frozen_candidate_set",
    "load_official_frozen_candidate_zip",
]
