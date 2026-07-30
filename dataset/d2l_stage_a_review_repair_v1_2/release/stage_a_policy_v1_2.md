# Stage A review policy V1.2

Policy ID: `d2l_cst_stage_a_evidence_aware_review_v1_2`

## Purpose

Stage A reviews only the English sense definition and part of speech. It does
not select a Vietnamese candidate and does not make a final glossary decision.

## Evidence roles

Positive definition and POS evidence must satisfy all of the following:

```text
origin = CORPUS_EXTRACTED
sense_relation = SAME_SENSE
context_role in {PRIMARY, BACKUP}
```

Contrastive and synthetic controlled contexts may be cited only as boundary
evidence. They cannot satisfy positive definition or POS support.

## Consensus

Automatic development finalization is eligible only when:

1. all three reviewer core decisions agree exactly;
2. all three reviewer provenance sidecars are complete and independent;
3. every positive evidence reference passes provenance validation;
4. evidence roles have been explicitly confirmed under the V1.2 schema;
5. no sense, POS, split, synthetic-support, or semantic-audit blocker exists.

Any 2-of-3 majority is an adjudication proposal, not final authority. Any
`REJECTED`, `UNCERTAIN`, sense conflation, POS conflation, or synthetic-positive
support routes the case to adjudication or splitting. Reviewer confidence is a
self-report and is never a vote weight.

## Legacy V1 reviews

V1 review rows use one undifferentiated `evidence_context_ids` field. The repair
tool may project proposed evidence roles from immutable source groups, but this
projection is not reviewer intent. Legacy rows remain blocked until evidence
roles are confirmed and reviewer provenance is complete.

## Split discipline

Blind method audit uses development cases only. Validation and test remain
closed until the review protocol is frozen and source-block leakage is repaired
or quarantined.
