from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from context_substitution.v2.contracts.validation import ContractValidationError
from context_substitution.v2.jsonio import StrictJSONError, load_json_file


ANNOTATION_SCHEMA_ID = "D2LContextSubstitutionFinalizedReviewedSelectionV1"
ANNOTATION_SCHEMA_VERSION = "1.0.0"
ANNOTATION_POLICY_ID = "DATASET_REVIEW_ADJUDICATION_AUTHORITY"
FINALIZED_SELECTION_FILE = "finalized_reviewed_selection.json"

_SELECTION_FIELDS = {
    "sense_relation",
    "context_type",
    "judgeability",
    "reason",
    "review_row_sha256",
}
_CONTEXT_TYPES = {
    "definition",
    "typical_usage",
    "domain_collocation",
    "syntactic_variation",
    "same_sense_difficult",
    "contrastive",
    "unknown",
}


def load_frozen_review_selection(
    review_root: Path,
    *,
    source_pilot_manifest_sha256: str,
    pilot_terms: Sequence[Mapping[str, Any]] | None = None,
    pilot_contexts: Sequence[Mapping[str, Any]] | None = None,
    pilot_candidates: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Consume a Dataset-owned finalized projection without resolving reviewer votes."""

    root = Path(review_root).resolve()
    if not root.is_dir():
        _fail("review_artifact", "$.review_artifact", "expected an immutable directory")
    path = root / FINALIZED_SELECTION_FILE
    if not path.is_file():
        status = _source_workflow_status(root)
        _fail(
            "dataset_review_authority",
            "$.review_artifact",
            "C cannot resolve raw reviewer votes; Dataset authority must publish "
            f"{FINALIZED_SELECTION_FILE} (source status: {status})",
        )
    value = _load_json(path)
    required = {
        "schema_id",
        "schema_version",
        "status",
        "authority_owner",
        "policy_id",
        "source_pilot_manifest_sha256",
        "effective_sense_contract_ref",
        "effective_sense_contract_sha256",
        "sense_inventory_version",
        "senses",
        "contexts",
        "candidates",
        "final_glossary_decision",
        "integrity",
    }
    if set(value) != required:
        _fail("schema", "$", "finalized reviewed-selection fields differ")
    _require_equal(value, "schema_id", ANNOTATION_SCHEMA_ID, "$")
    _require_equal(value, "schema_version", ANNOTATION_SCHEMA_VERSION, "$")
    _require_equal(value, "status", "COMPLETE_IMMUTABLE", "$")
    _require_equal(value, "authority_owner", ANNOTATION_POLICY_ID, "$")
    _require_string(value.get("policy_id"), "$.policy_id")
    if value["source_pilot_manifest_sha256"] != source_pilot_manifest_sha256:
        _fail("review_binding", "$.source_pilot_manifest_sha256", "pilot mismatch")
    if value["final_glossary_decision"] is not None:
        _fail("decision_owner", "$.final_glossary_decision", "must remain null")
    _verify_integrity(value)

    senses = _validate_senses(value["senses"], pilot_terms or ())
    contexts = _validate_contexts(value["contexts"], pilot_contexts or ())
    candidate_ids = _validate_candidates(value["candidates"], pilot_candidates or ())
    effective_sha = _require_sha256(
        value["effective_sense_contract_sha256"],
        "$.effective_sense_contract_sha256",
    )
    return {
        "review_artifact_ref": path.as_posix(),
        "review_artifact_sha256": value["integrity"]["self_sha256"],
        "effective_sense_contract_ref": _require_string(
            value["effective_sense_contract_ref"],
            "$.effective_sense_contract_ref",
        ),
        "effective_sense_contract_sha256": effective_sha,
        "sense_inventory_version": _require_string(
            value["sense_inventory_version"], "$.sense_inventory_version"
        ),
        "senses": senses,
        "contexts": contexts,
        "candidate_review_count": len(candidate_ids),
    }


def _validate_senses(
    value: Any, source_rows: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _fail("review_cover", "$.senses", "expected finalized sense rows")
    expected = {str(row["sense_id"]): row for row in source_rows}
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(value):
        path = f"$.senses[{index}]"
        if not isinstance(row, Mapping):
            _fail("schema", path, "expected object")
        required = {
            "term_id",
            "sense_id",
            "source_term",
            "scope_id",
            "source_term_sense_sha256",
            "effective_definition_en",
            "effective_part_of_speech",
            "reviewed_sense_contract_sha256",
        }
        if set(row) != required:
            _fail("schema", path, "finalized sense fields differ")
        _verify_row_hash(row, "reviewed_sense_contract_sha256", path=path)
        sense_id = _require_string(row["sense_id"], f"{path}.sense_id")
        if sense_id in result:
            _fail("duplicate", f"{path}.sense_id", "duplicate sense")
        source = expected.get(sense_id)
        if expected and source is None:
            _fail("review_binding", f"{path}.sense_id", "foreign sense")
        if source is not None:
            for field in ("term_id", "sense_id", "source_term", "scope_id"):
                if str(row[field]) != str(source[field]):
                    _fail("review_binding", f"{path}.{field}", "source differs")
            if row["source_term_sense_sha256"] != source["term_sense_sha256"]:
                _fail("review_binding", path, "sense source hash mismatch")
        result[sense_id] = dict(row)
    if expected and set(result) != set(expected):
        _fail("review_cover", "$.senses", "sense coverage mismatch")
    return result


def _validate_contexts(
    value: Any, source_rows: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, str]]:
    if not isinstance(value, list) or not value:
        _fail("review_cover", "$.contexts", "expected finalized context rows")
    expected = {str(row["context_id"]): row for row in source_rows}
    result: dict[str, dict[str, str]] = {}
    for index, row in enumerate(value):
        path = f"$.contexts[{index}]"
        if not isinstance(row, Mapping) or set(row) != {
            "context_id",
            "source_record_sha256",
            "reviewed_selection",
            "row_sha256",
        }:
            _fail("schema", path, "finalized context fields differ")
        _verify_row_hash(row, "row_sha256", path=path)
        context_id = _require_string(row["context_id"], f"{path}.context_id")
        if context_id in result:
            _fail("duplicate", f"{path}.context_id", "duplicate context")
        source = expected.get(context_id)
        if expected and source is None:
            _fail("review_binding", f"{path}.context_id", "foreign context")
        if source is not None and row["source_record_sha256"] != source["context_sha256"]:
            _fail("review_binding", path, "context source hash mismatch")
        result[context_id] = _validate_selection(
            row["reviewed_selection"], path=f"{path}.reviewed_selection"
        )
    if expected and set(result) != set(expected):
        _fail("review_cover", "$.contexts", "context coverage mismatch")
    return result


def _validate_candidates(
    value: Any, source_rows: Sequence[Mapping[str, Any]]
) -> set[str]:
    if not isinstance(value, list) or not value:
        _fail("review_cover", "$.candidates", "expected finalized candidate rows")
    expected = {str(row["candidate_instance_id"]): row for row in source_rows}
    result: set[str] = set()
    for index, row in enumerate(value):
        path = f"$.candidates[{index}]"
        if not isinstance(row, Mapping) or set(row) != {
            "candidate_instance_id",
            "source_record_sha256",
            "review_status",
            "row_sha256",
        }:
            _fail("schema", path, "finalized candidate fields differ")
        _verify_row_hash(row, "row_sha256", path=path)
        candidate_id = _require_string(
            row["candidate_instance_id"], f"{path}.candidate_instance_id"
        )
        if candidate_id in result:
            _fail("duplicate", path, "duplicate candidate")
        if row["review_status"] != "REVIEWED_FINAL":
            _fail("review_status", f"{path}.review_status", "candidate not finalized")
        source = expected.get(candidate_id)
        if expected and source is None:
            _fail("review_binding", path, "foreign candidate")
        if source is not None and row["source_record_sha256"] != source[
            "candidate_instance_sha256"
        ]:
            _fail("review_binding", path, "candidate source hash mismatch")
        result.add(candidate_id)
    if expected and result != set(expected):
        _fail("review_cover", "$.candidates", "candidate coverage mismatch")
    return result


def _validate_selection(value: Any, *, path: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _SELECTION_FIELDS:
        _fail("schema", path, "reviewed selection fields differ")
    relation = value["sense_relation"]
    context_type = value["context_type"]
    judgeability = value["judgeability"]
    if relation not in {"SAME_SENSE", "CONTRASTIVE", "AMBIGUOUS"}:
        _fail("review_label", f"{path}.sense_relation", "invalid relation")
    if context_type not in _CONTEXT_TYPES:
        _fail("review_label", f"{path}.context_type", "invalid context type")
    if judgeability not in {"JUDGEABLE", "AMBIGUOUS_SENSE", "INVALID_SOURCE"}:
        _fail("review_label", f"{path}.judgeability", "invalid judgeability")
    result = {key: _require_string(value[key], f"{path}.{key}") for key in _SELECTION_FIELDS}
    _require_sha256(result["review_row_sha256"], f"{path}.review_row_sha256")
    return result


def _verify_integrity(value: Mapping[str, Any]) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {"self_sha256"}:
        _fail("self_hash", "$.integrity", "invalid integrity")
    claimed = _require_sha256(integrity["self_sha256"], "$.integrity.self_sha256")
    identity = dict(value)
    identity["integrity"] = {}
    if claimed != _object_hash(identity):
        _fail("self_hash", "$.integrity.self_sha256", "hash mismatch")


def _verify_row_hash(row: Mapping[str, Any], field: str, *, path: str) -> None:
    claimed = _require_sha256(row.get(field), f"{path}.{field}")
    identity = dict(row)
    identity.pop(field, None)
    if claimed != _object_hash(identity):
        _fail("self_hash", f"{path}.{field}", "hash mismatch")


def _source_workflow_status(root: Path) -> str:
    path = root / "manifest.json"
    if not path.is_file():
        return "UNKNOWN"
    try:
        value = _load_json(path)
    except ContractValidationError:
        return "INVALID"
    return str(value.get("status") or "UNKNOWN")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return load_json_file(path, require_object=True)
    except StrictJSONError as exc:
        _fail("json", str(path), f"invalid strict JSON: {exc}")


def _require_equal(row: Mapping[str, Any], field: str, expected: str, path: str) -> None:
    if row.get(field) != expected:
        _fail("schema", f"{path}.{field}", f"expected {expected}")


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("string", path, "expected canonical nonempty string")
    return value


def _require_sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        _fail("sha256", path, "invalid SHA-256")
    return value


def _object_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _fail(code: str, path: str, message: str) -> None:
    raise ContractValidationError(code, path, message)


__all__ = [
    "ANNOTATION_POLICY_ID",
    "ANNOTATION_SCHEMA_ID",
    "ANNOTATION_SCHEMA_VERSION",
    "FINALIZED_SELECTION_FILE",
    "load_frozen_review_selection",
]
