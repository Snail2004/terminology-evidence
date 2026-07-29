# Evidence E Post-Zero-API Readiness Findings V1

Report version: 1.2.3

Status: `HOLD_EXTERNAL_INPUTS`

This report records findings discovered while implementing the post-zero-API
readiness milestone. Generated release evidence contains the machine-readable
counterpart `readiness_findings_report.json`.

## E-RDY-001 - stale accepted milestone metadata

- Severity: INFO
- Status: RESOLVED
- Finding: the V1.2 draft named `50d19c8` as the final tip and reported 63/63
  plus 5/5 tests.
- Resolution: the accepted integration tip is `a1707a8`; final accepted gates
  are 66/66 full E and 8/8 focused zero-API/registry.

## E-RDY-002 - official Dataset identity unavailable

- Severity: BLOCKER
- Status: HOLD_EXTERNAL
- Evidence: current pilot lacks official effective-sense, Vietnamese surface,
  domain-anchor and top-level input-contract authority.
- Close condition: 15 Dataset-owned COMPLETE
  `FrozenCandidateContractV1@1.1.0` inputs with package manifest.
- Current behavior: `BLOCKED_DEVELOPMENT_IDENTITY`, projected package count 0.

## E-RDY-003 - controlled registry empty

- Severity: BLOCKER
- Status: HOLD_EXTERNAL
- Evidence: published controlled registry is byte-empty.
- Close condition: non-empty sealed registry, retrieval-content schema and
  immutable content payloads or content-addressed references.
- Current behavior: no controlled retrieval provider is created.

## E-RDY-004 - provider canaries not authorized

- Severity: BLOCKER
- Status: HOLD_APPROVAL
- Close condition: official inputs, authority verification, safe secret loading
  and explicit maintainer approval.
- Current behavior: zero external API/provider calls.

## E-RDY-005 - Global Validator availability

- Severity: INFO
- Status: RESOLVED
- Finding: Global Validator executable has been integrated into canonical main.
- Consequence: E still cannot hand off real evidence until E-RDY-002 through
  E-RDY-004 close; Global availability does not waive producer authority.

## E-RDY-006 - cross-platform ZIP ordering

- Severity: LOW
- Status: RESOLVED
- Finding: the first focused test showed that Windows `Path` comparison did not
  produce the same lexical order as canonical ZIP member names.
- Resolution: release files are sorted by canonical POSIX relative path before
  manifest, checksum and ZIP generation.

## E-RDY-007 - external Contracts mapping fixtures unavailable

- Severity: INFO
- Status: RESOLVED
- Finding: the first readiness gate omitted `TERMINOLOGY_DATASET_ROOT`, leaving
  two real dataset-mapping tests skipped.
- Resolution: the final R2 gate binds the in-repository Dataset root and passes
  all 115 Contracts tests, including both V3 and pilot V1.1 mapping fixtures.

## E-RDY-008 - permissive artifact decoder and link traversal

- Severity: P1
- Status: RESOLVED
- Finding: readiness verification previously used default JSON parsing and did
  not reject symlink/path ambiguity before hashing.
- Resolution: one readiness-owned strict recursive JSON/JSONL decoder now
  rejects duplicate keys, non-finite/overflow values, invalid UTF-8 and
  trailing data; manifest refs are canonical, case-conflict checked and
  resolved beneath a symlink/junction-free artifact root.

## E-RDY-009 - release without a valid test gate

- Severity: P1
- Status: RESOLVED
- Finding: release JUnit was optional and unparsed.
- Resolution: JUnit is mandatory, must contain the exact hash-pinned 80-test E
  identity set with zero failures/errors/skips, and must match the sealed test
  source-tree hash before any output directory is created.

## E-RDY-010 - R2 release-only authority rejected as tag drift

- Severity: P1
- Status: RESOLVED
- Finding: the E readiness verifier compared the entire Contracts tree against
  the frozen V1.1 tag, so it rejected the independently reviewed R2 authority
  maintenance publication even though source, schema, policy and registry bytes
  remained unchanged.
- Resolution: active authority now requires the canonical in-repository R2
  receipt and pins its self/physical hashes, exact Contracts and release Git
  trees, final audit, final manifest and final ZIP. Legacy R1, R2 tamper,
  non-release drift and arbitrary release mutation fail closed.

## E-RDY-011 - standalone Dataset input lacked producer authority

- Severity: P1
- Status: RESOLVED_CODE_PATH
- Finding: a loose resealed COMPLETE candidate could be accepted without a
  Dataset release manifest or receipt.
- Resolution: official execution now requires an externally pinned receipt and
  exact 15-member manifest. Strict decoding, producer identity, member bytes,
  candidate self/input hashes and all join fields verify before engine setup.
- External state: E-RDY-002 remains HOLD until Dataset publishes the real set.

## E-RDY-012 - direct replay lacked an external manifest anchor

- Severity: P1
- Status: RESOLVED
- Resolution: replay CLI requires `--expected-manifest-sha256`; manifest and
  every JSONL stream use the shared strict decoder, and resealed local drift is
  rejected before replay.

## E-RDY-013 - JUnit prefix/count admitted fabricated execution evidence

- Severity: P1
- Status: RESOLVED
- Resolution: policy V2 rejects skipped tests and requires the exact 80
  testcase identities, identity SHA and E test-source tree SHA. Renamed,
  missing and fabricated replacements fail closed.

## Semantic boundary clarification

Offline fixture runs may produce schema-valid shared packages only for
projection conformance. They are not real attestation evidence authority.
`READY_FOR_REAL_DEVELOPMENT_PILOT` requires provider canaries to PASS, not HOLD.
`READY_FOR_GLOBAL_HANDOFF` additionally requires real-pilot ledger/replay and
successful exact identity/hash consumption by Global Validator.
