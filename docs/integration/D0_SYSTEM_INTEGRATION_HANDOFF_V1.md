# D0 System Integration Harness Handoff V1

Status: `TRUSTED_BATCH_AUTHORITY_AND_PRODUCER_SAFE_COHORT_READY_FOR_REVIEW`
Live status: `OFFICIAL_LIVE_AUTHORITY_NOT_YET_PROMOTED`

Base: `70eb6e0645ab00a26398520cb0610a4e5c707af1`
Mode: zero-network, zero-provider, no gold, no shared Contracts change.

## SI-01: trusted official V2 intake

- New official input admits only `HarnessEvidenceAvailabilityIntakeV2`,
  `HarnessProducerPackageSetV2`, and typed V2 external-hold receipts.
- V1 availability/package inputs are accepted only with explicit
  `HISTORICAL_REPLAY_ONLY` mode.
- `HarnessTrustedMainAuthorityProfileV1` pins issuer, authority, Dataset
  parent identity, producer Git/release receipts, Draft4 public schema bytes,
  authorization, run-start, run-stop, and `STOP_EVENT`.
- Authorization chronology and expiry are checked; run-start binds the exact
  authorization, candidate-set, run-spec, budget, and secret-readiness hashes;
  run-stop binds run-start and the final STOP_EVENT.
- External hold never creates a C/E HOLD package and remains bound to the
  exact Main stop chain.

## SI-02: producer-safe Dataset parent and D0 cohorts

The accepted Dataset parent is consumed read-only with these exact pins:

- ZIP: `8a39dce822dcb6aa228da25a5a10b7df07b6ac60ef68bca3e5466aba49449d73`
- manifest self: `194dd421ad7aef9272e90d1dff2ef96c5a8c8bf1ded7faba74283777e279ddc2`
- sense identity: `db2e5298324981c96bb83c5318fc219e2bd0c341273e439a3bae3900fe9a5708`
- candidate identity: `ea80716a38d443afa954f110b3a8346f17073f7e76aa6ea6f2fce377490dd77b`
- context identity: `eef660f3eff8dcec277ec607d0b56f16f66cdf55e708bb39cd6118167d7dd9fb`

The loader verifies 50 senses, 150 candidates, 386 contexts, publication
receipt, joins, record hashes, and zero provider/network/gold access. The D0
release emits only exact nested cohorts:

- cohort 1: the deterministic contrastive canary;
- cohort 15: five contrastive senses, three candidates per sense, including
  the canary.

Both builds are byte-identical. The official live authority remains HOLD.

## Gates

- focused trust/cohort/hardening: `14 passed`, `8 subtests`;
- full System Integration: `52 passed`, `47 subtests`;
- Contracts V1.1: `113 passed`, `2 skipped`;
- Global Validator: `80 passed`;
- Context Substitution C: `79 passed`;
- Vietnamese Attestation E: `75 passed`;
- schema validation, py_compile, CLI help, diff/scope/credential/cache scans:
  PASS;
- provider/network/Brave/gold: `0`;
- AUTO_APPROVED/certificates: `0/0`.

The exact child/parent/tree, schema hashes, JUnit identity, source archive,
Git bundle, patch, and post-test clean receipt are recorded in the external
reviewer package generated from the final Git child. No main merge or push is
performed by this worktree.

## Explicit holds

No live canary, Global CLI, M6 execution, provider call, network call, gold
access, or official runtime promotion is claimed. The Harness only verifies
and seals the accepted parent/cohort inputs; C/E semantics and Global action
policy remain unchanged.
