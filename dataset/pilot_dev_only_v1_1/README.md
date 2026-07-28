# D2L CST development-only pilot v1.1

This patch supersedes pilot_dev_only_v1 by closing every context reference in
the five selected term-sense records. It contains five primary contexts, all
referenced backup contexts, and one corpus contrastive context per sense.

Allowed development uses:

- prompt and rubric debugging;
- Trial Translator and Judge smoke tests;
- replacement and retry plumbing;
- cost, latency, and threshold-sensitivity smoke tests.

Not allowed:

- Context Selector development, because UNSELECTED contexts are intentionally
  excluded;
- threshold selection or precision-coverage calibration;
- official auto-approval before human review.
