# Terminology Contracts V1.1 Release Notes

V1.1 is a boundary hardening release. It does not change C/E algorithms, choose
weights, set thresholds, create human labels, or make glossary decisions.

## Consumer impact

- New producers emit `schema_version: 1.1.0` and the expanded provenance fields.
- Global Validator assemblers add `assembly_metadata` and verify nested hashes.
- Frozen decisions must load the sealed calibration artifact and feature registry.
- Decision packages carry complete run/replay metadata.
- Certificates bind candidate, input, C, E, gates, decision, policy, sense, and
  optional calibration artifacts.
- TAC rejects incomplete V1.1 certificates.

## Compatibility

V1.0 schemas remain byte-preserved in `schemas/legacy/v1.0.0`. The deterministic
migration keeps evidence and candidate identity, but marks unavailable V1.0
bindings as legacy-incomplete rather than fabricating them.

## Scientific boundary

C and E remain evidence producers. The Global Validator remains the only final
decision authority. Dataset V3 and pilot data are used only for mapping tests.
