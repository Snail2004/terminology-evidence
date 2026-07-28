# KIẾN TRÚC THUẬT TOÁN GLOBAL TERMINOLOGY VALIDATOR V1.1

**Trạng thái:** Agent-ready implementation specification
**Tên module:** Global Terminology Validator
**Phiên bản kiến trúc:** `global-validator-algorithm-v1.1.0`
**Contract authority:** `terminology_contracts_v1` tại tag `contracts-v1.1.0`
**Feature contract:** `1.1.0`
**Gate registry:** `1.1.0`
**Gate policy:** sealed `GatePolicyArtifactV1`
**Ngôn ngữ triển khai đề xuất:** Python 3.11+
**Runtime:** deterministic, zero-provider-call, fail-closed, replayable

> Tài liệu này thay thế phần thuật toán trong
> `Kien_truc_Global_Terminology_Validator_Hard_Gates_V1.md` khi có khác biệt
> với Terminology Contracts V1.1.0 đã freeze.

---

## 1. Mục tiêu

Global Terminology Validator là tầng quyết định trung tâm, nhận các artifact đã
được chuẩn hóa từ Dataset Adapter, Context Substitution và Vietnamese
Attestation.

Nó thực hiện:

```text
contract verification
→ exact identity join
→ producer gate-signal projection
→ constraint gate projection
→ sealed gate-policy application
→ feature assembly
→ calibrated score replay
→ deterministic decision resolution
→ decision package sealing
→ certificate exact projection
→ bundle verification
```

Nó không thực hiện:

- tìm context;
- dịch thử;
- tìm kiếm web;
- đánh giá snippet;
- tạo nhãn người;
- sửa sense definition;
- thay đổi candidate;
- tự đặt trọng số;
- tự đặt threshold;
- đọc raw dataset;
- gọi API hoặc LLM;
- sửa common contract;
- tự chọn variant hoặc scope khi phát certificate.

---

## 2. Authority và thứ tự ưu tiên

Khi code, tài liệu hoặc fixture mâu thuẫn, dùng thứ tự:

```text
1. Tag authority contracts-v1.1.0
2. Schema, registries, policies và semantic validators trong terminology_contracts_v1
3. Authority receipt do Main Manager phát hành
4. Tài liệu kiến trúc này
5. Các tài liệu Global Validator cũ
6. Implementation nội bộ của agent
```

Agent không được hard-code lại schema hoặc registry vào module riêng.

Các file authority phải được load từ package chung:

```text
terminology_contracts_v1/
├── schemas/v1.1.0/
├── registries/feature_contract_v1.1.0.json
├── registries/gate_registry_v1.1.0.json
├── policies/gate_policy_v1.0.0.json
└── python/terminology_contracts/
```

---

## 3. Ranh giới hệ thống

### 3.1. Luồng hợp lệ

```text
Dataset V3 / Pilot / Methodology companion
                ↓
          Dataset Adapter
                ↓
EffectiveSenseContractV1
FrozenCandidateContractV1
ConstraintEvidencePackageV1
                ↓
       ┌────────┴────────┐
       ↓                 ↓
Context Substitution     Vietnamese Attestation
       ↓                 ↓
ContextEvidencePackageV1 AttestationEvidencePackageV1
       └────────┬────────┘
                ↓
       Global Input Assembler
                ↓
       GlobalValidatorInputV1
                ↓
       Global Terminology Validator
                ↓
GlobalDecisionPackageV1
                ↓
TerminologyCertificateV1
                ↓
              TAC
```

### 3.2. Luồng bị cấm

```text
Global Validator → raw dataset
Global Validator → internal C engine
Global Validator → internal E engine
Global Validator → web/search provider
Global Validator → LLM Judge
Global Validator → mutable glossary store
```

---

## 4. Đơn vị quyết định

Mỗi decision áp dụng cho đúng một candidate contract:

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

Không join theo:

```text
row order
array index
source_term một mình
candidate_vi một mình
normalized string một mình
```

---

## 5. Input bắt buộc

Runtime chỉ nhận:

```text
GlobalValidatorInputV1
schema_version = 1.1.0
```

Input native COMPLETE phải chứa:

```text
candidate_key
input_contract_sha256
effective_sense_contract
frozen_candidate_contract
constraint_evidence
context_evidence
attestation_evidence
optional_probes
assembly_metadata
integrity
```

### 5.1. Ý nghĩa từng artifact

| Artifact | Producer | Vai trò |
|---|---|---|
| `EffectiveSenseContractV1` | Dataset/Sense authority | Definition, POS, scope và review status |
| `FrozenCandidateContractV1` | Dataset Adapter | Candidate bất biến và input content binding |
| `ConstraintEvidencePackageV1` | Dataset/constraint adapter | Sense review, polysemy, collision |
| `ContextEvidencePackageV1` | Agent C | Context features, support set, C gate signals |
| `AttestationEvidencePackageV1` | Agent E | E features, accepted evidence, E gate signals |
| `OptionalProbePackageV1` | Probe adapter | R/Q, mặc định không có |
| `assembly_metadata` | Input assembler | Hash của toàn bộ source packages |

---

## 6. Output

### 6.1. Output chính

```text
GateResultSetV1
GlobalDecisionPackageV1
TerminologyCertificateV1 | null
GlobalRunAudit
```

### 6.2. Năm trạng thái

```text
AUTO_APPROVED
PROVISIONAL
HUMAN_REVIEW
REJECTED
SPLIT_REQUIRED
```

### 6.3. Quy tắc certificate

| Mode | Decision | Certificate |
|---|---|---|
| `DEVELOPMENT_HEURISTIC` | mọi decision | Không phát |
| `FROZEN_CALIBRATED` | `AUTO_APPROVED` | Phát COMPLETE |
| `FROZEN_CALIBRATED` | `PROVISIONAL` | Phát COMPLETE, scope-limited |
| `FROZEN_CALIBRATED` | `HUMAN_REVIEW` | Không phát |
| `FROZEN_CALIBRATED` | `REJECTED` | Không phát |
| `FROZEN_CALIBRATED` | `SPLIT_REQUIRED` | Không phát |

Mọi certificate COMPLETE, kể cả `PROVISIONAL`, phải bind calibration artifact thật.

---

## 7. Kiến trúc module

