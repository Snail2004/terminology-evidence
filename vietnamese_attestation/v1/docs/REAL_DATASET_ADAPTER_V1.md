# Vietnamese Attestation Real Dataset Adapter V1

Status: REVIEW

This adapter is governed by the read-only handoff:

```text
dataset\D2L_C_E_REAL_ARTIFACT_ADAPTER_HANDOFF_V1.md
SHA-256 B2F995E42CE6AA66A54B04C1CB55ACA88DAF3B5DE89CC32B0B94C8E4B6D60730
```

It does not recursively scan that directory. It opens only the explicitly
selected immutable ZIP and, for pilot V1.1, the explicitly supplied V3 parent.

## Adapter contract

- Schema: `VietnameseAttestationDatasetAdapterV1` version `1.0.0`.
- Policy: `d2l_vietnamese_attestation_real_dataset_adapter_v1`.
- Candidate schema: `VietnameseAttestationCandidateInputV1` version `1.0.0`.
- Provider calls: `0`.
- `final_glossary_decision`: always `null`.

Supported physical authorities are exact, not prefix-compatible:

| Source | ZIP SHA-256 | Manifest SHA-256 | Counts |
| --- | --- | --- | --- |
| `D2LContextSupportSetValidationReadyV3` 3.0.0 | `2f8e6ad0519854b161eda8cce61b13cdfc2f5ee54d205d18c27f279493c4fe52` | `258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce` | 150 senses, 450 candidates, 1,340 contexts |
| `D2LCSTDevelopmentOnlyPilotV1_1` 1.1.0 | `664cd5bf9e3006ebd77cffa6665a3cd86690dff0201fc518cae407a121aa4f15` | `599692d33f9cc162698bc0e8fc0bf60cce1715cb0f34214fec499f14c1364eb5` | 5 senses, 15 candidates, 38 contexts |

Pilot V1.1 requires the exact V3 parent. Its core term-sense, candidate and
context rows must be byte-identical subsets of V3, and each pilot
`candidate_slot_id` must resolve against the V3 slot table.

The verified zero-API handback is stored in
`pilot-v1.1-adapter-receipt.json`.

## Fail-closed checks

- physical ZIP, manifest-file, manifest self-hash and every bound file hash;
- unsafe, duplicate, backslash, absolute, traversal and case-confusable ZIP
  names;
- exact source and row schema versions;
- canonical row self-hashes and unique IDs;
- candidate-to-sense joins on exact `term_id`, `sense_id`, `scope_id` and
  `shared_context_set_id`;
- selected context closure and roles for primary, backup and contrastive rows;
- source-text hashes and relative/absolute offset contracts;
- exact source cardinalities, split counts and context-role counts;
- candidate-slot bindings and pilot-to-parent lineage.

Recorded workstation paths in provenance are never dereferenced.

## Authority boundary

- `candidate_target_vi` remains an unreviewed candidate, not human gold.
- English `term_senses.surfaces` are not mapped to Vietnamese known surfaces.
- Known Vietnamese surfaces are `UNAVAILABLE_NOT_PROVIDED`.
- Domain anchors are `UNAVAILABLE_SCOPE_ID_ONLY`; `scope_id` is not expanded.
- Model-assisted definition/POS remains `PENDING_HUMAN_REVIEW`.
- Packaged contexts are marked `PROVENANCE_ONLY_NOT_ATTESTATION_EVIDENCE`.
- No C score, Context Judge output, pairwise output or local C status is read.
- Official/calibrated/human-reviewed authority is always false.

## Source-schema observations

`contexts.jsonl` does not contain `scope_id`. The adapter therefore joins each
context to one unique term-sense using exact `term_id`, `sense_id` and
`shared_context_set_id`; only that sealed term-sense supplies the scope.

V3 contains one non-consumed POS provenance reference:

```text
term sense: d2lce_73dbe839de3f1d00bf1226f0 (uncertainty)
field: part_of_speech_evidence_context_ids
missing packaged context: ctx_a5bf53f3daed100d0d815e2a
```

E does not map either definition/POS evidence-context array. Definition
provenance is bound by the complete `term_sense_sha256`, as required by the
handoff. All primary/backup/contrastive context references consumed by E are
closed. The missing context is not fabricated or copied into the package.

The review-workflow V1.3 ZIP is not required or supported by this development
adapter. The shared dataset directory did not contain that ZIP during this
gate.

## CLI

Pilot V1.1:

```powershell
python -m vietnamese_attestation.v1.cli.adapt_dataset `
  --source-zip <dataset>\pilot_dev_only_v1_1.zip `
  --parent-v3-zip <dataset>\d2l_context_support_set_validation_ready_v3.zip `
  --output adapter-package.json `
  --receipt-output adapter-receipt.json
```

V3 omits `--parent-v3-zip`. Neither command calls Search, Judge or another
provider.
