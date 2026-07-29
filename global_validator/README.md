# Global Terminology Validator V1.1

Deterministic, zero-provider-call consumer of sealed terminology evidence.

The validator consumes only `GlobalValidatorInputV1` and shared authority
artifacts from `terminology_contracts_v1`. It does not read raw datasets or
import Context Substitution / Vietnamese Attestation internals.

The normative design is:

- `v1/docs/Kien_truc_Thuat_toan_Global_Terminology_Validator_V1_1.md`
- `terminology_contracts_v1` at `contracts-v1.1.0`

The older Hard Gates V1 document is retained for history. Contracts V1.1 and
the V1.1 algorithm document win every conflict.

## Development

```powershell
$env:PYTHONPATH = "$PWD;$PWD\terminology_contracts_v1\python"
python -m pytest -q global_validator/v1/tests
python -m global_validator.v1.cli --help
```

## Release boundary

`DEVELOPMENT_HEURISTIC` always returns a non-authoritative decision and cannot
emit a certificate. `FROZEN_CALIBRATED` requires a verified calibration and an
immutable output bundle. The calibration shipped under contract examples is
test-only, remains non-production even when copied, and requires the explicit
`--allow-example-calibration` switch. A real frozen run must provide the
reviewed artifact's exact `--expected-calibration-sha256`.

Review evidence and open blockers are in `v1/release/` and
`v1/docs/IMPLEMENTATION_FINDINGS_V1_1.md`.
