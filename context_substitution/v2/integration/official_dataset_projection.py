from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Mapping

from context_substitution.v2.contracts.input import (
    INPUT_SCHEMA_ID,
    INPUT_SCHEMA_VERSION,
    seal_context_substitution_input,
)
from context_substitution.v2.contracts.provenance import SOURCE_LOCATOR_KIND
from context_substitution.v2.integration.authority import canonical_sha256
from context_substitution.v2.integration.common import seal_object
from context_substitution.v2.integration.official_dataset import (
    EXCLUDED_ELEVEN_SENSE_COMMIT,
    OFFICIAL_ADAPTER_RECEIPT_SCHEMA_ID,
    OFFICIAL_MAIN_COMMIT,
    OFFICIAL_MANIFEST_SELF_SHA256,
    OFFICIAL_PIN_SELF_SHA256,
    OFFICIAL_RECEIPT_SCHEMA_VERSION,
    OFFICIAL_RUNTIME_RECEIPT_SCHEMA_ID,
    OFFICIAL_ZIP_NAME,
    OFFICIAL_ZIP_SHA256,
    PARENT_DATASET_MANIFEST_SHA256,
    REVIEWED_DATASET_MANIFEST_SHA256,
    REVIEWED_PRODUCER_COMMIT,
    OfficialDatasetPilot,
)


_ROLE_ORDER = {"PRIMARY": 0, "BACKUP": 1, "CONTRASTIVE": 2}
_TARGET_ROLES = ("canonical", "alternative", "pending")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_OFFICIAL_ARTIFACT_URI = "artifact://d2l-stage-a-official-5-sense-pilot-v1"


def build_official_dataset_inputs(pilot: OfficialDatasetPilot) -> dict[str, Any]:
    """Project official Dataset bytes into the existing C runtime boundary."""

    input_payload = _build_runtime_input(pilot)
    adapter_receipt = _build_adapter_receipt(pilot)
    runtime_receipt = _build_runtime_receipt(
        pilot,
        input_payload=input_payload,
        adapter_receipt=adapter_receipt,
    )
    frozen_set = seal_object(
        {
            "schema_id": "DatasetFrozenCandidateSetV1",
            "schema_version": "1.0.0",
            "status": "COMPLETE_IMMUTABLE",
            "authority_owner": "DATASET_ADAPTER",
            "candidate_count": len(pilot.frozen_candidates),
            "candidates": sorted(
                (copy.deepcopy(row) for row in pilot.frozen_candidates),
                key=lambda row: row["candidate_key"]["candidate_id"],
            ),
            "final_glossary_decision": None,
            "integrity": {},
        },
        integrity_key="self_sha256",
    )
    return {
        "input": input_payload,
        "adapter_receipt": adapter_receipt,
        "runtime_receipt": runtime_receipt,
        "frozen_candidates": frozen_set,
    }


def validate_official_adapter_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_id",
        "schema_version",
        "status",
        "agent",
        "source_main_commit",
        "source_zip_name",
        "source_zip_sha256",
        "source_pin_self_sha256",
        "source_pin_physical_sha256",
        "official_manifest_sha256",
        "official_manifest_file_sha256",
        "dataset_manifest_sha256",
        "parent_dataset_manifest_sha256",
        "reviewed_dataset_manifest_sha256",
        "reviewed_producer_commit",
        "excluded_eleven_sense_commit",
        "counts",
        "provider_call_count",
        "network_call_count",
        "final_glossary_decision",
        "global_gate_action",
        "integrity",
    }
    row = _validate_receipt_common(
        value,
        required=required,
        schema_id=OFFICIAL_ADAPTER_RECEIPT_SCHEMA_ID,
    )
    _require_official_bindings(row)
    if row["counts"] != {
        "effective_sense_contracts": 5,
        "frozen_candidate_contracts": 15,
        "constraint_evidence_packages": 15,
        "contexts": 29,
    }:
        raise ValueError("official adapter receipt counts mismatch")
    return row


