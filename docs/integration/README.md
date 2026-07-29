# System Integration Harness V1

This package is an orchestration and replay boundary. It is not a new
terminology validator and it does not make a linguistic or glossary decision.
Dataset owns Frozen Candidate and Constraint packages; Context Substitution C
and Vietnamese Attestation E remain decision-neutral evidence producers; Global
Validator owns the final action/decision.

## V1 modes

- `FIXTURE_CONFORMANCE`: synthetic contract fixtures, zero network/provider
  calls, zero `AUTO_APPROVED`, zero certificates.
- `REAL_DEVELOPMENT_ZERO_NETWORK`: explicit producer packages, no provider
  calls, Global development mode only.
- `REAL_DEVELOPMENT_REPLAY`: checksum-first replay of a sealed run. The public
  Global CLI may be invoked again only when an explicit contracts root is
  supplied; private producer modules are never imported.

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

The harness discovers artifacts through an explicit `ArtifactInventoryV1`
manifest. It never scans the repository looking for a likely file. Every
package is strict-loaded, schema-checked, self-hash checked, and joined by the
complete candidate identity tuple. Any missing, duplicate, foreign, or drifted
package fails closed.

## Public CLI

```powershell
$env:PYTHONPATH = "$PWD;$PWD\terminology_contracts_v1\python"
python -m integration_harness --help
python -m integration_harness inventory --manifest <manifest.json>
python -m integration_harness validate-packages --manifest <manifest.json> --contracts-root terminology_contracts_v1
python -m integration_harness join --manifest <manifest.json> --contracts-root terminology_contracts_v1
python -m integration_harness run --manifest <manifest.json> --contracts-root terminology_contracts_v1 --authority-receipt <receipt.json> --mode FIXTURE_CONFORMANCE --run-id integration-dev-001 --output runs/integration-dev-001
python -m integration_harness replay --run-dir runs/integration-dev-001
```

`run` calls the public `global_validator.v1.cli` subprocess. The authority
receipt and action-policy paths are explicit inputs; local convenience config
cannot override pinned authority.

## Current readiness

M0-M5 are implemented and exercised with a 15-candidate zero-network public
CLI conformance fixture. The real M6 pilot remains deliberately blocked until
all official Dataset/C/E packages, reviewed Global release authority, and
required authority pins are available. No synthetic fixture is promoted as a
real producer release.
