# Consumer Guide: TAC

TAC consumes `TACOccurrenceInputV1` with an embedded complete V1.1 certificate.

- Accept only certificate status `AUTO_APPROVED` or `PROVISIONAL`.
- Verify candidate/sense, evidence, gates, decision, policy, and calibration
  bindings by calling `verify_certificate_bundle(...)` before occurrence checks.
- Interpret `source_term_span` as `UNICODE_CODEPOINT` offsets and require its
  selected text to normalize exactly to the certificate source term.
- Never reconstruct C/E evidence or make a new global glossary decision.
- Reject `LEGACY_INCOMPLETE` certificates outside explicit migration inspection.
