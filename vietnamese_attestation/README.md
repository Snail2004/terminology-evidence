# Vietnamese Attestation Evidence

Status: REVIEW.

The implementation lives under:

`vietnamese_attestation/v1/`

Its CLI and tests remain inside the owned domain at `v1/cli/` and `v1/tests/`.

This domain owns Evidence E only. It must not add files to Context
Substitution, import Context Substitution internals, or decide the final
glossary state. Combination with Evidence C belongs to the future Global
Terminology Validator.
