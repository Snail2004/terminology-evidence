# KIẾN TRÚC VÀ ROADMAP — SYSTEM INTEGRATION HARNESS AGENT V1

**Document ID:** `system-integration-harness-agent-v1.0`  
**Branch đề xuất:** `feature/system-integration-harness-v1`  
**Owner:** System Integration Harness Agent  
**Base:** latest reviewed canonical `main` tại thời điểm bắt đầu  
**Trạng thái:** `READY_TO_IMPLEMENT`  
**Mục tiêu:** Xây một lớp orchestration độc lập, fail-closed và có thể replay để nối Dataset Adapter, C, E và Global Validator mà không xâm phạm ownership của từng agent.

---

## 1. Sứ mệnh

System Integration Harness không phải là một validator mới.

Nó là lớp điều phối có nhiệm vụ:

```text
khám phá artifact
→ xác minh authority
→ xác minh checksum/schema/self-hash
→ exact join theo candidate/input identity
→ assemble GlobalValidatorInputV1
→ gọi Global Validator
→ lưu immutable run
→ replay
→ xuất integration report
```

Harness phải trả lời được:

```text
Các producer có bàn giao đúng artifact không?
Các package có cùng candidate/sense/scope/version không?
Hash và authority có khớp không?
Global có nhận đúng input không?
Development mode có giữ 0 AUTO_APPROVED và 0 certificate không?
Run có replay byte/semantic-deterministic không?
```

Harness không trả lời:

```text
candidate đúng hay sai về ngôn ngữ
C/E score có tốt không
threshold production là bao nhiêu
term nên được dịch thế nào
```

---

## 2. Phạm vi ownership

Agent chỉ được thêm hoặc sửa trong các đường dẫn được main maintainer phê duyệt, đề xuất:

```text
integration_harness/**
tests/system_integration/**
scripts/integration/**
docs/integration/**
```

Không sửa:

```text
dataset/**
context_substitution/**
vietnamese_attestation/**
global_validator/**
terminology_contracts_v1/**
```

Không copy và chỉnh sửa shared schemas vào harness.

Harness chỉ được:

```text
import public package/API đã công bố
hoặc
gọi CLI chính thức của producer/consumer
```

Không import:

```text
C internal modules
E internal modules
Dataset internal builder
Global private engine internals
provider/network SDK
```

---

## 3. Authority precedence

Thứ tự authority:

```text
1. contracts-v1.1.0 final authority receipt
2. exact Contracts manifest và tagged contract tree
3. Dataset-issued artifact receipts
4. C/E/Global release receipts
5. artifact manifests và CHECKSUMS
6. harness run spec
7. local convenience config
```

Khi có xung đột:

```text
higher authority wins
mismatch → fail closed
không tự sửa hoặc normalize để tiếp tục
```

Harness phải pin tối thiểu:

```text
contracts authority tag
contracts authority commit
contracts manifest SHA-256
GatePolicy SHA-256
feature contract version
Global action-policy SHA-256
Dataset manifest SHA-256
producer release commit/SHA
```

Global action-policy SHA thuộc Global release authority sidecar, không thuộc shared Contracts receipt.

---

## 4. Chế độ runtime

### 4.1. `FIXTURE_CONFORMANCE`

Dùng synthetic/contract fixtures.

Mục tiêu:

```text
kiểm schema
kiểm join
kiểm fail-closed
kiểm development invariants
kiểm storage/replay
```

Bắt buộc:

```text
provider/network calls = 0
AUTO_APPROVED = 0
certificate = 0
```

### 4.2. `REAL_DEVELOPMENT_ZERO_NETWORK`

Dùng package thật đã được producer tạo trước đó:

```text
Dataset official pilot inputs
C official packages
E official zero-network/shared packages
```

Harness không gọi provider.

Mục tiêu:

```text
real identity joins
real hashes
real producer receipts
Global DEVELOPMENT_HEURISTIC
```

