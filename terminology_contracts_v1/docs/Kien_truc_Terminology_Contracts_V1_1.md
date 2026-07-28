# KIẾN TRÚC VÀ KẾ HOẠCH NÂNG CẤP TERMINOLOGY CONTRACTS V1.1

**Vai trò tài liệu:** Đặc tả giao việc cho Contract Steward Agent  
**Release mục tiêu:** `terminology_contracts_v1.1.0`  
**Nguồn nâng cấp:** `terminology_contracts_v1.0.0`  
**Phạm vi:** Hợp đồng dữ liệu dùng chung giữa Dataset Adapter, Context Substitution (C), Vietnamese Attestation (E), Global Validator, Calibration và TAC  
**Nguyên tắc:** Contract-first, fail-closed, versioned, replayable, không phụ thuộc implementation nội bộ

---

## 1. Quyết định tổ chức

Nên giao công việc này cho một agent mới, độc lập, có vai trò:

```text
Contract Steward Agent
```

Không giao quyền sở hữu contract cho riêng:

```text
Context Substitution Agent
Vietnamese Attestation Agent
Global Validator Agent
```

Lý do:

1. Contract là authority chung, không phải sản phẩm nội bộ của C, E hay Global Validator.
2. Agent sở hữu một module có xu hướng tối ưu schema theo module đó.
3. Contract Steward phải kiểm tra tính tương thích hai chiều giữa tất cả producer và consumer.
4. Sau khi release V1.1, C, E và Global Validator chỉ được triển khai theo contract, không tự sửa schema.

Contract Steward có quyền:

- audit;
- đề xuất migration;
- sửa package contract;
- tạo schema, fixtures, validation utilities và compatibility tests;
- phát hành ZIP cùng checksum.

Contract Steward không có quyền:

- sửa thuật toán C/E;
- chọn trọng số C/E;
- đặt threshold;
- tạo human labels;
- quyết định cuối cho candidate;
- thay đổi thesis scope.

---

## 2. Authority hierarchy

Khi tài liệu hoặc code mâu thuẫn, dùng thứ tự ưu tiên:

```text
1. Báo cáo kiến trúc luận văn V2
2. Terminology Contracts V1.1 specification này
3. Kiến trúc Global Terminology Validator + Hard Gates V1
4. Kiến trúc Context Substitution Test V2
5. Kiến trúc Vietnamese Attestation Evidence V1
6. Dataset manifest V3 và Development Pilot V1.1
7. terminology_contracts_v1.0.0 hiện tại
8. Implementation nội bộ của từng agent
```

`terminology_contracts_v1.0.0` là migration source, không phải authority cuối nếu có mâu thuẫn với kiến trúc đã chốt.

---

## 3. Mục tiêu release V1.1

Release V1.1 phải tạo một interface ổn định để:

```text
Dataset Adapter
      ↓
FrozenCandidateContractV1
      ↓
C ──→ ContextEvidencePackageV1
E ──→ AttestationEvidencePackageV1
      ↓
GlobalValidatorInputV1
      ↓
GateResultSetV1
      ↓
GlobalDecisionPackageV1
      ↓
TerminologyCertificateV1
      ↓
TACOccurrenceInputV1
```

Sau release:

- C và E có thể thay đổi implementation nội bộ mà không làm Global Validator sửa.
- Dataset có thể đổi storage format nhưng phải được adapter map về contract.
- Global Validator không đọc raw dataset.
- TAC chỉ đọc certificate contract.
- Calibration artifact phải được verify, không chỉ kiểm tra chuỗi SHA.

---

## 4. Chiến lược version

### 4.1. Package version

```text
package_version = 1.1.0
```

### 4.2. Schema family

Giữ major family:

```text
ContextEvidencePackageV1
AttestationEvidencePackageV1
GlobalValidatorInputV1
GateResultSetV1
CalibrationArtifactV1
GlobalDecisionPackageV1
TerminologyCertificateV1
```

Đổi:

```text
schema_version: "1.0.0"
```

thành:

```text
schema_version: "1.1.0"
```