```text
global_terminology_validator/
├── pyproject.toml
├── README.md
├── AGENTS.md
│
├── global_validator/
│   └── v1/
│       ├── engine.py
│       ├── config.py
│       ├── errors.py
│       │
│       ├── authority/
│       │   ├── receipt.py
│       │   ├── loader.py
│       │   └── verifier.py
│       │
│       ├── input/
│       │   ├── loader.py
│       │   ├── joiner.py
│       │   └── binding.py
│       │
│       ├── gates/
│       │   ├── signal_projection.py
│       │   ├── constraint_projection.py
│       │   ├── policy_loader.py
│       │   ├── builder.py
│       │   └── precedence.py
│       │
│       ├── features/
│       │   ├── registry_loader.py
│       │   ├── assembler.py
│       │   └── selector.py
│       │
│       ├── calibration/
│       │   ├── loader.py
│       │   ├── verifier.py
│       │   └── scorer.py
│       │
│       ├── decision/
│       │   ├── resolver.py
│       │   ├── package_builder.py
│       │   └── validator.py
│       │
│       ├── certificates/
│       │   ├── issuer.py
│       │   ├── projector.py
│       │   └── bundle_verifier.py
│       │
│       ├── audit/
│       │   ├── run_record.py
│       │   ├── replay.py
│       │   └── canonical.py
│       │
│       └── cli.py
│
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── adversarial/
│   └── replay/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── GATE_PROJECTION.md
    ├── CALIBRATION_HANDOFF.md
    ├── CERTIFICATE_ISSUANCE.md
    └── VERSION_MATRIX.md
```

---

## 8. Hai execution modes

## 8.1. `DEVELOPMENT_HEURISTIC`

Mục tiêu:

- kiểm tra join;
- kiểm tra hard gates;
- inspect feature vector;
- chạy fixture và ablation;
- kiểm tra integration C/E;
- không tạo scientific approval.

Invariant:

```text
approval_score = null
AUTO_APPROVED bị cấm
certificate_ref = null
certificate không được phát
CalibrationArtifact không bắt buộc
```

Resolution mặc định khi không có blocking gate:

```text
decision = PROVISIONAL
reason = DEVELOPMENT_NO_FROZEN_CALIBRATION
```

Không tự tạo heuristic score.

## 8.2. `FROZEN_CALIBRATED`

Chỉ mở khi load được artifact thật:

```text
CalibrationArtifactV1
verification_status = SEALED
model_type = LOGISTIC_REGRESSION
feature_contract_version = 1.1.0
gate_policy_artifact_sha256 khớp
self_sha256 hợp lệ
```

Verifier phải kiểm tra:

- schema;
- strict finite numbers;
- canonical self-hash;
- development dataset hash;
- validation dataset hash;
- feature names;
- coefficient coverage;
- link function `LOGIT`;
- operating point;
- threshold;
- numerical tolerance;
- gate policy version;
- gate policy hash;
- threshold stability metadata khi có.

Không chấp nhận:

```text
một chuỗi SHA nhưng không có file
UNVERIFIED_LEGACY
model type khác logistic regression
unknown feature
missing coefficient
threshold khác operating point
policy hash mismatch
```

---

## 9. Thuật toán tổng thể

```python
def run_global_validator(
    input_path,
    mode,
    authority_receipt,
    gate_policy_path,
    feature_registry_path,
    calibration_path=None,
    output_dir=None,
):
    authority = load_and_verify_authority(authority_receipt)

    global_input = strict_load_json(input_path)
    verify_global_input_schema_and_semantics(
        global_input,
        authority=authority,
    )

    joined = join_and_verify_all_packages(global_input)

    gate_policy = load_and_verify_gate_policy(
        gate_policy_path,
        authority=authority,
    )

    gate_results = build_gate_result_set(
        joined=joined,
        gate_policy=gate_policy,
    )

    validate_gate_result_with_policy(
        gate_results,
        gate_policy,
    )

    assembled_features = assemble_features_from_registry(
        global_input=global_input,
        feature_registry_path=feature_registry_path,
    )

    if mode == "DEVELOPMENT_HEURISTIC":
        decision_features = {}
        approval_score = None
        decision = resolve_development_decision(gate_results)

    elif mode == "FROZEN_CALIBRATED":
        calibration = load_and_verify_calibration(
            calibration_path,
            authority=authority,
            gate_policy=gate_policy,
        )
        decision_features = select_exact_model_features(
            assembled_features,
            calibration.model.feature_names,
        )
        approval_score = replay_logistic_score(
            calibration,
            decision_features,
        )
        decision = resolve_frozen_decision(
            gate_results,
            approval_score,
            calibration.operating_point.threshold,
        )

    decision_package = build_and_seal_decision_package(
        global_input=global_input,
        gate_results=gate_results,
        decision_features=decision_features,
        approval_score=approval_score,
        decision=decision,
        mode=mode,
        calibration=calibration if mode == "FROZEN_CALIBRATED" else None,
        gate_policy=gate_policy,
        authority=authority,
    )

    verify_complete_decision_bundle(
        decision_package=decision_package,
        global_input=global_input,
        calibration=calibration if mode == "FROZEN_CALIBRATED" else None,
        gate_policy=gate_policy,
        feature_registry=feature_registry_path,
    )

    certificate = None
    if mode == "FROZEN_CALIBRATED" and decision in {
        "AUTO_APPROVED",
        "PROVISIONAL",
    }:
        certificate = issue_certificate_as_exact_projection(
            decision_package=decision_package,
            global_input=global_input,
            gate_policy=gate_policy,
            calibration=calibration,
        )

        verify_certificate_bundle(
            certificate=certificate,
            frozen_candidate=global_input.frozen_candidate_contract,
            effective_sense=global_input.effective_sense_contract,
            constraint_evidence=global_input.constraint_evidence,
            global_input=global_input,
            context_evidence=global_input.context_evidence,
            attestation_evidence=global_input.attestation_evidence,
            gate_result=gate_results,
            decision=decision_package,
            calibration=calibration,
            gate_policy=gate_policy,
        )

    persist_immutable_run(
        global_input,
        gate_results,
        decision_package,
        certificate,
    )

    return decision_package, certificate
```

---

## 10. Giai đoạn 0 — Authority bootstrap

Trước mỗi run, load authority receipt:

