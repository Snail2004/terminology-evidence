# D2L C/E Real Artifact Adapter Handoff V1

Document ID: `d2l_c_e_real_artifact_adapter_handoff_v1`  
Status: `AUTHORITATIVE_FOR_ADAPTER_IMPLEMENTATION`  
Scope: zero-API adapter/schema work only  
Date verified: `2026-07-28`  

## 1. Purpose

This document lets two independent implementation sessions consume the same
real D2L artifacts without inventing fields, labels, joins, or authority:

- **C**: Context Substitution V2.
- **E**: Vietnamese Attestation Evidence V1.

The immediate goal is to build and test adapters against the real immutable
artifacts. It is not permission to run an official semantic experiment,
calibrate thresholds, call a provider, or make a glossary decision.

## 2. Artifact authority

Use the ZIP files as immutable authorities. The extracted directories are
convenient byte-identical projections, not independent sources of truth.

| Role | ZIP | Schema | Manifest SHA-256 | ZIP SHA-256 | Status |
|---|---|---|---|---|---|
| Canonical structural dataset | `E:\Data-KL\d2l_context_support_set_validation_ready_v3.zip` | `D2LContextSupportSetValidationReadyV3` | `258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce` | `2f8e6ad0519854b161eda8cce61b13cdfc2f5ee54d205d18c27f279493c4fe52` | `VALIDATION_READY_HUMAN_REVIEW_REQUIRED` |
| Development subset | `E:\Data-KL\pilot_dev_only_v1_1.zip` | `D2LCSTDevelopmentOnlyPilotV1_1` | `599692d33f9cc162698bc0e8fc0bf60cce1715cb0f34214fec499f14c1364eb5` | `664cd5bf9e3006ebd77cffa6665a3cd86690dff0201fc518cae407a121aa4f15` | `DEVELOPMENT_PILOT_HUMAN_REVIEW_REQUIRED` |
| Human-review workflow | `E:\Data-KL\pilot_normalized_review_pack_v1_3.zip` | `D2LCSTReviewWorkflowV1_3` | `88a913f8d0ce05b2dc85695ec56d55defa834416e2939fdd2c5d0474788d025a` | `9659b5cbfc047130796ad26b79f80e1f25d8a0e1b21667e1d1b1dbb935fd03d7` | `STAGE_A_HUMAN_REVIEW_PENDING` |

Manifest-file hashes:

```text
V3 manifest.json       b5f2067427c6b88344109f2c62f8db02ac61b0cef76f193d5285f378ff5f96a8
Pilot V1.1 manifest    e45205adfe22b6b6c67680e159c64bb3c69c3a9849a3109a962134dc8cb3dd76
Review V1.3 manifest   b449e8023d99316e7a05658c3db7e77baeac09745ff63598113bd9b1e82b8254
```

The verified lineage is:

```text
D2LContextSupportSetValidationReadyV3
  -> D2LCSTDevelopmentOnlyPilotV1_1
  -> D2LCSTReviewWorkflowV1_3
```

`pilot_normalized_review_pack_v1_2.zip` is superseded history. Do not use it
as the current adapter or annotation authority.

## 3. Verified cardinalities and current authority

### V3

```text
term_senses.jsonl          150
candidate_instances.jsonl 450
contexts.jsonl            1340
split                      development=100, validation=25, test=25
context roles              PRIMARY=740, BACKUP=408,
                           CONTRASTIVE=150, UNSELECTED=42
human annotations          0
```

V3 passes structural integrity, candidate completeness, offset contracts, and
sentence-level split leakage checks. Official CST and official C/E calibration
remain blocked pending human review.

### Development pilot V1.1

```text
term senses  5
candidates   15
contexts     38 = PRIMARY 25 + BACKUP 8 + CONTRASTIVE 5
split        development only
```

Allowed: adapter, prompt/rubric, retry plumbing, cost/latency, and zero-API
smoke tests. Not allowed: selector development, threshold selection, official
auto-approval, or scientific reporting.

### Review workflow V1.3

