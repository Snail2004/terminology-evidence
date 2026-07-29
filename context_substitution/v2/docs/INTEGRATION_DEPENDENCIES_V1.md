# Context Substitution V2.2 Integration Dependencies

The source package does not vendor Dataset or shared-contract authority bytes.
Materialize these dependencies beside the standalone repository, or set the
environment variables below. Missing optional dependencies cause focused tests
to skip with an explicit reason; an integration release requires zero skips.

## Dataset

Set `CST_DATASET_ROOT` to a directory containing:

| Artifact | Identity |
|---|---|
| `pilot_dev_only_v1_1` | manifest `599692d33f9cc162698bc0e8fc0bf60cce1715cb0f34214fec499f14c1364eb5`; physical manifest `e45205adfe22b6b6c67680e159c64bb3c69c3a9849a3109a962134dc8cb3dd76` |
| `pilot_dev_only_v1_1.zip` | physical SHA `664cd5bf9e3006ebd77cffa6665a3cd86690dff0201fc518cae407a121aa4f15` |
| `d2l_context_support_set_validation_ready_v3` | manifest `258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce`; physical manifest `b5f2067427c6b88344109f2c62f8db02ac61b0cef76f193d5285f378ff5f96a8` |
| `d2l_context_support_set_validation_ready_v3.zip` | physical SHA `2f8e6ad0519854b161eda8cce61b13cdfc2f5ee54d205d18c27f279493c4fe52` |

Dataset Adapter must separately provide `frozen_candidates.json` with wrapper
`DatasetFrozenCandidateSetV1@1.0.0`, status `COMPLETE_IMMUTABLE`, owner
`DATASET_ADAPTER`, and official bound `FrozenCandidateContractV1@1.1.0` rows.
C does not generate this authority artifact.

## Terminology Contracts authority

- tag: `contracts-v1.1.0`
- commit: `38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed`
- contract manifest: `e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b`
- receipt canonical self-hash: `c2e291510f43f2fb82461c5aacd3085948346e98451e218f73192b0eb3c47ed4`
- receipt physical SHA: `3497460f16ca478dada7b25425775882f10d1cb2b5d3638c36cba4ec5fb2791b`

Set:

```powershell
$env:TERMINOLOGY_CONTRACTS_ROOT = 'C:\path\to\terminology_contracts_v1'
$env:TERMINOLOGY_CONTRACTS_AUTHORITY_RECEIPT = 'C:\path\to\authority_receipt.json'
```

`integration-release` verifies the exact receipt bytes, canonical self-hash,
authority package, green JUnit, exact run-ledger correspondence, replay,
Dataset Frozen Candidate binding, package files, and projection report before
it can emit `INTEGRATION_READY_ZERO_API`.

## Global Validator consumer

Global Validator V1.1 is active on canonical integration commit
`b87a1458b3bb0da20792a308769ae0da4442f7e3`. C does not import or inspect that
implementation. It emits only official, decision-neutral
`ContextEvidencePackageV1@1.1.0` packages. A real Global pilot still requires
COMPLETE C, E, and Dataset authority packages; synthetic C fixtures are local
conformance evidence only.
