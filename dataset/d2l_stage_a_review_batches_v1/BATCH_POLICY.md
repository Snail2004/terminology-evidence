# Batch policy

Policy ID: `d2l_cst_stage_a_split_safe_batches_v1`

1. The source is the immutable validation-ready V3 support set.
2. Every one of its 150 term-senses appears exactly once.
3. Batches are ordered by case-folded `source_term`, then `sense_id`.
4. A batch contains at most 10 senses and exactly one dataset split.
5. Each reviewer sees the same case data but writes an independent output.
6. Stage A decides only English definition and part of speech.
7. The four voting fields are definition status/value and POS status/value.
8. `scope_note` remains non-voting audit text.
9. Source IDs, source hashes, case hashes, and evidence IDs are immutable.
10. Development may inform method analysis. Validation and test may not be
    used to tune prompts, labels, thresholds, or merge policy.
