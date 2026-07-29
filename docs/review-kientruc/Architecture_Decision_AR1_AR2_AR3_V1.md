# ARCHITECTURE DECISION — AR-1, AR-2, AR-3

**Decision ID:** `terminology-evidence-architecture-decision-ar1-ar2-ar3-v1.0`  
**Date:** 2026-07-29  
**Decision authority:** External Architecture Review  
**Source package:** `architecture-review-consolidated-20260729-v1.zip`  
**Source package SHA-256:** `6882e05fb625a0db2503693b49eb26e923f5378bc28e6134da409cb2c13633fd`

```text
AR-1: OPTION A SELECTED
AR-2: ARCHITECTURE APPROVED WITH EXPLICIT CONSTRAINTS
AR-3: NARROW R2 COMMON-BINDING UPDATE AUTHORIZED
```

This decision does not authorize semantic Contract changes, authority resealing,
Global decision changes, Dataset/C/E ownership changes, calibration, validation,
hidden-test access or production approval.

---

# 1. AR-1 — Contract R2 tree binding

## 1.1. Decision

```text
SELECT OPTION A:
DETACHED, HASH-PINNED APPROVAL EVIDENCE OUTSIDE THE PINNED CONTRACT TREE
```

Options B and C are rejected for R2:

```text
B — explicit review-path exclusion: REJECTED
C — versioned authority republication: REJECTED FOR CURRENT R2
```

## 1.2. Authority identity

For Contract R2, authority identity remains the exact complete
`terminology_contracts_v1` module tree of the reviewed publication:

```text
publication commit:
282409c470049760904fa16de4c67d711b5fcd00

pinned module tree:
938bca1f9c60596ef9403a43f0355476ad42afef
```

No path is excluded from this tree identity.

The following remain immutable:

```text
contracts-v1.1.0 annotated tag
authority commit
tagged contract tree
Receipt R2 bytes
final Contracts ZIP bytes
schema/policy/registry/validator bytes
historical receipt bytes
```

## 1.3. Meaning of approval evidence

Independent approval evidence is:

```text
EXTERNAL PROOF OF AUTHORITY
```

It is not part of Contract authority content and does not mutate the authority
being approved.

Receipt R2 may remain byte-identical with:

```text
publication_status = PENDING_INDEPENDENT_REVIEW
```

Official approval is established only by verifying both:

```text
A. exact Contract R2 authority bundle;
B. external approval binding and its evidence inventory.
```

## 1.4. Canonical detached location

Use a repository-level path outside `terminology_contracts_v1/**`:

```text
review_evidence/
  contracts/
    contracts-v1.1.0/
      authority-r2/
        approval_binding_v1.json
        CHECKSUMS.sha256
        contracts_v1_1_0_authority_receipt_r2_independent_approval.json
        contracts_v1_1_authority_maintenance_v1_2_r2_independent_audit.json
        Independent_Review_Contract_Steward_Authority_Maintenance_V1_2_R2.md
        Hau_Review_Contract_Steward_R2_Authority_Promotion.md
```

The directory name and file names are canonical POSIX-relative paths.
Case-confusable duplicates, symlinks, junctions, reparse points, dot segments,
drive/UNC paths and path traversal are forbidden.

## 1.5. Approval binding schema

`approval_binding_v1.json` must be self-hashed and contain at least:

```text
schema_id
binding_version
approval_status
issued_at
publisher_role
authority_tag
authority_commit
authority_module_tree_git_oid
receipt_revision
receipt_canonical_self_sha256
receipt_physical_sha256
final_contracts_zip_sha256
approval_artifact_canonical_self_sha256
approval_artifact_physical_sha256
review_report_physical_sha256
independent_audit_physical_sha256
promotion_notes_physical_sha256
evidence_inventory
previous_binding_sha256 or null
integrity.self_sha256
```

The binding must not claim that its own presence changes Contract authority.

## 1.6. Ownership

```text
Contract Steward:
owns Contract authority publication and immutable Contract bytes.

External Reviewer:
issues review and approval evidence.

Main Maintainer / Review Governance:
owns detached evidence publication, approval_binding_v1.json and discovery.

Global / Integration Harness:
consume and verify; they do not issue or edit approval evidence.
```