### 4.3. `REAL_DEVELOPMENT_REPLAY`

Replay một run đã seal.

Bắt buộc:

```text
không gọi C/E provider
không gọi network
không thay config
CHECKSUMS PASS trước evaluation
same semantic decision package
```

### 4.4. Không hỗ trợ trong V1

```text
live Search/Judge orchestration
production FROZEN_CALIBRATED
AUTO_APPROVED publication
certificate publication
validation/test opening
threshold fitting
```

Các chức năng này chỉ được thêm bằng review riêng.

---

## 5. Đơn vị tích hợp

Đơn vị join là một candidate cụ thể:

```text
candidate_id
candidate_version
source_term
candidate_vi
sense_id
scope_id
sense_inventory_version
dataset_manifest_sha256
effective_sense_contract_sha256
input_contract_sha256
```

Mỗi candidate phải có đúng một bộ:

```text
1 FrozenCandidateContractV1
1 ConstraintEvidencePackageV1
1 ContextEvidencePackageV1
1 AttestationEvidencePackageV1
```

Sau join, Harness tạo:

```text
1 GlobalValidatorInputV1
```

Không chấp nhận:

```text
missing package
duplicate package
foreign package
candidate version drift
sense/scope drift
dataset manifest drift
effective sense hash drift
input contract hash drift
```

---

## 6. Kiến trúc thành phần

```text
Artifact Discovery
      ↓
Authority Resolver
      ↓
Package Integrity Verifier
      ↓
Candidate Index Builder
      ↓
Exact Identity Joiner
      ↓
Preflight Policy Validator
      ↓
Global Input Assembler
      ↓
Global Runner Adapter
      ↓
Run Sealer
      ↓
Replay Verifier
      ↓
Integration Reporter
```

### 6.1. Artifact Discovery

Nhiệm vụ:

```text
đọc release manifest
tìm Dataset/C/E/Global artifacts
không scan mù toàn repository
không chọn file theo tên gần đúng
```

Input nên là explicit artifact root hoặc manifest path.

Output:

```text
ArtifactInventoryV1
```

Mỗi artifact record:

```text
artifact_role
schema_id
schema_version
candidate_id nếu có
relative_path
physical_sha256
declared_self_sha256
producer
producer_commit
release_receipt_ref
```

### 6.2. Authority Resolver

Xác minh:

```text
contracts receipt
tag/commit
manifest
GatePolicy
feature registry
Global action-policy sidecar
producer release receipts
```

Output:

```text
ResolvedAuthoritySetV1
```

Không cho phép local config override authority hash.

### 6.3. Package Integrity Verifier

Với mỗi package:

```text
strict JSON parse
duplicate-key rejection
schema validation
semantic validation
self-hash verification
physical SHA verification
nested artifact hash verification
```

Thứ tự:

```text
physical file
→ strict parse
→ schema
→ semantic
→ self-hash
→ nested bindings
```

Không đọc field identity trước khi strict parse hoàn tất.

### 6.4. Candidate Index Builder

Tạo index:

```text
candidate_id → package records
```

Phát hiện:

```text
duplicate candidate
duplicate role
missing role
unexpected artifact
orphan package
```

Index phải deterministic:

```text
sort theo canonical candidate key
không phụ thuộc filesystem order
```

### 6.5. Exact Identity Joiner

Join không dựa chỉ vào `candidate_id`.

Bắt buộc exact equality cho toàn bộ identity tuple.

Join result:

```text
JoinedCandidateBundleV1
```

Mỗi mismatch phải có:

```text
error_code
artifact_role
expected
observed
artifact_ref
```

### 6.6. Preflight Policy Validator

Kiểm tra trước Global:

```text
Dataset owns Frozen Candidate
Dataset owns Constraint package
C final_glossary_decision = null
E final_glossary_decision = null
C/E không xuất global gate action
development input không chứa production certificate
all package statuses compatible
all required gate signals structurally complete
```

