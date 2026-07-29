# Controlled Vietnamese Registry Consumer Requirements V1

Status: `BLOCKED_BY_CONTROLLED_REGISTRY`

Authority owner: Dataset Agent

Consumer: Vietnamese Attestation Evidence E

## Current condition

The published controlled registry is byte-empty. Evidence E therefore reports:

```text
CONTROLLED_VIETNAMESE_REGISTRY_EMPTY
retrieval_provider_created = false
```

Fixture rows, model-generated rows and manually appended local rows are not
registry authority.

## Required authority handoff

Before Evidence E creates a controlled-corpus provider, Dataset Agent must
supply:

- non-empty immutable UTF-8 JSONL registry;
- registry physical SHA-256;
- registry manifest and schema/version;
- immutable content payloads or content-addressed references;
- manifest records binding every registry row to its content.

Each row must contain at least:

```text
source_id
organization_id
document_id
content_hash
dedup_group_id
source_tier
canonical_uri or artifact_ref
content_ref
content_mime_type
language
title
publication or organization metadata
license and provenance
retrieved_at or publication_date
```

All IDs must be non-empty and unique where required. `content_hash` must be a
lower-case, nonzero SHA-256 of the exact retrieval payload. Registry JSON must
reject duplicate keys at every object depth, non-finite values, trailing data,
blank rows and duplicate `source_id` values.

## Consumer validation

Evidence E validates before retrieval:

1. registry and manifest physical hashes;
2. schema/version and canonical JSONL parsing;
3. row uniqueness and supported source tier;
4. content-reference resolution without path traversal;
5. exact content hash and MIME/language metadata;
6. dedup and organization identity fields.

Every retrieved controlled source still passes:

- candidate-span detection;
- Vietnamese-language gate;
- concept and domain Judge;
- source-tier policy;
- document/dedup clustering;
- organization independence;
- machine-translation suspicion checks.

Registry membership alone never makes a candidate `ATTESTED`.

## Retrieval order

After authority is accepted, the intended order is:

```text
controlled corpus -> reviewed cache -> approved open-web search
```

Every route retains raw responses, failure ledger, provider attempts, hashes,
latency/cost and deterministic replay metadata.

## D2L-VI boundary

D2L-VI glossary or translation material may be candidate origin or Tier-3
attestation evidence. It cannot alone produce `ATTESTED`, approve production or
become a human gold/reference set.

Evidence E keeps `final_glossary_decision = null` for all outputs.
