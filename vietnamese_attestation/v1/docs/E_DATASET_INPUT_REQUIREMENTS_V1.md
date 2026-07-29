# Evidence E Dataset Input Requirements V1

Status: ACTIVE, FAIL-CLOSED

Owner: Vietnamese Attestation Evidence E

Consumer contract: `FrozenCandidateContractV1@1.1.0`

Contracts authority:

- tag: `contracts-v1.1.0`
- commit: `38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed`
- manifest: `e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b`

## Required handoff

Dataset Agent owns and seals every official input. Evidence E only consumes the
artifact and must not derive an official Frozen Candidate from raw dataset rows.

The handoff must contain exactly 15 COMPLETE candidates for the current pilot,
plus an immutable package manifest. Every candidate must provide:

```text
schema_id = FrozenCandidateContractV1
schema_version = 1.1.0
binding_status = COMPLETE

candidate_key.candidate_id
candidate_key.candidate_version
candidate_key.source_term
candidate_key.candidate_vi
candidate_key.sense_id
candidate_key.scope_id
candidate_key.sense_inventory_version
candidate_key.dataset_manifest_sha256
candidate_key.effective_sense_contract_sha256

effective_definition_en

surfaces.canonical_vi
surfaces.validated_variants_vi
surfaces.rejected_variants_vi

domain_profile.domain_id
domain_profile.anchors_vi
domain_profile.anchors_en

input_contract_sha256
integrity.self_sha256
```

The package manifest must bind the physical file SHA-256, candidate identity,
candidate self-hash, dataset manifest and effective-sense contract hash for each
member. Candidate IDs and candidate versions must be unique.

## Required provenance

Dataset Agent must retain authority for:

- canonical and rejected Vietnamese surfaces;
- effective definition and sense inventory;
- domain profile and domain anchors;
- dataset manifest and candidate version derivation;
- the exact top-level `input_contract_sha256`.

The current development pilot fields are not a substitute for this authority.
English source surfaces must not be copied into Vietnamese authority fields.

## Evidence E admission

Evidence E performs, in order:

1. strict JSON and official schema validation;
2. canonical self-hash validation;
3. exact manifest and member physical-hash validation;
4. exact candidate/sense/scope/dataset/effective-sense join validation;
5. adaptation through `adapt_shared_frozen_candidate`;
6. offline projection-conformance testing;
7. real Evidence E execution only after source/provider readiness passes.

Evidence E rejects before retrieval or provider use when any of the following is
missing, malformed or inconsistent:

- effective-sense hash;
- canonical Vietnamese surface;
- domain ID or either anchor set;
- candidate identity/version;
- dataset manifest binding;
- top-level input contract hash;
- nested canonical self-hash;
- package member physical hash;
- COMPLETE binding status.

## Output boundary

Offline fixture output is `OFFLINE_PROJECTION_CONFORMANCE_ONLY`. It is not real
attestation evidence authority and must not be handed to Global Validator as a
real-pilot package.

All E packages keep:

```text
final_glossary_decision = null
```

Evidence E never emits a global action or final glossary decision.
