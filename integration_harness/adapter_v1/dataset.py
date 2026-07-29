"""Strict Dataset pin/ZIP verification without importing Dataset internals."""

from __future__ import annotations

import copy
import hashlib
import re
import stat
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from integration_harness.errors import IntegrityError, ValidationError
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.identity import CandidateIdentity
from integration_harness.jsonio import canonical_bytes, load_json, loads_strict
from integration_harness.packages import validate_contract_schema
from integration_harness.paths import ensure_plain_root


OFFICIAL_MODE = "OFFICIAL_5_15_PREFLIGHT"
SYNTHETIC_MODE = "SYNTHETIC_50_150_CONFORMANCE"

OFFICIAL_PIN_SCHEMA = "D2LOfficialDatasetInputPinV1"
OFFICIAL_PIN_SELF_SHA256 = (
    "7ae7c94176e32b419cfac4bb36704d633c550068e34d00b80389ebb20f035b05"
)
OFFICIAL_ZIP_SHA256 = (
    "9b6a9ee1272b6403054b61f5399d4391328d1d2d8a964b1102af0a2656bc2738"
)
OFFICIAL_MANIFEST_SELF_SHA256 = (
    "16bd2b9c7a974bdccfb977384fa1a35381e6e810c110f489f31d1606398ce2f5"
)
OFFICIAL_PRODUCER_COMMIT = "c585308abbdcd64af7d9c428509e441e56090bee"
OFFICIAL_EXCLUDED_COMMIT = "b03093dd700f6b5ef87b43d97f4cc1852bea7c4c"

SYNTHETIC_PIN_SCHEMA = "HarnessSyntheticDatasetPinV1"
SYNTHETIC_MANIFEST_SCHEMA = "HarnessSyntheticDatasetManifestV1"


@dataclass(frozen=True)
class DatasetCandidate:
    identity: CandidateIdentity
    effective_path: str
    effective_raw: bytes
    effective: dict[str, Any]
    frozen_path: str
    frozen_raw: bytes
    frozen: dict[str, Any]
    constraint_path: str
    constraint_raw: bytes
    constraint: dict[str, Any]


@dataclass(frozen=True)
class DatasetRelease:
    mode: str
    zip_path: Path
    zip_raw: bytes
    pin_path: Path
    pin_raw: bytes
    pin: dict[str, Any]
    manifest_raw: bytes
    manifest: dict[str, Any]
    index_raw: bytes
    index: dict[str, Any]
    git_receipt_path: Path | None
    git_receipt_raw: bytes | None
    git_receipt: dict[str, Any] | None
    candidates: tuple[DatasetCandidate, ...]

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def sense_count(self) -> int:
        return len({item.identity.sense_id for item in self.candidates})


def load_dataset_release(
    zip_path: Path,
    pin_path: Path,
    *,
    git_receipt_path: Path | None,
    schema_root: Path,
    mode: str,
    repository_root: Path | None = None,
) -> DatasetRelease:
    """Verify an official 5/15 release or an explicit synthetic 50/150 fixture."""

    if mode not in {OFFICIAL_MODE, SYNTHETIC_MODE}:
        raise ValidationError(f"unsupported Dataset adapter mode: {mode}")
    zip_path = ensure_plain_root(zip_path.parent) / zip_path.name
    pin_path = ensure_plain_root(pin_path.parent) / pin_path.name
    if not zip_path.is_file() or not pin_path.is_file():
        raise ValidationError("Dataset ZIP and pin must both exist")
    zip_raw = zip_path.read_bytes()
    pin_raw = pin_path.read_bytes()
    pin = loads_strict(pin_raw, require_object=True)
    _verify_pin(pin, zip_raw=zip_raw, mode=mode)
    members = _load_safe_zip(zip_path, expected_count=pin["artifact"]["entry_count"])
    manifest_raw = _member(members, "manifest.json")
    manifest = loads_strict(manifest_raw, require_object=True)
    _verify_manifest(manifest, manifest_raw=manifest_raw, pin=pin, members=members, mode=mode)
    index_path = (
        "candidate_index_15.json"
        if mode == OFFICIAL_MODE
        else _string(manifest.get("candidate_index_path"), "manifest.candidate_index_path")
    )
    index_raw = _member(members, index_path)
    index = loads_strict(index_raw, require_object=True)
    _verify_self_hash(index, "candidate index")
    candidates = _load_candidates(
        members,
        index=index,
        manifest=manifest,
        schema_root=schema_root,
    )
    _verify_counts(pin, manifest, candidates, mode=mode)
    git_raw: bytes | None = None
    git_receipt: dict[str, Any] | None = None
    if mode == OFFICIAL_MODE:
        if git_receipt_path is None:
            raise ValidationError("official Dataset input requires its Git source receipt")
        git_receipt_path = ensure_plain_root(git_receipt_path.parent) / git_receipt_path.name
        git_raw = git_receipt_path.read_bytes()
        git_receipt = loads_strict(git_raw, require_object=True)
        _verify_git_receipt(
            git_receipt,
            raw=git_raw,
            pin=pin,
            zip_raw=zip_raw,
            repository_root=repository_root,
        )
    elif git_receipt_path is not None:
        raise ValidationError("synthetic Dataset input cannot claim a Git source receipt")
    return DatasetRelease(
        mode=mode,
        zip_path=zip_path,
        zip_raw=zip_raw,
        pin_path=pin_path,
        pin_raw=pin_raw,
        pin=pin,
        manifest_raw=manifest_raw,
        manifest=manifest,
        index_raw=index_raw,
        index=index,
        git_receipt_path=git_receipt_path,
        git_receipt_raw=git_raw,
        git_receipt=git_receipt,
        candidates=tuple(candidates),
    )


