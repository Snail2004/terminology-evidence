# INDEPENDENT TECHNICAL REVIEW — CONTRACT STEWARD AUTHORITY MAINTENANCE V1.2 / RECEIPT R2

**Review ID:** `contracts-v1.1-authority-r2-independent-review-v1.0`  
**Review date:** 2026-07-29  
**Review bundle:** `contracts_v1_1_authority_maintenance_v1_2_r2_review_bundle_282409c(1).zip`  
**Review bundle SHA-256:** `02d01c486105291c419bdf1096328f10e255cd5590e2713a1134f7604bf09b38`  
**Source ZIP SHA-256:** `0bb2963090ec64312cb80c6f19089e736fc634e3897819eb58a090698b562237`  
**Final Contracts ZIP SHA-256:** `2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471`  
**Receipt R2 physical SHA-256:** `acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79`  
**Receipt R2 canonical self SHA-256:** `a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618`

---

## 1. Verdict

```text
TAGGED CONTRACT CONTENT: PASS
SCHEMA/POLICY/REGISTRY IMMUTABILITY: PASS
FINAL ZIP IDENTITY: PASS
RECEIPT R2 CANONICAL INTEGRITY: PASS
RECEIPT R2 PHYSICAL DISTRIBUTION PIN: PASS
HISTORICAL RECEIPT PRESERVATION: PASS
FINAL RELEASE MANIFEST/CHECKSUMS: PASS
CURRENT JUNIT EVIDENCE: PASS
BASE CONTRACT SUITE: 115/115 PASS
AUTHORITY MAINTENANCE LOGIC: 30/30 PASS IN REVIEWER-SYNTHETIC GIT HARNESS
EXACT GIT GRAPH/PUBLICATION TREE: MAIN MERGE CHECK REQUIRED

OVERALL:
ACCEPTED_FOR_AUTHORITY_PROMOTION_WITH_NONBLOCKING_FINDINGS
```

The exact R2 receipt bytes and the exact final release artifacts are accepted.

The receipt itself must remain byte-identical and may continue to contain:

```text
publication_status = PENDING_INDEPENDENT_REVIEW
```

The independent approval is represented by the separate approval artifact issued
with this report. Do not edit and reseal R2 merely to change this field.

This review closes the Contract-owned R2 authority blocker. It does not close
Global-owned compatibility, replay, JSON or release-evidence findings.

---

## 2. Bundle and source integrity

### 2.1. Outer review bundle

```text
Entries: 15
Duplicate entries: 0
Unsafe/traversal entries: 0
Symlinks: 0
```

The outer bundle contains:

```text
source archive
R2 receipt and sidecar
final release ZIP and sidecar
release manifest/checksums
final audit
authority verification report
JUnit
commands
handoff report
```

The root `CHECKSUMS.sha256` belongs to the complete final release directory. Some
listed files are not duplicated at the outer bundle root, but all are present
inside the source ZIP under:

```text
terminology_contracts_v1/release/v1.1.0-final/
```

The root copies that are present are byte-identical to the copies in the source
ZIP.

### 2.2. Source archive

```text
ZIP comment: 282409c470049760904fa16de4c67d711b5fcd00
Entries: 270
Cache/bytecode entries: 0
.git: absent, as expected for git archive
```

After excluding the release subtree, current source is byte-identical to the
previously accepted tagged/final Contracts package. No schema, policy, registry,
fixture, migration, shared Python validator or semantic contract file changed.

---

## 3. Receipt R2 verification

Independent recomputation:

```text
Declared self SHA:
a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618

Calculated canonical self SHA:
a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618

Physical SHA:
acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79
```

Receipt bindings checked:

```text
authority tag: contracts-v1.1.0
authority commit: 38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed
tag object: 1a8c00d12f100145a276cd8304440ff0a7e8d2a1
contract tree: d6386c4c4d19ba2aad982a519b9b59ecfd2213c9
manifest self SHA: e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b
GatePolicy self SHA: 9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2
feature registry canonical SHA:
057f47d68097286f04f0870d2e78944e59c07b0cb4e9db7f9d8675c9f2c8b182
final ZIP SHA:
2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471
final audit self/physical SHA
portable relative paths
two superseded R1 receipts
```

No absolute workstation path participates in authority identity.

---

## 4. Final release verification

### 4.1. Release directory

From the source ZIP:

```text
Release-manifest records: 22
Actual member files excluding manifest/CHECKSUMS: 22
File-set equality: PASS
Per-file size/hash: PASS
Release manifest self-hash: PASS
CHECKSUMS exact sorted content: PASS
```

Top-level self-hashed reports independently recomputed and passed:

```text
authority verification report
final release audit
Git commit receipt
release manifest
static scan
credential scan
ownership scan
environment report
manifest verification
GatePolicy verification
feature-registry verification
```

### 4.2. Final Contracts ZIP

```text
Members: 159
Duplicate members: 0
Unsafe paths: 0
Symlinks: 0
Internal manifest records: 157
Manifest member verification: 157/157 PASS
Internal CHECKSUMS records: 158
Internal CHECKSUMS verification: 158/158 PASS
```

The final ZIP is byte-identical to the independently accepted RC4 artifact:

```text
2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471
```

This is strong evidence that semantic Contracts V1.1.0 content did not move.

---

## 5. Independent tests

### 5.1. Base Contracts suite with real datasets

Reviewer materialized:

```text
d2l_context_support_set_validation_ready_v3
pilot_dev_only_v1_1
```

Result:

```text
115 passed
0 failed
0 skipped
```

### 5.2. Current JUnit authenticity

Source collection:

```text
145 tests
```

