# Vietnamese Attestation Evidence

Status: reserved for a separate implementation session.

The future implementation must live under:

`pipeline/eval/terminology_evidence/vietnamese_attestation/v1/`

Its CLI and tests must mirror that path under:

- `pipeline/scripts/terminology_evidence/vietnamese_attestation/v1/`
- `pipeline/tests/terminology_evidence/vietnamese_attestation/v1/`

This domain owns Evidence E only. It must not add files to Context
Substitution, import Context Substitution internals, or decide the final
glossary state. Combination with Evidence C belongs to the future Global
Terminology Validator.
