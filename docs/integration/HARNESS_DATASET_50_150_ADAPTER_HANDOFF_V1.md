# System Integration Harness Batch Availability Authority V1

## Verdict

`BATCH_AVAILABILITY_AUTHORITY_READY_FOR_REVIEW`

The Harness now represents acquisition availability outside producer evidence
packages and outside `GlobalValidatorInputV1`. It does not create C/E HOLD
packages. Only candidates with valid, complete, `PRESENT` C and E packages are
materialized for the public Global boundary.

Implementation commit:

```text
3caefd26634f1a73e319e55913b7eec98b2ba276
parent 1197ff4933193d97104b872d52ab3f80db441d21
```

The authorization base was canonical main
`7fd046cc6a9b8f78fd122549feaefa4b2ab83821`. Main advanced independently to
`b79aab4359de0396c2c2481f50d949455673fb85` while this child was being built.
The child does not claim the later main as an ancestor; Maintainer owns the
mechanical integration and post-merge re-gate.

## Published Sidecars

- `HarnessCohortInventoryV1`: exact Dataset candidate identities and byte hashes.
- `GlobalBatchAuthorityV1`: exact Dataset/cohort/run/phase/split and C/E schema expectations.
- `EvidenceAvailabilityManifestV1`: one row per candidate and producer role.
- `GlobalBatchReadinessReportV1`: exact ready/not-submitted sets and rejection reasons.

Availability values are exactly:

```text
PRESENT | EXTERNAL_HOLD | MISSING | INVALID
```

`NOT_ATTESTED` and `ATTESTATION_UNJUDGEABLE` remain valid E package values and
are both classified as `PRESENT`. `EXTERNAL_HOLD`, `MISSING`, and `INVALID`
never become producer packages and never enter the Global join.

## Zero-provider Evidence

External artifact:

```text
system-integration-harness-batch-availability-v1-3caefd2-a
```

Deterministic repeat:

```text
system-integration-harness-batch-availability-v1-3caefd2-b
```

Both trees contain 692 files and compare with zero byte drift.

Key hashes:

```text
release manifest physical  efcb34d0bf076262caf3eec727b16384c23d58930994942f9285c4eda77a56d4
release manifest self      4c32ee289c619572c6464cc306a3a4f47ad93460418f00c1964a23542cffbe19
root CHECKSUMS             46664ecb70f1bafa6f1db89ac1a485136397020c81197e8fcf40877a506d3088
summary physical           e16948c252b7d5fbe4f44b9a0088ffc6b15e568d86fb741b443179418f210240
summary self               dc5e1f463b98c73dd4190216ffb862e3802308387c3f20fac9bf9ea34a920561
official ZIP               a59c29912050887044f0b9144d0595b46f67c05631e4fc11e21d0437b4ddf409
synthetic ZIP              1ded6babe92e3e7d184c4717eb71be90772bbcacd049f22a5114c478a2680155
```

Root `CHECKSUMS.sha256` validates 691 entries. The release manifest validates
690 non-root files. Both ZIPs use sorted POSIX member paths, contain no
duplicate/absolute/traversal member, and replay after extraction.

Official 5-sense/15-candidate preflight:

```text
expected            15
READY_FOR_GLOBAL      0
NOT_SUBMITTED        15
MISSING rows         30
joined                0
replay                SEALED_ADAPTER_AVAILABILITY_HOLD_REPLAY_PASS
```

Synthetic 50-sense/150-candidate conformance:

```text
expected            150
READY_FOR_GLOBAL    150
NOT_SUBMITTED         0
PRESENT rows        300
joined              150
replay                SEALED_ADAPTER_COMPLETE_REPLAY_PASS
```

The synthetic set is conformance evidence only and is not official producer
evidence.

## Gates

```text
focused authority/cohort      8 passed + 14 subtests
legacy adapter regression    10 passed
full Harness                 44 passed + 47 subtests
Contracts V1.1              113 passed, 2 skipped
Global Validator             80 passed
Context Substitution C       79 passed
Vietnamese Attestation E     75 passed
provider calls                0
network calls                 0
gold access                   0
AUTO_APPROVED                 0
certificates                  0
final_glossary_decision     null
```

Adversarial coverage includes missing/extra/duplicate identity, package and
sidecar hash drift, coherent sidecar reseal drift, forbidden non-package
producer entries, EXTERNAL_HOLD without an authoritative STOP_EVENT, valid
EXTERNAL_HOLD and INVALID exclusion, partial-ready exclusion, inventory
reorder, and reparse/junction rejection.

JUnit:

```text
docs/integration/system-integration-batch-authority-hardening-v1.junit.xml
docs/integration/system-integration-harness-v1-hardened.junit.xml
docs/integration/compat-contracts-v1.1.junit.xml
docs/integration/compat-global-validator-v1.1.junit.xml
docs/integration/compat-context-substitution-v2.2.junit.xml
docs/integration/compat-vietnamese-attestation-v1.1.junit.xml
```

## Remaining Hold

The official cohort correctly remains unavailable for Global because no
Maintainer-accepted complete official C/E package sets were supplied to this
run. M6, live authorization, provider/network execution, gold access,
AUTO_APPROVED, and certificate issuance remain out of scope.
