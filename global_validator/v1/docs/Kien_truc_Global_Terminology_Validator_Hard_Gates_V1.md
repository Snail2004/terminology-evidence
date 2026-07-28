# KIẾN TRÚC GLOBAL TERMINOLOGY VALIDATOR + HARD GATES V1

**Trạng thái:** Agent-ready implementation contract
**Mục tiêu:** Xây tầng hợp nhất bằng chứng C/E, hard gates, decision policy, calibration binding và certificate issuance
**Authority:** `terminology_contracts_v1`
**Runtime scope:** Không đọc raw dataset; chỉ nhận các package chuẩn theo contract
**Ngôn ngữ triển khai đề xuất:** Python 3.11+
**Phiên bản kiến trúc:** `global-validator-architecture-v1.0.0`

---

## 1. Mục tiêu

Module này nhận hai nguồn evidence độc lập:

- `ContextEvidencePackageV1` từ Context Substitution Test;
- `AttestationEvidencePackageV1` từ Vietnamese Attestation Evidence.

Sau đó module:

1. xác minh hai package nói về cùng một candidate;
2. áp dụng hard gates;
3. lắp feature vector;
4. chạy decision policy;
5. trả một trong năm trạng thái;
6. phát certificate khi được phép;
7. lưu đầy đủ provenance, policy version và hash.

Module này **không**:

- đọc trực tiếp `term_senses.jsonl`, `contexts.jsonl` hoặc dataset ZIP;
- gọi C hoặc E nội bộ;
- tự đặt trọng số C/E;
- tự đặt threshold;
- sinh nhãn người;
- thay đổi candidate, sense hoặc definition;
- sửa schema trong `terminology_contracts_v1`;
- cấp `AUTO_APPROVED` ở development mode.

---

## 2. Trạng thái cuối

Mỗi đơn vị quyết định là:

```text
(source_term, sense_id, scope_id, candidate_vi, candidate_version)
```

Năm trạng thái cuối:

```text
AUTO_APPROVED
PROVISIONAL
HUMAN_REVIEW
REJECTED
SPLIT_REQUIRED
```

Ý nghĩa:

| Trạng thái | Ý nghĩa |
|---|---|
| `AUTO_APPROVED` | Evidence đủ mạnh, không có gate chặn, vượt threshold đã calibration |
| `PROVISIONAL` | Có bằng chứng ủng hộ nhưng coverage/scope chưa đủ để auto-approve |
| `HUMAN_REVIEW` | Bất đồng, collision, gần ngưỡng hoặc thiếu thông tin cần người xử lý |
| `REJECTED` | Sai concept, sai sense, contradiction hoặc lỗi nghiêm trọng |
| `SPLIT_REQUIRED` | Source term/sense inventory chưa tách đúng nhiều nghĩa |

---

## 3. Luồng tổng thể

```text
EffectiveSenseContractV1
          ↓
FrozenCandidateContractV1
          ↓
 ┌─────────────────────────────┐
 │ C và E chạy độc lập         │
 │                             │
 │ ContextEvidencePackageV1    │
 │ AttestationEvidencePackageV1│
 └──────────────┬──────────────┘
                ↓
      GlobalValidatorInputV1
                ↓
        Contract Joiner
                ↓
         Hard Gate Engine
                ↓
       Feature Assembler
                ↓
        Decision Policy
                ↓
       Decision Resolver
                ↓
   GlobalDecisionPackageV1
                ↓
      Certificate Issuer
                ↓
   TerminologyCertificateV1
```

---

## 4. Hợp đồng đầu vào

Module chỉ nhận:

```text
GlobalValidatorInputV1
```

Input tối thiểu:

```json
{
  "schema_id": "GlobalValidatorInputV1",
  "schema_version": "1.0.0",
  "candidate_key": {
    "candidate_id": "cand-001",
    "candidate_version": "1",
    "source_term": "inference",
    "candidate_vi": "suy luận",
    "sense_id": "model_execution",
    "scope_id": "machine_learning",
    "sense_inventory_version": "sense-v1",
    "dataset_manifest_sha256": "...",
    "effective_sense_contract_sha256": "...",
    "input_contract_sha256": "..."
  },
  "context_evidence": {},
  "attestation_evidence": {},
  "optional_probes": {
    "R": null,
    "Q": null
  }
}
```

