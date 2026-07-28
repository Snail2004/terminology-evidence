from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pipeline.eval.contracts_v1 import (
    CanonicalPolicy,
    ContractValidationError,
    canonical_json,
    canonicalize,
    require_enum,
    require_exact_keys,
    require_int,
    require_list,
    require_mapping,
    require_nullable_string,
    require_number,
    require_rfc3339,
    require_sha256,
    require_string,
    require_unique,
    seal_payload,
    verify_payload_hash,
)
from pipeline.eval.terminology_evidence.context_substitution.v2.contracts.common import (
    PROVIDER_ROUTE_IDS as CONTEXT_PROVIDER_ROUTE_IDS,
    RUBRIC_VERSION as CONTEXT_RUBRIC_VERSION,
    RUN_POLICY as CONTEXT_RUN_POLICY,
    SCHEMA_ID as CONTEXT_SUBSTITUTION_SCHEMA_ID,
    SCHEMA_VERSION as CONTEXT_SUBSTITUTION_SCHEMA_VERSION,
)
from pipeline.eval.terminology_evidence.context_substitution.v2.contracts.provenance import (
    build_block_source_provenance,
    validate_source_provenance,
)


__all__ = [
    "INPUT_SCHEMA_ID",
    "MEASUREMENTS_SCHEMA_ID",
    "REPORT_SCHEMA_ID",
    "CONTEXT_SUBSTITUTION_SCHEMA_ID",
    "CONTEXT_SUBSTITUTION_SCHEMA_VERSION",
    "CONTEXT_RUBRIC_VERSION",
    "CONTEXT_PROVIDER_ROUTE_IDS",
    "ContextExecutionError",
    "ContextProviderRoute",
    "FailoverStructuredModel",
    "ProviderRawResponse",
    "extract_d2l_term_evidence_input",
    "run_d2l_context_substitution",
    "context_substitution_to_measurements",
    "score_d2l_term_evidence",
    "seal_d2l_term_evidence_measurements",
    "seal_d2l_context_substitution_run",
    "validate_d2l_term_evidence_input",
    "validate_d2l_term_evidence_measurements",
    "validate_d2l_term_evidence_report",
    "validate_d2l_context_substitution_run",
    "write_canonical_json",
]


INPUT_SCHEMA_ID = "D2LTermEvidenceInputV1"
MEASUREMENTS_SCHEMA_ID = "D2LTermEvidenceMeasurementsV1"
REPORT_SCHEMA_ID = "D2LTermEvidenceReportV1"
SCHEMA_VERSION = "1.1.0"
INPUT_SCHEMA_VERSION = "2.0.0"
DEFAULT_SAMPLE_SEED = "d2l_term_evidence_canary_v1"
CONTEXT_ENRICHMENT_POLICY = "sealed_evidence_then_exact_surface_match_v1"

_INPUT_HASH_PATH = ("integrity", "input_sha256")
_MEASUREMENTS_HASH_PATH = ("integrity", "measurements_sha256")
_REPORT_HASH_PATH = ("integrity", "report_sha256")

_STRATA = ("collision_or_multi_target", "ambiguous", "clear")
_TARGET_ROLES = frozenset({"canonical", "alternative", "rejected", "pending"})
_CONTEXT_LABELS = frozenset({"PASS", "MINOR", "FAIL"})
_CONTEXT_SELECTION_KINDS = frozenset({"sealed_evidence", "surface_match"})
_DECISIONS = frozenset(
    {
        "AUTO_APPROVED",
        "HUMAN_REVIEW",
        "REJECTED",
        "SPLIT_REQUIRED",
        "PROVISIONAL",
    }
)
_SOURCE_TYPES = frozenset(
    {"official", "academic", "vendor_docs", "technical_blog", "unknown"}
)

INPUT_POLICY = CanonicalPolicy(
    set_like_paths=frozenset(
        {
            ("terms", "*", "surfaces"),
            ("terms", "*", "source_member_candidate_ids"),
        }
    ),
    semantic_sequence_paths=frozenset(
        {
            ("terms",),
            ("terms", "*", "evidence_block_ids"),
            ("terms", "*", "source_occurrences"),
            ("terms", "*", "sense_contract", "definition_provenance"),
            ("terms", "*", "contexts"),
            ("terms", "*", "candidate_targets"),
        }
    ),
)

MEASUREMENTS_POLICY = CanonicalPolicy(
    set_like_paths=frozenset(),
    semantic_sequence_paths=frozenset(
        {
            ("measurements",),
            ("measurements", "*", "context_results"),
            ("measurements", "*", "web_evidence"),
            ("measurements", "*", "back_translation", "sentence_results"),
        }
    ),
)

REPORT_POLICY = CanonicalPolicy(
    set_like_paths=frozenset(
        {
            ("results", "*", "hard_gates"),
            ("results", "*", "rationale_codes"),
        }
    ),
    semantic_sequence_paths=frozenset({("results",)}),
)

def extract_d2l_term_evidence_input(
    candidate_index_path: Path,
    glossary_path: Path,
    document_path: Path,
    *,
    sample_size: int = 30,
    contexts_per_term: int = 5,
    seed: str = DEFAULT_SAMPLE_SEED,
) -> dict[str, Any]:
    """Build a deterministic, read-only term-evidence canary from sealed artifacts."""

    if sample_size < 1:
        raise ContractValidationError("range", "$.sample_size", "must be >= 1")
    if contexts_per_term < 1:
        raise ContractValidationError(
            "range", "$.contexts_per_term", "must be >= 1"
        )
    normalized_seed = require_string(seed, path="$.seed", maximum=200)

    candidate_index = _read_json(candidate_index_path)
    glossary = _read_json(glossary_path)
    document = _read_json(document_path)

    candidate_root = require_mapping(candidate_index, path="$.candidate_index")
    require_enum(
        candidate_root.get("index_version"),
        {"d2l_candidate_index_v2"},
        path="$.candidate_index.index_version",
    )
    candidates = require_list(
        candidate_root.get("candidates"), path="$.candidate_index.candidates"
    )
    candidate_by_id = _candidate_index(candidates)

    glossary_root = require_mapping(glossary, path="$.glossary")
    require_enum(
        glossary_root.get("schema"),
        {"d2l_sealed_glossary_v1"},
        path="$.glossary.schema",
    )
    records = require_list(glossary_root.get("records"), path="$.glossary.records")

    document_root = require_mapping(document, path="$.document")
    require_enum(
        document_root.get("schema_version"),
        {"1.5.0"},
        path="$.document.schema_version",
    )
    document_id = require_string(
        document_root.get("doc_id"), path="$.document.doc_id", maximum=500
    )
    block_by_id = _document_block_index(
        document_root, document_id=document_id
    )

    populations: dict[str, list[Mapping[str, Any]]] = {name: [] for name in _STRATA}
    record_ids: list[str] = []
    for index, raw_record in enumerate(records):
        record_path = f"$.glossary.records[{index}]"
        record = require_mapping(raw_record, path=record_path)
        record_id = require_string(record.get("record_id"), path=f"{record_path}.record_id")
        record_ids.append(record_id)
        value = require_mapping(record.get("value"), path=f"{record_path}.value")
        member_ids = _string_list(
            value.get("source_member_candidate_ids"),
            path=f"{record_path}.value.source_member_candidate_ids",
            minimum=1,
        )
        foreign = sorted(set(member_ids) - candidate_by_id.keys())
        if foreign:
            raise ContractValidationError(
                "foreign_candidate",
                f"{record_path}.value.source_member_candidate_ids",
                f"unknown candidate IDs: {', '.join(foreign)}",
            )
        populations[_classify_stratum(value)].append(record)
    require_unique(record_ids, path="$.glossary.records[*].record_id")

    selected_records = _sample_records(
        populations, sample_size=sample_size, seed=normalized_seed
    )
    terms = [
        _term_view(
            record,
            candidate_by_id=candidate_by_id,
            block_by_id=block_by_id,
            contexts_per_term=contexts_per_term,
        )
        for record in selected_records
    ]
    selected_counts = Counter(term["stratum"] for term in terms)

    payload = {
        "schema_id": INPUT_SCHEMA_ID,
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_artifacts": {
            "candidate_index": _artifact_binding(candidate_index_path),
            "glossary": _artifact_binding(glossary_path),
            "document": _artifact_binding(document_path),
        },
        "sampling": {
            "seed": normalized_seed,
            "requested_sample_size": sample_size,
            "selected_sample_size": len(terms),
            "contexts_per_term": contexts_per_term,
            "context_enrichment_policy": CONTEXT_ENRICHMENT_POLICY,
            "population_counts": {
                name: len(populations[name]) for name in _STRATA
            },
            "selected_counts": {name: selected_counts[name] for name in _STRATA},
        },
        "terms": terms,
        "integrity": {"input_sha256": "0" * 64},
    }
    sealed = seal_payload(payload, policy=INPUT_POLICY, hash_path=_INPUT_HASH_PATH)
    return validate_d2l_term_evidence_input(sealed)


