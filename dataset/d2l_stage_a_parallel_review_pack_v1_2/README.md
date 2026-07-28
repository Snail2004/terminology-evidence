# D2L Stage A parallel three-review pack v1.2

Send three separate copies to three reviewers. Each reviewer completes only the
assigned JSONL file. Humans may edit the returned JSONL directly. Do not combine
or expose the three files to one another before all reviews are returned.

Return either the three JSONL files or one ZIP containing exactly:

```text
ai_1.jsonl
ai_2.jsonl
ai_3.jsonl
```

The v1.2 merger votes only on the core decision fields:

- `definition_status`
- `effective_definition_en`
- `part_of_speech_status`
- `effective_part_of_speech`

`scope_note` is a non-voting explanatory field. The merger keeps every
reviewer's scope note, records all distinct variants, and chooses a deterministic
canonical note for the effective decision. Exact 3/3 or 2/3 core agreement is
therefore not blocked by harmless wording differences in scope notes. All-distinct
core signatures still require adjudication.