---

## 5. Contract Joiner

### 5.1. Mục tiêu

Xác minh C và E nói về cùng một candidate bất biến.

### 5.2. Các trường bắt buộc phải khớp

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

### 5.3. Quy tắc

- Không join theo row order.
- Không join theo array index.
- Không join chỉ bằng `source_term`.
- Không join chỉ bằng `candidate_vi`.
- Không tự normalize rồi tiếp tục khi hash/ID lệch.
- Mismatch phải fail closed.

### 5.4. Kết quả mismatch

```text
gate_id = INPUT_CONTRACT_MISMATCH
decision = HUMAN_REVIEW
approval_score = null
certificate = null
```

### 5.5. Output nội bộ

```python
@dataclass(frozen=True)
class JoinedEvidence:
    candidate_key: CandidateKey
    context_evidence: ContextEvidencePackage
    attestation_evidence: AttestationEvidencePackage
    optional_probes: OptionalProbeSet
```

---

## 6. Hard Gate Engine

Hard gates chạy **trước** approval score.

### 6.1. Danh sách gate

| Gate ID | Điều kiện | Hành động |
|---|---|---|
| `INPUT_CONTRACT_MISMATCH` | C/E không cùng candidate contract | `HUMAN_REVIEW` |
| `SENSE_DEFINITION_UNVERIFIED` | Definition/POS/sense upstream chưa freeze | `HUMAN_REVIEW` |
| `UNRESOLVED_POLYSEMY` | Một source surface chứa nhiều sense chưa tách | `SPLIT_REQUIRED` |
| `CONCEPT_MISMATCH` | Candidate biểu thị concept khác | `REJECTED` |
| `WRONG_SENSE` | Candidate đúng ở sense khác | `REJECTED` hoặc `SPLIT_REQUIRED` |
| `CONTRADICTION` | Mất phủ định, quan hệ hay thuộc tính quyết định | `REJECTED` hoặc `HUMAN_REVIEW` |
| `TARGET_COLLISION` | Hai source concepts map cùng target gây mất phân biệt | `HUMAN_REVIEW` |
| `JUDGE_DISAGREEMENT` | Critical disagreement giữa Judge | `HUMAN_REVIEW` |
| `INSUFFICIENT_EVIDENCE` | C/E coverage không đủ | Tối đa `PROVISIONAL` |
| `MISSING_CONTRASTIVE_CONTEXT` | Không có boundary evidence | `HUMAN_REVIEW` hoặc policy-calibrated cap |
| `INCOMPLETE_CONTEXT_TYPE_COVERAGE` | Thiếu required C1–C5 | `HUMAN_REVIEW` hoặc policy-calibrated cap |
| `ATTESTATION_UNJUDGEABLE` | Retrieval/Judge không đủ để đánh giá E | `PROVISIONAL` hoặc `HUMAN_REVIEW` |

### 6.2. Gate severity

```text
FATAL_SPLIT
FATAL_REJECT
ESCALATE_HUMAN
CAP_PROVISIONAL
INFORMATIONAL
```

### 6.3. Thứ tự ưu tiên

```text
1. INPUT_CONTRACT_MISMATCH
2. SENSE_DEFINITION_UNVERIFIED
3. UNRESOLVED_POLYSEMY
4. CONCEPT_MISMATCH / WRONG_SENSE / CONTRADICTION
5. TARGET_COLLISION / JUDGE_DISAGREEMENT
6. INSUFFICIENT_EVIDENCE
7. Các informational flags
```

### 6.4. Gate output

```json
{
  "gate_id": "WRONG_SENSE",
  "triggered": true,
  "severity": "FATAL_REJECT",
  "source_modules": ["C"],
  "evidence_refs": ["c-evidence-..."],
  "reason_codes": ["CONTEXT_JUDGE_WRONG_SENSE"],
  "policy_version": "gate-policy-v1"
}
```

### 6.5. Gate invariants

```text
FATAL_SPLIT → không được trả AUTO_APPROVED/PROVISIONAL/REJECTED
FATAL_REJECT → không được trả AUTO_APPROVED/PROVISIONAL
ESCALATE_HUMAN → không được trả AUTO_APPROVED
CAP_PROVISIONAL → không được trả AUTO_APPROVED
```

---

## 7. Feature Assembler

