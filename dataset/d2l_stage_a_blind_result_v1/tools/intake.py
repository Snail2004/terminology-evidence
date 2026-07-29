from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path
from typing import Any

from common import read_csv, read_json, seal, sha256_bytes, sha256_file, validate_self_hash


BLIND_POLICY_ID = "d2l_cst_stage_a_blind_paired_audit_development_v1"
BLIND_OUTPUT_FIELDS = [
    "schema_id",
    "policy_id",
    "blind_case_id",
    "case_sha256",
    "term_id",
    "sense_id",
    "blind_definition_en",
    "blind_part_of_speech",
    "positive_definition_evidence_ids",
    "positive_pos_evidence_ids",
    "split_recommendation",
    "confidence",
    "rationale",
    "risk_flags",
]
REQUIRED_REVIEW_FIELDS = {
    "blind_definition_en",
    "blind_part_of_speech",
    "positive_definition_evidence_ids",
    "positive_pos_evidence_ids",
    "split_recommendation",
    "confidence",
    "rationale",
}
IDENTITY_FIELDS = {
    "case_sha256",
    "term_id",
    "sense_id",
}
ALLOWED_SPLIT_RECOMMENDATIONS = {"SPLIT", "NO_SPLIT"}
LIST_SEPARATOR = re.compile(r"\s*[;|]\s*")


def normalize_part_of_speech(value: str) -> str:
    return " ".join(value.strip().casefold().replace("_", " ").split())


