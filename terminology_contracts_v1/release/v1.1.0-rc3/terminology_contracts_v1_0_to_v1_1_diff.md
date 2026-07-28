# Terminology Contracts V1.0 to V1.1 Diff

## Compatibility model

V1.0 is preserved byte-for-byte as a legacy schema family. V1.1 is selected by
explicit version and new producers emit only V1.1. The migration adapter is the
only normalization path.

## Canonical naming

- Gate observations serialize `action`, not gate `severity`.
- Calibration serializes `feature_contract_version`, not
  `feature_registry_version`.
- Certificates keep `validity_context_refs` and add
  `attestation_evidence_refs`; there is no `support_context_refs` alias.

## Added V1.1 fields

- Common provenance: `run_spec_id`, `execution_config_sha256`.
- Frozen candidate: canonically derived `input_contract_sha256` content binding
  plus explicit complete/legacy-incomplete status.
- C/E evidence: optional `diagnostics` plus complete producer-owned
  `gate_signals` for native V1.1 output.
- Gate observation: optional `source_modules`; three new gate IDs; exact
  projection from C/E signals.
- Gate policy: new sealed `GatePolicyArtifactV1` with per-gate allowed actions.
- Global input: embedded Effective Sense, Frozen Candidate, and
  `ConstraintEvidencePackageV1`, plus assembly hashes.
- Calibration: verification status, numerical tolerance, strict logistic model,
  replayable calibration-result metadata, gate-policy binding, and optional
  threshold-stability metadata.
- Feature registry: explicit producer path to global feature mapping.
- Global decision: full-input replay hash and calibrated score reproduction.
- Certificate: binding status, attestation refs, threshold/sense versions, and
  explicit input/C/E/constraint/global/gate/policy/decision/calibration hashes.
- TAC: explicit Unicode-codepoint offsets bound to the certificate source term.

## Migration behavior

Core data and candidate identity are preserved. Gate IDs are canonicalized and
self hashes are recomputed. Missing legacy provenance is marked
`LEGACY_INCOMPLETE`; calibration becomes `UNVERIFIED_LEGACY`. These artifacts
remain inspectable but cannot silently open native frozen issuance.

## Consumer impact

C/E add provenance and retain evidence-only authority. Global Validator verifies
real calibration files and emits run metadata. TAC requires a complete V1.1
certificate. Dataset adapters map records to contracts without exposing file
layout as runtime authority.
