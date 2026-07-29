# INDEPENDENT REVIEW — AR-1, CONTEXT SUBSTITUTION C, AND HARNESS AR-3 FINAL PACKAGE V1

**Review ID:** `independent-review-ar1-c-ar3-final-v1.0`  
**Review date:** 2026-07-29  
**Package:** `AR1_C_AR3_Final_Review_Package_V1.zip`  
**Package SHA-256:** `2c3f6bec4225771d2433c25b5751f98fa4dd59ef05de4a267bd4c7a83cee0019`

---

## 1. Final verdict

```text
AR-1 DETACHED APPROVAL:
ACCEPTED

CONTEXT SUBSTITUTION FINAL NARROW PATCH:
ACCEPTED_FOR_INTEGRATION_WITH_REQUIRED_EVIDENCE_CORRECTION

SYSTEM INTEGRATION HARNESS AR-3:
ACCEPTED_FOR_MERGE
subject to Main Git graph/scope verification

OVERALL:
ACCEPTED_WITH_NONBLOCKING_EVIDENCE FINDINGS
```

No P0 implementation or architecture blocker remains in the three reviewed
scopes.

The Harness commit:

```text
339ac9001f8eda54d617189c92aa25bbc5eec8c7
```

may be considered for merge after Main verifies the real Git parent, ancestry,
clean worktree and exact Harness-owned path set.

This verdict does not authorize:

```text
Dataset P0B completion
real M6 15-candidate execution
controlled-registry/live-provider execution
calibration
validation or hidden-test access
production AUTO_APPROVED
certificate publication
```

---

# 2. Review-package integrity

Independent verification:

```text
Outer ZIP entries: 57
Duplicate entries: 0
Unsafe/traversal paths: 0
ZIP symlinks: 0

Package manifest records: 55
Manifest file-set equality: PASS
Manifest size/hash verification: PASS
Manifest canonical self-hash: PASS

DELIVERABLES records: 56
DELIVERABLES verification: 56/56 PASS

Outer-manifest canonical self-hash: PASS
Outer ZIP physical SHA/size binding: PASS
```

The package is suitable as a review handoff.

---

# 3. AR-1 detached approval publication

## 3.1 Independent checks

The exact AR-1 source archive contains six files, all under:

```text
review_evidence/contracts/contracts-v1.1.0/authority-r2/**
```

No file is under:

```text
terminology_contracts_v1/**
```

The detached publication verifies independently:

```text
approval_binding_v1.json self-hash: PASS
approval_binding_v1.json physical hash: PASS
CHECKSUMS: 5/5 PASS
evidence inventory: 4/4 PASS
approval artifact canonical self-hash: PASS
case-confusable member check: PASS
symlink/reparse check: PASS
```

Accepted pins:

```text
AR-1 binding self SHA:
ab7acbccfbdf64b74071133d4e049a06cbafc66c989f9b9f7ce52a08caa720b2

AR-1 binding physical SHA:
3ad39870e4e95c51ac88ee6a3d451504d41ba26d3bf5dc6569d25a585a7147a5

Contract R2 module tree:
938bca1f9c60596ef9403a43f0355476ad42afef

Receipt R2 self SHA:
a69b887ae650ba277c25c0d00e917dc834aa509320379a5cd17ff0241cf1b618

Receipt R2 physical SHA:
acb1d40b39110470f90d8b793aa162ca02252cb825e51ca94882e85c1f6a2f79
```

## 3.2 AR-1 verdict

```text
ACCEPTED
```

Option A is implemented correctly at artifact level:

```text
approval evidence remains outside the pinned Contract tree;
Receipt R2 is not edited or resealed;
no path-exclusion authority model is introduced;
approval is hash-pinned external proof.
```

The real commit/tree relationship remains a Main Git verification item because
the handoff contains source archives, not a Git object bundle.

---

# 4. Context Substitution final narrow patch

## 4.1 Code closure

Independent code inspection and mutation execution confirm:

```text
ledger_event_sequence_sha256 binds the complete ordered ledger;
stored captures must immediately precede their attempts;
unstored attempts cannot consume captures;
capture and attempt records have exact field sets;
unknown fields are rejected;
sealed expected ledger manifest is checked before replay;
numeric overflow/non-finite persisted JSON is rejected;
decision neutrality remains intact.
```

Independent mutations:

```text
all captures moved before attempts → REJECTED
unknown capture field → REJECTED
unknown attempt field → REJECTED
capture moved across attempt boundary → REJECTED
valid sealed replay → PASS
provider calls during replay → 0
```

The provided two C release ZIPs are byte-identical:

```text
502747beaeb6abfe256efcb28900b723c2776931d6e56439b548201e64900d1a
```

C remains decision-neutral:

```text
final_glossary_decision = null
no Global action emitted
no production certificate
```

## 4.2 Independent full-source rerun

The source contains:

```text
79 collected C tests
```

With real Dataset V3, pilot V1.1 and exact Contract R2 materialized, independent
execution produced:

```text
78 passed
1 skipped
0 failed
```

The skip was:

```text
external integration dependency not materialized:
pilot_normalized_review_pack_v1_4
```

## 4.3 P1-C-EVID-1 — “Full C 69/69” is not the full current source suite

The handoff states:

```text
Full C: 69/69 PASS
```

and provides a 69-test JUnit. Exact source collection shows that this JUnit
contains only the integration-readiness tests and omits all ten
`test_core_contracts.py` tests.

Additionally, the C release ZIP internally contains only an aggregate
counter-only JUnit:

```xml
<testsuite tests="22" failures="0" errors="0" skipped="0" />
```

It contains no testcase identities.

### Disposition

