# D2L CST two-stage human review workflow v1.4

Do not annotate all tables in parallel.

1. Fill stage_a/sense_contract_review.csv.
2. Validate Stage A with --require-complete.
3. Freeze pilot_reviewed_sense_contract_v1.
4. Generate Stage B from that immutable effective contract.
5. Annotate and validate Stage B.
6. Finalize immutable pilot_human_annotations_v1.

Three reviewers work independently. Exact 2-of-3 majority resolves a row;
adjudication is required only when no exact majority exists.
Definition and POS corrections flow into every Stage B row. This five-sense
pilot is not authorized for threshold calibration.
