# Terminology Contracts V1.1 RC2 Hardening Addendum

This addendum is normative where an RC1 example conflicts with RC2.

1. `input_contract_sha256` is SHA-256 over the canonical Frozen Candidate,
   excluding `integrity.self_sha256` and the hash field itself.
2. Native Global Input embeds Effective Sense, Frozen Candidate, and
   `ConstraintEvidencePackageV1` for sense review, polysemy, and collision.
3. Frozen scoring supports only `LOGISTIC_REGRESSION` with `LOGIT`. The exact
   feature set, coefficients, score, threshold, and decision are replayed.
4. Producer-to-global feature mapping is machine-readable in the registry.
5. Replay binds Global Input, C/E, constraints, gates, features, engine, run
   specification, and execution configuration.
6. Certificate authority is established by `verify_certificate_bundle(...)`;
   structurally valid hash strings alone are not authority.
7. TAC uses `UNICODE_CODEPOINT` offsets and its span selects the normalized
   certificate source term.
8. JSON parsing rejects `NaN`, `Infinity`, and `-Infinity`.
9. V1.0 and migrated artifacts retain legacy semantics and cannot silently
   become native `COMPLETE` artifacts.

RC2 remains a release candidate until independent re-review passes and the
`contracts-v1.1.0` tag is issued.
