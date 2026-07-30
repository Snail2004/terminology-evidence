# D2L Stage A Official 5-Sense Pilot V1

This namespace builds and validates the zero-network P0B Dataset release for
the exact five reviewed senses selected by the independent review:

- `null hypothesis`
- `output gate`
- `Jupyter notebook`
- `learning rate`
- `contexts`

The release emits 5 `EffectiveSenseContractV1`, 15 COMPLETE
`FrozenCandidateContractV1`, and 15 COMPLETE
`ConstraintEvidencePackageV1` artifacts under Terminology Contracts V1.1.
It preserves role-specific Stage A evidence, binds the three R0 blind audits,
and marks Stage B eligibility as 33 `ELIGIBLE` plus 12
`BLOCKED_BY_STAGE_A` rows.

`COMPLETE` describes contract identity and binding completeness. It does not
approve a Vietnamese candidate. Stage B gold labels remain empty, target
collision remains explicitly unjudgeable, and no Global score, action,
certificate, final glossary decision, network call, or provider call is made.

Build:

```powershell
python -B tools/build_official_pilot.py `
  --output-root release/d2l_stage_a_pilot_5_senses_official_v1 `
  --created-at 2026-07-29T08:00:00Z
```

Validate:

```powershell
python -B tools/validate_official_pilot.py `
  --artifact-root release/d2l_stage_a_pilot_5_senses_official_v1 `
  --contracts-root ../../terminology_contracts_v1 `
  --zip-path release/d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip
```

Test:

```powershell
python -m unittest discover -s tests -p test_official_pilot.py
```
