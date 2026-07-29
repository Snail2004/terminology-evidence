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
- `authority/`: reviewed external-authority and exact-test manifests.
- `preregistration/`: authority receipts, append-only state ledger, amendments
  and explicit projection recovery.
- `fixtures/`: synthetic local conformance data, never thesis evidence.
- `reports/`: deterministic JSON, CSV and Markdown output.
- `cli/`: offline command-line entry point.
- `release_tools/`: exact Git-object collection, JUnit authority and external
  atomic publication.
- `tools/`: release/evidence command-line builder.

## Offline commands

```text
python -B -m evaluation.v1.cli validate-registries
python -B -m evaluation.v1.cli build-synthetic C:\work\terminology-evidence-artifacts\evaluation-synthetic-v1
python -B -m evaluation.v1.cli evaluate <rows.json> <external-report-directory>
python -B -m evaluation.v1.tools.build_release --source-commit <full-40-hex-head> --output <external-new-directory>
python -B -m evaluation.v1.cli verify-release <external-release-directory>
```

The normal release command requires a completely clean worktree whose `HEAD`
equals `--source-commit`. It materializes that Git object, runs the committed
exact testcase authority, verifies the release while still in external staging,
and publishes once by atomic rename. Verification cross-checks the Git source
receipt, source ZIP, committed expected-test manifest, parsed JUnit, registry
counts, ownership/static/credential scans, commands/environment and
`RELEASE_CHECKSUMS.sha256`. It never writes `evaluation/v1/release/`.

All persisted JSON is duplicate-key and non-finite-number strict. Candidate
joins require the full `(source_term, sense_id, scope_id, candidate_vi)` key.
Bootstrap resamples complete `sense_id` groups, not individual candidates.

## Receipt modes

- `REAL_AUTHORITY`: verifies the reviewed Contract R2, detached approval,
  Global action policy, Dataset manifest/split bindings and Evaluation
  registries. A freeze accepts only the resulting `VerifiedRealReceipt`
  capability and rechecks its physical receipt bytes immediately before use.
- `SYNTHETIC_LOCAL_CONFORMANCE`: schema, determinism and metric plumbing only;
  it emits `CONFORMANCE_ONLY` and cannot freeze or open any data split.
- `LEGACY_READ_ONLY`: verifies historical receipt bytes only; it cannot build a
  new receipt or authorize state transitions.

The event ledger is the only state authority. The JSON state file is an atomic
projection and divergence fails closed until an explicit, self-hashed recovery
plan is recorded, followed by its event, final projection publication and a
completion receipt bound to that final projection. Reviewed pre-test amendments
use an append-only refreeze event; post-validation refreeze preserves access
history and invalidates the superseded calibration. Validation and hidden-test
access are one-time transitions; primary-analysis amendments remain impossible
after hidden-test access. All receipt/event times are timezone-aware RFC3339 and
ledger time cannot move backwards.

Real provider calls and production calibration are intentionally out of scope
for this implementation pass.
