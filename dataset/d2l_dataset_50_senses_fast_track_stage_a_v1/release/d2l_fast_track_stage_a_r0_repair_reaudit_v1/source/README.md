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
