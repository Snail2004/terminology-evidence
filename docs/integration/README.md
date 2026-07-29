# System Integration Harness V1

This package is an orchestration, sealing, and replay boundary. It is not a
terminology validator and does not make linguistic or glossary decisions.
Dataset owns Frozen Candidate and Constraint packages; Context Substitution C
and Vietnamese Attestation E remain decision-neutral evidence producers;
Global Validator owns the final action and decision.

## Authority modes

- `SYNTHETIC_LOCAL_CONFORMANCE`: test-only synthetic authority. It is accepted
  only with `FIXTURE_CONFORMANCE` and cannot establish release readiness.
- `CONTRACTS_R2_CURRENT`: the only authority admitted for a new real
  development run. It requires the exact public Contract R2 verifier result,
  exact R2 distribution pins, the detached accepted AR-1 directory, and the
  separately reviewed Global action-policy sidecar.
- `CONTRACTS_R1_HISTORICAL_REPLAY`: accepted only when an existing sealed run
  explicitly records this compatibility mode and the exact resealed R1
  receipt. It cannot start a run and is never inferred as a fallback.

The detached AR-1 evidence is consumed read-only from
`review_evidence/contracts/contracts-v1.1.0/authority-r2/`. The Harness rejects
missing, additional, renamed, swapped, tampered, case-confusable, symlink, or
reparse-point members before package consumption.

## V1 execution modes

- `FIXTURE_CONFORMANCE`: synthetic contract fixtures, zero network/provider
  calls, zero `AUTO_APPROVED`, and zero certificates.
- `REAL_DEVELOPMENT_ZERO_NETWORK`: explicit complete producer packages under
  current R2 plus accepted AR-1, with Global development mode only.
- `REAL_DEVELOPMENT_REPLAY`: checksum-first replay of a sealed run. Current R2
  is reverified from the sealed receipt, approval evidence, verifier report,
  and action-policy sidecar. Historical R1 requires its explicit sealed mode.

V1 does not implement live Search/Judge orchestration, calibration fitting,
production certificates, human annotation, or downstream translation.

## Boundary

Implementation is confined to:

```text
integration_harness/**
tests/system_integration/**
scripts/integration/**
docs/integration/**
```

The Harness discovers artifacts through an explicit `ArtifactInventoryV1`
manifest. It never scans the repository for likely inputs. Every package is
strict-loaded, schema-checked, self-hash checked, and joined by the complete
candidate identity tuple. Missing, duplicate, foreign, or drifted packages
fail closed.

## Public CLI

```powershell
$env:PYTHONPATH = "$PWD;$PWD\terminology_contracts_v1\python"
python -B -m integration_harness --help
python -B -m integration_harness inventory --manifest <manifest.json>
python -B -m integration_harness validate-packages --manifest <manifest.json> --contracts-root terminology_contracts_v1
python -B -m integration_harness join --manifest <manifest.json> --contracts-root terminology_contracts_v1
python -B -m integration_harness authority-verify --contracts-root terminology_contracts_v1 --authority-receipt terminology_contracts_v1/release/v1.1.0-final/contracts_v1_1_0_authority_receipt_r2.json --approval-root review_evidence/contracts/contracts-v1.1.0/authority-r2 --authority-mode CONTRACTS_R2_CURRENT
python -B -m integration_harness run --manifest <manifest.json> --contracts-root terminology_contracts_v1 --authority-receipt terminology_contracts_v1/release/v1.1.0-final/contracts_v1_1_0_authority_receipt_r2.json --approval-root review_evidence/contracts/contracts-v1.1.0/authority-r2 --authority-mode CONTRACTS_R2_CURRENT --mode REAL_DEVELOPMENT_ZERO_NETWORK --run-id integration-dev-001 --output runs/integration-dev-001
python -B -m integration_harness replay --run-dir runs/integration-dev-001 --repository-root . --contracts-root terminology_contracts_v1
```

`run` calls the public `global_validator.v1.cli` subprocess. Authority,
approval, and action-policy paths are explicit inputs; local convenience
configuration cannot override persisted pins.

## Current readiness

M0-M5 are implemented. The test suite exercises a 15-candidate synthetic
zero-network fixture, exact current-R2 authority admission, detached AR-1
validation, current-R2 sealed replay, and explicit historical-R1 replay. The
real M6 pilot remains on hold until complete official Dataset/C/E packages are
supplied. No synthetic fixture is promoted as a producer release.
