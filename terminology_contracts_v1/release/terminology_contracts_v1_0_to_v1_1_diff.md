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
- Frozen candidate: `input_contract_sha256` package join binding.
- C/E evidence: optional `diagnostics`.
- Gate observation: optional `source_modules`; three new gate IDs.
- Global input: `assembly_metadata` and source package hashes.
- Calibration: `verification_status`; active feature contract version 1.1.0.
- Global decision: `run_metadata`, replay hash, feature contract binding.
- Certificate: binding status, attestation refs, threshold/sense versions, and
  explicit input/C/E/gate/decision/calibration hashes.

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