def seal_d2l_term_evidence_measurements(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    sealed = seal_payload(
        payload,
        policy=MEASUREMENTS_POLICY,
        hash_path=_MEASUREMENTS_HASH_PATH,
    )
    return validate_d2l_term_evidence_measurements(sealed)


def score_d2l_term_evidence(
    input_payload: Mapping[str, Any],
    measurements_payload: Mapping[str, Any],
) -> dict[str, Any]:
    input_doc = validate_d2l_term_evidence_input(input_payload)
    measurements_doc = validate_d2l_term_evidence_measurements(measurements_payload)
    input_sha256 = input_doc["integrity"]["input_sha256"]
    if measurements_doc["input_sha256"] != input_sha256:
        raise ContractValidationError(
            "input_binding",
            "$.measurements.input_sha256",
            "measurements do not bind the supplied input",
        )

    term_index = {row["term_id"]: row for row in input_doc["terms"]}
    target_index = {
        (term["term_id"], target["candidate_target_id"]): (term, target)
        for term in input_doc["terms"]
        for target in term["candidate_targets"]
    }
    measurement_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in measurements_doc["measurements"]:
        key = (row["term_id"], row["candidate_target_id"])
        if key not in target_index:
            raise ContractValidationError(
                "foreign_target",
                "$.measurements.measurements",
                f"unknown term/target binding: {key[0]} / {key[1]}",
            )
        if key in measurement_index:
            raise ContractValidationError(
                "duplicate_measurement",
                "$.measurements.measurements",
                f"duplicate term/target measurement: {key[0]} / {key[1]}",
            )
        measurement_index[key] = row

    results: list[dict[str, Any]] = []
    for key, (term, target) in target_index.items():
        measurement = measurement_index.get(key)
        if measurement is not None:
            _validate_measurement_binding(term, measurement)
        results.append(_score_target(term, target, measurement))
    results.sort(
        key=lambda row: (
            row["term_id"],
            row["target_role"],
            row["candidate_target_id"],
        )
    )
    status_counts = Counter(row["decision"] for row in results)
    report = {
        "schema_id": REPORT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "input_sha256": input_sha256,
        "measurements_sha256": measurements_doc["integrity"]["measurements_sha256"],
        "summary": {
            "term_count": len(term_index),
            "target_count": len(results),
            "measured_target_count": len(measurement_index),
            "decision_counts": {
                decision: status_counts[decision] for decision in sorted(_DECISIONS)
            },
        },
        "results": results,
        "integrity": {"report_sha256": "0" * 64},
    }
    sealed = seal_payload(report, policy=REPORT_POLICY, hash_path=_REPORT_HASH_PATH)
    return validate_d2l_term_evidence_report(sealed)


def validate_d2l_term_evidence_input(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = require_mapping(payload, path="$")
    require_exact_keys(
        root,
        required={
            "schema_id",
            "schema_version",
            "source_artifacts",
            "sampling",
            "terms",
            "integrity",
        },
        path="$",
    )
    source_artifacts = _validate_source_artifacts(root["source_artifacts"])
    sampling = _validate_sampling(root["sampling"])
    terms = [
        _validate_term(row, path=f"$.terms[{index}]")
        for index, row in enumerate(require_list(root["terms"], path="$.terms"))
    ]
    require_unique([row["term_id"] for row in terms], path="$.terms[*].term_id")
    if len(terms) != sampling["selected_sample_size"]:
        raise ContractValidationError(
            "sample_count",
            "$.terms",
            "term count differs from selected_sample_size",
        )
    if any(
        len(term["contexts"]) > sampling["contexts_per_term"] for term in terms
    ):
        raise ContractValidationError(
            "context_count",
            "$.terms[*].contexts",
            "context count exceeds contexts_per_term",
        )
    observed_counts = Counter(row["stratum"] for row in terms)
    if any(
        observed_counts[name] != sampling["selected_counts"][name] for name in _STRATA
    ):
        raise ContractValidationError(
            "stratum_count",
            "$.terms",
            "term strata differ from selected_counts",
        )
    integrity = _validate_integrity(
        root["integrity"], key="input_sha256", path="$.integrity"
    )
    normalized = {
        "schema_id": require_enum(root["schema_id"], {INPUT_SCHEMA_ID}, path="$.schema_id"),
        "schema_version": require_enum(
            root["schema_version"],
            {INPUT_SCHEMA_VERSION},
            path="$.schema_version",
        ),
        "source_artifacts": source_artifacts,
        "sampling": sampling,
        "terms": terms,
        "integrity": integrity,
    }
    if not verify_payload_hash(
        normalized, policy=INPUT_POLICY, hash_path=_INPUT_HASH_PATH
    ):
        raise ContractValidationError(
            "self_hash", "$.integrity.input_sha256", "input self-hash mismatch"
        )
    return canonicalize(normalized, policy=INPUT_POLICY)


def validate_d2l_term_evidence_measurements(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    root = require_mapping(payload, path="$")
    require_exact_keys(
        root,
        required={
            "schema_id",
            "schema_version",
            "input_sha256",
            "measurements",
            "integrity",
        },
        path="$",
    )
    measurements = [
        _validate_measurement(row, path=f"$.measurements[{index}]")
        for index, row in enumerate(
            require_list(root["measurements"], path="$.measurements")
        )
    ]
    keys = [
        f"{row['term_id']}\0{row['candidate_target_id']}" for row in measurements
    ]
    require_unique(keys, path="$.measurements[*]")
    integrity = _validate_integrity(
        root["integrity"], key="measurements_sha256", path="$.integrity"
    )
    normalized = {
        "schema_id": require_enum(
            root["schema_id"], {MEASUREMENTS_SCHEMA_ID}, path="$.schema_id"
        ),
        "schema_version": require_enum(
            root["schema_version"], {SCHEMA_VERSION}, path="$.schema_version"
        ),
        "input_sha256": require_sha256(
            root["input_sha256"], path="$.input_sha256"
        ),
        "measurements": measurements,
        "integrity": integrity,
    }
    if not verify_payload_hash(
        normalized,
        policy=MEASUREMENTS_POLICY,
        hash_path=_MEASUREMENTS_HASH_PATH,
    ):
        raise ContractValidationError(
            "self_hash",
            "$.integrity.measurements_sha256",
            "measurements self-hash mismatch",
        )
    return canonicalize(normalized, policy=MEASUREMENTS_POLICY)


def validate_d2l_term_evidence_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = require_mapping(payload, path="$")
    require_exact_keys(
        root,
        required={
            "schema_id",
            "schema_version",
            "input_sha256",
            "measurements_sha256",
            "summary",
            "results",
            "integrity",
        },
        path="$",
    )
    summary = _validate_report_summary(root["summary"])
    results = [
        _validate_result(row, path=f"$.results[{index}]")
        for index, row in enumerate(require_list(root["results"], path="$.results"))
    ]
    if len(results) != summary["target_count"]:
        raise ContractValidationError(
            "target_count", "$.results", "result count differs from target_count"
        )
    observed = Counter(row["decision"] for row in results)
    if any(
        observed[decision] != summary["decision_counts"][decision]
        for decision in _DECISIONS
    ):
        raise ContractValidationError(
            "decision_count", "$.results", "result decisions differ from summary"
        )
    integrity = _validate_integrity(
        root["integrity"], key="report_sha256", path="$.integrity"
    )
    normalized = {
        "schema_id": require_enum(root["schema_id"], {REPORT_SCHEMA_ID}, path="$.schema_id"),
        "schema_version": require_enum(
            root["schema_version"], {SCHEMA_VERSION}, path="$.schema_version"
        ),
        "input_sha256": require_sha256(
            root["input_sha256"], path="$.input_sha256"
        ),
        "measurements_sha256": require_sha256(
            root["measurements_sha256"], path="$.measurements_sha256"
        ),
        "summary": summary,
        "results": results,
        "integrity": integrity,
    }
    if not verify_payload_hash(
        normalized, policy=REPORT_POLICY, hash_path=_REPORT_HASH_PATH
    ):
        raise ContractValidationError(
            "self_hash", "$.integrity.report_sha256", "report self-hash mismatch"
        )
    return canonicalize(normalized, policy=REPORT_POLICY)


def write_canonical_json(
    path: Path, payload: Mapping[str, Any], *, document_kind: str
) -> None:
    policy = {
        "input": INPUT_POLICY,
        "measurements": MEASUREMENTS_POLICY,
        "report": REPORT_POLICY,
        "context_run": CONTEXT_RUN_POLICY,
    }.get(document_kind)
    if policy is None:
        raise ValueError(f"unknown document kind: {document_kind}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(dict(payload), policy=policy) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractValidationError("missing_file", str(path), "file not found") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError(
            "invalid_json", str(path), f"cannot read JSON: {exc}"
        ) from exc


def _artifact_binding(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {
        "ref": resolved.as_posix(),
        "physical_sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
    }


def _candidate_index(candidates: Sequence[Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(candidates):
        path = f"$.candidate_index.candidates[{index}]"
        row = require_mapping(raw, path=path)
        candidate_id = require_string(row.get("candidate_id"), path=f"{path}.candidate_id")
        if candidate_id in result:
            raise ContractValidationError(
                "duplicate_candidate", f"{path}.candidate_id", candidate_id
            )
        _string_list(row.get("surfaces"), path=f"{path}.surfaces", minimum=1)
        _string_list(
            row.get("evidence_block_ids"),
            path=f"{path}.evidence_block_ids",
            minimum=0,
        )
        result[candidate_id] = row
    return result


def _document_block_index(
    document: Mapping[str, Any],
    *,
    document_id: str,
) -> dict[str, dict[str, Any]]:
    chapters = require_list(document.get("chapters"), path="$.document.chapters")
    result: dict[str, dict[str, Any]] = {}
    global_index = 0
    for chapter_index, raw_chapter in enumerate(chapters):
        chapter_path = f"$.document.chapters[{chapter_index}]"
        chapter = require_mapping(raw_chapter, path=chapter_path)
        chapter_id = require_string(
            chapter.get("chapter_id"), path=f"{chapter_path}.chapter_id"
        )
        blocks = require_list(chapter.get("blocks"), path=f"{chapter_path}.blocks")
        for block_index, raw_block in enumerate(blocks):
            block_path = f"{chapter_path}.blocks[{block_index}]"
            block = require_mapping(raw_block, path=block_path)
            block_id = require_string(block.get("block_id"), path=f"{block_path}.block_id")
            if block_id in result:
                raise ContractValidationError("duplicate_block", block_path, block_id)
            source_text = require_string(
                block.get("source_text"),
                path=f"{block_path}.source_text",
                allow_empty=True,
            )
            result[block_id] = {
                "block_id": block_id,
                "chapter_id": chapter_id,
                "block_type": require_string(
                    block.get("block_type"), path=f"{block_path}.block_type"
                ),
                "source_text": source_text,
                "source_text_sha256": _sha256_text(source_text),
                "source_provenance": build_block_source_provenance(
                    document_id=document_id,
                    chapter_id=chapter_id,
                    block_id=block_id,
                    source_text=source_text,
                ),
                "_order": global_index,
            }
            global_index += 1
    return result


def _select_contexts(
    *,
    evidence_ids: Sequence[str],
    search_surfaces: Sequence[str],
    block_by_id: Mapping[str, Mapping[str, Any]],
    limit: int,
) -> list[dict[str, str | None]]:
    selected = [
        {
            "block_id": block_id,
            "selection_kind": "sealed_evidence",
            "matched_surface": None,
        }
        for block_id in evidence_ids[:limit]
    ]
    if len(selected) >= limit:
        return selected

    patterns = _surface_patterns(search_surfaces)
    selected_ids = {row["block_id"] for row in selected}
    candidates: list[dict[str, str]] = []
    for block in sorted(block_by_id.values(), key=lambda row: int(row["_order"])):
        block_id = str(block["block_id"])
        if block_id in selected_ids:
            continue
        matched_surface = _matching_surface(str(block["source_text"]), patterns)
        if matched_surface is None:
            continue
        candidates.append(
            {
                "block_id": block_id,
                "chapter_id": str(block["chapter_id"]),
                "matched_surface": matched_surface,
            }
        )

    selected_chapters = {
        str(block_by_id[str(row["block_id"])]["chapter_id"]) for row in selected
    }
    for candidate in candidates:
        if len(selected) >= limit:
            break
        if candidate["chapter_id"] in selected_chapters:
            continue
        selected.append(
            {
                "block_id": candidate["block_id"],
                "selection_kind": "surface_match",
                "matched_surface": candidate["matched_surface"],
            }
        )
        selected_ids.add(candidate["block_id"])
        selected_chapters.add(candidate["chapter_id"])

    for candidate in candidates:
        if len(selected) >= limit:
            break
        if candidate["block_id"] in selected_ids:
            continue
        selected.append(
            {
                "block_id": candidate["block_id"],
                "selection_kind": "surface_match",
                "matched_surface": candidate["matched_surface"],
            }
        )
        selected_ids.add(candidate["block_id"])
    return selected


def _surface_patterns(
    surfaces: Sequence[str],
) -> list[tuple[str, re.Pattern[str]]]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for surface in surfaces:
        normalized = unicodedata.normalize("NFC", surface).casefold().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append((surface, normalized))
    rows.sort(key=lambda row: (-len(row[1]), row[1], row[0]))
    result = []
    for surface, normalized in rows:
        parts = re.split(r"\s+", normalized)
        body = r"\s+".join(re.escape(part) for part in parts)
        result.append((surface, re.compile(rf"(?<!\w){body}(?!\w)")))
    return result


def _matching_surface(
    source_text: str, patterns: Sequence[tuple[str, re.Pattern[str]]]
) -> str | None:
    normalized_text = unicodedata.normalize("NFC", source_text).casefold()
    for surface, pattern in patterns:
        if pattern.search(normalized_text) is not None:
            return surface
    return None


def _classify_stratum(value: Mapping[str, Any]) -> str:
    resolution = require_mapping(value.get("resolution"), path="$.value.resolution")
    lineage = require_mapping(value.get("source_lineage"), path="$.value.source_lineage")
    resolution_authority = require_string(
        resolution.get("authority_kind"), path="$.value.resolution.authority_kind"
    )
    lineage_authority = require_string(
        lineage.get("authority_kind"), path="$.value.source_lineage.authority_kind"
    )
    if (
        resolution_authority == "stage3_multi_target_audit"
        or lineage_authority == "stage2_target_collision_audit"
    ):
        return "collision_or_multi_target"
    member_ids = _string_list(
        value.get("source_member_candidate_ids"),
        path="$.value.source_member_candidate_ids",
        minimum=1,
    )
    if (
        value.get("directive") == "contextual"
        or value.get("evidence_complete") is not True
        or len(member_ids) > 1
        or _has_rows(value.get("alternative_targets"))
        or _has_rows(value.get("rejected_target_proposals"))
        or _has_rows(value.get("pending_target_proposals"))
    ):
        return "ambiguous"
    return "clear"


def _sample_records(
    populations: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    sample_size: int,
    seed: str,
) -> list[Mapping[str, Any]]:
    total = sum(len(populations[name]) for name in _STRATA)
    if sample_size > total:
        raise ContractValidationError(
            "sample_size",
            "$.sampling.requested_sample_size",
            f"requested {sample_size}, population contains {total}",
        )
    ordered = {
        name: sorted(
            populations[name],
            key=lambda row: (
                _stable_digest(seed, require_string(row.get("record_id"), path="$.record_id")),
                str(row.get("record_id")),
            ),
        )
        for name in _STRATA
    }
    base, remainder = divmod(sample_size, len(_STRATA))
    quotas = {
        name: min(len(ordered[name]), base + (1 if index < remainder else 0))
        for index, name in enumerate(_STRATA)
    }
    left = sample_size - sum(quotas.values())
    while left:
        progressed = False
        for name in _STRATA:
            if quotas[name] < len(ordered[name]):
                quotas[name] += 1
                left -= 1
                progressed = True
                if not left:
                    break
        if not progressed:
            raise AssertionError("sample redistribution exhausted unexpectedly")
    return [
        row
        for name in _STRATA
        for row in ordered[name][: quotas[name]]
    ]


def _term_view(
    record: Mapping[str, Any],
    *,
    candidate_by_id: Mapping[str, Mapping[str, Any]],
    block_by_id: Mapping[str, Mapping[str, Any]],
    contexts_per_term: int,
) -> dict[str, Any]:
    value = require_mapping(record.get("value"), path="$.record.value")
    term_id = require_string(record.get("record_id"), path="$.record.record_id")
    member_ids = _string_list(
        value.get("source_member_candidate_ids"),
        path="$.record.value.source_member_candidate_ids",
        minimum=1,
    )
    evidence_ids = _string_list(
        value.get("evidence_block_ids"),
        path="$.record.value.evidence_block_ids",
        minimum=0,
    )
    if not evidence_ids:
        evidence_ids = _stable_unique(
            block_id
            for candidate_id in member_ids
            for block_id in _string_list(
                candidate_by_id[candidate_id].get("evidence_block_ids"),
                path=f"$.candidate[{candidate_id}].evidence_block_ids",
                minimum=0,
            )
        )
    foreign_blocks = sorted(set(evidence_ids) - block_by_id.keys())
    if foreign_blocks:
        raise ContractValidationError(
            "foreign_block",
            "$.record.value.evidence_block_ids",
            f"unknown block IDs: {', '.join(foreign_blocks)}",
        )
    if not evidence_ids:
        raise ContractValidationError(
            "missing_evidence",
            "$.record.value.evidence_block_ids",
            f"term {term_id} has no source evidence",
        )
    evidence_ids = sorted(
        set(evidence_ids), key=lambda block_id: block_by_id[block_id]["_order"]
    )
    source_term = require_string(
        value.get("canonical_source"),
        path="$.record.value.canonical_source",
        maximum=500,
    )
    source_definition = require_string(
        value.get("decision_rationale"),
        path="$.record.value.decision_rationale",
        maximum=4_000,
    )
    raw_entry_id = value.get("entry_id")
    sense_id = (
        require_string(raw_entry_id, path="$.record.value.entry_id", maximum=500)
        if raw_entry_id is not None
        else term_id
    )
    raw_chapter_id = value.get("chapter_id")
    scope_id = (
        require_string(
            raw_chapter_id,
            path="$.record.value.chapter_id",
            maximum=500,
        )
        if raw_chapter_id is not None
        else "d2l_book"
    )
    surfaces = _string_list(
        value.get("surfaces"), path="$.record.value.surfaces", minimum=1
    )
    selected_contexts = _select_contexts(
        evidence_ids=evidence_ids,
        search_surfaces=_stable_unique([source_term, *surfaces]),
        block_by_id=block_by_id,
        limit=contexts_per_term,
    )
    resolution = require_mapping(value.get("resolution"), path="$.record.value.resolution")
    lineage = require_mapping(
        value.get("source_lineage"), path="$.record.value.source_lineage"
    )
    alternatives = _target_rows(value.get("alternative_targets"), role="alternative")
    rejected = _target_rows(value.get("rejected_target_proposals"), role="rejected")
    pending = _target_rows(value.get("pending_target_proposals"), role="pending")
    canonical_target = require_string(
        value.get("canonical_target_vi"),
        path="$.record.value.canonical_target_vi",
        maximum=500,
    )
    target_specs = [
        {
            "role": "canonical",
            "target_vi": canonical_target,
            "applicability": require_nullable_string(
                value.get("canonical_applicability"),
                path="$.record.value.canonical_applicability",
                maximum=1_000,
            ),
        },
        *alternatives,
        *rejected,
        *pending,
    ]
    targets = []
    for index, target in enumerate(target_specs):
        target_id = "target_" + _stable_digest(
            term_id,
            target["role"],
            str(index),
            target["target_vi"],
            target["applicability"] or "",
        )[:24]
        targets.append({"candidate_target_id": target_id, **target})
    target_ids = [row["candidate_target_id"] for row in targets]
    require_unique(target_ids, path=f"$.terms[{term_id}].candidate_targets")
    return {
        "term_id": term_id,
        "source_term": source_term,
        "sense_id": sense_id,
        "scope_id": scope_id,
        "source_definition": source_definition,
        "sense_contract": {
            "definition_en": source_definition,
            "definition_source": "glossary_decision_rationale",
            "definition_provenance": evidence_ids,
            "definition_review_status": (
                value.get("definition_review_status")
                if value.get("definition_review_status")
                in {"VERIFIED", "UNVERIFIED", "INVALID"}
                else "UNVERIFIED"
            ),
            "sense_inventory_version": "d2l_sealed_glossary_v1",
        },
        "part_of_speech": "unknown",
        "source_occurrences": evidence_ids,
        "candidate_generation": _candidate_generation_contract(
            value=value,
            lineage=lineage,
        ),
        "sense_scope_provenance": {
            "sense_id_source": (
                "glossary_entry_id"
                if raw_entry_id is not None
                else "glossary_record_id"
            ),
            "scope_id_source": (
                "glossary_chapter_id"
                if raw_chapter_id is not None
                else "d2l_book_fallback"
            ),
            "definition_source": "glossary_decision_rationale",
            "part_of_speech_source": "unavailable",
        },
        "surfaces": surfaces,
        "stratum": _classify_stratum(value),
        "sense_note": source_definition,
        "source_member_candidate_ids": member_ids,
        "evidence_block_ids": evidence_ids,
        "contexts": [
            {
                **{
                    key: block_by_id[selection["block_id"]][key]
                    for key in (
                        "block_id",
                        "chapter_id",
                        "block_type",
                        "source_text",
                        "source_text_sha256",
                        "source_provenance",
                    )
                },
                "selection_kind": selection["selection_kind"],
                "matched_surface": selection["matched_surface"],
            }
            for selection in selected_contexts
        ],
        "candidate_targets": targets,
        "glossary_signals": {
            "lifecycle": require_string(
                record.get("lifecycle"), path="$.record.lifecycle"
            ),
            "directive": require_string(
                value.get("directive"), path="$.record.value.directive"
            ),
            "evidence_complete": value.get("evidence_complete") is True,
            "resolution_authority": require_string(
                resolution.get("authority_kind"),
                path="$.record.value.resolution.authority_kind",
            ),
            "source_authority": require_string(
                lineage.get("authority_kind"),
                path="$.record.value.source_lineage.authority_kind",
            ),
            "alternative_target_count": len(alternatives),
            "rejected_target_count": len(rejected),
            "pending_target_count": len(pending),
        },
    }


def _candidate_generation_contract(
    *,
    value: Mapping[str, Any],
    lineage: Mapping[str, Any],
) -> dict[str, Any]:
    nested = value.get("candidate_generation")
    recorded = nested if isinstance(nested, Mapping) else {}
    generator_model = _first_optional_string(
        recorded.get("generator_model"),
        value.get("generator_model"),
        lineage.get("model_id"),
    )
    prompt_version = _first_optional_string(
        recorded.get("prompt_version"),
        value.get("prompt_version"),
        lineage.get("prompt_version"),
    )
    run_id = _first_optional_string(
        recorded.get("run_id"),
        value.get("candidate_generation_run_id"),
        lineage.get("run_id"),
    )
    return {
        "generator_model": generator_model,
        "prompt_version": prompt_version,
        "run_id": run_id,
        "recording_status": (
            "RECORDED"
            if any((generator_model, prompt_version, run_id))
            else "UNAVAILABLE_IN_SEALED_ARTIFACT"
        ),
    }


def _first_optional_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None


def _score_target(
    term: Mapping[str, Any],
    target: Mapping[str, Any],
    measurement: Mapping[str, Any] | None,
) -> dict[str, Any]:
    glossary = _glossary_points(term, target)
    if measurement is None:
        components = {
            "context_substitution": _missing_component(35),
            "web_evidence": _missing_component(30),
            "back_translation": _missing_component(20),
            "glossary_consistency": glossary,
        }
        return _result_row(
            term,
            target,
            components=components,
            evidence_score=None,
            decision="PROVISIONAL",
            hard_gates=[],
            rationale_codes=["measurement_missing"],
        )

    context_results = measurement["context_results"]
    context = _context_points(context_results)
    web = _web_points(measurement["web_evidence"])
    back_translation = _back_translation_points(measurement["back_translation"])
    components = {
        "context_substitution": context,
        "web_evidence": web,
        "back_translation": back_translation,
        "glossary_consistency": glossary,
    }
    gates: list[str] = []
    if measurement["wrong_concept"]:
        gates.append("wrong_concept")
    if measurement["split_required"]:
        gates.append("split_required")
    if measurement["judge_disagreement"]:
        gates.append("judge_disagreement")
    if measurement["back_translation"] is not None and measurement[
        "back_translation"
    ]["contradiction"]:
        gates.append("back_translation_contradiction")
    independent_source_count = web["details"]["independent_source_count"]
    if not measurement["web_evidence"]:
        gates.append("no_web_evidence")
    elif independent_source_count < 2:
        gates.append("insufficient_web_independence")
    if len(context_results) < 3:
        gates.append("insufficient_context_coverage")
    if measurement["back_translation"] is None:
        gates.append("back_translation_missing")

    complete = all(row["points"] is not None for row in components.values())
    evidence_score = (
        round(sum(float(row["points"]) for row in components.values()), 2)
        if complete
        else None
    )
    if "wrong_concept" in gates:
        decision = "REJECTED"
    elif "split_required" in gates:
        decision = "SPLIT_REQUIRED"
    elif {"judge_disagreement", "back_translation_contradiction"} & set(gates):
        decision = "HUMAN_REVIEW"
    elif not complete or {
        "no_web_evidence",
        "insufficient_web_independence",
        "insufficient_context_coverage",
    } & set(gates):
        decision = "PROVISIONAL"
    elif evidence_score is not None and evidence_score >= 85:
        minimums_met = (
            float(context["points"]) / 35 >= 0.80
            and float(web["points"]) / 30 >= 0.72
            and float(back_translation["points"]) / 20 >= 0.75
        )
        if minimums_met:
            decision = "AUTO_APPROVED"
        else:
            decision = "PROVISIONAL"
            gates.append("auto_approval_minimum_not_met")
    elif evidence_score is not None and evidence_score >= 70:
        decision = "PROVISIONAL"
    elif evidence_score is not None and evidence_score >= 55:
        decision = "HUMAN_REVIEW"
    else:
        decision = "REJECTED"
    rationale = list(gates)
    if not rationale:
        rationale.append(
            "weighted_evidence_auto_approved"
            if decision == "AUTO_APPROVED"
            else "weighted_evidence_threshold_applied"
        )
    return _result_row(
        term,
        target,
        components=components,
        evidence_score=evidence_score,
        decision=decision,
        hard_gates=gates,
        rationale_codes=rationale,
    )


def _validate_measurement_binding(
    term: Mapping[str, Any], measurement: Mapping[str, Any]
) -> None:
    allowed_context_ids = {row["block_id"] for row in term["contexts"]}
    measured_context_ids = [
        row["block_id"] for row in measurement["context_results"]
    ]
    foreign_context_ids = sorted(set(measured_context_ids) - allowed_context_ids)
    if foreign_context_ids:
        raise ContractValidationError(
            "foreign_context",
            "$.measurements.context_results",
            f"context blocks are outside the extracted input: {', '.join(foreign_context_ids)}",
        )
    if len(measured_context_ids) != len(set(measured_context_ids)):
        raise ContractValidationError(
            "duplicate_context",
            "$.measurements.context_results",
            "a source context may be judged at most once",
        )
    back_translation = measurement["back_translation"]
    if back_translation is None:
        return
    back_translation_ids = [
        row["block_id"] for row in back_translation["sentence_results"]
    ]
    foreign_back_translation_ids = sorted(
        set(back_translation_ids) - set(measured_context_ids)
    )
    if foreign_back_translation_ids:
        raise ContractValidationError(
            "back_translation_binding",
            "$.measurements.back_translation.sentence_results",
            "back-translations must bind judged context blocks",
        )
    if len(back_translation_ids) != len(set(back_translation_ids)):
        raise ContractValidationError(
            "duplicate_context",
            "$.measurements.back_translation.sentence_results",
            "a source context may be back-translated at most once",
        )


def _context_points(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    labels = [row["label"] for row in rows]
    counts = Counter(labels)
    raw_scores = [row.get("raw_score") for row in rows]
    if len(labels) < 3:
        return {
            "points": None,
            "maximum_points": 35,
            "measurement_count": len(labels),
            "details": {
                "context_score_30": None,
                "pass_count": counts["PASS"],
                "minor_count": counts["MINOR"],
                "fail_count": counts["FAIL"],
            },
        }
    if any(value is not None for value in raw_scores):
        if any(value is None for value in raw_scores):
            raise ContractValidationError(
                "partial_raw_scores",
                "$.measurements.context_results",
                "raw_score must be present for every context or none",
            )
        numeric = [float(value) for value in raw_scores if value is not None]
        ratio = sum(numeric) / (10 * len(numeric))
        context_score_30: float | None = round(ratio * 30, 2)
        raw_details = {
            "minimum_raw_score": min(numeric),
            "maximum_raw_score": max(numeric),
            "score_range": max(numeric) - min(numeric),
        }
    else:
        ratio = sum(
            {"PASS": 1.0, "MINOR": 0.5, "FAIL": 0.0}[row] for row in labels
        ) / len(labels)
        context_score_30 = round(ratio * 30, 2)
        raw_details = {}
    points = round(ratio * 35, 2)
    return {
        "points": points,
        "maximum_points": 35,
        "measurement_count": len(labels),
        "details": {
            "context_score_30": context_score_30,
            "pass_count": counts["PASS"],
            "minor_count": counts["MINOR"],
            "fail_count": counts["FAIL"],
            **raw_details,
        },
    }


def _web_points(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "points": None,
            "maximum_points": 30,
            "measurement_count": 0,
            "details": {"independent_source_count": 0},
        }
    best_by_group: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        group = row["independence_group"]
        current = best_by_group.get(group)
        rank = (
            row["concept_match"],
            row["source_quality"],
            row["domain_relevance"],
            row["evidence_id"],
        )
        if current is None or rank > (
            current["concept_match"],
            current["source_quality"],
            current["domain_relevance"],
            current["evidence_id"],
        ):
            best_by_group[group] = row
    selected = list(best_by_group.values())
    source_quality = max(float(row["source_quality"]) for row in selected)
    domain_relevance = _mean(float(row["domain_relevance"]) for row in selected)
    concept_match = _mean(float(row["concept_match"]) for row in selected)
    independent_count = len(selected)
    points = round(
        source_quality * 10
        + min(independent_count / 3, 1.0) * 6
        + domain_relevance * 7
        + concept_match * 7,
        2,
    )
    return {
        "points": points,
        "maximum_points": 30,
        "measurement_count": len(rows),
        "details": {
            "independent_source_count": independent_count,
            "best_source_quality": round(source_quality, 4),
            "mean_domain_relevance": round(domain_relevance, 4),
            "mean_concept_match": round(concept_match, 4),
        },
    }


def _back_translation_points(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "points": None,
            "maximum_points": 20,
            "measurement_count": 0,
            "details": {"contradiction": False},
        }
    sentence_results = row["sentence_results"]
    if len(sentence_results) < 3:
        return {
            "points": None,
            "maximum_points": 20,
            "measurement_count": len(sentence_results),
            "details": {"contradiction": row["contradiction"]},
        }
    sentence_mean = _mean(float(value["match"]) for value in sentence_results)
    points = round(
        float(row["definition_match"]) * 8
        + sentence_mean * 8
        + (0 if row["contradiction"] else 4),
        2,
    )
    return {
        "points": points,
        "maximum_points": 20,
        "measurement_count": len(sentence_results) + 1,
        "details": {
            "definition_match": row["definition_match"],
            "mean_sentence_match": round(sentence_mean, 4),
            "contradiction": row["contradiction"],
        },
    }


def _glossary_points(
    term: Mapping[str, Any], target: Mapping[str, Any]
) -> dict[str, Any]:
    signals = term["glossary_signals"]
    valid = (
        signals["lifecycle"] == "committed"
        and signals["evidence_complete"]
        and signals["pending_target_count"] == 0
        and target["role"] not in {"rejected", "pending"}
        and (target["role"] != "alternative" or target["applicability"] is not None)
    )
    points = 15 if valid else 0 if target["role"] in {"rejected", "pending"} else 8
    return {
        "points": points,
        "maximum_points": 15,
        "measurement_count": 1,
        "details": {
            "committed": signals["lifecycle"] == "committed",
            "evidence_complete": signals["evidence_complete"],
            "pending_target_count": signals["pending_target_count"],
            "applicability_explicit": target["role"] != "alternative"
            or target["applicability"] is not None,
        },
    }


def _result_row(
    term: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    components: Mapping[str, Any],
    evidence_score: float | None,
    decision: str,
    hard_gates: Sequence[str],
    rationale_codes: Sequence[str],
) -> dict[str, Any]:
    measured_max = sum(
        row["maximum_points"] for row in components.values() if row["points"] is not None
    )
    observed = sum(
        float(row["points"]) for row in components.values() if row["points"] is not None
    )
    return {
        "term_id": term["term_id"],
        "candidate_target_id": target["candidate_target_id"],
        "source_term": term["source_term"],
        "target_vi": target["target_vi"],
        "target_role": target["role"],
        "stratum": term["stratum"],
        "component_scores": dict(components),
        "observed_points": round(observed, 2),
        "measured_maximum_points": measured_max,
        "evidence_score": evidence_score,
        "decision": decision,
        "hard_gates": list(hard_gates),
        "rationale_codes": list(rationale_codes),
    }


def _validate_source_artifacts(value: Any) -> dict[str, Any]:
    root = require_mapping(value, path="$.source_artifacts")
    require_exact_keys(
        root, required={"candidate_index", "glossary", "document"}, path="$.source_artifacts"
    )
    return {
        name: _validate_artifact_binding(
            root[name], path=f"$.source_artifacts.{name}"
        )
        for name in ("candidate_index", "glossary", "document")
    }


def _validate_artifact_binding(value: Any, *, path: str) -> dict[str, str]:
    row = require_mapping(value, path=path)
    require_exact_keys(row, required={"ref", "physical_sha256"}, path=path)
    return {
        "ref": require_string(row["ref"], path=f"{path}.ref", maximum=4_000),
        "physical_sha256": require_sha256(
            row["physical_sha256"], path=f"{path}.physical_sha256"
        ),
    }


def _validate_sampling(value: Any) -> dict[str, Any]:
    path = "$.sampling"
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "seed",
            "requested_sample_size",
            "selected_sample_size",
            "contexts_per_term",
            "context_enrichment_policy",
            "population_counts",
            "selected_counts",
        },
        path=path,
    )
    population = _validate_count_map(row["population_counts"], path=f"{path}.population_counts")
    selected = _validate_count_map(row["selected_counts"], path=f"{path}.selected_counts")
    requested = require_int(
        row["requested_sample_size"], path=f"{path}.requested_sample_size", minimum=1
    )
    selected_size = require_int(
        row["selected_sample_size"], path=f"{path}.selected_sample_size", minimum=1
    )
    if selected_size > requested:
        raise ContractValidationError("sample_count", path, "selected exceeds requested")
    if sum(selected.values()) != selected_size:
        raise ContractValidationError(
            "sample_count", f"{path}.selected_counts", "counts do not sum to selected size"
        )
    if any(selected[name] > population[name] for name in _STRATA):
        raise ContractValidationError(
            "sample_count", f"{path}.selected_counts", "selected count exceeds population"
        )
    return {
        "seed": require_string(row["seed"], path=f"{path}.seed", maximum=200),
        "requested_sample_size": requested,
        "selected_sample_size": selected_size,
        "contexts_per_term": require_int(
            row["contexts_per_term"], path=f"{path}.contexts_per_term", minimum=1
        ),
        "context_enrichment_policy": require_enum(
            row["context_enrichment_policy"],
            {CONTEXT_ENRICHMENT_POLICY},
            path=f"{path}.context_enrichment_policy",
        ),
        "population_counts": population,
        "selected_counts": selected,
    }


def _validate_count_map(value: Any, *, path: str) -> dict[str, int]:
    row = require_mapping(value, path=path)
    require_exact_keys(row, required=set(_STRATA), path=path)
    return {
        name: require_int(row[name], path=f"{path}.{name}", minimum=0)
        for name in _STRATA
    }


def _validate_term(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "term_id",
            "source_term",
            "sense_id",
            "scope_id",
            "source_definition",
            "sense_contract",
            "part_of_speech",
            "source_occurrences",
            "candidate_generation",
            "sense_scope_provenance",
            "surfaces",
            "stratum",
            "sense_note",
            "source_member_candidate_ids",
            "evidence_block_ids",
            "contexts",
            "candidate_targets",
            "glossary_signals",
        },
        path=path,
    )
    source_term = require_string(
        row["source_term"], path=f"{path}.source_term", maximum=500
    )
    source_definition = require_string(
        row["source_definition"],
        path=f"{path}.source_definition",
        maximum=4_000,
    )
    sense_contract = _validate_sense_contract(
        row["sense_contract"], path=f"{path}.sense_contract"
    )
    if sense_contract["definition_en"] != source_definition:
        raise ContractValidationError(
            "sense_contract_binding",
            f"{path}.sense_contract.definition_en",
            "sense contract definition must match source_definition",
        )
    surfaces = _string_list(row["surfaces"], path=f"{path}.surfaces", minimum=1)
    contexts = [
        _validate_context(child, path=f"{path}.contexts[{index}]")
        for index, child in enumerate(require_list(row["contexts"], path=f"{path}.contexts"))
    ]
    if not contexts:
        raise ContractValidationError("missing_context", f"{path}.contexts", "must not be empty")
    evidence_ids = _string_list(
        row["evidence_block_ids"], path=f"{path}.evidence_block_ids", minimum=1
    )
    source_occurrences = _string_list(
        row["source_occurrences"], path=f"{path}.source_occurrences", minimum=1
    )
    if source_occurrences != evidence_ids:
        raise ContractValidationError(
            "source_occurrence_binding",
            f"{path}.source_occurrences",
            "source occurrences must bind the exact evidence block sequence",
        )
    if not set(sense_contract["definition_provenance"]).issubset(
        source_occurrences
    ):
        raise ContractValidationError(
            "sense_contract_binding",
            f"{path}.sense_contract.definition_provenance",
            "definition provenance must bind source occurrences",
        )
    context_ids = [child["block_id"] for child in contexts]
    require_unique(context_ids, path=f"{path}.contexts[*].block_id")
    allowed_surfaces = [source_term, *surfaces]
    for index, context in enumerate(contexts):
        context_path = f"{path}.contexts[{index}]"
        if context["selection_kind"] == "sealed_evidence":
            if context["block_id"] not in evidence_ids:
                raise ContractValidationError(
                    "context_binding",
                    context_path,
                    "sealed context is outside evidence block IDs",
                )
            if context["matched_surface"] is not None:
                raise ContractValidationError(
                    "context_binding",
                    f"{context_path}.matched_surface",
                    "sealed context must not claim a surface match",
                )
            continue
        matched_surface = context["matched_surface"]
        if context["block_id"] in evidence_ids:
            raise ContractValidationError(
                "context_binding",
                context_path,
                "surface-match context duplicates sealed evidence",
            )
        if matched_surface not in allowed_surfaces:
            raise ContractValidationError(
                "surface_binding",
                f"{context_path}.matched_surface",
                "matched surface is outside the term surface set",
            )
        if (
            _matching_surface(
                context["source_text"], _surface_patterns([matched_surface])
            )
            is None
        ):
            raise ContractValidationError(
                "surface_binding",
                context_path,
                "matched surface is absent from source_text",
            )
    targets = [
        _validate_target(child, path=f"{path}.candidate_targets[{index}]")
        for index, child in enumerate(
            require_list(row["candidate_targets"], path=f"{path}.candidate_targets")
        )
    ]
    if not targets or targets[0]["role"] != "canonical":
        raise ContractValidationError(
            "canonical_target",
            f"{path}.candidate_targets",
            "first target must be canonical",
        )
    require_unique(
        [child["candidate_target_id"] for child in targets],
        path=f"{path}.candidate_targets[*].candidate_target_id",
    )
    return {
        "term_id": require_string(row["term_id"], path=f"{path}.term_id"),
        "source_term": source_term,
        "sense_id": require_string(
            row["sense_id"], path=f"{path}.sense_id", maximum=500
        ),
        "scope_id": require_string(
            row["scope_id"], path=f"{path}.scope_id", maximum=500
        ),
        "source_definition": source_definition,
        "sense_contract": sense_contract,
        "part_of_speech": require_string(
            row["part_of_speech"],
            path=f"{path}.part_of_speech",
            maximum=100,
        ),
        "source_occurrences": source_occurrences,
        "candidate_generation": _validate_candidate_generation(
            row["candidate_generation"],
            path=f"{path}.candidate_generation",
        ),
        "sense_scope_provenance": _validate_sense_scope_provenance(
            row["sense_scope_provenance"],
            path=f"{path}.sense_scope_provenance",
        ),
        "surfaces": surfaces,
        "stratum": require_enum(row["stratum"], _STRATA, path=f"{path}.stratum"),
        "sense_note": require_nullable_string(
            row["sense_note"], path=f"{path}.sense_note", maximum=4_000
        ),
        "source_member_candidate_ids": _string_list(
            row["source_member_candidate_ids"],
            path=f"{path}.source_member_candidate_ids",
            minimum=1,
        ),
        "evidence_block_ids": evidence_ids,
        "contexts": contexts,
        "candidate_targets": targets,
        "glossary_signals": _validate_glossary_signals(
            row["glossary_signals"], path=f"{path}.glossary_signals"
        ),
    }


def _validate_sense_contract(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "definition_en",
            "definition_source",
            "definition_provenance",
            "definition_review_status",
            "sense_inventory_version",
        },
        path=path,
    )
    return {
        "definition_en": require_string(
            row["definition_en"],
            path=f"{path}.definition_en",
            maximum=4_000,
        ),
        "definition_source": require_string(
            row["definition_source"],
            path=f"{path}.definition_source",
            maximum=500,
        ),
        "definition_provenance": _string_list(
            row["definition_provenance"],
            path=f"{path}.definition_provenance",
            minimum=1,
        ),
        "definition_review_status": require_enum(
            row["definition_review_status"],
            {"VERIFIED", "UNVERIFIED", "INVALID"},
            path=f"{path}.definition_review_status",
        ),
        "sense_inventory_version": require_string(
            row["sense_inventory_version"],
            path=f"{path}.sense_inventory_version",
            maximum=500,
        ),
    }


def _validate_candidate_generation(
    value: Any, *, path: str
) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "generator_model",
            "prompt_version",
            "run_id",
            "recording_status",
        },
        path=path,
    )
    fields = {
        key: require_nullable_string(
            row[key], path=f"{path}.{key}", maximum=500
        )
        for key in ("generator_model", "prompt_version", "run_id")
    }
    status = require_enum(
        row["recording_status"],
        {"RECORDED", "UNAVAILABLE_IN_SEALED_ARTIFACT"},
        path=f"{path}.recording_status",
    )
    if status == "RECORDED" and not any(fields.values()):
        raise ContractValidationError(
            "candidate_generation",
            path,
            "RECORDED requires at least one recorded generation identifier",
        )
    if status == "UNAVAILABLE_IN_SEALED_ARTIFACT" and any(fields.values()):
        raise ContractValidationError(
            "candidate_generation",
            path,
            "unavailable generation metadata must remain null",
        )
    return {**fields, "recording_status": status}


def _validate_context(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "block_id",
            "chapter_id",
            "block_type",
            "source_text",
            "source_text_sha256",
            "selection_kind",
            "matched_surface",
            "source_provenance",
        },
        path=path,
    )
    source_text = require_string(
        row["source_text"], path=f"{path}.source_text", allow_empty=True
    )
    source_hash = require_sha256(
        row["source_text_sha256"], path=f"{path}.source_text_sha256"
    )
    if source_hash != _sha256_text(source_text):
        raise ContractValidationError(
            "source_text_hash", f"{path}.source_text_sha256", "text hash mismatch"
        )
    source_provenance = validate_source_provenance(
        row["source_provenance"],
        path=f"{path}.source_provenance",
        source_text=source_text,
    )
    block_id = require_string(row["block_id"], path=f"{path}.block_id")
    chapter_id = require_string(
        row["chapter_id"], path=f"{path}.chapter_id"
    )
    if (
        source_provenance["block_id"] != block_id
        or source_provenance["chapter_id"] != chapter_id
        or source_provenance["source_hash"] != source_hash
    ):
        raise ContractValidationError(
            "source_provenance",
            f"{path}.source_provenance",
            "source locator does not bind the enclosing context",
        )
    return {
        "block_id": block_id,
        "chapter_id": chapter_id,
        "block_type": require_string(row["block_type"], path=f"{path}.block_type"),
        "source_text": source_text,
        "source_text_sha256": source_hash,
        "selection_kind": require_enum(
            row["selection_kind"],
            _CONTEXT_SELECTION_KINDS,
            path=f"{path}.selection_kind",
        ),
        "matched_surface": require_nullable_string(
            row["matched_surface"],
            path=f"{path}.matched_surface",
            maximum=500,
        ),
        "source_provenance": source_provenance,
    }