def validate_official_runtime_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_id",
        "schema_version",
        "status",
        "agent",
        "adapter_receipt_sha256",
        "source_manifest_sha256",
        "source_manifest_file_sha256",
        "official_manifest_sha256",
        "source_zip_sha256",
        "source_pin_self_sha256",
        "source_pin_physical_sha256",
        "parent_dataset_manifest_sha256",
        "source_term_sense_count",
        "source_candidate_count",
        "source_context_count",
        "adapted_term_sense_count",
        "adapted_candidate_count",
        "adapted_context_count",
        "input_sha256",
        "mode",
        "contract_bindings",
        "provider_call_count",
        "network_call_count",
        "final_glossary_decision",
        "global_gate_action",
        "integrity",
    }
    row = _validate_receipt_common(
        value,
        required=required,
        schema_id=OFFICIAL_RUNTIME_RECEIPT_SCHEMA_ID,
    )
    if row["source_manifest_sha256"] != PARENT_DATASET_MANIFEST_SHA256:
        raise ValueError("official runtime receipt source manifest mismatch")
    if row["official_manifest_sha256"] != OFFICIAL_MANIFEST_SELF_SHA256:
        raise ValueError("official runtime receipt release manifest mismatch")
    if row["source_zip_sha256"] != OFFICIAL_ZIP_SHA256:
        raise ValueError("official runtime receipt ZIP mismatch")
    if row["source_pin_self_sha256"] != OFFICIAL_PIN_SELF_SHA256:
        raise ValueError("official runtime receipt pin mismatch")
    if row["parent_dataset_manifest_sha256"] is not None:
        raise ValueError("official runtime receipt has an unexpected parent")
    if row["mode"] != "OFFICIAL_DATASET_ZERO_PROVIDER":
        raise ValueError("official runtime receipt mode mismatch")
    counts = (
        row["source_term_sense_count"],
        row["source_candidate_count"],
        row["source_context_count"],
        row["adapted_term_sense_count"],
        row["adapted_candidate_count"],
        row["adapted_context_count"],
    )
    if counts != (5, 15, 29, 5, 15, 29):
        raise ValueError("official runtime receipt counts mismatch")
    bindings = row["contract_bindings"]
    if not isinstance(bindings, list) or len(bindings) != 15:
        raise ValueError("official runtime receipt contract binding count mismatch")
    candidate_ids = [binding.get("candidate_id") for binding in bindings]
    if candidate_ids != sorted(candidate_ids) or len(set(candidate_ids)) != 15:
        raise ValueError("official runtime receipt candidate bindings are not canonical")
    binding_keys = {
        "candidate_id",
        "sense_id",
        "candidate_version",
        "input_contract_sha256",
        "effective_sense_contract_sha256",
        "effective_sense_contract_file_sha256",
        "frozen_candidate_self_sha256",
        "frozen_candidate_file_sha256",
        "constraint_evidence_self_sha256",
        "constraint_evidence_file_sha256",
    }
    for binding in bindings:
        if not isinstance(binding, Mapping) or set(binding) != binding_keys:
            raise ValueError("official runtime contract binding fields differ")
        for key, child in binding.items():
            if key not in {"candidate_id", "sense_id"} and not _is_sha256(child):
                raise ValueError(f"official runtime binding {key} is not SHA-256")
    return row


