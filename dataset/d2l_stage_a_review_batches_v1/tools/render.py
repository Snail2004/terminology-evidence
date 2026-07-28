from __future__ import annotations

from typing import Any


def review_instructions() -> str:
    return """# Stage A review instructions

Review the English term-sense cases using only the supplied corpus contexts.
`sense_review_cases.csv` contains case-level information and
`sense_review_contexts.csv` contains evidence rows. `SENSE_CASEBOOK.md`
presents the same evidence in readable form.

Edit only the assigned output file: `ai_1.csv`, `ai_2.csv`, or `ai_3.csv`.
Do not add, remove, or reorder rows. Preserve these immutable columns exactly:

- `schema_id`
- `policy_id`
- `case_sha256`
- `source_payload_sha256`
- `term_id`
- `sense_id`

For every row:

- `definition_status`: `ACCEPTED`, `CORRECTED`, or `REJECTED`.
- `part_of_speech_status`: `ACCEPTED`, `CORRECTED`, `UNCERTAIN`, or `REJECTED`.
- If accepted, copy the supplied model value exactly.
- If corrected, provide a concise replacement grounded in supplied contexts.
- `evidence_context_ids`: one or more supplied context IDs separated by `;`.
- `confidence`: a number from 0 to 1.
- `risk_flags`: leave blank when none; otherwise separate flags with `;`.
- Provide a concise `scope_note` and `rationale`.

Return the completed assigned CSV as an attached file. Do not paste its
contents into chat and do not add commentary rows or columns.
"""


def reviewer_message(slot: int, sense_count: int, batch_id: str) -> str:
    return f"""You are reviewer slot {slot} for batch `{batch_id}` containing {sense_count} English term-sense cases.

Read `REVIEW_INSTRUCTIONS_CSV.md`, `SENSE_CASEBOOK.md`,
`sense_review_cases.csv`, and `sense_review_contexts.csv`. Complete only
`ai_{slot}.csv`. Preserve every immutable ID and hash exactly. Evaluate the
English definition and part of speech using only supplied contexts. Do not
inspect or infer either other reviewer's decisions.

Return one attached file named exactly `ai_{slot}.csv`. Do not paste CSV text
into chat, do not wrap it in Markdown, and do not add columns or rows.
"""


def casebook(cases: list[dict[str, Any]], batch_id: str) -> str:
    lines = [
        f"# Stage A sense casebook: {batch_id}",
        "",
        "This casebook contains no Vietnamese candidates. Review the English",
        "sense definition and part of speech from supplied evidence only.",
        "",
    ]
    headings = (
        ("primary", "Primary contexts"),
        ("backup", "Backup contexts"),
        ("contrastive", "Contrastive contexts"),
        ("definition", "Definition evidence"),
        ("part_of_speech", "Part-of-speech evidence"),
    )
    for index, case in enumerate(cases, start=1):
        lines.extend(
            [
                f"## {index}. {case['source_term']}",
                "",
                f"- `sense_id`: `{case['sense_id']}`",
                f"- Split: `{case['split']}`",
                f"- Model definition: {case['model_definition_en']}",
                f"- Model POS: `{case['model_part_of_speech']}`",
                "",
            ]
        )
        missing = case.get("missing_evidence_context_ids") or {}
        if missing:
            rendered = ", ".join(
                f"{group}: {';'.join(context_ids)}"
                for group, context_ids in missing.items()
            )
            lines.extend(
                [
                    f"- Source package gap (not reviewable): `{rendered}`",
                    "",
                ]
            )
        for group, title in headings:
            contexts = case["evidence_contexts"][group]
            if not contexts:
                continue
            lines.extend([f"### {title}", ""])
            for context in contexts:
                source_text = " ".join(str(context["source_text"]).split())
                lines.append(f"- `{context['context_id']}`: {source_text}")
            lines.append("")
    return "\n".join(lines)


def batch_readme(batch_id: str, split: str, sense_count: int) -> str:
    return f"""# Review batch {batch_id}

- Split: `{split}`
- Term-senses: {sense_count}
- Reviewer slots: 3

For one reviewer, send the four shared source files plus only that reviewer's
blank CSV. Keep all three completed outputs independent until validation and
merge.
"""
