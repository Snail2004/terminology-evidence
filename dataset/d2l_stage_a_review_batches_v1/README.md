# D2L Stage A review batches v1

This package projects all 150 term-senses from
`d2l_context_support_set_validation_ready_v3` into small, split-safe Stage A
review batches.

Stage A reviews only the English sense definition and part of speech. It does
not expose Vietnamese candidates and it does not make a final glossary
decision.

## Batch layout

- development: 10 batches of 10 senses
- validation: 2 batches of 10 senses and 1 batch of 5 senses
- test: 2 batches of 10 senses and 1 batch of 5 senses
- total: 16 batches, 150 senses, three reviewer files per batch

No batch mixes dataset splits. The protocol is frozen before validation and
test review; validation and test outputs must not be used to revise prompts or
decision rules.

## Build and validate

From the repository root:

```powershell
python dataset/d2l_stage_a_review_batches_v1/tools/build_batches.py `
  --source-root dataset/d2l_context_support_set_validation_ready_v3 `
  --output-root dataset/d2l_stage_a_review_batches_v1/release

python dataset/d2l_stage_a_review_batches_v1/tools/validate_batches.py `
  --source-root dataset/d2l_context_support_set_validation_ready_v3 `
  --release-root dataset/d2l_stage_a_review_batches_v1/release
```

## Sending one batch to one reviewer

Send these five files from the selected batch directory:

1. `REVIEW_INSTRUCTIONS_CSV.md`
2. `SENSE_CASEBOOK.md`
3. `sense_review_cases.csv`
4. `sense_review_contexts.csv`
5. the assigned `ai_1.csv`, `ai_2.csv`, or `ai_3.csv`

Do not share completed reviewer outputs between reviewers. Each completed CSV
is validated against immutable source IDs and hashes before the three files are
merged.

## Review validation and merge

```powershell
python dataset/d2l_stage_a_review_batches_v1/tools/review_workflow.py validate `
  --batch-root dataset/d2l_stage_a_review_batches_v1/release/batches/development_001 `
  --review-file C:/path/to/ai_1.csv --require-complete

python dataset/d2l_stage_a_review_batches_v1/tools/review_workflow.py merge `
  --batch-root dataset/d2l_stage_a_review_batches_v1/release/batches/development_001 `
  --review-1 C:/path/to/ai_1.csv `
  --review-2 C:/path/to/ai_2.csv `
  --review-3 C:/path/to/ai_3.csv `
  --output-dir C:/path/to/development_001_merged
```

## Collecting all 48 returned reviews

Place returned files under one intake root. Each batch must contain three
physically distinct files, even when independent reviewers reach byte-identical
conclusions:

```text
completed_reviews/
  development_001/ai_1.csv
  development_001/ai_2.csv
  development_001/ai_3.csv
  ...
  test_003/ai_3.csv
```

Check progress without creating output:

```powershell
python dataset/d2l_stage_a_review_batches_v1/tools/review_intake.py status `
  --release-root dataset/d2l_stage_a_review_batches_v1/release `
  --intake-root C:/path/to/completed_reviews
```

After all 48 files pass, finalize all 16 batches atomically into one 150-sense
artifact. A validation or merge failure leaves the requested output path absent.

```powershell
python dataset/d2l_stage_a_review_batches_v1/tools/review_intake.py finalize `
  --release-root dataset/d2l_stage_a_review_batches_v1/release `
  --intake-root C:/path/to/completed_reviews `
  --output-root C:/path/to/finalized_stage_a_reviews
```
