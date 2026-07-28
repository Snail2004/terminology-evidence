from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from common import (
    file_bindings,
    seal,
    sha256_file,
    write_checksums,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)
from evidence import evidence_role


MANDATORY_TERMS = {"Adam", "fully-connected layers", "in place"}
BLIND_POLICY_ID = "d2l_cst_stage_a_blind_paired_audit_development_v1"


BLIND_CASE_FIELDS = [
    "schema_id",
    "policy_id",
    "blind_case_id",
    "selection_stratum",
    "case_sha256",
    "source_payload_sha256",
    "term_id",
    "sense_id",
    "scope_id",
    "source_term",
    "surfaces",
    "split",
]

BLIND_CONTEXT_FIELDS = [
    "blind_case_id",
    "term_id",
    "sense_id",
    "context_id",
    "context_role",
    "context_slot",
    "matched_surface_exact",
    "block_id",
    "chapter_id",
    "sentence_id",
    "content_sha256",
    "context_sha256",
    "source_text",
]

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


def _confidence(case: dict[str, Any]) -> float:
    return min(
        float(case.get("model_definition_confidence", 0)),
        float(case.get("model_part_of_speech_confidence", 0)),
    )


def select_blind_cases(
    cases: list[dict[str, Any]], consensus: list[dict[str, Any]]
) -> list[tuple[str, dict[str, Any]]]:
    case_by_id = {str(case["sense_id"]): case for case in cases}
    consensus_by_id = {str(row["sense_id"]): row for row in consensus}
    selected: list[tuple[str, dict[str, Any]]] = []
    selected_ids: set[str] = set()

    for case in sorted(cases, key=lambda value: str(value["source_term"]).casefold()):
        if case.get("source_term") in MANDATORY_TERMS:
            selected.append(("DISAGREEMENT", case))
            selected_ids.add(str(case["sense_id"]))

    ambiguous = sorted(
        (
            case
            for case in cases
            if str(case["sense_id"]) not in selected_ids
        ),
        key=lambda value: (_confidence(value), str(value["source_term"]).casefold()),
    )[:5]
    for case in ambiguous:
        selected.append(("AMBIGUITY_PROXY_LOW_CONFIDENCE", case))
        selected_ids.add(str(case["sense_id"]))

    unanimous = [
        case
        for case in cases
        if str(case["sense_id"]) not in selected_ids
        and consensus_by_id[str(case["sense_id"])]["agreement"] == "AGREEMENT_3_OF_3"
    ]
    unanimous.sort(
        key=lambda value: hashlib.sha256(
            f"{BLIND_POLICY_ID}|{value['sense_id']}".encode("utf-8")
        ).hexdigest()
    )
    for case in unanimous[:5]:
        selected.append(("DETERMINISTIC_RANDOM_UNANIMOUS", case))
        selected_ids.add(str(case["sense_id"]))

    if len(selected) != 13 or len(selected_ids) != 13:
        raise ValueError("Blind audit selection must contain exactly 13 unique senses")
    return selected


def _blind_case_id(case: dict[str, Any]) -> str:
    return "blind_" + hashlib.sha256(
        f"{BLIND_POLICY_ID}|{case['case_sha256']}".encode("utf-8")
    ).hexdigest()[:24]