```json
{
  "contract_version": "1.1.0",
  "authority_tag": "contracts-v1.1.0",
  "authority_commit": "<MAIN_AUTHORITY_COMMIT>",
  "package_path": "terminology_contracts_v1/",
  "manifest_sha256": "<MANIFEST_SHA256>",
  "release_zip_sha256": "<RELEASE_ZIP_SHA256>",
  "gate_policy_artifact_sha256": "<GATE_POLICY_SHA256>",
  "feature_contract_version": "1.1.0"
}
```

Kiểm tra:

```text
contract_version == 1.1.0
feature_contract_version == 1.1.0
package manifest hợp lệ
gate policy hash khớp receipt
schema registry khớp package
không dùng RC path làm authority
```

Mismatch:

```text
abort run
không tạo GlobalDecisionPackage COMPLETE
không phát certificate
ghi AuthorityVerificationFailure
```

---

## 11. Giai đoạn 1 — Strict loading

JSON loader phải từ chối:

```text
NaN
Infinity
-Infinity
duplicate key nếu parser hỗ trợ phát hiện
trailing garbage
unknown schema_id
unknown schema_version
```

Không dùng parser cho phép non-finite number.

Pseudo:

```python
payload = strict_json_loads(path.read_text("utf-8"))
schema_validate_instance(payload)
semantic_errors = validate_instance(payload, schema_dir)
if semantic_errors:
    raise InputValidationError(semantic_errors)
```

---

## 12. Giai đoạn 2 — Self-hash và nested artifact verification

Xác minh:

```text
GlobalValidatorInput.integrity.self_sha256
EffectiveSenseContract.integrity.self_sha256
FrozenCandidateContract.integrity.self_sha256
ConstraintEvidencePackage.integrity.self_sha256
ContextEvidencePackage.integrity.self_sha256
AttestationEvidencePackage.integrity.self_sha256
OptionalProbePackage.integrity.self_sha256
```

`FrozenCandidateContract.input_contract_sha256` phải được tính từ toàn bộ nội
dung Frozen Candidate, loại trừ chính field hash đang tính.

Không tin `assembly_metadata.source_package_hashes` mù quáng. Tính lại hash của
các nested packages và so sánh.

Native input bắt buộc:

```text
assembly_metadata.binding_status = COMPLETE
frozen_candidate.binding_status = COMPLETE
constraint_evidence.binding_status = COMPLETE
```

`LEGACY_INCOMPLETE` chỉ dùng inspect/migration, không được vào frozen decision.

---

## 13. Giai đoạn 3 — Exact Contract Joiner

Tất cả nested packages phải khớp exact:

```text
candidate_key
input_contract_sha256
```

Các trường trong candidate key phải khớp:

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

Các binding bổ sung:

```text
EffectiveSense self hash
    == candidate_key.effective_sense_contract_sha256

FrozenCandidate candidate_key
    == Global Input candidate_key

ConstraintEvidence candidate_key
    == Global Input candidate_key

C candidate_key
    == Global Input candidate_key

E candidate_key
    == Global Input candidate_key
```

### 13.1. Fail-closed behavior

Nếu input chưa tạo thành một `GlobalValidatorInputV1` semantic-valid:

```text
run status = INVALID_INPUT
decision package = null
certificate = null
```

Không cố normalize rồi tiếp tục.

`input_contract_mismatch` observation trong một COMPLETE GateResultSet hợp lệ
phải là `triggered=false`; mismatch thật bị chặn trước authority decision.

---

## 14. Giai đoạn 4 — Gate signal projection

Một COMPLETE `GateResultSetV1` phải có đúng 12 gate IDs, mỗi gate xuất hiện một
lần.

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

### 14.1. Tín hiệu do C sở hữu

C phải xuất đúng 7 signals:

```text
concept_mismatch
wrong_sense
contradiction
judge_disagreement
insufficient_evidence
missing_contrastive_context
incomplete_context_type_coverage
```

### 14.2. Tín hiệu do E sở hữu

E phải xuất đúng 5 signals:

```text
concept_mismatch
contradiction
judge_disagreement
insufficient_evidence
attestation_unjudgeable
```

### 14.3. Merge producer signals

Cho mỗi gate:

```python
assertions = all C/E signals where:
    gate_id == current_gate
    and asserted is True

triggered = len(assertions) > 0
source_modules = unique producer modules
reason_codes = stable_unique_union(all assertion reason_codes)
evidence_refs = stable_unique_union(all assertion evidence_refs)
```

Không được:

- bỏ module đã assert;
- bỏ reason code;
- bỏ evidence ref;
- thay `asserted=true` thành `triggered=false`;
- tự kích hoạt producer-owned gate khi không có assertion, trừ khi cùng gate có
  nguồn constraint/global được contract cho phép.

### 14.4. Stable ordering

Để reproducible:

```text
gate observations: theo gate registry order
source_modules: theo registry order
reason_codes: lexical order
evidence_refs: canonical JSON order hoặc stable source order
```

---

## 15. Giai đoạn 5 — Constraint projection

Từ `ConstraintEvidencePackageV1`:

```text
sense_review.status != VERIFIED
→ sense_definition_unverified = true

polysemy_resolution.status == UNRESOLVED
→ unresolved_polysemy = true

target_collision.status != CLEAR
→ target_collision = true
```

### 15.1. Sense review

```text
VERIFIED   → gate false
UNVERIFIED → gate true
```

Evidence ref lấy từ:

```text
sense_review.review_artifact_ref
```

### 15.2. Polysemy

```text
RESOLVED_SINGLE → false
RESOLVED_SPLIT  → false cho candidate sense đã tách
UNRESOLVED      → true
```

Evidence ref:

```text
polysemy_resolution.authority_ref
```

### 15.3. Target collision

```text
CLEAR       → false
COLLISION   → true
UNJUDGEABLE → true
```

Khi collision hash tồn tại:

```text
collision_index_sha256 phải khớp file thật
collision_index_ref.sha256 phải khớp file thật
```

Global runtime không tự quét raw dataset để tìm collision.

---

## 16. Giai đoạn 6 — Gate Policy application

Load sealed:

```text
GatePolicyArtifactV1
```

Không hard-code action trong resolver.

Policy V1.1 hiện quy định:

