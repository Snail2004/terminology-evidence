# D0 System Integration Harness Handoff V1

Status: `EV02_BOUND_D0_COHORT_READY_FOR_INDEPENDENT_REVIEW`
Live status: `REVIEW_ONLY_DRAFT_INPUT`

Base: `1ffac21e167ab87c0335a6c7772ed4b542edf0cb`
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
receipt, joins, record hashes, and zero provider/network/gold access. It then
verifies and consumes the exact accepted Evaluation EV-02 authority:

- child/tree: `7de0ecab74bc8439724e419743c18fee46cb885c` / `7d2ebf8f65051e8e0326350eb32301954fb62dfc`;
- authority ZIP: `86ca4e4453c6efc9c0fa11af1d37351c4e8640070c3ab7aa156006525c3bb63c`;
- cohort physical/self: `df19e7e605f50190e389b374d5a08589858e1ce043b935c69646a3223daa8705` / `206f5770c7ea32d5a232f986240cfdf5655700b6a15b614a2251d6caba218fad`;
- candidate-set: `e72286e06201297864d3163311336515092d841181e484c01276faa9b989fa0b`;
- selection authority: `0d52dd27e2657b9e9b0d353a5c66cc984b24dfbd6c8f6e79c98a99f69303745f`;
- canary: `candidate_479fdd8ff6d15304debec117`;
- exact cardinality: 5 senses, 15 candidates, `CANARY=1`, `REMAINDER=14`.

The D0 release no longer selects any cohort. It emits only byte-bound EV-02
phase projections:

- cohort 1: the exact EV-02 `CANARY` candidate;
- cohort 15: the exact EV-02 `CANARY + REMAINDER` candidate set.

Both builds are byte-identical. Alternate canary, candidate set, phase
membership, and cross-authority substitutions fail closed even after coherent
resealing. The official live authority remains HOLD.

Deterministic release evidence has 7 files in each build and zero A/B drift:

- manifest: `a6e8a8e3fda7a208399a2310f94692d0db50a4fda341668e07512522abfe3c47`;
- checksums: `16cef2dbdc71047cf2cf16be7d2c1ec03d16d30e20090311acd844ee5e40d67c`;
- cohort 1: `5881734bb0df2aacd05f3d383cf237c2c7289ab8e608ca9ce56ffbb43c89c096`;
- cohort 15: `fc1e696ded0beed7cd938b696c722660bee9fb1c29be15f49391b0ba9667868e`.

## Main-01 dependency

The Main-01 package is retained only as review input and cannot activate live
authority:

- final review ZIP: `423c063e1533e5c1e044a21d1b17b196b523d2615c0fd250d9687e4406f319da`;
- profile physical/self: `b9b56ce5d736a75c2084ff7f41e98f044f2d066b49e2f1e14ab3035087f8059a` / `f25afa9aa1a28de431bc9e3c8422543b95820d6d31198da8fb9437d86e2da995`;
- run-spec physical/self: `497ec63b9d4acdd88773b4f9dcc43b491efafe853af6b0750868694761ce4df7` / `7a409a656e86f4597997b87b2e666a35c52ae1a647d08c430fcb7faef43f1aff`.

## Review package integrity

`D0_SYSTEM_INTEGRATION_REVIEW_RECEIPT.json` is canonical self-hashed. Root
`CHECKSUMS.sha256` is sorted and covers every unpacked review member including
the receipt, while excluding only itself to avoid a circular hash. Missing,
extra, duplicate, unsafe, case-confusable, tampered, or resealed authority
drift fails closed.

## Gates

- focused EV-02/review-package: `9 passed`, `6 subtests`;
- full System Integration: `58 passed`, `53 subtests`;
- full JUnit: `111` cases, `0` failures/errors/skips, SHA256
  `4382b50283101c9f23fd1d166b4c39a431485c2be8341a861e5b7552c03d36fa`;
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
