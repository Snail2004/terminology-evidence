# D2L Fast-Track 50-sense Dataset - Stage A intake

This namespace freezes a 60-sense intake pool for the 50-sense target and
emits JSON Stage A review batches only for the 44 new senses. Sixteen existing
reviewed senses keep their prior review lineage and are not reviewed again.

The release contains:

- 60 sense-pool records;
- 180 provisional candidate records;
- selected real D2L positive contexts and explicitly labeled boundary probes;
- nine Stage A JSON batches for 44 new senses;
- separate reviewer-1 and reviewer-2 inputs according to R0/R3/R4 policy;
- individual Batch 1 handoff ZIPs.

No provider calls, Stage B gold, or final glossary decisions are created.

The companion adjudication-result release captures the nine completed Reviewer 3
files, validates all 24 routed cases against their sealed inputs, and keeps the
four unresolved R0 senses in a separate repair-and-reaudit queue.

The R0 repair companion applies only the reviewed definition/candidate changes
to those four senses and emits one blind re-audit handoff. At least one accepted
R0 re-audit is required before the exact 15/20/15 final-50 split can be frozen.

The R0 result companion captures the completed four-case re-audit without
overwriting the blank handoff. All four cases are accepted and unlock the final
selection gate.

The final Stage B release then freezes:

- 50 Stage A-ready senses in lane proportions 5/6/4/35;
- strata 15 clear, 20 ambiguous, and 15 collision/multi-target;
- a sentence/block leakage-safe 30/10/10 split;
- 150 distinct candidate instances;
- 50 Effective Sense, 150 Frozen Candidate, and 150 Constraint Evidence V1.1
  contracts;
- five Stage B batches and separate 150-case handoffs for Reviewer 1 and 2.

Stage B labels, adjudication results, C/E output, and final glossary decisions
remain empty. The release performs no provider or network calls.

After the two 150-case Stage B reviewer files return,
`build_stage_b_review_intake.py` captures and validates both results, measures
candidate-label agreement, and emits a Reviewer 3 handoff containing only label
disagreements. Consensus labels remain provisional and all final gold labels
stay null until adjudication is complete.
