# CODE REVIEW — TERMINOLOGY CONTRACTS V1.1

**Artifact reviewed:** `terminology_contracts_v1_1.zip`  
**Declared package version:** `1.1.0`  
**Release SHA-256:** `38e2ee307b247d535baedcde83427ebe3f30901d31bb921f03e6681b3160dbdc`  
**Review scope:** schemas, semantic validators, migration, calibration verifier, fixtures, dataset mapping, release integrity, and adversarial mutations.

## Verdict

```text
TERMINOLOGY CONTRACTS V1.1: RELEASE ENGINEERING PASS
COMMON AUTHORITY FREEZE: BLOCKED
PUBLISH TO C / E / GLOBAL VALIDATOR: NOT YET
```

The package is well organized and its declared test suite is reproducible, but several cross-module invariants are not actually enforced. The current artifact should be treated as **V1.1 release candidate**, not the frozen authority.

## Independently confirmed strengths

- External ZIP checksum matches the supplied checksum file.
- Internal `CHECKSUMS.sha256` verifies.
- Manifest verifies.
- Legacy V1.0 schemas and valid fixtures are byte-preserved.
- Current schemas are byte-identical aliases of V1.1.
- Dataset mapping tests pass against both real V3 and development pilot artifacts.
- Independent test run: `53 passed`.
- Valid and invalid fixtures behave as declared.
- Migration is deterministic on the supplied fixtures.
- No credential, ZIP traversal, symlink, or packaged `.pyc`/`__pycache__` issue was found.
- Canonical names `action`, `feature_contract_version`,
  `validity_context_refs`, and `attestation_evidence_refs` are implemented.
- The three missing gate IDs are present.
- Development mode correctly blocks `AUTO_APPROVED`.
- Frozen mode requires an actual calibration file rather than only a hash-shaped string.

---

# Blocking findings

## P0-1 — `input_contract_sha256` is not bound to the Frozen Candidate content

### Reproduction

A native `FrozenCandidateContractV1` can be modified in fields such as:

```text
effective_definition_en
effective_part_of_speech
scope_note
domain_profile
surfaces
alternatives_vi
```

then resealed with a new `self_sha256`, while keeping the old
`input_contract_sha256`. The validator still accepts it.

The implementation only checks that `input_contract_sha256` exists and is equal
between C, E, Global Input, gates, and decision packages. It does not define and
verify how that hash is derived from the actual Frozen Candidate payload.

### Impact

C and E could process different definitions/POS/scope contracts while presenting
the same join hash. The Global Validator would accept the packages as describing
the same input. This defeats the main purpose of the common contract.

### Required patch

Define one canonical binding algorithm, for example:

```text
input_contract_sha256 =
SHA256(canonical JSON of FrozenCandidateContract
       excluding integrity.self_sha256
       and excluding input_contract_sha256)
```

Add and test:

```text
seal_frozen_candidate_contract()
verify_frozen_candidate_binding()
```

Every downstream package must carry the verified binding. Legacy migration must
not fabricate a native-complete binding; mark it explicitly legacy-incomplete
when the original canonical input cannot be reconstructed.

---

## P0-2 — Frozen decisions are not verified against the calibrated feature vector

### Reproduction

With a valid sealed calibration artifact, all of the following mutated decision
packages validate:

```text
decision_features = {}
decision_features = {"BOGUS": 999}
decision_features missing calibrated features
low decision features + approval_score = 0.99
```

The validator checks the feature names inside the calibration artifact, but does
not require `GlobalDecisionPackage.decision_features` to exactly match those
names. It also does not recompute `approval_score` from the artifact model.

### Impact

A malformed or incorrectly implemented Global Validator can produce a
contract-valid `AUTO_APPROVED` decision unrelated to C/E evidence or the frozen
calibration model.

### Required patch

For `FROZEN_CALIBRATED`:

1. Require the exact feature-key set declared by
   `CalibrationArtifactV1.model.feature_names`.
2. Reject unknown, missing, duplicate, non-finite, or wrong-type feature values.
3. Recompute the score for every supported model type.
4. Require the recomputed score to equal `approval_score` within a registered
   numerical tolerance.
5. Derive the decision from the verified score, threshold, and gates.

Until model-specific evaluators exist, restrict frozen V1.1 to a single fully
specified model type, preferably `LOGISTIC_REGRESSION`.

---

## P0-3 — `GlobalValidatorInputV1` does not contain enough information to compute all registered gates

The runtime input contains candidate identity, C evidence, E evidence, and
optional probes. It does not include:

```text
FrozenCandidateContract / EffectiveSenseContract data
sense review status
polysemy/split authority
cross-candidate collision index or collision evidence package
```

However, the Global Validator is expected to compute:

```text
sense_definition_unverified
unresolved_polysemy
target_collision
```

`target_collision` is inherently cross-candidate and cannot be derived from a
single C/E envelope.

### Impact

The Global Validator agent must invent an undocumented hidden dependency, query
raw storage, or misuse producer flags. Different agents can implement different
gate semantics while all claiming contract conformity.

### Required patch

Choose and serialize one explicit design:

**Preferred:**

```text
GlobalValidatorInputV1
├── frozen_candidate_contract
├── context_evidence
├── attestation_evidence
├── constraint_evidence
│   ├── sense_review
│   ├── polysemy/split status
│   └── target_collision observations/index reference
└── optional_probes
```

