# YÊU CẦU EVALUATION — PRE-D0 ANALYSIS-PLAN ADDENDUM SAU GOLD DISTRIBUTION

**Base frozen content:** `25155f65149936c18d9c8f15b0763cc75335a176`  
**Base publication:** `f7289661aed3db124b55ef67ba3bd1f7f7dc92ea`  
**Mode:** zero-network, no candidate-level gold open, no C/E/Global output open.

## 1. Preserve frozen primary decisions

Do not change:

```text
Positive: ACCEPT
Negative: REJECT + SPLIT_REQUIRED
Excluded primary: CONDITIONAL + HUMAN_UNJUDGEABLE
Secondary mapping
statistical tests
split assignments
gold labels
```

## 2. Add aggregate-distribution limitation

Bind only the already published aggregate counts:

```text
development: 68 ACCEPT / 20 CONDITIONAL / 2 REJECT
validation: 26 ACCEPT / 4 CONDITIONAL / 0 REJECT
test: 23 ACCEPT / 7 CONDITIONAL / 0 REJECT
```

State that natural validation/test strict-negative metrics are
`NOT_ESTIMABLE`.

## 3. Bind adversarial companion protocol

Add an authority reference for a separate reviewed set covering:

```text
wrong sense
concept mismatch
split required
target collision
popular incorrect calque
candidate-induced contradiction
insufficient evidence
```

Natural and adversarial results must be reported separately.

## 4. Development-mode table policy

For D0/D1:

```text
AUTO_APPROVED precision = NOT_ESTIMABLE
AUTO_APPROVED coverage = NOT_ESTIMABLE
hard-rejection accuracy = NOT_ESTIMABLE where no eligible negatives exist
certificate metrics = NOT_APPLICABLE
```

Do not coerce undefined values to zero.

## 5. Access boundary

The amendment may use aggregate Dataset summary only. It must not open:

```text
candidate-level gold
validation candidate labels
test candidate labels
C/E/Global outputs
```

No D0 gold-access receipt may be issued until the new amendment and refreeze
are independently reviewed.

## 6. Handoff

Return:

```text
append-only amendment
new frozen plan version or amendment-chain receipt
exact content/publication commits
self/physical hashes
updated table shells
focused/full JUnit
external JUnit file
Git-object review bundle or accessible bundle
manifest/CHECKSUMS
gold access count = 0
provider/network calls = 0
```

Status:

```text
ANALYSIS_PLAN_ADDENDUM_FROZEN_BEFORE_D0_GOLD
NEEDS_REWORK
```
