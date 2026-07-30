# Pre-D0 Analysis-Plan Addendum V1

## Boundary

This append-only addendum supplements, but does not replace or mutate, the
frozen 50-sense/150-candidate analysis plan published by commits
`25155f65149936c18d9c8f15b0763cc75335a176` and
`f7289661aed3db124b55ef67ba3bd1f7f7dc92ea`.

The addendum uses only the aggregate Dataset distribution authorized by the
independent review. Candidate-level gold, reviewer decisions, C/E/Global
outputs, validation data and held-out test data remain unopened.

## Decisions preserved

The frozen label mappings remain unchanged:

- Primary positive: `ACCEPT`.
- Primary negative: `REJECT`, `SPLIT_REQUIRED`.
- Primary excluded: `CONDITIONAL`, `HUMAN_UNJUDGEABLE`.
- Secondary usable: `ACCEPT`, `CONDITIONAL`.
- Secondary not usable: `REJECT`, `SPLIT_REQUIRED`.
- Secondary excluded: `HUMAN_UNJUDGEABLE`.

No split assignment or gold label is changed.

## Authorized aggregate distribution

| Natural split | ACCEPT | CONDITIONAL | REJECT |
| --- | ---: | ---: | ---: |
| Development | 68 | 20 | 2 |
| Validation | 26 | 4 | 0 |
| Test | 23 | 7 | 0 |

The natural validation and test splits contain no strict-negative candidate.
Natural-set specificity, negative recall, critical-error recall,
false-auto-approval rate against strict negatives, hard-rejection accuracy and
negative-challenge production-threshold claims are therefore
`NOT_ESTIMABLE` for those splits.

## D0 development policy

D0 is a development experiment. In development mode:

- `AUTO_APPROVED` precision is `NOT_ESTIMABLE_IN_DEVELOPMENT_MODE`.
- `AUTO_APPROVED` coverage is `NOT_ESTIMABLE_IN_DEVELOPMENT_MODE`.
- Hard-rejection accuracy is `NOT_ESTIMABLE` where no eligible negatives
  exist.
- Certificate metrics are `NOT_APPLICABLE`.
- Undefined metrics must never be coerced to zero.

D0 reports status distributions, gate routing, C/E coverage, gold-aligned
evidence concordance after authorized gold access, within-sense ranking,
identity/replay, requests, retries, malformed responses, latency, tokens,
cost, missingness, manual-review rate and error analysis.

## Adversarial companion protocol

Strict-negative claims use a separately reviewed adversarial/negative
companion set covering:

- wrong sense;
- concept mismatch;
- split required;
- target collision;
- popular incorrect calque;
- candidate-induced contradiction;
- insufficient evidence.

Natural and adversarial prevalence and metrics are always reported separately.
This addendum freezes the companion protocol only; it does not fabricate,
select or authorize any adversarial case.

## Access order

Producer outputs for all 15 blind D0 candidates must be complete and sealed
before any D0 gold-access receipt can be issued. The one-candidate canary is a
member of the same frozen cohort and uses the same configuration as the
remaining 14 candidates.

At this refreeze boundary:

```text
producer outputs opened: NO
D0 gold opened: NO
validation opened: NO
held-out test opened: NO
provider/network calls: 0
```