Stage A has five sense rows. All reviewer and adjudication fields are blank.
Two independent reviewers are required. Adjudication is required only when
their decision signatures disagree. Corrections to definition/POS must flow
into every generated Stage B row.

## 4. Common adapter rules

Both adapters must perform these checks before producing normalized input:

1. Verify the physical ZIP SHA-256 when ZIP mode is used.
2. Reject unsafe ZIP names, absolute paths, `..`, backslashes, duplicate names,
   and case-confusable duplicates.
3. Require the exact supported `schema_id` and `schema_version`.
4. Recompute the manifest self-hash after removing `manifest_sha256`.
5. Verify every manifest-bound file by bytes.
6. Recompute row self-hashes using canonical UTF-8 JSON: sorted keys, compact
   separators, and `ensure_ascii=false`, after removing the row hash field.
7. Require unique IDs and exact referential closure.
8. Never require the workstation path in `provenance.source_artifact_ref` to
   exist. Portability authority comes from the packaged row bytes, row hash,
   manifest binding, embedded `source_text`, and recorded source hash.
9. Never join by text, array index, row order, normalized spelling, or casefold.
10. Never mutate the source ZIP or its extracted projection.

Exact joins use:

```text
term_id
sense_id
scope_id
shared_context_set_id
candidate_instance_id
candidate_slot_id       when available
context_id
```

The normalized cross-agent identity is:

```json
{
  "candidate_id": "<candidate_instance_id>",
  "candidate_version": "<candidate_instance_sha256>",
  "sense_id": "<sense_id>",
  "scope_id": "<scope_id>",
  "sense_inventory_version": "<development dataset_version or frozen reviewed version>",
  "dataset_manifest_sha256": "<manifest of exact rows consumed>",
  "parent_dataset_manifest_sha256": "<V3 manifest when the pilot is consumed>",
  "effective_sense_contract_sha256": null
}
```

For the development pilot, `dataset_manifest_sha256` is the pilot V1.1
manifest and `parent_dataset_manifest_sha256` is the V3 manifest. After Stage A
is frozen, `effective_sense_contract_sha256` must be non-null for official mode.

`candidate_version` is deliberately the immutable
`candidate_instance_sha256`; do not create a synthetic version from row order.

## 5. C session: Context Substitution adapter

### Ownership

The C session owns only:

```text
pipeline/eval/terminology_evidence/context_substitution/**
pipeline/scripts/terminology_evidence/context_substitution/**
pipeline/tests/terminology_evidence/context_substitution/**
```

It must not import from or edit `vietnamese_attestation`.

### Current gap

The existing `dataset/runtime_adapter.py` accepts legacy
`D2LContextSupportSetFreezeV1`. It does not accept the real V3 or pilot V1.1
schemas. A separate reviewed-support adapter is required; do not weaken or
reinterpret the legacy adapter.

### Source-to-C mapping

| Real artifact field | C normalized field |
|---|---|
| `candidate_instance_id` | `candidate_target_id` and downstream `candidate_id` |
| `candidate_instance_sha256` | `candidate_version` / provenance binding |
| `candidate_target_vi` | `target_vi` |
| `applicability` | `applicability` |
| `term_id` | `term_id` |
| `source_term` | `source_term` |
| `sense_id` | `sense_id` |
| `scope_id` | `scope_id` |
| `definition` | development `sense_contract.definition_en` only |
| `term_sense_sha256` | definition provenance |
| `dataset_version` | development `sense_inventory_version` |
| `primary_context_ids` | primary context references |
| `backup_context_ids` | backup context references |
| `contrastive_context_ids` | contrastive context references |
| `context_id` | canonical context ID |
| `source_text` + `content_sha256` | context text and byte/content binding |
| `context_sha256` | complete context-row binding |
| `provenance.chapter_id/block_id/sentence_id` | source locator |
| `provenance.source_start/source_end` | enclosing source span |
| `match_start/match_end` | context-text codepoint offsets |
| `source_match_start_absolute/source_match_end_absolute` | full-source codepoint offsets |