def _verify_pin(pin: Mapping[str, Any], *, zip_raw: bytes, mode: str) -> None:
    expected_schema = OFFICIAL_PIN_SCHEMA if mode == OFFICIAL_MODE else SYNTHETIC_PIN_SCHEMA
    if pin.get("schema_id") != expected_schema:
        raise ValidationError("Dataset pin schema does not match adapter mode")
    _verify_self_hash(pin, "Dataset pin")
    artifact = _mapping(pin.get("artifact"), "Dataset pin artifact")
    if artifact.get("physical_sha256") != sha256_bytes(zip_raw):
        raise IntegrityError("Dataset pin does not bind the ZIP bytes")
    if artifact.get("size_bytes") != len(zip_raw):
        raise IntegrityError("Dataset pin ZIP size mismatch")
    if not isinstance(artifact.get("entry_count"), int) or artifact["entry_count"] <= 0:
        raise ValidationError("Dataset pin entry_count must be positive")
    boundaries = _mapping(pin.get("boundaries"), "Dataset pin boundaries")
    for field in ("provider_calls", "network_calls", "auto_approved", "certificates"):
        if boundaries.get(field) != 0:
            raise ValidationError(f"Dataset pin violates zero-provider boundary: {field}")
    if boundaries.get("final_glossary_decision") is not None:
        raise ValidationError("Dataset pin contains a final glossary decision")
    if mode == OFFICIAL_MODE:
        if pin["integrity"]["self_sha256"] != OFFICIAL_PIN_SELF_SHA256:
            raise IntegrityError("official Dataset pin authority hash mismatch")
        if artifact["physical_sha256"] != OFFICIAL_ZIP_SHA256:
            raise IntegrityError("official Dataset ZIP authority hash mismatch")
        downstream = _mapping(pin.get("downstream"), "Dataset pin downstream")
        harness = _mapping(downstream.get("system_integration_harness"), "Harness policy")
        if harness.get("status") != "PREFLIGHT_AND_PIN_ONLY_UNTIL_C_E_ACCEPTED":
            raise ValidationError("official Dataset pin does not preserve the Harness HOLD")
    elif pin.get("status") != "SYNTHETIC_LOCAL_CONFORMANCE":
        raise ValidationError("synthetic Dataset pin has a non-conformance status")


