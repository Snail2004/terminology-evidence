# Global Validator V1.1 Implementation Findings

This file is append-only for implementation and review findings.

## GV-F001: Sealed gate policy does not select one action

- Severity: P1 design ambiguity.
- Status: resolved locally by a versioned Global Validator action-selection
  policy, still requiring maintainer review.
- Evidence: `GatePolicyArtifactV1` lists `allowed_actions`; several gates allow
  two actions. It does not select one action for a concrete trigger.
- Resolution: Global Validator owns a deterministic, self-hashed selection
  policy. The selected action must remain inside the sealed allowed set and its
  policy hash is bound into the execution configuration.

## GV-F002: Triggered constraints can lack upstream evidence refs

- Severity: P1 interoperability gap.
- Status: resolved deterministically, requiring contract-steward review.
- Evidence: an UNVERIFIED sense has no `review_artifact_ref`; UNRESOLVED
  polysemy has no `authority_ref`; UNJUDGEABLE collision has no index ref.
  However, a COMPLETE triggered gate requires a non-empty `evidence_refs`.
- Resolution: reference the sealed `ConstraintEvidencePackageV1` itself using
  its self hash and a stable embedded-artifact URI. Producer refs are preserved
  whenever present.

## GV-F003: Frozen calibration is fixture-only

- Severity: release blocker, not implementation blocker.
- Status: open.
- Evidence: no non-example human-frozen `CalibrationArtifactV1` exists in the
  standalone repository.
- Impact: implement and test frozen replay against the contract fixture, but
  production `AUTO_APPROVED` and certificate publication remain disabled until
  a separately reviewed human calibration is supplied.

## GV-F004: Legacy architecture document conflicts with Contracts V1.1

- Severity: documentation drift.
- Status: resolved by authority precedence.
- Evidence: the older document uses schema 1.0.0, uppercase gate IDs and a
  serialized severity field not present in V1.1.
- Resolution: preserve the document, but implement only the V1.1 algorithm and
  immutable `contracts-v1.1.0` authority.

## GV-F005: Published authority receipt has an invalid canonical self hash

- Severity: P1 authority publication defect.
- Status: open for maintainer re-publication; exact-byte fallback implemented.
- Evidence: declared self hash is
  `a95e50a6074fc8f3b749ebdf0e00657370bdc068a4d9efa7ffec27bbd807cb12`,
  while Contracts V1.1 canonical recomputation yields
  `c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4`.
- Physical receipt SHA-256 is
  `867c60892587cd108a052bbc16c3f057705360e10fc534ed1bd21ab0d3992d9e`.
- Resolution: accept only these exact published bytes plus all independently
  verified tag/commit/manifest/policy/registry/ZIP bindings. Report
  `PINNED_PHYSICAL_FALLBACK`; any byte or field drift still fails closed.
- Review request: maintainer should reissue a canonically sealed receipt in a
  future authority revision.

## GV-F006: Shared strict JSON loader permits duplicate keys

- Severity: P1 fail-closed gap.
- Status: resolved in the Global Validator boundary.
- Evidence: `terminology_contracts.integrity.strict_json_loads` rejects
  non-finite constants and trailing garbage but uses the default object parser,
  where a later duplicate key silently overwrites an earlier key.
- Resolution: every external JSON consumed by this runtime first passes a
  domain-owned duplicate-aware parser, then the official schema, integrity and
  semantic validators. The contracts package remains immutable.
- Review request: consider moving duplicate-key rejection into the next shared
  contracts release.

## GV-F007: Re-serializing the pinned authority receipt breaks replay

- Severity: P1 replay defect.
- Status: resolved.
- Evidence: the exact-byte fallback in GV-F005 binds the physical receipt SHA;
  canonical JSON re-serialization changes those bytes and makes a persisted run
  unable to verify its copied authority receipt.
- Resolution: immutable run bundles copy the verified receipt byte-for-byte and
  record the integrity mode and warning in `audit/authority_verification.json`.

## GV-F008: Collision index was verified only during certificate publication

- Severity: P1 evidence-binding gap.
- Status: resolved.
- Evidence: development decisions could previously consume constraint evidence
  containing a collision-index hash without supplying the indexed file.
- Resolution: all modes now require the exact strict-JSON collision index when
  the constraint package binds one, and verify both its physical SHA-256 and
  evidence-reference SHA before gate projection.

## GV-F009: Calibration SEALED status has no external approval anchor

- Severity: P1 production-authority gap.
- Status: resolved at the runtime admission boundary; authority publication is
  still pending.
- Evidence: Contracts V1.1 verifies a CalibrationArtifact's self hash, model,
  gate policy and internal dataset hashes, but the contracts authority receipt
  does not list which calibration self hash was human-reviewed for production.
- Resolution: frozen production mode requires an explicit nonzero
  `expected_calibration_sha256` and compares it with the verified artifact.
  Test-only mode accepts only the exact known contract-fixture self hash and
  rejects any other artifact. A copied fixture remains non-production.
- Review request: publish the reviewed human-frozen calibration hash in a
  future authority artifact so operators do not supply the pin manually.
