# Global Validator V1.1 Review Disposition

This document preserves the independent review as historical evidence and
records the disposition against the current Global-owned implementation. It
does not rewrite the original report or audit JSON.

## Reviewed evidence

- Review target: `056b520ede25c40aa3c72ca9785dccecab4691d3`
- Receipt/replay hardening parent: `4cd7930b56fff334b9e790550cbb8e17c373613f`
- Review report SHA-256:
  `3ef049a4928bc97811d5b2dcc9b02f0743530398f8685aff0082b44e00d2fb64`
- Review audit SHA-256:
  `dee38537fdd8055f81862292c0044d7463a4446869b93da1bbf68d2ab53f0886`
- Approved action-policy SHA-256:
  `4220b15b7b5d5b740946b9b258a5e1f25469a8f8409ca6e1a0b399464285c9f5`
- Action-policy authority self SHA-256:
  `1fca452c0604b7f41e9ffab72de0c134b108c52cafed279153bd7e98a0e8994a`

## Finding disposition

| Finding | Disposition | Closure |
|---|---|---|
| P0-GV-1 | CLOSED_FIXED | Runtime accepts only the reviewed action-policy SHA pinned by the immutable Global authority sidecar. |
| P0-GV-2 | CLOSED_FIXED | Decision verification validates the exact run config and compares the complete decision with deterministic recomputation. Certificate-bundle verification includes exact replay. |
| P1-GV-1 | CLOSED_FIXED | Generation, standalone verification, and replay validate timestamp ordering and exact timestamp bindings. |
| P1-GV-2 | CLOSED_FIXED | Fatal semantic, disagreement, and coverage signals require direct evidence references; package fallback remains only for nonfatal aggregate states and constraints. |
| P1-GV-3 | CLOSED_FIXED | Replay spec V1.1 treats the original repository path as a hint and accepts an explicit independently verified authority root. |
| P1-GV-4 | CLOSED_FIXED | Persisted replay verifies canonical checksums, strict JSON, file inventory, and stored semantic bindings before evaluation. |
| P1-GV-5 | NOT_APPLICABLE_TO_GIT_INTEGRATION | The reviewed ZIP was a temporary transfer artifact, not the integrated release vehicle. Generated release reports remain self-hashed. |
| P1-GV-6 | CLOSED_BY_INDEPENDENT_GIT_REGATE | Maintainer independently verified commit ancestry, scope, and clean status before integration. |

## Remaining external blockers

- Production `AUTO_APPROVED` and certificates remain blocked until a separately
  reviewed human-frozen calibration authority exists.
- The real 15-candidate pilot remains blocked until COMPLETE official C, E, and
  Dataset-owned packages are available.
- Development and zero-API synthetic integration remain enabled.

No provider or network call is required for this closure.
