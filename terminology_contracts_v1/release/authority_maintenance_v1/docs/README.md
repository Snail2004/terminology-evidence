# Authority Maintenance V1

This directory owns publication-only maintenance for Contracts V1.1.0.

## Boundaries

- Build source is always the exact annotated tag `contracts-v1.1.0`.
- The tagged contract manifest and semantic authority remain unchanged.
- Tools reject non-tag source refs, tag movement, manifest drift, release ZIP
  drift, policy/registry drift and non-portable receipt paths.
- Generated final artifacts belong under `release/v1.1.0-final/`.

## Commands

Run the full Contracts suite plus maintenance tests, commit the implementation,
then invoke `tools/build_authority_release.py` with that implementation commit.
Finally run `tools/verify_authority_receipt.py` against the generated R2
receipt. The exact release commands are copied into the final bundle.