## 1.7. Consumer policy

For an official new run:

```text
Contract R2 exact tree/receipt verification: REQUIRED
Detached approval binding verification: REQUIRED
```

For development conformance without the approval binding:

```text
authority status = UNAPPROVED_EXTERNAL_HOLD
production/frozen actions = forbidden
```

Global's exact Contract module-tree pin remains unchanged. The Integration
Harness is the required orchestration gate for the detached approval binding.
Direct consumers outside the Harness must perform the same verification or
remain development-only.

## 1.8. Implementation authorization for AR-1

Architecture is approved.

Main may issue a narrow governance-publication task to publish the detached
evidence and binding under `review_evidence/**`.

Not authorized:

```text
editing/resealing Receipt R2
adding evidence under terminology_contracts_v1/**
excluding paths from Global tree identity
republishing Contracts authority
moving the contracts-v1.1.0 tag
```

---

# 2. AR-2 — Evaluation & Preregistration architecture

## 2.1. Decision status

```text
ARCHITECTURE APPROVED
EVALUATION IMPLEMENTATION MAY RESUME WITHIN THIS DECISION
```

The dirty HOLD worktree is design evidence only. It must not be committed as one
opaque patch. Evaluation must resume from a clean reviewed baseline and apply
the approved design in reviewable commits.

---

## 2.2. Release source model

Approved model:

```text
ARCHIVE BY EXACT GIT OBJECT
+
CLEAN EXACT-HEAD REQUIREMENT FOR NORMAL MAINTAINER CLI
```

Rules:

1. Source archive bytes come from the specified Git commit/tree, not the live
   filesystem.
2. Normal maintainer release requires:
   ```text
   worktree clean
   HEAD == requested source commit
   no staged/untracked source bytes
   ```
3. Detached-object review mode may build from a specified Git object without
   trusting checkout state.
4. Generated release artifacts are staged outside the repository.
5. Publication is atomic.
6. No dirty path exception is granted during build, including
   `evaluation/v1/release/**`.
7. An optional in-repository publication is a separate reviewed publication
   commit after artifact bytes are frozen; it is not the source commit used to
   build itself.

---

## 2.3. Exact test identity authority

Approved model:

```text
COMMITTED, VERSIONED, SELF-HASHED EXPECTED-TEST MANIFEST
```

The manifest records exact pytest testcase identities and its own self-hash.

Release requirements:

```text
release runs its own Evaluation suite
JUnit is parsed, not synthesized from counters
failures = 0
errors = 0
skipped = 0
actual testcase identity set == committed expected set
testcase identity SHA == expected SHA
```

Externally supplied JUnit may be accepted only if all identities match exactly.
Count-only or prefix-only verification is forbidden.

Any test-set change requires review of the expected-test manifest in the same
source commit.

---

## 2.4. Receipt modes

Exactly three modes are approved:

### `REAL_AUTHORITY`

May emit a real frozen preregistration state only after verifying versioned
external authority artifacts against an approved authority profile.

### `SYNTHETIC_LOCAL_CONFORMANCE`

May exercise schemas and state transitions locally, but may emit only:

```text
CONFORMANCE_ONLY
```

It must never emit:

```text
FROZEN_BEFORE_VALIDATION
READY_FOR_VALIDATION
READY_FOR_HIDDEN_TEST
VALIDATION_ACCESSED
HIDDEN_TEST_ACCESSED
```

and must never open validation/test data.

### `LEGACY_READ_ONLY`

May verify historical receipt bytes and render a compatibility projection.
It cannot transition state, freeze a new plan or authorize access.

Legacy bytes must not be reinterpreted as the new real-authority schema.

---

## 2.5. Evaluation authority profile

Use verified external receipts, not arbitrary embedded placeholder hashes.

A committed, versioned and self-hashed `AllowedAuthorityProfile` must define the
accepted authority classes and exact required bindings, including:

```text
Contracts authority tag/commit/tree
Receipt R2 revision/self/physical hash
detached Contract approval-binding schema/hash requirements
Global action-policy authority identity
Global implementation/release identity required for evaluation
Dataset split-manifest schema and hash requirements
Evaluation metric/experiment/label-mapping registry versions
```

