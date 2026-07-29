# D2L Dataset Fast-Track: Glossary First

This companion artifact implements `dataset-fasttrack-glossary-first-v1.0`
without modifying Dataset V3, the methodology-hardening artifact, or any
reviewer output.

The build is deliberately fail-closed:

- D2L English corpus contexts remain the source-grounding authority.
- The pinned D2L-VI glossary is a Tier-3 candidate source, never gold truth.
- Dataset V3 candidates are reordered and provenance-normalized, not replaced.
- Cross-split source blocks are quarantined in this companion projection.
- Unreviewed senses remain `UNRESOLVED`; no official Effective Sense Contract,
  Frozen Candidate Contract, or COMPLETE Constraint Evidence Package is
  fabricated.
- Stage B labels are emitted blank for later human annotation.

## Build

```powershell
python tools/build_fasttrack_artifact.py `
  --repo-root C:\work\terminology_evidence-worktrees\dataset-v1 `
  --glossary-repo C:\work\terminology-evidence-sources\d2l-vi-c775d6b `
  --output release\d2l_dataset_fasttrack_glossary_first_v1 `
  --created-at 2026-07-29T00:00:00Z

python tools/validate_fasttrack_artifact.py `
  --artifact-root release\d2l_dataset_fasttrack_glossary_first_v1
```

No provider or external API call is made by either command.
