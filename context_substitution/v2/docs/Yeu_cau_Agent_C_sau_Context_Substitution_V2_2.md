# YÊU CẦU TIẾP THEO CHO AGENT C SAU CONTEXT SUBSTITUTION V2.2

**Trạng thái hiện tại:** Context Substitution V2.2 đã hoàn thành giai đoạn sửa thuật toán lõi theo review.
**Giai đoạn tiếp theo:** Integration readiness.
**Nguyên tắc:** Không mở rộng thêm kiến trúc CST và chưa chạy toàn bộ validation/test hoặc 150 senses.

**Standalone implementation note (2026-07-29):** Agent C chỉ sở hữu
`context_substitution/**`. CLI và tests vì vậy được đóng gói lần lượt tại
`context_substitution/v2/cli.py` và `context_substitution/v2/tests/**`.
Generated reports được ghi ngoài source tree và chỉ đi vào release ZIP theo
SHA-256. Cụm từ "chưa chạy validation/test" trong tài liệu này có nghĩa là
chưa chạy các **dataset split** validation/test; software tests vẫn bắt buộc.

---

## 1. Mục tiêu

Agent C cần chuyển trọng tâm từ phát triển thuật toán sang:

```text
đóng gói kiểm chứng
→ zero-API pilot
→ contract projection boundary
→ integration với Global Validator
→ API canary nhỏ
```

CST vẫn là Evidence Provider. Agent C không được tự đưa ra quyết định glossary cuối hoặc tự chọn action của global hard gates.

---

## 2. Đóng gói đầy đủ V2.2

Tạo integration release bundle chứa tối thiểu:

```text
context_substitution/**
context_substitution/v2/cli.py
context_substitution/v2/tests/**
junit.xml
commands.txt
environment.json
static_scan.json
credential_scan.json
```

CLI phải hỗ trợ tối thiểu:

```text
reviewed-support-validate
reviewed-support-to-runtime
context-run
run-validate
project-context-evidence
gold-evaluate
```

Không thay đổi thuật toán CST ở bước này.

---

## 3. Zero-API adapter smoke test trên pilot thật

Dùng:

```text
pilot_dev_only_v1_1
parent dataset = d2l_context_support_set_validation_ready_v3
split = development
```

Chạy cả hai đường vào:

```text
pilot directory
pilot ZIP
```

Kết quả từ hai đường phải tương đương về semantic content và candidate IDs.

### Acceptance criteria

```text
5 senses
15 candidates
25 primary contexts
8 backup contexts
5 contrastive contexts
0 missing references
0 API calls
```

Xuất receipt riêng ghi:

```text
dataset manifest hash
pilot manifest hash
adapter version
candidate count
context counts
missing reference count
API call count
```

---

## 4. Fake-provider end-to-end cho 15 candidates

Không gọi API thật.

Fake provider phải bao phủ:

```text
trial translation hợp lệ
invalid trial rồi retry
Judge PASS
Judge MINOR
Judge FAIL
Judge abstain
Judge 1/Judge 2 disagreement
malformed provider response
provider failover
pairwise tie-break
wrong sense
missing contrastive context
incomplete C1–C5 coverage
insufficient valid context
```

### Acceptance criteria

```text
15 candidate runs được tạo
final_glossary_decision luôn null
provider_attempts đầy đủ
mọi raw response được lưu content-addressed
response hash khớp raw ledger
deterministic replay tạo lại cùng normalized output
candidate thiếu evidence không được ELIGIBLE_FOR_COMBINATION
```

---

## 5. Raw provider ledger và replay

Mỗi provider attempt phải lưu:

```text
run_id
candidate_id
context_id
provider_id
model_id
prompt_hash
request_hash
response_hash
status
retry_index
failure_reason
started_at
completed_at
token_usage
latency
```

Raw response phải:

- được lưu nguyên trạng;
- có content hash;
- không bị ghi đè;
- có thể replay mà không gọi API;
- sinh lại cùng normalized result.

Artifact dự kiến:

```text
provider_attempts.jsonl
provider_responses/
replay_report.json
```

---

## 6. Projection boundary sang contract chung

Không để engine CST phụ thuộc trực tiếp vào common contract schema.

Kiến trúc bắt buộc:

```text
Context Substitution internal result
        ↓
C contract projection adapter
        ↓
ContextEvidencePackage V1.1
```