Không tự sửa:

```text
empty refs
missing signal
wrong status
```

### 6.7. Global Input Assembler

Chỉ dùng official assembler hoặc shared schema API.

Không tự định nghĩa GlobalValidatorInput clone.

Output:

```text
GlobalValidatorInputV1
assembly_receipt
assembly_sha256
```

Receipt phải bind:

```text
Dataset package hashes
C package hash
E package hash
Constraint package hash
authority set hash
assembler version
```

### 6.8. Global Runner Adapter

Ưu tiên gọi Global CLI/public API:

```text
global-validator validate-input
global-validator run
global-validator verify-decision
```

Harness không gọi private resolver trực tiếp.

Trong V1:

```text
mode = DEVELOPMENT_HEURISTIC
approval_score = null
AUTO_APPROVED forbidden
certificate forbidden
```

### 6.9. Run Sealer

Mỗi run lưu immutable directory.

Đề xuất:

```text
runs/<run_id>/
├── input/
│   ├── dataset/
│   ├── c/
│   ├── e/
│   ├── constraints/
│   └── global_inputs/
├── authority/
├── output/
│   ├── decisions/
│   └── reports/
├── audit/
│   ├── artifact_inventory.json
│   ├── authority_verification.json
│   ├── join_report.json
│   ├── assembly_report.json
│   └── execution_report.json
├── run_spec.json
├── manifest.json
└── CHECKSUMS.sha256
```

Không lưu secret.

Không dùng absolute local path làm authority identity.

### 6.10. Replay Verifier

Replay sequence:

```text
verify outer/bundle checksum
→ verify authority
→ verify source package hashes
→ rebuild joins
→ rebuild Global inputs
→ rerun Global development mode
→ compare semantic outputs
```

So sánh:

```text
decision status
gate result set
feature values
replay hash
input bindings
execution config hash
```

Timestamp mới có thể khác nếu contract cho phép, nhưng semantic run hash phải theo policy chính thức.

### 6.11. Fault Injector

Dùng cho tests, không dùng production run.

Hỗ trợ mutation có kiểm soát:

```text
missing package
duplicate package
candidate mismatch
sense mismatch
scope mismatch
dataset manifest mismatch
input contract mismatch
foreign C/E package
tampered self-hash
tampered physical hash
duplicate JSON key
NaN/Infinity
trailing garbage
wrong action-policy hash
CHECKSUMS drift
replay path traversal
```

### 6.12. Integration Reporter

Báo cáo tối thiểu:

```text
candidate count
joined count
failed count
failure codes
decision distribution
gate distribution
AUTO_APPROVED count
certificate count
provider/network calls
replay pass count
authority warnings
```

Không diễn giải semantic accuracy khi chưa có gold labels.

---

## 7. State machine

```text
DISCOVERED
  ↓
AUTHORITY_VERIFIED
  ↓
PACKAGES_VERIFIED
  ↓
JOINED
  ↓
PREFLIGHT_PASSED
  ↓
GLOBAL_INPUT_ASSEMBLED
  ↓
GLOBAL_RUN_COMPLETED
  ↓
SEALED
  ↓
REPLAY_VERIFIED
```

Failure state:

```text
REJECTED_PRE_AUTHORITY
REJECTED_INTEGRITY
REJECTED_JOIN
REJECTED_PREFLIGHT
REJECTED_GLOBAL_INPUT
REJECTED_EXECUTION
REJECTED_REPLAY
```

Không được skip state.

---

## 8. Error taxonomy

### Authority

```text
AUTHORITY_RECEIPT_INVALID
AUTHORITY_TAG_MISMATCH
AUTHORITY_COMMIT_MISMATCH
CONTRACT_MANIFEST_MISMATCH
GATE_POLICY_MISMATCH
FEATURE_REGISTRY_MISMATCH
GLOBAL_ACTION_POLICY_MISMATCH
```

### Integrity

