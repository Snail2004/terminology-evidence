# INDEPENDENT FINAL REVIEW — TERMINOLOGY CONTRACTS V1.1 RC4

**Artifact reviewed:** `terminology_contracts_v1_1_rc4.zip`
**Artifact SHA-256:** `2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471`
**Declared source commit:** `36e041abcaa0a8a34ab892ae094b0b3d9c3af2f4`
**Review scope:** release integrity, schemas, semantic validators, migration, dataset mapping, gate projection/policy, calibration replay, decision binding, certificate authority and TAC bundle verification.

## Verdict

```text
RELEASE ENGINEERING: PASS
ALL PREVIOUS P0 FINDINGS: CLOSED
COMMON AUTHORITY FREEZE: APPROVED
PUBLISH TO C / E / GLOBAL VALIDATOR / DATASET ADAPTER / TAC: APPROVED
```

RC4 is suitable to become the frozen shared contract authority **after the main
maintainer completes the mechanical merge, CI and tag procedure described below**.

The ZIP proves artifact content, not Git ancestry. The main maintainer must verify
that the merged tree corresponds to commit
`36e041abcaa0a8a34ab892ae094b0b3d9c3af2f4`.

---

## Independent verification

```text
External ZIP checksum: PASS
Internal CHECKSUMS.sha256: PASS
Manifest: PASS
ZIP path/symlink/cache safety: PASS
Credential scan result in release audit: PASS
Static Python import/compile: PASS
Test suite without dataset root: 113 passed, 2 skipped
Test suite with real V3 + pilot: 115 passed
V1.1 CLI validation: PASS
V1.0 legacy CLI validation: PASS
Migrated V1.1 CLI validation: PASS
External API calls: 0
```

## Authority invariants confirmed

- V1.0 remains a separate byte-preserved legacy family.
- Native producers emit V1.1 and migration is the only V1.0 normalization path.
- Frozen Candidate content is bound by `input_contract_sha256`.
- C/E packages require complete producer-owned gate signals.
- C/E gate signals must project exactly into the Global GateResultSet.
- Per-gate actions are constrained by a sealed GatePolicy artifact.
- Global Input explicitly binds Effective Sense, Frozen Candidate and Constraint Evidence.
- Frozen decisions use an exact machine-readable feature mapping.
- Approval score and status are replayed from the sealed logistic calibration model.
- Development mode cannot emit `AUTO_APPROVED`.
- Collision index, replay inputs, gate results, policy and calibration are bound.
- Certificate variants, blacklist, scope, C/E summary and threshold identifier are exact projections from verified artifacts.
- Certificate validity contexts are exactly the C positive support set.
- Contrastive and negative/boundary refs cannot be selected directly as certificate validity refs.
- Certificate issuance cannot predate decision completion.
- TAC verifies the complete certificate bundle and source-term occurrence span.
- Legacy-incomplete artifacts cannot silently become native frozen authority.

---

## Non-blocking hardening backlog

These do not block V1.1.0 publication, but should be tracked for V1.1.1:

### H1 — Evidence-reference type and disjointness checks

The official semantic validator currently trusts the C/E producer classification
of support/evidence references. Add checks such as:

```text
C positive_support_refs      → evidence_type = CONTEXT
C contrastive_refs           → evidence_type = CONTRASTIVE_CONTEXT
C support-set groups         → no duplicate evidence identity across groups
E accepted_evidence_refs     → evidence_type = ATTESTATION_SOURCE
```

This is producer-package hardening; certificate authority is already bound to the
exact producer package.

### H2 — Provenance timestamp ordering

Require:

```text
provenance.started_at <= provenance.completed_at
run_metadata.started_at <= run_metadata.completed_at
```

Current certificate issuance ordering is enforced, but general producer/decision
timestamp ordering should also be checked.

These tickets must not change the V1.1.0 schema incompatibly. Apply them through a
backward-compatible semantic-validator patch or V1.1.1 release.

---

## Required publication procedure

### 1. Merge by the main maintainer

```text
source branch: chore/contracts-v1.1
source commit: 36e041abcaa0a8a34ab892ae094b0b3d9c3af2f4
target branch: main
```

Do not let Contract Steward push directly to `main`.

### 2. Re-run CI from the merged main tree

Minimum gate:

```text
115/115 tests pass with real V3 + pilot
manifest/checksum pass
compile pass
credential/cache scan pass
external API calls = 0
```

### 3. Build the final authority artifact

Publish a non-RC artifact, for example:

```text
terminology_contracts_v1_1.zip
terminology_contracts_v1_1.zip.sha256
terminology_contracts_v1_1_audit.json
```

The final artifact may have a different physical ZIP hash from RC4 because the
release-channel metadata/name changes. Record both:

```text
authority Git commit
authority tag
package manifest hash
final ZIP SHA-256
```

### 4. Tag authority

```bash
git tag -a contracts-v1.1.0 -m "Freeze Terminology Contracts V1.1.0"
git push origin main
git push origin contracts-v1.1.0
```

### 5. Publish one authority receipt to all agents

The receipt must contain:

```text
contract_version = 1.1.0
authority_tag = contracts-v1.1.0
authority_commit = <merged main commit>
package_path = terminology_contracts_v1/
manifest_sha256 = <final manifest hash>
release_zip_sha256 = <final ZIP hash>
gate_policy_artifact_sha256 = <sealed policy hash>
feature_contract_version = 1.1.0
```

Agents must use the tag/commit as authority, not an unversioned copied folder.

---

## Agent adoption rules

### C Agent

- Rebase/cherry-pick `contracts-v1.1.0`.
- Project internal results to official `ContextEvidencePackageV1`.
- Emit complete `gate_signals`.
- Never emit final glossary decisions or gate actions.

### E Agent

- Rebase/cherry-pick the same tag.
- Project internal results to official `AttestationEvidencePackageV1`.
- Emit complete `gate_signals`.
- Never emit final glossary decisions or gate actions.

### Global Validator Agent

- Consume only official V1.1 packages.
- Load the sealed GatePolicy and real CalibrationArtifact.
- Run bundle verification and fail closed.
- Keep `AUTO_APPROVED` disabled until a real frozen calibration artifact exists.

### Dataset Agent

- Use official mapping contracts.
- Do not change contract schemas.
- Bind mapped candidates to dataset manifest and effective-sense artifacts.

### Main Manager

- Own merges, authority tags and release receipts.
- Reject direct agent edits to shared contract after freeze.
- Contract changes require a new controlled release.

---

## Final decision

```text
RC4 content is approved.
Proceed to merge → main CI → final build → tag contracts-v1.1.0 → publish receipt.
Do not distribute the RC4 ZIP itself as the permanent authority identifier.
```
