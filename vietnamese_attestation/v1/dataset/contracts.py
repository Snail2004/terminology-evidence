from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .archive import DatasetAdapterError


ADAPTER_SCHEMA_ID = "VietnameseAttestationDatasetAdapterV1"
ADAPTER_SCHEMA_VERSION = "1.0.0"
ADAPTER_POLICY_ID = "d2l_vietnamese_attestation_real_dataset_adapter_v1"
CANDIDATE_SCHEMA_ID = "VietnameseAttestationCandidateInputV1"
CANDIDATE_SCHEMA_VERSION = "1.0.0"
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def seal_adapter_candidate(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(dict(payload))
    row["schema_id"] = CANDIDATE_SCHEMA_ID
    row["schema_version"] = CANDIDATE_SCHEMA_VERSION
    row["policy_id"] = ADAPTER_POLICY_ID
    row["integrity"] = {"adapter_candidate_sha256": "0" * 64}
    row["integrity"]["adapter_candidate_sha256"] = _sha_without_nested(
        row, ("integrity", "adapter_candidate_sha256")
    )
    return validate_adapter_candidate(row)


def validate_adapter_candidate(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = _mapping(payload, "$.candidate")
    _exact_keys(
        row,
        {
            "schema_id",
            "schema_version",
            "policy_id",
            "candidate_id",
            "candidate_version",
            "term_id",
            "source_term",
            "candidate_vi",
            "sense_id",
            "scope_id",
            "shared_context_set_id",
            "source_candidate_slot_id",
            "identity_binding",
            "sense_contract",
            "formation",
            "context_provenance",
            "known_vietnamese_surfaces",
            "domain_anchors",
            "authority",
            "final_glossary_decision",
            "integrity",
        },
        "$.candidate",
    )
    _equal(row, "schema_id", CANDIDATE_SCHEMA_ID, "$.candidate")
    _equal(
        row, "schema_version", CANDIDATE_SCHEMA_VERSION, "$.candidate"
    )
    _equal(row, "policy_id", ADAPTER_POLICY_ID, "$.candidate")
    candidate_id = _string(row["candidate_id"], "$.candidate.candidate_id")
    candidate_version = _sha256(
        row["candidate_version"], "$.candidate.candidate_version"
    )
    identity = _identity_binding(row["identity_binding"])
    if identity["candidate_id"] != candidate_id:
        _fail("identity_mismatch", "$.candidate.identity_binding.candidate_id")
    if identity["candidate_version"] != candidate_version:
        _fail(
            "identity_mismatch",
            "$.candidate.identity_binding.candidate_version",
        )
    for field in ("sense_id", "scope_id"):
        value = _string(row[field], f"$.candidate.{field}")
        if identity[field] != value:
            _fail("identity_mismatch", f"$.candidate.identity_binding.{field}")
    sense_contract = _sense_contract(row["sense_contract"])
    formation = _formation(row["formation"])
    context_provenance = _context_provenance(row["context_provenance"])
    known_surfaces = _known_surfaces(row["known_vietnamese_surfaces"])
    domain_anchors = _domain_anchors(row["domain_anchors"])
    authority = _authority(row["authority"])
    if row["final_glossary_decision"] is not None:
        _fail(
            "final_authority_forbidden",
            "$.candidate.final_glossary_decision",
        )
    integrity = _mapping(row["integrity"], "$.candidate.integrity")
    _exact_keys(
        integrity, {"adapter_candidate_sha256"}, "$.candidate.integrity"
    )
    expected_hash = _sha256(
        integrity["adapter_candidate_sha256"],
        "$.candidate.integrity.adapter_candidate_sha256",
    )
    normalized = {
        "schema_id": CANDIDATE_SCHEMA_ID,
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "policy_id": ADAPTER_POLICY_ID,
        "candidate_id": candidate_id,
        "candidate_version": candidate_version,
        "term_id": _string(row["term_id"], "$.candidate.term_id"),
        "source_term": _string(
            row["source_term"], "$.candidate.source_term"
        ),
        "candidate_vi": _string(
            row["candidate_vi"], "$.candidate.candidate_vi"
        ),
        "sense_id": identity["sense_id"],
        "scope_id": identity["scope_id"],
        "shared_context_set_id": _string(
            row["shared_context_set_id"],
            "$.candidate.shared_context_set_id",
        ),
        "source_candidate_slot_id": _string(
            row["source_candidate_slot_id"],
            "$.candidate.source_candidate_slot_id",
        ),
        "identity_binding": identity,
        "sense_contract": sense_contract,
        "formation": formation,
        "context_provenance": context_provenance,
        "known_vietnamese_surfaces": known_surfaces,
        "domain_anchors": domain_anchors,
        "authority": authority,
        "final_glossary_decision": None,
        "integrity": {"adapter_candidate_sha256": expected_hash},
    }
    if sense_contract["sense_inventory_version"] != identity[
        "sense_inventory_version"
    ]:
        _fail(
            "identity_mismatch",
            "$.candidate.sense_contract.sense_inventory_version",
        )
    if _sha_without_nested(
        normalized, ("integrity", "adapter_candidate_sha256")
    ) != expected_hash:
        _fail(
            "candidate_self_hash",
            "$.candidate.integrity.adapter_candidate_sha256",
        )
    return normalized


def seal_adapter_package(payload: Mapping[str, Any]) -> dict[str, Any]:
    package = copy.deepcopy(dict(payload))
    package["schema_id"] = ADAPTER_SCHEMA_ID
    package["schema_version"] = ADAPTER_SCHEMA_VERSION
    package["policy_id"] = ADAPTER_POLICY_ID
    package["integrity"] = {"adapter_package_sha256": "0" * 64}
    package["integrity"]["adapter_package_sha256"] = _sha_without_nested(
        package, ("integrity", "adapter_package_sha256")
    )
    return validate_adapter_package(package)


def validate_adapter_package(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = _mapping(payload, "$")
    _exact_keys(
        root,
        {
            "schema_id",
            "schema_version",
            "policy_id",
            "source",
            "mode",
            "authority",
            "unavailable_fields",
            "candidates",
            "receipt",
            "final_glossary_decision",
            "integrity",
        },
        "$",
    )
    _equal(root, "schema_id", ADAPTER_SCHEMA_ID, "$")
    _equal(root, "schema_version", ADAPTER_SCHEMA_VERSION, "$")
    _equal(root, "policy_id", ADAPTER_POLICY_ID, "$")
    source = _source(root["source"])
    mode = _enum(
        root["mode"],
        {"DEVELOPMENT_ZERO_API", "VALIDATION_READY_ZERO_API"},
        "$.mode",
    )
    authority = _authority(root["authority"])
    unavailable = _unavailable(root["unavailable_fields"])
    raw_candidates = _list(root["candidates"], "$.candidates")
    candidates = [validate_adapter_candidate(row) for row in raw_candidates]
    candidate_ids = [row["candidate_id"] for row in candidates]
    if candidate_ids != sorted(candidate_ids) or len(candidate_ids) != len(
        set(candidate_ids)
    ):
        _fail("candidate_order", "$.candidates")
    receipt = _receipt(root["receipt"])
    if root["final_glossary_decision"] is not None:
        _fail("final_authority_forbidden", "$.final_glossary_decision")
    integrity = _mapping(root["integrity"], "$.integrity")
    _exact_keys(integrity, {"adapter_package_sha256"}, "$.integrity")
    expected_hash = _sha256(
        integrity["adapter_package_sha256"],
        "$.integrity.adapter_package_sha256",
    )
    normalized = {
        "schema_id": ADAPTER_SCHEMA_ID,
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "policy_id": ADAPTER_POLICY_ID,
        "source": source,
        "mode": mode,
        "authority": authority,
        "unavailable_fields": unavailable,
        "candidates": candidates,
        "receipt": receipt,
        "final_glossary_decision": None,
        "integrity": {"adapter_package_sha256": expected_hash},
    }
    _validate_receipt_bindings(normalized)
    if _sha_without_nested(
        normalized, ("integrity", "adapter_package_sha256")
    ) != expected_hash:
        _fail("package_self_hash", "$.integrity.adapter_package_sha256")
    return normalized


def _source(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.source")
    _exact_keys(
        row,
        {
            "schema_id",
            "schema_version",
            "zip_sha256",
            "manifest_file_sha256",
            "manifest_sha256",
            "dataset_version",
            "parent_dataset_manifest_sha256",
        },
        "$.source",
    )
    parent = row["parent_dataset_manifest_sha256"]
    return {
        "schema_id": _string(row["schema_id"], "$.source.schema_id"),
        "schema_version": _string(
            row["schema_version"], "$.source.schema_version"
        ),
        "zip_sha256": _sha256(row["zip_sha256"], "$.source.zip_sha256"),
        "manifest_file_sha256": _sha256(
            row["manifest_file_sha256"], "$.source.manifest_file_sha256"
        ),
        "manifest_sha256": _sha256(
            row["manifest_sha256"], "$.source.manifest_sha256"
        ),
        "dataset_version": _string(
            row["dataset_version"], "$.source.dataset_version"
        ),
        "parent_dataset_manifest_sha256": (
            None
            if parent is None
            else _sha256(parent, "$.source.parent_dataset_manifest_sha256")
        ),
    }


def _identity_binding(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.candidate.identity_binding")
    _exact_keys(
        row,
        {
            "candidate_id",
            "candidate_version",
            "sense_id",
            "scope_id",
            "sense_inventory_version",
            "dataset_manifest_sha256",
            "parent_dataset_manifest_sha256",
            "effective_sense_contract_sha256",
        },
        "$.candidate.identity_binding",
    )
    parent = row["parent_dataset_manifest_sha256"]
    if row["effective_sense_contract_sha256"] is not None:
        _fail(
            "effective_contract_forbidden",
            "$.candidate.identity_binding.effective_sense_contract_sha256",
        )
    return {
        "candidate_id": _string(
            row["candidate_id"], "$.candidate.identity_binding.candidate_id"
        ),
        "candidate_version": _sha256(
            row["candidate_version"],
            "$.candidate.identity_binding.candidate_version",
        ),
        "sense_id": _string(
            row["sense_id"], "$.candidate.identity_binding.sense_id"
        ),
        "scope_id": _string(
            row["scope_id"], "$.candidate.identity_binding.scope_id"
        ),
        "sense_inventory_version": _string(
            row["sense_inventory_version"],
            "$.candidate.identity_binding.sense_inventory_version",
        ),
        "dataset_manifest_sha256": _sha256(
            row["dataset_manifest_sha256"],
            "$.candidate.identity_binding.dataset_manifest_sha256",
        ),
        "parent_dataset_manifest_sha256": (
            None
            if parent is None
            else _sha256(
                parent,
                "$.candidate.identity_binding.parent_dataset_manifest_sha256",
            )
        ),
        "effective_sense_contract_sha256": None,
    }


def _sense_contract(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.candidate.sense_contract")
    _exact_keys(
        row,
        {
            "definition_en",
            "part_of_speech",
            "review_status",
            "term_sense_sha256",
            "sense_inventory_version",
            "effective_sense_contract_sha256",
        },
        "$.candidate.sense_contract",
    )
    if row["effective_sense_contract_sha256"] is not None:
        _fail(
            "effective_contract_forbidden",
            "$.candidate.sense_contract.effective_sense_contract_sha256",
        )
    return {
        "definition_en": _string(
            row["definition_en"], "$.candidate.sense_contract.definition_en"
        ),
        "part_of_speech": _string(
            row["part_of_speech"],
            "$.candidate.sense_contract.part_of_speech",
        ),
        "review_status": _enum(
            row["review_status"],
            {"PENDING_HUMAN_REVIEW"},
            "$.candidate.sense_contract.review_status",
        ),
        "term_sense_sha256": _sha256(
            row["term_sense_sha256"],
            "$.candidate.sense_contract.term_sense_sha256",
        ),
        "sense_inventory_version": _string(
            row["sense_inventory_version"],
            "$.candidate.sense_contract.sense_inventory_version",
        ),
        "effective_sense_contract_sha256": None,
    }


def _formation(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.candidate.formation")
    _exact_keys(
        row,
        {"method", "provenance", "applicability"},
        "$.candidate.formation",
    )
    provenance = _list(row["provenance"], "$.candidate.formation.provenance")
    for index, item in enumerate(provenance):
        _mapping(item, f"$.candidate.formation.provenance[{index}]")
    return {
        "method": _string(row["method"], "$.candidate.formation.method"),
        "provenance": copy.deepcopy(provenance),
        "applicability": copy.deepcopy(row["applicability"]),
    }


def _context_provenance(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.candidate.context_provenance")
    _exact_keys(
        row,
        {
            "primary_context_ids",
            "backup_context_ids",
            "contrastive_context_ids",
            "usage_policy",
        },
        "$.candidate.context_provenance",
    )
    return {
        "primary_context_ids": _string_list(
            row["primary_context_ids"],
            "$.candidate.context_provenance.primary_context_ids",
        ),
        "backup_context_ids": _string_list(
            row["backup_context_ids"],
            "$.candidate.context_provenance.backup_context_ids",
        ),
        "contrastive_context_ids": _string_list(
            row["contrastive_context_ids"],
            "$.candidate.context_provenance.contrastive_context_ids",
        ),
        "usage_policy": _enum(
            row["usage_policy"],
            {"PROVENANCE_ONLY_NOT_ATTESTATION_EVIDENCE"},
            "$.candidate.context_provenance.usage_policy",
        ),
    }


def _known_surfaces(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.candidate.known_vietnamese_surfaces")
    _exact_keys(
        row,
        {
            "status",
            "canonical",
            "validated_variants",
            "rejected_variants",
            "source_term_surfaces_usage",
        },
        "$.candidate.known_vietnamese_surfaces",
    )
    for field in ("canonical", "validated_variants", "rejected_variants"):
        if row[field] is not None:
            _fail(
                "invented_surface_authority",
                f"$.candidate.known_vietnamese_surfaces.{field}",
            )
    return {
        "status": _enum(
            row["status"],
            {"UNAVAILABLE_NOT_PROVIDED"},
            "$.candidate.known_vietnamese_surfaces.status",
        ),
        "canonical": None,
        "validated_variants": None,
        "rejected_variants": None,
        "source_term_surfaces_usage": _enum(
            row["source_term_surfaces_usage"],
            {"ENGLISH_SOURCE_ONLY_NOT_MAPPED"},
            "$.candidate.known_vietnamese_surfaces.source_term_surfaces_usage",
        ),
    }


def _domain_anchors(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.candidate.domain_anchors")
    _exact_keys(
        row,
        {"status", "domain_profile_id", "vi_anchors", "en_anchors"},
        "$.candidate.domain_anchors",
    )
    for field in ("domain_profile_id", "vi_anchors", "en_anchors"):
        if row[field] is not None:
            _fail(
                "invented_domain_authority",
                f"$.candidate.domain_anchors.{field}",
            )
    return {
        "status": _enum(
            row["status"],
            {"UNAVAILABLE_SCOPE_ID_ONLY"},
            "$.candidate.domain_anchors.status",
        ),
        "domain_profile_id": None,
        "vi_anchors": None,
        "en_anchors": None,
    }


def _authority(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.authority")
    _exact_keys(
        row,
        {
            "official",
            "calibrated",
            "human_review_complete",
            "candidate_is_human_gold",
            "final_decision_authority",
        },
        "$.authority",
    )
    expected = {
        "official": False,
        "calibrated": False,
        "human_review_complete": False,
        "candidate_is_human_gold": False,
        "final_decision_authority": "GLOBAL_TERMINOLOGY_VALIDATOR_ONLY",
    }
    if dict(row) != expected:
        _fail("development_authority", "$.authority")
    return expected


def _unavailable(value: Any) -> dict[str, str]:
    row = _mapping(value, "$.unavailable_fields")
    expected = {
        "domain_anchors": "UNAVAILABLE_SCOPE_ID_ONLY",
        "human_gold": "UNAVAILABLE_HUMAN_REVIEW_REQUIRED",
        "known_vietnamese_surfaces": "UNAVAILABLE_NOT_PROVIDED",
    }
    if dict(row) != expected:
        _fail("unavailable_fields", "$.unavailable_fields")
    return expected


def _receipt(value: Any) -> dict[str, Any]:
    row = _mapping(value, "$.receipt")
    fields = {
        "agent",
        "adapter_schema_id",
        "adapter_schema_version",
        "adapter_policy_id",
        "source_schema_id",
        "source_schema_version",
        "source_zip_sha256",
        "source_manifest_file_sha256",
        "source_manifest_sha256",
        "parent_dataset_manifest_sha256",
        "effective_sense_contract_sha256",
        "review_artifact_sha256",
        "term_sense_count",
        "candidate_count",
        "context_count",
        "mode",
        "provider_call_count",
        "final_glossary_decision",
    }
    _exact_keys(row, fields, "$.receipt")
    for field in (
        "effective_sense_contract_sha256",
        "review_artifact_sha256",
        "final_glossary_decision",
    ):
        if row[field] is not None:
            _fail("receipt_authority", f"$.receipt.{field}")
    parent = row["parent_dataset_manifest_sha256"]
    return {
        "agent": _enum(row["agent"], {"E"}, "$.receipt.agent"),
        "adapter_schema_id": _enum(
            row["adapter_schema_id"],
            {ADAPTER_SCHEMA_ID},
            "$.receipt.adapter_schema_id",
        ),
        "adapter_schema_version": _enum(
            row["adapter_schema_version"],
            {ADAPTER_SCHEMA_VERSION},
            "$.receipt.adapter_schema_version",
        ),
        "adapter_policy_id": _enum(
            row["adapter_policy_id"],
            {ADAPTER_POLICY_ID},
            "$.receipt.adapter_policy_id",
        ),
        "source_schema_id": _string(
            row["source_schema_id"], "$.receipt.source_schema_id"
        ),
        "source_schema_version": _string(
            row["source_schema_version"],
            "$.receipt.source_schema_version",
        ),
        "source_zip_sha256": _sha256(
            row["source_zip_sha256"], "$.receipt.source_zip_sha256"
        ),
        "source_manifest_file_sha256": _sha256(
            row["source_manifest_file_sha256"],
            "$.receipt.source_manifest_file_sha256",
        ),
        "source_manifest_sha256": _sha256(
            row["source_manifest_sha256"],
            "$.receipt.source_manifest_sha256",
        ),
        "parent_dataset_manifest_sha256": (
            None
            if parent is None
            else _sha256(
                parent, "$.receipt.parent_dataset_manifest_sha256"
            )
        ),
        "effective_sense_contract_sha256": None,
        "review_artifact_sha256": None,
        "term_sense_count": _nonnegative_int(
            row["term_sense_count"], "$.receipt.term_sense_count"
        ),
        "candidate_count": _nonnegative_int(
            row["candidate_count"], "$.receipt.candidate_count"
        ),
        "context_count": _nonnegative_int(
            row["context_count"], "$.receipt.context_count"
        ),
        "mode": _enum(
            row["mode"],
            {"DEVELOPMENT_ZERO_API", "VALIDATION_READY_ZERO_API"},
            "$.receipt.mode",
        ),
        "provider_call_count": _nonnegative_int(
            row["provider_call_count"], "$.receipt.provider_call_count"
        ),
        "final_glossary_decision": None,
    }


def _validate_receipt_bindings(package: Mapping[str, Any]) -> None:
    source = package["source"]
    receipt = package["receipt"]
    bindings = {
        "source_schema_id": "schema_id",
        "source_schema_version": "schema_version",
        "source_zip_sha256": "zip_sha256",
        "source_manifest_file_sha256": "manifest_file_sha256",
        "source_manifest_sha256": "manifest_sha256",
        "parent_dataset_manifest_sha256": "parent_dataset_manifest_sha256",
    }
    for receipt_field, source_field in bindings.items():
        if receipt[receipt_field] != source[source_field]:
            _fail("receipt_binding", f"$.receipt.{receipt_field}")
    if receipt["mode"] != package["mode"]:
        _fail("receipt_binding", "$.receipt.mode")
    if receipt["candidate_count"] != len(package["candidates"]):
        _fail("receipt_binding", "$.receipt.candidate_count")
    if receipt["provider_call_count"] != 0:
        _fail("provider_call_forbidden", "$.receipt.provider_call_count")
    for index, candidate in enumerate(package["candidates"]):
        identity = candidate["identity_binding"]
        if identity["dataset_manifest_sha256"] != source["manifest_sha256"]:
            _fail(
                "candidate_source_binding",
                f"$.candidates[{index}].identity_binding.dataset_manifest_sha256",
            )
        if identity["parent_dataset_manifest_sha256"] != source[
            "parent_dataset_manifest_sha256"
        ]:
            _fail(
                "candidate_source_binding",
                f"$.candidates[{index}].identity_binding.parent_dataset_manifest_sha256",
            )


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("type", path, "object required")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("type", path, "array required")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("type", path, "non-empty string required")
    return value


def _sha256(value: Any, path: str) -> str:
    text = _string(value, path)
    if not SHA256_RE.fullmatch(text):
        _fail("sha256", path, "lowercase SHA-256 required")
    return text


def _string_list(value: Any, path: str) -> list[str]:
    rows = [
        _string(item, f"{path}[{index}]")
        for index, item in enumerate(_list(value, path))
    ]
    if len(rows) != len(set(rows)):
        _fail("duplicate_array_item", path)
    return rows


def _nonnegative_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("type", path, "non-negative integer required")
    return value


def _enum(value: Any, allowed: set[str], path: str) -> str:
    text = _string(value, path)
    if text not in allowed:
        _fail("enum", path, f"expected one of {sorted(allowed)!r}")
    return text


def _exact_keys(row: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(row)
    if actual != expected:
        _fail(
            "keys",
            path,
            f"missing={sorted(expected - actual)!r} unknown={sorted(actual - expected)!r}",
        )


def _equal(row: Mapping[str, Any], field: str, expected: Any, path: str) -> None:
    if row.get(field) != expected:
        _fail("value", f"{path}.{field}", f"expected {expected!r}")


def _sha_without_nested(row: Mapping[str, Any], path: Sequence[str]) -> str:
    payload = copy.deepcopy(dict(row))
    cursor: dict[str, Any] = payload
    for key in path[:-1]:
        value = cursor.get(key)
        if not isinstance(value, dict):
            _fail("hash_path", "$.integrity")
        cursor = value
    cursor.pop(path[-1], None)
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fail(code: str, path: str, detail: str = "validation failed") -> None:
    raise DatasetAdapterError(code, path, detail)


__all__ = [
    "ADAPTER_POLICY_ID",
    "ADAPTER_SCHEMA_ID",
    "ADAPTER_SCHEMA_VERSION",
    "CANDIDATE_SCHEMA_ID",
    "CANDIDATE_SCHEMA_VERSION",
    "seal_adapter_candidate",
    "seal_adapter_package",
    "validate_adapter_candidate",
    "validate_adapter_package",
]
