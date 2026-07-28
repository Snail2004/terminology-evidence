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
2. Evaluate hard gates in registered precedence order.
3. In development mode, emit at most `PROVISIONAL` or `HUMAN_REVIEW`.
4. In frozen mode, load and verify the calibration file and its registry.
5. Issue a certificate only for `AUTO_APPROVED` or `PROVISIONAL`.

## Dataset boundary

Call `map_candidate_key` with normalized records and explicit immutable hashes.
The contract runtime never opens or assumes a V3/pilot storage path.
