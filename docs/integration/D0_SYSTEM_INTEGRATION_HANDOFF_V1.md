# D0 System Integration Harness Handoff V1

Status: `SI_EV02_PRODUCER_SAFE_BOUNDARY_READY_FOR_INDEPENDENT_REVIEW`
Live status: `REVIEW_ONLY_DRAFT_INPUT`
Run authorization: `RUN_AUTHORIZED_NO`

Base: `6bab618c45e4bc5519fc6d7ccaa870136316703b`
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
verifies and consumes only the exact four-member EV-02 producer handoff:

- child/tree: `7de0ecab74bc8439724e419743c18fee46cb885c` / `7d2ebf8f65051e8e0326350eb32301954fb62dfc`;
- producer handoff ZIP: `f44df544383b240f3d5d3b8a2ae93d4ce7665b94d0ce92f79400e56bd379e3f0`;
- handoff CHECKSUMS: `16a75f3fe8d5e079c0aa8dd796cdc6880a955a9df9d030f399632d543d7831ca`;
- acceptance receipt physical/self: `668e65fbe34ce410e699a90ba53e64724c054ab4cc81e307753549bb84d7dab7` / `dd768c8382ca521735df3110055fc58fd13727f058748ab1ba54b634d9413e0c`;
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
resealing. The known full Evaluation authority ZIP is explicitly prohibited;
aggregate-label, split-statistics, and any extra member are rejected before
their content is consumed. The official live authority remains HOLD.

Deterministic release evidence has 7 files in each build and zero A/B drift:

- manifest: `958a21f067418db803d18423746a5a719e70bba2b6d96b78209aa0129036523e`;
- checksums: `583edc611a8d2b8495fa6bd617d807c3f8ba60c325fa1a6db04369729beacb06`;
- cohort 1: `67692f66da38d96590ad77a6de7b06c4598720e77e07770c55b9f8f34ff24a2f`;
- cohort 15: `8c90cc05b2c0e20bbbfe9f74b3cb33acccf43b9e3a6c3fed16fac890471fbcb6`.

## Main-01 dependency

The Main-01 package is retained only as review input and cannot activate live
authority:

- final review ZIP: `423c063e1533e5c1e044a21d1b17b196b523d2615c0fd250d9687e4406f319da`;
- profile physical/self: `b9b56ce5d736a75c2084ff7f41e98f044f2d066b49e2f1e14ab3035087f8059a` / `f25afa9aa1a28de431bc9e3c8422543b95820d6d31198da8fb9437d86e2da995`;
- run-spec physical/self: `497ec63b9d4acdd88773b4f9dcc43b491efafe853af6b0750868694761ce4df7` / `7a409a656e86f4597997b87b2e666a35c52ae1a647d08c430fcb7faef43f1aff`.

Main's exact SI-consumable authority profile remains pending. No issuer,
authority schema, or run authorization is inferred from generic Main receipts.

## Review package integrity

`D0_SYSTEM_INTEGRATION_REVIEW_RECEIPT.json` is canonical self-hashed. Root
`CHECKSUMS.sha256` is sorted and covers every unpacked review member including
the receipt, while excluding only itself to avoid a circular hash. Missing,
extra, duplicate, unsafe, case-confusable, tampered, or resealed authority
drift fails closed.

The review package includes read-only exact copies of the Dataset ZIP,
publication receipt, required manifest sidecar, and EV-02 producer handoff.
`run_ev02_focused_review_v1.py` verifies all dependency hashes and requires
exactly 9 focused tests plus 9 subtests with zero skips.

## Gates

- focused EV-02/review-package: `9 passed`, `9 subtests`, `0 skips`;
- full System Integration: `58 passed`, `56 subtests`;
- full JUnit: `114` cases, `0` failures/errors/skips, SHA256
  `7bb754e27afb7952fe77d65a8fba618b362f26abdde78f8751370ffddeff51ec`;
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
