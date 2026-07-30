# AGENT C — ONE-SESSION NARROW REWORK

## Base

Use the exact accepted C base supplied by Main. Do not change Dataset/cohort,
rubric, aggregation or provider plan.

## Scope

1. Bind one frozen `context_id -> context_type` map to every candidate run.
2. Add critical disagreement arbitration.
3. Re-run the underflow three-candidate regression inputs.
4. Produce a review-ready narrow child.

## Required logic

```text
primary semantic <= 2 and secondary semantic >= 3
OR
secondary semantic <= 2 and primary semantic >= 3

=> CRITICAL_JUDGE_DISAGREEMENT
=> suppress single-judge fatal semantic gate
=> recommendation = HUMAN_REVIEW_REQUIRED
```

Unanimous critical errors and deterministic contradiction/wrong-sense rules
must remain fatal.

## Required tests

```text
- context role invariant across candidates;
- override rejection;
- primary/secondary disagreement both directions;
- unanimous fatal preserved;
- deterministic fatal preserved;
- final_glossary_decision null;
- gold access zero;
- clean full suite.
```

## Return

```text
C_CONTEXT_ROLE_AND_CRITICAL_ARBITRATION_REWORK_READY_FOR_REVIEW
PROVIDER_CALLS_AS_AUTHORIZED_ONLY
GOLD_ACCESS_0
```