| Gate | Allowed actions |
|---|---|
| `input_contract_mismatch` | `FATAL_REJECT` |
| `sense_definition_unverified` | `ESCALATE_HUMAN` |
| `unresolved_polysemy` | `FATAL_SPLIT`, `ESCALATE_HUMAN` |
| `concept_mismatch` | `FATAL_REJECT` |
| `wrong_sense` | `FATAL_REJECT`, `FATAL_SPLIT` |
| `contradiction` | `FATAL_REJECT`, `ESCALATE_HUMAN` |
| `target_collision` | `ESCALATE_HUMAN` |
| `judge_disagreement` | `ESCALATE_HUMAN` |
| `insufficient_evidence` | `CAP_PROVISIONAL`, `ESCALATE_HUMAN` |
| `missing_contrastive_context` | `CAP_PROVISIONAL`, `ESCALATE_HUMAN` |
| `incomplete_context_type_coverage` | `CAP_PROVISIONAL`, `ESCALATE_HUMAN` |
| `attestation_unjudgeable` | `CAP_PROVISIONAL`, `ESCALATE_HUMAN` |

### 16.1. Action selection

Allowed action set không có nghĩa engine được tùy ý chọn.

Action selection phải đến từ một versioned deterministic policy config, ví dụ:

```json
{
  "policy_id": "global-gate-resolution-v1",
  "policy_version": "1.0.0",
  "action_selection": {
    "unresolved_polysemy": {
      "UNRESOLVED": "FATAL_SPLIT"
    },
    "wrong_sense": {
      "C_ASSERTED": "FATAL_REJECT",
      "BOUNDARY_SPLIT_REQUIRED": "FATAL_SPLIT"
    },
    "contradiction": {
      "CRITICAL_CONFIRMED": "FATAL_REJECT",
      "DISPUTED": "ESCALATE_HUMAN"
    },
    "insufficient_evidence": {
      "LOW_COVERAGE": "CAP_PROVISIONAL",
      "NO_JUDGEABLE_EVIDENCE": "ESCALATE_HUMAN"
    }
  }
}
```

Policy config này:

- không được vượt allowed actions của sealed GatePolicy;
- phải versioned;
- phải bind vào `execution_config_sha256`;
- không được sửa sau khi mở test;
- không phải calibration threshold.

### 16.2. Non-triggered gates

```text
triggered = false
→ action = NONE
→ reason_codes = []
→ evidence_refs = []
```

### 16.3. Triggered gates

```text
triggered = true
→ action != NONE
→ reason_codes không rỗng
→ evidence_refs không rỗng
```

---

## 17. Gate precedence

Canonical precedence:

```text
FATAL_SPLIT
> FATAL_REJECT
> ESCALATE_HUMAN
> CAP_PROVISIONAL
> NONE
```

Algorithm:

```python
def highest_blocking_action(observations):
    triggered_actions = {
        obs.action
        for obs in observations
        if obs.triggered
    }

    for action in [
        "FATAL_SPLIT",
        "FATAL_REJECT",
        "ESCALATE_HUMAN",
        "CAP_PROVISIONAL",
        "NONE",
    ]:
        if action in triggered_actions:
            return action

    return "NONE"
```

Không dùng số severity tự đặt.

---

## 18. Giai đoạn 7 — Feature Assembler

Load:

```text
registries/feature_contract_v1.1.0.json
```

Không viết mapping bằng tay trong engine.

### 18.1. Core C features

```text
features.C_mean
    → C_mean

features.C_min
    → C_min

features.C_max
    → C_max

features.C_range
    → C_range

features.evidence_coverage
    → C_evidence_coverage

features.required_context_type_coverage
    → C_required_context_type_coverage

features.judge_agreement
    → C_judge_agreement

features.valid_context_count
    → C_valid_context_count

features.pass_count
    → C_pass_count

features.minor_count
    → C_minor_count

features.fail_count
    → C_fail_count
```

### 18.2. Core E features

```text
features.E_authority
    → E_authority

features.E_independence
    → E_independence

features.E_domain
    → E_domain

features.E_concept
    → E_concept

features.E_conventionality
    → E_conventionality

features.E_coverage
    → E_coverage
```

### 18.3. Diagnostic features

Chỉ map khi tồn tại:

```text
diagnostics.replacement_rate
    → C_replacement_rate

diagnostics.contrastive_boundary_support
    → C_contrastive_boundary_support

diagnostics.strong_positive_cluster_count
    → E_strong_positive_cluster_count

diagnostics.conflict_ratio
    → E_conflict_ratio
```

Diagnostic không tự động tham gia model.

### 18.4. Optional probes

```text
OptionalProbe R AVAILABLE → R_score
OptionalProbe Q AVAILABLE → Q_score
```

R/Q chỉ tham gia nếu tên xuất hiện trong:

```text
CalibrationArtifact.model.feature_names
```

### 18.5. Numeric invariants

Mọi feature:

```text
không boolean
finite number
không NaN/Infinity
```

Continuous features theo schema phải nằm trong `[0,1]`.

Count giữ dạng count, không tự normalize.

---

## 19. Giai đoạn 8 — Model feature selection

Trong frozen mode:

```python
assembled = assemble_decision_features(global_input, feature_registry)

feature_names = calibration.model.feature_names

decision_features = select_model_features(
    assembled,
    feature_names,
)
```

Yêu cầu exact set:

```text
decision_features.keys == model.feature_names
```

Không chấp nhận:

```text
thiếu feature
feature thừa
unknown feature
duplicate feature
null feature
non-finite feature
```

---

## 20. Giai đoạn 9 — Logistic score replay

V1.1 frozen mode chỉ hỗ trợ:

```text
model_type = LOGISTIC_REGRESSION
link_function = LOGIT
```

Với:

```text
z = intercept + Σ coefficient_i × feature_i
approval_score = sigmoid(z)
```

Stable sigmoid:

```python
def sigmoid(z):
    if z >= 0:
        return 1.0 / (1.0 + exp(-z))
    ez = exp(z)
    return ez / (1.0 + ez)
```

Score được tính bởi code, không lấy score do agent khác truyền.

So sánh score:

```text
abs(actual - replayed) <= numerical_tolerance
```

`approval_score` không được diễn giải là xác suất đúng tuyệt đối trừ khi luận văn
đã chứng minh calibration xác suất.

---

## 21. Giai đoạn 10 — Decision Resolver

### 21.1. Development mode

```python
if blocking == "FATAL_SPLIT":
    return SPLIT_REQUIRED
if blocking == "FATAL_REJECT":
    return REJECTED
if blocking == "ESCALATE_HUMAN":
    return HUMAN_REVIEW
if blocking == "CAP_PROVISIONAL":
    return PROVISIONAL
return PROVISIONAL
```

### 21.2. Frozen mode