This is an evidence-labeling/release-chain finding, not a failure of the narrow
ledger patch. Independent execution confirms the omitted core tests pass.

Required correction:

```text
1. Rename the 69-test JUnit as focused integration-readiness evidence; or
2. issue a full current-source JUnit containing all 79 identities;
3. record the one external skip explicitly, or materialize the dependency and
   obtain zero skips;
4. do not describe the counter-only 22-test release JUnit as exact suite proof.
```

## 4.4 C verdict

```text
ACCEPTED_FOR_INTEGRATION_WITH_REQUIRED_EVIDENCE_CORRECTION
```

No code rollback or new semantic rework is required.

---

# 5. System Integration Harness AR-3

## 5.1 Source/release checks

```text
Final raw source paths: 24
Final P0 child paths changed from initial AR-3 child: 12
Paths unchanged from initial child: 12
All 24 final raw source files match the release ZIP bytes
Release ZIP members: 43
Unsafe paths: 0
Case collisions: 0
Symlinks: 0
Cache/bytecode: 0
```

The provided Harness JUnit is authentic against the exact source collection:

```text
Source-collected tests: 26
JUnit testcase identities: 26
Exact identity-set match: PASS
Failures: 0
Errors: 0
Skips: 0
```

Independently runnable non-Git-bound test groups passed:

```text
strict integrity: 3 tests + 6 subtests
inventory/join: 4 tests
authority/preflight: 2 tests
CLI/release: 3 tests
```

The exact production Git-bound positive checks cannot be reproduced from the
source-only package because the original `.git` object database is not included.

## 5.2 P0-AR3-1 closure

The final code closes the original external-root/fake-verifier bypass through
multiple independent checks:

```text
production repository root must equal the active Harness checkout root;
Contracts root must be the canonical terminology_contracts_v1 child;
custom verifier commands are non-production conformance only;
the verifier object must be the exact public verifier class;
GIT_* environment variables are removed;
GIT_NO_REPLACE_OBJECTS=1;
R2 publication ancestry and exact subtree OID are checked;
all 227 active Contract files are compared against reviewed Git blob OIDs;
Contract subtree worktree must be clean;
the checkout is checked again after the public verifier returns.
```

The final authority set persists:

```text
R2 receipt revision/self/physical hashes
tag/tag object/authority commit/tagged tree
R2 publication commit/module tree/file count
manifest/GatePolicy/feature-registry hashes
release manifest/CHECKSUMS/audit/final ZIP
AR-1 binding and approval hashes
Global action-policy and authority hashes
public Contract verifier report hashes
compatibility mode
```

R1 is limited to explicit sealed historical replay and cannot start or replace a
current R2 run.

## 5.3 Canary verification

The sealed canary independently passes:

```text
CHECKSUMS: 27 entries PASS
run manifest self-hash: PASS
authority mode: CONTRACTS_R2_CURRENT
Contract module tree: 938bca1f...
Contract file count: 227
decision: PROVISIONAL
AUTO_APPROVED: 0
certificate: 0
provider/network calls: 0
```

This is a real-authority Harness canary with a synthetic candidate and fake
development Global decision. It does not claim real M6 semantic evidence.

## 5.4 P1-HAR-REL-1 — Release builder is not commit/test bound

The current exact release ZIP is accepted because:

```text
its physical SHA is pinned by the review package;
the 24 reviewed source paths match its member bytes;
the external 26-test JUnit exactly matches source collection;
the package manifest and DELIVERABLES are valid.
```

However, the Harness `build-release` implementation itself:

```text
archives the live filesystem;
does not require a clean exact HEAD;
does not build from Git object bytes;
does not parse or bind JUnit;
does not emit an internal per-file manifest/CHECKSUMS;
does not fix member timestamps/order for deterministic reproduction.
```

### Disposition

This does not reopen AR-3 common-binding architecture and does not invalidate
the exact reviewed release.

Required before the next official Harness release or real M6 pilot archive:

```text
exact Git-object or clean-exact-HEAD source binding;
canonical sorted member inventory;
internal manifest and CHECKSUMS;
exact testcase-identity JUnit binding;
commands/environment/Git receipt;
two-build deterministic evidence within the pinned environment.
```

## 5.5 Harness verdict

```text
ACCEPTED_FOR_MERGE
```

No remaining P0 finding was found in the authorized AR-3 binding scope.

Main must still verify on the canonical repository:

```text
child commit = 339ac9001f8eda54d617189c92aa25bbc5eec8c7
expected parent/ancestry
cumulative AR-3 scope = 24 Harness-owned paths
final child scope = 12 allowlisted Harness-owned paths
8 frozen files unchanged
worktree clean
diff check PASS
```

---

# 6. Required actions

## Main

```text
1. Record AR-1 as accepted.
2. Keep C in main; add an evidence-correction receipt.
3. Verify Harness Git graph and exact scope.
4. Merge exact Harness commit 339ac900 if the Git checks pass.
5. Do not merge a rebuilt or amended Harness commit under this verdict.
```

## C evidence correction

No code patch required. Provide:

```text
corrected test-scope report
full source-identity JUnit, or accurate focused-suite label
explicit 78 PASS / 1 external SKIP independent/full result
```

## Harness evidence hardening

Create a separate follow-up backlog item for the release builder. Do not mix it
into the already-reviewed AR-3 common-binding child unless Main deliberately
opens a new narrow review.

---

# 7. Final decision

```text
AR-1: PASS
C: PASS_WITH_REQUIRED_EVIDENCE_CORRECTION
HARNESS AR-3: ACCEPT_FOR_MERGE
OVERALL: ACCEPTED_WITH_NONBLOCKING_EVIDENCE FINDINGS
```