Module này chỉ chuẩn hóa và lắp feature vector. Không quyết định.

### 7.1. C features

```text
C_mean
C_min
C_range
C_pass_count
C_minor_count
C_fail_count
C_evidence_coverage
C_required_type_coverage
C_judge_agreement
C_replacement_rate
C_contrastive_boundary_support
```

### 7.2. E features

```text
E_authority
E_independence
E_domain
E_concept
E_conventionality
E_coverage
E_span_yield
E_judge_coverage
E_strong_positive_cluster_count
E_conflict_ratio
```

### 7.3. Optional features

```text
R_score = null by default
Q_score = null by default
```

R/Q chỉ được đưa vào khi có probe artifact chứng minh giá trị bổ sung.

### 7.4. Thang đo

- Các feature liên tục nằm trong `[0,1]`.
- Count giữ dạng số nguyên.
- Không tự đổi count sang score nếu chưa có policy.
- Không gọi `approval_score` là xác suất nếu chưa calibration xác suất.

### 7.5. Example

```json
{
  "C_mean": 0.86,
  "C_min": 0.70,
  "C_range": 0.20,
  "C_pass_count": 4,
  "C_minor_count": 1,
  "C_fail_count": 0,
  "C_evidence_coverage": 1.0,
  "C_required_type_coverage": 0.8,
  "C_judge_agreement": 0.9,

  "E_authority": 0.75,
  "E_independence": 0.67,
  "E_domain": 1.0,
  "E_concept": 0.83,
  "E_conventionality": 0.6,
  "E_coverage": 0.8,
  "E_span_yield": 0.4,
  "E_judge_coverage": 0.9
}
```

---

## 8. Decision Policy

Có hai mode bắt buộc.

### 8.1. `DEVELOPMENT_HEURISTIC`

Mục đích:

- debug pipeline;
- test gates;
- inspect feature distributions;
- chạy ablation;
- không dùng cho scientific auto-approval.

Quy tắc:

```text
approval_score = null hoặc diagnostic_only
AUTO_APPROVED bị cấm
CalibrationArtifact không bắt buộc
```

Allowed decisions:

```text
PROVISIONAL
HUMAN_REVIEW
REJECTED
SPLIT_REQUIRED
```

### 8.2. `FROZEN_CALIBRATED`

Chỉ hoạt động khi có:

```text
CalibrationArtifactV1
```

Artifact phải được:

- đọc từ file;
- xác minh schema;
- xác minh self-hash;
- xác minh dataset/validation hash;
- xác minh selected feature registry;
- xác minh threshold;
- xác minh policy version.

Không chấp nhận chỉ truyền chuỗi SHA giả.

### 8.3. Calibration artifact tối thiểu

```json
{
  "schema_id": "CalibrationArtifactV1",
  "schema_version": "1.0.0",
  "development_dataset_sha256": "...",
  "validation_dataset_sha256": "...",
  "feature_registry_version": "feature-registry-v1",
  "gate_policy_version": "gate-policy-v1",
  "metric_target": {
    "auto_approval_precision": 0.95
  },
  "selected_policy": {
    "model_type": "logistic_regression",
    "threshold": 0.84
  },
  "calibration_results": {
    "precision": 0.956,
    "coverage": 0.41
  },
  "integrity": {
    "calibration_sha256": "..."
  }
}
```

---

## 9. Decision Resolver

### 9.1. Resolution rules

```text
Có FATAL_SPLIT
→ SPLIT_REQUIRED

Nếu không có FATAL_SPLIT nhưng có FATAL_REJECT
→ REJECTED

Nếu có ESCALATE_HUMAN
→ HUMAN_REVIEW

Nếu có CAP_PROVISIONAL
→ PROVISIONAL hoặc HUMAN_REVIEW theo policy

Không có gate chặn + DEVELOPMENT_HEURISTIC
→ PROVISIONAL hoặc HUMAN_REVIEW

Không có gate chặn + FROZEN_CALIBRATED
  + approval_score >= auto_threshold
→ AUTO_APPROVED

Không có gate chặn + FROZEN_CALIBRATED
  + approval_score < auto_threshold
→ PROVISIONAL hoặc HUMAN_REVIEW
```

### 9.2. Không được phép

