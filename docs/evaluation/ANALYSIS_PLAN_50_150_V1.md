# Analysis Plan 50 Senses / 150 Candidates V1

## Freeze boundary

This plan is frozen before any C, E or Global output is compared with human
gold. It contains no observed label, score, estimate, threshold or result row.
The machine-readable plan is the authority; this document is its human-readable
companion.

Scope:

- 50 term senses.
- 150 Vietnamese candidates, exactly 3 candidates per sense.
- Split membership and stage counts must come from a future sealed Dataset
  split manifest and must total the exact scope above.
- Result-dependent sampling is forbidden.

## Frozen label mapping

Primary binary analysis:

- Positive: `ACCEPT`.
- Negative: `REJECT`, `SPLIT_REQUIRED`.
- Excluded: `CONDITIONAL`, `HUMAN_UNJUDGEABLE`.

Secondary sensitivity analysis:

- Usable: `ACCEPT`, `CONDITIONAL`.
- Not usable: `REJECT`, `SPLIT_REQUIRED`.
- Excluded: `HUMAN_UNJUDGEABLE`.

The secondary mapping cannot replace the primary result.

## Frozen metric families

### Dataset and human review

- Gold-label distribution.
- Raw reviewer agreement and Cohen's kappa.
- Agreement by clear, ambiguous and risk strata.
- Adjudication rate.
- `HUMAN_UNJUDGEABLE` rate.

### Context Substitution (C)

- Trial validity and evidence coverage.
- Support, mixed and contradiction distribution.
- Critical-gate frequency.
- Within-sense top-1 accuracy.
- C-versus-gold cross-tabulation.
- Escalation rate.
- Requests, input/output/total tokens and sealed cost when available.

### Vietnamese Attestation (E)

- Controlled-corpus coverage and Brave fallback rate.
- Eligible and independent source counts.
- Sense-match and domain-match rates.
- Attestation status distribution, including strong, limited, no-evidence,
  unjudgeable and conflicting outcomes.

The reporting buckets map one-to-one to the exact E Contract V1.1 values:
`ATTESTED_STRONG <- ATTESTED`, `ATTESTED_LIMITED <- WEAKLY_ATTESTED`,
`NO_EVIDENCE <- NOT_ATTESTED`,
`UNJUDGEABLE <- ATTESTATION_UNJUDGEABLE`, and
`CONFLICTING <- CONFLICTING_ATTESTATION`. This reporting projection never
rewrites or reclassifies the producer-owned E value.

### Global and pipeline

- Five registered primary metrics: AUTO_APPROVED precision and coverage, false
  approval count, human-review rate and hard-rejection accuracy.
- Development status and gate-routing distributions.
- Exact identity-join and replay success.
- Safety invariants: zero `AUTO_APPROVED` and zero production certificates
  before a reviewed production calibration exists.

Exact definitions and denominators are in
`analysis_plan_50_150_v1.json`.

## Missing-data policy

- No imputation.
- No silent complete-case deletion.
- Producer failure is not a negative gold label.
- Missing cost is `NA`, never zero.
- Every table reports planned, available, eligible, excluded and missing counts.
- Exclusions require a frozen reason code and artifact/reviewer evidence.
- Primary exclusions follow the label mapping above; the secondary sensitivity
  analysis is reported separately.

## Confidence intervals and tests

- Proportions: 95% Wilson intervals.
- Grouped metrics: percentile bootstrap clustered by `sense_id`, 2,000
  replicates, fixed seed `20260730`.
- Paired binary comparisons: exact two-sided McNemar.
- Continuous paired comparisons: paired sense bootstrap.
- Formal secondary tests: Holm correction.
- Effect sizes are mandatory; p-values alone are prohibited.
- D0 is descriptive only and cannot support a confirmatory claim.

## Access order

```text
D0 development canary
-> seal C/E/Global outputs
-> authorized development-canary gold access
-> close and seal D0 report

D1 development
-> only preregistered amendment + refreeze may change primary analysis
-> close and seal D1 analysis

V1 validation
-> requires D1 closure and policy freeze
-> close and seal validation report

T1 held-out test
-> requires validation closure and calibration freeze
-> one ordered held-out access
```

Gold access must use a self-hashed event bound to the analysis-plan freeze,
Dataset split manifest, sealed producer bundle, sealed gold bundle, authorized
scope and human approval receipt. Events form the exact `D0 -> D1 -> V1 -> T1`
hash chain. This frozen package contains zero actual access events.

## Planned output tables

Twelve empty table shells are frozen in `planned_tables_v1.json`:

1. Cohort and artifact availability.
2. Gold-label distribution.
3. Human-review agreement.
4. C evidence and gates.
5. C versus gold cross-tabulation.
6. E coverage and status.
7. Global statuses, gates and routing.
8. Primary gold-aligned performance.
9. Calibration and threshold stability.
10. Paired comparisons and decision flips.
11. Requests, tokens and cost.
12. Missingness and exclusion audit.

No result cell is populated at freeze time.

## Amendments and nonclaims

- Before D0, changes require an append-only amendment and a new freeze.
- After D0, primary changes require a new version, explicit disclosure and
  refreeze; silent result-driven changes are forbidden.
- After T1, primary-analysis changes are forbidden.
- This plan does not create gold, open a split, choose a threshold or claim
  system quality.