Lớp projection phải nằm riêng để khi contract chính thức thay đổi chỉ sửa boundary, không sửa thuật toán CST.

---

## 7. Mapping C hard flags sang gate signals

Chuẩn bị mapping nội bộ:

```text
CONTEXT_WRONG_SENSE
    → wrong_sense

CONTEXT_SEMANTIC_MISMATCH
    → concept_mismatch

CONTEXT_CONTRADICTION
    → contradiction

MISSING_CONTRASTIVE_CONTEXT
    → missing_contrastive_context

INCOMPLETE_CONTEXT_TYPE_COVERAGE
    → incomplete_context_type_coverage

CONTEXT_EVIDENCE_INSUFFICIENT
    → insufficient_evidence

JUDGE_DISAGREEMENT
    → judge_disagreement
```

Agent C chỉ được xuất:

```text
gate_id
asserted
reason_codes
evidence_refs
source_module
```

Agent C không được tự chọn:

```text
FATAL_REJECT
FATAL_SPLIT
CAP_PROVISIONAL
ESCALATE_HUMAN
```

Các action này thuộc `GatePolicyArtifact` và Global Validator.

---

## 8. Frozen human-reviewed handoff

Agent C không tự tạo nhãn review.

Artifact human-reviewed cần cung cấp:

```text
review_artifact_sha256
effective_sense_contract_sha256
candidate_id
sense_id
scope_id
effective_definition_en
effective_part_of_speech
reviewed context relation
reviewed context type
reviewed validity
review provenance
```

### Test bắt buộc

```text
frozen mode không gọi Context Selector
frozen mode dùng trực tiếp reviewed rows
sửa một reviewed row làm hash verification fail
thiếu một reviewed context làm run fail closed
review artifact không hoàn chỉnh không thể giả danh frozen authority
effective sense hash mismatch bị từ chối
```

Cho đến khi human-reviewed artifact được freeze, chỉ chạy:

```text
MODEL_CLASSIFICATION_DEVELOPMENT
```

Không gọi development review pack là human-frozen authority.

---

## 9. Contract authority đã được tích hợp

Authority chính thức:

```text
contracts-v1.1.0
```

đã được Project Maintainer phát hành và merge nguyên trạng vào branch C. C chỉ
tiêu thụ package chung, không direct-edit `terminology_contracts_v1/**`.

Closure:

1. thay provisional projection bằng schema chính thức;
2. bind đúng `input_contract_sha256`;
3. xuất `ContextEvidencePackageV1.1`;
4. xuất `gate_signals` theo contract chính thức;
5. chạy contract conformance tests;
6. tạo 15 C evidence packages zero-API ở trạng thái local HOLD.

Không copy schema contract vào module C. C phải import contract authority chung.
Global Validator chưa được xây dựng nên chưa có handoff hoặc dependency runtime.

---

## 10. Zero-API integration với Global Validator

Bàn giao cho Global Validator:

```text
15 ContextEvidencePackage V1.1
C package hashes
input_contract_sha256
candidate identity
sense/scope identity
gate_signals
evidence refs
support-set refs
run/replay provenance
```

Integration phải kiểm tra:

```text
candidate/hash join chính xác
mismatch fail closed
C không đưa final decision
gate signals được Global tiếp nhận
development mode không AUTO_APPROVED
replay không gọi API
```

---

## 11. API canary nhỏ sau integration

Chỉ chạy sau khi:

```text
contract integration pass
zero-API replay pass
human-reviewed handoff đủ điều kiện cho mode tương ứng
```

Thứ tự canary đề xuất:

```text
ShopAI-only development canary
CKey-only development canary
Gemini-official-only development canary
optional cross-family Judge canary
```

Mỗi canary chỉ dùng một subset nhỏ của development pilot.

Báo riêng:

```text
success rate
invalid response rate
retry rate
failover rate
latency
token usage
cost
Judge disagreement
raw ledger completeness
```

Không chạy dataset split validation/test và chưa chạy toàn bộ 150 senses.

---

## 12. Calibration sau khi có nhãn người

Chỉ calibration khi development/validation human labels đã sẵn sàng.

Cần báo:

```text
precision–coverage curve
Wilson/bootstrap confidence intervals
cluster bootstrap theo sense_id
threshold distribution
threshold confidence interval
decision flip rate
judge–human agreement
invalid-context replacement rate
cost per candidate
```

