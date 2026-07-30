# Batch Authority Hardening V1

Status: `BATCH_AUTHORITY_HARDENED_READY_FOR_INDEPENDENT_REVIEW`

Base: `efe70fc6a800a5a4dabfbd979bb8877e1f08d44d`

Mode: zero network, zero provider, no gold access. This child changes only
System Integration Harness-owned code, tests, schemas, and documentation.

## Closed findings

- `P0-SI-1`: new official `PRESENT` intake requires
  `HarnessProducerPackageSetV2` and a detached
  `HarnessProducerSetAcceptanceReceiptV1`. The receipt binds exact run, phase,
  split, producer role/component/version/run/commit/tree, package-set manifest
  bytes, candidate cohort, candidate-set hash, approval artifact, and a null
  final decision. An arbitrary self-hashed JSON is rejected.
- `P0-SI-2`: `HarnessExternalAcquisitionHoldReceiptV2` binds an exact
  `HarnessProducerRunAuthorizationReceiptV1` and
  `HarnessProducerRunStopEventV1`. A running/revoked/resealed chain is rejected.
  No C/E HOLD evidence package is created.
- `P1-SI-4`: active V2 inventory and sidecars derive cardinality from the exact
  cohort. End-to-end build/replay covers 1, 3, 15, 30, 90, and 150 candidates.
  The V1 sidecar family retains explicit historical replay semantics and cannot
  be mixed with V2.
- `P1-SI-8`: obsolete producer-HOLD and `adapter-create-hold-set` operational
  documentation was removed.

## Active schemas

- `ArtifactInventoryExactCohortV2@2.0.0`
- `HarnessCohortInventoryV2@2.0.0`
- `GlobalBatchAuthorityV2@2.0.0`
- `EvidenceAvailabilityManifestV2@2.0.0`
- `GlobalBatchReadinessReportV2@2.0.0`
- `HarnessEvidenceAvailabilityIntakeV2@2.0.0`
- `HarnessProducerPackageSetV2@2.0.0`
- `HarnessProducerSetAcceptanceReceiptV1@1.0.0`
- `HarnessExternalAcquisitionHoldReceiptV2@2.0.0`

V1 schema bytes and meanings are unchanged. New artifacts emit V2; replay
admits a complete V1 family only as historical evidence.

## Verified gates

```text
focused authority/cohort: 8 passed + 14 subtests
full System Integration: 44 passed + 47 subtests
Contracts V1.1:          115 passed
Global Validator V1.1:   80 passed
Context Substitution C:   79 passed
Vietnamese Attestation E: 75 passed
provider/network calls:     0 / 0
gold access:                0
AUTO_APPROVED/certificates: 0 / 0
```

Exact JUnit files are stored beside this report. The external reviewer bundle
contains the Git receipt, UTF-8 format patch, source archive, testcase identity
report, schema hashes, and byte-exact official/synthetic adapter evidence.

## Remaining hold

This implementation proves the authority path with deterministic controlled
fixtures; it does not claim that real C/E producer sets have been accepted.
Official current 50/150 admission and M6 remain blocked until Main publishes
the exact producer-safe Dataset release and independently accepts both complete
official producer package sets. Global action policy and evidence semantics are
unchanged.