```text
STRICT_JSON_REJECTED
PHYSICAL_HASH_MISMATCH
SELF_HASH_MISMATCH
NESTED_HASH_MISMATCH
CHECKSUM_MISMATCH
```

### Discovery

```text
MISSING_ARTIFACT
DUPLICATE_ARTIFACT
UNKNOWN_ARTIFACT_ROLE
ORPHAN_ARTIFACT
```

### Join

```text
CANDIDATE_ID_MISMATCH
CANDIDATE_VERSION_MISMATCH
SOURCE_TERM_MISMATCH
CANDIDATE_VI_MISMATCH
SENSE_ID_MISMATCH
SCOPE_ID_MISMATCH
SENSE_INVENTORY_VERSION_MISMATCH
DATASET_MANIFEST_MISMATCH
EFFECTIVE_SENSE_HASH_MISMATCH
INPUT_CONTRACT_HASH_MISMATCH
```

### Producer boundary

```text
NON_NULL_FINAL_GLOSSARY_DECISION
PRODUCER_EMITTED_GLOBAL_ACTION
UNOFFICIAL_FROZEN_CANDIDATE
INCOMPLETE_CONSTRAINT_PACKAGE
MISSING_REQUIRED_GATE_SIGNAL
```

### Development invariant

```text
DEVELOPMENT_APPROVAL_SCORE_NON_NULL
DEVELOPMENT_AUTO_APPROVED
DEVELOPMENT_CERTIFICATE_EMITTED
NETWORK_CALL_DETECTED
```

### Replay

```text
REPLAY_INPUT_DRIFT
REPLAY_AUTHORITY_DRIFT
REPLAY_DECISION_DRIFT
REPLAY_GATE_DRIFT
REPLAY_FEATURE_DRIFT
```

---

## 9. CLI đề xuất

```text
integration-harness authority-verify
integration-harness inventory
integration-harness validate-packages
integration-harness join
integration-harness assemble
integration-harness run
integration-harness replay
integration-harness verify-run
integration-harness inject-fault
integration-harness build-release
```

### Ví dụ

```bash
integration-harness run \
  --dataset-release artifacts/dataset-pilot \
  --c-release artifacts/c-pilot \
  --e-release artifacts/e-pilot \
  --global-release artifacts/global \
  --authority-root terminology_contracts_v1 \
  --mode REAL_DEVELOPMENT_ZERO_NETWORK \
  --output runs/pilot-001
```

Không hard-code Windows path.

---

## 10. Cấu hình run

`run_spec.json` tối thiểu:

```json
{
  "schema_id": "SystemIntegrationRunSpecV1",
  "schema_version": "1.0.0",
  "run_id": "integration_dev_001",
  "mode": "REAL_DEVELOPMENT_ZERO_NETWORK",
  "contracts_authority": {
    "tag": "contracts-v1.1.0",
    "commit": "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed",
    "manifest_sha256": "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
  },
  "global_action_policy_sha256": "4220b15b7b5d5b740946b9b258a5e1f25469a8f8409ca6e1a0b399464285c9f5",
  "expected_candidate_count": 15,
  "network_policy": "FORBIDDEN",
  "development_invariants": {
    "auto_approved_count": 0,
    "certificate_count": 0,
    "approval_score_must_be_null": true
  }
}
```

Không pin absolute artifact path trong semantic hash.

---

## 11. Test matrix bắt buộc

### 11.1. Happy path

```text
15 synthetic candidates
15 complete joins
15 Global inputs
15 PROVISIONAL hoặc expected development statuses
0 AUTO_APPROVED
0 certificate
15/15 replay PASS
0 network calls
```

### 11.2. Missing/duplicate

```text
missing C package → reject
missing E package → reject
missing Constraint package → reject
duplicate C package → reject
duplicate candidate → reject
```

### 11.3. Identity mismatch

```text
candidate_id mismatch → reject
candidate_version mismatch → reject
candidate_vi mismatch → reject
sense mismatch → reject
scope mismatch → reject
effective sense hash mismatch → reject
input contract mismatch → reject
```