Provided JUnit:

```text
145 testcase records
145 unique testcase identities
0 failures
0 errors
0 skipped
```

Exact source-collection identity comparison:

```text
missing from JUnit: 0
stale in JUnit: 0
```

Therefore the JUnit provided for this exact source is accepted.

### 5.3. Maintenance logic

The source-only bundle does not contain the original Git object database.
Reviewer therefore created a synthetic Git harness with:

```text
the exact accepted tagged file bytes
the current authority-maintenance source
an annotated synthetic tag
reviewer-local Git OIDs
```

Constants referring to Git OIDs and the reviewer-local rebuilt ZIP hash were
changed only in the disposable review harness.

Result:

```text
30 passed
```

This validates builder/verifier mutation behavior, historical-receipt handling,
path checks, JUnit failure/skip gates, manifest/ZIP tamper rejection and
idempotence logic. It does not replace Main's verification of the real Git
object graph.

---

## 6. Findings

## P2-CON-JSON-1 — Authority strict JSON does not reject exponent overflow at parse time

Reproduction:

```text
{"x": 1e9999}  → accepted as +Infinity
{"x":-1e9999}  → accepted as -Infinity
nested/list overflow → accepted
```

The loader rejects literal `NaN`, `Infinity` and `-Infinity`, but does not check
`parse_float` overflow.

Current R2 receipt verification remains fail-closed because the receipt uses an
exact field shape and downstream fields enforce their expected string/integer
types and values. No accepted R2 artifact contains a non-finite number.

Recommended backlog:

```text
finite parse_float or recursive finite-number scan
tests for positive/negative/nested/list exponent overflow
```

Do not change the accepted R2 bytes for this finding.

---

## P2-CON-REL-2 — Builder validates JUnit totals, not the exact expected testcase set

`_read_junit()` correctly rejects:

```text
zero tests
failures
errors
skips
```

but does not itself pin the exact 145 testcase identities. A fabricated
145-pass JUnit could satisfy the builder.

The current artifact is not affected: reviewer independently matched all 145
provided testcase identities to the exact source collection.

Recommended for the next maintenance release:

```text
record testcase identity SHA
verify exact expected identity set/hash
reject renamed/missing/fabricated replacement tests
```

---

## P2-CON-REP-3 — Deterministic final ZIP rebuild is environment-bounded

Using the exact accepted ZIP member bytes, fixed timestamp, fixed permissions,
compression level 9 and current builder logic, a Linux reviewer rebuild produced
a semantically identical ZIP with a different physical SHA.

Likely cause:

```text
Python/zlib/platform compression implementation differences
```

The pinned final ZIP itself remains valid and byte-identical to approved RC4.
The finding limits the claim that any platform can independently recreate the
same compressed bytes.

Recommended:

```text
pin Python and zlib versions for byte-level rebuild
or
define the approved stored ZIP bytes as distribution authority and verify
member bytes semantically on other platforms
```

---

## MERGE-CHECK-CON-4 — Real Git graph and final publication commit require Main verification

The source ZIP comment and reports state:

```text
final commit: 282409c470049760904fa16de4c67d711b5fcd00
parent: 3efc430312f080b4f8b1752e18173501283292f8
branch: chore/contracts-v1.1-authority-r2
```

The embedded Git receipt was generated before the final publication commit and
binds implementation commit `3efc430...`; it does not independently prove the
final `282409c...` graph.

Main must verify:

```bash
git rev-parse 282409c470049760904fa16de4c67d711b5fcd00^
git diff --name-status \
  677ef6b434f268153363ea06b335cb8df188ee19 \
  282409c470049760904fa16de4c67d711b5fcd00
git diff --check \
  3efc430312f080b4f8b1752e18173501283292f8 \
  282409c470049760904fa16de4c67d711b5fcd00
git status --porcelain
```

Expected:

```text
all cumulative changes under terminology_contracts_v1/release/**
contracts-v1.1.0 annotated tag unchanged
tag commit unchanged
tagged contract tree unchanged
worktree clean
```

This is a promotion condition, not a defect in the R2 receipt bytes.

---

## 7. Promotion policy

### Accepted authority pins

Consumers may pin exactly:

```text
receipt physical SHA:
acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79

receipt canonical self SHA:
a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618

final Contracts ZIP SHA:
2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471
```

after Main completes the Git merge checks and stores the separate independent
approval artifact.

### Do not modify

```text
contracts_v1_1_0_authority_receipt_r2.json
final Contracts ZIP
tag contracts-v1.1.0
tagged schemas/policies/registries
historical R1 receipt bytes
```

### Global follow-up

This review resolves:

```text
HOLD-GV-AUTH-4 — exact Contract R2 publication not independently reviewed
```

subject to Main's Git graph check.

Global must still:

```text
close its own narrow findings
load the exact accepted R2 bundle
rerun 68 Global tests
rerun 145 Contracts tests
run authority CLI
record 0 network calls
```

If Main's exact Git verification changes any publication commit/tree pin expected
by Global, Global must make a narrow compatibility update.

---

## 8. Final conclusion

Receipt R2 correctly repairs the invalid R1 self-hash without changing frozen
Contracts V1.1.0 semantics. The final release ZIP is exactly the accepted RC4
artifact, the new receipt is canonically and physically sealed, historical bytes
are preserved, and current JUnit evidence matches the exact 145-test source
collection.

The remaining findings are nonblocking maintenance/reproducibility hardening.
No Contracts V1.1.1 semantic change is required.

**Final verdict:**

```text
ACCEPTED_FOR_AUTHORITY_PROMOTION_WITH_NONBLOCKING_FINDINGS
```