V3 has `candidate_slots.jsonl`; pilot V1.1 does not. For pilot input, resolve
each `candidate_slot_id` against the immutable V3 slot table. Do not infer slot
number or candidate role from pilot row order. Apply an explicit candidate-role
policy only after exact slot resolution. The existing default
`canonical, alternative, pending` may be reused only if the C input contract
still explicitly seals that policy.

The V3 slot table contains `212` `RECORDED` rows and `238`
`MODEL_GENERATED` rows. The development adapter must preserve and accept both
exact statuses; it must not reuse the legacy adapter's `RECORDED`-only gate.
`MODEL_GENERATED` remains development evidence and does not become human gold
or official candidate authority.

### Selector modes

Development mode:

```text
MODEL_CLASSIFICATION_DEVELOPMENT
```

- May consume model-proposed definition/POS and context labels.
- Must retain `PENDING_HUMAN_REVIEW` provenance.
- Cannot claim official or calibrated results.

Official mode:

```text
FROZEN_HUMAN_REVIEWED_SELECTION
```

- Requires the frozen Stage A effective sense contract.
- Requires the frozen Stage B review artifact.
- Uses frozen labels without another selector call.
- Records both `review_artifact_sha256` and
  `effective_sense_contract_sha256`.

### C acceptance gates

1. V3 reads as exactly `150/450/1340`.
2. Pilot reads as exactly `5/15/38` and retains all 38 referenced contexts.
3. V3 slot lookup resolves every pilot candidate exactly once and preserves
   both `RECORDED` and `MODEL_GENERATED` status.
4. Broken candidate/context/sense references fail closed.
5. Manifest, row, source-text, offset, and provenance tampering fail closed.
6. The adapter succeeds when recorded Windows source paths are unavailable.
7. Development mode cannot emit `VERIFIED` or official authority.
8. Frozen mode rejects absent, mismatched, or mutable review contracts.
9. The adapter does not import E and leaves `final_glossary_decision=null`.
10. A zero-API smoke run produces 5 sense and 15 candidate input records.

## 6. E session: Vietnamese Attestation adapter

### Ownership

The E session owns only:

```text
pipeline/eval/terminology_evidence/vietnamese_attestation/**
pipeline/scripts/terminology_evidence/vietnamese_attestation/**
pipeline/tests/terminology_evidence/vietnamese_attestation/**
```

It must not import from or edit `context_substitution`.

### Current gap

The E namespace is reserved and has no implementation. Build the adapter first;
do not begin retrieval, provider integration, Attestation Judge calls, or
threshold logic in the same milestone.

### Source-to-E mapping

| Real artifact field | E normalized field |
|---|---|
| `candidate_instance_id` | `candidate_id` |
| `candidate_instance_sha256` | `candidate_version` |
| `candidate_target_vi` | `candidate_vi` |
| `term_senses.source_term` | `source_term` |
| `sense_id` | `sense_id` |
| `scope_id` | `scope_id` |
| `term_senses.definition` | development `sense_contract.definition_en` only |
| `term_sense_sha256` | definition provenance |
| `dataset_version` | development `sense_inventory_version` |
| `formation_method` | candidate formation metadata |
| `formation_provenance` | candidate provenance; preserve all entries |

Join candidate and term-sense records by exact `term_id`, `sense_id`,
`scope_id`, and `shared_context_set_id`. Reject disagreement in any key.

Important field meanings:

- `term_senses.surfaces` are English source surfaces, not validated Vietnamese
  variants.
- Candidate rows are alternatives to evaluate; they are not human gold.
- V3 does not provide a reviewed Vietnamese `known_surfaces` registry.
- `scope_id` is not a complete domain profile and must not be expanded into
  invented Vietnamese/English anchors.

Until reviewed data exists, emit explicit unavailable/pending status for known
Vietnamese surfaces and domain anchors. Do not fabricate canonical, validated,
or rejected variants.

E may use packaged source contexts only as provenance or query anchors when an
E policy explicitly allows it. E must not read:

```text
C score
C local status
Context Judge output
pairwise output
Global Validator decision
```

After Stage A freeze, E may consume the shared effective definition/POS
contract. E must not consume Stage B C decisions as attestation evidence.

### E acceptance gates

