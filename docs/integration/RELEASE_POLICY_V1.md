# Release Policy V1

`system_integration_harness_v1_rc1.zip` is a source/test release artifact. It
must contain only the four Harness-owned path families, release metadata, and
reports. It must not contain credentials, raw provider credentials, `.pyc`,
`__pycache__`, `.pytest_cache`, or absolute local paths as authority identity.

## Authority admission

New non-fixture runs are admitted only under `CONTRACTS_R2_CURRENT`. Admission
requires all of the following to agree exactly:

- the official public Contract R2 verifier report;
- the pinned R2 receipt and distribution artifacts;
- the canonical active Contracts Git subtree, exact reviewed tree OID, clean
  subtree status, and absence of symlink/junction/reparse members;
- the detached accepted AR-1 binding and its exact six-member evidence root;
- the separately reviewed Global action policy and authority sidecar.

The Harness seals these public inputs into each run and revalidates them before
semantic replay. No filename-based or automatic fallback from R2 to R1 exists.
No caller-supplied verifier command or conformance fixture can establish R2
authority.
The exact resealed R1 receipt is accepted only for a run that already records
`CONTRACTS_R1_HISTORICAL_REPLAY` in its sealed run specification.

## Scope and readiness

This RC is integration tooling, not Contract, Dataset, C, E, Global decision,
or production approval authority. It does not modify candidate joins,
calibration, Global action selection, or producer packages.

A real M6 pilot may be reported only when the architecture dependency contract
is satisfied and every official producer receipt is verified. Missing
dependencies are reported as `REAL_PILOT_NOT_EXECUTED` or
`BLOCKED_BY_<DEPENDENCY>`; they are not fabricated or silently normalized.

`ArtifactInventory50_150V1` does not relax this rule. Explicit C/E HOLD files
are accepted only when the caller names the corresponding role in the intake
policy, remain sealed as HOLD records, and block Global execution. The
official 5/15 Dataset pin may be preflighted while C/E remain unavailable. A
synthetic 50/150 inventory proves cardinality, identity, shared-sense and
replay behavior only; it is not an official Dataset release.

Every development run must preserve zero provider/network calls, zero
`AUTO_APPROVED`, and zero certificates. Synthetic fixture evidence remains
`SYNTHETIC_LOCAL_CONFORMANCE` regardless of whether its replay passes.
