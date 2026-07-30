# D2L Stage A blind result V1

This companion validates three completed development-only blind reviews,
normalizes their list delimiters without changing the source CSV files, and
produces a sealed comparison against the anchored Stage A records.

It deliberately does not:

- infer reviewer identity or independence from filenames;
- overwrite or package the external source CSV files;
- claim semantic equivalence for independently worded definitions;
- issue a final glossary decision.

The result remains blocked until reviewer provenance and the three-case Stage A
adjudication are complete.

## Build

From the repository root:

```powershell
python dataset/d2l_stage_a_blind_result_v1/tools/build_blind_result_artifact.py `
  --pack-root dataset/d2l_stage_a_review_repair_v1_2/release/blind_audit_pack_development_v1 `
  --anchor-reference dataset/d2l_stage_a_review_repair_v1_2/release/blind_audit_anchor_reference.jsonl `
  --anchored-consensus dataset/d2l_stage_a_review_repair_v1_2/release/recomputed_consensus_records_v2.jsonl `
  --review-file C:/path/to/blind_reviewer_1.csv `
  --review-file C:/path/to/blind_reviewer_2.csv `
  --review-file C:/path/to/blind_reviewer_3.csv `
  --output-root D:/temp/blind_audit_result_v1
```

## Validate

```powershell
python dataset/d2l_stage_a_blind_result_v1/tools/validate_blind_result_artifact.py `
  --artifact-root D:/temp/blind_audit_result_v1
```

## Tests

```powershell
python -m unittest discover -s dataset/d2l_stage_a_blind_result_v1/tests -v
```