def _verify_manifest(
    manifest: Mapping[str, Any],
    *,
    manifest_raw: bytes,
    pin: Mapping[str, Any],
    members: Mapping[str, bytes],
    mode: str,
) -> None:
    expected_schema = (
        "D2LOfficial5SensePilotManifestV1"
        if mode == OFFICIAL_MODE
        else SYNTHETIC_MANIFEST_SCHEMA
    )
    if manifest.get("schema_id") != expected_schema or manifest.get("schema_version") != "1.0.0":
        raise ValidationError("unsupported Dataset release manifest")
    clone = copy.deepcopy(dict(manifest))
    declared = clone.pop("manifest_sha256", None)
    computed = sha256_bytes(canonical_bytes(clone))
    if declared != computed:
        raise IntegrityError("Dataset release manifest self hash mismatch")
    pin_manifest = _mapping(pin.get("manifest"), "Dataset pin manifest")
    if pin_manifest.get("self_sha256") != declared:
        raise IntegrityError("Dataset pin and manifest self hashes differ")
    if pin_manifest.get("physical_sha256") != sha256_bytes(manifest_raw):
        raise IntegrityError("Dataset pin and manifest physical hashes differ")
    if mode == OFFICIAL_MODE and declared != OFFICIAL_MANIFEST_SELF_SHA256:
        raise IntegrityError("official Dataset manifest authority hash mismatch")
    if manifest.get("provider_call_count") != 0 or manifest.get("final_glossary_decision") is not None:
        raise ValidationError("Dataset manifest violates zero-provider decision neutrality")
    checksums = _parse_checksums(_member(members, "CHECKSUMS.sha256"))
    expected_checksum_paths = set(members) - {"CHECKSUMS.sha256"}
    if set(checksums) != expected_checksum_paths:
        raise IntegrityError("Dataset ZIP checksum member set mismatch")
    for name, expected in checksums.items():
        if sha256_bytes(members[name]) != expected:
            raise IntegrityError(f"Dataset ZIP checksum mismatch: {name}")
    files = _mapping(manifest.get("files"), "Dataset manifest files")
    expected_files = set(members) - {"manifest.json", "CHECKSUMS.sha256"}
    if set(files) != expected_files:
        raise IntegrityError("Dataset manifest file inventory mismatch")
    for name, metadata_value in files.items():
        metadata = _mapping(metadata_value, f"Dataset manifest file {name}")
        if metadata.get("sha256") != sha256_bytes(members[name]):
            raise IntegrityError(f"Dataset manifest hash mismatch: {name}")
        if metadata.get("size_bytes") != len(members[name]):
            raise IntegrityError(f"Dataset manifest size mismatch: {name}")


def _load_candidates(
    members: Mapping[str, bytes],
    *,
    index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    schema_root: Path,
) -> list[DatasetCandidate]:
    entries = index.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("Dataset candidate index must contain entries")
    if index.get("candidate_count") != len(entries):
        raise ValidationError("Dataset candidate index count mismatch")
    if index.get("final_glossary_decision") is not None:
        raise ValidationError("Dataset candidate index contains a final decision")
    result: list[DatasetCandidate] = []
    candidate_ids: set[str] = set()
    candidate_keys: set[str] = set()
    for offset, entry_value in enumerate(entries):
        entry = _mapping(entry_value, f"candidate index entry {offset}")
        effective_path = _safe_member_path(entry.get("effective_sense_path"))
        frozen_path = _safe_member_path(entry.get("frozen_candidate_path"))
        constraint_path = _safe_member_path(entry.get("constraint_evidence_path"))
        effective_raw = _member(members, effective_path)
        frozen_raw = _member(members, frozen_path)
        constraint_raw = _member(members, constraint_path)
        effective = loads_strict(effective_raw, require_object=True)
        frozen = loads_strict(frozen_raw, require_object=True)
        constraint = loads_strict(constraint_raw, require_object=True)
        for value, schema_id, label in (
            (effective, "EffectiveSenseContractV1", effective_path),
            (frozen, "FrozenCandidateContractV1", frozen_path),
            (constraint, "ConstraintEvidencePackageV1", constraint_path),
        ):
            if value.get("schema_id") != schema_id or value.get("schema_version") != "1.1.0":
                raise ValidationError(f"Dataset contract schema mismatch: {label}")
            _verify_self_hash(value, label)
            validate_contract_schema(value, schema_root)
        identity = CandidateIdentity.from_package(frozen)
        if CandidateIdentity.from_package(constraint) != identity:
            raise ValidationError(f"Dataset candidate identity mismatch: {identity.candidate_id}")
        if frozen.get("binding_status") != "COMPLETE" or constraint.get("binding_status") != "COMPLETE":
            raise ValidationError(f"Dataset candidate is not COMPLETE: {identity.candidate_id}")
        if identity.candidate_id in candidate_ids or identity.key in candidate_keys:
            raise ValidationError(f"duplicate Dataset candidate: {identity.candidate_id}")
        candidate_ids.add(identity.candidate_id)
        candidate_keys.add(identity.key)
        _match_entry(entry, identity, effective, frozen, constraint)
        result.append(
            DatasetCandidate(
                identity=identity,
                effective_path=effective_path,
                effective_raw=effective_raw,
                effective=effective,
                frozen_path=frozen_path,
                frozen_raw=frozen_raw,
                frozen=frozen,
                constraint_path=constraint_path,
                constraint_raw=constraint_raw,
                constraint=constraint,
            )
        )
    return sorted(result, key=lambda item: item.identity.candidate_id)