def _validate_sense_scope_provenance(value: Any, *, path: str) -> dict[str, str]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "sense_id_source",
            "scope_id_source",
            "definition_source",
            "part_of_speech_source",
        },
        path=path,
    )
    return {
        key: require_string(row[key], path=f"{path}.{key}", maximum=200)
        for key in (
            "sense_id_source",
            "scope_id_source",
            "definition_source",
            "part_of_speech_source",
        )
    }


def _validate_target(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={"candidate_target_id", "role", "target_vi", "applicability"},
        path=path,
    )
    return {
        "candidate_target_id": require_string(
            row["candidate_target_id"], path=f"{path}.candidate_target_id"
        ),
        "role": require_enum(row["role"], _TARGET_ROLES, path=f"{path}.role"),
        "target_vi": require_string(
            row["target_vi"], path=f"{path}.target_vi", maximum=500
        ),
        "applicability": require_nullable_string(
            row["applicability"], path=f"{path}.applicability", maximum=1_000
        ),
    }


def _validate_glossary_signals(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "lifecycle",
            "directive",
            "evidence_complete",
            "resolution_authority",
            "source_authority",
            "alternative_target_count",
            "rejected_target_count",
            "pending_target_count",
        },
        path=path,
    )
    if not isinstance(row["evidence_complete"], bool):
        raise ContractValidationError(
            "type", f"{path}.evidence_complete", "expected a boolean"
        )
    return {
        "lifecycle": require_string(row["lifecycle"], path=f"{path}.lifecycle"),
        "directive": require_string(row["directive"], path=f"{path}.directive"),
        "evidence_complete": row["evidence_complete"],
        "resolution_authority": require_string(
            row["resolution_authority"], path=f"{path}.resolution_authority"
        ),
        "source_authority": require_string(
            row["source_authority"], path=f"{path}.source_authority"
        ),
        "alternative_target_count": require_int(
            row["alternative_target_count"],
            path=f"{path}.alternative_target_count",
            minimum=0,
        ),
        "rejected_target_count": require_int(
            row["rejected_target_count"],
            path=f"{path}.rejected_target_count",
            minimum=0,
        ),
        "pending_target_count": require_int(
            row["pending_target_count"],
            path=f"{path}.pending_target_count",
            minimum=0,
        ),
    }