def _build_runtime_input(pilot: OfficialDatasetPilot) -> dict[str, Any]:
    terms_by_sense = {str(row["sense_id"]): row for row in pilot.term_senses}
    effective_by_sense = {
        str(row["sense_id"]): row for row in pilot.effective_senses
    }
    contexts_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    for row in pilot.contexts:
        contexts_by_sense.setdefault(str(row["sense_id"]), []).append(row)
    candidates_by_id = {
        str(row["candidate_instance_id"]): row for row in pilot.candidate_instances
    }
    normalized_terms = []
    for selection in pilot.selection_receipt["records"]:
        sense_id = str(selection["sense_id"])
        term = terms_by_sense[sense_id]
        effective = effective_by_sense[sense_id]
        targets = []
        for role, candidate_id in zip(
            _TARGET_ROLES, selection["candidate_ids"], strict=True
        ):
            candidate = candidates_by_id[str(candidate_id)]
            formation = candidate.get("formation_provenance")
            formation_rows = formation if isinstance(formation, list) else []
            run_id = next(
                (
                    str(row[key])
                    for row in formation_rows
                    for key in ("audit_sha256", "source_artifact_sha256")
                    if row.get(key)
                ),
                None,
            )
            targets.append(
                {
                    "candidate_target_id": str(candidate_id),
                    "role": role,
                    "target_vi": str(candidate["candidate_target_vi"]),
                    "applicability": candidate.get("applicability"),
                    "candidate_generation": {
                        "generator_model": None,
                        "prompt_version": None,
                        "run_id": run_id,
                        "recording_status": (
                            "RECORDED" if run_id is not None else "UNAVAILABLE_IN_SEALED_ARTIFACT"
                        ),
                        "candidate_version": str(candidate["candidate_instance_sha256"]),
                        "candidate_slot_id": str(candidate["candidate_slot_id"]),
                        "candidate_slot_status": "RECORDED",
                        "formation_method": str(candidate["formation_method"]),
                    },
                }
            )
        contexts = sorted(
            contexts_by_sense[sense_id],
            key=lambda row: (
                _ROLE_ORDER.get(str(row.get("context_role")), 99),
                str(row["context_id"]),
            ),
        )
        normalized_terms.append(
            {
                "term_id": str(term["term_id"]),
                "source_term": str(effective["source_term"]),
                "sense_id": sense_id,
                "scope_id": str(effective["scope_id"]),
                "sense_contract": {
                    "definition_en": str(effective["effective_definition_en"]),
                    "definition_source": "official_effective_sense_contract_v1",
                    "definition_provenance": [
                        "effective_sense_contract:"
                        + effective["integrity"]["self_sha256"],
                        "review_artifact:" + str(effective["review_artifact_sha256"]),
                    ],
                    "definition_review_status": "VERIFIED",
                    "sense_inventory_version": str(
                        effective["sense_inventory_version"]
                    ),
                },
                "part_of_speech": str(effective["effective_part_of_speech"]),
                "source_occurrences": [str(row["context_id"]) for row in contexts],
                "contexts": [_runtime_context(row) for row in contexts],
                "candidate_targets": targets,
            }
        )
    files = pilot.manifest["files"]
    return seal_context_substitution_input(
        {
            "schema_id": INPUT_SCHEMA_ID,
            "schema_version": INPUT_SCHEMA_VERSION,
            "input_origin": {
                "kind": "VALIDATION_READY_SUPPORT_SET_V3",
                "source_schema_id": "D2LContextSupportSetValidationReadyV3",
                "source_schema_version": "3.0.0",
                "source_sha256": PARENT_DATASET_MANIFEST_SHA256,
            },
            "source_artifacts": {
                "candidate_index": {
                    "ref": f"{_OFFICIAL_ARTIFACT_URI}/candidate_index_15.json",
                    "physical_sha256": files["candidate_index_15.json"]["sha256"],
                },
                "glossary": {
                    "ref": (
                        f"{_OFFICIAL_ARTIFACT_URI}/materialized_input/"
                        "term_senses_5.jsonl"
                    ),
                    "physical_sha256": files[
                        "materialized_input/term_senses_5.jsonl"
                    ]["sha256"],
                },
                "document": {
                    "ref": (
                        f"{_OFFICIAL_ARTIFACT_URI}/materialized_input/contexts_29.jsonl"
                    ),
                    "physical_sha256": files[
                        "materialized_input/contexts_29.jsonl"
                    ]["sha256"],
                },
            },
            "selection_contract": {
                "selector_mode": "MODEL_CLASSIFICATION_DEVELOPMENT",
                "authority_status": "DEVELOPMENT_PENDING_HUMAN_REVIEW",
                "dataset_manifest_sha256": PARENT_DATASET_MANIFEST_SHA256,
                "parent_dataset_manifest_sha256": None,
                "review_artifact_ref": None,
                "review_artifact_sha256": None,
                "effective_sense_contract_ref": None,
                "effective_sense_contract_sha256": None,
            },
            "terms": normalized_terms,
            "integrity": {"input_sha256": "0" * 64},
        }
    )


