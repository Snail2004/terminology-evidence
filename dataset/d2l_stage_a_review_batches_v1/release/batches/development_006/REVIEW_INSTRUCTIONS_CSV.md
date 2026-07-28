# Stage A review instructions

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