def _validate_measurement(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "term_id",
            "candidate_target_id",
            "context_results",
            "web_evidence",
            "back_translation",
            "wrong_concept",
            "split_required",
            "judge_disagreement",
        },
        path=path,
    )
    context_results = [
        _validate_context_result(child, path=f"{path}.context_results[{index}]")
        for index, child in enumerate(
            require_list(row["context_results"], path=f"{path}.context_results")
        )
    ]
    web = [
        _validate_web_evidence(child, path=f"{path}.web_evidence[{index}]")
        for index, child in enumerate(
            require_list(row["web_evidence"], path=f"{path}.web_evidence")
        )
    ]
    require_unique(
        [child["evidence_id"] for child in web],
        path=f"{path}.web_evidence[*].evidence_id",
    )
    booleans = {}
    for key in ("wrong_concept", "split_required", "judge_disagreement"):
        if not isinstance(row[key], bool):
            raise ContractValidationError("type", f"{path}.{key}", "expected a boolean")
        booleans[key] = row[key]
    return {
        "term_id": require_string(row["term_id"], path=f"{path}.term_id"),
        "candidate_target_id": require_string(
            row["candidate_target_id"], path=f"{path}.candidate_target_id"
        ),
        "context_results": context_results,
        "web_evidence": web,
        "back_translation": _validate_back_translation(
            row["back_translation"], path=f"{path}.back_translation"
        ),
        **booleans,
    }