```python
if blocking == "FATAL_SPLIT":
    return SPLIT_REQUIRED

if blocking == "FATAL_REJECT":
    return REJECTED

if blocking == "ESCALATE_HUMAN":
    return HUMAN_REVIEW

if blocking == "CAP_PROVISIONAL":
    return PROVISIONAL

if approval_score >= threshold:
    return AUTO_APPROVED

return PROVISIONAL
```

### 21.3. Invariants

```text
score cao không bù wrong_sense
score cao không bù concept_mismatch
score cao không bù contradiction
score cao không bù collision
score cao không bù unresolved_polysemy
```

---

## 22. Decision reasons

`decision_reasons` phải deterministic và machine-readable.

Ưu tiên:

1. reason cho blocking action cao nhất;
2. các triggered gate IDs;
3. mode/threshold reason.

Ví dụ:

```text
GATE_FATAL_REJECT
WRONG_SENSE
CONTEXT_JUDGE_WRONG_SENSE
```

Frozen no-gate:

```text
CALIBRATED_SCORE_AT_OR_ABOVE_THRESHOLD
```

Frozen dưới threshold:

```text
CALIBRATED_SCORE_BELOW_AUTO_APPROVAL_THRESHOLD
```

Development no-gate:

```text
DEVELOPMENT_NO_FROZEN_CALIBRATION
```

Không dùng free-text làm authority reason.

---

## 23. Giai đoạn 11 — GlobalDecisionPackage

Package phải bind:

```text
candidate_key
input_contract_sha256
context_evidence_sha256
attestation_evidence_sha256
GateResultSetV1
decision_features
approval_score
decision
decision_reasons
decision_policy
certificate_ref
run_metadata
integrity
```

### 23.1. Development decision policy

```json
{
  "mode": "DEVELOPMENT_HEURISTIC",
  "calibration_artifact_sha256": null,
  "threshold": null,
  "feature_contract_version": "1.1.0",
  "gate_policy_artifact_sha256": "<POLICY_HASH>"
}
```

### 23.2. Frozen decision policy

```json
{
  "mode": "FROZEN_CALIBRATED",
  "calibration_artifact_sha256": "<CALIBRATION_HASH>",
  "threshold": 0.84,
  "feature_contract_version": "1.1.0",
  "gate_policy_artifact_sha256": "<POLICY_HASH>"
}
```

Threshold phải đúng bằng operating point trong calibration artifact.

---

## 24. Run metadata và replay binding

Mỗi decision phải lưu:

```text
binding_status
global_run_id
global_run_spec_id
started_at
completed_at
engine_version
execution_config_sha256
feature_contract_version
gate_policy_version
gate_policy_artifact_sha256
input_package_hashes
replay_spec_sha256
```

`input_package_hashes` gồm:

```text
global_validator_input_sha256
context_evidence_sha256
attestation_evidence_sha256
effective_sense_contract_sha256
frozen_candidate_contract_sha256
constraint_evidence_sha256
gate_result_sha256
gate_policy_artifact_sha256
```

### 24.1. Replay spec

Replay hash bind:

```text
candidate_key
input_contract_sha256
decision_policy
decision_features
gate policy version
gate policy hash
input package hashes
global_run_spec_id
engine_version
execution_config_sha256
feature_contract_version
```

### 24.2. Replay invariant

Replay phải chạy từ artifact đã lưu:

```text
GlobalValidatorInput
GatePolicyArtifact
Feature Registry
CalibrationArtifact khi frozen
execution config
```

Không gọi lại C/E và không đọc dataset.

Kết quả replay phải giống:

```text
GateResultSet self hash
decision features
approval score
decision
decision reasons
DecisionPackage self hash
```

Timestamps và run ID có thể khác nếu chạy một execution mới; semantic output phải
giống.

---

## 25. Giai đoạn 12 — Certificate Issuer

Certificate không phải object do issuer tự sáng tác. Nó là exact projection từ
verified bundle.

### 25.1. Candidate fields

Lấy nguyên từ verified candidate key.

### 25.2. Application fields

```text
allowed_variants
    = FrozenCandidate.surfaces.validated_variants_vi

forbidden_candidates
    = FrozenCandidate.surfaces.rejected_variants_vi

scope_note
    = FrozenCandidate.scope_note
```

Không thêm, xóa hoặc xếp lại tùy ý.

### 25.3. Context refs

```text
validity_context_refs
    = ContextEvidence.support_set.positive_support_refs
```

Không dùng:

```text
contrastive_refs
negative_or_boundary_refs
```

### 25.4. Attestation refs

`attestation_evidence_refs` phải là refs thuộc:

```text
AttestationEvidence.accepted_evidence_refs
```

Policy đơn giản nhất cho V1.1:

```text
certificate.attestation_evidence_refs
    = AttestationEvidence.accepted_evidence_refs
```

Không lấy rejected evidence.

### 25.5. Evidence summary

```text
evidence_summary.C_mean
    = ContextEvidence.features.C_mean

evidence_summary.E_features
    = AttestationEvidence.features
```

### 25.6. Threshold version

```text
threshold_version
    = CalibrationArtifact.operating_point.operating_point_id
```

### 25.7. Gate summary

```text
gate_summary
    = sorted triggered gate IDs
```

### 25.8. Artifact hashes

Certificate COMPLETE bind:

```text
input_contract_sha256
context_evidence_sha256
attestation_evidence_sha256
gate_result_sha256
decision_package_sha256
calibration_artifact_sha256
global_validator_input_sha256
frozen_candidate_contract_sha256
constraint_evidence_sha256
gate_policy_artifact_sha256
effective_sense_contract_sha256
```

### 25.9. Time ordering

```text
certificate.issued_at >= decision.run_metadata.completed_at
```

Nên kiểm tra bổ sung:

```text
run_metadata.started_at <= run_metadata.completed_at
producer provenance.started_at <= producer provenance.completed_at
```

---

## 26. Certificate bundle verification

Sau khi issuer tạo certificate, bắt buộc gọi official:

```python
verify_certificate_bundle(...)
```

Truyền đầy đủ:

```text
certificate path
Frozen Candidate path
Effective Sense path
Constraint Evidence path
Global Input path
C package path
E package path
GateResult path
Decision path
Calibration path
GatePolicy path
Collision index path khi có
Feature Registry path
TAC path khi verify TAC
```

Chỉ persist certificate authority khi:

```text
errors == []
```

Structural schema validation một mình không đủ.

