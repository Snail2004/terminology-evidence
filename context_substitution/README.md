# Context Substitution

Owner: Contextual Evidence C only.

Public package:

`context_substitution.v2`

Owned concerns:

- `contracts`: canonical schemas, provenance, and run validation;
- `runtime`: selection, trial, judging, pairwise, and aggregation;
- `providers`: ShopAI Key, CKey, and official Gemini adapters;
- `dataset`: optional frozen support-set preparation;
- `evidence`: certificate support-set projection;
- `evaluation`: local gold evaluation.

V2.2 adds the real V3/Pilot adapter, immutable reviewed-selection mode,
content-addressed provider-response replay, artifact-bound calibration,
model-family Judge independence, and positive/negative/contrastive support-set
separation. See
`v2/docs/VERSION_MATRIX.md` for exact contract identities.

Standalone CLI:

```powershell
python -m context_substitution.v2 --help
```

The integration-readiness layer lives under `v2/integration`. It provides a
zero-API directory/ZIP pilot receipt, deterministic fake-provider coverage,
content-addressed replay verification, a decision-neutral projection draft,
and a deterministic release bundle. The projection remains explicitly pending
until the shared `ContextEvidencePackageV1.1` authority is released.

This domain must not implement Vietnamese attestation, web/corpus attestation,
Global Validator decisions, or final glossary sealing. The 150 term-sense V3
dataset is adapter-validated but has not been submitted to live providers by
this implementation work.
