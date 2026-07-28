# Consumer Guide: TAC

TAC consumes `TACOccurrenceInputV1` with an embedded complete V1.1 certificate.

- Accept only certificate status `AUTO_APPROVED` or `PROVISIONAL`.
- Verify candidate/sense, evidence, gates, decision, policy, and calibration
  bindings by calling `verify_certificate_bundle(...)` before occurrence checks.
- Accept only the exact positive support set as certificate validity contexts.
- Reject any certificate whose variants, blacklist, scope, C/E summary,
  threshold identifier, policy, or issuance time differs from the verified
  source artifacts.
- Structural certificate validation alone is not an authority check.
- Interpret `source_term_span` as `UNICODE_CODEPOINT` offsets and require its
  selected text to normalize exactly to the certificate source term.
- Never reconstruct C/E evidence or make a new global glossary decision.
- Reject `LEGACY_INCOMPLETE` certificates outside explicit migration inspection.