def _match_entry(
    entry: Mapping[str, Any],
    identity: CandidateIdentity,
    effective: Mapping[str, Any],
    frozen: Mapping[str, Any],
    constraint: Mapping[str, Any],
) -> None:
    for field in ("candidate_id", "candidate_version", "candidate_vi", "source_term", "sense_id"):
        if entry.get(field) != identity.as_dict()[field]:
            raise ValidationError(f"candidate index identity mismatch: {field}")
    if entry.get("input_contract_sha256") != identity.input_contract_sha256:
        raise ValidationError("candidate index input contract mismatch")
    expected_hashes = {
        "effective_sense_sha256": effective["integrity"]["self_sha256"],
        "frozen_candidate_sha256": frozen["integrity"]["self_sha256"],
        "constraint_evidence_sha256": constraint["integrity"]["self_sha256"],
    }
    for field, expected in expected_hashes.items():
        if entry.get(field) != expected:
            raise IntegrityError(f"candidate index package hash mismatch: {field}")
    if effective["integrity"]["self_sha256"] != identity.effective_sense_contract_sha256:
        raise ValidationError("effective sense hash is not bound to candidate identity")
    for field in ("source_term", "sense_id", "scope_id", "sense_inventory_version"):
        if effective.get(field) != identity.as_dict()[field]:
            raise ValidationError(f"effective sense identity mismatch: {field}")
    if effective.get("parent_dataset_manifest_sha256") != identity.dataset_manifest_sha256:
        raise ValidationError("effective sense Dataset identity mismatch")


def _verify_counts(
    pin: Mapping[str, Any],
    manifest: Mapping[str, Any],
    candidates: list[DatasetCandidate],
    *,
    mode: str,
) -> None:
    candidate_count = len(candidates)
    sense_count = len({item.identity.sense_id for item in candidates})
    counts = _mapping(manifest.get("counts"), "Dataset manifest counts")
    if counts.get("candidate") != candidate_count or counts.get("selected_sense") != sense_count:
        raise ValidationError("Dataset manifest candidate/sense counts mismatch")
    if counts.get("frozen_candidate_contract") != candidate_count:
        raise ValidationError("Dataset frozen candidate count mismatch")
    if counts.get("constraint_evidence_package") != candidate_count:
        raise ValidationError("Dataset constraint package count mismatch")
    if counts.get("effective_sense_contract") != sense_count:
        raise ValidationError("Dataset effective sense count mismatch")
    pin_counts = _mapping(pin.get("counts"), "Dataset pin counts")
    if pin_counts.get("frozen_candidate_contracts") != candidate_count:
        raise ValidationError("Dataset pin candidate count mismatch")
    if pin_counts.get("constraint_evidence_packages") != candidate_count:
        raise ValidationError("Dataset pin constraint count mismatch")
    if pin_counts.get("effective_sense_contracts") != sense_count:
        raise ValidationError("Dataset pin sense count mismatch")
    expected = (5, 15) if mode == OFFICIAL_MODE else (50, 150)
    if (sense_count, candidate_count) != expected:
        raise ValidationError(
            f"Dataset profile mismatch: expected {expected[0]}/{expected[1]}, "
            f"got {sense_count}/{candidate_count}"
        )
    per_sense: dict[str, int] = {}
    for item in candidates:
        per_sense[item.identity.sense_id] = per_sense.get(item.identity.sense_id, 0) + 1
    if set(per_sense.values()) != {3}:
        raise ValidationError("Dataset profile requires exactly three candidates per sense")