def _runtime_context(row: Mapping[str, Any]) -> dict[str, Any]:
    source_text = str(row["source_text"])
    if row.get("binding_kind") == "SYNTHETIC_BOUNDARY_PROBE":
        provenance = {
            "document_id": "synthetic-contrastive-review-probe",
            "chapter_id": "synthetic-contrastive",
            "block_id": str(row["context_id"]),
            "sentence_id": str(row["context_id"]),
            "source_start": 0,
            "source_end": len(source_text),
            "source_locator_kind": SOURCE_LOCATOR_KIND,
            "source_hash": str(row["content_sha256"]),
        }
    else:
        raw = row["provenance"]
        provenance = {
            "document_id": str(raw["document_id"]),
            "chapter_id": str(raw["chapter_id"]),
            "block_id": str(raw["block_id"]),
            "sentence_id": str(raw["sentence_id"]),
            "source_start": int(raw["source_start"]),
            "source_end": int(raw["source_end"]),
            "source_locator_kind": SOURCE_LOCATOR_KIND,
            "source_hash": str(row["content_sha256"]),
        }
    return {
        "context_id": str(row["context_id"]),
        "chapter_id": provenance["chapter_id"],
        "block_id": provenance["block_id"],
        "block_type": "sentence",
        "source_text": source_text,
        "source_text_sha256": str(row["content_sha256"]),
        "source_provenance": provenance,
        "reviewed_selection": None,
    }


def _build_adapter_receipt(pilot: OfficialDatasetPilot) -> dict[str, Any]:
    return seal_object(
        {
            "schema_id": OFFICIAL_ADAPTER_RECEIPT_SCHEMA_ID,
            "schema_version": OFFICIAL_RECEIPT_SCHEMA_VERSION,
            "status": "PASS",
            "agent": "CONTEXT_SUBSTITUTION_C",
            "source_main_commit": OFFICIAL_MAIN_COMMIT,
            "source_zip_name": OFFICIAL_ZIP_NAME,
            "source_zip_sha256": pilot.zip_sha256,
            "source_pin_self_sha256": pilot.pin["integrity"]["self_sha256"],
            "source_pin_physical_sha256": pilot.pin_physical_sha256,
            "official_manifest_sha256": pilot.manifest["manifest_sha256"],
            "official_manifest_file_sha256": hashlib.sha256(
                pilot.file_bytes["manifest.json"]
            ).hexdigest(),
            "dataset_manifest_sha256": PARENT_DATASET_MANIFEST_SHA256,
            "parent_dataset_manifest_sha256": None,
            "reviewed_dataset_manifest_sha256": REVIEWED_DATASET_MANIFEST_SHA256,
            "reviewed_producer_commit": REVIEWED_PRODUCER_COMMIT,
            "excluded_eleven_sense_commit": EXCLUDED_ELEVEN_SENSE_COMMIT,
            "counts": {
                "effective_sense_contracts": len(pilot.effective_senses),
                "frozen_candidate_contracts": len(pilot.frozen_candidates),
                "constraint_evidence_packages": len(pilot.constraint_packages),
                "contexts": len(pilot.contexts),
            },
            "provider_call_count": 0,
            "network_call_count": 0,
            "final_glossary_decision": None,
            "global_gate_action": None,
            "integrity": {},
        },
        integrity_key="receipt_sha256",
    )


