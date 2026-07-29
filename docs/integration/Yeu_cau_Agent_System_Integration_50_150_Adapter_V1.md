# YÊU CẦU AGENT SYSTEM INTEGRATION — DATASET 50/150 ADAPTER V1

**Priority:** P0 cho zero-provider integration
**Mode:** zero-network, zero-provider, no gold access
**Owner:** System Integration Harness
**Không được:** sửa Dataset, C, E, Global hoặc Evaluation semantics.

## Mục tiêu

Xây adapter Harness cho `pipeline_input_50_150` và chuẩn bị exact join/replay
trước khi live acquisition.

## Công việc

1. Định nghĩa ArtifactInventory cho:

```text
Dataset release ZIP
Dataset manifest
Main/Dataset pin receipt
50 Effective Sense records
150 Frozen Candidate records
150 Constraint Evidence packages
C package set or explicit per-candidate HOLD
E package set or explicit per-candidate HOLD
Global action-policy sidecar
```

2. Materialize shared Effective Sense bytes một lần và bắt buộc C/E/Harness dùng
cùng physical identity.

3. Exact joins:

```text
candidate_id
candidate_version
sense_id
scope_id
dataset/input hashes
producer component/version/run
C/E package identities
```

4. Reject:

```text
missing candidate
duplicate candidate
extra candidate
sense/scope/version mismatch
C/E inferred join
inventory drift
symlink/junction/reparse path
unreviewed authority fallback
```

5. Hỗ trợ hai giai đoạn:

```text
official 5-sense / 15-candidate conformance
future 50-sense / 150-candidate development batch
```

6. Bind:

```text
Dataset pin + ZIP + manifest
C/E set manifests
run inventory
seal
replay
public Global CLI invocation
```

7. Global luôn chạy:

```text
DEVELOPMENT_HEURISTIC
AUTO_APPROVED = 0
certificates = 0
```

## Tests

```text
15/15 exact join
150/150 synthetic identity conformance
explicit E HOLD accepted only by policy
missing/extra package reject
shared-sense byte drift reject
inventory reorder/drift reject
reparse/junction reject
two deterministic seals
replay byte identity
```

## Deliverables

```text
HARNESS_DATASET_50_150_ADAPTER_HANDOFF_V1.md
artifact_inventory_50_150_schema.json
focused/full JUnit
zero-provider 15-candidate integration artifact
synthetic 150-candidate conformance artifact
manifest + CHECKSUMS
exact commit/parent/changed paths
```

## Return status

```text
READY_FOR_OFFICIAL_50_150_INPUT
READY_FOR_15_CANDIDATE_ZERO_PROVIDER_RUN
NEEDS_NARROW_REWORK
BLOCKED_BY_DATASET_RELEASE_SCHEMA
```
