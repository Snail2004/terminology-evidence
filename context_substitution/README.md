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
content-addressed replay verification, an official decision-neutral
`ContextEvidencePackageV1@1.1.0` producer, and a deterministic release bundle.
The producer is pinned to local authority tag `contracts-v1.1.0`. Official
package sets are `COMPLETE` only when their Frozen Candidates come from Dataset
Adapter authority. Synthetic zero-API conformance sets use the distinct
`SYNTHETIC_LOCAL_CONFORMANCE` status. Global Validator V1.1 is an active
consumer, but C remains decision-neutral and emits no global action.

The official five-sense Dataset pilot is consumed without extraction or
network access:

```powershell
python -B -m context_substitution.v2 official-five-sense-pilot `
  --dataset-zip <official-five-sense.zip> `
  --dataset-pin <official_dataset_input_pin_v1.json> `
  --evidence-root <empty-evidence-directory>
```

The command verifies the pinned ZIP, all 5 Effective Sense contracts, all 15
Frozen Candidates, all 15 Constraint Evidence packages, and the excluded
eleven-sense lineage. It then emits exactly 15 decision-neutral C packages,
an exact replay ledger, and byte-identical copies of the accepted ZIP and pin
for independent release validation. Local deterministic fake attempts exercise
the C pipeline; provider and network call counts remain zero.

RC2 admission is fail-closed: JUnit must be green with zero unexpected skips,
the provider ledger must correspond exactly to the sealed C run, authority
receipt hashes must match the corrected publication, and Frozen Candidates
must come from Dataset Adapter authority. C-local test fixtures cannot enter
official projection.

This domain must not implement Vietnamese attestation, web/corpus attestation,
Global Validator decisions, or final glossary sealing. The 150 term-sense V3
dataset is adapter-validated but has not been submitted to live providers by
this implementation work.