def _validate_context_result(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "block_id",
            "label",
            "test_translation_vi",
            "judge_reason",
            "provenance",
        },
        optional={"raw_score"},
        path=path,
    )
    result = {
        "block_id": require_string(row["block_id"], path=f"{path}.block_id"),
        "label": require_enum(row["label"], _CONTEXT_LABELS, path=f"{path}.label"),
        "test_translation_vi": require_string(
            row["test_translation_vi"],
            path=f"{path}.test_translation_vi",
            maximum=8_000,
        ),
        "judge_reason": require_string(
            row["judge_reason"], path=f"{path}.judge_reason", maximum=2_000
        ),
        "provenance": _validate_provenance(
            row["provenance"], path=f"{path}.provenance"
        ),
    }
    if "raw_score" in row:
        result["raw_score"] = _bounded_number(
            row["raw_score"], path=f"{path}.raw_score", maximum=10
        )
    return result


def _validate_web_evidence(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "evidence_id",
            "query",
            "url",
            "retrieved_at",
            "source_type",
            "snippet_vi",
            "snippet_sha256",
            "content_sha256",
            "independence_group",
            "source_quality",
            "domain_relevance",
            "concept_match",
            "provenance",
        },
        path=path,
    )
    snippet = require_string(
        row["snippet_vi"], path=f"{path}.snippet_vi", maximum=8_000
    )
    snippet_sha256 = require_sha256(
        row["snippet_sha256"], path=f"{path}.snippet_sha256"
    )
    if snippet_sha256 != _sha256_text(snippet):
        raise ContractValidationError(
            "snippet_hash",
            f"{path}.snippet_sha256",
            "snippet_sha256 does not match snippet_vi",
        )
    return {
        "evidence_id": require_string(row["evidence_id"], path=f"{path}.evidence_id"),
        "query": require_string(row["query"], path=f"{path}.query", maximum=2_000),
        "url": require_string(row["url"], path=f"{path}.url", maximum=4_000),
        "retrieved_at": require_rfc3339(
            row["retrieved_at"], path=f"{path}.retrieved_at"
        ),
        "source_type": require_enum(
            row["source_type"], _SOURCE_TYPES, path=f"{path}.source_type"
        ),
        "snippet_vi": snippet,
        "snippet_sha256": snippet_sha256,
        "content_sha256": require_sha256(
            row["content_sha256"], path=f"{path}.content_sha256"
        ),
        "independence_group": require_string(
            row["independence_group"], path=f"{path}.independence_group", maximum=500
        ),
        "source_quality": _unit_interval(
            row["source_quality"], path=f"{path}.source_quality"
        ),
        "domain_relevance": _unit_interval(
            row["domain_relevance"], path=f"{path}.domain_relevance"
        ),
        "concept_match": _unit_interval(
            row["concept_match"], path=f"{path}.concept_match"
        ),
        "provenance": _validate_provenance(
            row["provenance"], path=f"{path}.provenance"
        ),
    }


