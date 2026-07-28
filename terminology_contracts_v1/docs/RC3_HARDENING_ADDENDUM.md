# Terminology Contracts V1.1 RC3 Hardening Addendum

This addendum is normative where an RC2 example conflicts with RC3.

## Producer gate signals

Native V1.1 Context and Attestation evidence packages emit their complete
producer-owned `gate_signals` arrays. A signal declares evidence only; it never
chooses a global action. Signals must agree with deterministic producer state
and flags. The Global Validator projects the OR of C/E assertions into the
matching `GateResultSetV1` observation and preserves asserting modules, reason
codes, and evidence references.

Migrated V1.0 evidence does not fabricate signals. It remains acceptable only
with explicit legacy-migration validation and cannot become native authority.

## Sealed gate policy

`policies/gate_policy_v1.0.0.json` is the active per-gate action authority.
Complete gate results, calibration artifacts, decisions, replay metadata, and
certificates bind its exact self hash. A consumer loads the artifact and rejects
an action outside the gate's `allowed_actions` rule.

## Collision index and calibration

`ConstraintEvidencePackageV1.target_collision` binds both the collision-index
SHA-256 and a matching `COLLISION_INDEX` evidence reference. Bundle verification
loads the supplied index bytes and checks their physical SHA-256.

Calibration artifacts may include a sealed cluster-bootstrap threshold
stability block. The confidence interval must satisfy
`threshold_ci_lower <= threshold_median <= threshold_ci_upper`.

## Release status

RC3 closes independent-review findings P0-N1, P0-N2, P1-N1, and P1-N2. It
remains a release candidate until independent review accepts the exact ZIP hash.
