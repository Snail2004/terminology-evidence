# Terminology Inter-Module Contracts V1.1

This package is the shared boundary authority for the Dataset Adapter, Context
Substitution (C), Vietnamese Attestation (E), Global Validator, Calibration,
Terminology Certificate, and TAC.

## Authority and ownership

- C and E emit independent evidence. They never emit a final glossary decision.
- The Global Validator owns hard gates and calibrated decisions.
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
python -m terminology_contracts.cli validate-dir examples/valid/v1.1.0 --schema-dir schemas
python migrations/v1_0_0_to_v1_1_0.py source.json target.json report.json
python -m pytest -q tests
```

Frozen decisions require the calibration file and feature registry to be loaded,
not merely a hash string. Migrated legacy decision/certificate artifacts remain
`LEGACY_INCOMPLETE` until missing bindings are supplied by verified producers.
