# Parallel review instructions

Each reviewer receives an independent copy of this package and edits exactly one
assigned file: `ai_1.jsonl`, `ai_2.jsonl`, or `ai_3.jsonl`.

For each of the five records:

- Choose `definition_status`: `ACCEPTED`, `CORRECTED`, or `REJECTED`.
- Choose `part_of_speech_status`: `ACCEPTED`, `CORRECTED`, `UNCERTAIN`, or
  `REJECTED`.
- If accepted, copy the supplied model value exactly.
- If corrected, provide a concise replacement grounded in supplied contexts.
- Cite at least one supplied `context_id` and provide a short rationale.

Do not add, remove, reorder, or modify immutable IDs and hashes. Return five raw
JSONL lines without Markdown fences. A person may then edit the returned JSONL
directly; no separate reviewer ID, timestamp, or completion status is required.

Validate each completed file:

`python validate_review.py . ai_1.jsonl --require-complete`

After all three files pass:

`python merge_three_reviews.py . ai_1.jsonl ai_2.jsonl ai_3.jsonl --output-dir merged_review`
