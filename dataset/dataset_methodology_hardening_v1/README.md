# Dataset Methodology Hardening V1

This package builds a companion artifact for
`d2l_context_support_set_validation_ready_v3`. It never rewrites the parent
dataset. The artifact audits corpus origin, derives deterministic statistical
units, records source-block split leakage, and freezes one downstream A-D block
per represented chapter.

The builder deliberately does not fabricate controlled Vietnamese sources,
blind adversarial cases, TAC drift labels, or human review. Those sections are
present with explicit blockers until independently supplied evidence exists.

## Build

```powershell
python dataset/dataset_methodology_hardening_v1/tools/build_artifact.py `
  --parent-root dataset/d2l_context_support_set_validation_ready_v3 `
  --source-document C:/work/agent-based-translation-d2l-direct-builder-v1/jobs/src_d2l_full_book_local_b858af3a5252/source_package_snapshot/document.json `
  --output-root dataset/dataset_methodology_hardening_v1/release `
  --archive-path dataset/dataset_methodology_hardening_v1/dataset_methodology_hardening_v1.zip
```

## Validate

```powershell
python dataset/dataset_methodology_hardening_v1/tools/validate_artifact.py `
  --parent-root dataset/d2l_context_support_set_validation_ready_v3 `
  --artifact-root dataset/dataset_methodology_hardening_v1/release `
  --archive-path dataset/dataset_methodology_hardening_v1/dataset_methodology_hardening_v1.zip
```

`PASS_WITH_BLOCKERS` means the package is internally consistent and honest,
not that official CST/C+E calibration is ready. Read `validation_report.json`
for unresolved human, external-source, blind-adversarial, TAC, and block-leakage
requirements.
