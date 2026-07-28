# Consumer Guide: TAC

TAC consumes `TACOccurrenceInputV1` with an embedded complete V1.1 certificate.

- Accept only certificate status `AUTO_APPROVED` or `PROVISIONAL`.
- Verify candidate/sense, evidence, gates, decision, policy, and calibration
  bindings before occurrence-level checks.
- Never reconstruct C/E evidence or make a new global glossary decision.
- Reject `LEGACY_INCOMPLETE` certificates outside explicit migration inspection.