def build_blind_pack(
    *,
    output_root: Path,
    selected: list[tuple[str, dict[str, Any]]],
    context_authority: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"Blind output already exists: {output_root}")
    output_root.mkdir(parents=True)
    case_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    casebook: list[str] = ["# Development-only blind Stage A audit", ""]

    for stratum, case in selected:
        if case.get("split") != "development":
            raise ValueError("Blind audit may contain development cases only")
        blind_id = _blind_case_id(case)
        case_row = {
            "schema_id": "D2LCSTBlindReviewCaseV1",
            "policy_id": BLIND_POLICY_ID,
            "blind_case_id": blind_id,
            "selection_stratum": stratum,
            "case_sha256": case["case_sha256"],
            "source_payload_sha256": case["source_payload_sha256"],
            "term_id": case["term_id"],
            "sense_id": case["sense_id"],
            "scope_id": case["scope_id"],
            "source_term": case["source_term"],
            "surfaces": " | ".join(case.get("surfaces") or []),
            "split": case["split"],
        }
        case_rows.append(case_row)
        output_rows.append(
            {
                "schema_id": "D2LCSTBlindReviewOutputV1",
                "policy_id": BLIND_POLICY_ID,
                "blind_case_id": blind_id,
                "case_sha256": case["case_sha256"],
                "term_id": case["term_id"],
                "sense_id": case["sense_id"],
                "blind_definition_en": "",
                "blind_part_of_speech": "",
                "positive_definition_evidence_ids": "",
                "positive_pos_evidence_ids": "",
                "split_recommendation": "",
                "confidence": "",
                "rationale": "",
                "risk_flags": "",
            }
        )
        casebook.extend([f"## {case['source_term']}", ""])
        seen: set[str] = set()
        for contexts in case.get("evidence_contexts", {}).values():
            for projected in contexts:
                context_id = str(projected["context_id"])
                if context_id in seen:
                    continue
                authority = context_authority.get(context_id)
                if authority is None or evidence_role(authority) != "POSITIVE_ELIGIBLE":
                    continue
                seen.add(context_id)
                provenance = authority.get("provenance") or {}
                source_text = str(authority.get("source_text", ""))
                row = {
                    "blind_case_id": blind_id,
                    "term_id": case["term_id"],
                    "sense_id": case["sense_id"],
                    "context_id": context_id,
                    "context_role": authority.get("context_role", ""),
                    "context_slot": authority.get("context_slot", ""),
                    "matched_surface_exact": authority.get("matched_surface", ""),
                    "block_id": provenance.get("block_id", ""),
                    "chapter_id": provenance.get("chapter_id", ""),
                    "sentence_id": provenance.get("sentence_id", ""),
                    "content_sha256": authority.get("content_sha256", ""),
                    "context_sha256": authority.get("context_sha256", ""),
                    "source_text": source_text,
                }
                context_rows.append(row)
                casebook.extend([f"- `{context_id}`: {source_text}", ""])

    write_csv(output_root / "blind_cases.csv", BLIND_CASE_FIELDS, case_rows)
    write_jsonl(output_root / "blind_cases.jsonl", case_rows)
    write_csv(output_root / "blind_contexts.csv", BLIND_CONTEXT_FIELDS, context_rows)
    for slot in (1, 2, 3):
        write_csv(
            output_root / f"blind_reviewer_{slot}.csv",
            BLIND_OUTPUT_FIELDS,
            output_rows,
        )
    write_text(output_root / "BLIND_CASEBOOK.md", "\n".join(casebook))
    write_text(
        output_root / "BLIND_REVIEW_INSTRUCTIONS.md",
        """# Blind review instructions

Decide the English definition, part of speech, and whether the case must be
split using only the supplied term, scope, surfaces, and corpus contexts.

You must not view model definitions, model confidence, anchored reviewer
outputs, validation/test cases, or another blind reviewer output. Cite corpus
context IDs separately for definition and POS. Return only your assigned CSV.
""",
    )
    manifest = seal(
        {
            "schema_id": "D2LCSTBlindAuditPackManifestV1",
            "policy_id": BLIND_POLICY_ID,
            "status": "READY_FOR_BLIND_REVIEW",
            "split": "development",
            "sense_count": len(case_rows),
            "selection_counts": {
                stratum: sum(1 for row in case_rows if row["selection_stratum"] == stratum)
                for stratum in sorted({row["selection_stratum"] for row in case_rows})
            },
            "context_count": len(context_rows),
            "reviewer_slots": 3,
            "forbidden_fields_absent": [
                "model_definition_en",
                "model_definition_confidence",
                "model_part_of_speech",
                "model_part_of_speech_confidence",
                "context_type_proposal",
            ],
            "files": file_bindings(output_root),
        },
        "manifest_sha256",
    )
    write_json(output_root / "manifest.json", manifest)
    write_checksums(output_root, output_root / "CHECKSUMS.sha256")
    return manifest


def blind_pack_hashes(pack_root: Path) -> dict[str, str]:
    return {
        "manifest_file_sha256": sha256_file(pack_root / "manifest.json"),
        "checksums_file_sha256": sha256_file(pack_root / "CHECKSUMS.sha256"),
    }