Runtime artifacts are supplied externally and verified against this profile.

Reject:

```text
empty authority fields
placeholder values
unknown fields
unverified Git labels
self-hash-only receipts
synthetic authorities in REAL_AUTHORITY mode
```

---

## 2.6. Durable state model

Approved source of truth:

```text
APPEND-ONLY, HASH-CHAINED EVENT LEDGER
```

Each event must contain:

```text
sequence_number
event_type
issued_at
actor
previous_event_sha256
authority_refs
payload
event_sha256
```

The mutable state JSON is only an atomically published projection of the ledger.

### Writer model

For V1:

```text
one local writer
exclusive operating-system lock
in-process lock
no distributed multi-writer support
```

The lock is held across validation, event append, fsync and projection
publication.

### Write ordering

```text
1. validate current ledger and projected state;
2. construct and hash event;
3. append event;
4. fsync ledger;
5. build new projection from ledger;
6. write temporary projection;
7. fsync temporary file and parent directory where supported;
8. atomic replace;
9. release lock.
```

### Divergence and crash recovery

The ledger is authoritative.

On ledger/projection divergence:

```text
FAIL CLOSED
```

No silent rollback, truncation or state rewrite is allowed.

Recovery requires an explicit, self-hashed recovery receipt containing:

```text
ledger head before recovery
old projection hash
rebuilt projection hash
reason
operator
time
recovery tool/version
```

Recovery rebuilds only the projection from a valid ledger; it does not rewrite
historical events.

---

## 2.7. Freeze and access events

At minimum, persist distinct events:

```text
PREREGISTRATION_FROZEN
VALIDATION_ACCESS_OPENED
CALIBRATION_ARTIFACT_FROZEN
HIDDEN_TEST_ACCESS_OPENED
AMENDMENT_ACCEPTED
EXPLORATORY_POST_TEST_DECLARED
RECOVERY_RECORDED
```

Each access event is one-time and bound to:

```text
frozen preregistration receipt
split manifest
authority profile
actor
access timestamp
previous ledger head
```

Reload/restart must preserve the consumed access state.

### Amendment rules

Before validation access:

```text
versioned amendments are allowed;
a new freeze receipt is required.
```

After validation access but before hidden-test access:

```text
an amendment must be append-only;
it must invalidate affected calibration artifacts;
a new preregistration version and re-freeze are required;
the validation-access history is never erased.
```

After hidden-test access:

```text
primary-analysis amendments are forbidden.
```

Only explicitly classified:

```text
EXPLORATORY_POST_TEST
```

work may continue, in a separate analysis namespace that cannot replace or
overwrite primary results.

---

## 2.8. Compatibility APIs

Existing in-memory `FreezeState`, `AccessLog` or amendment wrappers may remain
only as:

```text
READ-ONLY PROJECTIONS
```

All mutating compatibility methods must be removed, disabled or routed through
the durable ledger writer. No bypass path may create a frozen/accessed state in
memory only.

---

## 2.9. Canonical paths and filesystem containment

All manifests and ledger artifact references use canonical POSIX-relative paths.

Reject:

```text
backslashes
absolute paths
drive/UNC paths
colon-bearing path segments
"." or ".." segments
empty segments
duplicate paths after Unicode/casefold normalization
symlinks
junctions
reparse points
intermediate-component traversal
```

Existing noncanonical manifests must be regenerated. Silent normalization is
forbidden.

Containment must be checked before and after file resolution and before hashing.

---

## 2.10. Evaluation implementation scope

Evaluation may resume implementation for:

```text
Git-object release
clean-HEAD preflight
external staging/atomic publication
exact-test manifest and JUnit matching
real/synthetic/legacy receipt modes
allowed-authority profile verification
durable ledger/locking/atomic projection
one-time access events
amendment and recovery semantics
canonical path containment
adversarial tests
```

Evaluation may not:

```text
create Stage B gold
edit Dataset/C/E/Global/Contracts
select a real calibration threshold
open validation or hidden test
issue production certificates
turn synthetic fixtures into real authority
```

Required review gates before merge:

