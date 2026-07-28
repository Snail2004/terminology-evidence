# Terminology Inter-Module Contracts V1.1

This package is the shared boundary authority for the Dataset Adapter, Context
Substitution (C), Vietnamese Attestation (E), Global Validator, Calibration,
Terminology Certificate, and TAC.

The checked-in V1.1 implementation is release candidate `v1.1.0-rc2`. It must
pass independent re-review before the immutable `contracts-v1.1.0` authority
tag is issued. RC1 and its review evidence remain archived under `release/`.
The corrected normative details are summarized in
`docs/RC2_HARDENING_ADDENDUM.md`.

## Authority and ownership

- C and E emit independent evidence. They never emit a final glossary decision.
- The Global Validator owns hard gates and calibrated decisions.
- `ConstraintEvidencePackageV1` supplies explicit sense-review, polysemy, and
  cross-candidate collision inputs; the validator does not query hidden state.
- TAC consumes only a complete `TerminologyCertificateV1`.
- Weights and thresholds come only from a loaded, sealed, verified
  `CalibrationArtifactV1`; this package does not choose them.
- Dataset files are mapping-test inputs, not runtime dependencies.

## Version layout

- `schemas/legacy/v1.0.0/`: immutable V1.0 schemas.
- `schemas/v1.1.0/`: V1.1 authority.
- `schemas/current/`: byte-identical V1.1 alias.
- `examples/valid/v1.0.0/`: legacy fixtures.
- `examples/valid/v1.1.0/`: native V1.1 fixtures.
- `examples/migrated/v1.1.0/`: deterministic migration outputs.
- `release/v1.1.0-rc2/`: corrected candidate, audit, checksum, and JUnit proof.

V1.0 is accepted only through explicit version-aware validation or migration.
New producers emit V1.1.

## Canonical names

- gate field: `action`
- calibration field: `feature_contract_version`
- certificate context fields: `validity_context_refs` and
  `attestation_evidence_refs`

The active schema does not serialize `feature_registry_version`, gate
`severity`, or `support_context_refs` aliases.

## Commands

```powershell
$env:PYTHONPATH=(Resolve-Path python).Path
python -m terminology_contracts.cli validate-dir examples/valid/v1.1.0 --schema-dir schemas --global-input examples/valid/v1.1.0/global_validator_input.json
python migrations/v1_0_0_to_v1_1_0.py source.json target.json report.json
python -m pytest -q tests
```

Frozen decisions require the calibration file and feature registry to be loaded,
not merely a hash string. They replay the exact mapped feature vector and score.
Certificate/TAC consumers use `verify_certificate_bundle(...)` to load every
referenced artifact. Migrated artifacts remain `LEGACY_INCOMPLETE`; they are
never reinterpreted as native-complete V1.1.