---

## 27. Error model

### 27.1. Error categories

```text
AUTHORITY_ERROR
SCHEMA_ERROR
INTEGRITY_ERROR
JOIN_ERROR
GATE_PROJECTION_ERROR
GATE_POLICY_ERROR
FEATURE_ASSEMBLY_ERROR
CALIBRATION_ERROR
DECISION_REPLAY_ERROR
CERTIFICATE_BINDING_ERROR
REPLAY_ERROR
IO_ERROR
```

### 27.2. Fail-closed rules

Bất kỳ error nào trước decision:

```text
không phát certificate
không AUTO_APPROVED
run status FAILED
```

Bất kỳ error nào khi certificate issuance:

```text
decision package có thể giữ để audit
certificate bị xóa hoặc không publish
run status CERTIFICATE_FAILED
```

Không swallow exception và tiếp tục.

---

## 28. Immutability và storage

Mỗi run tạo thư mục mới:

```text
runs/<global_run_id>/
├── input/
│   ├── global_validator_input.json
│   ├── gate_policy.json
│   ├── feature_registry.json
│   └── calibration.json
├── output/
│   ├── gate_result_set.json
│   ├── global_decision_package.json
│   └── terminology_certificate.json
├── audit/
│   ├── run.json
│   ├── validation_errors.json
│   ├── feature_assembly.json
│   ├── score_replay.json
│   └── certificate_bundle.json
└── CHECKSUMS.sha256
```

Không ghi đè run cũ.

Raw C/E provider responses không cần copy vào Global run; chỉ giữ refs và package
hashes.

---

## 29. Global Input Assembler

Assembler có thể nằm ngoài runtime engine hoặc là CLI riêng.

Nó nhận:

```text
EffectiveSenseContract
FrozenCandidateContract
ConstraintEvidencePackage
ContextEvidencePackage
AttestationEvidencePackage
OptionalProbePackage[]
```

Nó:

1. verify từng artifact;
2. verify candidate key;
3. verify input binding;
4. embed exact payload;
5. tính source package hashes;
6. tạo `assembly_metadata`;
7. seal `GlobalValidatorInputV1`.

Assembler không đọc dataset raw. Dataset Adapter phải hoàn thành mapping trước.

---

## 30. Dataset readiness

Dataset hiện đủ cho:

```text
adapter development
contract mapping tests
zero-API integration
development pilot 5 senses / 15 candidates
```

Global Validator không nhận trực tiếp:

```text
term_senses.jsonl
candidate files
contexts.jsonl
dataset ZIP
```

Nó chỉ nhận contract artifacts.

Các artifact chưa có human freeze có thể chạy development mode, nhưng không mở
frozen approval.

---

## 31. Calibration handoff

Global Agent được phép xây:

- CalibrationArtifact loader;
- verifier;
- score replay;
- threshold stability report reader;
- offline calibration utility tách riêng.

Global Agent không được:

- tự sinh human labels;
- dùng test set để fit;
- chọn threshold bằng trực giác;
- thay threshold sau khi mở hidden test.

Calibration release cần:

```text
development labels
validation labels
real C/E outputs
feature registry version
sealed gate policy hash
cluster bootstrap theo sense_id
operating point
precision lower bound
coverage
decision flip rate
```

Claim nên báo confidence interval, không chỉ point estimate.

---

## 32. Ablation và experiment modes

Runtime nên hỗ trợ:

```text
V1_CONTEXT_ONLY
V2_CONTEXT_PLUS_ATTESTATION
V3_EVIDENCE_NO_GATES
V4_EVIDENCE_PLUS_GATES
```

Nhưng ablation không được tạo artifact authority như production.

### 32.1. V1 Context only

- E features absent hoặc masked theo experiment config;
- không giả E evidence;
- không phát production certificate.

### 32.2. V2 C + E

- assemble C/E;
- gates disabled;
- chỉ experiment output.

### 32.3. V3 calibrated no gates

- score replay;
- gate set giữ để audit nhưng resolver ignore trong experiment branch;
- ghi rõ `experimental_non_authority=true`.

### 32.4. V4 proposed

- full gate precedence;
- full calibration;
- authority path.

Ablation outputs phải nằm trong namespace riêng:

```text
experiment_runs/
```

Không trộn với certified runs.

---

## 33. CLI

```bash
global-validator authority-verify \
  --receipt authority_receipt.json \
  --contracts-root terminology_contracts_v1/

global-validator assemble-input \
  --effective-sense effective_sense.json \
  --frozen-candidate frozen_candidate.json \
  --constraints constraint_evidence.json \
  --context-evidence C.json \
  --attestation-evidence E.json \
  --output global_input.json

global-validator validate-input \
  --input global_input.json \
  --gate-policy gate_policy.json \
  --feature-registry feature_contract_v1.1.0.json

global-validator run \
  --input global_input.json \
  --mode DEVELOPMENT_HEURISTIC \
  --gate-policy gate_policy.json \
  --feature-registry feature_contract_v1.1.0.json \
  --output-dir runs/

global-validator run \
  --input global_input.json \
  --mode FROZEN_CALIBRATED \
  --gate-policy gate_policy.json \
  --feature-registry feature_contract_v1.1.0.json \
  --calibration calibration.json \
  --output-dir runs/

global-validator replay \
  --run-dir runs/<global_run_id>

global-validator verify-decision \
  --decision decision.json \
  --global-input global_input.json \
  --gate-policy gate_policy.json \
  --feature-registry feature_contract_v1.1.0.json \
  --calibration calibration.json

global-validator verify-certificate-bundle \
  --bundle-dir runs/<global_run_id>
```

Exit codes:

```text
0 success
2 schema/contract error
3 integrity/hash error
4 join error
5 gate/policy error
6 calibration error
7 certificate error
8 replay mismatch
9 internal error
```

---

## 34. Test matrix bắt buộc

## 34.1. Authority tests

```text
wrong authority tag → fail
manifest mismatch → fail
gate policy hash mismatch → fail
feature contract version mismatch → fail
RC package used as authority → fail hoặc explicit non-authority mode
```

## 34.2. Strict JSON tests

```text
NaN → reject
Infinity → reject
-Infinity → reject
unknown property → reject
wrong schema version → reject
```

## 34.3. Join tests

