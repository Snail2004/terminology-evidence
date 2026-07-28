# D2L Stage A review repair V1.2

This companion artifact hardens the Stage A review workflow without mutating
Dataset V3, the V1 batch release, or returned reviewer CSV files.

It provides:

- a versioned review schema with separate definition, POS, and boundary
  evidence fields;
- provenance templates bound to the exact returned review bytes;
- evidence-aware, fail-closed consensus;
- explicit adjudication directives for the three disputed development cases;
- a deterministic development-only blind-audit pack;
- a sealed repair report, manifest, checksums, and deterministic ZIP.

The builder never marks pending provenance or blind annotations as complete.
An artifact can be structurally valid while remaining blocked for semantic
finalization.

## Build

From the repository root:

```powershell
python dataset/d2l_stage_a_review_repair_v1_2/tools/build_repair_artifact.py `
  --repository-root . `
  --output-root D:/temp/d2l_stage_a_review_repair_v1_2
```

## Validate

```powershell
python dataset/d2l_stage_a_review_repair_v1_2/tools/validate_repair_artifact.py `
  --artifact-root D:/temp/d2l_stage_a_review_repair_v1_2
```

Validate a completed V1.2 review file against its exact batch and Dataset V3:

```powershell
python dataset/d2l_stage_a_review_repair_v1_2/tools/review_validation.py `
  --batch-root C:/path/to/development_005 `
  --review-file C:/path/to/reviewer_1_v1_2.csv `
  --dataset-root dataset/d2l_context_support_set_validation_ready_v3 `
  --require-complete
```

## Tests

```powershell
python -m unittest discover -s dataset/d2l_stage_a_review_repair_v1_2/tests -v
```

## Frozen boundaries

- `dataset/d2l_context_support_set_validation_ready_v3/**` is immutable.
- `dataset/d2l_stage_a_review_batches_v1/**` is read-only input.
- returned `result/*.csv` files remain byte-identical external evidence.
- `terminology_contracts_v1/**` is authority input and is never modified here.
- no validation/test batch is opened by the blind-audit builder.
- this domain does not issue `final_glossary_decision`.