### 11.4. Authority/integrity

```text
wrong Contracts manifest → reject
wrong GatePolicy → reject
wrong Global action policy → reject
tampered package self-hash → reject
tampered physical hash → reject
duplicate JSON key → reject
NaN/Infinity → reject
trailing garbage → reject
```

### 11.5. Ownership

```text
C non-null final decision → reject
E non-null final decision → reject
C/E global action field → reject
C-local Frozen Candidate → reject
Global-local Frozen Candidate → reject
```

### 11.6. Development invariants

```text
approval_score non-null → reject
AUTO_APPROVED → reject
certificate emitted → reject
provider call detected → reject
```

### 11.7. Replay

```text
CHECKSUMS mismatch → reject before execution
authority drift → reject
source package drift → reject
decision drift → reject
same sealed run → PASS
portable replay with new authority root and exact hashes → PASS
```

---

## 12. Release artifact

Tên đề xuất:

```text
system_integration_harness_v1_rc1.zip
system_integration_harness_v1_rc1.zip.sha256
```

Bên trong:

```text
source/
tests/
docs/
fixtures/
junit.xml
commands.txt
environment.json
static_scan.json
credential_scan.json
ownership_scan.json
git_commit_receipt.json
release_manifest.json
CHECKSUMS.sha256
synthetic_integration_summary.json
fault_injection_report.json
replay_report.json
```

Không chứa:

```text
.pyc
__pycache__
.pytest_cache
secret
raw provider credentials
```

---

## 13. Milestones

### M0 — Repository bootstrap

```text
branch created from latest main
ownership paths agreed
package skeleton
CLI skeleton
tests discoverable
```

### M1 — Authority and strict loader

```text
Contracts receipt verification
Global action-policy pin
duplicate-aware JSON
manifest/checksum verification
```

### M2 — Artifact inventory and joins

```text
artifact discovery
candidate index
exact identity join
join report
```

### M3 — Synthetic Global assembly

```text
assemble 15 synthetic Global inputs
run DEVELOPMENT_HEURISTIC
enforce zero approval/certificate
```

### M4 — Immutable run and replay

```text
run layout
CHECKSUMS
portable replay
semantic comparison
```

### M5 — Adversarial suite

```text
all error classes
fault injector
fail-closed reports
```

### M6 — Real 15-candidate integration

Chỉ chạy khi có:

```text
15 Dataset-owned Frozen Candidates
15 COMPLETE Constraint packages
15 official C packages
15 official E packages
reviewed Global RC2
authority receipt R2 hoặc accepted compatibility mode
```

Kết quả:

```text
15 inputs assembled
0 mismatch
0 network calls
0 AUTO_APPROVED
0 certificate
15/15 replay PASS
```

---

## 14. Dependency contract với các agent

### Dataset Agent phải bàn giao

```text
15 FrozenCandidateContractV1 COMPLETE
15 ConstraintEvidencePackageV1 COMPLETE
Dataset release manifest
candidate index
artifact checksums
authority receipt
```

### C phải bàn giao

```text
15 ContextEvidencePackageV1
projection manifest
release receipt
provider/replay ledger refs
gate-signal coverage report
```

### E phải bàn giao

```text
15 AttestationEvidencePackageV1
projection manifest
release receipt
raw/replay ledger refs
gate-signal coverage report
```

### Global phải bàn giao

```text
reviewed implementation RC
pinned action-policy sidecar
public CLI/API
decision verifier
portable replay
release receipt
```

### Contract Steward phải bàn giao

```text
canonical authority receipt R2
final Contracts V1.1.0 package
authority verification report
```

---

## 15. Blocker policy

Harness không đợi thụ động.

Khi dependency chưa có:

```text
dùng contract fixtures
xây validator
xây joins
xây fault tests
xây replay
```

Nhưng phải ghi:

