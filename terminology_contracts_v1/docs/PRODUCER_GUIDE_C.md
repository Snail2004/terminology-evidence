# Producer Guide: Context Substitution (C)

C consumes `FrozenCandidateContractV1` and emits
`ContextEvidencePackageV1@1.1.0`.

- Verify the Frozen Candidate content binding, then preserve the full candidate
  key and input contract hash unchanged.
- Emit core C fields with their existing producer names.
- Keep optional diagnostics outside the default decision feature vector.
- Emit `missing_contrastive_context` and
  `incomplete_context_type_coverage` flags when their contract conditions hold.
- Bind `run_spec_id`, `execution_config_sha256`, provider route, prompts, inputs,
  and raw ledger reference.
- Keep `final_glossary_decision` null and do not read E output.
