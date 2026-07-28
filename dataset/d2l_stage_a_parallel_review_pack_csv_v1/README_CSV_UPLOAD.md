# Stage A CSV upload package

This folder is a CSV/Markdown projection of the five-case parallel review pilot.
It exists only for AI interfaces that do not accept JSON or JSONL uploads.

Send reviewer slot 1 these files:

- `REVIEW_INSTRUCTIONS_CSV.md`
- `SENSE_CASEBOOK.md`
- `sense_review_cases.csv`
- `sense_review_contexts.csv`
- `ai_1.csv`

Reviewers 2 and 3 receive the corresponding `ai_2.csv` or `ai_3.csv`. Do not
share one reviewer's completed output with another reviewer.

The completed CSV must retain all immutable IDs and hashes. Fields containing
multiple IDs use semicolon separators. Convert the completed CSV back to JSONL
and run the validator from `d2l_stage_a_parallel_review_pack_v1_2` before
merging the three reviews. That merger votes on the four core semantic fields
and keeps `scope_note` as non-voting audit text.
