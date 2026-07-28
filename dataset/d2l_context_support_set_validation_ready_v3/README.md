# D2L Context Support Set Validation-Ready V3

V3 preserves all 150 V2 term-senses and all 450 candidate instances. It fixes
the mixed offset coordinate contract, replaces the 117-sense transitive split
with an exact sentence-disjoint 100/25/25 split, and provides complete human
review queues.

## Machine verdict

- Structural integrity: PASS
- Candidate completeness: PASS
- Offset coordinate contract: PASS
- Sentence-level split leakage: PASS
- Official CST: BLOCKED
- Official C + E calibration: BLOCKED

## Pilot

The `pilot_8_corpus_contrastive` directory contains 8 senses,
24 candidates, and 48 selected
contexts. Human review remains blank by design.

## Important boundary

Sentence ID is the canonical leakage unit because each CST evidence item is a
sentence. Block overlap is not hidden: every cross-split block is listed in
`block_overlap_audit.csv`. If a later protocol requires block-disjoint evidence,
the source support set must be resampled rather than relabeled.

Only 1 sense currently has all five
model-proposed C1-C5 labels. V3 does not fabricate missing human labels.