### 4.3. Legacy preservation

Phải giữ schema cũ tại:

```text
schemas/legacy/v1.0.0/
```

Schema mới tại:

```text
schemas/v1.1.0/
```

Có thể có thư mục alias:

```text
schemas/current/
```

trỏ hoặc copy tới `v1.1.0`.

### 4.4. Compatibility

Runtime mới:

```text
accept v1.1.0 trực tiếp
accept v1.0.0 chỉ qua migration adapter
normalize nội bộ về v1.1.0
emit v1.1.0
```

Không âm thầm coi payload V1.0 là V1.1.

---

## 5. Quyết định tên trường canonical

Để giảm thay đổi không cần thiết, V1.1 khóa các tên sau.

### 5.1. Gate action

Canonical:

```text
action
```

Allowed values:

```text
NONE
FATAL_REJECT
FATAL_SPLIT
ESCALATE_HUMAN
CAP_PROVISIONAL
```

Không dùng trường song song:

```text
severity
```

Trong tài liệu mô tả có thể gọi là severity class, nhưng serialized field phải là `action`.

### 5.2. Calibration feature version

Canonical:

```text
feature_contract_version
```

Không đổi sang:

```text
feature_registry_version
```

Global Validator architecture phải được cập nhật để dùng tên canonical này.

### 5.3. Certificate context refs

Canonical cho context support:

```text
validity_context_refs
```

Bổ sung riêng:

```text
attestation_evidence_refs
```

Không thêm alias `support_context_refs`, tránh hai tên cùng nghĩa.

### 5.4. Gate IDs

Serialized gate IDs dùng lowercase snake_case:

```text
input_contract_mismatch
sense_definition_unverified
unresolved_polysemy
concept_mismatch
wrong_sense
contradiction
target_collision
judge_disagreement
insufficient_evidence
missing_contrastive_context
incomplete_context_type_coverage
attestation_unjudgeable
```

Trong UI hoặc báo cáo có thể hiển thị uppercase, nhưng JSON phải dùng lowercase canonical.

---

## 6. Frozen Candidate Contract

`candidate_key` là khóa join chung.

Bắt buộc:

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
```

`input_contract_sha256` nằm ở envelope/package level và phải được đối chiếu giữa:

```text
FrozenCandidateContract
ContextEvidencePackage
AttestationEvidencePackage
GlobalValidatorInput
GateResultSet
GlobalDecisionPackage
```

### 6.1. Join invariant

Các giá trị sau phải giống tuyệt đối:

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

Không join bằng:

```text
row order
array index
source_term một mình
candidate_vi một mình
normalized text một mình
```

Mismatch phải fail closed.

---

## 7. Context Evidence Package V1.1

Giữ toàn bộ core fields V1.0:

```text
schema_id
schema_version
candidate_key
input_contract_sha256
selector_mode
review_artifact_sha256
features
contrastive_status
flags
local_status
support_set
provenance
final_glossary_decision
integrity
```

### 7.1. Core features giữ nguyên

```text
C_mean
C_min
C_max
C_range
evidence_coverage
required_context_type_coverage
judge_agreement
valid_context_count
pass_count
minor_count
fail_count
```

Không đổi tên các field này trong producer package.

Khi Global Validator flatten feature vector, có thể map thành:

```text
C_mean
C_min
C_max
C_range
C_evidence_coverage
C_required_context_type_coverage
C_judge_agreement
C_valid_context_count
C_pass_count
C_minor_count
C_fail_count
```

Việc prefix chỉ xảy ra ở Feature Assembler, không sửa schema C.

### 7.2. Optional diagnostics

Bổ sung object tùy chọn:

```json
{
  "diagnostics": {
    "replacement_rate": 0.8,
    "contrastive_boundary_support": 0.5
  }
}
```

Quy tắc:

- `diagnostics` không phải core decision features.
- Global Validator không được sử dụng diagnostic feature trừ khi tên feature xuất hiện trong sealed `CalibrationArtifactV1.model.feature_names`.
- Diagnostics có thể nullable.
- Không làm producer V1.0 migration thất bại nếu không có diagnostics.

### 7.3. Contrastive gates

Mapping bắt buộc:

```text
contrastive_status = ABSENT
→ candidate for gate missing_contrastive_context

