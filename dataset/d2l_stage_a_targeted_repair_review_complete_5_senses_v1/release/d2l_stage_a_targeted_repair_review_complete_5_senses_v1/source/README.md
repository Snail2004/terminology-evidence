# D2L Stage A targeted repair review complete - 5 senses

This namespace consumes the sealed five-case review pack, the three-reviewer
result package, and the completed two-row adjudication sheet. It emits a
review-complete Dataset projection for five senses and fifteen candidates.

The output is not an official glossary decision and does not emit
`EffectiveSenseContractV1`, `FrozenCandidateContractV1`, Stage B gold, or any
provider result. It remains a Dataset-owned Stage A review artifact.

Build:

```text
python -B tools/build_complete_review.py --output-root release/d2l_stage_a_targeted_repair_review_complete_5_senses_v1
```

Validate:

```text
python -B tools/validate_complete_review.py --artifact-root release/d2l_stage_a_targeted_repair_review_complete_5_senses_v1 --zip-path release/d2l_stage_a_targeted_repair_review_complete_5_senses_v1_reviewer_handoff.zip
```