```text
candidate_id mismatch → fail
candidate_version mismatch → fail
source_term mismatch → fail
candidate_vi mismatch → fail
sense_id mismatch → fail
scope_id mismatch → fail
sense inventory mismatch → fail
dataset manifest mismatch → fail
effective sense hash mismatch → fail
input contract hash mismatch → fail
nested self-hash mismatch → fail
```

## 34.4. Gate coverage tests

```text
GateResult thiếu một gate → reject
duplicate gate_id → reject
unknown gate → reject
triggered=false + action!=NONE → reject
triggered=true + action=NONE → reject
triggered gate thiếu reason → reject
triggered gate thiếu evidence ref → reject
```

## 34.5. C/E signal projection tests

```text
C wrong_sense=true nhưng gate=false → reject
C missing contrastive=true nhưng gate=false → reject
E unjudgeable=true nhưng gate=false → reject
C/E cùng assert concept_mismatch nhưng source module bị thiếu → reject
reason code producer bị bỏ → reject
evidence ref producer bị bỏ → reject
```

## 34.6. Constraint projection tests

```text
sense UNVERIFIED nhưng gate=false → reject
polysemy UNRESOLVED nhưng gate=false → reject
collision COLLISION nhưng gate=false → reject
collision UNJUDGEABLE nhưng gate=false → reject
collision index hash mismatch → reject
```

## 34.7. Gate policy tests

```text
wrong_sense + CAP_PROVISIONAL → reject
concept_mismatch + ESCALATE_HUMAN → reject
target_collision + FATAL_REJECT → reject
insufficient_evidence + FATAL_SPLIT → reject
policy self-hash mismatch → reject
policy missing gate rule → reject
```

## 34.8. Precedence tests

```text
FATAL_SPLIT + FATAL_REJECT → SPLIT_REQUIRED
FATAL_REJECT + ESCALATE_HUMAN → REJECTED
ESCALATE_HUMAN + CAP_PROVISIONAL → HUMAN_REVIEW
CAP_PROVISIONAL only → PROVISIONAL
NONE in development → PROVISIONAL
```

## 34.9. Development tests

```text
AUTO_APPROVED → reject
approval_score != null → reject
certificate_ref != null → reject
certificate emitted → fail test
```

## 34.10. Calibration tests

```text
missing file → fail
fake SHA → fail
bad self hash → fail
UNVERIFIED_LEGACY → fail
non-logistic model → fail
unknown feature → fail
missing model feature → fail
extra decision feature → fail
coefficient mismatch → fail
threshold mismatch → fail
gate policy mismatch → fail
dataset hash mismatch → fail
score replay mismatch → fail
```

## 34.11. Decision tests

```text
score 0.99 + wrong_sense → REJECTED
score 0.99 + unresolved_polysemy → SPLIT_REQUIRED
score 0.99 + collision → HUMAN_REVIEW
score >= threshold + no gates → AUTO_APPROVED
score < threshold + no gates → PROVISIONAL
```

## 34.12. Certificate tests

```text
development certificate → reject
HUMAN_REVIEW certificate → reject
REJECTED certificate → reject
SPLIT_REQUIRED certificate → reject
injected allowed variant → reject
removed blacklist entry → reject
expanded scope → reject
fabricated C_mean → reject
fabricated E features → reject
arbitrary threshold version → reject
contrastive validity ref → reject
negative validity ref → reject
issued before decision completion → reject
random artifact hash → reject
```

## 34.13. Replay tests

```text
same inputs → same gates/features/score/decision
changed execution config → replay hash changes
changed feature → replay hash changes
changed gate result → replay hash changes
changed policy hash → replay hash changes
replay makes 0 provider calls
```

---

## 35. Zero-API integration trên pilot

Input:

```text
5 senses
15 candidates
15 C packages
15 E packages
15 Frozen Candidate contracts
15 Constraint Evidence packages
```

Mỗi candidate chạy development mode.

Acceptance criteria:

```text
15 GlobalValidatorInput COMPLETE
15 GateResultSet COMPLETE
15 GlobalDecisionPackage valid
0 AUTO_APPROVED
0 certificates
0 API calls
0 join mismatch ngoài fixture cố ý
deterministic replay PASS
all hashes verified
```

Negative fixtures phải bao phủ:

```text
wrong sense
concept mismatch
polysemy unresolved
target collision
missing contrastive
incomplete C1–C5
E unjudgeable
insufficient evidence
judge disagreement
```

---

## 36. Defensive hardening khuyến nghị

Không chặn V1.1 nhưng nên triển khai:

### 36.1. Evidence reference type

```text
positive_support_refs → evidence_type CONTEXT
contrastive_refs → evidence_type CONTRASTIVE_CONTEXT
accepted E refs → evidence_type ATTESTATION_SOURCE
```

### 36.2. Support-set disjointness

Không cho cùng một evidence identity xuất hiện đồng thời trong:

```text
positive
contrastive
negative_or_boundary
```

### 36.3. Timestamp ordering

```text
started_at <= completed_at
issued_at >= decision.completed_at
```

### 36.4. Stable canonicalization

Mọi unordered semantic set phải được sort trước seal.

---

## 37. Logging và observability

Mỗi run ghi:

```text
run stage
start/end time
artifact path
artifact self hash
validation result
gate count
triggered gate count
highest action
feature count
mode
score khi frozen
threshold khi frozen
decision
certificate issued
replay status
```

Không log:

```text
API key
provider secret
raw credentials
full private paths khi xuất public audit
```

---

## 38. Security

- Không load pickle/joblib không tin cậy.
- Calibration model chỉ là JSON coefficients.
- Dùng safe relative paths.
- Không follow symlink ngoài artifact root.
- Không cho ZIP traversal.
- Không shell-execute nội dung từ artifact.
- Không import Python code từ release artifact ngoài installed authority package.
- Verify hash trước khi dùng file.

---

## 39. Performance

Global Validator không có provider call, nên mục tiêu:

```text
single candidate development run < 500 ms
single candidate frozen run < 1 s
15-candidate zero-API integration < 30 s
```

Không tối ưu trước correctness.

Cache được phép cho:

```text
parsed schemas
verified registries
verified gate policy
verified calibration artifact
```

Cache key phải gồm physical file hash.

---

## 40. Artifact bàn giao

Agent Global phải trả:

```text
global_validator_v1_1_integration_rc.zip
global_validator_v1_1_integration_rc.zip.sha256
global_validator_v1_1_audit.json
junit.xml
commands.txt
environment.json
static_scan.json
credential_scan.json
authority_verification_report.json
pilot_zero_api_summary.json
gate_projection_report.json
gate_policy_report.json
feature_assembly_report.json
decision_replay_report.json
certificate_bundle_report.json
VERSION_MATRIX.md
```

