# AGENT E — ONE-SESSION BGE-M3 RETRIEVAL REWORK

## Base

Use the exact accepted E authority/lifecycle base supplied by Main. Preserve
Main-profile, SI-owner, EV-02, Draft4 ledger/lifecycle, retry and unknown-outcome
logic.

## Scope

1. Add exact Main-pinned BGE-M3 Q8_0 local embedding authority.
2. Add candidate-specific query plans.
3. Add dense lead ranking.
4. Preserve exact candidate/variant span gate.
5. Rank occurrence windows with intended/excluded sense embeddings.
6. Add detailed unjudgeable reason codes.
7. Separate local-loopback, provider and external-network telemetry.

## Hard constraints

```text
embedding never creates attestation;
documents without candidate surface never count as evidence;
positive-evidence predicate remains unchanged;
no implicit variant generation;
no fixed cosine correctness threshold in D0;
gold remains closed.
```

## D0 defaults

```text
max URLs/candidate = 20
min successful extracted docs before no-evidence = 6
max windows/document = 3
max Judge snippets/candidate = 12
early stop = 2 SAME clusters + 2 organizations
```

## Tests

```text
- exact model-file hash required;
- wrong model authority rejected;
- local loopback counted separately;
- recorded fixtures report network=0;
- embedding only changes ranking;
- exact-span gate cannot be bypassed;
- intended/excluded margin recorded;
- top-k deterministic;
- reason-code coverage;
- accepted-evidence predicate unchanged;
- full suite clean.
```

## Return

```text
E_BGE_M3_CANDIDATE_SPECIFIC_RETRIEVAL_REWORK_READY_FOR_REVIEW
REAL_PROVIDER_CALLS_0_UNLESS_SEPARATELY_AUTHORIZED
GOLD_ACCESS_0
```
