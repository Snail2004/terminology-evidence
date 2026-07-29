"""Fail-closed consumer for Dataset-owned Frozen Candidate release sets."""

from __future__ import annotations

import copy
import hashlib
import json
import re
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
OFFICIAL_DATASET_PRODUCER_COMPONENT_ID = "candidate-freezer"
OFFICIAL_PILOT_MEMBER_COUNT = 15
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class OfficialFrozenCandidateSet:
    manifest: dict[str, Any]
    receipt: dict[str, Any]
    candidates: tuple[dict[str, Any], ...]
    manifest_physical_sha256: str
    receipt_physical_sha256: str


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
    "OFFICIAL_PILOT_MEMBER_COUNT",
    "OFFICIAL_SET_MANIFEST_SCHEMA_ID",
    "OFFICIAL_SET_RECEIPT_SCHEMA_ID",
    "OFFICIAL_SET_SCHEMA_VERSION",
    "OfficialFrozenCandidateSet",
    "load_official_frozen_candidate_set",
]
