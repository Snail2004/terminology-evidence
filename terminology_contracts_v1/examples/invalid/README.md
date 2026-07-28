# Invalid fixtures

Các file trong thư mục này **phải FAIL**:

- `global_input_mismatched_candidate.json`: C package lệch `sense_id`.
- `context_bad_counts.json`: tổng PASS/MINOR/FAIL không bằng số context hợp lệ.
- `attested_without_evidence.json`: `ATTESTED` nhưng không có accepted evidence.
- `dev_policy_auto_approved.json`: development heuristic cố phát `AUTO_APPROVED`.