ZIP phải chứa:

```text
source
CLI
test source
fixtures
docs
reports
```

Không chứa:

```text
secret
API key
.pyc
__pycache__
local virtual environment
raw dataset
```

---

## 41. Definition of Done

Agent chỉ được báo hoàn thành khi:

1. dùng đúng tag `contracts-v1.1.0`;
2. authority receipt verify PASS;
3. runtime không đọc raw dataset;
4. runtime không import C/E internals;
5. strict JSON validation hoạt động;
6. exact join fail closed;
7. đủ đúng 12 gates;
8. C/E signal projection pass;
9. constraint projection pass;
10. sealed GatePolicy được load và verify;
11. feature assembler dùng registry machine-readable;
12. development mode không AUTO_APPROVED;
13. frozen calibration score replay chính xác;
14. decision resolver tuân precedence;
15. decision replay hash đầy đủ;
16. certificate là exact projection;
17. bundle verification pass;
18. 15-candidate zero-API integration pass;
19. deterministic replay pass;
20. JUnit và audit artifact đầy đủ;
21. không secret/cache;
22. chưa bật production AUTO_APPROVED nếu chưa có frozen human calibration.

---

## 42. Những việc chưa được làm ở giai đoạn đầu

Không:

- chạy toàn bộ 150 senses;
- fit threshold từ fixture;
- mở hidden test;
- phát production certificate;
- triển khai TAC engine trong cùng module;
- thêm R/Q mặc định;
- viết custom model ngoài logistic regression;
- tự thay đổi gate action policy;
- sửa common contract.

---

## 43. Thứ tự triển khai đề xuất

```text
Phase 1 — Authority loader + strict contract validation
Phase 2 — Global input joiner
Phase 3 — Gate projection + sealed policy
Phase 4 — Feature assembler
Phase 5 — Development resolver
Phase 6 — Decision package + replay
Phase 7 — Frozen calibration verifier/scorer
Phase 8 — Certificate exact projector + bundle verification
Phase 9 — CLI + audit packaging
Phase 10 — 15-candidate zero-API integration
```

Mỗi phase phải merge với tests trước khi sang phase kế.

---

## 44. Prompt giao trực tiếp cho Agent Global Validator

```text
Bạn là Agent Global Terminology Validator.

Hãy xây Global Terminology Validator theo:
- file Kien_truc_Thuat_toan_Global_Terminology_Validator_V1_1.md;
- contract authority tại tag contracts-v1.1.0;
- package terminology_contracts_v1/.

Contract authority có ưu tiên cao hơn mọi tài liệu cũ.

Runtime chỉ nhận GlobalValidatorInputV1 schema_version 1.1.0.
Không đọc raw dataset, không gọi C/E nội bộ, không gọi provider hoặc LLM.

Thực hiện theo thứ tự:

1. Xây Authority Loader và verify authority receipt, manifest, schema registry,
   feature registry và sealed GatePolicy.
2. Xây strict JSON loader và official schema/semantic validation.
3. Xây Contract Joiner kiểm tra exact candidate_key, input_contract_sha256,
   nested self hashes và assembly hashes. Mismatch phải fail closed.
4. Xây Gate Engine tạo đúng 12 observations:
   - project đầy đủ C/E gate_signals;
   - project sense review, polysemy và collision constraints;
   - preserve source_modules, reason_codes và evidence_refs;
   - load sealed GatePolicy và reject action không hợp lệ.
5. Xây Feature Assembler bằng machine-readable feature registry.
   Không hard-code mapping và không tạo scalar E_score.
6. Xây DEVELOPMENT_HEURISTIC:
   - approval_score = null;
   - cấm AUTO_APPROVED;
   - không phát certificate;
   - không có blocking gate thì PROVISIONAL.
7. Xây FROZEN_CALIBRATED:
   - chỉ load CalibrationArtifact SEALED thật;
   - chỉ LOGISTIC_REGRESSION;
   - exact model feature set;
   - replay score;
   - threshold lấy từ operating point;
   - chưa bật production nếu chưa có human-frozen calibration.
8. Xây deterministic Decision Resolver theo:
   FATAL_SPLIT > FATAL_REJECT > ESCALATE_HUMAN > CAP_PROVISIONAL > NONE.
9. Xây GlobalDecisionPackage với full run metadata, package hashes và replay hash.
10. Xây Certificate Issuer dưới dạng exact projection:
    - variants/blacklist/scope từ Frozen Candidate;
    - validity refs đúng bằng positive C support refs;
    - E refs từ accepted evidence;
    - C/E summary từ producer packages;
    - threshold version từ calibration operating point;
    - bind toàn bộ artifact hashes.
11. Bắt buộc gọi official verify_certificate_bundle trước khi publish certificate.
12. Xây CLI, immutable run storage, deterministic replay và audit reports.
13. Chạy zero-API integration trên 5 senses/15 candidates.
    Kết quả development bắt buộc: 15 decisions, 0 AUTO_APPROVED,
    0 certificates, 0 API calls, replay PASS.
14. Không sửa terminology_contracts_v1 và không copy schema vào module riêng.

Bàn giao:

global_validator_v1_1_integration_rc.zip
global_validator_v1_1_integration_rc.zip.sha256
global_validator_v1_1_audit.json
junit.xml
commands.txt
environment.json
static_scan.json
credential_scan.json
authority_verification_report.json
pilot_zero_api_summary.json
gate_projection_report.json
gate_policy_report.json
feature_assembly_report.json
decision_replay_report.json
certificate_bundle_report.json
VERSION_MATRIX.md

Báo lại:
- branch;
- commit hash;
- adopted authority tag/commit/manifest SHA;
- test summary;
- zero-API counts;
- replay status;
- phần còn chờ C/E packages, Dataset Adapter hoặc frozen calibration.
```

---

## 45. Kết luận

Global Terminology Validator không phải một LLM Judge bổ sung. Nó là một
deterministic authority engine:

```text
verified artifacts
→ hard constraints
→ registered features
→ frozen calibrated policy
→ replayable decision
→ exact certificate
```

Giá trị của module nằm ở việc không cho score, model hoặc implementation nội bộ
vượt qua các ranh giới đã được contract hóa.
