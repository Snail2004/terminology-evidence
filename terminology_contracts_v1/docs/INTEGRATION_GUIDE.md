# Integration Guide

## Stable join key

Every package carries exactly the same `candidate_key`:

```text
candidate_id
candidate_version
source_term
candidate_vi
sense_id
scope_id
sense_inventory_version
dataset_manifest_sha256
effective_sense_contract_sha256
```

Global Validator additionally requires identical `input_contract_sha256` from the
frozen candidate contract.

## Join failure

Any mismatch returns `input_contract_mismatch` with action `ESCALATE_HUMAN` or
fails the run before scientific scoring. Never silently coerce or match by text.

## 0–1 feature scale

C/E normalized evidence features use `[0,1]`. Counts remain integer diagnostics.
No schema assigns fixed weights. The only approved source of weights/thresholds is a
sealed `CalibrationArtifactV1`.

## Local versus global authority

- C local status: contextual evidence only.
- E local status: Vietnamese attestation only.
- Gate result: non-compensable safety constraints.
- Global decision: only component allowed to emit final decision.

## Compatibility strategy

An implementation may have internal Pydantic/dataclass models, but its boundary JSON
must validate against this package. CI should validate valid fixtures and reject all
invalid fixtures.
