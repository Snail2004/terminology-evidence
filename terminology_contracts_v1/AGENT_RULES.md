# Contract Integration Rules

## All components

- Validate schema version, canonical self hash, candidate key, and package hash.
- Reject cross-package identity or hash drift before scientific scoring.
- Do not match packages by text, array position, or row order.
- Do not reinterpret V1.0 as V1.1; use the migration adapter.

## Dataset Adapter

- Emit immutable IDs, versions, dataset manifest hash, and the explicit
  effective-sense-contract hash.
- Do not infer or fabricate a human-review binding.
- Keep raw dataset storage layout outside the runtime contract.

## C and E producers

- Consume the same `FrozenCandidateContractV1` binding.
- Preserve provider/run/replay provenance and raw-ledger references.
- Keep `final_glossary_decision` null.
- Do not read each other's output.

## Global Validator

- Apply hard gates before calibrated scoring.
- Never issue `AUTO_APPROVED` or a certificate in development mode.
- Load and verify the actual calibration artifact before frozen scoring.
- Use only registered feature names and the artifact's own threshold.

## TAC

- Consume a complete V1.1 certificate per occurrence.
- Do not reconstruct or re-decide the candidate from producer internals.

## Release discipline

V1.1 becomes immutable after release. Any contract change requires V1.2 or V2,
an explicit compatibility statement, fixtures, migration impact, and review.
