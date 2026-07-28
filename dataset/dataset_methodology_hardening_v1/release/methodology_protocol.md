# Methodology Protocol V1

## Parent immutability

The artifact is a derived companion to
`d2l_context_support_set_validation_ready_v3`. Parent IDs, splits, records,
manifests, and hashes are read-only. Every derived record binds its parent ID,
parent hash, transformation ID, and transformation version.

## Context origin

`CORPUS_EXTRACTED` requires all of the following:

1. The bound source-document SHA256 matches the physical source document.
2. The source block exists and its UTF-8 text hash matches provenance.
3. The context text is a verbatim substring of that source block.
4. Context-local and source-absolute term offsets are internally consistent.
5. Required document, chapter, block, sentence, and hash provenance is present.

Model-generated probes are classified as `SYNTHETIC_CONTROLLED`, receive
`FAIL_SYNTHETIC`, and are excluded from C primary/support and statistical units.
Case-only differences between `matched_surface` and the exact source slice are
accepted; the offsets and case-folded surface must still agree.

## Statistical units

One statistical unit is produced for every candidate-instance and selected
corpus context pair. IDs are content-derived, never row-order-derived:

- `occurrence_id`: candidate, context, document, and block identity.
- `pairing_id`: sense, candidate slot, and context identity.
- `resampling_group_id`: term-sense identity.
- `source_block_cluster_id`: document and source-block identity.

Source-block clusters crossing development/validation/test are reported as
blockers. They are not hidden by the sentence-disjoint parent split.

## Controlled Vietnamese evidence

No source is accepted without source tier, organization/document separation,
content hash, deduplication group, retrieval timestamp, and access note. An
empty registry is valid as a staging file but blocks official E calibration.
`INSUFFICIENT_EVIDENCE` remains a valid downstream result.

## Adversarial and TAC evidence

Adversarial sources are `AUTHOR_DESIGNED` and `BLIND_SECOND_PARTY`. The blind
creator must not inspect the final gate implementation. No blind status or
expected gate is inferred by this builder. TAC natural and synthetic-controlled
drift stay separate, and synthetic drift is forbidden from C evidence.

## Downstream A-D block freeze

The selected population is terminology-rich D2L source blocks represented by
the 150-sense parent. Before any A-D model run, the builder selects exactly one
block per represented chapter using this deterministic ordering:

1. collision-risk term count, descending;
2. ambiguous term count, descending;
3. unique term-sense count, descending;
4. terminology density, descending;
5. block ID, ascending.

All four arms (`A`, `B`, `C`, `D`) use the same frozen block IDs. This is a
purposeful hard-terminology sample and does not support whole-book population
generalization without a separate representative sample.

## Readiness semantics

`PASS_WITH_BLOCKERS` means hashes, provenance, deterministic transformations,
and artifact structure validate. It does not override unresolved human review,
cross-split block leakage, missing controlled Vietnamese sources, missing blind
adversarial cases, or missing TAC drift cases.
