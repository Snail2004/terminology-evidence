# Evaluation and Preregistration V1

This domain freezes evaluation questions, metrics, split discipline, calibration
rules and reporting before validation or test data are opened. It is an
evaluation consumer: it does not create gold labels, make Global decisions,
modify C/E artifacts or issue a production calibration artifact.

## Layout

- `registries/`: machine-readable preregistration registries.
- `artifacts/`: strict loaders, authority checks, exact joins and eligibility.
- `metrics/`: Wilson, sense-grouped bootstrap, McNemar and primary metrics.
- `calibration/`: deterministic logistic regression and operating-point helper.
- `preregistration/`: receipt, freeze state, access log and amendments.
- `fixtures/`: synthetic local conformance data, never thesis evidence.
- `reports/`: deterministic JSON, CSV and Markdown output.
- `cli/`: offline command-line entry point.
- `tools/`: release/evidence builder.

## Offline commands

```text
python -m evaluation.v1.cli validate-registries
python -m evaluation.v1.cli build-synthetic evaluation/v1/release/synthetic
python -m evaluation.v1.cli evaluate evaluation/v1/release/synthetic/rows.json evaluation/v1/release/synthetic/report
```

All persisted JSON is duplicate-key and non-finite-number strict. Candidate
joins require the full `(source_term, sense_id, scope_id, candidate_vi)` key.
Bootstrap resamples complete `sense_id` groups, not individual candidates.

## Readiness states

- `SYNTHETIC_LOCAL_CONFORMANCE`: schema, determinism and metric plumbing only.
- `DEVELOPMENT`: development artifacts with explicit authority and split data.
- `READY_FOR_VALIDATION`: maintainer-approved preregistration plus complete
  Stage B and provider packages.
- `READY_FOR_HIDDEN_TEST`: reviewed calibration, frozen threshold and empty
  test-access log.

Real provider calls and production calibration are intentionally out of scope
for this implementation pass.