```text
REAL_PILOT_NOT_EXECUTED
BLOCKED_BY_<DEPENDENCY>
```

Không tạo fake producer authority để gỡ blocker.

---

## 16. Definition of Done V1

Harness đạt `INTEGRATION_READY` khi:

1. Chỉ sửa owned paths.
2. Strict JSON và authority verification PASS.
3. Exact joins cover toàn bộ identity tuple.
4. Missing/duplicate/foreign package fail closed.
5. 15 synthetic candidates chạy thành công.
6. Development mode giữ 0 AUTO_APPROVED.
7. Development mode giữ 0 certificate.
8. Network/provider calls bằng 0.
9. Immutable run có manifest và CHECKSUMS.
10. Replay verify checksum trước execution.
11. Replay không phụ thuộc original absolute path.
12. 15/15 replay PASS.
13. Fault-injection suite PASS.
14. Source release sạch cache/credential.
15. Independent review chấp nhận RC.

Harness đạt `READY_FOR_REAL_PILOT` khi thêm:

16. Nhận đủ 15 official Dataset/C/E packages.
17. Global RC2 đã được review.
18. Authority receipts/policies được pin.
19. Real 15-candidate join PASS.
20. Real 15/15 replay PASS.

---

## 17. Không thuộc phạm vi V1

```text
provider orchestration
Search/Judge calls
human annotation UI
gold-label management
calibration fitting
validation/test evaluation
TAC execution
downstream translation A–D
production certificate publication
```

---

## 18. Báo cáo Agent cần gửi reviewer

```text
repository
branch
base main commit
implementation commit
parent/merge-base
worktree status
changed paths
authority hashes
test result
synthetic pilot result
fault-injection result
replay result
release ZIP path/SHA
real pilot status
remaining blockers
```

---

## 19. Prompt giao trực tiếp cho Agent

```text
You are the System Integration Harness Agent for the terminology-evidence
project.

Create branch feature/system-integration-harness-v1 from the latest reviewed
canonical main. Do not modify Dataset, Context Substitution C, Vietnamese
Attestation E, Global Validator or terminology_contracts_v1 internals.

Build a standalone, fail-closed integration harness that:

1. Verifies Contracts V1.1.0 authority and the exact Global action-policy pin.
2. Strict-loads JSON with duplicate-key, NaN/Infinity and trailing-data rejection.
3. Discovers artifacts only through explicit manifests.
4. Verifies physical hashes, self-hashes, nested bindings and CHECKSUMS.
5. Joins Dataset, Constraint, C and E packages by the complete candidate identity.
6. Rejects missing, duplicate, foreign or mismatched packages.
7. Enforces producer ownership:
   - Dataset owns Frozen Candidate and Constraint packages;
   - C/E final_glossary_decision must be null;
   - C/E must not emit Global gate actions.
8. Assembles official GlobalValidatorInputV1 packages.
9. Calls only the public Global Validator CLI/API in DEVELOPMENT_HEURISTIC mode.
10. Enforces approval_score=null, 0 AUTO_APPROVED and 0 certificates.
11. Stores immutable run bundles with manifest and CHECKSUMS.
12. Replays without network/provider calls and without dependence on the original
    absolute repository path.
13. Includes a fault-injection suite for authority, hash, identity, ownership and
    replay failures.
14. Runs a 15-candidate synthetic zero-network integration first.
15. Runs the real 15-candidate pilot only after official Dataset/C/E packages
    and reviewed Global RC2 are available.
16. Does not invent missing authority artifacts or producer outputs.

Deliver:
- clean source;
- tests and JUnit;
- CLI;
- commands/environment;
- scan reports;
- Git receipt;
- release manifest and checksums;
- synthetic integration summary;
- fault-injection report;
- replay report;
- RC ZIP and SHA.

Report back with branch/commit/base, changed paths, authority pins, tests,
synthetic result, replay result, release SHA and remaining blockers.
```
