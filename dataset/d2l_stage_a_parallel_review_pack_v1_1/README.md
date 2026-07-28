# D2L Stage A parallel three-review pack v1

Send three separate copies to three reviewers. Each reviewer completes only the
assigned JSONL file. Humans may edit the returned JSONL directly. Do not combine
or expose the three files to one another before all reviews are returned.

Return either the three JSONL files or one ZIP containing exactly:

```text
ai_1.jsonl
ai_2.jsonl
ai_3.jsonl
```

The bundled merger resolves exact 3/3 agreement or exact 2/3 majority and marks
all-distinct signatures for adjudication.
