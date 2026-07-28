# Terminology Contracts V1.1 RC4 Release Notes

V1.1 is a boundary hardening release. It does not change C/E algorithms, choose
weights, set thresholds, create human labels, or make glossary decisions.

## Consumer impact

- Certificate fields that affect TAC are verified as exact projections of the
  Frozen Candidate, positive C support, C/E features, calibration operating
  point, and completed Global Decision.
- Contrastive and negative/boundary contexts cannot become validity contexts.
- Native C/E `gate_signals` are required by JSON Schema as well as semantic
  validation.
- Standalone GateResultSet validation requires the exact sealed gate policy.
- Every complete certificate binds calibration, including `PROVISIONAL`, so
  its threshold identifier can be verified.

- Native C/E evidence now carries an exact producer-owned `gate_signals` set;
  the Global Validator must project asserted signals into gate results.
- `GatePolicyArtifactV1` is a sealed authority. Gate results, calibration,
  decisions, replay metadata, and certificates bind its exact hash.
- Collision status binds a collision-index evidence reference whose physical
  bytes are checked by certificate bundle verification.
- Calibration may seal cluster-bootstrap threshold-stability metadata.

- Frozen Candidate `input_contract_sha256` is now canonically derived and
  verified from its complete content.
- Global input embeds the Frozen Candidate, Effective Sense Contract, and
  `ConstraintEvidencePackageV1` needed for sense/polysemy/collision gates.
- New producers emit `schema_version: 1.1.0` and the expanded provenance fields.
- Global Validator assemblers add `assembly_metadata` and verify nested hashes.
- Frozen decisions load the sealed calibration artifact and machine-readable
  feature mapping, then replay the logistic score and exact decision.
- Decision replay binds the feature vector, all input hashes, gates, engine,
  run specification, and execution configuration.
- Certificates bind candidate, input, C, E, gates, decision, policy, sense, and
  optional calibration artifacts.
- Certificate/TAC consumers verify the actual artifact bundle; TAC also binds a
  Unicode-codepoint span to the certificate source term.
- Strict JSON parsing rejects all non-finite numbers.

## Compatibility

V1.0 schemas remain byte-preserved in `schemas/legacy/v1.0.0`. The deterministic
migration keeps evidence and candidate identity, but marks unavailable V1.0
bindings as legacy-incomplete rather than fabricating them.

RC1 remains immutable at SHA-256
`38e2ee307b247d535baedcde83427ebe3f30901d31bb921f03e6681b3160dbdc`.
RC2 remains immutable at SHA-256
`2530ebf80d4826a740d1d1efad5952adf8611cec67797d7bd806731a15cb1954`.
RC3 remains immutable at SHA-256
`25e8705631d52cccc8620dc0936c3245897b694abf8eafd8e9f54e0bd94b34f3`.
RC4 is a re-review candidate and is not the final frozen authority until that
review passes.

## Scientific boundary

C and E remain evidence producers. The Global Validator remains the only final
decision authority. Dataset V3 and pilot data are used only for mapping tests.