Không dùng heuristic development làm frozen test policy.

---

## 13. Artifact bàn giao

```text
context_substitution_v2_2_integration_rc.zip
context_substitution_v2_2_integration_rc.zip.sha256
context_substitution_v2_2_audit.json
junit.xml
commands.txt
environment.json
static_scan.json
credential_scan.json
pilot_adapter_receipt.json
pilot_zero_api_summary.json
development_frozen_candidates.json
context_evidence_packages/manifest.json
context_evidence_packages/packages/
provider_attempts.jsonl
provider_responses/
replay_report.json
```

---

## 14. Không thuộc phạm vi Agent C

Agent C không được:

- quyết định glossary cuối;
- sửa common contract;
- tự đặt global gate action;
- tự tạo human-reviewed labels;
- chỉnh dataset đã freeze;
- chạy dataset split validation/test trước khi policy được freeze;
- chạy API diện rộng;
- dùng synthetic context làm C primary evidence;
- coi C score là xác suất đúng.

---

## 15. Definition of Done

Chỉ báo hoàn thành integration readiness khi:

1. release bundle đầy đủ source, CLI, tests và reports;
2. zero-API adapter smoke test đạt đúng counts;
3. 15 fake-provider runs hoàn tất;
4. raw ledger và replay pass;
5. `final_glossary_decision` luôn `null`;
6. projection adapter được tách khỏi engine;
7. gate-signal mapping đã có test;
8. frozen reviewed mode fail closed;
9. contract conformance pass sau khi có tag chính thức;
10. 15 C evidence packages được Global Validator nhận thành công;
11. không có secret, `.pyc`, `__pycache__`;
12. chưa chạy dataset split validation/test hoặc full-scale API.

---

## 16. Prompt giao trực tiếp cho Agent C

```text
Context Substitution V2.2 đã hoàn thành giai đoạn sửa thuật toán lõi.
Chuyển sang giai đoạn integration readiness; không mở rộng thêm kiến trúc CST.

Làm theo thứ tự:

1. Tạo release bundle đầy đủ gồm source, CLI, tests, JUnit, commands,
   environment và scan reports.
2. Chạy zero-API adapter smoke test trên pilot_dev_only_v1_1 với parent V3.
   Kết quả bắt buộc: 5 senses, 15 candidates, 25 primary, 8 backup,
   5 contrastive, 0 missing references, 0 API calls.
3. Chạy fake-provider end-to-end cho toàn bộ 15 candidates, bao phủ retry,
   failover, invalid response, Judge disagreement, wrong sense,
   missing contrastive và incomplete C1–C5.
4. Kiểm chứng raw provider ledger và deterministic replay.
   final_glossary_decision phải luôn null.
5. Chuẩn bị projection adapter riêng từ internal C result sang common
   ContextEvidencePackage; không nhúng common schema vào engine.
6. Chuẩn bị mapping từ C hard flags sang gate signals, nhưng không tự định nghĩa
   global gate action và không sửa contract chung.
7. Thêm tests cho FROZEN_HUMAN_REVIEWED_SELECTION. Frozen mode phải dùng
   trực tiếp reviewed rows và fail closed khi review/effective-sense hash lệch.
8. Serializer chính thức dùng authority `contracts-v1.1.0`; RC2-RC4 chỉ là
   review evidence, không phải runtime authority.
9. Sau khi contract integration pass, giữ 15 ContextEvidencePackage zero-API
   ở local HOLD cho tới khi maintainer mở phase Global Validator riêng.
10. Chưa chạy validation/test, chưa chạy 150 senses và chưa chạy API diện rộng.

Artifact bàn giao:

context_substitution_v2_2_integration_rc.zip
context_substitution_v2_2_integration_rc.zip.sha256
context_substitution_v2_2_audit.json
junit.xml
commands.txt
environment.json
static_scan.json
credential_scan.json
pilot_adapter_receipt.json
pilot_zero_api_summary.json
development_frozen_candidates.json
context_evidence_packages/manifest.json
context_evidence_packages/packages/
provider_attempts.jsonl
provider_responses/
replay_report.json

Báo lại commit hash, test summary, smoke-test counts và các phần còn chờ
contract hoặc human-reviewed artifact.
```
