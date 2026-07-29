# Contracts V1.1.1 Backlog

These items are deliberately excluded from the V1.1.0 authority-maintenance
patch because they change shared contract or semantic-validation behavior:

1. Move duplicate-key rejection into the shared strict JSON loader.
2. Define shared evidence-reference typing and disjointness constraints.
3. Require `started_at <= completed_at` in shared run provenance.
4. Require certificate issuance not to precede decision completion.
5. Add an external approval anchor for a human-frozen calibration artifact.
6. Decide whether authority receipts need a shared versioned schema.

Until V1.1.1 is reviewed, duplicate-key rejection remains an authority-boundary
and consumer-boundary responsibility.