def _verify_git_receipt(
    receipt: Mapping[str, Any],
    *,
    raw: bytes,
    pin: Mapping[str, Any],
    zip_raw: bytes,
    repository_root: Path | None,
) -> None:
    _verify_self_hash(receipt, "Dataset Git receipt")
    producer = _mapping(receipt.get("producer"), "Dataset Git receipt producer")
    if producer.get("commit") != OFFICIAL_PRODUCER_COMMIT:
        raise ValidationError("Dataset Git receipt producer commit mismatch")
    exclusions = _mapping(receipt.get("version_exclusions"), "Dataset Git exclusions")
    if exclusions.get("later_dataset_commit_not_accepted_by_this_receipt") != OFFICIAL_EXCLUDED_COMMIT:
        raise ValidationError("Dataset Git receipt does not preserve the excluded commit")
    pin_git = _mapping(pin.get("producer_git"), "Dataset pin producer_git")
    if pin_git.get("receipt_physical_sha256") != sha256_bytes(raw):
        raise IntegrityError("Dataset pin does not bind Git receipt bytes")
    if pin_git.get("receipt_self_sha256") != receipt["integrity"]["self_sha256"]:
        raise IntegrityError("Dataset pin does not bind Git receipt identity")
    artifact = _mapping(receipt.get("artifact"), "Dataset Git receipt artifact")
    if artifact.get("physical_sha256") != sha256_bytes(zip_raw):
        raise IntegrityError("Dataset Git receipt does not bind ZIP bytes")
    if repository_root is None:
        return
    repository_root = ensure_plain_root(repository_root)
    git_path = _string(artifact.get("git_path"), "Dataset Git artifact path")
    try:
        produced = subprocess.run(
            ["git", "-C", str(repository_root), "show", f"{OFFICIAL_PRODUCER_COMMIT}:{git_path}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise IntegrityError("cannot verify Dataset producer Git object") from exc
    if produced != zip_raw:
        raise IntegrityError("Dataset ZIP differs from the pinned producer Git object")


def _load_safe_zip(path: Path, *, expected_count: int) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    folded: set[str] = set()
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise IntegrityError("Dataset ZIP CRC verification failed")
            infos = archive.infolist()
            if len(infos) != expected_count:
                raise IntegrityError("Dataset ZIP entry count mismatch")
            for info in infos:
                name = _safe_member_path(info.filename)
                if name in result or name.casefold() in folded:
                    raise IntegrityError(f"duplicate or case-confusable ZIP member: {name}")
                if info.is_dir() or info.flag_bits & 0x1:
                    raise IntegrityError(f"unsupported ZIP member: {name}")
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise IntegrityError(f"ZIP symlink is forbidden: {name}")
                result[name] = archive.read(info)
                folded.add(name.casefold())
    except (OSError, zipfile.BadZipFile) as exc:
        raise IntegrityError(f"cannot read Dataset ZIP: {exc}") from exc
    return result


def _parse_checksums(raw: bytes) -> dict[str, str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntegrityError("Dataset CHECKSUMS is not UTF-8") from exc
    if not text.endswith("\n"):
        raise IntegrityError("Dataset CHECKSUMS must end with LF")
    result: dict[str, str] = {}
    paths: list[str] = []
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if match is None:
            raise IntegrityError("malformed Dataset checksum line")
        path = _safe_member_path(match.group(2))
        if path in result:
            raise IntegrityError("duplicate Dataset checksum path")
        result[path] = match.group(1)
        paths.append(path)
    if paths != sorted(paths):
        raise IntegrityError("Dataset checksums are not sorted")
    return result


def _verify_self_hash(value: Mapping[str, Any], label: str) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or integrity.get("self_sha256") != self_sha256(value):
        raise IntegrityError(f"{label} self hash mismatch")


def _member(members: Mapping[str, bytes], name: str) -> bytes:
    try:
        return members[name]
    except KeyError as exc:
        raise IntegrityError(f"Dataset ZIP member is missing: {name}") from exc


def _safe_member_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise IntegrityError("unsafe Dataset ZIP member path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise IntegrityError(f"unsafe Dataset ZIP member path: {value}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise IntegrityError(f"unsafe Dataset ZIP member path: {value}")
    if len(path.parts[0]) >= 2 and path.parts[0][1:2] == ":":
        raise IntegrityError(f"drive-qualified Dataset ZIP member: {value}")
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


__all__ = [
    "DatasetCandidate",
    "DatasetRelease",
    "OFFICIAL_MODE",
    "SYNTHETIC_MODE",
    "load_dataset_release",
]