def _validate_back_translation(value: Any, *, path: str) -> dict[str, Any] | None:
    if value is None:
        return None
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "definition_match",
            "definition_back_translation_en",
            "sentence_results",
            "contradiction",
            "contradiction_reason",
            "provenance",
        },
        path=path,
    )
    if not isinstance(row["contradiction"], bool):
        raise ContractValidationError(
            "type", f"{path}.contradiction", "expected a boolean"
        )
    return {
        "definition_match": _unit_interval(
            row["definition_match"], path=f"{path}.definition_match"
        ),
        "definition_back_translation_en": require_string(
            row["definition_back_translation_en"],
            path=f"{path}.definition_back_translation_en",
            maximum=4_000,
        ),
        "sentence_results": [
            _validate_back_translation_sentence(
                child, path=f"{path}.sentence_results[{index}]"
            )
            for index, child in enumerate(
                require_list(row["sentence_results"], path=f"{path}.sentence_results")
            )
        ],
        "contradiction": row["contradiction"],
        "contradiction_reason": require_nullable_string(
            row["contradiction_reason"],
            path=f"{path}.contradiction_reason",
            maximum=2_000,
        ),
        "provenance": _validate_provenance(
            row["provenance"], path=f"{path}.provenance"
        ),
    }


def _validate_back_translation_sentence(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={"block_id", "back_translation_en", "match"},
        path=path,
    )
    return {
        "block_id": require_string(row["block_id"], path=f"{path}.block_id"),
        "back_translation_en": require_string(
            row["back_translation_en"],
            path=f"{path}.back_translation_en",
            maximum=8_000,
        ),
        "match": _unit_interval(row["match"], path=f"{path}.match"),
    }


