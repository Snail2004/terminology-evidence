# Integration Guide

## Stable join

All packages use the exact nine-field `candidate_key` plus the envelope-level
`input_contract_sha256`. Any mismatch is a contract failure; never coerce text
or join by row order.

## Version handling

Validate `schema_version` before selecting a schema. Native runtime emits V1.1.
V1.0 is accepted only through `schemas/legacy/v1.0.0` or the explicit migration
adapter, never by treating its bytes as V1.1.

## Decision order

1. Validate schema, self hashes, candidate joins, and package hashes.
2. Verify the Frozen Candidate content binding and declared constraint package.
3. Project all asserted C/E gate signals into exactly one observation per gate.
4. Load the sealed gate policy and reject actions outside each gate rule.
5. In development mode, emit at most `PROVISIONAL` or `HUMAN_REVIEW`.
6. In frozen mode, load calibration and registry, assemble mapped features,
   replay the logistic score, and derive the decision.
7. Issue a certificate only for `AUTO_APPROVED` or `PROVISIONAL`, then verify
   its complete external artifact bundle before TAC consumption.
8. Derive certificate application fields exactly from Frozen Candidate,
   positive C support, C/E features, calibration operating point, and decision
   completion time. Issuer-local subsets or overrides are forbidden in V1.1.

## Dataset boundary

Call `map_candidate_key` with normalized records and explicit immutable hashes.
The contract runtime never opens or assumes a V3/pilot storage path.
