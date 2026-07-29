from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from .common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    seal_record,
    sha256_bytes,
    sha256_file,
    write_checksums,
    write_csv,
    write_json,
    write_jsonl,
)


BLIND_POLICY_ID = "d2l_fasttrack_stage_a_blind_selection_v1_1"
DISAGREEMENT_TERMS = {"contexts", "fully-connected layers", "in place"}


def _rank(label: str, sense_id: str) -> str:
    return sha256_bytes(f"{BLIND_POLICY_ID}:{label}:{sense_id}".encode("utf-8"))


def select_blind_cases(
    senses: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sense_by_id = {row["sense_id"]: row for row in senses}
    risk_by_id = {row["sense_id"]: row for row in risk_rows}
    selected: list[tuple[str, dict[str, Any]]] = []
    selected_ids: set[str] = set()

    def add(category: str, row: dict[str, Any]) -> None:
        sense_id = row["sense_id"]
        if sense_id in selected_ids:
            return
        if row["split"] != "development":
            raise ValueError(f"blind selection must be development-only: {sense_id}")
        selected.append((category, row))
        selected_ids.add(sense_id)

    development_r0 = sorted(
        (row for row in risk_rows if row["split"] == "development" and row["risk_class"] == "R0_CLEAR"),
        key=lambda row: row["sense_id"],
    )
    if len(development_r0) != 3:
        raise ValueError(f"expected exactly 3 available development R0 cases, found {len(development_r0)}")
    for row in development_r0:
        add("ALL_AVAILABLE_DEVELOPMENT_R0", row)

    clear_controls = sorted(
        (
            row
            for row in risk_rows
            if row["split"] == "development"
            and row["risk_class"] in {"R1_QUALIFIED", "R2_MISSING"}
            and sense_by_id[row["sense_id"]]["stratum"] == "clear"
            and int(row["active_real_positive_context_count"]) > 0
        ),
        key=lambda row: (_rank("clear-control", row["sense_id"]), row["sense_id"]),
    )
    if len(clear_controls) < 2:
        raise ValueError("fewer than two eligible clear controls")
    for row in clear_controls[:2]:
        add("DETERMINISTIC_CLEAR_CONTROL", row)

    disagreements = sorted(
        (
            row
            for row in risk_rows
            if str(row["source_term"]).casefold() in DISAGREEMENT_TERMS
        ),
        key=lambda row: row["source_term"].casefold(),
    )
    if len(disagreements) != 3:
        raise ValueError("expected three registered disagreement cases")
    for row in disagreements:
        add("REGISTERED_DISAGREEMENT", row)

    ambiguity_pool = [
        row
        for row in risk_rows
        if row["split"] == "development"
        and row["risk_class"] == "R3_AMBIGUOUS"
        and row["sense_id"] not in selected_ids
    ]
    adam = [row for row in ambiguity_pool if str(row["source_term"]).casefold() == "adam"]
    if len(adam) != 1:
        raise ValueError("Adam must be available as one ambiguity case")
    add("AMBIGUOUS_POLYSEMOUS", adam[0])
    ambiguity_pool = [row for row in ambiguity_pool if row["sense_id"] not in selected_ids]
    ambiguity_pool.sort(key=lambda row: (_rank("ambiguity", row["sense_id"]), row["sense_id"]))
    if len(ambiguity_pool) < 4:
        raise ValueError("fewer than four additional ambiguity cases")
    for row in ambiguity_pool[:4]:
        add("AMBIGUOUS_POLYSEMOUS", row)

    if len(selected) != 13:
        raise ValueError(f"expected 13 blind cases, found {len(selected)}")

    records: list[dict[str, Any]] = []
    for category, risk in selected:
        sense = sense_by_id[risk["sense_id"]]
        record = {
            "schema_id": "D2LFastTrackBlindSelectionCaseV1",
            "policy_id": BLIND_POLICY_ID,
            "blind_case_id": f"blindft_{sha256_bytes(risk['sense_id'].encode('utf-8'))[:16]}",
            "selection_stratum": category,
            "term_id": risk["term_id"],
            "sense_id": risk["sense_id"],
            "source_term": risk["source_term"],
            "split": risk["split"],
            "risk_class": risk["risk_class"],
            "v3_stratum": sense["stratum"],
            "active_real_positive_context_count": int(risk["active_real_positive_context_count"]),
            "review_status": "PENDING_BLIND_REVIEW",
        }
        records.append(seal_record(record))
    return records


def build_blind_pack(
    zip_path: Path,
    senses: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    contexts_by_id: dict[str, dict[str, Any]],
    parent_projection_set_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases = select_blind_cases(senses, risk_rows)
    projection_by_sense = {row["sense_id"]: row for row in projections}
    selection_counts = Counter(row["selection_stratum"] for row in cases)
    risk_counts = Counter(row["risk_class"] for row in cases)

    with tempfile.TemporaryDirectory(prefix="d2l_fasttrack_blind_") as temporary:
        root = Path(temporary)
        write_jsonl(root / "blind_cases.jsonl", cases)
        case_fields = [
            "blind_case_id",
            "selection_stratum",
            "term_id",
            "sense_id",
            "source_term",
            "split",
            "risk_class",
            "v3_stratum",
            "active_real_positive_context_count",
            "review_status",
            "record_sha256",
        ]
        write_csv(
            root / "blind_cases.csv",
            [{field: row[field] for field in case_fields} for row in cases],
            case_fields,
        )

        context_rows: list[dict[str, Any]] = []
        seen_contexts: set[str] = set()
        for case in cases:
            projection = projection_by_sense[case["sense_id"]]
            context_ids = list(dict.fromkeys(
                projection["positive_definition_evidence_ids"]
                + projection["positive_pos_evidence_ids"]
            ))
            for context_id in context_ids:
                if context_id in seen_contexts:
                    continue
                seen_contexts.add(context_id)
                context = contexts_by_id[context_id]
                provenance = context["provenance"]
                context_rows.append(
                    {
                        "context_id": context_id,
                        "sense_id": context["sense_id"],
                        "source_term": case["source_term"],
                        "context_role": context["context_role"],
                        "source_text": context["source_text"],
                        "chapter_id": provenance["chapter_id"],
                        "block_id": provenance["block_id"],
                        "sentence_id": provenance["sentence_id"],
                        "content_sha256": context["content_sha256"],
                    }
                )
        write_csv(
            root / "blind_contexts.csv",
            context_rows,
            [
                "context_id",
                "sense_id",
                "source_term",
                "context_role",
                "source_text",
                "chapter_id",
                "block_id",
                "sentence_id",
                "content_sha256",
            ],
        )

        reviewer_rows = [
            {
                "blind_case_id": row["blind_case_id"],
                "sense_id": row["sense_id"],
                "source_term": row["source_term"],
                "split_decision": "",
                "part_of_speech": "",
                "definition_en": "",
                "scope_note": "",
                "rationale": "",
                "review_status": "",
            }
            for row in cases
        ]
        reviewer_fields = [
            "blind_case_id",
            "sense_id",
            "source_term",
            "split_decision",
            "part_of_speech",
            "definition_en",
            "scope_note",
            "rationale",
            "review_status",
        ]
        for slot in (1, 2, 3):
            write_csv(root / f"blind_reviewer_{slot}.csv", reviewer_rows, reviewer_fields)
        (root / "BLIND_REVIEW_INSTRUCTIONS.md").write_text(
            "# Blind Stage A review\n\n"
            "Use only `blind_cases.csv` and `blind_contexts.csv`. Do not inspect glossary priority, "
            "model definition/POS/confidence, or another reviewer output. Fill exactly one reviewer "
            "sheet independently. Allowed split decisions: `NO_SPLIT`, `SPLIT`, `UNJUDGEABLE`. "
            "Set `review_status=REVIEWED` only after all fields are complete.\n",
            encoding="utf-8",
            newline="\n",
        )
        files = build_file_inventory(root, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LFastTrackBlindAuditPackManifestV1",
            "policy_id": BLIND_POLICY_ID,
            "status": "PENDING_BLIND_REVIEW",
            "parent_fasttrack_projection_set_sha256": parent_projection_set_sha256,
            "case_count": len(cases),
            "context_count": len(context_rows),
            "development_only": True,
            "selection_counts": dict(sorted(selection_counts.items())),
            "risk_counts": dict(sorted(risk_counts.items())),
            "files": files,
        }
        manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
        write_json(root / "manifest.json", manifest)
        write_checksums(root, root / "CHECKSUMS.sha256")
        build_deterministic_zip(root, zip_path)

    receipt = seal_record(
        {
            "schema_id": "D2LFastTrackBlindSelectionReceiptV1",
            "policy_id": BLIND_POLICY_ID,
            "status": "CURRENT_SELECTION_PENDING_REVIEW",
            "development_only": True,
            "case_count": len(cases),
            "selection_counts": dict(sorted(selection_counts.items())),
            "risk_counts": dict(sorted(risk_counts.items())),
            "available_r0_counts": {
                "development": sum(row["split"] == "development" and row["risk_class"] == "R0_CLEAR" for row in risk_rows),
                "validation": sum(row["split"] == "validation" and row["risk_class"] == "R0_CLEAR" for row in risk_rows),
                "test": sum(row["split"] == "test" and row["risk_class"] == "R0_CLEAR" for row in risk_rows),
            },
            "selection_rule": "ALL_AVAILABLE_DEVELOPMENT_R0_PLUS_2_PREREGISTERED_CLEAR_CONTROLS_PLUS_3_DISAGREEMENTS_PLUS_5_AMBIGUITY_CASES",
            "selected_sense_ids": [row["sense_id"] for row in cases],
            "selected_cases_sha256": sha256_bytes(canonical_json_bytes(cases)),
            "pack_sha256": sha256_file(zip_path),
            "matches_current_risk_policy": True,
            "historical_blind_result_reused_as_current": False,
        },
        "receipt_sha256",
    )
    return cases, receipt