def _validate_provenance(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "model_id",
            "prompt_version",
            "prompt_sha256",
            "response_sha256",
        },
        path=path,
    )
    return {
        "model_id": require_string(
            row["model_id"], path=f"{path}.model_id", maximum=500
        ),
        "prompt_version": require_string(
            row["prompt_version"], path=f"{path}.prompt_version", maximum=200
        ),
        "prompt_sha256": require_sha256(
            row["prompt_sha256"], path=f"{path}.prompt_sha256"
        ),
        "response_sha256": require_sha256(
            row["response_sha256"], path=f"{path}.response_sha256"
        ),
    }


def _validate_report_summary(value: Any) -> dict[str, Any]:
    path = "$.summary"
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "term_count",
            "target_count",
            "measured_target_count",
            "decision_counts",
        },
        path=path,
    )
    counts = require_mapping(row["decision_counts"], path=f"{path}.decision_counts")
    require_exact_keys(counts, required=set(_DECISIONS), path=f"{path}.decision_counts")
    return {
        "term_count": require_int(row["term_count"], path=f"{path}.term_count", minimum=0),
        "target_count": require_int(
            row["target_count"], path=f"{path}.target_count", minimum=0
        ),
        "measured_target_count": require_int(
            row["measured_target_count"],
            path=f"{path}.measured_target_count",
            minimum=0,
        ),
        "decision_counts": {
            decision: require_int(
                counts[decision], path=f"{path}.decision_counts.{decision}", minimum=0
            )
            for decision in sorted(_DECISIONS)
        },
    }