def normalize_definition(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def parse_id_list(value: str) -> list[str]:
    items = [item.strip() for item in LIST_SEPARATOR.split(value.strip()) if item.strip()]
    if len(items) != len(set(items)):
        raise ValueError("list contains duplicate values")
    return items


def _parse_csv_bytes(payload: bytes, path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Review is not UTF-8: {path}") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fieldnames = list(reader.fieldnames or [])
    return fieldnames, list(reader)


def _capture_review(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    before = resolved.stat()
    payload = resolved.read_bytes()
    after = resolved.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"Review changed while being captured: {path}")
    fieldnames, rows = _parse_csv_bytes(payload, resolved)
    return {
        "resolved_path": resolved,
        "source_file_name": resolved.name,
        "size_bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "fieldnames": fieldnames,
        "rows": rows,
    }


def _validate_pack(pack_root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    manifest = read_json(pack_root / "manifest.json")
    if not validate_self_hash(manifest, "manifest_sha256"):
        raise ValueError("Blind pack manifest self-hash is invalid")
    if manifest.get("schema_id") != "D2LCSTBlindAuditPackManifestV1":
        raise ValueError("Unsupported blind pack schema")
    if manifest.get("policy_id") != BLIND_POLICY_ID:
        raise ValueError("Blind pack policy mismatch")
    if manifest.get("split") != "development" or manifest.get("sense_count") != 13:
        raise ValueError("Blind pack must contain 13 development senses")
    if manifest.get("reviewer_slots") != 3:
        raise ValueError("Blind pack must declare exactly three reviewer slots")

    for relative in ("blind_cases.csv", "blind_contexts.csv", "BLIND_REVIEW_INSTRUCTIONS.md"):
        binding = (manifest.get("files") or {}).get(relative)
        path = pack_root / relative
        if not binding or not path.is_file():
            raise ValueError(f"Blind pack binding is missing: {relative}")
        if binding.get("sha256") != sha256_file(path) or binding.get("size_bytes") != path.stat().st_size:
            raise ValueError(f"Blind pack binding drift: {relative}")

    cases = read_csv(pack_root / "blind_cases.csv")
    contexts = read_csv(pack_root / "blind_contexts.csv")
    if len(cases) != 13 or len({row["blind_case_id"] for row in cases}) != 13:
        raise ValueError("Blind pack case set is incomplete or duplicated")
    return cases, contexts, manifest


def validate_and_normalize_reviews(
    *,
    pack_root: Path,
    review_paths: list[Path],
) -> dict[str, Any]:
    if len(review_paths) != 3:
        raise ValueError("Exactly three review paths are required")
    resolved_keys = [os.path.normcase(str(path.resolve(strict=True))) for path in review_paths]
    if len(set(resolved_keys)) != 3:
        raise ValueError("Reviewer inputs must be three distinct physical paths")

    cases, contexts, manifest = _validate_pack(pack_root)
    case_by_id = {row["blind_case_id"]: row for row in cases}
    valid_contexts: dict[str, set[str]] = {case_id: set() for case_id in case_by_id}
    for row in contexts:
        case_id = row.get("blind_case_id", "")
        if case_id not in valid_contexts:
            raise ValueError(f"Context references an unknown blind case: {case_id}")
        valid_contexts[case_id].add(row["context_id"])

    captures = [_capture_review(path) for path in review_paths]
    normalized_by_slot: dict[int, list[dict[str, Any]]] = {}
    input_bindings: list[dict[str, Any]] = []
    for slot, capture in enumerate(captures, start=1):
        if capture["fieldnames"] != BLIND_OUTPUT_FIELDS:
            raise ValueError(f"Reviewer {slot} CSV columns do not match the blind template")
        rows = capture["rows"]
        if len(rows) != len(cases):
            raise ValueError(f"Reviewer {slot} must contain exactly {len(cases)} rows")
        seen: set[str] = set()
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            case_id = row.get("blind_case_id", "")
            if case_id in seen:
                raise ValueError(f"Reviewer {slot} duplicates blind case {case_id}")
            seen.add(case_id)
            case = case_by_id.get(case_id)
            if case is None:
                raise ValueError(f"Reviewer {slot} contains unknown blind case {case_id}")
            if row.get("schema_id") != "D2LCSTBlindReviewOutputV1":
                raise ValueError(f"Reviewer {slot} has an unsupported schema")
            if row.get("policy_id") != BLIND_POLICY_ID:
                raise ValueError(f"Reviewer {slot} has a policy mismatch")
            for field in IDENTITY_FIELDS:
                if row.get(field) != case.get(field):
                    raise ValueError(f"Reviewer {slot} case {case_id} has {field} drift")
            for field in REQUIRED_REVIEW_FIELDS:
                if not str(row.get(field, "")).strip():
                    raise ValueError(f"Reviewer {slot} case {case_id} leaves {field} blank")
            if row["split_recommendation"] not in ALLOWED_SPLIT_RECOMMENDATIONS:
                raise ValueError(f"Reviewer {slot} case {case_id} has invalid split recommendation")
            try:
                confidence = float(row["confidence"])
            except ValueError as exc:
                raise ValueError(f"Reviewer {slot} case {case_id} has invalid confidence") from exc
            if not 0 <= confidence <= 1:
                raise ValueError(f"Reviewer {slot} case {case_id} confidence is outside 0..1")
            definition_ids = parse_id_list(row["positive_definition_evidence_ids"])
            pos_ids = parse_id_list(row["positive_pos_evidence_ids"])
            if not definition_ids or not pos_ids:
                raise ValueError(f"Reviewer {slot} case {case_id} must cite definition and POS evidence")
            for context_id in definition_ids + pos_ids:
                if context_id not in valid_contexts[case_id]:
                    raise ValueError(
                        f"Reviewer {slot} case {case_id} cites foreign context {context_id}"
                    )
            risk_flags = parse_id_list(row.get("risk_flags", "")) if row.get("risk_flags", "").strip() else []
            if risk_flags == ["NONE"]:
                risk_flags = []
            normalized_rows.append(
                seal(
                    {
                        "schema_id": "D2LCSTBlindNormalizedReviewRecordV1",
                        "policy_id": "d2l_cst_stage_a_blind_result_intake_v1",
                        "reviewer_slot": slot,
                        "source_review_sha256": capture["sha256"],
                        "blind_case_id": case_id,
                        "case_sha256": row["case_sha256"],
                        "term_id": row["term_id"],
                        "sense_id": row["sense_id"],
                        "source_term": case["source_term"],
                        "selection_stratum": case["selection_stratum"],
                        "blind_definition_en": row["blind_definition_en"].strip(),
                        "blind_definition_normalized": normalize_definition(row["blind_definition_en"]),
                        "blind_part_of_speech": row["blind_part_of_speech"].strip(),
                        "blind_part_of_speech_normalized": normalize_part_of_speech(
                            row["blind_part_of_speech"]
                        ),
                        "positive_definition_evidence_ids": definition_ids,
                        "positive_pos_evidence_ids": pos_ids,
                        "split_recommendation": row["split_recommendation"],
                        "confidence": confidence,
                        "rationale": row["rationale"].strip(),
                        "risk_flags": risk_flags,
                        "final_glossary_decision": None,
                    },
                    "record_sha256",
                )
            )
        if seen != set(case_by_id):
            raise ValueError(f"Reviewer {slot} does not cover the exact blind case set")
        normalized_by_slot[slot] = sorted(
            normalized_rows, key=lambda value: value["blind_case_id"]
        )
        input_bindings.append(
            {
                "reviewer_slot": slot,
                "source_file_name": capture["source_file_name"],
                "sha256": capture["sha256"],
                "size_bytes": capture["size_bytes"],
            }
        )

    return {
        "cases": cases,
        "contexts": contexts,
        "pack_manifest": manifest,
        "normalized_by_slot": normalized_by_slot,
        "input_bindings": input_bindings,
    }
