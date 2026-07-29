# Global Terminology Validator V1.1 Review Handoff

## Implemented

- Exact `contracts-v1.1.0` authority verification, including manifest, tag,
  contract tree, sealed gate policy and feature registry.
- Duplicate-aware strict JSON loading followed by official integrity, schema and
  semantic validation. Literal non-finite numbers and exponent overflow are
  rejected before schema evaluation, including nested arrays and objects.
- Exact Global Input joins and physical collision-index binding.
- Deterministic projection of all 12 registered hard gates from C, E and
  constraint evidence.
- Self-hashed action-selection policy restricted to actions allowed by the
  sealed GatePolicyArtifact and pinned by the reviewed Global action-policy
  authority sidecar.
- Registry-based feature assembly; development and frozen calibrated decision
  modes; deterministic precedence and replay hash.
- Exact certificate projection, official certificate-bundle verification,
  immutable run directories, canonical complete checksums and fail-closed
  semantic replay.
- Replay preflight verifies strict JSON, safe bundle paths, checksums,
  authority, copied input projections, gate/decision bindings, audit records
  and any certificate bundle before recomputation.
- When an explicit verified authority root is supplied, the persisted
  repository path is treated only as opaque provenance. Without that override,
  an unusable or relative repository path still fails closed.
- Release evidence requires clean Global and Contracts JUnit inputs and binds
  their physical hashes, current testcase identity sets and identity hashes.
- Standalone decision and certificate-bundle verification perform exact
  configured-policy recomputation. Replay spec V1.1 supports a separately
  verified portable authority root rather than trusting the original path.
- Fatal semantic, disagreement and coverage signals require direct producer
  evidence refs; sealed-package fallback remains limited to aggregate nonfatal
  states and constraint evidence.
- CLI commands: authority verify, input assembly/validation, run, replay,
  decision verification and certificate-bundle verification.
- Synthetic zero-API pilot: five senses, 15 candidates, 15 provisional
  decisions, zero AUTO_APPROVED, zero certificates, zero network calls, 15/15
  deterministic replays.

## Review Findings

The detailed append-only log is
`global_validator/v1/docs/IMPLEMENTATION_FINDINGS_V1_1.md`.

- `GV-F001`: shared gate policy permits multiple actions; the implementation
  adds a versioned Global-owned deterministic selection policy.
- `GV-F002`: unresolved constraint states may lack an upstream evidence ref;
  the sealed constraint package itself is used as deterministic fallback
  evidence.
- `GV-F003`: no real human-frozen calibration artifact exists. Production
  AUTO_APPROVED and certificate publication remain blocked. The contract
  example requires an explicit test-only flag and is identified by self hash
  even if copied elsewhere.
- `GV-F005`/`GV-F010`: the maintainer resealed the authority receipt.
  Admission now reports `CANONICAL_SELF_HASH` with zero warnings and binds both
  its canonical and physical published hashes; the fallback was removed.
- `GV-F006`: the shared JSON loader permits duplicate keys. This boundary adds
  duplicate-key rejection without modifying contracts.
- `GV-F007`: the pinned receipt must be copied byte-for-byte into replay
  bundles; canonical re-serialization is forbidden.
- `GV-F008`: collision-index binding is now checked before any gate or score in
  every mode, not only during certificate publication.
- `GV-F009`: production frozen mode requires an exact reviewed calibration
  self-hash pin; test-only mode accepts only the known contract fixture.
- `GV-F011`: persisted replay previously trusted an unverified decision hash.
  Bundle, gate, decision, certificate and recomputed semantic outputs are now
  independently verified and cross-bound.
- `GV-F012`: independent review found an unpinned action policy, partial
  standalone verifiers, broad C/E fallback and absolute-path replay. These are
  closed by the authority sidecar, exact recomputation, direct-evidence rules
  and portable replay authority override. See the preserved review and
  disposition report.
- `P1-GV-PORT-1`, `P1-GV-JSON-2` and `P1-GV-REL-3`: cross-platform replay,
  exponent overflow and stale JUnit evidence are closed by the narrow
  post-review patch and adversarial regressions.

## Known Gaps

- The 15-candidate pilot is a sealed synthetic contracts fixture. Real pilot
  execution waits for reviewed, COMPLETE `GlobalValidatorInputV1` packages from
  C/E and the Dataset Adapter.
- Frozen score/certificate behavior is implemented and tested only against the
  explicitly non-production contract calibration fixture.
- Contract R2 bytes pass the integration gate, but Global does not promote the
  Contract-owned publication verdict; that external review remains separately
  owned.

## Verification

- Global Validator focused/contract/adversarial/integration suite: `80/80`
  passed with zero skipped tests.
- Shared Contracts V1.1 and R2 authority-maintenance suite: `145/145` passed
  with zero skipped tests against `E:\Data-KL`.
- Synthetic pilot: `5` senses, `15` candidates, `15/15` replay PASS,
  `0` network/provider calls, `0` AUTO_APPROVED and `0` certificates.
- Frozen contract fixture: score replay and official certificate-bundle
  verification PASS; fixture-only certificate is not production authority.
- Release builder: PASS, `0` network/provider calls, bound to clean R2
  integration commit `b35825d1166da630aa9e8b7d551907bbee0b1864`.
- Python compile, diff-check, ownership/cache and credential-pattern scans:
  PASS.
- Global JUnit physical SHA-256:
  `54603c517bcd23c3720ad0dade3e9909d71e79aedd0a7008e51269a72a836009`;
  testcase identity SHA-256:
  `a82d5ad1cb815c90a271a8c7c6e4223957ed28cb372950dc6f89b226d07dc854`.
- Contracts JUnit physical SHA-256:
  `95e5b36585d045504e24dd60a4830fb9f59f3183444661500c2eaac6a964ca64`;
  testcase identity SHA-256:
  `a3ac806065590af4627daaca3b2cb542666320d8ed2c4dfed54261d1130fbde1`.

## Reviewer Focus

1. Validate the action-policy authority sidecar and rejection of any other
   otherwise-allowed policy mapping.
2. Confirm the sealed-package fallback evidence convention for incomplete
   constraint refs.
3. Adversarially mutate joins, gate signals, calibration, timestamps,
   collision index, decision/gate/certificate output, checksum listing and
   authority receipt, including coherent self-hash/checksum reseals.
4. Confirm no runtime imports producer internals or networking libraries and no
   runtime path reads raw datasets.
5. Do not treat the frozen fixture certificate as production authority.