def _validate_result(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={
            "term_id",
            "candidate_target_id",
            "source_term",
            "target_vi",
            "target_role",
            "stratum",
            "component_scores",
            "observed_points",
            "measured_maximum_points",
            "evidence_score",
            "decision",
            "hard_gates",
            "rationale_codes",
        },
        path=path,
    )
    components = require_mapping(row["component_scores"], path=f"{path}.component_scores")
    component_names = {
        "context_substitution",
        "web_evidence",
        "back_translation",
        "glossary_consistency",
    }
    require_exact_keys(components, required=component_names, path=f"{path}.component_scores")
    validated_components = {
        name: _validate_component_score(
            components[name], path=f"{path}.component_scores.{name}"
        )
        for name in sorted(component_names)
    }
    evidence_score = row["evidence_score"]
    if evidence_score is not None:
        evidence_score = _bounded_number(
            evidence_score, path=f"{path}.evidence_score", maximum=100
        )
    return {
        "term_id": require_string(row["term_id"], path=f"{path}.term_id"),
        "candidate_target_id": require_string(
            row["candidate_target_id"], path=f"{path}.candidate_target_id"
        ),
        "source_term": require_string(row["source_term"], path=f"{path}.source_term"),
        "target_vi": require_string(row["target_vi"], path=f"{path}.target_vi"),
        "target_role": require_enum(
            row["target_role"], _TARGET_ROLES, path=f"{path}.target_role"
        ),
        "stratum": require_enum(row["stratum"], _STRATA, path=f"{path}.stratum"),
        "component_scores": validated_components,
        "observed_points": _bounded_number(
            row["observed_points"], path=f"{path}.observed_points", maximum=100
        ),
        "measured_maximum_points": require_int(
            row["measured_maximum_points"],
            path=f"{path}.measured_maximum_points",
            minimum=0,
        ),
        "evidence_score": evidence_score,
        "decision": require_enum(row["decision"], _DECISIONS, path=f"{path}.decision"),
        "hard_gates": _string_list(
            row["hard_gates"], path=f"{path}.hard_gates", minimum=0
        ),
        "rationale_codes": _string_list(
            row["rationale_codes"], path=f"{path}.rationale_codes", minimum=1
        ),
    }


def _validate_component_score(value: Any, *, path: str) -> dict[str, Any]:
    row = require_mapping(value, path=path)
    require_exact_keys(
        row,
        required={"points", "maximum_points", "measurement_count", "details"},
        path=path,
    )
    maximum = require_int(
        row["maximum_points"], path=f"{path}.maximum_points", minimum=0
    )
    points = row["points"]
    if points is not None:
        points = _bounded_number(points, path=f"{path}.points", maximum=maximum)
    details = require_mapping(row["details"], path=f"{path}.details")
    return {
        "points": points,
        "maximum_points": maximum,
        "measurement_count": require_int(
            row["measurement_count"], path=f"{path}.measurement_count", minimum=0
        ),
        "details": dict(details),
    }


def _validate_integrity(value: Any, *, key: str, path: str) -> dict[str, str]:
    row = require_mapping(value, path=path)
    require_exact_keys(row, required={key}, path=path)
    return {key: require_sha256(row[key], path=f"{path}.{key}")}


def _target_rows(value: Any, *, role: str) -> list[dict[str, Any]]:
    rows = require_list(value, path=f"$.value.{role}_targets")
    result = []
    for index, raw in enumerate(rows):
        path = f"$.value.{role}_targets[{index}]"
        if isinstance(raw, str):
            target_vi = require_string(raw, path=path, maximum=500)
            applicability = None
        else:
            row = require_mapping(raw, path=path)
            target_vi = require_string(
                row.get("target_vi"), path=f"{path}.target_vi", maximum=500
            )
            applicability = require_nullable_string(
                row.get("applicability"),
                path=f"{path}.applicability",
                maximum=1_000,
            )
        result.append(
            {"role": role, "target_vi": target_vi, "applicability": applicability}
        )
    return result


def _string_list(value: Any, *, path: str, minimum: int) -> list[str]:
    raw = require_list(value, path=path)
    result = [
        require_string(child, path=f"{path}[{index}]")
        for index, child in enumerate(raw)
    ]
    if len(result) < minimum:
        raise ContractValidationError(
            "array_too_short", path, f"expected at least {minimum} items"
        )
    require_unique(result, path=path)
    return result


def _has_rows(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _stable_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _stable_digest(*parts: str) -> str:
    payload = "\0".join(unicodedata.normalize("NFC", part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(unicodedata.normalize("NFC", value).encode("utf-8")).hexdigest()


def _unit_interval(value: Any, *, path: str) -> float:
    return float(_bounded_number(value, path=path, maximum=1))


def _bounded_number(value: Any, *, path: str, maximum: float) -> int | float:
    result = require_number(value, path=path, minimum=0)
    if result > maximum:
        raise ContractValidationError("range", path, f"must be <= {maximum}")
    return result


def _mean(values: Iterable[float]) -> float:
    rows = list(values)
    return sum(rows) / len(rows)


def _missing_component(maximum_points: int) -> dict[str, Any]:
    return {
        "points": None,
        "maximum_points": maximum_points,
        "measurement_count": 0,
        "details": {},
    }


# Compatibility facade: Context Substitution V1 lives in a package of focused
# modules; existing callers can keep importing the original evidence module.
from pipeline.eval.terminology_evidence.context_substitution.v2.runtime.engine import (  # noqa: E402
    run_d2l_context_substitution,
)
from pipeline.eval.terminology_evidence.context_substitution.v2.providers.base import (  # noqa: E402
    ContextExecutionError,
    ContextProviderRoute,
    FailoverStructuredModel,
    ProviderRawResponse,
)
from pipeline.eval.terminology_evidence.context_substitution.v2.contracts.run import (  # noqa: E402
    context_substitution_to_measurements,
    seal_context_substitution_run as seal_d2l_context_substitution_run,
    validate_context_substitution_run as validate_d2l_context_substitution_run,
)