- Không để score cao bù `WRONG_SENSE`.
- Không để E cao bù `CONCEPT_MISMATCH`.
- Không để C cao bù `TARGET_COLLISION`.
- Không cấp `AUTO_APPROVED` khi calibration chưa verify.
- Không cấp certificate nếu input contract mismatch.

---

## 10. Certificate Issuer

### 10.1. Trạng thái được phát certificate

```text
AUTO_APPROVED
PROVISIONAL
```

### 10.2. Trạng thái không phát certificate

```text
HUMAN_REVIEW
REJECTED
SPLIT_REQUIRED
```

### 10.3. Certificate tối thiểu

```json
{
  "schema_id": "TerminologyCertificateV1",
  "schema_version": "1.0.0",
  "candidate_key": {},
  "status": "AUTO_APPROVED",
  "scope_note": "...",
  "allowed_variants": [],
  "forbidden_candidates": [],
  "support_context_refs": [],
  "attestation_evidence_refs": [],
  "gate_summary": [],
  "decision_package_sha256": "...",
  "policy_version": "global-policy-v1",
  "threshold_version": "threshold-v1",
  "sense_inventory_version": "sense-v1",
  "certificate_version": "certificate-v1",
  "integrity": {
    "certificate_sha256": "..."
  }
}
```

### 10.4. Certificate semantics

Certificate chỉ có hiệu lực trong:

```text
candidate_version
sense_id
scope_id
sense_inventory_version
support evidence region
policy version
```

Không phải quyền áp dụng candidate trong mọi context tương lai.

---

## 11. Provenance và audit

Mỗi run phải lưu:

```text
global_run_id
global_run_spec_id
started_at
completed_at
input package hashes
candidate contract hash
C package hash
E package hash
gate policy version
feature registry version
decision policy version
calibration artifact hash
decision package hash
certificate hash
```

### 11.1. Replay

Phải có thể replay từ:

```text
GlobalValidatorInputV1
+
GatePolicyV1
+
CalibrationArtifactV1
```

mà không cần gọi lại C/E.

### 11.2. Immutability

- Không sửa C/E package.
- Không ghi đè output cũ.
- Mỗi run tạo output mới.
- Breaking schema change phải tăng major version.

---

## 12. Ablation support

Engine phải hỗ trợ:

```text
gates_enabled = true/false
use_context_evidence = true/false
use_attestation_evidence = true/false
use_optional_R = true/false
use_optional_Q = true/false
```

Cấu hình chính:

```text
V0 Direct LLM decision
V1 Context only
V2 C + E
V3 Evidence calibrated, no gates
V4 Evidence + gates + calibrated threshold
V5 V4 + optional R/Q
```

Agent hiện tại chỉ cần hỗ trợ V1–V4 ở contract/runtime level.

---

## 13. Cấu trúc source đề xuất

```text
global_terminology_validator/
├── README.md
├── AGENTS.md
├── pyproject.toml
│
├── global_validator/
│   └── v1/
│       ├── engine.py
│       ├── joiner.py
│       ├── feature_assembler.py
│       │
│       ├── gates/
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── contract.py
│       │   ├── concept.py
│       │   ├── sense.py
│       │   ├── polysemy.py
│       │   ├── collision.py
│       │   ├── contradiction.py
│       │   ├── sufficiency.py
│       │   └── disagreement.py
│       │
│       ├── decision/
│       │   ├── policy.py
│       │   ├── resolver.py
│       │   └── feature_registry.py
│       │
│       ├── calibration/
│       │   ├── artifact.py
│       │   ├── loader.py
│       │   └── verifier.py
│       │
│       ├── certificates/
│       │   └── issuer.py
│       │
│       ├── audit/
│       │   ├── provenance.py
│       │   ├── canonical.py
│       │   └── replay.py
│       │
│       └── cli.py
│
├── tests/
│   ├── test_joiner.py
│   ├── test_gate_precedence.py
│   ├── test_feature_assembler.py
│   ├── test_decision_modes.py
│   ├── test_calibration_binding.py
│   ├── test_certificate_issuer.py
│   ├── test_ablation_modes.py
│   └── test_end_to_end_fixtures.py
│
└── docs/
    ├── ARCHITECTURE.md
    ├── GATE_POLICY.md
    ├── CALIBRATION_HANDOFF.md
    └── VERSION_MATRIX.md
```

---

## 14. CLI đề xuất

