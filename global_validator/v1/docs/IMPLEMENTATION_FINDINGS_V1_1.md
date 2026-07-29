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

## GV-F010: Authority receipt canonical reseal closes GV-F005 and GV-F007

- Severity: P1 authority closure.
- Status: resolved by maintainer publication and consumer rework.
- Evidence: the maintainer canonically resealed the local authority receipt
  without changing its tag, commit or manifest. Its canonical self SHA-256 is
  `c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4` and
  its physical SHA-256 is
  `3497460f16ca478dada7b25425775882f10d1cb2b5d3638c36cba4ec5fb2791b`.
- Resolution: remove `PINNED_PHYSICAL_FALLBACK`. Authority admission now
  requires both the published canonical self hash and published physical hash,
  reports `CANONICAL_SELF_HASH`, and emits zero warnings. Any semantic or byte
  drift fails closed.

## GV-F011: Replay trusted unverified persisted output hashes

- Severity: P1 replay integrity defect.
- Status: resolved locally, requiring maintainer re-gate.
- Evidence: a development decision could be edited from `PROVISIONAL` to
  `REJECTED` while retaining its old self hash and checksum listing;
  `replay_run()` previously read that unverified hash as the expected result
  and returned `matched=True`.
- Resolution: replay now verifies the canonical complete checksum listing,
  safe paths, exact bundle surface, symlink exclusion and duplicate-aware
  strict JSON before loading replay metadata. It then verifies authority,
  copied authority surfaces, input projections, GateResultSet self hash/schema/
  policy/bindings, decision self hash/schema/input/run bindings, audit records
  and any certificate bundle before semantic replay. Recomputed features,
  gates, decision and certificate must match the verified stored payloads
  exactly. Stale tamper and coherently resealed semantic drift both fail closed.

## GV-F012: Independent review found unpinned policy and partial verifiers

- Severity: P0 decision-authority and P1 evidence/replay portability defects.
- Status: resolved in the Global-owned review-closure candidate; maintainer
  re-gate required.
- Evidence: the independent review of `056b520e` showed that a different
  self-hashed allowed action policy changed the decision, standalone decision
  verification accepted a forged execution-config hash and reversed timestamps,
  fatal C/E signals could use whole-package fallback, and replay bound the
  original absolute repository path.
- Resolution: an immutable Global action-policy authority sidecar pins the
  reviewed policy and Contracts authority. Standalone decision verification
  now validates the complete run config and compares the full decision with
  deterministic recomputation. Certificate-bundle verification includes exact
  replay. Fatal semantic, disagreement and coverage signals require direct
  evidence refs. Replay spec V1.1 treats the original path as a non-authoritative
  hint and accepts an explicit authority root whose tag, commit, receipt,
  manifest, policy and registry are reverified.
- Review evidence and per-finding dispositions are preserved in
  `GLOBAL_VALIDATOR_V1_1_REVIEW_DISPOSITION.md` and the self-hashed release
  report `review_finding_disposition.json`.
