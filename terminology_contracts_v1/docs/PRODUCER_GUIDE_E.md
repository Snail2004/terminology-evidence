# Producer Guide: Vietnamese Attestation (E)

E consumes the same frozen candidate as C and emits
`AttestationEvidencePackageV1@1.1.0`.

- Verify the Frozen Candidate content binding, then preserve candidate and input
  bindings unchanged.
- Emit the six independent E features; do not add a scalar `E_score`.
- `ATTESTED` requires accepted attestation evidence.
- `ATTESTATION_UNJUDGEABLE` supplies evidence for the matching hard gate.
- Bind full run/replay provenance and raw provider response ledger references.
- Keep `final_glossary_decision` null and do not read C output.