```bash
global-validator validate-input \
  --input global_validator_input.json

global-validator run \
  --input global_validator_input.json \
  --mode DEVELOPMENT_HEURISTIC \
  --output-dir runs/

global-validator run \
  --input global_validator_input.json \
  --mode FROZEN_CALIBRATED \
  --calibration calibration_artifact.json \
  --output-dir runs/

global-validator replay \
  --run-dir runs/<global_run_id>

global-validator verify-certificate \
  --certificate certificate.json
```

---

## 15. Test matrix bắt buộc

### 15.1. Contract tests

```text
C/E candidate_id mismatch → fail closed
sense_id mismatch → fail closed
scope mismatch → fail closed
effective sense contract hash mismatch → fail closed
schema version mismatch → fail closed
```

### 15.2. Gate precedence

```text
SPLIT + REJECT → SPLIT_REQUIRED
REJECT + HUMAN → REJECTED
HUMAN + PROVISIONAL cap → HUMAN_REVIEW
PROVISIONAL cap only → PROVISIONAL
```

### 15.3. Mode tests

```text
development mode cannot AUTO_APPROVE
frozen mode without artifact fails
frozen mode with bad hash fails
frozen mode with verified artifact may AUTO_APPROVE
```

### 15.4. Certificate tests

```text
AUTO_APPROVED → certificate emitted
PROVISIONAL → scoped certificate emitted
HUMAN_REVIEW → no certificate
REJECTED → no certificate
SPLIT_REQUIRED → no certificate
```

### 15.5. Score/gate conflict tests

```text
approval_score 0.99 + WRONG_SENSE → REJECTED
approval_score 0.99 + TARGET_COLLISION → HUMAN_REVIEW
approval_score 0.99 + UNRESOLVED_POLYSEMY → SPLIT_REQUIRED
```

---

## 16. Definition of Done

Agent chỉ được báo hoàn thành khi:

1. toàn bộ source dùng `terminology_contracts_v1` làm authority;
2. runtime không đọc raw dataset;
3. không import internal implementation của C/E;
4. Contract Joiner fail closed;
5. Gate precedence có test;
6. development mode cấm `AUTO_APPROVED`;
7. frozen mode bắt buộc verified `CalibrationArtifactV1`;
8. certificate chỉ phát đúng trạng thái;
9. provenance và self-hash đầy đủ;
10. CLI, tests và JUnit report được đóng gói;
11. không có `__pycache__`, `.pyc`, secret hoặc API key;
12. zero-API end-to-end fixture pass.

---

## 17. Scope guardrails cho agent

### MUST

- MUST đọc `terminology_contracts_v1/AGENT_RULES.md`.
- MUST validate mọi input/output theo schema.
- MUST fail closed khi mismatch.
- MUST lưu policy version và hash.
- MUST tách gates khỏi evidence score.
- MUST giữ `AUTO_APPROVED` bị khóa trong development.
- MUST dùng calibration artifact để mở frozen mode.

### MUST NOT

- MUST NOT tự đặt trọng số C/E.
- MUST NOT tự đặt threshold.
- MUST NOT đọc raw dataset trong runtime.
- MUST NOT gọi C/E nội bộ.
- MUST NOT sửa schema chung.
- MUST NOT tạo nhãn người.
- MUST NOT phát certificate khi chưa đủ điều kiện.
- MUST NOT xem score là xác suất đúng tuyệt đối.

---

## 18. Chỉ thị giao agent

```text
Xây Global Terminology Validator + Hard Gates V1 theo file kiến trúc này và
terminology_contracts_v1 làm authority.

Runtime chỉ nhận GlobalValidatorInputV1, không đọc raw dataset và không import nội bộ
Context Substitution hoặc Vietnamese Attestation.

Hoàn thiện Contract Joiner, Hard Gate Engine, Feature Assembler, hai decision modes,
CalibrationArtifact verifier, Decision Resolver, Certificate Issuer, provenance,
replay, CLI và tests.

Không tự đặt trọng số hoặc threshold. Development mode cấm AUTO_APPROVED.
Frozen calibrated mode chỉ mở khi CalibrationArtifactV1 được load và verify thành công.

Dùng fixtures để chạy zero-API end-to-end. Đóng gói source, CLI, tests, JUnit,
commands và version matrix để reviewer audit.
```
