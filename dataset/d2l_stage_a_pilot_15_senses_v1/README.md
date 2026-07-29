# D2L Stage A Pilot: 15 Senses

This namespace is a new pilot artifact derived from the immutable Dataset V3
and the immutable glossary-first fast-track release. It does not modify either
parent artifact and it does not create human authority.

The selection is frozen at 15 development senses in three groups of five:

- `CLEAR_LOW_RISK`: three R0 cases, one R1 case, and one clear R2 case.
- `AMBIGUOUS_POLYSEMOUS`: five R3 cases requiring two blind human reviewers.
- `GATE_ADJUDICATION_RISK`: collision, wrong-sense, insufficient-evidence,
  E-unjudgeable, and mandatory-adjudication cases.

The release is intentionally `BLOCKED_BY_HUMAN_REVIEW`. Review templates are
blank, official Effective Sense/Frozen Candidate/Constraint packages are not
emitted, and the 45 Stage B rows contain no gold labels.

The review ZIP also contains the three-case R0 blind-audit template and the
review instructions. Proposed definitions/POS values are source projections
only; they are not human decisions.

## Build and validate

```powershell
python tools\build_pilot.py `
  --repo-root C:\work\terminology_evidence-worktrees\dataset-v1 `
  --output release\d2l_stage_a_pilot_15_senses_v1 `
  --created-at 2026-07-29T00:00:00Z

python tools\validate_pilot.py `
  --artifact-root release\d2l_stage_a_pilot_15_senses_v1 `
  --repo-root C:\work\terminology_evidence-worktrees\dataset-v1
```

Both commands are local and make zero provider/API calls.

Human reviewers must fill the review result and provenance templates before
any Effective Sense contract or integration package can be emitted.