required_context_type_coverage < policy minimum
→ candidate for gate incomplete_context_type_coverage
```

Contract chỉ truyền dữ liệu/flag. Gate policy quyết định action.

---

## 8. Attestation Evidence Package V1.1

Giữ core features:

```text
E_authority
E_independence
E_domain
E_concept
E_conventionality
E_coverage
```

Giữ stage metrics:

```text
search_coverage
fetch_coverage
extraction_coverage
language_coverage
span_yield
judge_coverage
unique_document_count
duplicate_cluster_count
independent_organization_count
```

### 8.1. Optional diagnostics

Bổ sung:

```json
{
  "diagnostics": {
    "strong_positive_cluster_count": 3,
    "conflict_ratio": 0.1
  }
}
```

Quy tắc giống C:

- không mặc định tham gia policy;
- chỉ được dùng nếu calibration artifact đăng ký;
- không thay thế core E vector;
- không tạo scalar `E_score`.

### 8.2. Attestation unjudgeable

Mapping:

```text
local_status = ATTESTATION_UNJUDGEABLE
→ gate candidate attestation_unjudgeable
```

Một candidate không được `ATTESTED` chỉ vì general-word evidence khi không có accepted strong-positive evidence. Đây là invariant của producer E và phải có fixture kiểm tra contract-level status consistency.

---

## 9. Gate Result Set V1.1

### 9.1. Bổ sung gate IDs

Thêm:

```text
missing_contrastive_context
incomplete_context_type_coverage
attestation_unjudgeable
```

### 9.2. Observation schema

Mỗi observation:

```json
{
  "gate_id": "wrong_sense",
  "triggered": true,
  "action": "FATAL_REJECT",
  "source_modules": ["C"],
  "reason_codes": ["CONTEXT_JUDGE_WRONG_SENSE"],
  "evidence_refs": []
}
```

Bổ sung optional:

```text
source_modules
```

Allowed:

```text
CONTRACT
SENSE
C
E
GLOBAL
HUMAN_REVIEW
```

### 9.3. Invariants

```text
triggered = false → action phải là NONE
action != NONE → triggered phải là true
FATAL_SPLIT → final decision SPLIT_REQUIRED
FATAL_REJECT → final decision REJECTED, trừ khi FATAL_SPLIT ưu tiên
ESCALATE_HUMAN → không AUTO_APPROVED
CAP_PROVISIONAL → không AUTO_APPROVED
```

Native C/E packages phải phát hành đầy đủ `gate_signals` thuộc phạm vi producer.
Global Validator lấy phép OR các assertion từ C/E và bắt buộc chiếu sang
`GateResultSetV1`; không được bỏ qua signal đã assert. Reason codes, evidence
refs và source module của producer phải được bảo toàn trong gate observation.

Mỗi `action` phải thuộc `allowed_actions` của gate tương ứng trong sealed
`GatePolicyArtifactV1`. Gate result, calibration, decision, replay metadata và
certificate cùng bind `gate_policy_artifact_sha256`; chuỗi version đơn lẻ không
đủ làm authority.

### 9.4. Precedence

```text
FATAL_SPLIT
> FATAL_REJECT
> ESCALATE_HUMAN
> CAP_PROVISIONAL
> NONE
```

---

## 10. Global Validator Input V1.1

Giữ envelope:

```text
candidate_key
input_contract_sha256
context_evidence
attestation_evidence
optional_probes
integrity
```

Bổ sung:

```text
assembly_metadata
```

Ví dụ:

```json
{
  "assembly_metadata": {
    "assembler_id": "global-input-assembler",
    "assembler_version": "1.1.0",
    "assembled_at": "2026-07-28T00:00:00Z",
    "source_package_hashes": {
      "context_evidence_sha256": "...",
      "attestation_evidence_sha256": "..."
    }
  }
}
```

Global Validator phải verify lại hashes, không tin assembly metadata mù quáng.

---

## 11. Calibration Artifact V1.1

Giữ canonical field:

```text
feature_contract_version
```

### 11.1. Sealed artifact requirements

Schema validation là chưa đủ. Verifier phải kiểm tra:

1. `self_sha256` theo canonical JSON;
2. development dataset hash;
3. validation dataset hash;
4. gate policy version;
5. feature contract version;
6. feature names tồn tại trong feature registry;
7. model parameters phù hợp model type;
8. threshold lấy từ artifact;
9. precision target và operating point đầy đủ;
10. artifact chưa bị sửa sau khi seal.

Trước khi freeze, calibration có thể bind `threshold_stability` từ cluster
bootstrap theo `sense_id`, gồm số replicate, median/CI của threshold và decision
flip rate. CI phải thỏa `lower <= median <= upper`.

### 11.2. Không được phép

```text
calibration_artifact_sha256 = "000...000"
```

không đủ để mở frozen mode.

Frozen mode chỉ mở khi:

```text
artifact file loaded
schema valid
canonical hash valid
binding valid
policy version compatible
feature contract compatible
```

### 11.3. Feature registry

Release phải có:

```text
registries/feature_contract_v1.1.0.json
```

Registry chia:

```text
core_features
optional_probe_features
diagnostic_features
deprecated_features
```

Chỉ feature nằm trong registry mới được xuất hiện trong calibration model.

---

## 12. Global Decision Package V1.1

Giữ core fields V1.0 và bổ sung `run_metadata`.

### 12.1. Run metadata

```json
{
  "run_metadata": {
    "global_run_id": "gv-run-001",
    "global_run_spec_id": "gv-spec-001",
    "started_at": "2026-07-28T00:00:00Z",
    "completed_at": "2026-07-28T00:00:01Z",
    "engine_version": "1.0.0",
    "feature_contract_version": "1.1.0",
    "gate_policy_version": "gate-policy-v1",
    "input_package_hashes": {
      "global_validator_input_sha256": "...",
      "context_evidence_sha256": "...",
      "attestation_evidence_sha256": "..."
    },
    "replay_spec_sha256": "..."
  }
}
```

### 12.2. Development invariant

```text
decision_policy.mode = DEVELOPMENT_HEURISTIC
→ decision không được AUTO_APPROVED
→ certificate_ref phải null
```

### 12.3. Frozen invariant

```text
decision_policy.mode = FROZEN_CALIBRATED
→ calibration_artifact_sha256 bắt buộc
→ threshold bắt buộc
→ threshold phải bằng operating point trong verified artifact
```

---

## 13. Terminology Certificate V1.1

Giữ:

```text
validity_context_refs
evidence_summary
gate_summary
decision_package_sha256
policy_version
```

Bổ sung:

```text
attestation_evidence_refs
threshold_version
sense_inventory_version
effective_sense_contract_sha256
```

### 13.1. Status allowed

```text
AUTO_APPROVED
PROVISIONAL
```

Không phát certificate cho:

```text
HUMAN_REVIEW
REJECTED
SPLIT_REQUIRED
```

### 13.2. Certificate binding

Certificate phải bind tới:

```text
candidate key
input contract hash
effective sense contract hash
C package hash
E package hash
gate result hash
decision package hash
calibration artifact hash nếu có
policy version
certificate version
```

---

## 14. Provenance V1.1

Common provenance hiện có:

```text
run_id
started_at
completed_at
component_id
component_version
policy_version
prompt_hashes
model_routes
source_artifact_hashes
raw_ledger_ref
notes
```

V1.1 bổ sung:

```text
run_spec_id
execution_config_sha256
```

Lý do:

- phân biệt một run specification với từng execution;
- tránh collision khi chạy lại;
- bind đầy đủ cache/provider/config;
- hỗ trợ replay.

### 14.1. Raw ledger

Producer có provider calls phải lưu:

```text
raw_ledger_ref
```

Global Validator không cần raw provider content nhưng phải giữ refs/hashes từ upstream.

---

## 15. Migration V1.0 → V1.1

Release phải có:

```text
migrations/v1_0_0_to_v1_1_0.py
```

### 15.1. Migration behavior

- preserve mọi core field;
- đổi `schema_version` thành `1.1.0`;
- thêm optional fields bằng null/empty defaults;
- không tự tạo evidence;
- không tự tạo review hash;
- không tự suy diễn diagnostic values;
- canonicalize gate IDs;
- tạo migration provenance;
- recompute self hash.

### 15.2. Migration report

Mỗi payload migrated phải có sidecar:

```json
{
  "source_schema_version": "1.0.0",
  "target_schema_version": "1.1.0",
  "migration_tool_version": "1.0.0",
  "fields_added": [],
  "fields_renamed": [],
  "warnings": [],
  "source_sha256": "...",
  "target_sha256": "..."
}
```

---

## 16. Package structure

```text
terminology_contracts_v1_1/
├── README.md
├── AGENT_RULES.md
├── CHANGELOG.md
├── VERSION_MATRIX.md
├── RELEASE_NOTES_V1_1.md
├── manifest.json
├── CHECKSUMS.sha256
├── pyproject.toml
│
├── schemas/
│   ├── legacy/
│   │   └── v1.0.0/
│   ├── v1.1.0/
│   └── current/
│
├── registries/
│   ├── feature_contract_v1.1.0.json
│   ├── gate_registry_v1.1.0.json
│   └── schema_registry_v1.1.0.json
│
├── migrations/
│   ├── v1_0_0_to_v1_1_0.py
│   └── README.md
│
├── examples/
│   ├── valid/
│   │   ├── v1.0.0/
│   │   └── v1.1.0/
│   └── invalid/
│
├── python/
│   └── terminology_contracts/
│       ├── validation.py
│       ├── canonical.py
│       ├── integrity.py
│       ├── migration.py
│       ├── registries.py
│       └── cli.py
│
├── tests/
│   ├── test_schema_validation.py
│   ├── test_candidate_join.py
│   ├── test_gate_invariants.py
│   ├── test_calibration_seal.py
│   ├── test_development_mode.py
│   ├── test_certificate_binding.py
│   ├── test_migration_v1_0_to_v1_1.py
│   └── test_dataset_mapping_fixtures.py
│
└── docs/
    ├── INTEGRATION_GUIDE.md
    ├── PRODUCER_GUIDE_C.md
    ├── PRODUCER_GUIDE_E.md
    ├── CONSUMER_GUIDE_GLOBAL_VALIDATOR.md
    ├── CONSUMER_GUIDE_TAC.md
    └── COMPATIBILITY_MATRIX.md