def _build_runtime_receipt(
    pilot: OfficialDatasetPilot,
    *,
    input_payload: Mapping[str, Any],
    adapter_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    effective = {str(row["sense_id"]): row for row in pilot.effective_senses}
    constraints = {
        str(row["candidate_key"]["candidate_id"]): row
        for row in pilot.constraint_packages
    }
    files = pilot.manifest["files"]
    bindings = []
    for frozen in sorted(
        pilot.frozen_candidates,
        key=lambda row: row["candidate_key"]["candidate_id"],
    ):
        key = frozen["candidate_key"]
        candidate_id = str(key["candidate_id"])
        sense_id = str(key["sense_id"])
        constraint = constraints[candidate_id]
        bindings.append(
            {
                "candidate_id": candidate_id,
                "sense_id": sense_id,
                "candidate_version": key["candidate_version"],
                "input_contract_sha256": frozen["input_contract_sha256"],
                "effective_sense_contract_sha256": effective[sense_id]["integrity"][
                    "self_sha256"
                ],
                "effective_sense_contract_file_sha256": files[
                    f"effective_sense_contracts_5/{sense_id}.json"
                ]["sha256"],
                "frozen_candidate_self_sha256": frozen["integrity"]["self_sha256"],
                "frozen_candidate_file_sha256": files[
                    f"frozen_candidate_contracts_15/{candidate_id}.json"
                ]["sha256"],
                "constraint_evidence_self_sha256": constraint["integrity"][
                    "self_sha256"
                ],
                "constraint_evidence_file_sha256": files[
                    f"constraint_evidence_packages_15/{candidate_id}.json"
                ]["sha256"],
            }
        )
    return seal_object(
        {
            "schema_id": OFFICIAL_RUNTIME_RECEIPT_SCHEMA_ID,
            "schema_version": OFFICIAL_RECEIPT_SCHEMA_VERSION,
            "status": "PASS",
            "agent": "CONTEXT_SUBSTITUTION_C",
            "adapter_receipt_sha256": adapter_receipt["integrity"]["receipt_sha256"],
            "source_manifest_sha256": PARENT_DATASET_MANIFEST_SHA256,
            "source_manifest_file_sha256": hashlib.sha256(
                pilot.file_bytes["manifest.json"]
            ).hexdigest(),
            "official_manifest_sha256": pilot.manifest["manifest_sha256"],
            "source_zip_sha256": pilot.zip_sha256,
            "source_pin_self_sha256": pilot.pin["integrity"]["self_sha256"],
            "source_pin_physical_sha256": pilot.pin_physical_sha256,
            "parent_dataset_manifest_sha256": None,
            "source_term_sense_count": 5,
            "source_candidate_count": 15,
            "source_context_count": 29,
            "adapted_term_sense_count": 5,
            "adapted_candidate_count": 15,
            "adapted_context_count": 29,
            "input_sha256": input_payload["integrity"]["input_sha256"],
            "mode": "OFFICIAL_DATASET_ZERO_PROVIDER",
            "contract_bindings": bindings,
            "provider_call_count": 0,
            "network_call_count": 0,
            "final_glossary_decision": None,
            "global_gate_action": None,
            "integrity": {},
        },
        integrity_key="receipt_sha256",
    )


def _validate_receipt_common(
    value: Mapping[str, Any],
    *,
    required: set[str],
    schema_id: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError(f"{schema_id} fields differ")
    row = copy.deepcopy(dict(value))
    if row["schema_id"] != schema_id or row["schema_version"] != OFFICIAL_RECEIPT_SCHEMA_VERSION:
        raise ValueError(f"{schema_id} identity mismatch")
    if row["status"] != "PASS" or row["agent"] != "CONTEXT_SUBSTITUTION_C":
        raise ValueError(f"{schema_id} status/agent mismatch")
    _verify_nested_self_hash(row, schema_id, key="receipt_sha256")
    if (
        row["provider_call_count"] != 0
        or row["network_call_count"] != 0
        or row["final_glossary_decision"] is not None
        or row["global_gate_action"] is not None
    ):
        raise ValueError(f"{schema_id} exceeds C zero-provider authority")
    return row


def _require_official_bindings(row: Mapping[str, Any]) -> None:
    expected = {
        "source_main_commit": OFFICIAL_MAIN_COMMIT,
        "source_zip_name": OFFICIAL_ZIP_NAME,
        "source_zip_sha256": OFFICIAL_ZIP_SHA256,
        "source_pin_self_sha256": OFFICIAL_PIN_SELF_SHA256,
        "official_manifest_sha256": OFFICIAL_MANIFEST_SELF_SHA256,
        "dataset_manifest_sha256": PARENT_DATASET_MANIFEST_SHA256,
        "parent_dataset_manifest_sha256": None,
        "reviewed_dataset_manifest_sha256": REVIEWED_DATASET_MANIFEST_SHA256,
        "reviewed_producer_commit": REVIEWED_PRODUCER_COMMIT,
        "excluded_eleven_sense_commit": EXCLUDED_ELEVEN_SENSE_COMMIT,
    }
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError(f"official adapter receipt {key} mismatch")


def _verify_nested_self_hash(
    value: Mapping[str, Any],
    label: str,
    *,
    key: str,
) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {key}:
        raise ValueError(f"{label} integrity fields differ")
    claimed = integrity.get(key)
    identity = copy.deepcopy(dict(value))
    identity["integrity"].pop(key)
    if not _is_sha256(claimed) or canonical_sha256(identity) != claimed:
        raise ValueError(f"{label} self SHA mismatch")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


__all__ = [
    "build_official_dataset_inputs",
    "validate_official_adapter_receipt",
    "validate_official_runtime_receipt",
]
