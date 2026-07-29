# Context Substitution V2.2 Real-Dataset Adapter Rework

## Scope

This rework closes the Context Substitution C adapter boundary only. It does
not implement Vietnamese Attestation E, web evidence, Global Validator
internals, or a final glossary decision. Global Validator V1.1 is now an active
consumer of official shared packages; C only emits the contract-conformant,
decision-neutral `ContextEvidencePackageV1@1.1.0` input assigned to it.

## Accepted source artifacts

### Validation-ready V3

- schema: `D2LContextSupportSetValidationReadyV3` / `3.0.0`
- manifest SHA-256: `258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce`
- physical manifest SHA-256: `b5f2067427c6b88344109f2c62f8db02ac61b0cef76f193d5285f378ff5f96a8`
- rows: 150 term-senses, 450 candidates, 1,340 contexts
- adaptation requires one explicit split: development, validation, or test

### Development Pilot V1.1

- schema: `D2LCSTDevelopmentOnlyPilotV1_1` / `1.1.0`
- manifest SHA-256: `599692d33f9cc162698bc0e8fc0bf60cce1715cb0f34214fec499f14c1364eb5`
- physical manifest SHA-256: `e45205adfe22b6b6c67680e159c64bb3c69c3a9849a3109a962134dc8cb3dd76`
- rows: 5 term-senses, 15 candidates, 38 contexts
- exact parent: the V3 manifest above

Absolute workstation paths embedded in historical manifests are retained as
audit text only. Runtime source bindings use portable `artifact://` references
and verified physical hashes.

## Selection modes

`MODEL_CLASSIFICATION_DEVELOPMENT` invokes the candidate-neutral selector and
cannot claim human authority. `FROZEN_HUMAN_REVIEWED_SELECTION` consumes only
`D2LContextSubstitutionFinalizedReviewedSelectionV1` issued by Dataset
Review/Adjudication Authority. C never reads raw reviewer votes, calculates a
2-of-3 majority, or performs adjudication.

The current review pack remains `STAGE_A_HUMAN_REVIEW_PENDING`. It is valid
input for human review but is not accepted as a frozen Context Substitution
authority until a complete immutable review artifact is produced.

## Reproducible zero-API commands

```powershell
python -m context_substitution.v2 reviewed-support-validate `
  --source dataset/pilot_dev_only_v1_1 `
  --parent-v3 dataset/d2l_context_support_set_validation_ready_v3

python -m context_substitution.v2 reviewed-support-to-runtime `
  --source dataset/pilot_dev_only_v1_1 `
  --parent-v3 dataset/d2l_context_support_set_validation_ready_v3 `
  --source-split development `
  --output D:/temp/cst-pilot-input.json `
  --receipt D:/temp/cst-pilot-receipt.json
```

`context-run` requires explicit `--allow-api`. Its route file references API
key environment-variable names, not raw secrets, and may define the three
registered routes: `shopaikey_gemini`, `ckey_gemini`, and
`gemini_official`. Frozen runs additionally require a sealed calibration
artifact and content-addressed response ledger.

`pilot-smoke`, `fake-provider-pilot`, `replay-validate`,
`development-fixture-freeze`, `project-context-evidence`, and
`integration-release` are zero-API integration commands. Generated evidence
must be written outside the source tree. The projection command emits official
`ContextEvidencePackageV1@1.1.0` payloads pinned to `contracts-v1.1.0`. The
development fixture freezer now emits a test-only schema which official
projection rejects. `project-context-evidence` requires Dataset-issued
`FrozenCandidateContractV1` rows. See `INTEGRATION_DEPENDENCIES_V1.md`.
Official package sets are labeled `COMPLETE`; synthetic zero-API conformance
sets are labeled `SYNTHETIC_LOCAL_CONFORMANCE` and cannot enter an integration
release.

## Fail-closed behavior

- source, parent, file, row, input, receipt, review, and calibration hash drift;
- unsafe ZIP members or source-file gaps;
- cross-split or incomplete parent binding;
- fake/zero calibration hashes or precision below the registered floor;
- missing frozen reviewed context rows;
- missing raw provider response storage in frozen execution;
- foreign, subset, extra, reordered, or drifted provider ledger attempts;
- raw response path traversal, absolute paths, or symlink escape;
- failing/empty JUnit or semantically inconsistent release evidence;
- C-local Frozen Candidate fixtures entering official projection;
- missing contrastive context or incomplete C1-C5 coverage becoming globally
  eligible;
- any final glossary decision emitted by this adapter.
