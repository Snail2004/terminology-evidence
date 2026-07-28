# Terminology Contracts V1.1 RC4 Hardening Addendum

This addendum is normative where an earlier release-candidate example conflicts
with RC4.

## Certificate derivation

A complete V1.1 certificate is not an issuer-authored summary. Bundle
verification requires exact equality for:

- `allowed_variants` and Frozen Candidate `validated_variants_vi`;
- `forbidden_candidates` and Frozen Candidate `rejected_variants_vi`;
- `scope_note` and Frozen Candidate `scope_note`;
- `validity_context_refs` and C `positive_support_refs`;
- `evidence_summary.C_mean` and C `features.C_mean`;
- `evidence_summary.E_features` and the complete E `features` object;
- `threshold_version` and the calibration `operating_point_id`;
- `policy_version` and the Global Decision policy version.

The certificate must be issued at or after Global Decision completion.
Contrastive and negative/boundary contexts are never certificate validity
contexts in V1.1. Every complete certificate, including `PROVISIONAL`, binds a
calibration artifact so its threshold identity remains verifiable.

## Gate validation

Native C/E evidence requires `gate_signals` at both JSON Schema and semantic
validation layers. Explicit V1.0 migration remains legacy-incomplete and does
not fabricate signals.

A complete standalone `GateResultSetV1` is valid only when its exact sealed
`GatePolicyArtifactV1` is loaded and every triggered action is allowed for its
gate. Consumers use `validate_gate_result_with_policy(...)`.

## Closure

RC4 closes independent-review findings P0-RC3-1, P0-RC3-2, P1-1, and P1-2.
RC4 remains a release candidate until independent re-review passes.