```

---

## 17. Contract tests bắt buộc

### 17.1. Candidate join

```text
candidate_id mismatch → reject
candidate_version mismatch → reject
sense_id mismatch → reject
scope_id mismatch → reject
dataset manifest hash mismatch → reject
effective sense contract hash mismatch → reject
input contract hash mismatch → reject
```

### 17.2. Gate tests

```text
missing_contrastive_context accepted by schema
incomplete_context_type_coverage accepted by schema
attestation_unjudgeable accepted by schema
triggered=false + action!=NONE rejected
triggered=true + action=NONE rejected hoặc warning theo pre-registered rule
```

### 17.3. Development policy

```text
DEVELOPMENT_HEURISTIC + AUTO_APPROVED → invalid
DEVELOPMENT_HEURISTIC + certificate_ref != null → invalid
```

### 17.4. Calibration

```text
fake SHA only → reject
invalid canonical hash → reject
unknown feature name → reject
threshold differs from artifact → reject
dataset hash mismatch → reject
gate policy mismatch → reject
```

### 17.5. Certificate

```text
AUTO_APPROVED → certificate valid
PROVISIONAL → certificate valid
HUMAN_REVIEW → certificate invalid
REJECTED → certificate invalid
SPLIT_REQUIRED → certificate invalid
missing decision binding → invalid
```

### 17.6. Migration

```text
all valid V1.0 fixtures migrate to valid V1.1
all migrated payloads preserve candidate identity
source hash and target hash differ and are recorded
migration is deterministic
second migration is idempotent hoặc bị từ chối rõ ràng
```

### 17.7. Dataset mapping

Dùng V3 và development pilot để kiểm tra:

```text
candidate_id mapping
sense_id mapping
scope_id mapping
sense inventory version
dataset manifest hash
effective sense contract placeholder/review binding
```

Contract runtime không được phụ thuộc vào storage layout của dataset.

---

## 18. Deliverables

Agent phải trả:

```text
terminology_contracts_v1_1.zip
terminology_contracts_v1_1.zip.sha256
terminology_contracts_v1_1_audit.json
terminology_contracts_v1_0_to_v1_1_diff.md
junit.xml
commands.txt
```

`audit.json` tối thiểu gồm:

```text
file count
schema count
fixture count
test count
test result
manifest verification
checksum verification
migration result
credential scan result
pyc/cache scan result
```

---

## 19. Definition of Done

Release chỉ được chấp nhận khi:

1. package version là `1.1.0`;
2. V1.0 được lưu ở legacy;
3. V1.1 có schema registry;
4. canonical names được khóa;
5. ba gate còn thiếu đã được thêm;
6. Global Decision có run/replay metadata;
7. certificate có attestation refs và binding đầy đủ;
8. calibration verifier kiểm tra artifact thật;
9. migration V1.0 → V1.1 deterministic;
10. toàn bộ valid fixtures pass;
11. toàn bộ invalid fixtures bị reject đúng;
12. dataset mapping smoke test pass;
13. không có secret, `.pyc`, `__pycache__`;
14. ZIP, checksum, audit và JUnit đầy đủ;
15. không gọi API bên ngoài.

---

## 20. Những gì gửi cho Contract Steward Agent

Bắt buộc:

```text
terminology_contracts_v1(1).zip
Kien_truc_Terminology_Contracts_V1_1.md
Kien_truc_Global_Terminology_Validator_Hard_Gates_V1.md
Bao_cao_kien_truc_kiem_dinh_thuat_ngu_v2.docx
Kien_truc_Context_Substitution_Test_v2.md
Kien_truc_Vietnamese_Attestation_Evidence_v1.md
d2l_context_support_set_validation_ready_v3.zip
pilot_dev_only_v1_1.zip
```

Khuyến nghị gửi thêm:

```text
Code_review_Context_Substitution_V2_1.md
Code_review_Vietnamese_Attestation_Evidence_V1.md
pilot_normalized_review_pack_v1_2.zip
```

Review pack chỉ để hiểu handoff; không coi V1.2 là human-reviewed authority cuối.

---

## 21. Prompt giao agent

```text
Bạn là Contract Steward Agent độc lập.

Nhiệm vụ là nâng terminology_contracts_v1.0.0 lên
terminology_contracts_v1.1.0 theo Kien_truc_Terminology_Contracts_V1_1.md.

Contract này là authority chung cho Dataset Adapter, Context Substitution,
Vietnamese Attestation, Global Validator, Calibration và TAC.

Không sửa thuật toán C/E, không đặt trọng số, không đặt threshold, không tạo nhãn
người và không gọi API ngoài.

Giữ thay đổi ở mức tối thiểu nhưng đủ để:
- khóa canonical naming;
- thêm các gate còn thiếu;
- bổ sung run/replay provenance;
- seal và verify CalibrationArtifact thật;
- bind certificate đầy đủ;
- hỗ trợ migration V1.0 → V1.1;
- kiểm tra mapping với dataset V3 và development pilot.

Phải bảo tồn schema V1.0 trong legacy, tạo fixtures hợp lệ/không hợp lệ,
contract tests, migration tests, checksum, audit JSON, JUnit và diff report.

Mọi producer/consumer phải giao tiếp qua schema V1.1, không phụ thuộc
implementation nội bộ hoặc raw dataset layout.
```
