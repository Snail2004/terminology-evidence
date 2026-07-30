# Dataset Fast-Track Policy V1.1

Policy ID: `dataset-fasttrack-glossary-first-v1.1`

This is a repair companion to the immutable `d2l_dataset_fasttrack_glossary_first_v1`.
It preserves the parent artifact and records its manifest and ZIP hashes in
`source_bindings.json`.

## Authority boundaries

- D2L English corpus contexts are the source-grounding authority.
- The pinned D2L-VI glossary is a Tier-3 candidate source, not gold truth.
- Model outputs improve recall but cannot finalize a sense or candidate label.
- Human review is required by risk: R1/R2 one reviewer, R3 two independent
  reviewers, and R4 formal adjudication.
- Validation and test candidate labels remain 100% human-reviewed and hidden
  from Global scoring.
- C and E produce evidence only; `final_glossary_decision` stays null.

## Evidence separation

Positive definition/POS evidence must be real D2L corpus context with
`SAME_SENSE` and `PRIMARY` or `BACKUP` role. Contrastive and synthetic contexts
are boundary evidence only and cannot support definition, POS, or primary C
scores.

## Blind audit selection

The development-only blind pack contains all three available development R0
cases, two deterministic clear controls, three registered disagreement cases,
and five ambiguous/polysemous cases. Historical blind outputs remain evidence
of their original selection only and cannot satisfy the current selection gate.

## Fail-closed publication

This companion release does not reinterpret unresolved V3 records as reviewed.
It emits pending projections and blank Stage B labels. Official Effective Sense,
Frozen Candidate, and COMPLETE Constraint Evidence contracts remain absent until
review provenance, adjudication, split leakage, and downstream evidence gates
are actually complete.