```text
clean, reviewable commits
full Evaluation suite
adversarial crash/concurrency/path/JUnit/receipt tests
0 provider/network calls
release artifact with manifest/CHECKSUMS/JUnit/commands/environment
independent review
```

---

# 3. AR-3 — System Integration Harness R2 common binding

## 3.1. Decision

```text
AUTHORIZED:
NARROW CONTRACT R2 COMMON-BINDING UPDATE
```

Classification remains:

```text
COMMON_BINDING_UPDATE
NOT AN ARCHITECTURE CHANGE
```

## 3.2. Required new-run policy

Every new official Harness run must verify:

```text
exact reviewed Contract R2 receipt schema
receipt_revision = 2
exact receipt self and physical hashes
exact authority tag and tag object
authority commit
contract tree
manifest
GatePolicy
feature registry
release manifest
CHECKSUMS
final audit
final Contracts ZIP
AR-1 detached approval binding
AR-1 approval artifact and evidence inventory
separate Global action-policy sidecar
```

The exact R2 receipt's pending publication status is not rewritten. Approval is
established by the detached AR-1 binding.

Prefer calling the public Contract R2 verifier and binding its output rather
than copying private Contract verification logic.

## 3.3. Historical R1 policy

R1 is allowed only under an explicit mode such as:

```text
CONTRACTS_R1_HISTORICAL_REPLAY
```

Rules:

```text
R1 cannot start a new run
R1 cannot be selected by fallback
R1 is accepted only when the sealed historical run already binds R1
compatibility mode is recorded in run spec and replay report
production/current integration requires R2
```

## 3.4. Persisted authority set

`AuthoritySet`, run spec and replay evidence must persist at least:

```text
Contracts receipt revision/self/physical hashes
authority tag/tag object/commit/tree
manifest/GatePolicy/feature-registry bindings
release manifest/CHECKSUMS/audit/final ZIP hashes
detached approval-binding self/physical hashes
approval artifact self/physical hashes
Global action-policy self/physical hashes
compatibility mode
public verifier report hash
```

Replay verifies the same set before semantic execution.

## 3.5. Mandatory adversarial tests

Add positive and negative coverage for:

```text
gate_policy_self_sha256 drift
feature_registry_file_sha256 drift
receipt_revision drift
contract_tree_git_oid drift
authority_status drift
final_release_zip_sha256 drift
missing/swapped/tampered detached approval binding
approval artifact hash drift
Global action-policy sidecar drift
R1 used for a new run
automatic R1 fallback
R1 historical replay with explicit mode
noncanonical path/case/symlink/junction input
```

## 3.6. Allowed code scope

The child may change only Harness-owned paths needed for:

```text
public authority adapter
preflight binding
AuthoritySet/run-spec persistence
replay verification
release pins/reports
positive/adversarial tests
```

It must not change:

```text
shared Contract bytes
Dataset/C/E ownership
Global decision/gate/calibration algorithm
candidate identity joins
development invariants
M6 real-pilot architecture
```

## 3.7. Merge condition

The authorization permits implementation, not automatic merge.

Required before merge:

```text
exact narrow diff review
all legacy fixture tests
new R2 positive/adversarial tests
R1 historical replay tests
0 network/provider calls
clean release artifact
independent review verdict
```

---

# 4. Main Maintainer coordination order

Execute in this order:

```text
1. Record this architecture decision.
2. Publish AR-1 detached evidence through a narrow governance task.
3. Keep Contract R2 tree at 938bca1f...
4. Allow Evaluation to resume from a clean baseline under AR-2.
5. Allow Harness to implement the AR-3 narrow child.
6. Review AR-1 publication, Evaluation release and Harness child independently.
7. Do not open validation/test or real production mode.
```

---

# 5. Final decision summary

| Item | Decision | Implementation state |
|---|---|---|
| AR-1 | **A — detached external approval evidence** | Architecture approved; narrow governance publication may be scheduled |
| AR-2 | **Git-object release, exact JUnit identities, versioned receipt modes, durable hash-chain ledger** | Evaluation may resume within frozen scope |
| AR-3 | **Narrow R2 common-binding update permitted** | Explicitly authorized; merge still requires review |

