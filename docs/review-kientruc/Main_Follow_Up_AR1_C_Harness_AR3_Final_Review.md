# MAIN FOLLOW-UP — AR-1 / C / HARNESS AR-3 FINAL REVIEW

## Decisions

```text
AR-1: ACCEPTED
C 93ebff8: ACCEPTED; evidence correction required
Harness 339ac900: ACCEPTED FOR MERGE after exact Git checks
```

## Before merging Harness

Verify on canonical repository:

```bash
git rev-parse 339ac9001f8eda54d617189c92aa25bbc5eec8c7^
git merge-base --is-ancestor 339ac9001f8eda54d617189c92aa25bbc5eec8c7 HEAD
git diff --name-status <AR3_BASE> 339ac9001f8eda54d617189c92aa25bbc5eec8c7
git diff --check <PARENT> 339ac9001f8eda54d617189c92aa25bbc5eec8c7
git status --porcelain
```

Confirm:

```text
24/24 cumulative AR-3 paths are Harness-owned
12/12 final rework paths are allowlisted
8 frozen paths are unchanged
Contract tree remains 938bca1f...
no provider/network execution
```

Merge only exact commit `339ac900...`.

## C evidence correction

Do not reopen C code. Publish a correction receipt stating:

```text
69-test JUnit = focused integration-readiness suite
current source collection = 79 tests
independent full rerun = 78 PASS / 1 external SKIP
skip dependency = pilot_normalized_review_pack_v1_4
```

A later complete handoff should include an exact 79-identity JUnit or explicitly
materialize/waive the external dependency.

## Harness release hardening backlog

Before the next official release or real M6 archive:

```text
build from exact Git object or clean exact HEAD
exact source file inventory
internal manifest and CHECKSUMS
exact JUnit identity binding
commands/environment/Git receipt
deterministic sorted archive
```