Alternatively, define a separate `ConstraintEvidencePackageV1` producer. The
Global Validator must not read raw dataset layout or undeclared global state.

---

# High-priority findings

## P1-1 — Replay hash does not bind the evidence used for the decision

`replay_spec_sha256` currently covers only:

```text
candidate_key
input_contract_sha256
gate_policy_version
decision_policy
```

It omits:

```text
GlobalValidatorInput hash
decision_features
GateResultSet hash
C/E package hashes
engine execution configuration
```

Changing the feature vector can preserve the same replay hash and still validate.

**Patch:** Define a canonical replay specification containing all immutable
inputs needed to reproduce the decision, then verify it from loaded artifacts.

---

## P1-2 — Certificate validation is structural, not bundle verification

A complete certificate accepts arbitrary nonzero values for:

```text
decision_package_sha256
gate_result_sha256
calibration_artifact_sha256
context_evidence_sha256
attestation_evidence_sha256
```

without loading those artifacts and checking their candidate, policy, decision,
status, and hash relationships.

**Patch:** Add a `verify_certificate_bundle(...)` API that loads and verifies the
decision, gates, C, E, calibration, and Frozen Candidate artifacts. TAC should
call this verifier, not only `validate_instance(certificate)`.

---

## P1-3 — TAC occurrence is not bound to the certificate source term

The following payloads validate:

```text
source_term_span outside source_text bounds
source_term_span selecting unrelated text
certificate for a different source_term
```

**Patch:** Validate:

```text
0 <= start < end <= len(source_text)
normalized source_text[start:end] matches certificate.candidate_key.source_term
certificate input binding is COMPLETE
```

If occurrence matching requires token offsets rather than character offsets,
serialize the offset unit explicitly.

---

## P1-4 — Non-finite JSON numbers can pass

Python's default JSON parser accepts `NaN`, and `NaN` passes several `[0,1]`
schema checks. `decision_features` also accepts arbitrary numeric values.

**Patch:**

- use strict JSON parsing with `parse_constant` rejection;
- apply `math.isfinite` to every serialized numeric feature, threshold, score,
  coefficient, and metric;
- add invalid fixtures for `NaN`, `Infinity`, and `-Infinity`.

---

## P1-5 — Calibration model formats are under-specified

The verifier currently accepts:

```text
RULE_SET with arbitrary nonempty rule objects
ISOTONIC y values outside [0,1]
ISOTONIC x values outside the declared score domain
empty calibration_results
```

These artifacts cannot be reliably replayed across agents.

**Patch:** Add model-specific schemas and evaluators, or remove unsupported model
types from V1.1. Require a concrete calibration-results schema including sample
counts, precision, coverage, uncertainty method, and selected operating point.

---

## P1-6 — Producer-to-global feature mapping is not machine-readable

The registry lists producer feature names and global feature names separately,
but does not declare the exact mapping, especially:

```text
evidence_coverage → C_evidence_coverage
required_context_type_coverage → C_required_context_type_coverage
diagnostics.replacement_rate → C_replacement_rate
```

**Patch:** Add a canonical mapping table and a tested
`assemble_decision_features()` function. Global Validator must not infer names
from prose.

---

# Lower-priority hardening

## P2-1 — Gate observations need uniqueness and audit requirements

Currently:

- duplicate `gate_id` observations are allowed;
- triggered fatal gates may have empty `reason_codes`;
- triggered fatal gates may have empty `evidence_refs`.

Require one observation per registered gate and evidence/reason requirements for
triggered gates, with narrowly defined exceptions for mechanical contract gates.

## P2-2 — Dataset `candidate_version` mapping is semantically weak

The mapper falls back to a candidate record's `schema_version`, which produces
`3.0.0` for all current V3 candidates. This is a schema version, not a candidate
content revision.

Prefer an explicit candidate version or a stable content binding such as
`candidate_instance_sha256`. Keep `candidate_id` and dataset manifest binding as
separate fields.

## P2-3 — Native fixtures retain migration-looking run metadata

The native complete Global Decision fixture still contains values such as:

```text
engine_version = terminology-contracts-migration-1.0.0
global_run_id = migrated-...
```

This is valid structurally but confusing for agents. Generate a truly native
fixture distinct from migrated fixtures.

---

# Recommended release plan

Because V1.1 has not yet been published as the authority, do not tag the current
ZIP. Keep it as:

```text
terminology_contracts_v1.1.0-rc1
```

Patch the existing `chore/contracts-v1.1` branch and issue:

```text
terminology_contracts_v1.1.0-rc2
```

After the P0 and P1 tests pass, freeze and tag:

```text
contracts-v1.1.0
```

Do not send the current artifact to C, E, or Global Validator as the final
interface. They may continue internal implementation, but interface adaptation
should wait for the corrected release.

## Minimum re-review gate

The next artifact must include regression tests demonstrating that all of these
are rejected:

```text
modified Frozen Candidate with stale input_contract_sha256
empty/unknown/missing frozen decision features
approval_score inconsistent with calibrated model
Global input missing declared constraint evidence
replay hash missing feature/input/gate bindings
certificate with random artifact hashes
TAC span outside source text
TAC certificate for another source term
NaN/Infinity feature values
undefined RULE_SET or out-of-range ISOTONIC model
duplicate triggered gate IDs
```
