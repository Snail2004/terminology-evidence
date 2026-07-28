# Repository Governance

## Canonical repository

- Repository root: `C:\work\terminology_evidence`
- Protected branch: `main`
- Integration branch: created and owned by the Project Maintainer when needed
- Historical monorepo repositories and worktrees are reference-only

## Ownership

| Role | Branch | Owned paths |
|---|---|---|
| Context Substitution C | `feature/context-substitution-v2` | `context_substitution/**` |
| Dataset/Annotation | `feature/terminology-dataset-v1` | `dataset/**` |
| Vietnamese Attestation E | `feature/vietnamese-attestation-v1` | `vietnamese_attestation/**` |
| Contract Steward | `chore/contracts-v1.1` | `terminology_contracts_v1/**` |
| Global Validator | `feature/global-validator-v1` | `global_validator/**` |
| Project Maintainer | `main`, integration branches | repository integration, root governance, releases |

`legacy_term_evidence/**` is frozen compatibility code. Changes require an
explicit maintainer reservation and compatibility evidence.

## Required workflow

1. Work only in the assigned branch and worktree.
2. Stage owned paths explicitly. Never use `git add .` or `git add -A`.
3. Never stage `API-Key/**`, credentials, caches, or local runtime output.
4. Commit a focused change and leave the worktree clean.
5. Send the maintainer the full commit SHA, parent SHA, changed paths, exact
   test commands and results, and known gaps.
6. The maintainer reviews the diff, runs integration gates, merges to `main`,
   and creates release tags.

Agents must not switch to, commit on, or push `main`. Agents must not write to
another role's worktree or depend on uncommitted files from another branch.

## Architecture authority

Context Substitution C and Vietnamese Attestation E are independent evidence
providers. Neither provider owns `final_glossary_decision`. Only the Global
Validator may combine their sealed evidence into a glossary recommendation.

Shared datasets do not grant runtime authority. Human-reviewed, development,
synthetic, and evaluation-only records must retain their declared status and
provenance through every adapter.
