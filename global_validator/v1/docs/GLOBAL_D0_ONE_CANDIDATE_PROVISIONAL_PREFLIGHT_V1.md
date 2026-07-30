# Global D0 One-Candidate Provisional Preflight V1

## Status

```text
GLOBAL_COMPATIBILITY_PREPARATION_ALLOWED
GLOBAL_D0_ONE_CANDIDATE_ZERO_PROVIDER_PREFLIGHT_READY_FOR_MAIN_ACCEPTANCE
GLOBAL_D0_DEVELOPMENT_PREFLIGHT_PASS = NO
RUN_AUTHORIZED = NO
```

This preparation covers only:

```text
candidate_479fdd8ff6d15304debec117
```

It does not assemble a live Global input, run the decision engine, load gold,
read a corpus, call a provider, or open a network connection.

## Preparation surface pins

| Surface | Pin | Scope |
| --- | --- | --- |
| C-01 | `a9965c93782834fd8d913df370f437a26059d267` | Accepted Context Evidence output surface; Global remains final decision owner |
| SI | `2d4aac1341561057e45e61f691cb2062413ede9c` | Accepted EV-02 owner binding and exact one-candidate canary |
| E-05 base | `894bd1cc9f11e00322aeb9e7fc0120f440ca2a37` | Accepted lifecycle/ledger parent surface |
| E final token-only child | `0888bfd180fcd00b43848977a0576160ad471400` / tree `345d1f837767f26d9154d4d287c3507c66aaa842` | Accepted only for zero-provider canary preparation; no live authority |
| Draft4 token accounting | `0acb5a82106dbcefa13fcb998590f7ce04af852f` / tree `f315548679756e671a227436d705487ce53f4408` | Token-only preparation authority; no live authority |

The SI candidate-set pin is
`e72286e06201297864d3163311336515092d841181e484c01276faa9b989fa0b`.

## Token-only compatibility

The provisional fixture accepts only:

```text
input_tokens: nonnegative integer
output_tokens: nonnegative integer
reasoning_tokens: nonnegative integer
total_tokens: exact sum of the three fields above
network_request_count: durable nonnegative integer, exactly 0 in preparation
cost: null
currency: null
status: TOKEN_ONLY_COST_UNAVAILABLE
```

The Draft4 preparation authority is pinned by self SHA-256
`467eaad13fe23b08be15ee86bc1777e66faae9eb06c407f596e3c9b273155e80`.
It authorizes token-accounting consumption only, with no price-table
interpretation. The final E narrow child is pinned to its exact parent, tree,
review-package SHA-256
`b8c5a02323ff04c2f0a8bdf22b60495c9cd22deeb23428f8dcbbb309c0b64836`,
complete-bundle SHA-256
`3ad42c58ec8f57b77425d111a63197d53200d49b0c2566b6e24d61a25f85df19`,
and two direct Git blob OIDs. Caller-supplied authority drift is rejected.

## Locked invariants

```text
approval_score = null
AUTO_APPROVED = 0
certificates = 0
provider = 0
network = 0
gold = 0
corpus = 0
```

Only the narrow E token-only preparation claim is true. Live E authority,
Global preflight acceptance, and run authorization remain false. The validator
cannot emit a Global decision or certificate.

## Exact blockers

1. Main has not independently accepted this Global preflight child/package.
2. `E_LIVE_RUNTIME_AUTHORITY_ACTIVE` remains false.
3. `RUN_AUTHORIZED` remains false.

Main may now review this exact zero-provider development preflight. Acceptance
must still not authorize provider, network, gold, corpus, AUTO_APPROVED, or
certificates.
