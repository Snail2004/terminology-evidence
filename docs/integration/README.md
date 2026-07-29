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
  separately reviewed Global action-policy sidecar. The Contracts root must be
  the exact `terminology_contracts_v1` subtree of the checkout containing the
  Harness; its active Git tree must equal reviewed tree
  `938bca1f9c60596ef9403a43f0355476ad42afef`, with no tracked or untracked
  worktree drift.
- `CONTRACTS_R1_HISTORICAL_REPLAY`: accepted only when an existing sealed run
  explicitly records this compatibility mode and the exact resealed R1
  receipt. It cannot start a run and is never inferred as a fallback.

The detached AR-1 evidence is consumed read-only from
`review_evidence/contracts/contracts-v1.1.0/authority-r2/`. The Harness rejects
missing, additional, renamed, swapped, tampered, case-confusable, symlink, or
reparse-point members before package consumption.

The production Contract verifier is selected only from that verified tree.
Custom commands and exact-report fakes are labeled
`NON_PRODUCTION_CONFORMANCE` and cannot establish `CONTRACTS_R2_CURRENT`.

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

## Dataset 50/150 adapter

`ArtifactInventory50_150V1` is a Harness-owned intake projection for the
official Dataset 5-sense/15-candidate pin and future 50-sense/150-candidate
development fixtures. It verifies the Dataset ZIP, pin, manifest, candidate
index, producer Git receipt, and C/E package-set bindings without importing
producer internals. Effective Sense files are materialized once and may be
referenced by exactly three candidates only when their shared identity and
physical bytes are identical.

An explicit producer HOLD is a blocking intake result, never an evidence
package. A bundle containing a HOLD can be replayed as a preflight audit but
cannot be passed to Global. Complete synthetic bundles are always labeled
`SYNTHETIC_LOCAL_CONFORMANCE`; they cannot establish official readiness.

The accepted Main Dataset pin is kept read-only at
`review_evidence/dataset/d2l-stage-a-official-5-sense-pilot-v1/`. The current
official Dataset is therefore `OFFICIAL_5_15_PREFLIGHT` until Main accepts both
producer package sets. The 50/150 release schema is not inferred from the
dirty Dataset worktree; an official 50/150 pin must be published separately.

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
python -B -m integration_harness adapter-build --dataset-zip <dataset.zip> --dataset-pin <dataset-pin.json> --dataset-git-receipt <git-receipt.json> --context-set-manifest <c-set/manifest.json> --attestation-set-manifest <e-set/manifest.json> --contracts-root terminology_contracts_v1 --adapter-mode OFFICIAL_5_15_PREFLIGHT --allow-hold-role context_evidence --allow-hold-role attestation_evidence --output <adapter-bundle>
python -B -m integration_harness adapter-replay --bundle <adapter-bundle> --contracts-root terminology_contracts_v1
python -B -m integration_harness adapter-create-hold-set --dataset-zip <dataset.zip> --dataset-pin <dataset-pin.json> --dataset-git-receipt <git-receipt.json> --contracts-root terminology_contracts_v1 --adapter-mode OFFICIAL_5_15_PREFLIGHT --role attestation_evidence --reason-code PRODUCER_PACKAGE_NOT_MAIN_ACCEPTED --issuer-commit <harness-commit> --run-id <hold-run-id> --output <hold-set>
```

`run` calls the public `global_validator.v1.cli` subprocess. Authority,
approval, and action-policy paths are explicit inputs; local convenience
configuration cannot override persisted pins.

## Current readiness

M0-M5 and the Dataset 50/150 adapter conformance layer are implemented. The
adapter gate exercises the accepted official 5/15 Dataset pin as a HOLD
preflight and a synthetic 50/150 bundle with deterministic seal/replay. The
real M6 pilot remains on hold until complete official Dataset/C/E packages are
supplied and accepted. No synthetic fixture is promoted as a producer release.