1. V3 maps exactly 450 candidates to 150 senses.
2. Pilot maps exactly 15 candidates to 5 senses.
3. Every normalized `candidate_id` equals `candidate_instance_id` byte-for-byte.
4. Every `candidate_version` equals `candidate_instance_sha256` byte-for-byte.
5. Join-key, manifest, and row tampering fail closed.
6. Missing reviewed known surfaces remain unavailable, not empty evidence of
   `NO_ATTESTATION`.
7. Missing domain anchors are a warning/pending condition, not invented data.
8. Development mode is marked non-official and non-calibrated.
9. The adapter does not import C and leaves `final_glossary_decision=null`.
10. All tests are zero-API and use only the real pilot/V3 bytes or exact local
    fixture copies bound to their hashes.

## 7. Human-review handoff

Neither C nor E may create or simulate human labels.

The authority sequence is:

```text
1. Complete Stage A with two independent reviewers.
2. Adjudicate only disagreements.
3. Freeze pilot_reviewed_sense_contract_v1.
4. Generate Stage B from that immutable effective contract.
5. Complete context, contrastive, and candidate review.
6. Freeze pilot_human_annotations_v1.
7. Run C and E independently on the development pilot.
8. Join only in the Global Terminology Validator.
9. Calibrate on validation after policy freeze.
10. Open test only after calibration and policy freeze.
```

The shared effective sense contract is the only human-reviewed definition/POS
authority consumed by both agents.

## 8. Required handback from each session

Each session returns:

```text
1. Exact branch/worktree/HEAD and changed paths.
2. Adapter schema ID and version.
3. Supported source schema IDs and exact manifest hashes.
4. One zero-API pilot adapter receipt with input/output counts.
5. Focused positive and adversarial test results.
6. Confirmation that no provider/API call occurred.
7. Confirmation that source ZIPs remain byte-identical.
8. Explicit list of unavailable fields; no inferred substitutes.
9. final_glossary_decision=null.
```

Recommended adapter receipt fields:

```json
{
  "agent": "C_OR_E",
  "adapter_schema_id": "...",
  "adapter_schema_version": "...",
  "source_schema_id": "...",
  "source_zip_sha256": "...",
  "source_manifest_sha256": "...",
  "parent_dataset_manifest_sha256": "...",
  "effective_sense_contract_sha256": null,
  "review_artifact_sha256": null,
  "term_sense_count": 5,
  "candidate_count": 15,
  "context_count": 38,
  "mode": "DEVELOPMENT_ZERO_API",
  "provider_call_count": 0,
  "final_glossary_decision": null
}
```

## 9. Start prompt for the C session

```text
Read E:\Data-KL\D2L_C_E_REAL_ARTIFACT_ADAPTER_HANDOFF_V1.md first.
You own only the Context Substitution paths listed there. Implement a strict
zero-API adapter for D2LContextSupportSetValidationReadyV3 and
D2LCSTDevelopmentOnlyPilotV1_1 without weakening the legacy Freeze V1 adapter.
Use exact artifact bytes and hashes from the handoff. Do not touch E, do not
invent human labels, do not run providers, and do not make a glossary decision.
Return the required adapter receipt and focused gates.
```

## 10. Start prompt for the E session

```text
Read E:\Data-KL\D2L_C_E_REAL_ARTIFACT_ADAPTER_HANDOFF_V1.md first.
You own only the Vietnamese Attestation paths listed there. Implement only the
strict zero-API V3/pilot input adapter and contracts in this milestone. Do not
import/read C outputs, do not begin retrieval or Judge/provider work, do not
invent known Vietnamese surfaces/domain anchors/human labels, and do not make a
glossary decision. Return the required adapter receipt and focused gates.
```

## 11. Stop conditions

Stop and report instead of guessing when any of these occurs:

- unsupported schema/version;
- ZIP, manifest, file, or row hash mismatch;
- missing or conflicting join key;
- broken candidate-slot/context reference;
- duplicate ID or cross-split leakage;
- official mode requested without frozen review artifacts;
- request to read the other agent's evidence;
- request to synthesize human labels or final glossary authority.
