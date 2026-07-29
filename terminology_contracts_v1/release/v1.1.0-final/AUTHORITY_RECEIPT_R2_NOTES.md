# Contracts V1.1.0 Authority Receipt R2

## Scope

This maintenance release changes publication metadata only. It does not move
the `contracts-v1.1.0` tag and does not modify the tagged schemas, policies,
registries, fixtures, migrations, or semantic validators.

## Authority identity

- Tag: `contracts-v1.1.0`
- Annotated tag object: `1a8c00d12f100145a276cd8304440ff0a7e8d2a1`
- Authority commit: `38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed`
- Manifest self SHA-256: `e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b`
- GatePolicy self SHA-256: `9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2`

## Receipt history

The original publication receipt declared an invalid canonical self hash. The
maintainer subsequently resealed the same payload in place. Both exact byte
sequences are preserved under `history/`:

1. `contracts_v1_1_0_authority_receipt_r1_invalid.json`
   - declared self SHA-256: `a95e50a6074fc8f3b749ebdf0e00657370bdc068a4d9efa7ffec27bbd807cb12`
   - canonical self SHA-256: `c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4`
   - physical SHA-256: `867c60892587cd108a052bbc16c3f057705360e10fc534ed1bd21ab0d3992d9e`
2. `contracts_v1_1_0_authority_receipt_r1_resealed.json`
   - canonical self SHA-256: `c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4`
   - physical SHA-256: `3497460f16ca478dada7b25425775882f10d1cb2b5d3638c36cba4ec5fb2791b`

Both are historical artifacts with status `SUPERSEDED_BY_RECEIPT_R2`. R2 uses
only portable relative paths as authority identities and binds the tagged
manifest, deterministic final ZIP, GatePolicy, feature registry and final
release audit.

## Review state

The generated R2 receipt is integrity-sealed with publication status
`PENDING_INDEPENDENT_REVIEW`. It must not replace consumer pins until an
independent reviewer accepts the exact receipt bytes and release artifacts.
