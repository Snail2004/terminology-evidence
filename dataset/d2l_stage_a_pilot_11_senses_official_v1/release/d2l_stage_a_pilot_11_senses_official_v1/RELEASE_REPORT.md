# D2L Stage A Official 11-Sense Pilot V1

## Release verdict

`READY_FOR_REAL_PILOT_REVIEW`

This zero-network Dataset release contains exactly:

- 11 `EffectiveSenseContractV1` records;
- 33 `FrozenCandidateContractV1` records with `binding_status=COMPLETE`;
- 33 `ConstraintEvidencePackageV1` records with `binding_status=COMPLETE`;
- 33 Stage B rows marked `ELIGIBLE` and 12 marked `BLOCKED_BY_STAGE_A`;
- 0 Stage B gold labels, 0 final glossary decisions, and 0 provider calls.

`stage_b_eligible_33.csv` is the reviewer input. `stage_b_blocked_12.csv` is an
exclusion ledger and is not eligible for annotation.

The eleven official pilot senses are `null hypothesis`, `output gate`, `Jupyter notebook`,
`learning rate`, `contexts`, `attention scoring function`, `Gradient Clipping`, `underflow`,
`momentum`, `word embedding`, and `vanishing gradients`. The four held Stage A senses
remain held and were not changed by this release.

## Method boundaries

`COMPLETE` means the Dataset identity, content binding, and contract joins are complete.
It does not mean a Vietnamese candidate is correct. Candidate gold labels remain blank,
target collision is explicitly `UNJUDGEABLE`, and no Global action, score, certificate,
or final glossary decision is emitted.

Human authority is represented by a pseudonymous owner-attested roster sidecar. It does
not disclose PII and explicitly records that external identity verification was not
performed. Blind-audit records are case-sealed and semantically bound to all R0 decisions.

Parent packages are references only. No incomplete nested `CHECKSUMS.sha256` is presented
as a materialized parent package.
