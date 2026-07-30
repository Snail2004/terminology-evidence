# D2L Stage A Targeted Repair Review Pack - 5 Senses

This namespace creates a zero-network review package for four unresolved
Stage A parents. The parent term
`in place` is split into two proposed senses, so the review surface contains
five output senses:

- `in place` - mutation on existing storage
- `in place` - established or operating configuration
- `Adam`
- `statistical power`
- `fully-connected layers`

The package contains exactly 25 source-grounded D2L review contexts, 15
Vietnamese candidate proposals, and three blank independent reviewer
templates. Review contexts are copied from the hash-bound D2L source snapshot.
Synthetic boundary text is retained only in the rejected-evidence ledger.

This package does not emit an official terminology contract, Stage B gold
label, provider call, or final glossary decision. It is separate from the
canonical Main Dataset 5-sense authority. The later local 11-sense candidate
is used only as a non-overlap guard and is not treated as authority.

Build:

```powershell
python -B tools/build_review_pack.py `
  --output-root release/d2l_stage_a_targeted_repair_review_pack_5_senses_v1
```

Validate:

```powershell
python -B tools/validate_review_pack.py `
  --artifact-root release/d2l_stage_a_targeted_repair_review_pack_5_senses_v1 `
  --source-document <D2L_SOURCE_DOCUMENT_JSON> `
  --zip-path release/d2l_stage_a_targeted_repair_review_pack_5_senses_v1_reviewer_handoff.zip
```

Test:

```powershell
python -m unittest discover -s tests -p test_review_pack.py
```
