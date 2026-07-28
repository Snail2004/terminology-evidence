# Merge policy v1.2

The three-review merger treats the four semantic decision fields as the voting
key:

```text
definition_status
effective_definition_en
part_of_speech_status
effective_part_of_speech
```

`scope_note` is retained for audit but is not a voting field. It is explanatory
free text and may differ in wording while describing the same boundary. The
merged record stores all distinct scope-note variants and selects the
lexicographically smallest non-empty variant from the winning semantic set as
the canonical effective note. A minority review can never supply the effective
scope note.

This policy does not normalize or override a semantic disagreement. Different
definition, POS, or status values still produce majority or adjudication as
usual.
