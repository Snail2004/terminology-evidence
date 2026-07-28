# Terminology Evidence

This is the standalone repository for the terminology-dictionary validation
system. Its canonical local checkout is `C:\work\terminology_evidence`.

The repository was bootstrapped from an earlier monorepo source snapshot, but
it has independent Git history, branches, releases, and ownership. Historical
`pipeline/...` paths embedded in copied manifests or architecture documents are
provenance; they do not make this repository a worktree of the old monorepo.

This repository contains independent evidence providers. It is an architecture
boundary, not a shared implementation bucket.

## Current domains

| Domain | Responsibility | Status |
|---|---|---|
| `context_substitution/v2` | Contextual Evidence C | Implemented |
| `vietnamese_attestation/v1` | Vietnamese Attestation Evidence E | Reserved |
| `legacy_term_evidence/v1` | Compatibility input and measurement adapter | Frozen |
| `terminology_contracts_v1` | Shared versioned contracts | Active |
| `dataset` | Shared reviewed and development datasets | Active |

The Global Terminology Validator is a separate consumer. Evidence providers do
not decide the final glossary state.

## Git governance

See `GOVERNANCE.md`. Feature agents never commit to `main`; the Project
Maintainer reviews commit handoffs, runs integration gates, merges to `main`,
and creates release tags.

## Required layout for every future architecture

1. Create one peer domain directory under `terminology_evidence/`.
2. Put every implementation under an explicit version directory such as `v1`.
3. Keep implementation, CLI, tests, and docs within the owning domain unless a
   separately versioned shared contract is required.
4. Keep at most 12 direct Python modules in one directory. Split larger
   packages by concern before adding another module.
5. Use the standard concern directories when applicable:
   `contracts`, `runtime`, `providers`, `dataset`, `evidence`, and
   `evaluation`.
6. A domain may expose only its version package facade. Other domains must not
   import its internal concern packages.
7. Do not place provider-specific business logic in a generic `shared`
   directory. Shared code is allowed only after two real consumers exist and
   the shared contract is independently versioned.
8. Integration of Evidence C and Evidence E belongs to the future Global
   Validator, never to either provider.
9. Update `architecture_boundaries.json` and its layout test when adding a new
   architecture.

Architecture enforcement tests will be maintained as repository-level
integration tests. Copied legacy path contracts remain unchanged until a
versioned migration is accepted.

Architecture references are classified with their owners:

- Context Substitution specification:
  `context_substitution/v2/docs/`;
- Vietnamese Attestation specification:
  `vietnamese_attestation/v1/docs/`;
- cross-architecture reports: `docs/`.

Do not drop architecture documents directly into this umbrella directory.
